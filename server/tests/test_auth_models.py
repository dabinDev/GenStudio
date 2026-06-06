from __future__ import annotations

import os
import sys
import tempfile

from fastapi.testclient import TestClient
import httpx
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

db_path = os.path.join(tempfile.gettempdir(), "genstudio-test.sqlite3")
if os.path.exists(db_path):
    os.remove(db_path)

os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["GENSTUDIO_SECRET_KEY"] = "test-secret"

from app.database import Base, SessionLocal, engine  # noqa: E402
import app.main as main_module  # noqa: E402
from app.main import app  # noqa: E402
from app.proxy_utils import build_test_body  # noqa: E402


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


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
