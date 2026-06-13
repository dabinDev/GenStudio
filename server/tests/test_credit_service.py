from __future__ import annotations

import os
import sys
import tempfile

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

db_path = os.path.join(tempfile.gettempdir(), "genstudio-credit-service-test.sqlite3")
if os.path.exists(db_path):
    os.remove(db_path)

os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["GENSTUDIO_SECRET_KEY"] = "test-secret"

from app.database import Base
from app.db_models import ApiKey, ModelGroup, SubModel, User


def make_db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_user(db: Session, email: str, external_id: str | None = None) -> User:
    user = User(
        external_user_id=external_id or email,
        email=email,
        nickname=email.split("@")[0],
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_model(
    db: Session,
    owner: User,
    *,
    capability: str = "image",
    is_public: bool = False,
    model_name: str = "demo-model",
) -> tuple[ModelGroup, SubModel]:
    api_key = ApiKey(
        user_id=owner.id,
        name="test key",
        base_url="https://api.example.com",
        api_key_ciphertext="cipher",
    )
    db.add(api_key)
    db.flush()
    model = ModelGroup(
        user_id=owner.id,
        api_key_id=api_key.id,
        name=f"{capability} model",
        vendor="Test",
        capability=capability,
        adapter="text-chat" if capability == "text" else "image-openai",
        description="",
        primary_sub_model_id="",
        is_public=is_public,
    )
    db.add(model)
    db.flush()
    sub_model = SubModel(
        model_group_id=model.id,
        api_key_id=api_key.id,
        model_name=model_name,
        display_name=model_name,
        capability=capability,
        adapter=model.adapter,
        is_primary=True,
        status="active",
    )
    db.add(sub_model)
    db.flush()
    model.primary_sub_model_id = sub_model.id
    db.commit()
    db.refresh(model)
    db.refresh(sub_model)
    return model, sub_model


def test_default_account_has_zero_balance() -> None:
    from app.credit_service import get_or_create_credit_account

    db = make_db()
    user = make_user(db, "artist@example.com")

    account = get_or_create_credit_account(db, user.id)

    assert account.balance == 0
    assert account.reserved_balance == 0
    assert account.total_recharged == 0
    assert account.total_spent == 0
    assert account.total_refunded == 0


def test_private_model_price_is_zero_even_when_default_is_positive() -> None:
    from app.credit_service import estimate_credit_price, set_capability_price

    db = make_db()
    owner = make_user(db, "owner@example.com")
    model, sub_model = make_model(db, owner, capability="image", is_public=False)
    set_capability_price(db, "image", 3)

    estimate = estimate_credit_price(db, user=owner, capability="image", model_group=model, sub_model=sub_model)

    assert estimate.price == 0
    assert estimate.source == "private_model"
    assert estimate.enabled is False


def test_public_model_uses_override_before_default() -> None:
    from app.credit_service import estimate_credit_price, set_capability_price, set_model_price

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com")
    model, sub_model = make_model(db, admin, capability="video", is_public=True)
    set_capability_price(db, "video", 6)
    set_model_price(db, admin, model.id, 9)

    estimate = estimate_credit_price(db, user=admin, capability="video", model_group=model, sub_model=sub_model)

    assert estimate.price == 9
    assert estimate.source == "model_override"
    assert estimate.enabled is True


def test_admin_adjust_credits_requires_reason_and_blocks_negative_balance() -> None:
    from app.credit_service import admin_adjust_credits, get_or_create_credit_account

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="admin")
    target = make_user(db, "artist@example.com", external_id="artist")

    with pytest.raises(HTTPException) as missing_reason:
        admin_adjust_credits(db, admin=admin, target_user=target, amount=5, reason="")
    assert missing_reason.value.status_code == 400

    admin_adjust_credits(db, admin=admin, target_user=target, amount=10, reason="manual recharge")
    assert get_or_create_credit_account(db, target.id).balance == 10

    with pytest.raises(HTTPException) as overdraw:
        admin_adjust_credits(db, admin=admin, target_user=target, amount=-11, reason="manual deduction")
    assert overdraw.value.status_code == 400
    assert get_or_create_credit_account(db, target.id).balance == 10


def test_reserve_capture_and_refund_are_idempotent() -> None:
    from app.credit_service import (
        admin_adjust_credits,
        capture_generation_credits,
        get_or_create_credit_account,
        refund_generation_credits,
        reserve_generation_credits,
    )

    db = make_db()
    user = make_user(db, "artist@example.com")
    admin_adjust_credits(db, admin=user, target_user=user, amount=5, reason="seed")

    reserve = reserve_generation_credits(
        db,
        user=user,
        capability="image",
        price=2,
        model_group_id="mdl_1",
        task_id="task_capture",
    )
    account = get_or_create_credit_account(db, user.id)
    assert account.balance == 3
    assert account.reserved_balance == 2

    capture_generation_credits(db, reserve.id)
    capture_generation_credits(db, reserve.id)
    account = get_or_create_credit_account(db, user.id)
    assert account.balance == 3
    assert account.reserved_balance == 0
    assert account.total_spent == 2

    refund_generation_credits(db, reserve.id, reason="late failure ignored")
    account = get_or_create_credit_account(db, user.id)
    assert account.balance == 3
    assert account.reserved_balance == 0
    assert account.total_refunded == 0


def test_refund_generation_credits_restores_balance_only_once() -> None:
    from app.credit_service import (
        admin_adjust_credits,
        get_or_create_credit_account,
        refund_generation_credits,
        reserve_generation_credits,
    )

    db = make_db()
    user = make_user(db, "artist@example.com")
    admin_adjust_credits(db, admin=user, target_user=user, amount=4, reason="seed")

    reserve = reserve_generation_credits(
        db,
        user=user,
        capability="video",
        price=3,
        model_group_id="mdl_1",
        task_id="task_refund",
    )
    refund_generation_credits(db, reserve.id, reason="task failed")
    refund_generation_credits(db, reserve.id, reason="task failed again")

    account = get_or_create_credit_account(db, user.id)
    assert account.balance == 4
    assert account.reserved_balance == 0
    assert account.total_refunded == 3


def test_signup_bonus_is_granted_only_once() -> None:
    from app.credit_service import (
        get_or_create_credit_account,
        grant_signup_bonus,
        set_setting,
        SIGNUP_BONUS_AMOUNT_KEY,
        SIGNUP_BONUS_ENABLED_KEY,
    )

    db = make_db()
    user = make_user(db, "new-user@example.com")
    set_setting(db, SIGNUP_BONUS_ENABLED_KEY, "true")
    set_setting(db, SIGNUP_BONUS_AMOUNT_KEY, "8")

    first = grant_signup_bonus(db, user)
    second = grant_signup_bonus(db, user)

    account = get_or_create_credit_account(db, user.id)
    assert first is not None
    assert second is None
    assert account.balance == 8
    assert account.total_recharged == 8
