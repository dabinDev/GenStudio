from __future__ import annotations

import os
import sys

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["GENSTUDIO_SECRET_KEY"] = "test-secret"

from app.auth import get_current_user, require_admin_user
from app.database import Base
from app.db_models import ModelGroup, User


def make_db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_user(db: Session, email: str, external_id: str = "user-1", status: str = "active") -> User:
    user = User(
        external_user_id=external_id,
        email=email,
        nickname=email.split("@")[0],
        status=status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_require_admin_user_allows_configured_admin() -> None:
    db = make_db()
    admin = make_user(db, "cage_ben@sina.com")
    app = FastAPI()

    def override_current_user() -> User:
        return admin

    app.dependency_overrides[get_current_user] = override_current_user

    @app.get("/admin-only")
    def admin_only(user: User = Depends(require_admin_user)) -> dict[str, str]:
        return {"id": user.id}

    client = TestClient(app)
    response = client.get("/admin-only")
    assert response.status_code == 200
    assert response.json() == {"id": admin.id}


def test_require_admin_user_rejects_non_admin() -> None:
    db = make_db()
    user = make_user(db, "normal@example.com")
    app = FastAPI()

    def override_current_user() -> User:
        return user

    app.dependency_overrides[get_current_user] = override_current_user

    @app.get("/admin-only")
    def admin_only(_user: User = Depends(require_admin_user)) -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/admin-only")
    assert response.status_code == 403


@pytest.mark.parametrize("status", ["disabled", "deleted"])
def test_require_admin_user_rejects_inactive_admin(status: str) -> None:
    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", status=status)
    app = FastAPI()

    def override_current_user() -> User:
        return admin

    app.dependency_overrides[get_current_user] = override_current_user

    @app.get("/admin-only")
    def admin_only(_user: User = Depends(require_admin_user)) -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/admin-only")
    assert response.status_code == 403


def test_model_group_has_admin_public_metadata_columns() -> None:
    db = make_db()
    owner = make_user(db, "owner@example.com")
    model = ModelGroup(
        user_id=owner.id,
        api_key_id="key_missing_for_column_test",
        name="GPT 5.5",
        vendor="OpenAI",
        capability="text",
        adapter="openai-chat",
        description="private note",
        is_public=True,
        public_display_name="平台 GPT 5.5",
        public_description="平台公用文案模型",
        input_hint="输入你要创作的内容",
        icon_url="https://example.com/icon.svg",
        public_tags_json='["recommended"]',
        prompt_optimize_enabled=True,
        default_parameters_json='{"temperature": "0.8"}',
    )
    db.add(model)
    db.commit()
    db.refresh(model)

    assert model.public_display_name == "平台 GPT 5.5"
    assert model.public_description == "平台公用文案模型"
    assert model.input_hint == "输入你要创作的内容"
    assert model.prompt_optimize_enabled is True
