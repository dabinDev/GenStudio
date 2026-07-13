from __future__ import annotations

import os
import json
import sys
import tempfile
from datetime import datetime, timedelta

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
from app.db_models import (
    AdminRoleAssignment,
    AdminOperationLog,
    ApiKey,
    CallLog,
    CatalogModel,
    Conversation,
    ConversationMessage,
    CreditTransaction,
    ModelGroup,
    ModelHealthCheck,
    SessionRecord,
    SubModel,
    SystemSetting,
    TaskEvent,
    User,
    UserCreditAccount,
    UserCredential,
    utcnow,
)
from app.schemas import AdminModelUpdate
from app.security import encrypt_secret


def csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrfToken"]}


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


def test_admin_model_health_records_latest_result() -> None:
    from app.admin_service import get_model_health, record_model_health_check

    db_session = make_db()
    admin_user = make_user(db_session, "cage_ben@sina.com")
    model_group = make_model(db_session, admin_user)

    record_model_health_check(
        db_session,
        admin=admin_user,
        model=model_group,
        status="failed",
        duration_ms=3210,
        message="连接失败",
        raw={"status": 502},
    )

    health = get_model_health(db_session, model_group.id)

    assert health["modelGroupId"] == model_group.id
    assert health["latest"]["status"] == "failed"
    assert health["latest"]["message"] == "连接失败"


def test_admin_model_health_hides_raw_without_raw_permission() -> None:
    from app.admin_service import get_model_health, record_model_health_check

    db_session = make_db()
    owner = make_user(db_session, "cage_ben@sina.com", external_id="health-raw-owner")
    viewer = make_user(db_session, "viewer-health-raw@example.com", external_id="health-raw-viewer")
    db_session.add(AdminRoleAssignment(user_id=viewer.id, role="viewer", assigned_by=owner.id))
    model_group = make_model(db_session, owner)

    record_model_health_check(
        db_session,
        admin=owner,
        model=model_group,
        status="failed",
        duration_ms=100,
        message="failed",
        raw={"secret": "provider-token"},
    )

    health = get_model_health(db_session, model_group.id, include_raw_json=False)

    assert health["latest"]["raw"] == {"hidden": True, "reason": "record:raw_json required"}
    assert health["recent"][0]["raw"] == {"hidden": True, "reason": "record:raw_json required"}


def test_admin_model_health_route_returns_404_for_missing_model() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="health-missing-admin")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    response = client.get("/api/admin/models/missing-model/health")

    assert response.status_code == 404
    assert response.json()["detail"]["message"] == "模型不存在。"

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_model_health_route_hides_raw_without_raw_permission() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app
    from app.admin_service import record_model_health_check

    db = make_db()
    owner = make_user(db, "cage_ben@sina.com", external_id="health-route-raw-owner")
    viewer = make_user(db, "viewer-route-health-raw@example.com", external_id="health-route-raw-viewer")
    db.add(AdminRoleAssignment(user_id=viewer.id, role="viewer", assigned_by=owner.id))
    model = make_model(db, owner)
    record_model_health_check(
        db,
        admin=owner,
        model=model,
        status="failed",
        duration_ms=100,
        message="failed",
        raw={"secret": "provider-token"},
    )

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: viewer
    client = TestClient(app)

    response = client.get(f"/api/admin/models/{model.id}/health")

    assert response.status_code == 200
    assert response.json()["health"]["latest"]["raw"] == {"hidden": True, "reason": "record:raw_json required"}

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_model_health_check_route_records_success(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    import app.main as main_module
    from app.auth import get_current_user, require_csrf
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="health-admin")
    model = make_model(db, admin, name="Health Text", capability="text")
    sub_model = SubModel(
        model_group_id=model.id,
        api_key_id=model.api_key_id,
        model_name="gpt-health",
        display_name="GPT Health",
        capability="text",
        adapter="openai-chat",
        is_primary=True,
    )
    db.add(sub_model)
    db.flush()
    model.primary_sub_model_id = sub_model.id
    db.commit()

    async def fake_forward_json(method: str, url: str, api_key: str, body: dict | None = None):
        request = httpx.Request(method, url)
        response = httpx.Response(200, json={"id": "chatcmpl-health"}, request=request)
        return response, {"id": "chatcmpl-health"}

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_csrf] = lambda: None
    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)

    response = client.post(f"/api/admin/models/{model.id}/health-check")

    assert response.status_code == 200
    payload = response.json()["health"]
    assert payload["latest"]["status"] == "success"
    assert payload["latest"]["subModelId"] == sub_model.id
    assert payload["recent"][0]["status"] == "success"
    health_row = db.query(ModelHealthCheck).filter(ModelHealthCheck.model_group_id == model.id).one()
    assert health_row.status == "success"
    assert health_row.sub_model_id == sub_model.id
    audit = db.query(AdminOperationLog).filter(AdminOperationLog.action == "model_health_check").one()
    assert audit.target_id == model.id
    assert audit.status == "success"

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_model_health_check_route_is_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    import app.main as main_module
    from app.auth import get_current_user, require_csrf
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="health-rate-admin")
    model = make_model(db, admin, name="Health Rate Text", capability="text")
    sub_model = SubModel(
        model_group_id=model.id,
        api_key_id=model.api_key_id,
        model_name="gpt-health-rate",
        display_name="GPT Health Rate",
        capability="text",
        adapter="openai-chat",
        is_primary=True,
    )
    db.add(sub_model)
    db.flush()
    model.primary_sub_model_id = sub_model.id
    db.commit()

    async def fake_forward_json(method: str, url: str, api_key: str, body: dict | None = None):
        request = httpx.Request(method, url)
        response = httpx.Response(200, json={"id": "chatcmpl-health-rate"}, request=request)
        return response, {"id": "chatcmpl-health-rate"}

    def override_db():
        yield db

    settings = main_module.get_settings()
    original_limit = settings.rate_limit_model_test_per_window
    settings.rate_limit_model_test_per_window = 1

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_csrf] = lambda: None
    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)

    first = client.post(f"/api/admin/models/{model.id}/health-check")
    second = client.post(f"/api/admin/models/{model.id}/health-check")

    assert first.status_code == 200
    assert second.status_code == 429

    settings.rate_limit_model_test_per_window = original_limit
    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_model_health_check_route_requires_model_test_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main_module
    from app.auth import get_current_user, require_csrf
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="health-permission-admin")
    model = make_model(db, admin, name="Health Permission Text", capability="text")

    def override_db():
        yield db

    def deny_model_test(user: User | None, checked_permission: str, settings) -> bool:
        return checked_permission != "model:test"

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_csrf] = lambda: None
    monkeypatch.setattr(main_module, "can", deny_model_test)
    client = TestClient(app)

    response = client.post(f"/api/admin/models/{model.id}/health-check")

    assert response.status_code == 403
    assert response.json()["detail"]["message"] == "当前账号没有执行该后台操作的权限。"

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_model_health_check_route_records_missing_api_key_configuration() -> None:
    import app.main as main_module
    from app.auth import get_current_user, require_csrf
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="health-missing-key-admin")
    model = make_model(db, admin, name="Health Missing Key Text", capability="text")
    sub_model = SubModel(
        model_group_id=model.id,
        api_key_id="missing-api-key",
        model_name="gpt-health-missing-key",
        display_name="GPT Health Missing Key",
        capability="text",
        adapter="openai-chat",
        is_primary=True,
    )
    db.add(sub_model)
    db.flush()
    model.primary_sub_model_id = sub_model.id
    model.api_key_id = ""
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_csrf] = lambda: None
    client = TestClient(app)

    response = client.post(f"/api/admin/models/{model.id}/health-check")

    assert response.status_code == 200
    payload = response.json()["health"]
    assert payload["latest"]["status"] == "failed"
    assert payload["latest"]["subModelId"] == sub_model.id
    health_row = db.query(ModelHealthCheck).filter(ModelHealthCheck.model_group_id == model.id).one()
    assert health_row.status == "failed"
    assert "API key" in health_row.raw_json
    audit = db.query(AdminOperationLog).filter(AdminOperationLog.action == "model_health_check").one()
    assert audit.target_id == model.id
    assert audit.status == "error"

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_model_health_check_route_reports_model_without_testable_sub_model() -> None:
    import app.main as main_module
    from app.auth import get_current_user, require_csrf
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="health-no-submodel-admin")
    model = make_model(db, admin, name="Health Empty Text", capability="text")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_csrf] = lambda: None
    client = TestClient(app)

    response = client.post(f"/api/admin/models/{model.id}/health-check")

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "模型缺少可测试的子模型。"

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_model_health_check_route_records_upstream_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    import app.main as main_module
    from app.auth import get_current_user, require_csrf
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="health-failure-admin")
    model = make_model(db, admin, name="Health Failure Text", capability="text")
    sub_model = SubModel(
        model_group_id=model.id,
        api_key_id=model.api_key_id,
        model_name="gpt-health-failure",
        display_name="GPT Health Failure",
        capability="text",
        adapter="openai-chat",
        is_primary=True,
    )
    db.add(sub_model)
    db.flush()
    model.primary_sub_model_id = sub_model.id
    db.commit()

    async def fake_forward_json(method: str, url: str, api_key: str, body: dict | None = None):
        request = httpx.Request(method, url)
        response = httpx.Response(500, json={"error": {"message": "upstream exploded"}}, request=request)
        return response, {"error": {"message": "upstream exploded"}}

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_csrf] = lambda: None
    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)

    response = client.post(f"/api/admin/models/{model.id}/health-check")

    assert response.status_code == 200
    payload = response.json()["health"]
    assert payload["latest"]["status"] == "failed"
    assert payload["latest"]["subModelId"] == sub_model.id
    health_row = db.query(ModelHealthCheck).filter(ModelHealthCheck.model_group_id == model.id).one()
    assert health_row.status == "failed"
    assert health_row.sub_model_id == sub_model.id
    assert "upstream exploded" in health_row.message
    audit = db.query(AdminOperationLog).filter(AdminOperationLog.action == "model_health_check").one()
    assert audit.target_id == model.id
    assert audit.status == "error"

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_model_health_check_route_records_forward_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main_module
    from app.auth import get_current_user, require_csrf
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="health-exception-admin")
    model = make_model(db, admin, name="Health Exception Text", capability="text")
    sub_model = SubModel(
        model_group_id=model.id,
        api_key_id=model.api_key_id,
        model_name="gpt-health-exception",
        display_name="GPT Health Exception",
        capability="text",
        adapter="openai-chat",
        is_primary=True,
    )
    db.add(sub_model)
    db.flush()
    model.primary_sub_model_id = sub_model.id
    db.commit()

    async def fake_forward_json(method: str, url: str, api_key: str, body: dict | None = None):
        raise TimeoutError("upstream timed out")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_csrf] = lambda: None
    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)

    response = client.post(f"/api/admin/models/{model.id}/health-check")

    assert response.status_code == 200
    payload = response.json()["health"]
    assert payload["latest"]["status"] == "failed"
    assert payload["latest"]["subModelId"] == sub_model.id
    health_row = db.query(ModelHealthCheck).filter(ModelHealthCheck.model_group_id == model.id).one()
    assert health_row.status == "failed"
    assert health_row.sub_model_id == sub_model.id
    assert "TimeoutError" in health_row.raw_json
    audit = db.query(AdminOperationLog).filter(AdminOperationLog.action == "model_health_check").one()
    assert audit.target_id == model.id
    assert audit.status == "error"

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_model_health_check_route_uses_kkyi_video_test_request(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    import app.main as main_module
    from app.auth import get_current_user, require_csrf
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="health-kkyi-admin")
    model = make_model(db, admin, name="Health KKYi Video", capability="video")
    sub_model = SubModel(
        model_group_id=model.id,
        api_key_id=model.api_key_id,
        model_name="kkyi-video",
        display_name="KKYi Video",
        capability="video",
        adapter="kkyi-video",
        is_primary=True,
    )
    db.add(sub_model)
    db.flush()
    model.primary_sub_model_id = sub_model.id
    db.commit()
    captured: dict[str, object] = {}
    normalized_body = {"model": "kkyi-video", "prompt": "normalized ping", "quantity": 1}

    def fake_is_kkyi_video_model(candidate: SubModel, base_url: str) -> bool:
        captured["kkyi_base_url"] = base_url
        return candidate.id == sub_model.id

    def fake_normalize_kkyi_video_body(body: dict, model_name: str, candidate: SubModel | None = None) -> dict:
        captured["pre_normalized_body"] = body
        captured["normalized_model_name"] = model_name
        captured["normalized_sub_model_id"] = candidate.id if candidate else ""
        return normalized_body

    async def fake_forward_json(method: str, url: str, api_key: str, body: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        captured["body"] = body
        request = httpx.Request(method, url)
        response = httpx.Response(200, json={"id": "video-health"}, request=request)
        return response, {"id": "video-health"}

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_csrf] = lambda: None
    monkeypatch.setattr(main_module, "is_kkyi_video_model", fake_is_kkyi_video_model)
    monkeypatch.setattr(main_module, "normalize_kkyi_video_body", fake_normalize_kkyi_video_body)
    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)

    response = client.post(f"/api/admin/models/{model.id}/health-check")

    assert response.status_code == 200
    assert response.json()["health"]["latest"]["status"] == "success"
    assert captured["method"] == "POST"
    assert captured["url"] == "https://token.example.com/v1/video/generations"
    assert captured["body"] == normalized_body
    assert captured["normalized_model_name"] == "kkyi-video"
    assert captured["normalized_sub_model_id"] == sub_model.id
    assert captured["pre_normalized_body"] != normalized_body

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_batch_model_health_check_records_partial_results(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    import app.main as main_module
    from app.auth import get_current_user, require_csrf
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="batch-health-admin")
    healthy_model = make_model(db, admin, name="Batch Healthy Text", capability="text")
    failing_model = make_model(db, admin, name="Batch Failing Text", capability="text")
    healthy_sub_model = SubModel(
        model_group_id=healthy_model.id,
        api_key_id=healthy_model.api_key_id,
        model_name="gpt-batch-healthy",
        display_name="GPT Batch Healthy",
        capability="text",
        adapter="openai-chat",
        is_primary=True,
    )
    failing_sub_model = SubModel(
        model_group_id=failing_model.id,
        api_key_id=failing_model.api_key_id,
        model_name="gpt-batch-failing",
        display_name="GPT Batch Failing",
        capability="text",
        adapter="openai-chat",
        is_primary=True,
    )
    db.add_all([healthy_sub_model, failing_sub_model])
    db.flush()
    healthy_model.primary_sub_model_id = healthy_sub_model.id
    failing_model.primary_sub_model_id = failing_sub_model.id
    db.commit()

    async def fake_forward_json(method: str, url: str, api_key: str, body: dict | None = None):
        request = httpx.Request(method, url)
        if body and body.get("model") == "gpt-batch-healthy":
            response = httpx.Response(200, json={"id": "batch-ok"}, request=request)
            return response, {"id": "batch-ok"}
        response = httpx.Response(503, json={"error": {"message": "batch upstream down"}}, request=request)
        return response, {"error": {"message": "batch upstream down"}}

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_csrf] = lambda: None
    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)

    response = client.post(
        "/api/admin/models/batch-health-check",
        json={"modelIds": [healthy_model.id, failing_model.id]},
    )

    assert response.status_code == 200
    payload = response.json()
    by_model = {item["modelId"]: item for item in payload["results"]}
    assert by_model[healthy_model.id]["status"] == "success"
    assert by_model[healthy_model.id]["health"]["latest"]["subModelId"] == healthy_sub_model.id
    assert by_model[failing_model.id]["status"] == "failed"
    assert by_model[failing_model.id]["health"]["latest"]["subModelId"] == failing_sub_model.id
    health_rows = db.query(ModelHealthCheck).order_by(ModelHealthCheck.model_group_id).all()
    assert {row.model_group_id: row.status for row in health_rows} == {
        healthy_model.id: "success",
        failing_model.id: "failed",
    }
    audit_rows = db.query(AdminOperationLog).filter(AdminOperationLog.action == "model_health_check").all()
    assert {row.target_id: row.status for row in audit_rows} == {
        healthy_model.id: "success",
        failing_model.id: "error",
    }

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_batch_model_health_check_keeps_running_after_oversized_raw(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    import app.main as main_module
    from app.auth import get_current_user, require_csrf
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="batch-health-raw-admin")
    large_raw_model = make_model(db, admin, name="Batch Large Raw", capability="image")
    ok_model = make_model(db, admin, name="Batch After Raw", capability="text")
    large_raw_sub_model = SubModel(
        model_group_id=large_raw_model.id,
        api_key_id=large_raw_model.api_key_id,
        model_name="gpt-image-large-raw",
        display_name="Image Large Raw",
        capability="image",
        adapter="image-openai",
        is_primary=True,
    )
    ok_sub_model = SubModel(
        model_group_id=ok_model.id,
        api_key_id=ok_model.api_key_id,
        model_name="gpt-batch-after-raw",
        display_name="GPT Batch After Raw",
        capability="text",
        adapter="openai-chat",
        is_primary=True,
    )
    db.add_all([large_raw_sub_model, ok_sub_model])
    db.flush()
    large_raw_model.primary_sub_model_id = large_raw_sub_model.id
    ok_model.primary_sub_model_id = ok_sub_model.id
    db.commit()

    async def fake_forward_json(method: str, url: str, api_key: str, body: dict | None = None):
        request = httpx.Request(method, url)
        if body and body.get("model") == "gpt-image-large-raw":
            raw = {
                "data": [
                    {
                        "url": "https://cdn.example.com/generated.png",
                        "revised_prompt": "large prompt " * 1000,
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            }
            response = httpx.Response(200, json=raw, request=request)
            return response, raw
        response = httpx.Response(200, json={"id": "batch-after-raw"}, request=request)
        return response, {"id": "batch-after-raw"}

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_csrf] = lambda: None
    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)

    response = client.post(
        "/api/admin/models/batch-health-check",
        json={"modelIds": [large_raw_model.id, ok_model.id]},
    )

    assert response.status_code == 200
    by_model = {item["modelId"]: item for item in response.json()["results"]}
    assert by_model[large_raw_model.id]["status"] == "success"
    assert by_model[ok_model.id]["status"] == "success"
    large_raw_row = db.query(ModelHealthCheck).filter(ModelHealthCheck.model_group_id == large_raw_model.id).one()
    assert len(large_raw_row.raw_json.encode("utf-8")) <= 3900
    assert "truncated" in large_raw_row.raw_json
    assert db.query(ModelHealthCheck).filter(ModelHealthCheck.model_group_id == ok_model.id).count() == 1

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_batch_model_health_check_requires_model_test_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main_module
    from app.auth import get_current_user, require_csrf
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="batch-health-denied-admin")
    model = make_model(db, admin, name="Denied Batch Health", capability="text")

    def override_db():
        yield db

    def deny_model_test(user: User | None, checked_permission: str, settings) -> bool:
        return checked_permission != "model:test"

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_csrf] = lambda: None
    monkeypatch.setattr(main_module, "can", deny_model_test)
    client = TestClient(app)

    response = client.post("/api/admin/models/batch-health-check", json={"modelIds": [model.id]})

    assert response.status_code == 403

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_batch_model_health_check_keeps_running_after_route_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    import app.main as main_module
    from app.auth import get_current_user, require_csrf
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="batch-health-errors-admin")
    ok_model = make_model(db, admin, name="Batch OK Text", capability="text")
    no_sub_model = make_model(db, admin, name="Batch No Sub Text", capability="text")
    rate_limited_model = make_model(db, admin, name="Batch Rate Text", capability="text")
    ok_sub_model = SubModel(
        model_group_id=ok_model.id,
        api_key_id=ok_model.api_key_id,
        model_name="gpt-batch-ok",
        display_name="GPT Batch OK",
        capability="text",
        adapter="openai-chat",
        is_primary=True,
    )
    rate_sub_model = SubModel(
        model_group_id=rate_limited_model.id,
        api_key_id=rate_limited_model.api_key_id,
        model_name="gpt-batch-rate",
        display_name="GPT Batch Rate",
        capability="text",
        adapter="openai-chat",
        is_primary=True,
    )
    db.add_all([ok_sub_model, rate_sub_model])
    db.flush()
    ok_model.primary_sub_model_id = ok_sub_model.id
    rate_limited_model.primary_sub_model_id = rate_sub_model.id
    db.commit()

    async def fake_forward_json(method: str, url: str, api_key: str, body: dict | None = None):
        request = httpx.Request(method, url)
        response = httpx.Response(200, json={"id": "batch-ok"}, request=request)
        return response, {"id": "batch-ok"}

    def override_db():
        yield db

    settings = main_module.get_settings()
    original_limit = settings.rate_limit_model_test_per_window
    settings.rate_limit_model_test_per_window = 1

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_csrf] = lambda: None
    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)

    first_rate_response = client.post(
        "/api/admin/models/batch-health-check",
        json={"modelIds": [rate_limited_model.id]},
    )
    mixed_response = client.post(
        "/api/admin/models/batch-health-check",
        json={"modelIds": ["missing-model", no_sub_model.id, rate_limited_model.id, ok_model.id]},
    )

    assert first_rate_response.status_code == 200
    assert mixed_response.status_code == 200
    by_model = {item["modelId"]: item for item in mixed_response.json()["results"]}
    assert by_model["missing-model"]["error"]["statusCode"] == 404
    assert by_model[no_sub_model.id]["error"]["statusCode"] == 400
    assert by_model[rate_limited_model.id]["error"]["statusCode"] == 429
    assert by_model[ok_model.id]["status"] == "success"
    assert db.query(ModelHealthCheck).filter(ModelHealthCheck.model_group_id == ok_model.id).count() == 1

    settings.rate_limit_model_test_per_window = original_limit
    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_remove_unavailable_models_removes_only_latest_failed_models() -> None:
    import app.main as main_module
    from app.auth import get_current_user, require_csrf
    from app.admin_service import record_model_health_check
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="remove-unavailable-admin")
    failed_model = make_model(db, admin, name="Remove Failed", capability="text")
    recovered_model = make_model(db, admin, name="Keep Recovered", capability="text")
    never_checked_model = make_model(db, admin, name="Keep Unchecked", capability="text")

    old_failed = record_model_health_check(
        db,
        admin=admin,
        model=recovered_model,
        status="failed",
        duration_ms=100,
        message="old failure",
    )
    latest_success = record_model_health_check(
        db,
        admin=admin,
        model=recovered_model,
        status="success",
        duration_ms=80,
        message="recovered",
    )
    latest_failed = record_model_health_check(
        db,
        admin=admin,
        model=failed_model,
        status="failed",
        duration_ms=120,
        message="still unavailable",
    )
    old_failed.created_at = datetime(2026, 1, 1)
    latest_success.created_at = datetime(2026, 1, 2)
    latest_failed.created_at = datetime(2026, 1, 3)
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_csrf] = lambda: None
    client = TestClient(app)

    response = client.post(
        "/api/admin/models/remove-unavailable",
        json={"modelIds": [failed_model.id, recovered_model.id, never_checked_model.id]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["removedIds"] == [failed_model.id]
    assert {item["modelId"]: item["reason"] for item in payload["skipped"]} == {
        recovered_model.id: "latest_health_success",
        never_checked_model.id: "no_health_check",
    }
    assert db.get(ModelGroup, failed_model.id) is None
    assert db.get(ModelGroup, recovered_model.id) is not None
    assert db.get(ModelGroup, never_checked_model.id) is not None
    assert failed_model.id not in {model["id"] for model in payload["models"]}
    audit = db.query(AdminOperationLog).filter(AdminOperationLog.action == "remove_unavailable_models").one()
    assert audit.status == "success"
    assert failed_model.id in audit.summary_json

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_remove_unavailable_models_skips_unknown_and_pending_health() -> None:
    import app.main as main_module
    from app.auth import get_current_user, require_csrf
    from app.admin_service import record_model_health_check
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="remove-unavailable-unknown-admin")
    unknown_model = make_model(db, admin, name="Keep Unknown", capability="text")
    pending_model = make_model(db, admin, name="Keep Pending", capability="text")
    failed_model = make_model(db, admin, name="Remove Explicit Failed", capability="text")
    record_model_health_check(db, admin=admin, model=unknown_model, status="", duration_ms=20, message="")
    record_model_health_check(db, admin=admin, model=pending_model, status="pending", duration_ms=20, message="")
    record_model_health_check(db, admin=admin, model=failed_model, status="failed", duration_ms=20, message="")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_csrf] = lambda: None
    client = TestClient(app)

    response = client.post(
        "/api/admin/models/remove-unavailable",
        json={"modelIds": [unknown_model.id, pending_model.id, failed_model.id]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["removedIds"] == [failed_model.id]
    assert {item["modelId"]: item["reason"] for item in payload["skipped"]} == {
        unknown_model.id: "latest_health_not_failed",
        pending_model.id: "latest_health_not_failed",
    }
    assert db.get(ModelGroup, unknown_model.id) is not None
    assert db.get(ModelGroup, pending_model.id) is not None
    assert db.get(ModelGroup, failed_model.id) is None

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_remove_unavailable_models_requires_model_delete_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main_module
    from app.auth import get_current_user, require_csrf
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="remove-unavailable-denied-admin")
    model = make_model(db, admin, name="Denied Remove", capability="text")

    def override_db():
        yield db

    def deny_model_delete(user: User | None, checked_permission: str, settings) -> bool:
        return checked_permission != "model:delete"

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_csrf] = lambda: None
    monkeypatch.setattr(main_module, "can", deny_model_delete)
    client = TestClient(app)

    response = client.post("/api/admin/models/remove-unavailable", json={"modelIds": [model.id]})

    assert response.status_code == 403

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


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


def test_admin_creation_records_filter_processing_video_and_task_id_alias() -> None:
    from app.admin_service import list_admin_creation_records
    from app.database import SessionLocal, init_db
    from app.db_models import CallLog, Conversation, ConversationMessage, User

    init_db()
    db = SessionLocal()
    try:
        user = make_user(db, "video-processing@example.com", external_id="video-processing")
        conversation = Conversation(
            id="cnv_video_processing",
            user_id=user.id,
            title="Video processing",
            capability="video",
        )
        db.add(conversation)
        db.flush()
        user_message = ConversationMessage(
            id="msg_video_processing_user",
            conversation_id=conversation.id,
            user_id=user.id,
            role="user",
            capability="video",
            content="make a reference video",
            status="success",
        )
        assistant_message = ConversationMessage(
            id="msg_video_processing_assistant",
            conversation_id=conversation.id,
            user_id=user.id,
            role="assistant",
            capability="video",
            content="video task queued",
            status="processing",
            request_json=json.dumps({"duration": 8, "resolution": "720p", "video_mode": "reference"}),
            response_json=json.dumps({"providerTaskId": "task_provider_alias"}),
        )
        db.add_all([user_message, assistant_message])
        db.add(
            CallLog(
                id="log_video_processing",
                user_id=user.id,
                capability="video",
                endpoint="/api/proxy/video/create",
                status="processing",
                duration_ms=100,
                request_params_json=json.dumps({"duration": 8, "resolution": "720p", "video_mode": "reference"}),
                response_summary_json=json.dumps({"providerTaskId": "task_provider_alias"}),
                conversation_id=conversation.id,
                message_id=assistant_message.id,
            )
        )
        db.commit()

        records = list_admin_creation_records(
            db,
            capability="video",
            status="processing",
            duration="8",
            resolution="720p",
            mode="reference",
        )

        assert len(records) == 1
        assert records[0]["status"] == "processing"
        assert records[0]["taskId"] == "task_provider_alias"
    finally:
        db.close()


def test_admin_creation_records_non_success_status_matches_error_and_processing() -> None:
    from app.admin_service import list_admin_creation_records

    db = make_db()
    user = make_user(db, "non-success-records@example.com", external_id="non-success-records")
    conversation = Conversation(
        user_id=user.id,
        title="Non success records",
        capability="image",
        status="active",
    )
    db.add(conversation)
    db.flush()
    db.add_all(
        [
            ConversationMessage(
                conversation_id=conversation.id,
                user_id=user.id,
                role="assistant",
                capability="image",
                content="done",
                status="success",
                created_at=utcnow(),
            ),
            ConversationMessage(
                conversation_id=conversation.id,
                user_id=user.id,
                role="assistant",
                capability="image",
                content="still running",
                status="processing",
                created_at=utcnow() + timedelta(seconds=1),
            ),
            ConversationMessage(
                conversation_id=conversation.id,
                user_id=user.id,
                role="assistant",
                capability="image",
                content="",
                status="error",
                error_message="upstream failed",
                created_at=utcnow() + timedelta(seconds=2),
            ),
        ]
    )
    db.commit()

    records = list_admin_creation_records(db, capability="image", status="non_success")

    assert {item["status"] for item in records} == {"processing", "error"}


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


def test_prompt_template_version_history_and_multi_sample_preview() -> None:
    from app.admin_service import (
        list_prompt_template_versions,
        render_prompt_template_samples,
        upsert_prompt_template,
    )
    from app.schemas import PromptTemplateUpdate

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="prompt-version-admin")
    template = upsert_prompt_template(
        db,
        admin,
        PromptTemplateUpdate(
            capability="image",
            modelGroupId="",
            templateType="prompt_optimize",
            name="Image optimize",
            content="v1 {{prompt}}",
            enabled=True,
        ),
    )
    upsert_prompt_template(
        db,
        admin,
        PromptTemplateUpdate(
            capability="image",
            modelGroupId="",
            templateType="prompt_optimize",
            name="Image optimize",
            content="v2 {{prompt}}",
            enabled=False,
        ),
    )

    versions = list_prompt_template_versions(db, template.id)
    assert [item["version"] for item in versions] == [2, 1]
    assert [item["templateId"] for item in versions] == [template.id, template.id]
    assert versions[0]["content"] == "v2 {{prompt}}"
    assert versions[0]["enabled"] is False
    assert versions[0]["updatedBy"] == admin.id

    samples = render_prompt_template_samples(
        "cap={{capability}} prompt={{prompt}}",
        capability="image",
        prompts=["生成车", "生成猫"],
    )
    assert samples == [
        {"prompt": "生成车", "rendered": "cap=image prompt=生成车"},
        {"prompt": "生成猫", "rendered": "cap=image prompt=生成猫"},
    ]


def test_prompt_template_model_status_overview_marks_model_specific_templates() -> None:
    from app.admin_service import prompt_template_model_status_overview, upsert_prompt_template
    from app.schemas import PromptTemplateUpdate

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="prompt-overview-admin")
    image_model = make_model(db, admin, name="Image Model", capability="image")
    image_model.prompt_optimize_enabled = False
    text_model = make_model(db, admin, name="Text Model", capability="text")
    db.commit()
    upsert_prompt_template(
        db,
        admin,
        PromptTemplateUpdate(
            capability="image",
            modelGroupId="",
            templateType="prompt_optimize",
            name="Image default",
            content="default {{prompt}}",
            enabled=True,
        ),
    )
    upsert_prompt_template(
        db,
        admin,
        PromptTemplateUpdate(
            capability="image",
            modelGroupId=image_model.id,
            templateType="prompt_optimize",
            name="Image model",
            content="model {{prompt}}",
            enabled=False,
        ),
    )

    overview = prompt_template_model_status_overview(db, capability="image")

    image_row = next(item for item in overview if item["modelGroupId"] == image_model.id)
    assert image_row["modelName"] == "Image Model"
    assert image_row["usesDefault"] is True
    assert image_row["promptOptimizeEnabled"] is False
    assert image_row["hasModelTemplate"] is True
    assert image_row["modelTemplateEnabled"] is False

    assert all(item["modelGroupId"] != text_model.id for item in overview)


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


def test_admin_users_can_be_filtered_by_role_and_status() -> None:
    from app.admin_service import list_admin_users

    db = make_db()
    admin = make_user(db, "admin@example.com", external_id="admin-filter")
    operator = make_user(db, "operator@example.com", external_id="operator-filter")
    disabled_operator = make_user(
        db,
        "disabled.operator@example.com",
        external_id="disabled-operator-filter",
        status="disabled",
    )
    normal = make_user(db, "normal@example.com", external_id="normal-filter")
    db.add_all(
        [
            AdminRoleAssignment(user_id=admin.id, role="admin", assigned_by=admin.id),
            AdminRoleAssignment(user_id=operator.id, role="operator", assigned_by=admin.id),
            AdminRoleAssignment(user_id=disabled_operator.id, role="operator", assigned_by=admin.id),
        ]
    )
    db.commit()

    operator_ids = {user.id for user in list_admin_users(db, role="operator")}
    assert operator_ids == {operator.id, disabled_operator.id}

    active_operator_ids = {user.id for user in list_admin_users(db, role="operator", status="active")}
    assert active_operator_ids == {operator.id}

    regular_user_ids = {user.id for user in list_admin_users(db, role="user")}
    assert regular_user_ids == {normal.id}


def test_admin_user_serialization_uses_latest_session_ip() -> None:
    from app.admin_service import serialize_admin_user

    db = make_db()
    user = make_user(db, "recent-ip@example.com", external_id="recent-ip")
    now = utcnow()
    db.add_all(
        [
            SessionRecord(
                user_id=user.id,
                token_hash="older-token",
                expires_at=now + timedelta(days=1),
                created_at=now - timedelta(hours=2),
                last_seen_at=now - timedelta(hours=2),
                client_ip="10.0.0.1",
            ),
            SessionRecord(
                user_id=user.id,
                token_hash="newer-token",
                expires_at=now + timedelta(days=1),
                created_at=now - timedelta(hours=1),
                last_seen_at=now - timedelta(minutes=5),
                client_ip="203.0.113.8",
            ),
            SessionRecord(
                user_id=user.id,
                token_hash="expired-token",
                expires_at=now - timedelta(minutes=1),
                created_at=now - timedelta(minutes=30),
                last_seen_at=now - timedelta(minutes=1),
                client_ip="198.51.100.10",
            ),
        ]
    )
    db.commit()
    db.refresh(user)

    payload = serialize_admin_user(user)

    assert payload["sessionCount"] == 2
    assert payload["recentLoginIp"] == "198.51.100.10"


def test_admin_users_route_applies_role_and_status_filters() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="route-admin-filter")
    operator = make_user(db, "route.operator@example.com", external_id="route-operator-filter")
    disabled_operator = make_user(
        db,
        "route.disabled.operator@example.com",
        external_id="route-disabled-operator-filter",
        status="disabled",
    )
    normal = make_user(db, "route.normal@example.com", external_id="route-normal-filter")
    db.add_all(
        [
            AdminRoleAssignment(user_id=operator.id, role="operator", assigned_by=admin.id),
            AdminRoleAssignment(user_id=disabled_operator.id, role="operator", assigned_by=admin.id),
        ]
    )
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    response = client.get("/api/admin/users?role=operator&status=active")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["users"]] == [operator.id]
    assert normal.id not in {item["id"] for item in response.json()["users"]}
    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_users_route_marks_duplicate_identity_groups() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="route-duplicate-admin")
    first = make_user(db, "dup.admin@example.com", external_id="route-duplicate-first")
    second = make_user(db, "dup.admin@example.com", external_id="route-duplicate-second")
    unique = make_user(db, "unique.admin@example.com", external_id="route-duplicate-unique")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    response = client.get("/api/admin/users?search=admin@example.com")

    assert response.status_code == 200
    users = response.json()["users"]
    duplicate_rows = [item for item in users if item["email"] == "dup.admin@example.com"]
    assert {item["id"] for item in duplicate_rows} == {first.id, second.id}
    assert all(item["duplicateIdentity"]["identity"] == "email:dup.admin@example.com" for item in duplicate_rows)
    assert all(item["duplicateIdentity"]["duplicateCount"] == 2 for item in duplicate_rows)
    assert all(item["duplicateIdentity"]["targetUserId"] in {first.id, second.id} for item in duplicate_rows)
    unique_row = next(item for item in users if item["id"] == unique.id)
    assert unique_row["duplicateIdentity"] is None

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_users_route_normalizes_duplicate_email_and_phone_fallback() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="route-duplicate-normalize-admin")
    upper = make_user(db, "Case.Dup@Example.com", external_id="route-duplicate-case-upper")
    lower = make_user(db, "case.dup@example.com", external_id="route-duplicate-case-lower")
    phone_a = make_user(db, "", external_id="route-duplicate-phone-a")
    phone_b = make_user(db, "", external_id="route-duplicate-phone-b")
    phone_a.phone = "13800138000"
    phone_b.phone = "13800138000"
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    response = client.get("/api/admin/users")

    assert response.status_code == 200
    users = response.json()["users"]
    case_rows = [item for item in users if item["id"] in {upper.id, lower.id}]
    assert all(item["duplicateIdentity"]["identity"] == "email:case.dup@example.com" for item in case_rows)
    phone_rows = [item for item in users if item["id"] in {phone_a.id, phone_b.id}]
    assert all(item["duplicateIdentity"]["identity"] == "phone:13800138000" for item in phone_rows)

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_user_update_response_keeps_duplicate_identity() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="route-duplicate-update-admin")
    first = make_user(db, "update.dup@example.com", external_id="route-duplicate-update-first")
    make_user(db, "update.dup@example.com", external_id="route-duplicate-update-second")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    response = client.put(f"/api/admin/users/{first.id}", json={"nickname": "Updated duplicate"})

    assert response.status_code == 200
    duplicate = response.json()["user"]["duplicateIdentity"]
    assert duplicate["identity"] == "email:update.dup@example.com"
    assert duplicate["duplicateCount"] == 2

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_user_mutation_responses_keep_duplicate_identity_for_all_actions() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="route-duplicate-actions-admin")
    role_target = make_user(db, "actions.role.dup@example.com", external_id="route-duplicate-actions-role-first")
    make_user(db, "actions.role.dup@example.com", external_id="route-duplicate-actions-role-second")
    status_target = make_user(db, "actions.status.dup@example.com", external_id="route-duplicate-actions-status-first")
    make_user(db, "actions.status.dup@example.com", external_id="route-duplicate-actions-status-second")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    requests = [
        (
            lambda: client.put(
                f"/api/admin/users/{role_target.id}/role",
                json={"role": "viewer", "note": "duplicate"},
            ),
            "email:actions.role.dup@example.com",
        ),
        (
            lambda: client.post(
                f"/api/admin/users/{status_target.id}/credits/adjust",
                json={"amount": 2, "reason": "duplicate check"},
            ),
            "email:actions.status.dup@example.com",
        ),
        (lambda: client.post(f"/api/admin/users/{status_target.id}/disable"), "email:actions.status.dup@example.com"),
        (lambda: client.post(f"/api/admin/users/{status_target.id}/enable"), "email:actions.status.dup@example.com"),
        (lambda: client.post(f"/api/admin/users/{status_target.id}/delete"), "email:actions.status.dup@example.com"),
        (lambda: client.post(f"/api/admin/users/{status_target.id}/restore"), "email:actions.status.dup@example.com"),
    ]

    for make_request, expected_identity in requests:
        response = make_request()
        assert response.status_code == 200
        duplicate = response.json()["user"]["duplicateIdentity"]
        assert duplicate["identity"] == expected_identity
        assert duplicate["duplicateCount"] == 2

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_users_export_requires_permission_respects_filters_and_writes_audit_log() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    owner = make_user(db, "cage_ben@sina.com", external_id="user-export-owner")
    viewer = make_user(db, "viewer-user-export@example.com", external_id="user-export-viewer")
    operator = make_user(db, "export.operator@example.com", external_id="export-operator")
    disabled_operator = make_user(
        db,
        "export.disabled.operator@example.com",
        external_id="export-disabled-operator",
        status="disabled",
    )
    normal = make_user(db, "export.normal@example.com", external_id="export-normal")
    db.add_all(
        [
            AdminRoleAssignment(user_id=viewer.id, role="viewer", assigned_by=owner.id),
            AdminRoleAssignment(user_id=operator.id, role="operator", assigned_by=owner.id),
            AdminRoleAssignment(user_id=disabled_operator.id, role="operator", assigned_by=owner.id),
        ]
    )
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    app.dependency_overrides[get_current_user] = lambda: viewer
    denied = client.get("/api/admin/users/export", params={"role": "operator", "status": "active"})
    assert denied.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: owner
    exported = client.get("/api/admin/users/export", params={"role": "operator", "status": "active"})

    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert "attachment;" in exported.headers["content-disposition"]
    assert "用户ID,外部用户ID,邮箱,昵称,手机号,后台角色,角色来源,状态,可用积分,冻结积分,累计充值,累计消耗,累计退回,会话数,最近登录IP,最近活跃,创建时间" in exported.text
    assert operator.email in exported.text
    assert disabled_operator.email not in exported.text
    assert normal.email not in exported.text
    audit = db.query(AdminOperationLog).filter(AdminOperationLog.action == "export_users").one()
    assert audit.admin_user_id == owner.id
    assert audit.target_type == "user"
    assert audit.target_id == "export"
    assert '"count": 1' in audit.summary_json
    assert '"role": "operator"' in audit.summary_json
    assert '"status": "active"' in audit.summary_json

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


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


def test_admin_audit_logs_filter_by_actor_status_target_and_time_range() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="audit-filter-admin")
    other_admin = make_user(db, "audit-other@example.com", external_id="audit-filter-other")
    now = utcnow()
    db.add_all(
        [
            AdminOperationLog(
                admin_user_id=admin.id,
                action="disable_user",
                target_type="user",
                target_id="usr_target_1",
                status="success",
                summary_json="{}",
                created_at=now - timedelta(minutes=5),
            ),
            AdminOperationLog(
                admin_user_id=admin.id,
                action="delete_user",
                target_type="user",
                target_id="usr_target_1",
                status="error",
                summary_json="{}",
                created_at=now - timedelta(minutes=4),
            ),
            AdminOperationLog(
                admin_user_id=admin.id,
                action="restore_user",
                target_type="user",
                target_id="usr_target_1",
                status="success",
                summary_json="{}",
                created_at=now - timedelta(days=3),
            ),
            AdminOperationLog(
                admin_user_id=admin.id,
                action="publish_model",
                target_type="model",
                target_id="mdl_target_1",
                status="success",
                summary_json="{}",
                created_at=now - timedelta(days=2),
            ),
            AdminOperationLog(
                admin_user_id=other_admin.id,
                action="update_model",
                target_type="model",
                target_id="mdl_target_2",
                status="error",
                summary_json="{}",
                created_at=now - timedelta(minutes=2),
            ),
        ]
    )
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    response = client.get(
        "/api/admin/audit-logs",
        params={
            "adminUserId": admin.id,
            "targetType": "user",
            "targetId": "target_1",
            "status": "success",
            "startAt": (now - timedelta(hours=1)).isoformat(),
            "endAt": (now + timedelta(hours=1)).isoformat(),
        },
    )

    assert response.status_code == 200
    logs = response.json()["logs"]
    assert [item["action"] for item in logs] == ["disable_user"]

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


@pytest.mark.parametrize(
    ("action", "expected_risk"),
    [
        ("delete_user", "high"),
        ("disable_user", "high"),
        ("update_admin_role", "high"),
        ("merge_duplicate_users", "high"),
        ("unpublish_model", "high"),
        ("delete_model", "high"),
        ("adjust_credits", "medium"),
        ("update_credit_settings", "medium"),
        ("save_prompt_template", "medium"),
        ("publish_model", "medium"),
        ("restore_user", "medium"),
        ("update_model", "medium"),
    ],
)
def test_admin_audit_logs_classify_sensitive_actions(action: str, expected_risk: str) -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id=f"audit-risk-{action}")
    db.add(
        AdminOperationLog(
            admin_user_id=admin.id,
            action=action,
            target_type="user",
            target_id="usr_target",
            status="success",
            summary_json="{}",
        )
    )
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    response = client.get("/api/admin/audit-logs", params={"risk": expected_risk})

    assert response.status_code == 200
    assert response.json()["logs"][0]["action"] == action
    assert response.json()["logs"][0]["riskLevel"] == expected_risk

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_audit_logs_error_status_is_always_high_risk() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="audit-risk-error")
    db.add(
        AdminOperationLog(
            admin_user_id=admin.id,
            action="view_dashboard",
            target_type="dashboard",
            target_id="",
            status="error",
            summary_json="{}",
        )
    )
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    response = client.get("/api/admin/audit-logs", params={"risk": "high"})

    assert response.status_code == 200
    assert response.json()["logs"][0]["action"] == "view_dashboard"
    assert response.json()["logs"][0]["riskLevel"] == "high"

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_audit_logs_apply_risk_filter_before_limit() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="audit-risk-limit")
    now = utcnow()
    db.add_all(
        [
            AdminOperationLog(
                admin_user_id=admin.id,
                action="view_dashboard",
                target_type="dashboard",
                status="success",
                summary_json="{}",
                created_at=now,
            ),
            AdminOperationLog(
                admin_user_id=admin.id,
                action="update_admin_role",
                target_type="user",
                target_id="usr_target",
                status="success",
                summary_json="{}",
                created_at=now - timedelta(minutes=1),
            ),
        ]
    )
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    response = client.get("/api/admin/audit-logs", params={"risk": "high", "limit": 1})

    assert response.status_code == 200
    assert [item["action"] for item in response.json()["logs"]] == ["update_admin_role"]

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_audit_logs_risk_filter_searches_beyond_default_limit_window() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="audit-risk-window")
    now = utcnow()
    rows = [
        AdminOperationLog(
            admin_user_id=admin.id,
            action="view_dashboard",
            target_type="dashboard",
            status="success",
            summary_json="{}",
            created_at=now - timedelta(seconds=index),
        )
        for index in range(301)
    ]
    rows.append(
        AdminOperationLog(
            admin_user_id=admin.id,
            action="update_admin_role",
            target_type="user",
            target_id="usr_deep_high_risk",
            status="success",
            summary_json="{}",
            created_at=now - timedelta(seconds=400),
        )
    )
    db.add_all(rows)
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    response = client.get("/api/admin/audit-logs", params={"risk": "high", "limit": 1})

    assert response.status_code == 200
    assert [item["targetId"] for item in response.json()["logs"]] == ["usr_deep_high_risk"]

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_audit_logs_export_requires_permission_and_respects_filters() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.db_models import AdminRoleAssignment
    from app.main import app

    db = make_db()
    owner = make_user(db, "cage_ben@sina.com", external_id="audit-export-owner")
    viewer = make_user(db, "viewer-audit-export@example.com", external_id="audit-export-viewer")
    now = utcnow()
    db.add_all(
        [
            AdminRoleAssignment(user_id=viewer.id, role="viewer", assigned_by=owner.id),
            AdminOperationLog(
                admin_user_id=owner.id,
                action="delete_user",
                target_type="user",
                target_id="usr_export_target",
                status="success",
                summary_json='{"reason":"cleanup"}',
                created_at=now,
            ),
            AdminOperationLog(
                admin_user_id=owner.id,
                action="update_model",
                target_type="model",
                target_id="mdl_export_other",
                status="error",
                summary_json='{"reason":"other"}',
                created_at=now - timedelta(minutes=1),
            ),
        ]
    )
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    app.dependency_overrides[get_current_user] = lambda: viewer
    denied = client.get("/api/admin/audit-logs/export", params={"targetType": "user"})
    assert denied.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: owner
    exported = client.get("/api/admin/audit-logs/export", params={"targetType": "user", "risk": "high"})

    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert "attachment;" in exported.headers["content-disposition"]
    assert "日志ID,管理员,操作,目标类型,目标ID,风险等级,状态,摘要,创建时间" in exported.text
    assert "delete_user" in exported.text
    assert "usr_export_target" in exported.text
    assert "high" in exported.text
    assert "cleanup" in exported.text
    assert "mdl_export_other" not in exported.text

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_records_export_requires_permission_respects_filters_and_writes_audit_log() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    owner = make_user(db, "cage_ben@sina.com", external_id="record-export-owner")
    viewer = make_user(db, "viewer-record-export@example.com", external_id="record-export-viewer")
    user = make_user(db, "record-user@example.com", external_id="record-export-user")
    other_user = make_user(db, "other-record-user@example.com", external_id="record-export-other-user")
    model = make_model(db, owner, name="Record Export Model", capability="text")
    other_model = make_model(db, owner, name="Other Export Model", capability="text")
    db.add(AdminRoleAssignment(user_id=viewer.id, role="viewer", assigned_by=owner.id))
    db.flush()
    conversation = Conversation(user_id=user.id, title="record export", capability="text", model_group_id=model.id)
    other_conversation = Conversation(
        user_id=other_user.id,
        title="other record export",
        capability="text",
        model_group_id=other_model.id,
    )
    db.add_all([conversation, other_conversation])
    db.flush()
    message = ConversationMessage(
        id="msg_record_export_match",
        conversation_id=conversation.id,
        user_id=user.id,
        model_group_id=model.id,
        role="assistant",
        capability="text",
        content="record export answer",
        status="success",
        request_json=json.dumps({"prompt": "record export prompt"}),
        response_json=json.dumps({"content": "record export answer"}),
    )
    other_message = ConversationMessage(
        id="msg_record_export_other",
        conversation_id=other_conversation.id,
        user_id=other_user.id,
        model_group_id=other_model.id,
        role="assistant",
        capability="text",
        content="other answer",
        status="error",
        error_message="other error",
    )
    db.add_all([message, other_message])
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    app.dependency_overrides[get_current_user] = lambda: viewer
    denied = client.get("/api/admin/records/text/export", params={"keyword": "record export"})
    assert denied.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: owner
    exported = client.get(
        "/api/admin/records/text/export",
        params={"keyword": "record export", "modelGroupId": model.id, "status": "success"},
    )

    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert "attachment;" in exported.headers["content-disposition"]
    assert "消息ID,用户,类型,模型,状态,提示词,响应,错误信息,资源数,任务ID,耗时ms,创建时间" in exported.text
    assert "msg_record_export_match" in exported.text
    assert "record-user@example.com" in exported.text
    assert "record export answer" in exported.text
    assert "msg_record_export_other" not in exported.text
    audit = db.query(AdminOperationLog).filter(AdminOperationLog.action == "export_records").one()
    assert audit.admin_user_id == owner.id
    assert audit.target_type == "record"
    assert audit.target_id == "text"

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_credit_settings_and_user_adjustment_routes() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.config import get_settings
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="admin-credit-route")
    normal = make_user(db, "normal-credit@example.com", external_id="normal-credit-route")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    settings_response = client.get("/api/admin/credits/settings")
    assert settings_response.status_code == 200
    assert settings_response.json()["settings"]["defaults"]["image"] == 1

    update_response = client.put(
        "/api/admin/credits/settings",
        json={
            "defaults": {"text": 0, "image": 2, "video": 5},
            "signupBonusEnabled": True,
            "signupBonusAmount": 7,
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["settings"]["defaults"] == {"text": 0, "image": 2, "video": 5}
    assert update_response.json()["settings"]["signupBonusAmount"] == 7

    adjust_response = client.post(
        f"/api/admin/users/{normal.id}/credits/adjust",
        json={"amount": 10, "reason": "manual recharge"},
    )
    assert adjust_response.status_code == 200
    assert adjust_response.json()["account"]["balance"] == 10
    assert adjust_response.json()["transaction"]["reason"] == "manual recharge"

    user_credits = client.get(f"/api/admin/users/{normal.id}/credits")
    assert user_credits.status_code == 200
    assert user_credits.json()["account"]["balance"] == 10
    assert user_credits.json()["transactions"][0]["amount"] == 10

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_identifier_permissions_are_enforced_on_sensitive_admin_routes() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.config import Settings, get_settings
    from app.database import get_db
    from app.main import app

    db = make_db()
    operator = make_user(db, "operator@example.com", external_id="ops-admin")
    target = make_user(db, "delete-target@example.com", external_id="delete-target")
    model = make_model(db, operator)
    settings = Settings(admin_emails=[], admin_identifiers=["ops-admin"])

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: operator
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)

    models = client.get("/api/admin/models")
    assert models.status_code == 200

    model_update = client.put(
        f"/api/admin/models/{model.id}",
        json={"publicDisplayName": "Operator model"},
    )
    assert model_update.status_code == 200

    credit_settings = client.put(
        "/api/admin/credits/settings",
        json={"defaults": {"text": 1, "image": 2, "video": 3}},
    )
    assert credit_settings.status_code == 403

    delete_user = client.post(f"/api/admin/users/{target.id}/delete")
    assert delete_user.status_code == 403

    role_update = client.put(
        f"/api/admin/users/{target.id}/role",
        json={"role": "viewer", "note": "limit access"},
    )
    assert role_update.status_code == 403

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_read_routes_enforce_permission_points() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.db_models import AdminRoleAssignment
    from app.main import app

    db = make_db()
    owner = make_user(db, "cage_ben@sina.com", external_id="owner-read-permissions")
    viewer = make_user(db, "viewer-read@example.com", external_id="viewer-read")
    operator = make_user(db, "operator-read@example.com", external_id="operator-read")
    db.add_all(
        [
            AdminRoleAssignment(user_id=viewer.id, role="viewer", assigned_by=owner.id),
            AdminRoleAssignment(user_id=operator.id, role="operator", assigned_by=owner.id),
        ]
    )
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    app.dependency_overrides[get_current_user] = lambda: viewer
    assert client.get("/api/admin/dashboard/metrics").status_code == 200
    assert client.get("/api/admin/records/text").status_code == 200
    assert client.get("/api/admin/audit-logs").status_code == 200
    assert client.get("/api/admin/credits/settings").status_code == 200
    assert client.get("/api/admin/users").status_code == 200
    assert client.get("/api/admin/models").status_code == 200
    assert client.post(f"/api/admin/users/{operator.id}/credits/adjust", json={"amount": 1, "reason": "x"}).status_code == 403
    assert client.put("/api/admin/credits/settings", json={"signupBonusAmount": 3}).status_code == 403

    app.dependency_overrides[get_current_user] = lambda: operator
    assert client.get("/api/admin/models").status_code == 200
    assert client.post(f"/api/admin/models/{make_model(db, owner).id}/publish").status_code == 403
    assert client.put("/api/admin/credits/settings", json={"signupBonusAmount": 3}).status_code == 403

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_record_routes_check_record_view_permission(monkeypatch) -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="record-view-denied")

    def override_db():
        yield db

    def deny_record_view(user: User | None, permission: str, settings) -> bool:
        if permission == "record:view":
            return False
        return True

    monkeypatch.setattr(main_module, "can", deny_record_view)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    response = client.get("/api/admin/records/text")

    assert response.status_code == 403

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_records_hide_raw_json_without_raw_permission() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    owner = make_user(db, "cage_ben@sina.com", external_id="raw-owner")
    viewer = make_user(db, "viewer-raw@example.com", external_id="viewer-raw")
    db.add(AdminRoleAssignment(user_id=viewer.id, role="viewer", assigned_by=owner.id))
    model = make_model(db, owner, name="Raw Image", capability="image")
    conversation = Conversation(
        user_id=owner.id,
        title="raw image",
        capability="image",
        model_group_id=model.id,
    )
    db.add(conversation)
    db.flush()
    message = ConversationMessage(
        conversation_id=conversation.id,
        user_id=owner.id,
        model_group_id=model.id,
        role="assistant",
        capability="image",
        content="done",
        status="success",
        request_json='{"prompt":"secret prompt","seed":123,"apiKey":"sk-secret"}',
        response_json='{"taskId":"task_raw_1","imageUrl":"https://cdn.example.com/raw.png","rawProvider":{"token":"secret"}}',
    )
    db.add(message)
    db.flush()
    db.add(
        CallLog(
            user_id=owner.id,
            model_group_id=model.id,
            capability="image",
            endpoint="/api/proxy/image",
            status="success",
            duration_ms=1200,
            request_params_json='{"prompt":"call secret","size":"1024x1024"}',
            response_summary_json='{"taskId":"task_raw_1","status":"completed","provider":"full"}',
            conversation_id=conversation.id,
            message_id=message.id,
        )
    )
    db.add(
        TaskEvent(
            task_id="task_raw_1",
            event_type="completed",
            status="success",
            capability="image",
            endpoint="/api/proxy/image/query",
            user_id=owner.id,
            model_group_id=model.id,
            conversation_id=conversation.id,
            message_id=message.id,
            payload_json='{"taskId":"task_raw_1","status":"completed","providerPayload":{"signedUrl":"secret"}}',
        )
    )
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: viewer
    client = TestClient(app)

    records_response = client.get("/api/admin/records/images")
    detail_response = client.get(f"/api/admin/records/detail/{message.id}")
    timeline_response = client.get("/api/admin/tasks/task_raw_1/timeline")

    assert records_response.status_code == 200
    assert detail_response.status_code == 200
    assert timeline_response.status_code == 200
    record = records_response.json()["records"][0]
    detail = detail_response.json()["record"]
    timeline = timeline_response.json()["events"]
    assert record["requestParams"] == {"hidden": True, "reason": "record:raw_json required"}
    assert record["responseSummary"] == {"hidden": True, "reason": "record:raw_json required"}
    assert detail["request"] == {"hidden": True, "reason": "record:raw_json required"}
    assert detail["response"] == {"hidden": True, "reason": "record:raw_json required"}
    assert all("payload" not in event for event in detail["timeline"])
    assert all("responseSummary" not in event for event in detail["timeline"])
    assert all("payload" not in event for event in timeline)
    assert all("responseSummary" not in event for event in timeline)

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_records_keep_raw_json_with_raw_permission() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="raw-admin")
    model = make_model(db, admin, name="Raw Image", capability="image")
    conversation = Conversation(
        user_id=admin.id,
        title="raw image",
        capability="image",
        model_group_id=model.id,
    )
    db.add(conversation)
    db.flush()
    message = ConversationMessage(
        conversation_id=conversation.id,
        user_id=admin.id,
        model_group_id=model.id,
        role="assistant",
        capability="image",
        content="done",
        status="success",
        request_json='{"prompt":"secret prompt","seed":123}',
        response_json='{"taskId":"task_raw_admin","imageUrl":"https://cdn.example.com/raw.png"}',
    )
    db.add(message)
    db.add(
        TaskEvent(
            task_id="task_raw_admin",
            event_type="completed",
            status="success",
            capability="image",
            endpoint="/api/proxy/image/query",
            user_id=admin.id,
            model_group_id=model.id,
            conversation_id=conversation.id,
            message_id=message.id,
            payload_json='{"taskId":"task_raw_admin","status":"completed"}',
        )
    )
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    record = client.get("/api/admin/records/images").json()["records"][0]
    detail = client.get(f"/api/admin/records/detail/{message.id}").json()["record"]
    timeline = client.get("/api/admin/tasks/task_raw_admin/timeline").json()["events"]

    assert record["requestParams"]["prompt"] == "secret prompt"
    assert record["responseSummary"]["imageUrl"] == "https://cdn.example.com/raw.png"
    assert detail["request"]["seed"] == 123
    assert detail["response"]["taskId"] == "task_raw_admin"
    assert timeline[0]["payload"]["taskId"] == "task_raw_admin"

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


@pytest.mark.parametrize(
    ("path", "permission", "method", "json_body"),
    [
        ("/api/admin/models", "model:view", "GET", None),
        ("/api/admin/models/missing/health", "model:view", "GET", None),
        ("/api/admin/overview", "record:view", "GET", None),
        ("/api/admin/dashboard/metrics", "record:view", "GET", None),
        ("/api/admin/credits/settings", "credit:view", "GET", None),
        ("/api/admin/credits/transactions", "credit:view", "GET", None),
        ("/api/admin/overview/users", "user:view", "GET", None),
        ("/api/admin/overview/models", "model:view", "GET", None),
        ("/api/admin/prompt-templates", "settings:view", "GET", None),
        ("/api/admin/prompt-templates/test", "settings:view", "POST", {"content": "{{prompt}}", "prompt": "x"}),
        ("/api/admin/users", "user:view", "GET", None),
        ("/api/admin/users/missing/credits", "credit:view", "GET", None),
        ("/api/admin/records/text", "record:view", "GET", None),
        ("/api/admin/records/images", "record:view", "GET", None),
        ("/api/admin/records/videos", "record:view", "GET", None),
        ("/api/admin/records/detail/missing", "record:view", "GET", None),
        ("/api/admin/tasks/task_missing/timeline", "record:view", "GET", None),
        ("/api/admin/audit-logs", "audit:view", "GET", None),
    ],
)
def test_admin_read_routes_have_explicit_permission_guards(
    monkeypatch,
    path: str,
    permission: str,
    method: str,
    json_body: dict[str, str] | None,
) -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id=f"guard-{permission}-{path}")

    def override_db():
        yield db

    def deny_expected_permission(user: User | None, checked_permission: str, settings) -> bool:
        return checked_permission != permission

    monkeypatch.setattr(main_module, "can", deny_expected_permission)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    response = client.request(method, path, json=json_body)

    assert response.status_code == 403

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


@pytest.mark.parametrize("role", ["admin", "operator", "viewer"])
def test_admin_user_merge_route_requires_maintenance_permission(role: str) -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    owner = make_user(db, "cage_ben@sina.com", external_id=f"merge-owner-{role}")
    actor = make_user(db, f"{role}-merge@example.com", external_id=f"merge-{role}")
    db.add(AdminRoleAssignment(user_id=actor.id, role=role, assigned_by=owner.id))
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: actor
    client = TestClient(app)

    response = client.post(
        "/api/admin/maintenance/user-merge",
        json={"apply": False, "identityFilter": "email:dup@example.com"},
    )

    assert response.status_code == 403

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_user_merge_dry_run_returns_summary_without_changing_users() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="merge-dry-admin")
    first = make_user(db, "dup@example.com", external_id="merge-dry-first")
    second = make_user(db, "dup@example.com", external_id="merge-dry-second")
    api_key = make_api_key(db, second)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    response = client.post(
        "/api/admin/maintenance/user-merge",
        json={"apply": False, "identityFilter": "email:dup@example.com"},
    )

    assert response.status_code == 200
    payload = response.json()["summary"]
    assert payload["apply"] is False
    assert payload["groupCount"] == 1
    assert payload["mergedUsers"] == 1
    assert payload["movedRecords"] == 0
    assert db.get(User, first.id) is not None
    assert db.get(User, second.id) is not None
    db.refresh(api_key)
    assert api_key.user_id == second.id

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_user_merge_apply_requires_csrf_token() -> None:
    import app.main as main_module
    from app.database import Base, get_db
    from app.main import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    seed_db = TestingSession()
    make_user(seed_db, "cage_ben@sina.com", external_id="merge-csrf-admin")
    make_user(seed_db, "dup@example.com", external_id="merge-csrf-first")
    make_user(seed_db, "dup@example.com", external_id="merge-csrf-second")
    seed_db.close()

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    login = client.post(
        "/api/auth/dev-login",
        json={"externalUserId": "merge-csrf-admin", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    assert login.status_code == 200

    response = client.post(
        "/api/admin/maintenance/user-merge",
        json={"apply": True, "identityFilter": "email:dup@example.com"},
    )

    assert response.status_code == 403
    verify_db = TestingSession()
    try:
        assert verify_db.query(User).filter(User.email == "dup@example.com").count() == 2
    finally:
        verify_db.close()

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_user_merge_apply_merges_records_and_writes_audit_log() -> None:
    import json

    import app.main as main_module
    from app.database import Base, get_db
    from app.main import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    seed_db = TestingSession()
    admin = make_user(seed_db, "cage_ben@sina.com", external_id="merge-apply-admin")
    first = make_user(seed_db, "dup@example.com", external_id="merge-apply-first")
    second = make_user(seed_db, "dup@example.com", external_id="merge-apply-second")
    seed_db.add(
        UserCredential(
            user_id=first.id,
            provider="local",
            identifier="dup@example.com",
            email="dup@example.com",
            password_hash="hash",
        )
    )
    api_key = make_api_key(seed_db, second)
    conversation = Conversation(
        user_id=second.id,
        title="duplicate conversation",
        capability="text",
        model_group_id=None,
        status="active",
    )
    seed_db.add(conversation)
    seed_db.commit()
    seed_db.close()

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    login = client.post(
        "/api/auth/dev-login",
        json={"externalUserId": admin.external_user_id, "email": admin.email, "nickname": "Admin"},
    )
    assert login.status_code == 200

    response = client.post(
        "/api/admin/maintenance/user-merge",
        json={"apply": True, "identityFilter": "email:dup@example.com"},
        headers=csrf_headers(client),
    )

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["apply"] is True
    assert summary["groupCount"] == 1
    assert summary["mergedUsers"] == 1
    assert summary["movedRecords"] >= 1
    assert summary["groups"][0]["targetUserId"] == first.id
    assert summary["groups"][0]["sourceUserIds"] == [second.id]

    verify_db = TestingSession()
    try:
        assert verify_db.get(User, first.id) is not None
        assert verify_db.get(User, second.id) is None
        assert verify_db.get(ApiKey, api_key.id).user_id == first.id
        assert verify_db.get(Conversation, conversation.id).user_id == first.id
        log = (
            verify_db.query(AdminOperationLog)
            .filter(AdminOperationLog.action == "merge_duplicate_users")
            .one()
        )
        assert log.admin_user_id == admin.id
        assert log.target_type == "maintenance"
        audit_summary = json.loads(log.summary_json)
        assert audit_summary["apply"] is True
        assert audit_summary["identityFilter"] == "email:dup@example.com"
        assert audit_summary["groupCount"] == 1
        assert audit_summary["mergedUsers"] == 1
        assert audit_summary["movedRecords"] >= 1
    finally:
        verify_db.close()

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_user_merge_apply_preserves_credit_task_health_and_role_records() -> None:
    import app.main as main_module
    from app.database import Base, get_db
    from app.main import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    seed_db = TestingSession()
    admin = make_user(seed_db, "cage_ben@sina.com", external_id="merge-linked-admin")
    target = make_user(seed_db, "dup-linked@example.com", external_id="merge-linked-target")
    source = make_user(seed_db, "dup-linked@example.com", external_id="merge-linked-source")
    actor = make_user(seed_db, "actor-linked@example.com", external_id="merge-linked-actor")
    seed_db.add(
        UserCredential(
            user_id=target.id,
            provider="local",
            identifier="dup-linked@example.com",
            email="dup-linked@example.com",
            password_hash="hash",
        )
    )
    target_account = UserCreditAccount(
        user_id=target.id,
        balance=10,
        reserved_balance=2,
        total_recharged=20,
        total_spent=5,
        total_refunded=1,
    )
    source_account = UserCreditAccount(
        user_id=source.id,
        balance=7,
        reserved_balance=3,
        total_recharged=8,
        total_spent=4,
        total_refunded=2,
    )
    seed_db.add_all([target_account, source_account])
    api_key = make_api_key(seed_db, source)
    model = ModelGroup(
        user_id=source.id,
        api_key_id=api_key.id,
        name="Source model",
        vendor="OpenAI",
        capability="image",
        adapter="image-openai",
    )
    seed_db.add(model)
    seed_db.flush()
    source_transaction = CreditTransaction(
        user_id=source.id,
        type="generation_reserve",
        amount=-3,
        balance_after=7,
        reserved_after=3,
        capability="image",
        model_group_id=model.id,
        task_id="task_merge_source",
        status="reserved",
    )
    operator_transaction = CreditTransaction(
        user_id=target.id,
        type="admin_adjustment",
        amount=5,
        balance_after=10,
        reserved_after=2,
        operator_user_id=source.id,
        status="succeeded",
    )
    task_event = TaskEvent(
        task_id="task_merge_source",
        event_type="created",
        status="running",
        capability="image",
        endpoint="/api/proxy/image",
        user_id=source.id,
        model_group_id=model.id,
    )
    health_check = ModelHealthCheck(
        model_group_id=model.id,
        admin_user_id=source.id,
        status="success",
        duration_ms=120,
        message="ok",
    )
    source_role = AdminRoleAssignment(user_id=source.id, role="viewer", assigned_by=actor.id, note="source role")
    target_role = AdminRoleAssignment(user_id=target.id, role="operator", assigned_by=source.id, note="target role")
    actor_role = AdminRoleAssignment(user_id=actor.id, role="viewer", assigned_by=source.id, note="actor role")
    seed_db.add_all(
        [
            source_transaction,
            operator_transaction,
            task_event,
            health_check,
            source_role,
            target_role,
            actor_role,
        ]
    )
    seed_db.commit()
    source_account_id = source_account.id
    seed_db.close()

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    login = client.post(
        "/api/auth/dev-login",
        json={"externalUserId": admin.external_user_id, "email": admin.email, "nickname": "Admin"},
    )
    assert login.status_code == 200

    response = client.post(
        "/api/admin/maintenance/user-merge",
        json={"apply": True, "identityFilter": "email:dup-linked@example.com"},
        headers=csrf_headers(client),
    )

    assert response.status_code == 200
    assert response.json()["summary"]["groups"][0]["targetUserId"] == target.id
    verify_db = TestingSession()
    try:
        assert verify_db.get(User, source.id) is None
        merged_account = verify_db.query(UserCreditAccount).filter(UserCreditAccount.user_id == target.id).one()
        assert merged_account.balance == 17
        assert merged_account.reserved_balance == 5
        assert merged_account.total_recharged == 28
        assert merged_account.total_spent == 9
        assert merged_account.total_refunded == 3
        assert verify_db.get(UserCreditAccount, source_account_id) is None
        assert verify_db.get(CreditTransaction, source_transaction.id).user_id == target.id
        assert verify_db.get(CreditTransaction, operator_transaction.id).operator_user_id == target.id
        assert verify_db.get(TaskEvent, task_event.id).user_id == target.id
        assert verify_db.get(ModelHealthCheck, health_check.id).admin_user_id == target.id
        assert verify_db.get(AdminRoleAssignment, target_role.id).assigned_by == target.id
        assert verify_db.get(AdminRoleAssignment, actor_role.id).assigned_by == target.id
        assert verify_db.get(AdminRoleAssignment, source_role.id) is None
        assert verify_db.query(AdminRoleAssignment).filter(AdminRoleAssignment.user_id == target.id).one().role == "operator"
    finally:
        verify_db.close()

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_user_merge_audit_uses_surviving_admin_when_actor_is_merged_source() -> None:
    import json

    import app.main as main_module
    from app.database import Base, get_db
    from app.main import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    seed_db = TestingSession()
    target_admin = make_user(seed_db, "cage_ben@sina.com", external_id="merge-self-target")
    source_admin = make_user(seed_db, "cage_ben@sina.com", external_id="merge-self-source")
    seed_db.add(
        UserCredential(
            user_id=target_admin.id,
            provider="local",
            identifier="cage_ben@sina.com",
            email="cage_ben@sina.com",
            password_hash="hash",
        )
    )
    seed_db.commit()
    seed_db.close()

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    login = client.post(
        "/api/auth/dev-login",
        json={
            "externalUserId": source_admin.external_user_id,
            "email": source_admin.email,
            "nickname": "Source Admin",
        },
    )
    assert login.status_code == 200

    response = client.post(
        "/api/admin/maintenance/user-merge",
        json={"apply": True, "identityFilter": "email:cage_ben@sina.com"},
        headers=csrf_headers(client),
    )

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["groups"][0]["targetUserId"] == target_admin.id
    assert summary["groups"][0]["sourceUserIds"] == [source_admin.id]
    verify_db = TestingSession()
    try:
        assert verify_db.get(User, source_admin.id) is None
        log = (
            verify_db.query(AdminOperationLog)
            .filter(AdminOperationLog.action == "merge_duplicate_users")
            .one()
        )
        assert log.admin_user_id == target_admin.id
        audit_summary = json.loads(log.summary_json)
        assert audit_summary["actorUserId"] == target_admin.id
    finally:
        verify_db.close()

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_user_merge_dry_run_preserves_credit_task_health_and_role_records() -> None:
    from app.user_maintenance import merge_duplicate_users_by_identity

    db = make_db()
    target = make_user(db, "dup-dry-linked@example.com", external_id="merge-dry-linked-target")
    source = make_user(db, "dup-dry-linked@example.com", external_id="merge-dry-linked-source")
    db.add(
        UserCredential(
            user_id=target.id,
            provider="local",
            identifier="dup-dry-linked@example.com",
            email="dup-dry-linked@example.com",
            password_hash="hash",
        )
    )
    source_account = UserCreditAccount(user_id=source.id, balance=7, reserved_balance=3)
    api_key = make_api_key(db, source)
    model = ModelGroup(
        user_id=source.id,
        api_key_id=api_key.id,
        name="Source dry model",
        capability="image",
        adapter="image-openai",
    )
    db.add_all([source_account, model])
    db.flush()
    transaction = CreditTransaction(
        user_id=source.id,
        type="generation_reserve",
        amount=-3,
        operator_user_id=source.id,
        status="reserved",
    )
    task_event = TaskEvent(task_id="task_dry", user_id=source.id, model_group_id=model.id)
    health_check = ModelHealthCheck(model_group_id=model.id, admin_user_id=source.id, status="success")
    source_role = AdminRoleAssignment(user_id=source.id, role="viewer", assigned_by=source.id)
    db.add_all([transaction, task_event, health_check, source_role])
    db.commit()

    summary = merge_duplicate_users_by_identity(
        db,
        apply=False,
        identity_filter="email:dup-dry-linked@example.com",
    )
    db.expire_all()

    assert summary["apply"] is False
    assert summary["groupCount"] == 1
    assert db.get(User, source.id) is not None
    assert db.get(UserCreditAccount, source_account.id).user_id == source.id
    assert db.get(CreditTransaction, transaction.id).user_id == source.id
    assert db.get(CreditTransaction, transaction.id).operator_user_id == source.id
    assert db.get(TaskEvent, task_event.id).user_id == source.id
    assert db.get(ModelHealthCheck, health_check.id).admin_user_id == source.id
    assert db.get(AdminRoleAssignment, source_role.id).user_id == source.id
    assert db.get(AdminRoleAssignment, source_role.id).assigned_by == source.id


def test_user_merge_dry_run_reports_role_conflicts_without_changing_roles() -> None:
    from app.user_maintenance import merge_duplicate_users_by_identity

    db = make_db()
    target = make_user(db, "dup-dry-role@example.com", external_id="merge-dry-role-target")
    source = make_user(db, "dup-dry-role@example.com", external_id="merge-dry-role-source")
    assigner = make_user(db, "dry-role-assigner@example.com", external_id="merge-dry-role-assigner")
    db.add(
        UserCredential(
            user_id=target.id,
            provider="local",
            identifier="dup-dry-role@example.com",
            email="dup-dry-role@example.com",
            password_hash="hash",
        )
    )
    target_role = AdminRoleAssignment(user_id=target.id, role="operator", assigned_by=assigner.id, note="target role")
    source_role = AdminRoleAssignment(user_id=source.id, role="admin", assigned_by=assigner.id, note="source role")
    db.add_all([target_role, source_role])
    db.commit()

    summary = merge_duplicate_users_by_identity(
        db,
        apply=False,
        identity_filter="email:dup-dry-role@example.com",
    )
    db.expire_all()

    assert summary["roleConflictCount"] == 1
    conflict = summary["groups"][0]["roleConflicts"][0]
    assert conflict["targetRole"] == "operator"
    assert conflict["discardedRole"] == "admin"
    assert conflict["resolution"] == "kept_target_role"
    assert db.get(AdminRoleAssignment, target_role.id).user_id == target.id
    assert db.get(AdminRoleAssignment, source_role.id).user_id == source.id


def test_user_merge_moves_source_only_credit_account_to_target() -> None:
    from app.user_maintenance import merge_duplicate_users_by_identity

    db = make_db()
    target = make_user(db, "dup-credit-only@example.com", external_id="merge-credit-only-target")
    source = make_user(db, "dup-credit-only@example.com", external_id="merge-credit-only-source")
    db.add(
        UserCredential(
            user_id=target.id,
            provider="local",
            identifier="dup-credit-only@example.com",
            email="dup-credit-only@example.com",
            password_hash="hash",
        )
    )
    source_account = UserCreditAccount(
        user_id=source.id,
        balance=9,
        reserved_balance=4,
        total_recharged=13,
        total_spent=2,
        total_refunded=1,
    )
    db.add(source_account)
    db.commit()

    summary = merge_duplicate_users_by_identity(
        db,
        apply=True,
        identity_filter="email:dup-credit-only@example.com",
    )
    db.commit()
    db.expire_all()

    assert summary["mergedUsers"] == 1
    assert db.get(User, source.id) is None
    moved_account = db.get(UserCreditAccount, source_account.id)
    assert moved_account.user_id == target.id
    assert moved_account.balance == 9
    assert moved_account.reserved_balance == 4
    assert moved_account.total_recharged == 13
    assert moved_account.total_spent == 2
    assert moved_account.total_refunded == 1


def test_user_merge_moves_source_role_when_target_has_no_role() -> None:
    from app.user_maintenance import merge_duplicate_users_by_identity

    db = make_db()
    target = make_user(db, "dup-role-only@example.com", external_id="merge-role-only-target")
    source = make_user(db, "dup-role-only@example.com", external_id="merge-role-only-source")
    assigner = make_user(db, "role-assigner@example.com", external_id="merge-role-only-assigner")
    db.add(
        UserCredential(
            user_id=target.id,
            provider="local",
            identifier="dup-role-only@example.com",
            email="dup-role-only@example.com",
            password_hash="hash",
        )
    )
    source_role = AdminRoleAssignment(user_id=source.id, role="viewer", assigned_by=source.id, note="source role")
    assigner_role = AdminRoleAssignment(user_id=assigner.id, role="operator", assigned_by=source.id, note="assigner role")
    db.add_all([source_role, assigner_role])
    db.commit()

    summary = merge_duplicate_users_by_identity(
        db,
        apply=True,
        identity_filter="email:dup-role-only@example.com",
    )
    db.commit()
    db.expire_all()

    assert summary["mergedUsers"] == 1
    assert db.get(User, source.id) is None
    moved_role = db.get(AdminRoleAssignment, source_role.id)
    assert moved_role.user_id == target.id
    assert moved_role.role == "viewer"
    assert moved_role.assigned_by == target.id
    assert db.get(AdminRoleAssignment, assigner_role.id).assigned_by == target.id


def test_admin_user_merge_reports_role_conflicts_in_summary_and_audit_log() -> None:
    import json

    import app.main as main_module
    from app.database import Base, get_db
    from app.main import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    seed_db = TestingSession()
    admin = make_user(seed_db, "cage_ben@sina.com", external_id="merge-role-conflict-admin")
    target = make_user(seed_db, "dup-role-conflict@example.com", external_id="merge-role-conflict-target")
    source = make_user(seed_db, "dup-role-conflict@example.com", external_id="merge-role-conflict-source")
    seed_db.add(
        UserCredential(
            user_id=target.id,
            provider="local",
            identifier="dup-role-conflict@example.com",
            email="dup-role-conflict@example.com",
            password_hash="hash",
        )
    )
    target_role = AdminRoleAssignment(user_id=target.id, role="operator", assigned_by=admin.id, note="target role")
    source_role = AdminRoleAssignment(user_id=source.id, role="admin", assigned_by=admin.id, note="source role")
    seed_db.add_all([target_role, source_role])
    seed_db.commit()
    seed_db.close()

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    login = client.post(
        "/api/auth/dev-login",
        json={"externalUserId": admin.external_user_id, "email": admin.email, "nickname": "Admin"},
    )
    assert login.status_code == 200

    response = client.post(
        "/api/admin/maintenance/user-merge",
        json={"apply": True, "identityFilter": "email:dup-role-conflict@example.com"},
        headers=csrf_headers(client),
    )

    assert response.status_code == 200
    summary = response.json()["summary"]
    conflict = summary["groups"][0]["roleConflicts"][0]
    assert conflict["targetRole"] == "operator"
    assert conflict["discardedRole"] == "admin"
    assert conflict["sourceUserId"] == source.id
    assert conflict["resolution"] == "kept_target_role"
    assert summary["roleConflictCount"] == 1

    verify_db = TestingSession()
    try:
        log = (
            verify_db.query(AdminOperationLog)
            .filter(AdminOperationLog.action == "merge_duplicate_users")
            .one()
        )
        audit_summary = json.loads(log.summary_json)
        assert audit_summary["roleConflictCount"] == 1
        assert audit_summary["roleConflicts"][0]["discardedRole"] == "admin"
    finally:
        verify_db.close()

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_asset_cleanup_defaults_to_seven_days_and_previews_expired_files(tmp_path) -> None:
    import app.main as main_module
    from app.database import Base, get_db
    from app.main import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    seed_db = TestingSession()
    admin = make_user(seed_db, "cage_ben@sina.com", external_id="asset-cleanup-preview-admin")
    seed_db.close()

    generated_dir = tmp_path / "generated_assets"
    uploaded_dir = tmp_path / "uploaded_assets"
    generated_dir.mkdir()
    uploaded_dir.mkdir()
    old_generated = generated_dir / "old.png"
    fresh_uploaded = uploaded_dir / "fresh.png"
    old_generated.write_bytes(b"old-generated")
    fresh_uploaded.write_bytes(b"fresh-uploaded")
    old_time = (datetime.now() - timedelta(days=8)).timestamp()
    fresh_time = (datetime.now() - timedelta(days=2)).timestamp()
    os.utime(old_generated, (old_time, old_time))
    os.utime(fresh_uploaded, (fresh_time, fresh_time))

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(main_module, "GENERATED_ASSET_DIR", generated_dir)
    monkeypatch.setattr(main_module, "LOCAL_UPLOAD_DIR", uploaded_dir)
    client = TestClient(app)
    login = client.post(
        "/api/auth/dev-login",
        json={"externalUserId": admin.external_user_id, "email": admin.email, "nickname": "Admin"},
    )
    assert login.status_code == 200

    response = client.get("/api/admin/asset-cleanup/preview")

    assert response.status_code == 200
    payload = response.json()["summary"]
    assert payload["retentionDays"] == 7
    assert payload["expiredFiles"] == 1
    assert payload["totalFiles"] == 2
    assert payload["targets"][0]["label"] == "生成图片缓存"
    assert old_generated.exists()
    assert fresh_uploaded.exists()

    monkeypatch.undo()
    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_asset_cleanup_run_deletes_expired_files_and_writes_audit_log(tmp_path) -> None:
    import app.main as main_module
    from app.database import Base, get_db
    from app.main import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    seed_db = TestingSession()
    admin = make_user(seed_db, "cage_ben@sina.com", external_id="asset-cleanup-run-admin")
    seed_db.close()

    generated_dir = tmp_path / "generated_assets"
    uploaded_dir = tmp_path / "uploaded_assets"
    generated_dir.mkdir()
    uploaded_dir.mkdir()
    old_generated = generated_dir / "old.png"
    fresh_generated = generated_dir / "fresh.png"
    old_uploaded = uploaded_dir / "old-upload.png"
    old_generated.write_bytes(b"old-generated")
    fresh_generated.write_bytes(b"fresh-generated")
    old_uploaded.write_bytes(b"old-uploaded")
    old_time = (datetime.now() - timedelta(days=9)).timestamp()
    fresh_time = (datetime.now() - timedelta(hours=6)).timestamp()
    os.utime(old_generated, (old_time, old_time))
    os.utime(old_uploaded, (old_time, old_time))
    os.utime(fresh_generated, (fresh_time, fresh_time))

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(main_module, "GENERATED_ASSET_DIR", generated_dir)
    monkeypatch.setattr(main_module, "LOCAL_UPLOAD_DIR", uploaded_dir)
    client = TestClient(app)
    login = client.post(
        "/api/auth/dev-login",
        json={"externalUserId": admin.external_user_id, "email": admin.email, "nickname": "Admin"},
    )
    assert login.status_code == 200

    response = client.post(
        "/api/admin/asset-cleanup/run",
        json={},
        headers=csrf_headers(client),
    )

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["retentionDays"] == 7
    assert summary["deletedFiles"] == 2
    assert summary["failedFiles"] == 0
    assert not old_generated.exists()
    assert not old_uploaded.exists()
    assert fresh_generated.exists()
    verify_db = TestingSession()
    try:
        log = verify_db.query(AdminOperationLog).filter(AdminOperationLog.action == "asset_cache_cleanup").one()
        audit_summary = json.loads(log.summary_json)
        assert audit_summary["deletedFiles"] == 2
        assert audit_summary["retentionDays"] == 7
    finally:
        verify_db.close()

    monkeypatch.undo()
    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_asset_cleanup_settings_update_changes_retention_and_writes_audit_log() -> None:
    import app.main as main_module
    from app.database import Base, get_db
    from app.main import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    seed_db = TestingSession()
    admin = make_user(seed_db, "cage_ben@sina.com", external_id="asset-cleanup-settings-admin")
    seed_db.close()

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    login = client.post(
        "/api/auth/dev-login",
        json={"externalUserId": admin.external_user_id, "email": admin.email, "nickname": "Admin"},
    )
    assert login.status_code == 200

    response = client.put(
        "/api/admin/asset-cleanup/settings",
        json={"enabled": False, "retentionDays": 14},
        headers=csrf_headers(client),
    )

    assert response.status_code == 200
    assert response.json()["settings"]["enabled"] is False
    assert response.json()["settings"]["retentionDays"] == 14
    verify_db = TestingSession()
    try:
        log = verify_db.query(AdminOperationLog).filter(AdminOperationLog.action == "update_asset_cleanup_settings").one()
        audit_summary = json.loads(log.summary_json)
        assert audit_summary["enabled"] is False
        assert audit_summary["retentionDays"] == 14
    finally:
        verify_db.close()

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_asset_cleanup_run_rejects_invalid_retention_days() -> None:
    import app.main as main_module
    from app.database import Base, get_db
    from app.main import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    seed_db = TestingSession()
    admin = make_user(seed_db, "cage_ben@sina.com", external_id="asset-cleanup-invalid-admin")
    seed_db.close()

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    login = client.post(
        "/api/auth/dev-login",
        json={"externalUserId": admin.external_user_id, "email": admin.email, "nickname": "Admin"},
    )
    assert login.status_code == 200

    response = client.post(
        "/api/admin/asset-cleanup/run",
        json={"retentionDays": 0},
        headers=csrf_headers(client),
    )

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "缓存保留天数不能小于 1 天。"

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_asset_cleanup_view_allows_cleanup_permission_without_settings_view(monkeypatch, tmp_path) -> None:
    import app.main as main_module
    from app.database import Base, get_db
    from app.main import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    seed_db = TestingSession()
    admin = make_user(seed_db, "cage_ben@sina.com", external_id="asset-cleanup-permission-admin")
    seed_db.close()

    generated_dir = tmp_path / "generated_assets"
    uploaded_dir = tmp_path / "uploaded_assets"
    generated_dir.mkdir()
    uploaded_dir.mkdir()

    def cleanup_only_can(_user, permission: str, _settings) -> bool:
        return permission == "maintenance:asset_cleanup"

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(main_module, "can", cleanup_only_can)
    monkeypatch.setattr(main_module, "GENERATED_ASSET_DIR", generated_dir)
    monkeypatch.setattr(main_module, "LOCAL_UPLOAD_DIR", uploaded_dir)
    client = TestClient(app)
    login = client.post(
        "/api/auth/dev-login",
        json={"externalUserId": admin.external_user_id, "email": admin.email, "nickname": "Admin"},
    )
    assert login.status_code == 200

    settings_response = client.get("/api/admin/asset-cleanup/settings")
    preview_response = client.get("/api/admin/asset-cleanup/preview")

    assert settings_response.status_code == 200
    assert settings_response.json()["settings"]["retentionDays"] == 7
    assert preview_response.status_code == 200
    assert preview_response.json()["summary"]["retentionDays"] == 7

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_asset_cleanup_preview_does_not_expose_absolute_paths_to_settings_view_only(monkeypatch, tmp_path) -> None:
    import app.main as main_module
    from app.database import Base, get_db
    from app.main import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    seed_db = TestingSession()
    admin = make_user(seed_db, "cage_ben@sina.com", external_id="asset-cleanup-settings-viewer")
    seed_db.close()

    generated_dir = tmp_path / "generated_assets"
    uploaded_dir = tmp_path / "uploaded_assets"
    generated_dir.mkdir()
    uploaded_dir.mkdir()

    def settings_view_only_can(_user, permission: str, _settings) -> bool:
        return permission == "settings:view"

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(main_module, "can", settings_view_only_can)
    monkeypatch.setattr(main_module, "GENERATED_ASSET_DIR", generated_dir)
    monkeypatch.setattr(main_module, "LOCAL_UPLOAD_DIR", uploaded_dir)
    client = TestClient(app)
    login = client.post(
        "/api/auth/dev-login",
        json={"externalUserId": admin.external_user_id, "email": admin.email, "nickname": "Viewer"},
    )
    assert login.status_code == 200

    response = client.get("/api/admin/asset-cleanup/preview")

    assert response.status_code == 200
    targets = response.json()["summary"]["targets"]
    assert targets
    assert all(target["path"] == "" for target in targets)

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_scheduled_asset_cleanup_runs_at_most_once_per_day(tmp_path) -> None:
    from app.asset_cleanup import build_cleanup_targets, maybe_run_scheduled_asset_cleanup

    db = make_db()
    generated_dir = tmp_path / "generated_assets"
    uploaded_dir = tmp_path / "uploaded_assets"
    generated_dir.mkdir()
    uploaded_dir.mkdir()
    old_file = generated_dir / "old.png"
    second_old_file = uploaded_dir / "old-upload.png"
    old_file.write_bytes(b"old-generated")
    second_old_file.write_bytes(b"old-uploaded")
    base_now = datetime.now().timestamp()
    old_time = base_now - 9 * 86400
    os.utime(old_file, (old_time, old_time))
    os.utime(second_old_file, (old_time, old_time))
    targets = build_cleanup_targets(generated_dir, uploaded_dir)

    first = maybe_run_scheduled_asset_cleanup(db, targets=targets, now_ts=base_now)
    second = maybe_run_scheduled_asset_cleanup(db, targets=targets, now_ts=base_now + 3600)
    third = maybe_run_scheduled_asset_cleanup(db, targets=targets, now_ts=base_now + 90000)

    assert first is not None
    assert first["deletedFiles"] == 2
    assert second is None
    assert third is not None
    assert third["deletedFiles"] == 0


def test_scheduled_asset_cleanup_once_uses_app_asset_targets_and_closes_session(monkeypatch) -> None:
    import app.main as main_module

    class FakeSession:
        closed = False

        def close(self) -> None:
            self.closed = True

    fake_db = FakeSession()

    def fake_session_local() -> FakeSession:
        return fake_db

    def fake_targets() -> list[str]:
        return ["asset-targets"]

    def fake_maybe_run(db, *, targets):
        assert db is fake_db
        assert targets == ["asset-targets"]
        return {"deletedFiles": 1}

    monkeypatch.setattr(main_module, "SessionLocal", fake_session_local)
    monkeypatch.setattr(main_module, "asset_cleanup_targets", fake_targets)
    monkeypatch.setattr(main_module, "maybe_run_scheduled_asset_cleanup", fake_maybe_run, raising=False)

    result = main_module.run_scheduled_asset_cleanup_once()

    assert result == {"deletedFiles": 1}
    assert fake_db.closed is True


def test_scheduled_asset_cleanup_sets_auto_marker_before_running(monkeypatch, tmp_path) -> None:
    from app.asset_cleanup import (
        ASSET_CLEANUP_LAST_AUTO_RUN_KEY,
        build_cleanup_targets,
        maybe_run_scheduled_asset_cleanup,
    )

    db = make_db()
    generated_dir = tmp_path / "generated_assets"
    uploaded_dir = tmp_path / "uploaded_assets"
    generated_dir.mkdir()
    uploaded_dir.mkdir()
    targets = build_cleanup_targets(generated_dir, uploaded_dir)
    observed_marker = {"value": None}

    def fake_run_asset_cleanup(run_db, *, targets, retention_days, now_ts=None, admin=None):
        marker = run_db.get(SystemSetting, ASSET_CLEANUP_LAST_AUTO_RUN_KEY)
        observed_marker["value"] = marker.value if marker else None
        return {
            "retentionDays": retention_days,
            "cutoffTs": now_ts,
            "totalFiles": 0,
            "expiredFiles": 0,
            "totalBytes": 0,
            "expiredBytes": 0,
            "deletedFiles": 0,
            "deletedBytes": 0,
            "failedFiles": 0,
            "failures": [],
            "ranAt": datetime.now().isoformat(),
            "targets": [],
        }

    monkeypatch.setattr("app.asset_cleanup.run_asset_cleanup", fake_run_asset_cleanup)

    result = maybe_run_scheduled_asset_cleanup(db, targets=targets, now_ts=90000)

    assert result is not None
    assert observed_marker["value"] == "90000.0"


def test_scheduled_asset_cleanup_records_failures_for_future_visibility(monkeypatch, tmp_path) -> None:
    from app.asset_cleanup import (
        ASSET_CLEANUP_LAST_RUN_KEY,
        build_cleanup_targets,
        maybe_run_scheduled_asset_cleanup,
    )

    db = make_db()
    generated_dir = tmp_path / "generated_assets"
    uploaded_dir = tmp_path / "uploaded_assets"
    generated_dir.mkdir()
    uploaded_dir.mkdir()
    targets = build_cleanup_targets(generated_dir, uploaded_dir)

    def fake_run_asset_cleanup(*_args, **_kwargs):
        raise OSError("disk not reachable")

    monkeypatch.setattr("app.asset_cleanup.run_asset_cleanup", fake_run_asset_cleanup)

    result = maybe_run_scheduled_asset_cleanup(db, targets=targets, now_ts=90000)

    assert result is None
    marker = db.get(SystemSetting, ASSET_CLEANUP_LAST_RUN_KEY)
    assert marker is not None
    payload = json.loads(marker.value)
    assert payload["status"] == "failed"
    assert "disk not reachable" in payload["message"]


def test_super_admin_can_update_database_admin_role() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="role-owner")
    target = make_user(db, "role-target@example.com", external_id="role-target")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    response = client.put(
        f"/api/admin/users/{target.id}/role",
        json={"role": "viewer", "note": "read only"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["adminRole"] == "viewer"
    assert response.json()["user"]["adminRoleSource"] == "database"
    logs = client.get("/api/admin/audit-logs")
    assert logs.status_code == 200
    assert logs.json()["logs"][0]["action"] == "update_admin_role"

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_database_role_user_auth_me_reports_admin_status() -> None:
    import app.main as main_module
    from app.database import get_db
    from app.main import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    seed_db = TestingSession()
    owner = make_user(seed_db, "cage_ben@sina.com", external_id="auth-role-owner")
    target = make_user(seed_db, "viewer-auth@example.com", external_id="auth-role-viewer")
    seed_db.add(AdminRoleAssignment(user_id=target.id, role="viewer", assigned_by=owner.id))
    seed_db.commit()
    seed_db.close()

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    login = client.post(
        "/api/auth/dev-login",
        json={
            "externalUserId": "auth-role-viewer",
            "email": "viewer-auth@example.com",
            "nickname": "Viewer Auth",
        },
    )
    me = client.get("/api/auth/me")

    assert login.status_code == 200
    assert login.json()["user"]["isAdmin"] is True
    assert me.status_code == 200
    assert me.json()["user"]["isAdmin"] is True

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_non_admin_cannot_adjust_credits() -> None:
    import app.main as main_module
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    db = make_db()
    normal = make_user(db, "normal-admin-denied@example.com", external_id="normal-admin-denied")
    target = make_user(db, "target-admin-denied@example.com", external_id="target-admin-denied")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: normal
    client = TestClient(app)

    response = client.post(
        f"/api/admin/users/{target.id}/credits/adjust",
        json={"amount": 1, "reason": "x"},
    )

    assert response.status_code == 403

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_register_returns_signup_bonus_credit_snapshot() -> None:
    import app.main as main_module
    from app.credit_service import update_credit_settings
    from app.database import get_db
    from app.main import app

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com", external_id="admin-signup-bonus")
    update_credit_settings(db, admin, signup_bonus_enabled=True, signup_bonus_amount=6)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    response = client.post(
        "/api/auth/register",
        json={
            "email": "bonus-user@example.com",
            "password": "abc12345",
            "nickname": "Bonus User",
        },
    )

    assert response.status_code == 200
    assert response.json()["user"]["credits"]["balance"] == 6
    assert response.json()["user"]["credits"]["totalRecharged"] == 6

    app.dependency_overrides.clear()
    main_module.rate_limiter.clear()


def test_admin_users_pagination_and_summary() -> None:
    from app.admin_service import admin_users_summary, count_admin_users, list_admin_users

    db = make_db()
    for i in range(5):
        user = make_user(db, f"page-user{i}@example.com", external_id=f"page-ext-{i}")
        db.add(UserCreditAccount(user_id=user.id, balance=10 * (i + 1)))
    db.commit()

    assert count_admin_users(db) == 5
    assert len(list_admin_users(db, page=1, page_size=2)) == 2
    assert len(list_admin_users(db, page=3, page_size=2)) == 1
    assert len(list_admin_users(db, limit=None)) == 5

    summary = admin_users_summary(db)
    assert summary["totalUsers"] == 5
    assert summary["totalBalance"] == 150


def test_admin_models_pagination_and_count() -> None:
    from app.admin_service import count_admin_models, list_admin_models

    db = make_db()
    owner = make_user(db, "model-owner@example.com")
    for i in range(3):
        make_model(db, owner, name=f"Paginated Model {i}")

    assert count_admin_models(db) == 3
    assert len(list_admin_models(db, page=1, page_size=2)) == 2
    assert len(list_admin_models(db, limit=None)) == 3


def test_admin_records_time_filter_and_pagination() -> None:
    from app.admin_service import list_admin_creation_records

    db = make_db()
    user = make_user(db, "records-user@example.com")
    conversation = Conversation(user_id=user.id, title="记录", capability="text")
    db.add(conversation)
    db.commit()
    for ts in (datetime(2026, 1, 1), datetime(2026, 6, 1)):
        db.add(
            ConversationMessage(
                conversation_id=conversation.id,
                user_id=user.id,
                role="assistant",
                capability="text",
                content="生成结果",
                status="success",
                created_at=ts,
            )
        )
    db.commit()

    assert len(list_admin_creation_records(db, capability="text")) == 2
    filtered = list_admin_creation_records(db, capability="text", start_at="2026-03-01T00:00:00")
    assert len(filtered) == 1
    first_page = list_admin_creation_records(db, capability="text", page=1, page_size=1)
    assert len(first_page) == 1


def test_admin_audit_logs_pagination() -> None:
    from app.admin_service import count_admin_audit_logs, list_admin_audit_logs

    db = make_db()
    for i in range(4):
        db.add(
            AdminOperationLog(
                admin_user_id="admin",
                action=f"action-{i}",
                target_type="user",
                target_id=f"user-{i}",
                status="success",
            )
        )
    db.commit()

    assert count_admin_audit_logs(db) == 4
    assert len(list_admin_audit_logs(db, page=1, page_size=2)) == 2
    assert len(list_admin_audit_logs(db, unlimited=True)) == 4


def test_prompt_template_version_restore() -> None:
    from app.admin_service import restore_prompt_template_version, upsert_prompt_template
    from app.schemas import PromptTemplateUpdate

    db = make_db()
    admin = make_user(db, "cage_ben@sina.com")
    first = upsert_prompt_template(
        db,
        admin,
        PromptTemplateUpdate(capability="text", templateType="prompt_optimize", name="v1", content="第一版 {{prompt}}", enabled=True),
    )
    upsert_prompt_template(
        db,
        admin,
        PromptTemplateUpdate(capability="text", templateType="prompt_optimize", name="v2", content="第二版 {{prompt}}", enabled=True),
    )

    restored = restore_prompt_template_version(db, admin, first.id, 1)
    assert restored.content == "第一版 {{prompt}}"
    assert restored.name == "v1"
