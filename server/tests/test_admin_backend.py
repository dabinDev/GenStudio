from __future__ import annotations

import os
import sys
import tempfile

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

db_path = os.path.join(tempfile.gettempdir(), "genstudio-admin-backend-test.sqlite3")
if os.path.exists(db_path):
    os.remove(db_path)

os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["GENSTUDIO_SECRET_KEY"] = "test-secret"

from app.auth import get_current_user, require_admin_user
from app.database import Base
from app.db_models import ApiKey, CatalogModel, Conversation, ConversationMessage, ModelGroup, SubModel, User
from app.schemas import AdminModelUpdate
from app.security import encrypt_secret


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


def make_api_key(db: Session, user: User) -> ApiKey:
    key = ApiKey(
        user_id=user.id,
        name="Primary key",
        base_url="https://token.example.com",
        api_key_ciphertext=encrypt_secret("sk-test"),
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return key


def make_model(db: Session, user: User, *, name: str = "GPT 5.5", capability: str = "text") -> ModelGroup:
    key = make_api_key(db, user)
    model = ModelGroup(
        user_id=user.id,
        api_key_id=key.id,
        name=name,
        vendor="OpenAI",
        capability=capability,
        adapter="openai-chat",
        description="private note",
        primary_sub_model_id="",
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def test_admin_can_publish_and_unpublish_model() -> None:
    from app.admin_service import publish_model, unpublish_model

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com")
    model = make_model(db, admin)

    published = publish_model(db, admin, model.id)
    assert published.is_public is True

    unpublished = unpublish_model(db, admin, model.id)
    assert unpublished.is_public is False


def test_admin_can_update_public_model_metadata() -> None:
    from app.admin_service import update_admin_model

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com")
    model = make_model(db, admin)

    updated = update_admin_model(
        db,
        admin,
        model.id,
        AdminModelUpdate(
            publicDisplayName="平台 GPT",
            publicDescription="平台公用模型",
            inputHint="请输入你的创作要求",
            iconUrl="https://example.com/gpt.svg",
            publicTags=["recommended", "stable"],
            promptOptimizeEnabled=False,
            defaultParameters={"temperature": "0.7"},
            isPublic=True,
        ),
    )

    assert updated.is_public is True
    assert updated.public_display_name == "平台 GPT"
    assert updated.public_description == "平台公用模型"
    assert updated.input_hint == "请输入你的创作要求"
    assert updated.icon_url == "https://example.com/gpt.svg"
    assert updated.prompt_optimize_enabled is False
    assert "recommended" in updated.public_tags_json
    assert "temperature" in updated.default_parameters_json


def test_admin_model_list_filters_by_capability_public_state_and_search() -> None:
    from app.admin_service import list_admin_models, publish_model

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com")
    make_model(db, admin, name="Text Alpha", capability="text")
    image = make_model(db, admin, name="Image Beta", capability="image")
    publish_model(db, admin, image.id)

    rows = list_admin_models(db, capability="image", search="Beta", public_state="public")
    assert [item.name for item in rows] == ["Image Beta"]


def test_admin_model_serialization_falls_back_from_broken_names_to_catalog() -> None:
    from app.model_service import serialize_model

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com")
    key = make_api_key(db, admin)
    catalog = CatalogModel(
        external_id="10030",
        display_name="GPT-5.5",
        model_name="gpt-5.5",
        model_type=1,
        capability="text",
        description="可读描述",
        input_hint="请输入创作目标",
    )
    db.add(catalog)
    db.flush()
    model = ModelGroup(
        user_id=admin.id,
        api_key_id=key.id,
        catalog_model_id=catalog.id,
        name="??????",
        vendor="???",
        capability="text",
        adapter="text-chat",
        description="????????????",
        input_hint="????????????",
    )
    db.add(model)
    db.flush()
    sub_model = SubModel(
        model_group_id=model.id,
        api_key_id=key.id,
        catalog_model_id=catalog.id,
        model_name="gpt-5.5",
        display_name="???",
        capability="text",
        adapter="text-chat",
        is_primary=True,
    )
    db.add(sub_model)
    db.flush()
    model.primary_sub_model_id = sub_model.id
    db.commit()
    db.refresh(model)

    payload = serialize_model(model, admin, is_admin=True).model_dump()

    assert payload["name"] == "GPT-5.5"
    assert payload["vendor"] == "???"
    assert payload["description"] == "可读描述"
    assert payload["inputHint"] == "请输入创作目标"
    assert payload["subModels"][0]["displayName"] == "GPT-5.5"


def test_admin_creation_records_replace_broken_historical_text() -> None:
    from app.admin_service import list_admin_creation_records

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com")
    model = make_model(db, admin, name="GPT Image 2", capability="image")
    conversation = Conversation(
        user_id=admin.id,
        title="历史坏记录",
        capability="image",
        model_group_id=model.id,
        status="active",
    )
    db.add(conversation)
    db.flush()
    message = ConversationMessage(
        conversation_id=conversation.id,
        user_id=admin.id,
        model_group_id=model.id,
        role="user",
        capability="image",
        content="????????????????????????????????",
        status="success",
        request_json='{"model":"gpt-image-2","prompt":"????????????????"}',
        response_json='{"summary":"????????????????","decoded":"åå²åå®¹ç¼ç å¼å¸¸ï¼æ æ³è¿åã","error":{"message":"???????, ??????: ?13.662560, ???????: ?15.000000"}}',
        error_message="???????, ??????: ?13.662560, ???????: ?15.000000",
    )
    db.add(message)
    db.commit()

    records = list_admin_creation_records(db, capability="image")

    assert records[0]["prompt"] == "历史内容编码异常，无法还原。"
    assert records[0]["requestParams"]["prompt"] == "历史内容编码异常，无法还原。"
    assert records[0]["responseSummary"]["summary"] == "历史内容编码异常，无法还原。"
    assert records[0]["responseSummary"]["decoded"] == "历史内容编码异常，无法还原。"
    assert records[0]["responseSummary"]["error"]["message"] == "历史内容编码异常，无法还原。"
    assert records[0]["errorMessage"] == "历史内容编码异常，无法还原。"
    assert "??" not in str(records[0])


def test_admin_creation_records_filter_by_user_search() -> None:
    from app.admin_service import list_admin_creation_records

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="admin")
    other = make_user(db, "artist@example.com", external_id="artist")
    model = make_model(db, admin, name="GPT 5.5", capability="text")
    for user, content in [(admin, "管理员请求"), (other, "画师请求")]:
        conversation = Conversation(
            user_id=user.id,
            title=content,
            capability="text",
            model_group_id=model.id,
            status="active",
        )
        db.add(conversation)
        db.flush()
        db.add(
            ConversationMessage(
                conversation_id=conversation.id,
                user_id=user.id,
                model_group_id=model.id,
                role="user",
                capability="text",
                content=content,
                status="success",
            )
        )
    db.commit()

    records = list_admin_creation_records(db, capability="text", user_search="artist")

    assert len(records) == 1
    assert records[0]["prompt"] == "画师请求"
    assert records[0]["user"]["email"] == "artist@example.com"


def test_admin_creation_records_pair_adjacent_user_prompt_across_conversations() -> None:
    from app.admin_service import list_admin_creation_records

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="admin")
    request_model = make_model(db, admin, name="GPT 5.5 request", capability="text")
    response_model = make_model(db, admin, name="GPT 5.5 response", capability="text")
    request_conversation = Conversation(
        user_id=admin.id,
        title="请求",
        capability="text",
        model_group_id=request_model.id,
        status="active",
    )
    response_conversation = Conversation(
        user_id=admin.id,
        title="响应",
        capability="text",
        model_group_id=response_model.id,
        status="active",
    )
    db.add_all([request_conversation, response_conversation])
    db.flush()
    user_message = ConversationMessage(
        conversation_id=request_conversation.id,
        user_id=admin.id,
        model_group_id=request_model.id,
        role="user",
        capability="text",
        content="12123123",
        status="success",
    )
    assistant_message = ConversationMessage(
        conversation_id=response_conversation.id,
        user_id=admin.id,
        model_group_id=response_model.id,
        role="assistant",
        capability="text",
        content="这是回答",
        status="success",
    )
    db.add_all([user_message, assistant_message])
    db.commit()

    records = list_admin_creation_records(db, capability="text")

    assert len(records) == 1
    assert records[0]["prompt"] == "12123123"
    assert records[0]["response"] == "这是回答"


def test_prompt_template_uses_model_specific_before_default() -> None:
    from app.admin_service import get_prompt_template_for_scope, upsert_prompt_template
    from app.schemas import PromptTemplateUpdate

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com")
    model = make_model(db, admin)

    upsert_prompt_template(
        db,
        admin,
        PromptTemplateUpdate(
            capability="text",
            modelGroupId="",
            templateType="prompt_optimize",
            name="Text default",
            content="default {{prompt}}",
            enabled=True,
        ),
    )
    model_template = upsert_prompt_template(
        db,
        admin,
        PromptTemplateUpdate(
            capability="text",
            modelGroupId=model.id,
            templateType="prompt_optimize",
            name="Model text",
            content="model {{prompt}}",
            enabled=True,
        ),
    )

    resolved = get_prompt_template_for_scope(db, "text", model.id)
    assert resolved.id == model_template.id
    assert resolved.content == "model {{prompt}}"


def test_prompt_template_falls_back_to_capability_default() -> None:
    from app.admin_service import get_prompt_template_for_scope, upsert_prompt_template
    from app.schemas import PromptTemplateUpdate

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com")
    upsert_prompt_template(
        db,
        admin,
        PromptTemplateUpdate(
            capability="image",
            modelGroupId="",
            templateType="prompt_optimize",
            name="Image default",
            content="image {{prompt}}",
            enabled=True,
        ),
    )

    resolved = get_prompt_template_for_scope(db, "image", "missing-model")
    assert resolved.content == "image {{prompt}}"


def test_disabled_prompt_template_is_not_used() -> None:
    from fastapi import HTTPException

    from app.admin_service import get_prompt_template_for_scope, upsert_prompt_template
    from app.schemas import PromptTemplateUpdate

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com")
    upsert_prompt_template(
        db,
        admin,
        PromptTemplateUpdate(
            capability="video",
            modelGroupId="",
            templateType="prompt_optimize",
            name="Video default",
            content="video {{prompt}}",
            enabled=False,
        ),
    )

    with pytest.raises(HTTPException) as exc:
        get_prompt_template_for_scope(db, "video", "")
    assert exc.value.status_code == 404


def test_admin_user_lifecycle_status_changes() -> None:
    from app.admin_service import (
        admin_delete_user,
        admin_disable_user,
        admin_enable_user,
        admin_restore_user,
        list_admin_users,
    )

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="admin")
    user = make_user(db, "user@example.com", external_id="user")

    assert list_admin_users(db, search="user@example.com")[0].id == user.id
    assert admin_disable_user(db, admin, user.id).status == "disabled"
    assert admin_enable_user(db, admin, user.id).status == "active"
    assert admin_delete_user(db, admin, user.id).status == "deleted"
    assert admin_restore_user(db, admin, user.id).status == "active"


def test_admin_cannot_disable_self() -> None:
    from fastapi import HTTPException

    from app.admin_service import admin_disable_user

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="admin")

    with pytest.raises(HTTPException) as exc:
        admin_disable_user(db, admin, admin.id)
    assert exc.value.status_code == 400


def test_admin_model_routes_require_admin_and_return_audit_logs() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="admin-route")
    normal = make_user(db, "normal@example.com", external_id="normal-route")
    model = make_model(db, admin)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: normal
    client = TestClient(app)
    denied = client.get("/api/admin/models")
    assert denied.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: admin
    publish = client.post(f"/api/admin/models/{model.id}/publish")
    assert publish.status_code == 200
    assert publish.json()["model"]["isPublic"] is True

    unpublish = client.post(f"/api/admin/models/{model.id}/unpublish")
    assert unpublish.status_code == 200
    assert unpublish.json()["model"]["isPublic"] is False

    logs = client.get("/api/admin/audit-logs")
    assert logs.status_code == 200
    assert [item["action"] for item in logs.json()["logs"][:2]] == ["unpublish_model", "publish_model"]

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()
