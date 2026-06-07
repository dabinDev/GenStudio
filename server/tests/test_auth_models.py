from __future__ import annotations

import os
import sys
import tempfile

from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

db_path = os.path.join(tempfile.gettempdir(), "genstudio-test.sqlite3")
if os.path.exists(db_path):
    os.remove(db_path)

os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["GENSTUDIO_SECRET_KEY"] = "test-secret"

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.config import Settings  # noqa: E402
import app.main as main_module  # noqa: E402
from app.main import app  # noqa: E402
from app.proxy_utils import build_test_body, filter_model_ids_for_capability  # noqa: E402


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    main_module.rate_limiter.clear()


def csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrfToken"]}


def test_dev_login_creates_session_and_me_returns_user() -> None:
    client = TestClient(app)

    login = client.post(
        "/api/auth/dev-login",
        json={"externalUserId": "official-1", "email": "u@example.com", "nickname": "User"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["externalUserId"] == "official-1"

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "u@example.com"


def test_register_creates_local_user_and_stores_argon_password_hash() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/auth/register",
        json={
            "email": "Local.User@Example.com",
            "password": "StrongPass123!",
            "nickname": "Local User",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == "local.user@example.com"
    assert payload["user"]["nickname"] == "Local User"
    assert "genstudio_session=" in response.headers["set-cookie"]

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "local.user@example.com"

    with SessionLocal() as db:
        row = db.execute(
            text("select password_hash from user_credentials where identifier = :identifier"),
            {"identifier": "local.user@example.com"},
        ).one()
    password_hash = row[0]
    assert "StrongPass123!" not in password_hash
    assert password_hash.startswith("$argon2")


def test_login_with_local_account_establishes_session() -> None:
    client = TestClient(app)
    registered = client.post(
        "/api/auth/register",
        json={"email": "login@example.com", "password": "StrongPass123!", "nickname": "Login User"},
    )
    assert registered.status_code == 200

    login_client = TestClient(app)
    login = login_client.post(
        "/api/auth/login",
        json={"identifier": "login@example.com", "password": "StrongPass123!"},
    )

    assert login.status_code == 200
    assert login.json()["user"]["email"] == "login@example.com"
    assert "genstudio_session=" in login.headers["set-cookie"]
    assert login_client.get("/api/auth/me").json()["user"]["nickname"] == "Login User"


def test_duplicate_local_email_registration_is_rejected() -> None:
    client = TestClient(app)
    first = client.post(
        "/api/auth/register",
        json={"email": "dupe@example.com", "password": "StrongPass123!", "nickname": "First"},
    )
    assert first.status_code == 200

    duplicate = client.post(
        "/api/auth/register",
        json={"email": "DUPE@example.com", "password": "StrongPass123!", "nickname": "Second"},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["message"]


def test_login_lockout_blocks_correct_password_after_repeated_failures() -> None:
    client = TestClient(app)
    registered = client.post(
        "/api/auth/register",
        json={"email": "locked@example.com", "password": "StrongPass123!", "nickname": "Locked User"},
    )
    assert registered.status_code == 200

    login_client = TestClient(app)
    for _ in range(4):
        failed = login_client.post(
            "/api/auth/login",
            json={"identifier": "locked@example.com", "password": "WrongPass123!"},
        )
        assert failed.status_code == 401

    lock_trigger = login_client.post(
        "/api/auth/login",
        json={"identifier": "locked@example.com", "password": "WrongPass123!"},
    )
    assert lock_trigger.status_code == 429

    locked = login_client.post(
        "/api/auth/login",
        json={"identifier": "locked@example.com", "password": "StrongPass123!"},
    )

    assert locked.status_code == 429


def test_authenticated_state_changing_routes_require_csrf_token() -> None:
    client = TestClient(app)
    registered = client.post(
        "/api/auth/register",
        json={"email": "csrf@example.com", "password": "StrongPass123!", "nickname": "CSRF User"},
    )
    assert registered.status_code == 200

    without_token = client.post(
        "/api/models",
        json={
            "name": "GPT Gateway",
            "vendor": "OpenAI",
            "capability": "text",
            "adapter": "text-chat",
            "baseUrl": "https://token.example.com",
            "apiKey": "sk-test",
            "primaryModelName": "gpt-4o",
        },
    )
    assert without_token.status_code == 403

    with_token = client.post(
        "/api/models",
        headers=csrf_headers(client),
        json={
            "name": "GPT Gateway",
            "vendor": "OpenAI",
            "capability": "text",
            "adapter": "text-chat",
            "baseUrl": "https://token.example.com",
            "apiKey": "sk-test",
            "primaryModelName": "gpt-4o",
        },
    )
    assert with_token.status_code == 200


def test_model_create_returns_primary_sub_model() -> None:
    client = TestClient(app)
    client.post("/api/auth/dev-login", json={"externalUserId": "official-1"})

    response = client.post(
        "/api/models",
        headers=csrf_headers(client),
        json={
            "name": "GPT Gateway",
            "vendor": "OpenAI",
            "capability": "text",
            "adapter": "text-chat",
            "baseUrl": "https://token.example.com",
            "apiKey": "sk-test",
            "primaryModelName": "gpt-4o",
        },
    )

    assert response.status_code == 200
    model = response.json()["model"]
    assert model["primaryModelName"] == "gpt-4o"
    assert model["subModels"][0]["isPrimary"] is True


def test_model_create_persists_all_fetched_sub_models() -> None:
    client = TestClient(app)
    client.post("/api/auth/dev-login", json={"externalUserId": "official-1"})

    response = client.post(
        "/api/models",
        headers=csrf_headers(client),
        json={
            "name": "GPT Gateway",
            "vendor": "OpenAI",
            "capability": "text",
            "adapter": "text-chat",
            "baseUrl": "https://token.example.com",
            "apiKey": "sk-test",
            "primaryModelName": "gpt-4.1",
            "availableModelNames": ["gpt-4o", "gpt-4.1"],
        },
    )

    assert response.status_code == 200
    model = response.json()["model"]
    assert model["primaryModelName"] == "gpt-4.1"
    assert {item["modelName"] for item in model["subModels"]} == {"gpt-4o", "gpt-4.1"}
    assert [item for item in model["subModels"] if item["isPrimary"]][0]["modelName"] == "gpt-4.1"


def test_model_update_can_change_primary_model_and_delete() -> None:
    client = TestClient(app)
    client.post("/api/auth/dev-login", json={"externalUserId": "official-1"})
    created = client.post(
        "/api/models",
        headers=csrf_headers(client),
        json={
            "name": "GPT Gateway",
            "vendor": "OpenAI",
            "capability": "text",
            "adapter": "text-chat",
            "baseUrl": "https://token.example.com",
            "apiKey": "sk-test",
            "primaryModelName": "gpt-4o",
        },
    ).json()["model"]

    updated = client.put(
        f"/api/models/{created['id']}",
        headers=csrf_headers(client),
        json={"primaryModelName": "gpt-4.1", "name": "GPT Gateway Updated"},
    )

    assert updated.status_code == 200
    model = updated.json()["model"]
    assert model["name"] == "GPT Gateway Updated"
    assert model["primaryModelName"] == "gpt-4.1"
    assert {item["modelName"] for item in model["subModels"]} == {"gpt-4o", "gpt-4.1"}

    deleted = client.delete(f"/api/models/{created['id']}", headers=csrf_headers(client))
    assert deleted.status_code == 200
    assert client.get("/api/models").json()["models"] == []


def test_public_models_are_visible_without_login_and_readonly_for_non_admin() -> None:
    admin = TestClient(app)
    admin.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-1", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    public_model = admin.post(
        "/api/models",
        headers=csrf_headers(admin),
        json={
            "name": "GPT 5.5 Public",
            "vendor": "OpenAI",
            "capability": "text",
            "adapter": "text-chat",
            "baseUrl": "https://token.example.com",
            "apiKey": "sk-test",
            "primaryModelName": "gpt-5.5",
            "description": "Public gateway from https://token.example.com",
            "isPublic": True,
        },
    )
    private_model = admin.post(
        "/api/models",
        headers=csrf_headers(admin),
        json={
            "name": "Private GPT",
            "vendor": "OpenAI",
            "capability": "text",
            "adapter": "text-chat",
            "baseUrl": "https://token.example.com",
            "apiKey": "sk-test",
            "primaryModelName": "gpt-4o",
        },
    )
    assert public_model.status_code == 200
    assert private_model.status_code == 200

    guest = TestClient(app)
    guest_models = guest.get("/api/models")

    assert guest_models.status_code == 200
    guest_payload = guest_models.json()["models"]
    assert [item["name"] for item in guest_payload] == ["GPT 5.5 Public"]
    assert guest_payload[0]["isPublic"] is True
    assert guest_payload[0]["canEdit"] is False
    assert guest_payload[0]["primaryModelName"] == "gpt-5.5"
    assert guest_payload[0]["baseUrl"] == ""
    assert "https://" not in guest_payload[0]["description"]
    assert guest_payload[0]["description"] == "平台公共模型，可直接用于创作。"

    normal = TestClient(app)
    normal.post(
        "/api/auth/dev-login",
        json={"externalUserId": "normal-1", "email": "normal@example.com", "nickname": "Normal"},
    )
    normal_models = normal.get("/api/models").json()["models"]
    public_row = next(item for item in normal_models if item["id"] == public_model.json()["model"]["id"])
    assert public_row["canEdit"] is False
    assert public_row["baseUrl"] == ""
    assert "https://" not in public_row["description"]

    admin_row = next(item for item in admin.get("/api/models").json()["models"] if item["id"] == public_model.json()["model"]["id"])
    assert admin_row["canEdit"] is True
    assert admin_row["baseUrl"] == "https://token.example.com"
    assert admin_row["description"] == "Public gateway from https://token.example.com"


def test_non_admin_cannot_edit_delete_or_switch_public_model() -> None:
    admin = TestClient(app)
    admin.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-1", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    created = admin.post(
        "/api/models",
        headers=csrf_headers(admin),
        json={
            "name": "GPT 5.5 Public",
            "vendor": "OpenAI",
            "capability": "text",
            "adapter": "text-chat",
            "baseUrl": "https://token.example.com",
            "apiKey": "sk-test",
            "primaryModelName": "gpt-5.5",
            "availableModelNames": ["gpt-5.5", "gpt-5.4"],
            "isPublic": True,
        },
    ).json()["model"]

    normal = TestClient(app)
    normal.post(
        "/api/auth/dev-login",
        json={"externalUserId": "normal-1", "email": "normal@example.com", "nickname": "Normal"},
    )
    headers = csrf_headers(normal)

    updated = normal.put(f"/api/models/{created['id']}", headers=headers, json={"name": "Stolen"})
    deleted = normal.delete(f"/api/models/{created['id']}", headers=headers)
    primary = normal.post(
        f"/api/models/{created['id']}/primary",
        headers=headers,
        json={"subModelId": created["subModels"][1]["id"]},
    )

    assert updated.status_code == 403
    assert deleted.status_code == 403
    assert primary.status_code == 403


def test_admin_can_publish_private_model_for_other_users_to_use(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        return (
            httpx.Response(200, json={"choices": [{"message": {"content": "public response"}}]}),
            {"choices": [{"message": {"content": "public response"}}]},
        )

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    admin = TestClient(app)
    admin.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-1", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    created = admin.post(
        "/api/models",
        headers=csrf_headers(admin),
        json={
            "name": "Admin GPT",
            "vendor": "OpenAI",
            "capability": "text",
            "adapter": "text-chat",
            "baseUrl": "https://token.example.com",
            "apiKey": "sk-test",
            "primaryModelName": "gpt-5.5",
        },
    ).json()["model"]

    published = admin.put(
        f"/api/models/{created['id']}",
        headers=csrf_headers(admin),
        json={"isPublic": True},
    )
    assert published.status_code == 200
    assert published.json()["model"]["isPublic"] is True
    assert published.json()["model"]["canEdit"] is True

    normal = TestClient(app)
    normal.post(
        "/api/auth/dev-login",
        json={"externalUserId": "normal-1", "email": "normal@example.com", "nickname": "Normal"},
    )
    public_model = next(item for item in normal.get("/api/models").json()["models"] if item["id"] == created["id"])
    assert public_model["baseUrl"] == ""
    assert public_model["canEdit"] is False

    response = normal.post(
        "/api/proxy/text",
        headers=csrf_headers(normal),
        json={
            "subModelId": public_model["primarySubModelId"],
            "requestBody": {"messages": [{"role": "user", "content": "hello"}]},
        },
    )
    assert response.status_code == 200
    assert response.json()["content"] == "public response"


def test_auth_me_marks_default_admin_email() -> None:
    admin = TestClient(app)
    admin.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-1", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    normal = TestClient(app)
    normal.post(
        "/api/auth/dev-login",
        json={"externalUserId": "normal-1", "email": "normal@example.com", "nickname": "Normal"},
    )

    assert admin.get("/api/auth/me").json()["user"]["isAdmin"] is True
    assert normal.get("/api/auth/me").json()["user"]["isAdmin"] is False


def test_auth_me_marks_configured_admin_identifier(monkeypatch) -> None:
    from app.auth import is_admin_user
    from app.config import Settings
    from app.db_models import User

    settings = Settings(admin_emails=[], admin_identifiers=["cylonai"])
    user = User(external_user_id="local-cylonai", email="", phone="", nickname="cylonai", status="active")

    assert is_admin_user(user, settings) is True


def test_sub_model_proxy_requires_login() -> None:
    client = TestClient(app)

    response = client.post("/api/proxy/text", json={"subModelId": "sub_missing", "requestBody": {}})

    assert response.status_code == 401


def test_proxy_test_surfaces_upstream_error_message(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(401, json={"error": {"message": "Invalid API key"}}), {"error": {"message": "Invalid API key"}}

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)

    response = client.post(
        "/api/proxy/test",
        json={
            "config": {"baseUrl": "https://token.example.com", "apiKey": "sk-test"},
            "capability": "text",
            "adapter": "text-chat",
            "model": "gpt-4o",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"]["message"] == "Invalid API key"


def test_proxy_test_omits_html_upstream_raw(monkeypatch) -> None:
    html = "<html><head><title>504 Gateway Time-out</title></head><body>nginx</body></html>"

    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(504, text=html), html

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)

    response = client.post(
        "/api/proxy/test",
        json={
            "config": {"baseUrl": "https://token.example.com", "apiKey": "sk-test"},
            "capability": "image",
            "adapter": "image-openai",
            "model": "gpt-image-2",
        },
    )

    assert response.status_code == 504
    detail = response.json()["detail"]
    assert detail["message"] == "上游服务超时，请稍后重试。"
    assert detail["request"]["url"] == "https://token.example.com/v1/images/generations"
    assert detail["durationMs"] >= 0
    assert "raw" not in detail


def test_proxy_test_normalizes_openai_bad_response_status_code(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        raw = {"error": {"message": "openai_error", "type": "bad_response_status_code", "code": "bad_response_status_code"}}
        return httpx.Response(502, json=raw), raw

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)

    response = client.post(
        "/api/proxy/test",
        json={
            "config": {"baseUrl": "https://token.example.com", "apiKey": "sk-test"},
            "capability": "image",
            "adapter": "image-openai",
            "model": "gpt-image-2",
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"]["message"] == "上游模型服务返回异常，请稍后重试或检查模型接口。"


def test_proxy_test_normalizes_non_json_upstream_wrapper_error(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        raw = {
            "error": {
                "message": "invalid character '<' looking for beginning of value",
                "type": "bad_response_body",
                "code": "bad_response_body",
            }
        }
        return httpx.Response(502, json=raw), raw

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)

    response = client.post(
        "/api/proxy/test",
        json={
            "config": {"baseUrl": "https://token.example.com", "apiKey": "sk-test"},
            "capability": "image",
            "adapter": "image-openai",
            "model": "gpt-image-2",
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"]["message"] == "上游接口返回了非 JSON 内容，请检查模型接口路径或稍后重试。"


def test_proxy_test_accepts_json_payload_returned_as_text(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        return (
            httpx.Response(200, text='{"id":"resp_test","choices":[{"message":{"content":"pong"}}]}'),
            '{"id":"resp_test","choices":[{"message":{"content":"pong"}}]}',
        )

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)

    response = client.post(
        "/api/proxy/test",
        json={
            "config": {"baseUrl": "https://token.example.com", "apiKey": "sk-test"},
            "capability": "text",
            "adapter": "text-chat",
            "model": "gpt-4o",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == 200
    assert payload["request"]["url"] == "https://token.example.com/v1/chat/completions"
    assert payload["durationMs"] >= 0
    assert payload["raw"]["id"] == "resp_test"


def test_image_proxy_test_uses_provider_safe_default_size() -> None:
    body = build_test_body("image", "gpt-image-2")

    assert body["size"] == "1024x1024"


def test_model_ids_are_filtered_by_requested_capability() -> None:
    ids = [
        "gpt-5.5",
        "gpt-image-2",
        "doubao-seedance-2-0-260128",
        "text-embedding-3-small",
    ]

    assert filter_model_ids_for_capability(ids, "text") == ["gpt-5.5"]
    assert filter_model_ids_for_capability(ids, "image") == ["gpt-image-2"]
    assert filter_model_ids_for_capability(ids, "video") == ["doubao-seedance-2-0-260128"]


def test_production_settings_reject_insecure_launch_defaults() -> None:
    settings = Settings(
        environment="production",
        secret_key="dev-genstudio-secret-change-me",
        cookie_secure=False,
        enable_dev_login=True,
        auto_create_tables=True,
        frontend_url="http://127.0.0.1:5173",
        official_auth_exchange_url="",
        official_auth_client_secret="",
        cors_origins=["http://127.0.0.1:5173", "https://studio.cylonai.cn"],
        object_storage_enabled=False,
        object_storage_public_base_url="",
        object_storage_endpoint_url="",
        object_storage_bucket="",
        object_storage_access_key_id="",
        object_storage_secret_access_key="",
    )

    with pytest.raises(ValueError) as exc_info:
        settings.validate_startup()

    message = str(exc_info.value)
    assert "GENSTUDIO_SECRET_KEY" in message
    assert "GENSTUDIO_COOKIE_SECURE" in message
    assert "GENSTUDIO_ENABLE_DEV_LOGIN" in message
    assert "GENSTUDIO_AUTO_CREATE_TABLES" in message
    assert "OFFICIAL_AUTH_EXCHANGE_URL" in message
    assert "GENSTUDIO_CORS_ORIGINS" in message
    assert "OBJECT_STORAGE_ENABLED" in message
    assert "OBJECT_STORAGE_PUBLIC_BASE_URL" in message
    assert "OBJECT_STORAGE_ENDPOINT_URL" in message
    assert "OBJECT_STORAGE_BUCKET" in message
    assert "OBJECT_STORAGE_ACCESS_KEY_ID" in message
    assert "OBJECT_STORAGE_SECRET_ACCESS_KEY" in message


def test_production_settings_accept_hardened_studio_domain_config() -> None:
    settings = Settings(
        environment="production",
        secret_key="prod-secret-" + "x" * 48,
        cookie_secure=True,
        enable_dev_login=False,
        auto_create_tables=False,
        frontend_url="https://studio.cylonai.cn",
        official_auth_exchange_url="https://www.cylonai.cn/api/oauth/exchange",
        official_auth_client_id="genstudio",
        official_auth_client_secret="official-secret",
        cors_origins=["https://studio.cylonai.cn"],
        object_storage_enabled=True,
        object_storage_public_base_url="https://oss.example.com/genstudio",
        object_storage_endpoint_url="https://oss.example.com",
        object_storage_region="auto",
        object_storage_bucket="genstudio",
        object_storage_access_key_id="access-key",
        object_storage_secret_access_key="secret-key",
    )

    settings.validate_startup()
    assert settings.is_production is True
    assert settings.cors_origins == ["https://studio.cylonai.cn"]


def test_public_auth_callback_exchanges_code_sets_cookie_and_redirects(monkeypatch) -> None:
    async def fake_exchange(code, settings):
        assert code == "official-code"
        return {
            "external_user_id": "official-2",
            "email": "callback@example.com",
            "phone": "",
            "nickname": "Callback User",
            "avatar_url": "",
        }

    monkeypatch.setattr(main_module, "exchange_official_code", fake_exchange)
    client = TestClient(app, follow_redirects=False)

    response = client.get("/auth/callback?code=official-code")

    assert response.status_code == 307
    assert response.headers["location"] == "http://127.0.0.1:5173/#/settings"
    assert "genstudio_session=" in response.headers["set-cookie"]


def test_public_auth_callback_accepts_safe_next_path(monkeypatch) -> None:
    async def fake_exchange(code, settings):
        assert code == "official-code"
        return {
            "external_user_id": "official-3",
            "email": "safe-next@example.com",
            "phone": "",
            "nickname": "Safe Next",
            "avatar_url": "",
        }

    monkeypatch.setattr(main_module, "exchange_official_code", fake_exchange)
    client = TestClient(app, follow_redirects=False)

    response = client.get("/auth/callback?code=official-code&next=%2F%23%2Fvideos")

    assert response.status_code == 307
    assert response.headers["location"] == "http://127.0.0.1:5173/#/videos"
    assert "genstudio_session=" in response.headers["set-cookie"]


def test_public_auth_callback_rejects_external_next_redirect(monkeypatch) -> None:
    async def fake_exchange(code, settings):
        return {
            "external_user_id": "official-4",
            "email": "unsafe-next@example.com",
            "phone": "",
            "nickname": "Unsafe Next",
            "avatar_url": "",
        }

    monkeypatch.setattr(main_module, "exchange_official_code", fake_exchange)
    client = TestClient(app, follow_redirects=False)

    response = client.get("/auth/callback?code=official-code&next=https%3A%2F%2Fevil.example%2F")

    assert response.status_code == 307
    assert response.headers["location"] == "http://127.0.0.1:5173/#/settings"
    assert "evil.example" not in response.headers["location"]


def test_public_auth_callback_failure_redirects_to_friendly_error_page(monkeypatch) -> None:
    async def fake_exchange(code, settings):
        raise main_module.HTTPException(status_code=401, detail={"message": "code 已失效"})

    monkeypatch.setattr(main_module, "exchange_official_code", fake_exchange)
    client = TestClient(app, follow_redirects=False)

    response = client.get("/auth/callback?code=expired-code")

    assert response.status_code == 307
    assert response.headers["location"].startswith("http://127.0.0.1:5173/#/auth-error")
    assert "genstudio_session=" not in response.headers.get("set-cookie", "")


def test_public_auth_callback_accepts_local_dev_code_when_official_exchange_is_unconfigured() -> None:
    client = TestClient(app, follow_redirects=False)

    response = client.get("/auth/callback?code=dev:alice")

    assert response.status_code == 307
    assert response.headers["location"] == "http://127.0.0.1:5173/#/settings"
    assert "genstudio_session=" in response.headers["set-cookie"]

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["externalUserId"] == "dev-alice"
    assert me.json()["user"]["nickname"] == "alice"


def test_dev_auth_code_is_rejected_when_dev_login_is_disabled() -> None:
    settings = Settings(enable_dev_login=False, official_auth_exchange_url="")

    with pytest.raises(main_module.HTTPException) as exc_info:
        import anyio

        anyio.run(main_module.exchange_official_code, "dev:alice", settings)

    assert exc_info.value.status_code == 404
