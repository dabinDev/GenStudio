from __future__ import annotations

import os
import sys
import tempfile
import base64
import asyncio
import time
import json

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

db_path = os.path.join(tempfile.gettempdir(), "genstudio-conversation-test.sqlite3")
if os.path.exists(db_path):
    os.remove(db_path)

os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["GENSTUDIO_SECRET_KEY"] = "test-secret"

from app.database import Base, engine  # noqa: E402
import app.main as main_module  # noqa: E402
from app.main import app  # noqa: E402


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    main_module.rate_limiter.clear()


def login(client: TestClient, user_id: str) -> None:
    response = client.post(
        "/api/auth/dev-login",
        json={
            "externalUserId": user_id,
            "email": f"{user_id}@example.com",
            "nickname": user_id,
        },
    )
    assert response.status_code == 200


def csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrfToken"]}


def png_bytes(width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
        + b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_image_4k_size_for_ratio_maps_ratios_and_sizes() -> None:
    # Canonical aspect ratios map to their fixed 4K sizes.
    assert main_module.image_4k_size_for_ratio("16:9") == "3840x2160"
    assert main_module.image_4k_size_for_ratio("9:16") == "2160x3840"
    assert main_module.image_4k_size_for_ratio("1:1") == "4096x4096"
    # An already-4K explicit "WxH" size (what the frontend sends) is preserved
    # rather than collapsing to a 4096 square, keeping the requested aspect ratio.
    assert main_module.image_4k_size_for_ratio("3840x2160") == "3840x2160"
    assert main_module.image_4k_size_for_ratio("2160x3840") == "2160x3840"
    # A non-4K size still scales up while preserving its aspect ratio.
    assert main_module.image_4k_size_for_ratio("1024x512") == "4096x2048"
    # Garbage falls back to a safe square.
    assert main_module.image_4k_size_for_ratio("not-a-size") == "4096x4096"


def wait_for_completed_task(client: TestClient, endpoint: str, headers: dict[str, str], body: dict, *, timeout: float = 2.0) -> dict:
    deadline = time.time() + timeout
    last_payload: dict = {}
    while time.time() < deadline:
        response = client.post(endpoint, headers=headers, json=body)
        assert response.status_code == 200
        last_payload = response.json()
        if last_payload.get("status") == "completed":
            return last_payload
        time.sleep(0.05)
    raise AssertionError(f"task did not complete before timeout: {last_payload}")


def wait_for_task_status(
    client: TestClient,
    endpoint: str,
    headers: dict[str, str],
    body: dict,
    status: str,
    *,
    timeout: float = 2.0,
) -> dict:
    deadline = time.time() + timeout
    last_payload: dict = {}
    while time.time() < deadline:
        response = client.post(endpoint, headers=headers, json=body)
        assert response.status_code == 200
        last_payload = response.json()
        if last_payload.get("status") == status:
            return last_payload
        time.sleep(0.05)
    raise AssertionError(f"task did not reach {status} before timeout: {last_payload}")


def create_text_model(client: TestClient) -> str:
    response = client.post(
        "/api/models",
        headers=csrf_headers(client),
        json={
            "name": "GPT Text",
            "vendor": "Test",
            "capability": "text",
            "adapter": "text-chat",
            "baseUrl": "https://token.example.com",
            "apiKey": "sk-test",
            "primaryModelName": "gpt-4o",
        },
    )
    assert response.status_code == 200
    return response.json()["model"]["primarySubModelId"]


def create_model(client: TestClient, capability: str, adapter: str, model_name: str) -> str:
    response = client.post(
        "/api/models",
        headers=csrf_headers(client),
        json={
            "name": f"{capability} model",
            "vendor": "Test",
            "capability": capability,
            "adapter": adapter,
            "baseUrl": "https://token.example.com",
            "apiKey": "sk-test",
            "primaryModelName": model_name,
        },
    )
    assert response.status_code == 200
    return response.json()["model"]["primarySubModelId"]


def create_model_with_base_url(
    client: TestClient,
    capability: str,
    adapter: str,
    model_name: str,
    base_url: str,
) -> str:
    response = client.post(
        "/api/models",
        headers=csrf_headers(client),
        json={
            "name": f"{capability} model",
            "vendor": "Test",
            "capability": capability,
            "adapter": adapter,
            "baseUrl": base_url,
            "apiKey": "sk-test",
            "primaryModelName": model_name,
        },
    )
    assert response.status_code == 200
    return response.json()["model"]["primarySubModelId"]


def create_public_model(admin: TestClient, capability: str, adapter: str, model_name: str) -> dict:
    response = admin.post(
        "/api/models",
        headers=csrf_headers(admin),
        json={
            "name": f"Public {capability} model",
            "vendor": "Test",
            "capability": capability,
            "adapter": adapter,
            "baseUrl": "https://token.example.com",
            "apiKey": "sk-test",
            "primaryModelName": model_name,
            "isPublic": True,
        },
    )
    assert response.status_code == 200
    return response.json()["model"]


def test_conversations_are_isolated_per_user() -> None:
    alice = TestClient(app)
    bob = TestClient(app)
    login(alice, "alice")
    login(bob, "bob")

    created = alice.post(
        "/api/conversations",
        headers=csrf_headers(alice),
        json={"title": "Alice chat", "capability": "text"},
    )
    assert created.status_code == 200

    alice_list = alice.get("/api/conversations")
    bob_list = bob.get("/api/conversations")

    assert [item["title"] for item in alice_list.json()["conversations"]] == ["Alice chat"]
    assert bob_list.json()["conversations"] == []


def test_conversation_title_can_be_renamed_by_owner_only() -> None:
    alice = TestClient(app)
    bob = TestClient(app)
    login(alice, "alice")
    login(bob, "bob")

    created = alice.post(
        "/api/conversations",
        headers=csrf_headers(alice),
        json={"title": "Alice chat", "capability": "text"},
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation"]["id"]

    renamed = alice.post(
        f"/api/conversations/{conversation_id}/rename",
        headers=csrf_headers(alice),
        json={"title": "新标题"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["conversation"]["title"] == "新标题"

    detail = alice.get(f"/api/conversations/{conversation_id}")
    assert detail.json()["conversation"]["title"] == "新标题"

    blocked = bob.post(
        f"/api/conversations/{conversation_id}/rename",
        headers=csrf_headers(bob),
        json={"title": "Bob title"},
    )
    assert blocked.status_code == 404


def test_text_proxy_records_successful_conversation_message(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        return (
            httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "# 标题\n\n正文"}}],
                    "usage": {"total_tokens": 12},
                },
            ),
            {
                "choices": [{"message": {"content": "# 标题\n\n正文"}}],
                "usage": {"total_tokens": 12},
            },
        )

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_text_model(client)

    response = client.post(
        "/api/proxy/text",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "conversationId": "",
            "requestBody": {"messages": [{"role": "user", "content": "写一段 markdown"}]},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation"]["title"] == "写一段 markdown"
    assert payload["assistantMessage"]["status"] == "success"
    assert payload["assistantMessage"]["content"].startswith("# 标题")
    messages = client.get(f"/api/conversations/{payload['conversation']['id']}").json()["conversation"]["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]

    summary = client.get("/api/calls/summary")
    assert summary.status_code == 200
    assert summary.json()["summary"]["total"] == 1
    assert summary.json()["summary"]["success"] == 1
    assert summary.json()["summary"]["byCapability"]["text"]["success"] == 1


def test_text_proxy_returns_failed_conversation_for_gateway_timeout(monkeypatch) -> None:
    html = "<html><head><title>504 Gateway Time-out</title></head><body>nginx</body></html>"

    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(504, text=html), html

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)

    with TestClient(app) as client:
        login(client, "alice")
        sub_model_id = create_text_model(client)
        response = client.post(
            "/api/proxy/text",
            headers=csrf_headers(client),
            json={
                "subModelId": sub_model_id,
                "conversationId": "",
                "requestBody": {"messages": [{"role": "user", "content": "timeout text"}]},
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "failed"
        assert payload["content"] == ""
        assert payload["assistantMessage"]["status"] == "error"
        assert payload["assistantMessage"]["canRetry"] is True
        conversation = client.get(f"/api/conversations/{payload['conversation']['id']}").json()["conversation"]
        assert conversation["messages"][-1]["errorMessage"] == "生成失败，请稍后重试。"


def test_text_proxy_hands_off_long_request_and_query_updates_message(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        await asyncio.sleep(0.05)
        return httpx.Response(200, json={"choices": [{"message": {"content": "long text done"}}]}), {
            "choices": [{"message": {"content": "long text done"}}],
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    settings = main_module.get_settings()
    monkeypatch.setattr(settings, "long_request_handoff_seconds", 0.01, raising=False)

    with TestClient(app) as client:
        login(client, "alice")
        sub_model_id = create_text_model(client)
        headers = csrf_headers(client)

        response = client.post(
            "/api/proxy/text",
            headers=headers,
            json={
                "subModelId": sub_model_id,
                "conversationId": "",
                "requestBody": {"messages": [{"role": "user", "content": "slow text"}]},
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "processing"
        assert payload["taskId"].startswith("text-task-")
        assert payload["assistantMessage"]["content"] == payload["taskId"]
        assert payload["assistantMessage"]["status"] == "processing"

        completed = wait_for_completed_task(
            client,
            "/api/proxy/text/query",
            headers,
            {
                "subModelId": sub_model_id,
                "conversationId": payload["conversation"]["id"],
                "taskId": payload["taskId"],
            },
        )

        assert completed["content"] == "long text done"
        assert completed["assistantMessage"]["status"] == "success"
        assert completed["assistantMessage"]["content"] == "long text done"
        conversation = client.get(f"/api/conversations/{payload['conversation']['id']}").json()["conversation"]
        assert conversation["messages"][-1]["content"] == "long text done"


def test_text_long_request_marks_message_failed_when_background_parser_crashes(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        await asyncio.sleep(0.05)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ignored"}}]}), {
            "choices": [{"message": {"content": "ignored"}}],
        }

    def broken_pick_text_content(raw):
        raise RuntimeError("parser exploded")

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    monkeypatch.setattr(main_module, "pick_text_content", broken_pick_text_content)
    settings = main_module.get_settings()
    monkeypatch.setattr(settings, "long_request_handoff_seconds", 0.01, raising=False)

    with TestClient(app) as client:
        login(client, "alice")
        sub_model_id = create_text_model(client)
        headers = csrf_headers(client)

        response = client.post(
            "/api/proxy/text",
            headers=headers,
            json={
                "subModelId": sub_model_id,
                "conversationId": "",
                "requestBody": {"messages": [{"role": "user", "content": "slow text crash"}]},
            },
        )

        assert response.status_code == 200
        payload = response.json()
        failed = wait_for_task_status(
            client,
            "/api/proxy/text/query",
            headers,
            {
                "subModelId": sub_model_id,
                "conversationId": payload["conversation"]["id"],
                "taskId": payload["taskId"],
            },
            "failed",
        )

        assert failed["assistantMessage"]["status"] == "error"
        assert failed["assistantMessage"]["canRetry"] is True


def test_public_text_model_records_assistant_message_for_non_admin_user(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        return (
            httpx.Response(200, json={"choices": [{"message": {"content": "优化后的公开模型回复"}}]}),
            {"choices": [{"message": {"content": "优化后的公开模型回复"}}]},
        )

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    admin = TestClient(app)
    login(admin, "admin")
    admin.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-public", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    public_model = create_public_model(admin, "text", "text-chat", "gpt-5.5")

    normal = TestClient(app)
    login(normal, "normal-user")
    visible_public = next(item for item in normal.get("/api/models").json()["models"] if item["id"] == public_model["id"])

    response = normal.post(
        "/api/proxy/text",
        headers=csrf_headers(normal),
        json={
            "subModelId": visible_public["primarySubModelId"],
            "requestBody": {"messages": [{"role": "user", "content": "写一段公开模型测试"}]},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["assistantMessage"]["content"] == "优化后的公开模型回复"
    conversation = normal.get(f"/api/conversations/{payload['conversation']['id']}").json()["conversation"]
    assert [message["role"] for message in conversation["messages"]] == ["user", "assistant"]
    assert conversation["messages"][-1]["content"] == "优化后的公开模型回复"


def test_public_image_model_records_generated_asset_for_non_admin_user(monkeypatch) -> None:
    from app.database import SessionLocal
    from app.credit_service import admin_adjust_credits
    from app.db_models import User

    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/public-image.png"}]}), {
            "data": [{"url": "https://cdn.example.com/public-image.png"}]
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    admin = TestClient(app)
    login(admin, "admin")
    admin.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-public", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    public_model = create_public_model(admin, "image", "image-openai", "gpt-image-2")

    normal = TestClient(app)
    login(normal, "normal-user")
    with SessionLocal() as db:
        admin_user = db.query(User).filter(User.email == "cage_ben@sina.com").one()
        normal_user = db.query(User).filter(User.external_user_id == "normal-user").one()
        admin_adjust_credits(db, admin=admin_user, target_user=normal_user, amount=1, reason="test seed")
    visible_public = next(item for item in normal.get("/api/models").json()["models"] if item["id"] == public_model["id"])

    response = normal.post(
        "/api/proxy/image",
        headers=csrf_headers(normal),
        json={
            "subModelId": visible_public["primarySubModelId"],
            "requestBody": {"prompt": "生成公开模型图片"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    conversation = normal.get(f"/api/conversations/{payload['conversation']['id']}").json()["conversation"]
    assert conversation["messages"][-1]["assets"][0]["url"] == "https://cdn.example.com/public-image.png"


def test_public_image_model_charges_double_credits_for_4k_batch(monkeypatch) -> None:
    from app.database import SessionLocal
    from app.credit_service import admin_adjust_credits, set_capability_price
    from app.db_models import CreditTransaction, User

    calls: list[dict] = []

    async def fake_forward_json(method, url, api_key, body=None):
        calls.append(dict(body or {}))
        image_number = len(calls)
        return httpx.Response(200, json={"data": [{"url": f"https://cdn.example.com/4k-{image_number}.png"}]}), {
            "data": [{"url": f"https://cdn.example.com/4k-{image_number}.png"}]
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)

    async def fake_remote_dimensions(url):
        return (3840, 2160)

    monkeypatch.setattr(main_module, "remote_image_dimensions", fake_remote_dimensions)
    admin = TestClient(app)
    login(admin, "admin")
    admin.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-public", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    public_model = create_public_model(admin, "image", "image-openai", "gpt-image-2")

    normal = TestClient(app)
    login(normal, "normal-4k-user")
    with SessionLocal() as db:
        admin_user = db.query(User).filter(User.email == "cage_ben@sina.com").one()
        normal_user = db.query(User).filter(User.external_user_id == "normal-4k-user").one()
        set_capability_price(db, "image", 3, admin=admin_user)
        admin_adjust_credits(db, admin=admin_user, target_user=normal_user, amount=20, reason="test seed")
    visible_public = next(item for item in normal.get("/api/models").json()["models"] if item["id"] == public_model["id"])
    headers = csrf_headers(normal)

    response = normal.post(
        "/api/proxy/image",
        headers=headers,
        json={
            "subModelId": visible_public["primarySubModelId"],
            "enable4k": True,
            "requestBody": {"prompt": "4k batch", "quantity": 2, "ratio": "16:9"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    completed = wait_for_completed_task(
        normal,
        "/api/proxy/image/query",
        headers,
        {
            "subModelId": visible_public["primarySubModelId"],
            "conversationId": payload["conversation"]["id"],
            "taskId": payload["taskId"],
        },
    )
    assert completed["credits"]["account"]["balance"] == 8
    assert [call["size"] for call in calls] == ["3840x2160", "3840x2160"]
    with SessionLocal() as db:
        reserve = (
            db.query(CreditTransaction)
            .filter(CreditTransaction.type == "generation_reserve")
            .order_by(CreditTransaction.created_at.desc())
            .first()
        )
        assert reserve is not None
        assert reserve.amount == -12
        metadata = json.loads(reserve.metadata_json)
        assert metadata["is4k"] is True
        assert metadata["multiplier"] == 2
        assert metadata["targetSize"] == "3840x2160"
        assert metadata["effectiveUnitPrice"] == 6


def test_public_image_model_charges_regular_credits_without_4k(monkeypatch) -> None:
    from app.database import SessionLocal
    from app.credit_service import admin_adjust_credits, set_capability_price
    from app.db_models import CreditTransaction, User

    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/regular.png"}]}), {
            "data": [{"url": "https://cdn.example.com/regular.png"}]
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    admin = TestClient(app)
    login(admin, "admin")
    admin.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-public", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    public_model = create_public_model(admin, "image", "image-openai", "gpt-image-2")

    normal = TestClient(app)
    login(normal, "normal-regular-user")
    with SessionLocal() as db:
        admin_user = db.query(User).filter(User.email == "cage_ben@sina.com").one()
        normal_user = db.query(User).filter(User.external_user_id == "normal-regular-user").one()
        set_capability_price(db, "image", 3, admin=admin_user)
        admin_adjust_credits(db, admin=admin_user, target_user=normal_user, amount=20, reason="test seed")
    visible_public = next(item for item in normal.get("/api/models").json()["models"] if item["id"] == public_model["id"])

    response = normal.post(
        "/api/proxy/image",
        headers=csrf_headers(normal),
        json={
            "subModelId": visible_public["primarySubModelId"],
            "requestBody": {"prompt": "regular batch", "quantity": 2},
        },
    )

    assert response.status_code == 200
    with SessionLocal() as db:
        reserve = (
            db.query(CreditTransaction)
            .filter(CreditTransaction.type == "generation_reserve")
            .order_by(CreditTransaction.created_at.desc())
            .first()
        )
        assert reserve is not None
        assert reserve.amount == -6
        assert '"is4k":true' not in reserve.metadata_json


def test_manual_4k_size_is_charged_as_4k(monkeypatch) -> None:
    from app.database import SessionLocal
    from app.credit_service import admin_adjust_credits, set_capability_price
    from app.db_models import CreditTransaction, User

    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/manual-4k.png"}]}), {
            "data": [{"url": "https://cdn.example.com/manual-4k.png"}]
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)

    async def fake_remote_dimensions(url):
        return (4096, 4096)

    monkeypatch.setattr(main_module, "remote_image_dimensions", fake_remote_dimensions)
    admin = TestClient(app)
    login(admin, "admin")
    admin.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-public", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    public_model = create_public_model(admin, "image", "image-openai", "gpt-image-2")

    normal = TestClient(app)
    login(normal, "manual-4k-user")
    with SessionLocal() as db:
        admin_user = db.query(User).filter(User.email == "cage_ben@sina.com").one()
        normal_user = db.query(User).filter(User.external_user_id == "manual-4k-user").one()
        set_capability_price(db, "image", 3, admin=admin_user)
        admin_adjust_credits(db, admin=admin_user, target_user=normal_user, amount=20, reason="test seed")
    visible_public = next(item for item in normal.get("/api/models").json()["models"] if item["id"] == public_model["id"])

    response = normal.post(
        "/api/proxy/image",
        headers=csrf_headers(normal),
        json={
            "subModelId": visible_public["primarySubModelId"],
            "requestBody": {"prompt": "manual 4k", "size": "4096x4096"},
        },
    )

    assert response.status_code == 200
    with SessionLocal() as db:
        reserve = (
            db.query(CreditTransaction)
            .filter(CreditTransaction.type == "generation_reserve")
            .order_by(CreditTransaction.created_at.desc())
            .first()
        )
        assert reserve is not None
        assert reserve.amount == -6
        assert json.loads(reserve.metadata_json)["is4k"] is True


def test_manual_wide_4k_size_is_charged_as_4k(monkeypatch) -> None:
    from app.database import SessionLocal
    from app.credit_service import admin_adjust_credits, set_capability_price
    from app.db_models import CreditTransaction, User

    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/manual-wide-4k.png"}]}), {
            "data": [{"url": "https://cdn.example.com/manual-wide-4k.png"}]
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)

    async def fake_remote_dimensions(url):
        return (4096, 2048)

    monkeypatch.setattr(main_module, "remote_image_dimensions", fake_remote_dimensions)
    admin = TestClient(app)
    login(admin, "admin")
    admin.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-public", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    public_model = create_public_model(admin, "image", "image-openai", "gpt-image-2")

    normal = TestClient(app)
    login(normal, "manual-wide-4k-user")
    with SessionLocal() as db:
        admin_user = db.query(User).filter(User.email == "cage_ben@sina.com").one()
        normal_user = db.query(User).filter(User.external_user_id == "manual-wide-4k-user").one()
        set_capability_price(db, "image", 3, admin=admin_user)
        admin_adjust_credits(db, admin=admin_user, target_user=normal_user, amount=20, reason="test seed")
    visible_public = next(item for item in normal.get("/api/models").json()["models"] if item["id"] == public_model["id"])

    response = normal.post(
        "/api/proxy/image",
        headers=csrf_headers(normal),
        json={
            "subModelId": visible_public["primarySubModelId"],
            "requestBody": {"prompt": "manual wide 4k", "size": "4096x2048"},
        },
    )

    assert response.status_code == 200
    with SessionLocal() as db:
        reserve = (
            db.query(CreditTransaction)
            .filter(CreditTransaction.type == "generation_reserve")
            .order_by(CreditTransaction.created_at.desc())
            .first()
        )
        assert reserve is not None
        assert reserve.amount == -6
        metadata = json.loads(reserve.metadata_json)
        assert metadata["is4k"] is True
        assert metadata["targetSize"] == "4096x2048"


def test_4k_local_output_below_target_fails_and_refunds(monkeypatch) -> None:
    from app.database import SessionLocal
    from app.credit_service import admin_adjust_credits, set_capability_price
    from app.db_models import CreditTransaction, User

    small_image = base64.b64encode(png_bytes(1983, 793)).decode("ascii")

    async def fake_forward_json(method, url, api_key, body=None):
        assert body["size"] == "3840x2160"
        return httpx.Response(200, json={"data": [{"b64_json": small_image}]}), {
            "data": [{"b64_json": small_image}]
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    admin = TestClient(app)
    login(admin, "admin")
    admin.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-public", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    public_model = create_public_model(admin, "image", "image-openai", "gpt-image-2")

    normal = TestClient(app)
    login(normal, "small-4k-user")
    with SessionLocal() as db:
        admin_user = db.query(User).filter(User.email == "cage_ben@sina.com").one()
        normal_user = db.query(User).filter(User.external_user_id == "small-4k-user").one()
        set_capability_price(db, "image", 3, admin=admin_user)
        admin_adjust_credits(db, admin=admin_user, target_user=normal_user, amount=20, reason="test seed")
    visible_public = next(item for item in normal.get("/api/models").json()["models"] if item["id"] == public_model["id"])

    response = normal.post(
        "/api/proxy/image",
        headers=csrf_headers(normal),
        json={
            "subModelId": visible_public["primarySubModelId"],
            "enable4k": True,
            "requestBody": {"prompt": "4k too small", "ratio": "16:9"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    # Strict: a below-4K local output fails, is not shown, and credits are refunded.
    assert payload["status"] == "failed"
    assert payload["images"] == []
    assert "4K 生成未返回 4K 图片" in payload["assistantMessage"]["errorMessage"]
    assert payload["credits"]["account"]["balance"] == 20  # refunded
    with SessionLocal() as db:
        reserve = (
            db.query(CreditTransaction)
            .filter(CreditTransaction.type == "generation_reserve")
            .order_by(CreditTransaction.created_at.desc())
            .first()
        )
        assert reserve is not None
        assert reserve.amount == -6
        assert reserve.status == "refunded"


def test_4k_remote_url_below_target_fails_and_refunds(monkeypatch) -> None:
    """Strict: the upstream returns a remote URL pointing at a non-4K image.
    The probe measures it via HTTP, the generation fails, the image is not shown,
    and credits are refunded — a non-4K output is never passed off as success."""
    from app.database import SessionLocal
    from app.credit_service import admin_adjust_credits, set_capability_price
    from app.db_models import CreditTransaction, User

    async def fake_forward_json(method, url, api_key, body=None):
        assert body["size"] == "3840x2160"
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/not-really-4k.png"}]}), {
            "data": [{"url": "https://cdn.example.com/not-really-4k.png"}]
        }

    async def fake_remote_dimensions(url):
        return (1983, 793)

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    monkeypatch.setattr(main_module, "remote_image_dimensions", fake_remote_dimensions)
    admin = TestClient(app)
    login(admin, "admin")
    admin.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-public", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    public_model = create_public_model(admin, "image", "image-openai", "gpt-image-2")

    normal = TestClient(app)
    login(normal, "remote-small-4k-user")
    with SessionLocal() as db:
        admin_user = db.query(User).filter(User.email == "cage_ben@sina.com").one()
        normal_user = db.query(User).filter(User.external_user_id == "remote-small-4k-user").one()
        set_capability_price(db, "image", 3, admin=admin_user)
        admin_adjust_credits(db, admin=admin_user, target_user=normal_user, amount=20, reason="test seed")
    visible_public = next(item for item in normal.get("/api/models").json()["models"] if item["id"] == public_model["id"])

    response = normal.post(
        "/api/proxy/image",
        headers=csrf_headers(normal),
        json={
            "subModelId": visible_public["primarySubModelId"],
            "enable4k": True,
            "requestBody": {"prompt": "remote 4k too small", "ratio": "16:9"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["images"] == []
    assert "4K 生成未返回 4K 图片" in payload["assistantMessage"]["errorMessage"]
    assert payload["credits"]["account"]["balance"] == 20  # refunded
    with SessionLocal() as db:
        reserve = (
            db.query(CreditTransaction)
            .filter(CreditTransaction.type == "generation_reserve")
            .order_by(CreditTransaction.created_at.desc())
            .first()
        )
        assert reserve is not None
        assert reserve.amount == -6
        assert reserve.status == "refunded"


def test_4k_remote_url_unreachable_passes_open(monkeypatch) -> None:
    """When the probe cannot measure a remote image (network failure), the 4K
    output is not rejected — we only fail when we positively measure a too-small
    image, so a transient infra blip never nukes a paid generation."""
    from app.database import SessionLocal
    from app.credit_service import admin_adjust_credits, set_capability_price
    from app.db_models import User

    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/unreachable-4k.png"}]}), {
            "data": [{"url": "https://cdn.example.com/unreachable-4k.png"}]
        }

    async def fake_remote_dimensions(url):
        return None

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    monkeypatch.setattr(main_module, "remote_image_dimensions", fake_remote_dimensions)
    admin = TestClient(app)
    login(admin, "admin")
    admin.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-public", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    public_model = create_public_model(admin, "image", "image-openai", "gpt-image-2")

    normal = TestClient(app)
    login(normal, "remote-blip-4k-user")
    with SessionLocal() as db:
        admin_user = db.query(User).filter(User.email == "cage_ben@sina.com").one()
        normal_user = db.query(User).filter(User.external_user_id == "remote-blip-4k-user").one()
        set_capability_price(db, "image", 3, admin=admin_user)
        admin_adjust_credits(db, admin=admin_user, target_user=normal_user, amount=20, reason="test seed")
    visible_public = next(item for item in normal.get("/api/models").json()["models"] if item["id"] == public_model["id"])

    response = normal.post(
        "/api/proxy/image",
        headers=csrf_headers(normal),
        json={
            "subModelId": visible_public["primarySubModelId"],
            "enable4k": True,
            "requestBody": {"prompt": "remote 4k unreachable", "ratio": "16:9"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("status") != "failed"
    assert len(payload["images"]) == 1
    assert payload["credits"]["account"]["balance"] == 14


def test_remote_image_url_is_probeable_blocks_internal_targets() -> None:
    assert main_module.remote_image_url_is_probeable("https://cdn.example.com/a.png") is True
    assert main_module.remote_image_url_is_probeable("http://127.0.0.1/a.png") is False
    assert main_module.remote_image_url_is_probeable("http://localhost:8000/a.png") is False
    assert main_module.remote_image_url_is_probeable("http://169.254.169.254/latest/meta-data") is False
    assert main_module.remote_image_url_is_probeable("http://10.0.0.5/a.png") is False
    assert main_module.remote_image_url_is_probeable("http://192.168.1.10/a.png") is False
    assert main_module.remote_image_url_is_probeable("ftp://cdn.example.com/a.png") is False
    assert main_module.remote_image_url_is_probeable("/api/assets/generated/x.png") is False


def test_image_dimensions_from_bytes_sniffs_formats() -> None:
    assert main_module.image_dimensions_from_bytes(png_bytes(3840, 2160)) == (3840, 2160)
    # Minimal lossy WEBP (VP8) header advertising 3840x2160.
    width, height = 3840, 2160
    vp8 = (
        b"RIFF" + (0).to_bytes(4, "little") + b"WEBP" + b"VP8 "
        + (0).to_bytes(4, "little") + b"\x00\x00\x00" + b"\x9d\x01\x2a"
        + (width & 0x3FFF).to_bytes(2, "little") + (height & 0x3FFF).to_bytes(2, "little")
    )
    assert main_module.image_dimensions_from_bytes(vp8) == (3840, 2160)
    assert main_module.image_dimensions_from_bytes(b"not an image") is None


def test_enable_4k_rejects_non_openai_image_adapter() -> None:
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "video-unified-generic", "not-openai-image")

    response = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "enable4k": True,
            "requestBody": {"prompt": "unsupported 4k"},
        },
    )

    assert response.status_code == 400
    assert "4K" in response.json()["detail"]["message"]


def test_4k_credit_check_uses_doubled_total(monkeypatch) -> None:
    from app.database import SessionLocal
    from app.credit_service import admin_adjust_credits, set_capability_price
    from app.db_models import User

    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/too-expensive.png"}]}), {
            "data": [{"url": "https://cdn.example.com/too-expensive.png"}]
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    admin = TestClient(app)
    login(admin, "admin")
    admin.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-public", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    public_model = create_public_model(admin, "image", "image-openai", "gpt-image-2")

    normal = TestClient(app)
    login(normal, "short-balance-4k-user")
    with SessionLocal() as db:
        admin_user = db.query(User).filter(User.email == "cage_ben@sina.com").one()
        normal_user = db.query(User).filter(User.external_user_id == "short-balance-4k-user").one()
        set_capability_price(db, "image", 3, admin=admin_user)
        admin_adjust_credits(db, admin=admin_user, target_user=normal_user, amount=5, reason="test seed")
    visible_public = next(item for item in normal.get("/api/models").json()["models"] if item["id"] == public_model["id"])

    response = normal.post(
        "/api/proxy/image",
        headers=csrf_headers(normal),
        json={
            "subModelId": visible_public["primarySubModelId"],
            "enable4k": True,
            "requestBody": {"prompt": "not enough credits"},
        },
    )

    assert response.status_code == 402


def test_prompt_optimize_uses_public_gpt_model_without_creating_conversation(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_forward_json(method, url, api_key, body=None):
        captured["method"] = method
        captured["url"] = url
        captured["api_key"] = api_key
        captured["body"] = body
        return (
            httpx.Response(200, json={"choices": [{"message": {"content": "一辆小米 SU7 变形成蓝色未来机甲，保留车身线条。"}}]}),
            {"choices": [{"message": {"content": "一辆小米 SU7 变形成蓝色未来机甲，保留车身线条。"}}]},
        )

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    admin = TestClient(app)
    login(admin, "admin")
    admin.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-public", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    create_public_model(admin, "text", "text-chat", "gpt-5.5")

    guest = TestClient(app)
    response = guest.post(
        "/api/proxy/prompt/optimize",
        json={
            "capability": "image",
            "prompt": "生成小米 SU7 变形金刚",
            "parameters": {"ratio": "16:9", "resolution": "2k"},
            "referenceCount": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["prompt"].startswith("一辆小米 SU7")
    assert captured["method"] == "POST"
    assert captured["url"] == "https://token.example.com/v1/chat/completions"
    assert (captured["body"] or {})["model"] == "gpt-5.5"
    assert guest.get("/api/conversations").status_code == 401


def test_text_proxy_extracts_content_from_part_array(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        return (
            httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": [
                                    {"type": "text", "text": "第一段"},
                                    {"type": "text", "text": "第二段"},
                                ]
                            }
                        }
                    ]
                },
            ),
            {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": "第一段"},
                                {"type": "text", "text": "第二段"},
                            ]
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_text_model(client)

    response = client.post(
        "/api/proxy/text",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "requestBody": {"messages": [{"role": "user", "content": "分段输出"}]},
        },
    )

    assert response.status_code == 200
    assert response.json()["content"] == "第一段\n第二段"


def test_text_proxy_extracts_content_from_responses_payload(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        return (
            httpx.Response(
                200,
                json={
                    "output": [
                        {
                            "content": [
                                {"type": "output_text", "text": "Responses 正文"},
                            ]
                        }
                    ]
                },
            ),
            {
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": "Responses 正文"},
                        ]
                    }
                ]
            },
        )

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_text_model(client)

    response = client.post(
        "/api/proxy/text",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "requestBody": {"messages": [{"role": "user", "content": "responses"}]},
        },
    )

    assert response.status_code == 200
    assert response.json()["content"] == "Responses 正文"


def test_text_proxy_records_retryable_failed_message(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(401, json={"error": {"message": "Invalid API key"}}), {
            "error": {"message": "Invalid API key"}
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_text_model(client)

    response = client.post(
        "/api/proxy/text",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "requestBody": {"messages": [{"role": "user", "content": "会失败的请求"}]},
        },
    )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["message"] == "生成失败，请稍后重试。"
    assert detail["assistantMessage"]["status"] == "error"
    assert detail["assistantMessage"]["canRetry"] is True
    messages = client.get(f"/api/conversations/{detail['conversation']['id']}").json()["conversation"]["messages"]
    assert messages[-1]["errorMessage"] == "生成失败，请稍后重试。"


def test_image_proxy_records_generated_assets(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/image.png"}]}), {
            "data": [{"url": "https://cdn.example.com/image.png"}]
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")

    response = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "requestBody": {"prompt": "生成一张绿色茶饮海报"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["assistantMessage"]["assets"][0]["url"] == "https://cdn.example.com/image.png"
    conversation = client.get(f"/api/conversations/{payload['conversation']['id']}").json()["conversation"]
    assert conversation["messages"][-1]["assets"][0]["assetType"] == "image"


def test_image_proxy_batches_requested_quantity_into_single_image_calls(monkeypatch) -> None:
    calls: list[dict] = []

    async def fake_forward_json(method, url, api_key, body=None):
        assert method == "POST"
        calls.append(dict(body or {}))
        await asyncio.sleep(0)
        image_number = len(calls)
        return httpx.Response(200, json={"data": [{"url": f"https://cdn.example.com/batch-{image_number}.png"}]}), {
            "data": [{"url": f"https://cdn.example.com/batch-{image_number}.png"}]
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")
    headers = csrf_headers(client)

    response = client.post(
        "/api/proxy/image",
        headers=headers,
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "batch image", "quantity": 3}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processing"
    assert payload["taskId"].startswith("local-image-task-")
    assert payload["assistantMessage"]["status"] == "processing"

    completed = wait_for_completed_task(
        client,
        "/api/proxy/image/query",
        headers,
        {
            "subModelId": sub_model_id,
            "conversationId": payload["conversation"]["id"],
            "taskId": payload["taskId"],
        },
    )

    assert len(calls) == 3
    assert [call["quantity"] for call in calls] == [1, 1, 1]
    assert [image["src"] for image in completed["images"]] == [
        "https://cdn.example.com/batch-1.png",
        "https://cdn.example.com/batch-2.png",
        "https://cdn.example.com/batch-3.png",
    ]
    assert completed["raw"]["batch"]["requestedCount"] == 3
    assert completed["raw"]["batch"]["successCount"] == 3
    assert completed["assistantMessage"]["status"] == "success"
    assert len(completed["assistantMessage"]["assets"]) == 3
    conversation = client.get(f"/api/conversations/{payload['conversation']['id']}").json()["conversation"]
    assert len(conversation["messages"][-1]["assets"]) == 3


def test_image_proxy_batch_keeps_successful_images_when_one_call_fails(monkeypatch) -> None:
    calls: list[dict] = []

    async def fake_forward_json(method, url, api_key, body=None):
        assert method == "POST"
        calls.append(dict(body or {}))
        await asyncio.sleep(0)
        if len(calls) == 2:
            return httpx.Response(502, json={"error": {"message": "temporary upstream failure"}}), {
                "error": {"message": "temporary upstream failure"}
            }
        return httpx.Response(200, json={"data": [{"url": f"https://cdn.example.com/partial-{len(calls)}.png"}]}), {
            "data": [{"url": f"https://cdn.example.com/partial-{len(calls)}.png"}]
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")
    headers = csrf_headers(client)

    response = client.post(
        "/api/proxy/image",
        headers=headers,
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "partial batch image", "n": 3}},
    )

    assert response.status_code == 200
    payload = response.json()
    completed = wait_for_completed_task(
        client,
        "/api/proxy/image/query",
        headers,
        {
            "subModelId": sub_model_id,
            "conversationId": payload["conversation"]["id"],
            "taskId": payload["taskId"],
        },
    )

    assert len(calls) == 3
    assert [call["n"] for call in calls] == [1, 1, 1]
    assert [image["src"] for image in completed["images"]] == [
        "https://cdn.example.com/partial-1.png",
        "https://cdn.example.com/partial-3.png",
    ]
    assert completed["status"] == "completed"
    assert completed["raw"]["batch"]["failedCount"] == 1
    assert completed["assistantMessage"]["status"] == "success"
    assert len(completed["assistantMessage"]["assets"]) == 2


def test_image_proxy_keeps_separate_assistant_messages_for_repeated_batches(monkeypatch) -> None:
    calls: list[dict] = []

    async def fake_forward_json(method, url, api_key, body=None):
        assert method == "POST"
        calls.append(dict(body or {}))
        await asyncio.sleep(0)
        image_number = len(calls)
        return httpx.Response(200, json={"data": [{"url": f"https://cdn.example.com/repeated-{image_number}.png"}]}), {
            "data": [{"url": f"https://cdn.example.com/repeated-{image_number}.png"}]
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")
    headers = csrf_headers(client)

    first = client.post(
        "/api/proxy/image",
        headers=headers,
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "first image batch", "quantity": 2}},
    )
    assert first.status_code == 200
    first_payload = first.json()
    first_completed = wait_for_completed_task(
        client,
        "/api/proxy/image/query",
        headers,
        {
            "subModelId": sub_model_id,
            "conversationId": first_payload["conversation"]["id"],
            "taskId": first_payload["taskId"],
        },
    )

    second = client.post(
        "/api/proxy/image",
        headers=headers,
        json={
            "subModelId": sub_model_id,
            "conversationId": first_payload["conversation"]["id"],
            "requestBody": {"prompt": "second image batch", "quantity": 2},
        },
    )
    assert second.status_code == 200
    second_payload = second.json()
    second_completed = wait_for_completed_task(
        client,
        "/api/proxy/image/query",
        headers,
        {
            "subModelId": sub_model_id,
            "conversationId": first_payload["conversation"]["id"],
            "taskId": second_payload["taskId"],
        },
    )

    conversation = client.get(f"/api/conversations/{first_payload['conversation']['id']}").json()["conversation"]
    assistant_messages = [message for message in conversation["messages"] if message["role"] == "assistant"]

    assert first_completed["assistantMessage"]["id"] != second_completed["assistantMessage"]["id"]
    assert [message["content"] for message in conversation["messages"] if message["role"] == "user"] == [
        "first image batch",
        "second image batch",
    ]
    assert len(assistant_messages) == 2
    assert [asset["url"] for asset in assistant_messages[0]["assets"]] == [
        "https://cdn.example.com/repeated-1.png",
        "https://cdn.example.com/repeated-2.png",
    ]
    assert [asset["url"] for asset in assistant_messages[1]["assets"]] == [
        "https://cdn.example.com/repeated-3.png",
        "https://cdn.example.com/repeated-4.png",
    ]


def test_image_proxy_records_reference_assets_on_user_message(monkeypatch) -> None:
    upload_name = "conversation-reference.jpg"
    (main_module.LOCAL_UPLOAD_DIR / upload_name).write_bytes(b"fake-reference-image")
    reference_url = f"/api/assets/uploads/{upload_name}"

    async def fake_forward_multipart(url, api_key, *, data=None, files=None):
        assert url == "https://token.example.com/v1/images/edits"
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/edited.png"}]}), {
            "data": [{"url": "https://cdn.example.com/edited.png"}]
        }

    monkeypatch.setattr(main_module, "forward_multipart", fake_forward_multipart)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")

    response = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "requestBody": {"prompt": "参考图编辑", "image": [reference_url]},
        },
    )

    assert response.status_code == 200
    conversation = response.json()["conversation"]
    user_message = conversation["messages"][0]
    assert user_message["role"] == "user"
    assert user_message["assets"][0]["url"].startswith("/api/assets/")
    assert user_message["assets"][0]["url"].endswith("/content")
    assert user_message["assets"][0]["metadata"]["role"] == "reference"
    assert user_message["assets"][0]["metadata"]["source"] == "input"


def test_reference_asset_metadata_is_persisted_but_not_forwarded_upstream(monkeypatch) -> None:
    forwarded_bodies = []
    monkeypatch.setattr(main_module.get_settings(), "object_storage_public_base_url", "https://cdn.example.com")

    async def fake_forward_json(method, url, api_key, body=None):
        forwarded_bodies.append(body)
        return httpx.Response(200, json={"data": [{"url": "https://provider.example.com/result.png"}]}), {
            "data": [{"url": "https://provider.example.com/result.png"}]
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")
    reference_url = "https://cdn.example.com/references/reference.png"

    response = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "referenceAssets": [
                {
                    "url": reference_url,
                    "thumbnailUrl": "https://cdn.example.com/references/reference.webp",
                    "objectKey": "references/reference.png",
                    "thumbnailObjectKey": "references/reference.webp",
                    "index": 1,
                    "role": "reference",
                    "label": "参考图",
                }
            ],
            "requestBody": {"prompt": "use reference", "images": [reference_url]},
        },
    )

    assert response.status_code == 200
    assert all("referenceAssets" not in (body or {}) for body in forwarded_bodies)
    user_asset = response.json()["conversation"]["messages"][0]["assets"][0]
    assert user_asset["thumbnailUrl"] == "https://cdn.example.com/references/reference.webp"
    assert user_asset["metadata"] == {
        "role": "reference",
        "label": "参考图",
        "source": "input",
        "index": 1,
        "objectKey": "references/reference.png",
        "thumbnailObjectKey": "references/reference.webp",
        "storageStatus": "r2_synced",
    }


def test_image_proxy_returns_policy_specific_user_message(monkeypatch) -> None:
    raw = {"error": {"message": "Your request was rejected because it violated our relevant policies."}}

    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(400, json=raw), raw

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")

    response = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "会被审核拦截的图片"}},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["message"] == "内容未通过安全审核，请调整提示词或参考图后重试。"
    assert detail["assistantMessage"]["errorMessage"] == "内容未通过安全审核，请调整提示词或参考图后重试。"
    assert "raw" not in detail


def test_image_proxy_returns_parameter_specific_user_message(monkeypatch) -> None:
    raw = {"error": {"message": "size 480p is not supported", "code": "invalid_request"}}

    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(400, json=raw), raw

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")

    response = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "参数错误", "size": "480p"}},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "当前模型不支持所选参数，请调整尺寸、比例、分辨率或时长后再试。"


def test_image_proxy_maps_unsupported_image_model_message(monkeypatch) -> None:
    raw = {"error": {"message": "not supported model for image generation, only imagen models are supported"}}

    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(500, json=raw), raw

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gemini-3.1-flash-image-preview")

    response = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "模型不支持图片生成"}},
    )

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["message"] == "当前模型不支持图片生成，请更换模型或检查模型配置。"
    assert detail["assistantMessage"]["errorMessage"] == "当前模型不支持图片生成，请更换模型或检查模型配置。"


def test_image_proxy_maps_upstream_login_message_to_key_error(monkeypatch) -> None:
    raw = {"message": "请先登录。"}

    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(404, json=raw), raw

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")

    response = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "上游要求登录"}},
    )

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["message"] == "模型密钥不可用，请检查配置后再试。"
    assert detail["assistantMessage"]["errorMessage"] == "模型密钥不可用，请检查配置后再试。"


def test_image_proxy_returns_model_unavailable_for_logged_in_inaccessible_sub_model() -> None:
    owner = TestClient(app)
    login(owner, "alice")
    sub_model_id = create_model(owner, "image", "image-openai", "gpt-image-2")

    other = TestClient(app)
    login(other, "bob")
    response = other.post(
        "/api/proxy/image",
        headers=csrf_headers(other),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "测试不可访问模型"}},
    )

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["message"] == "模型不存在或未开通，请检查模型配置。"
    assert "raw" not in detail


def test_image_proxy_records_async_task_as_processing_message(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        assert method == "POST"
        return httpx.Response(200, json={"code": "success", "data": {"task_id": "image-task-1", "status": "processing"}}), {
            "code": "success",
            "data": {"task_id": "image-task-1", "status": "processing"},
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")

    response = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "async image"}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["taskId"] == "image-task-1"
    assert payload["status"] == "processing"
    assert payload["images"] == []
    assert payload["assistantMessage"]["content"] == "image-task-1"
    assert payload["assistantMessage"]["status"] == "processing"
    conversation = client.get(f"/api/conversations/{payload['conversation']['id']}").json()["conversation"]
    assert conversation["messages"][-1]["content"] == "image-task-1"
    assert conversation["messages"][-1]["status"] == "processing"


def test_image_query_updates_processing_message_with_generated_asset(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        if method == "POST":
            return httpx.Response(200, json={"code": "success", "data": {"task_id": "image-task-1", "status": "processing"}}), {
                "code": "success",
                "data": {"task_id": "image-task-1", "status": "processing"},
            }
        assert method == "GET"
        assert url == "https://token.example.com/v1/images/generations/image-task-1"
        return httpx.Response(
            200,
            json={
                "id": "image-task-1",
                "status": "completed",
                "data": {
                    "url": "https://cdn.example.com/async-image.png",
                    "progress": "100%",
                },
            },
        ), {
            "id": "image-task-1",
            "status": "completed",
            "data": {
                "url": "https://cdn.example.com/async-image.png",
                "progress": "100%",
            },
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")

    created = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "async image"}},
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation"]["id"]

    queried = client.post(
        "/api/proxy/image/query",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "conversationId": conversation_id, "taskId": "image-task-1"},
    )

    assert queried.status_code == 200
    payload = queried.json()
    assert payload["status"] == "completed"
    assert payload["images"][0]["src"] == "https://cdn.example.com/async-image.png"
    assert payload["assistantMessage"]["status"] == "success"
    assert payload["assistantMessage"]["assets"][0]["url"] == "https://cdn.example.com/async-image.png"
    conversation = client.get(f"/api/conversations/{conversation_id}").json()["conversation"]
    assert conversation["messages"][-1]["content"] == "completed"
    assert conversation["messages"][-1]["assets"][0]["assetType"] == "image"


def test_image_query_keeps_repeated_async_results_in_separate_messages(monkeypatch) -> None:
    created_tasks: list[str] = []

    async def fake_forward_json(method, url, api_key, body=None):
        if method == "POST":
            task_id = f"image-task-{len(created_tasks) + 1}"
            created_tasks.append(task_id)
            return httpx.Response(200, json={"code": "success", "data": {"task_id": task_id, "status": "processing"}}), {
                "code": "success",
                "data": {"task_id": task_id, "status": "processing"},
            }
        assert method == "GET"
        task_id = url.rsplit("/", 1)[-1]
        return httpx.Response(
            200,
            json={
                "id": task_id,
                "status": "completed",
                "data": {
                    "url": f"https://cdn.example.com/{task_id}.png",
                    "progress": "100%",
                },
            },
        ), {
            "id": task_id,
            "status": "completed",
            "data": {
                "url": f"https://cdn.example.com/{task_id}.png",
                "progress": "100%",
            },
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")
    headers = csrf_headers(client)

    first_created = client.post(
        "/api/proxy/image",
        headers=headers,
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "first async image"}},
    )
    assert first_created.status_code == 200
    conversation_id = first_created.json()["conversation"]["id"]
    first_queried = client.post(
        "/api/proxy/image/query",
        headers=headers,
        json={"subModelId": sub_model_id, "conversationId": conversation_id, "taskId": "image-task-1"},
    )
    assert first_queried.status_code == 200

    second_created = client.post(
        "/api/proxy/image",
        headers=headers,
        json={
            "subModelId": sub_model_id,
            "conversationId": conversation_id,
            "requestBody": {"prompt": "second async image"},
        },
    )
    assert second_created.status_code == 200
    second_queried = client.post(
        "/api/proxy/image/query",
        headers=headers,
        json={"subModelId": sub_model_id, "conversationId": conversation_id, "taskId": "image-task-2"},
    )
    assert second_queried.status_code == 200

    conversation = client.get(f"/api/conversations/{conversation_id}").json()["conversation"]
    assert [(message["role"], message["content"]) for message in conversation["messages"]] == [
        ("user", "first async image"),
        ("assistant", "completed"),
        ("user", "second async image"),
        ("assistant", "completed"),
    ]
    assistant_messages = [message for message in conversation["messages"] if message["role"] == "assistant"]
    assert [asset["url"] for asset in assistant_messages[0]["assets"]] == ["https://cdn.example.com/image-task-1.png"]
    assert [asset["url"] for asset in assistant_messages[1]["assets"]] == ["https://cdn.example.com/image-task-2.png"]


def test_image_proxy_hands_off_long_request_and_query_updates_asset(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        assert method == "POST"
        await asyncio.sleep(0.05)
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/slow-image.png"}]}), {
            "data": [{"url": "https://cdn.example.com/slow-image.png"}],
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    settings = main_module.get_settings()
    monkeypatch.setattr(settings, "long_request_handoff_seconds", 0.01, raising=False)

    with TestClient(app) as client:
        login(client, "alice")
        sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")
        headers = csrf_headers(client)

        response = client.post(
            "/api/proxy/image",
            headers=headers,
            json={"subModelId": sub_model_id, "requestBody": {"prompt": "slow image"}},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "processing"
        assert payload["taskId"].startswith("local-image-task-")
        assert payload["images"] == []
        assert payload["assistantMessage"]["content"] == payload["taskId"]
        assert payload["assistantMessage"]["status"] == "processing"

        completed = wait_for_completed_task(
            client,
            "/api/proxy/image/query",
            headers,
            {
                "subModelId": sub_model_id,
                "conversationId": payload["conversation"]["id"],
                "taskId": payload["taskId"],
            },
        )

        assert completed["images"][0]["src"] == "https://cdn.example.com/slow-image.png"
        assert completed["assistantMessage"]["status"] == "success"
        assert completed["assistantMessage"]["assets"][0]["url"] == "https://cdn.example.com/slow-image.png"
        conversation = client.get(f"/api/conversations/{payload['conversation']['id']}").json()["conversation"]
        assert conversation["messages"][-1]["assets"][0]["assetType"] == "image"


def test_image_long_request_marks_message_failed_when_background_parser_crashes(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        assert method == "POST"
        await asyncio.sleep(0.05)
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/slow-image.png"}]}), {
            "data": [{"url": "https://cdn.example.com/slow-image.png"}],
        }

    def broken_extract_images_from_response(raw):
        raise RuntimeError("image parser exploded")

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    monkeypatch.setattr(main_module, "extract_images_from_response", broken_extract_images_from_response)
    settings = main_module.get_settings()
    monkeypatch.setattr(settings, "long_request_handoff_seconds", 0.01, raising=False)

    with TestClient(app) as client:
        login(client, "alice")
        sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")
        headers = csrf_headers(client)

        response = client.post(
            "/api/proxy/image",
            headers=headers,
            json={"subModelId": sub_model_id, "requestBody": {"prompt": "slow image crash"}},
        )

        assert response.status_code == 200
        payload = response.json()
        failed = wait_for_task_status(
            client,
            "/api/proxy/image/query",
            headers,
            {
                "subModelId": sub_model_id,
                "conversationId": payload["conversation"]["id"],
                "taskId": payload["taskId"],
            },
            "failed",
        )

        assert failed["assistantMessage"]["status"] == "error"
        assert failed["assistantMessage"]["canRetry"] is True


def test_image_long_request_query_finds_failed_message_after_upstream_error_without_task_id(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        await asyncio.sleep(0.05)
        return httpx.Response(502, json={"error": {"message": "policy rejected"}}), {
            "error": {"message": "policy rejected"}
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    settings = main_module.get_settings()
    monkeypatch.setattr(settings, "long_request_handoff_seconds", 0.01, raising=False)

    with TestClient(app) as client:
        login(client, "alice")
        sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")
        headers = csrf_headers(client)

        response = client.post(
            "/api/proxy/image",
            headers=headers,
            json={"subModelId": sub_model_id, "requestBody": {"prompt": "slow rejected image"}},
        )

        assert response.status_code == 200
        payload = response.json()
        failed = wait_for_task_status(
            client,
            "/api/proxy/image/query",
            headers,
            {
                "subModelId": sub_model_id,
                "conversationId": payload["conversation"]["id"],
                "taskId": payload["taskId"],
            },
            "failed",
        )

        assert failed["assistantMessage"]["status"] == "error"
        assert failed["assistantMessage"]["canRetry"] is True
        assert failed["assistantMessage"]["errorMessage"] == "生成失败，请稍后重试。"
        assert "raw" not in failed


def test_image_query_uses_single_failed_message_as_legacy_local_task_fallback(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(502, json={"error": {"message": "policy rejected"}}), {
            "error": {"message": "policy rejected"}
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)

    with TestClient(app) as client:
        login(client, "alice")
        sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")
        headers = csrf_headers(client)

        response = client.post(
            "/api/proxy/image",
            headers=headers,
            json={"subModelId": sub_model_id, "requestBody": {"prompt": "legacy rejected image"}},
        )

        assert response.status_code == 200
        payload = response.json()
        queried = client.post(
            "/api/proxy/image/query",
            headers=headers,
            json={
                "subModelId": sub_model_id,
                "conversationId": payload["conversation"]["id"],
                "taskId": "local-image-task-legacy",
            },
        )

        assert queried.status_code == 200
        assert queried.json()["status"] == "failed"
        assert queried.json()["assistantMessage"]["status"] == "error"
        assert "raw" not in queried.json()


def test_image_proxy_normalizes_html_gateway_timeout(monkeypatch) -> None:
    html = "<html><head><title>504 Gateway Time-out</title></head><body>nginx</body></html>"

    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(504, text=html), html

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")

    response = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "timeout image"}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["images"] == []
    assert payload["assistantMessage"]["status"] == "error"
    assert payload["assistantMessage"]["canRetry"] is True
    conversation = client.get(f"/api/conversations/{payload['conversation']['id']}").json()["conversation"]
    assert conversation["messages"][-1]["errorMessage"] == "生成失败，请稍后重试。"


def test_image_proxy_hides_non_json_upstream_details_from_user(monkeypatch) -> None:
    raw = {
        "error": {
            "message": "invalid character '<' looking for beginning of value",
            "type": "bad_response_body",
            "code": "bad_response_body",
        }
    }

    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(502, json=raw), raw

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "new-api-image")

    response = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "bad json image"}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert "raw" not in payload
    assert payload["assistantMessage"]["errorMessage"] == "生成失败，请稍后重试。"
    conversation = client.get(f"/api/conversations/{payload['conversation']['id']}").json()["conversation"]
    assert conversation["messages"][-1]["errorMessage"] == "生成失败，请稍后重试。"


def test_image_proxy_records_config_path_timeout_in_conversation(monkeypatch) -> None:
    html = "<html><head><title>504 Gateway Time-out</title></head><body>nginx</body></html>"

    async def fake_forward_json(method, url, api_key, body=None):
        assert url == "https://token.example.com/v1/images/generations"
        return httpx.Response(504, text=html), html

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")

    response = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={
            "config": {"baseUrl": "https://token.example.com", "apiKey": "sk-test"},
            "model": "gpt-image-2",
            "conversationId": "local-conversation-a66fec0e-cdca-420c-9e5f-dc68c27e8ac2",
            "requestBody": {"prompt": "timeout image", "image": ["data:image/jpeg;base64,abc"]},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["images"] == []
    assert payload["conversation"]["messages"][-1]["status"] == "error"
    assert payload["conversation"]["messages"][-1]["canRetry"] is True
    conversation = client.get(f"/api/conversations/{payload['conversation']['id']}").json()["conversation"]
    assert [message["role"] for message in conversation["messages"]] == ["user", "assistant"]
    assert conversation["messages"][-1]["errorMessage"] == "生成失败，请稍后重试。"


def test_image_proxy_returns_transient_conversation_for_anonymous_config_timeout(monkeypatch) -> None:
    html = "<html><head><title>504 Gateway Time-out</title></head><body>nginx</body></html>"

    async def fake_forward_json(method, url, api_key, body=None):
        assert url == "https://token.example.com/v1/images/generations"
        assert api_key == "sk-test"
        assert body["prompt"] == "timeout image"
        return httpx.Response(504, text=html), html

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)

    response = client.post(
        "/api/proxy/image",
        json={
            "config": {"baseUrl": "https://token.example.com", "apiKey": "sk-test"},
            "model": "gpt-image-2",
            "conversationId": "local-conversation-a66fec0e-cdca-420c-9e5f-dc68c27e8ac2",
            "requestBody": {"prompt": "timeout image", "image": ["data:image/jpeg;base64,abc"]},
        },
    )

    assert response.status_code == 504
    detail = response.json()["detail"]
    message = "生成失败，请稍后重试。"
    assert detail["message"] == message
    assert "raw" not in detail
    conversation = detail["conversation"]
    assert conversation["id"] == "local-conversation-a66fec0e-cdca-420c-9e5f-dc68c27e8ac2"
    assert conversation["title"] == "timeout image"
    assert conversation["capability"] == "image"
    assert conversation["modelGroupId"] is None
    assert conversation["subModelId"] is None
    assert [item["role"] for item in conversation["messages"]] == ["user", "assistant"]
    assert conversation["messages"][0]["content"] == "timeout image"
    assistant = detail["assistantMessage"]
    assert assistant["id"] == conversation["messages"][-1]["id"]
    assert assistant["status"] == "error"
    assert assistant["errorMessage"] == message
    assert assistant["canRetry"] is True
    assert assistant["assets"] == []


def test_image_proxy_rejects_oversized_data_url_reference_before_forwarding(monkeypatch) -> None:
    async def fail_if_forwarded(method, url, api_key, body=None):
        raise AssertionError("oversized local references should be rejected before forwarding")

    monkeypatch.setattr(main_module, "forward_json", fail_if_forwarded)
    client = TestClient(app)
    large_reference = f"data:image/jpeg;base64,{'a' * (11 * 1024 * 1024)}"

    response = client.post(
        "/api/proxy/image",
        json={
            "config": {"baseUrl": "https://token.example.com", "apiKey": "sk-test"},
            "model": "gpt-image-2",
            "conversationId": "local-conversation-large-ref",
            "requestBody": {"prompt": "edit reference", "image": [large_reference]},
        },
    )

    assert response.status_code == 413
    detail = response.json()["detail"]
    assert detail["conversation"]["messages"][-1]["status"] == "error"
    assert detail["assistantMessage"]["canRetry"] is True


def test_image_proxy_persists_b64_response_as_generated_asset(monkeypatch) -> None:
    tiny_png = base64.b64encode(b"fake-png").decode("ascii")
    huge_raw = {
        "data": [{"b64_json": tiny_png, "revised_prompt": "small image"}],
        "usage": {"total_tokens": 7},
    }

    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(200, json=huge_raw), huge_raw

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")

    response = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "requestBody": {"prompt": "image from b64"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    image_url = payload["images"][0]["src"]
    assert image_url.startswith("/api/assets/generated/")
    assert "b64_json" not in payload["raw"]["data"][0]
    assert payload["raw"]["data"][0]["url"] == image_url
    assert payload["assistantMessage"]["assets"][0]["url"].startswith("/api/assets/")
    assert payload["assistantMessage"]["assets"][0]["url"].endswith("/content")
    conversation = client.get(f"/api/conversations/{payload['conversation']['id']}").json()["conversation"]
    assert conversation["messages"][-1]["assets"][0]["url"].startswith("/api/assets/")
    assert conversation["messages"][-1]["assets"][0]["url"].endswith("/content")

    asset_response = client.get(image_url)
    assert asset_response.status_code == 200
    assert asset_response.content == b"fake-png"


def test_image_proxy_persists_data_url_response_as_generated_asset(monkeypatch) -> None:
    tiny_png = base64.b64encode(b"fake-png-from-data-url").decode("ascii")
    data_url = f"data:image/png;base64,{tiny_png}"
    raw = {
        "data": [{"url": data_url, "revised_prompt": "small image"}],
        "usage": {"total_tokens": 7},
    }

    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(200, json=raw), raw

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")

    response = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "requestBody": {"prompt": "image from data url"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    image_url = payload["images"][0]["src"]
    assert image_url.startswith("/api/assets/generated/")
    assert payload["raw"]["data"][0]["url"] == image_url
    assert "data:image/png;base64" not in payload["raw"]["data"][0]["url"]
    assert payload["assistantMessage"]["assets"][0]["url"].startswith("/api/assets/")
    assert payload["assistantMessage"]["assets"][0]["url"].endswith("/content")

    asset_response = client.get(image_url)
    assert asset_response.status_code == 200
    assert asset_response.content == b"fake-png-from-data-url"


def test_image_proxy_sanitizes_large_reference_data_urls_before_storing(monkeypatch) -> None:
    reference_data_url = f"data:image/jpeg;base64,{'a' * 8000}"

    async def fake_forward_multipart(url, api_key, *, data=None, files=None):
        assert url == "https://token.example.com/v1/images/edits"
        assert data["prompt"] == "edit reference"
        assert files[0][0] == "image"
        assert files[0][1][0] == "reference-0.jpg"
        assert files[0][1][2] == "image/jpeg"
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/generated.png"}]}), {
            "data": [{"url": "https://cdn.example.com/generated.png"}]
        }

    monkeypatch.setattr(main_module, "forward_multipart", fake_forward_multipart)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")

    response = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "requestBody": {"prompt": "edit reference", "image": [reference_data_url]},
        },
    )

    assert response.status_code == 200
    conversation = client.get(f"/api/conversations/{response.json()['conversation']['id']}").json()["conversation"]
    assistant = conversation["messages"][-1]
    assert assistant["assets"][0]["url"] == "https://cdn.example.com/generated.png"

    from app.database import SessionLocal
    from app.db_models import ConversationMessage

    with SessionLocal() as db:
        messages = db.query(ConversationMessage).order_by(ConversationMessage.created_at).all()
        assert len(messages[0].request_json) < 1000
        assert "<data-url image/jpeg" in messages[0].request_json
        assert "a" * 100 not in messages[0].request_json


def test_image_proxy_expands_local_upload_reference_before_forwarding(monkeypatch) -> None:
    upload_name = "reference-car.jpg"
    (main_module.LOCAL_UPLOAD_DIR / upload_name).write_bytes(b"fake-jpeg")

    async def fake_forward_multipart(url, api_key, *, data=None, files=None):
        assert url == "https://token.example.com/v1/images/edits"
        assert files == [("image", ("reference-car.jpg", b"fake-jpeg", "image/jpeg"))]
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/generated.png"}]}), {
            "data": [{"url": "https://cdn.example.com/generated.png"}]
        }

    monkeypatch.setattr(main_module, "forward_multipart", fake_forward_multipart)
    client = TestClient(app)

    response = client.post(
        "/api/proxy/image",
        json={
            "config": {"baseUrl": "https://token.example.com", "apiKey": "sk-test"},
            "model": "gpt-image-2",
            "requestBody": {
                "prompt": "edit local upload",
                "image": [f"/api/assets/uploads/{upload_name}"],
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["images"][0]["src"] == "https://cdn.example.com/generated.png"


def test_image_proxy_uses_edit_endpoint_for_reference_images(monkeypatch) -> None:
    upload_name = "reference-edit.jpg"
    (main_module.LOCAL_UPLOAD_DIR / upload_name).write_bytes(b"fake-jpeg")

    async def fail_json_forward(method, url, api_key, body=None):
        raise AssertionError("reference image requests should use multipart image edits")

    async def fake_forward_image_edit(url, api_key, *, data=None, files=None):
        assert url == "https://token.example.com/v1/images/edits"
        assert api_key == "sk-test"
        assert data["prompt"] == "edit local upload"
        assert data["model"] == "gpt-image-2"
        assert files == [("image", ("reference-edit.jpg", b"fake-jpeg", "image/jpeg"))]
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/edited.png"}]}), {
            "data": [{"url": "https://cdn.example.com/edited.png"}]
        }

    monkeypatch.setattr(main_module, "forward_json", fail_json_forward)
    monkeypatch.setattr(main_module, "forward_multipart", fake_forward_image_edit)
    client = TestClient(app)

    response = client.post(
        "/api/proxy/image",
        json={
            "config": {"baseUrl": "https://token.example.com", "apiKey": "sk-test"},
            "model": "gpt-image-2",
            "requestBody": {
                "prompt": "edit local upload",
                "image": [f"/api/assets/uploads/{upload_name}"],
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["images"][0]["src"] == "https://cdn.example.com/edited.png"


def test_image_proxy_treats_image_openai_images_field_as_edit_references(monkeypatch) -> None:
    upload_name = "reference-images-field.jpg"
    (main_module.LOCAL_UPLOAD_DIR / upload_name).write_bytes(b"fake-jpeg")

    async def fail_json_forward(method, url, api_key, body=None):
        raise AssertionError("image-openai reference uploads should use image edits")

    async def fake_forward_image_edit(url, api_key, *, data=None, files=None):
        assert url == "https://token.example.com/v1/images/edits"
        assert data["prompt"] == "restore same person"
        assert data["model"] == "gpt-image-2"
        assert files == [("image", ("reference-images-field.jpg", b"fake-jpeg", "image/jpeg"))]
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/edited.png"}]}), {
            "data": [{"url": "https://cdn.example.com/edited.png"}]
        }

    monkeypatch.setattr(main_module, "forward_json", fail_json_forward)
    monkeypatch.setattr(main_module, "forward_multipart", fake_forward_image_edit)
    client = TestClient(app)

    response = client.post(
        "/api/proxy/image",
        json={
            "config": {"baseUrl": "https://token.example.com", "apiKey": "sk-test"},
            "adapter": "image-openai",
            "model": "gpt-image-2",
            "requestBody": {
                "prompt": "restore same person",
                "images": [f"/api/assets/uploads/{upload_name}"],
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["images"][0]["src"] == "https://cdn.example.com/edited.png"


def test_image_proxy_falls_back_to_generation_when_edit_endpoint_returns_html_parse_error(monkeypatch) -> None:
    upload_name = "reference-fallback.jpg"
    (main_module.LOCAL_UPLOAD_DIR / upload_name).write_bytes(b"fake-jpeg")
    calls: list[str] = []

    async def fake_forward_image_edit(url, api_key, *, data=None, files=None):
        calls.append("edit")
        assert url == "https://token.example.com/v1/images/edits"
        assert files == [("image", ("reference-fallback.jpg", b"fake-jpeg", "image/jpeg"))]
        raw = {
            "error": {
                "message": "invalid character '<' looking for beginning of value",
                "type": "bad_response_body",
                "code": "bad_response_body",
            }
        }
        return httpx.Response(502, json=raw), raw

    async def fake_forward_generation(method, url, api_key, body=None):
        calls.append("generation")
        assert method == "POST"
        assert url == "https://token.example.com/v1/images/generations"
        assert body["prompt"] == "edit local upload"
        assert body["image"][0].startswith("data:image/jpeg;base64,")
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/fallback.png"}]}), {
            "data": [{"url": "https://cdn.example.com/fallback.png"}]
        }

    monkeypatch.setattr(main_module, "forward_multipart", fake_forward_image_edit)
    monkeypatch.setattr(main_module, "forward_json", fake_forward_generation)
    client = TestClient(app)

    response = client.post(
        "/api/proxy/image",
        json={
            "config": {"baseUrl": "https://token.example.com", "apiKey": "sk-test"},
            "model": "gpt-image-2",
            "requestBody": {
                "prompt": "edit local upload",
                "image": [f"/api/assets/uploads/{upload_name}"],
            },
        },
    )

    assert response.status_code == 200
    assert calls == ["edit", "generation"]
    assert response.json()["images"][0]["src"] == "https://cdn.example.com/fallback.png"


def test_image_proxy_allows_normal_sized_local_jpeg_reference(monkeypatch) -> None:
    upload_name = "normal-reference.jpg"
    (main_module.LOCAL_UPLOAD_DIR / upload_name).write_bytes(b"x" * 60426)

    async def fake_forward_multipart(url, api_key, *, data=None, files=None):
        assert url == "https://token.example.com/v1/images/edits"
        assert files[0][1][0] == "normal-reference.jpg"
        assert files[0][1][1] == b"x" * 60426
        assert files[0][1][2] == "image/jpeg"
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/generated.png"}]}), {
            "data": [{"url": "https://cdn.example.com/generated.png"}]
        }

    monkeypatch.setattr(main_module, "forward_multipart", fake_forward_multipart)
    client = TestClient(app)

    response = client.post(
        "/api/proxy/image",
        json={
            "config": {"baseUrl": "https://token.example.com", "apiKey": "sk-test"},
            "model": "gpt-image-2",
            "requestBody": {
                "prompt": "edit normal local upload",
                "image": [f"/api/assets/uploads/{upload_name}"],
            },
        },
    )

    assert response.status_code == 200


def test_image_proxy_records_http_error_as_retryable_conversation_message(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        raise httpx.ReadTimeout("upstream timed out")

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")

    response = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "requestBody": {"prompt": "timeout image generation"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["assistantMessage"]["status"] == "error"
    assert payload["assistantMessage"]["canRetry"] is True
    conversation = client.get(f"/api/conversations/{payload['conversation']['id']}").json()["conversation"]
    assert [message["role"] for message in conversation["messages"]] == ["user", "assistant"]
    assert conversation["messages"][-1]["errorMessage"] == "生成失败，请稍后重试。"


def test_image_proxy_returns_latest_messages_when_appending_to_existing_conversation(monkeypatch) -> None:
    calls = 0

    async def fake_forward_json(method, url, api_key, body=None):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"data": [{"url": f"https://cdn.example.com/image-{calls}.png"}]}), {
            "data": [{"url": f"https://cdn.example.com/image-{calls}.png"}]
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")

    first = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "requestBody": {"prompt": "first image"},
        },
    )
    assert first.status_code == 200
    first_conversation = first.json()["conversation"]

    second = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "conversationId": first_conversation["id"],
            "requestBody": {"prompt": "second image"},
        },
    )

    assert second.status_code == 200
    second_conversation = second.json()["conversation"]
    assert second_conversation["updatedAt"] != first_conversation["updatedAt"]
    assert [message["role"] for message in second_conversation["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert second_conversation["messages"][-1]["assets"][0]["url"] == "https://cdn.example.com/image-2.png"


def test_video_create_and_query_record_playable_asset(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        if method == "POST":
            return httpx.Response(200, json={"id": "task-1", "status": "processing"}), {
                "id": "task-1",
                "status": "processing",
            }
        return httpx.Response(200, json={"id": "task-1", "status": "completed", "video_url": "https://cdn.example.com/video.mp4"}), {
            "id": "task-1",
            "status": "completed",
            "video_url": "https://cdn.example.com/video.mp4",
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "video", "video-unified-generic", "seedance-2.0")

    created = client.post(
        "/api/proxy/video/create",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "一杯茶旋转"}},
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation"]["id"]

    queried = client.post(
        "/api/proxy/video/query",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "conversationId": conversation_id,
            "taskId": "task-1",
        },
    )

    assert queried.status_code == 200
    assert queried.json()["assistantMessage"]["assets"][0]["url"] == "https://cdn.example.com/video.mp4"


def test_video_create_records_submitted_task_event_visible_in_timeline(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(200, json={"id": "task-event-create", "status": "processing"}), {
            "id": "task-event-create",
            "status": "processing",
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "admin")
    client.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-task-events", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    sub_model_id = create_model(client, "video", "video-unified-generic", "seedance-2.0")

    created = client.post(
        "/api/proxy/video/create",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "structured event video"}},
    )

    assert created.status_code == 200
    timeline = client.get("/api/admin/tasks/task-event-create/timeline")
    assert timeline.status_code == 200
    events = timeline.json()["events"]
    task_events = [event for event in events if event["source"] == "task_event"]
    assert [event["eventType"] for event in task_events] == ["submitted"]
    assert task_events[0]["status"] == "processing"
    assert task_events[0]["endpoint"] == "/api/proxy/video/create"
    assert task_events[0]["payload"]["providerTaskId"] == "task-event-create"
    assert task_events[0]["payload"]["conversationId"] == created.json()["conversation"]["id"]


def test_video_query_completed_records_completed_task_event_visible_in_timeline(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        if method == "POST":
            return httpx.Response(200, json={"id": "task-event-complete", "status": "processing"}), {
                "id": "task-event-complete",
                "status": "processing",
            }
        return httpx.Response(
            200,
            json={"id": "task-event-complete", "status": "completed", "video_url": "https://cdn.example.com/event.mp4"},
        ), {
            "id": "task-event-complete",
            "status": "completed",
            "video_url": "https://cdn.example.com/event.mp4",
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "admin")
    client.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-task-events", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    sub_model_id = create_model(client, "video", "video-unified-generic", "seedance-2.0")
    headers = csrf_headers(client)

    created = client.post(
        "/api/proxy/video/create",
        headers=headers,
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "completed structured event video"}},
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation"]["id"]

    queried = client.post(
        "/api/proxy/video/query",
        headers=headers,
        json={"subModelId": sub_model_id, "conversationId": conversation_id, "taskId": "task-event-complete"},
    )

    assert queried.status_code == 200
    timeline = client.get("/api/admin/tasks/task-event-complete/timeline")
    assert timeline.status_code == 200
    task_events = [event for event in timeline.json()["events"] if event["source"] == "task_event"]
    assert [event["eventType"] for event in task_events] == ["submitted", "completed"]
    assert [event["status"] for event in task_events] == ["processing", "success"]
    assert task_events[1]["endpoint"] == "/api/proxy/video/query"
    assert task_events[1]["payload"]["videoUrl"] == "https://cdn.example.com/event.mp4"
    assert task_events[1]["payload"]["status"] == "completed"


def test_image_create_records_submitted_task_event_visible_in_timeline(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(
            200,
            json={"code": "success", "data": {"task_id": "image-task-event-create", "status": "processing"}},
        ), {
            "code": "success",
            "data": {"task_id": "image-task-event-create", "status": "processing"},
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "admin")
    client.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-image-task-events", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")

    created = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "structured event image"}},
    )

    assert created.status_code == 200
    timeline = client.get("/api/admin/tasks/image-task-event-create/timeline")
    assert timeline.status_code == 200
    task_events = [event for event in timeline.json()["events"] if event["source"] == "task_event"]
    assert [event["eventType"] for event in task_events] == ["submitted"]
    assert task_events[0]["status"] == "processing"
    assert task_events[0]["endpoint"] == "/api/proxy/image"
    assert task_events[0]["payload"]["providerTaskId"] == "image-task-event-create"
    assert task_events[0]["payload"]["conversationId"] == created.json()["conversation"]["id"]


def test_image_query_completed_records_completed_task_event_visible_in_timeline(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        if method == "POST":
            return httpx.Response(
                200,
                json={"code": "success", "data": {"task_id": "image-task-event-complete", "status": "processing"}},
            ), {
                "code": "success",
                "data": {"task_id": "image-task-event-complete", "status": "processing"},
            }
        return httpx.Response(
            200,
            json={
                "id": "image-task-event-complete",
                "status": "completed",
                "data": {"url": "https://cdn.example.com/event-image.png", "progress": "100%"},
            },
        ), {
            "id": "image-task-event-complete",
            "status": "completed",
            "data": {"url": "https://cdn.example.com/event-image.png", "progress": "100%"},
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "admin")
    client.post(
        "/api/auth/dev-login",
        json={"externalUserId": "admin-image-task-events", "email": "cage_ben@sina.com", "nickname": "Admin"},
    )
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")
    headers = csrf_headers(client)

    created = client.post(
        "/api/proxy/image",
        headers=headers,
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "completed structured event image"}},
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation"]["id"]

    queried = client.post(
        "/api/proxy/image/query",
        headers=headers,
        json={"subModelId": sub_model_id, "conversationId": conversation_id, "taskId": "image-task-event-complete"},
    )

    assert queried.status_code == 200
    timeline = client.get("/api/admin/tasks/image-task-event-complete/timeline")
    assert timeline.status_code == 200
    task_events = [event for event in timeline.json()["events"] if event["source"] == "task_event"]
    assert [event["eventType"] for event in task_events] == ["submitted", "completed"]
    assert [event["status"] for event in task_events] == ["processing", "success"]
    assert task_events[1]["endpoint"] == "/api/proxy/image/query"
    assert task_events[1]["payload"]["images"][0]["src"] == "https://cdn.example.com/event-image.png"
    assert task_events[1]["payload"]["status"] == "completed"


def test_video_create_with_different_sub_model_does_not_reuse_existing_conversation(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(200, json={"id": f"task-{body['model']}", "status": "processing"}), {
            "id": f"task-{body['model']}",
            "status": "processing",
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    veo_sub_model_id = create_model(client, "video", "video-unified-generic", "gemini-veo-3.1")
    happyhorse_sub_model_id = create_model(client, "video", "video-unified-generic", "happyhorse-1.0-i2v")

    veo_created = client.post(
        "/api/proxy/video/create",
        headers=csrf_headers(client),
        json={"subModelId": veo_sub_model_id, "requestBody": {"model": "gemini-veo-3.1", "prompt": "veo prompt"}},
    )
    assert veo_created.status_code == 200
    veo_conversation_id = veo_created.json()["conversation"]["id"]

    happyhorse_created = client.post(
        "/api/proxy/video/create",
        headers=csrf_headers(client),
        json={
            "subModelId": happyhorse_sub_model_id,
            "conversationId": veo_conversation_id,
            "requestBody": {"model": "happyhorse-1.0-i2v", "prompt": "happyhorse prompt"},
        },
    )

    assert happyhorse_created.status_code == 200
    payload = happyhorse_created.json()
    assert payload["conversation"]["id"] != veo_conversation_id
    assert payload["conversation"]["subModelId"] == happyhorse_sub_model_id
    old_conversation = client.get(f"/api/conversations/{veo_conversation_id}").json()["conversation"]
    assert [message["content"] for message in old_conversation["messages"] if message["role"] == "user"] == ["veo prompt"]


def test_video_query_extracts_nested_veo_result_url(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        if method == "POST":
            return httpx.Response(200, json={"id": "task-veo", "status": "processing"}), {
                "id": "task-veo",
                "status": "processing",
            }
        return httpx.Response(
            200,
            json={
                "code": "success",
                "data": {
                    "task_id": "task-veo",
                    "status": "SUCCESS",
                    "progress": "100%",
                    "result_url": "https://ai-api.kkidc.com/v1/videos/task-veo/content",
                    "data": {
                        "status": "completed",
                        "url": "https://accessfree.example.com/task-veo.mp4",
                        "video_url": "https://accessfree.example.com/task-veo.mp4",
                        "result": {
                            "video_url": "https://access3.example.com/task-veo.mp4",
                            "download_url": "https://access3.example.com/task-veo.mp4",
                        },
                        "metadata": {
                            "video_url": "https://metadata.example.com/task-veo.mp4",
                        },
                    },
                },
            },
        ), {
            "code": "success",
            "data": {
                "task_id": "task-veo",
                "status": "SUCCESS",
                "progress": "100%",
                "result_url": "https://ai-api.kkidc.com/v1/videos/task-veo/content",
                "data": {
                    "status": "completed",
                    "url": "https://accessfree.example.com/task-veo.mp4",
                    "video_url": "https://accessfree.example.com/task-veo.mp4",
                    "result": {
                        "video_url": "https://access3.example.com/task-veo.mp4",
                        "download_url": "https://access3.example.com/task-veo.mp4",
                    },
                    "metadata": {
                        "video_url": "https://metadata.example.com/task-veo.mp4",
                    },
                },
            },
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "video", "video-unified-generic", "gemini-veo-3.1-generate-preview-ref-8s")

    created = client.post(
        "/api/proxy/video/create",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "veo nested video"}},
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation"]["id"]

    queried = client.post(
        "/api/proxy/video/query",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "conversationId": conversation_id, "taskId": "task-veo"},
    )

    assert queried.status_code == 200
    payload = queried.json()
    assert payload["status"] == "completed"
    assert payload["videoUrl"] == "https://accessfree.example.com/task-veo.mp4"
    assert payload["assistantMessage"]["status"] == "success"
    assert payload["assistantMessage"]["assets"][0]["url"] == "https://accessfree.example.com/task-veo.mp4"


def test_video_query_prefers_kkyi_authenticated_content_url_and_serializes_proxy(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        if method == "POST":
            return httpx.Response(200, json={"id": "task-auth", "status": "processing"}), {
                "id": "task-auth",
                "status": "processing",
            }
        return httpx.Response(
            200,
            json={
                "code": "success",
                "data": {
                    "task_id": "task-auth",
                    "status": "SUCCESS",
                    "progress": "100%",
                    "result_url": "https://ai-api.kkidc.com/v1/videos/task-auth/content",
                    "data": {
                        "status": "completed",
                        "url": "https://apibusiness.bafang.me/v1/videos/inner-task/content",
                        "video_url": "https://apibusiness.bafang.me/v1/videos/inner-task/content",
                        "download_url": "https://apibusiness.bafang.me/v1/videos/inner-task/content",
                    },
                },
            },
        ), {
            "code": "success",
            "data": {
                "task_id": "task-auth",
                "status": "SUCCESS",
                "progress": "100%",
                "result_url": "https://ai-api.kkidc.com/v1/videos/task-auth/content",
                "data": {
                    "status": "completed",
                    "url": "https://apibusiness.bafang.me/v1/videos/inner-task/content",
                    "video_url": "https://apibusiness.bafang.me/v1/videos/inner-task/content",
                    "download_url": "https://apibusiness.bafang.me/v1/videos/inner-task/content",
                },
            },
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model_with_base_url(
        client,
        "video",
        "video-unified-generic",
        "gemini-veo-3.1-generate-preview-8s",
        "https://ai-api.kkidc.com",
    )

    created = client.post(
        "/api/proxy/video/create",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "veo auth content"}},
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation"]["id"]

    queried = client.post(
        "/api/proxy/video/query",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "conversationId": conversation_id, "taskId": "task-auth"},
    )

    assert queried.status_code == 200
    payload = queried.json()
    assert payload["status"] == "completed"
    assert payload["videoUrl"] == "https://ai-api.kkidc.com/v1/videos/task-auth/content"
    asset = payload["assistantMessage"]["assets"][0]
    assert asset["assetType"] == "video"
    assert asset["url"] == f"/api/assets/video-content/{asset['id']}"


def test_video_content_proxy_streams_asset_with_model_key_and_range(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        if method == "POST":
            return httpx.Response(200, json={"id": "task-auth", "status": "processing"}), {
                "id": "task-auth",
                "status": "processing",
            }
        return httpx.Response(200, json={"id": "task-auth", "status": "completed", "video_url": "https://ai-api.kkidc.com/v1/videos/task-auth/content"}), {
            "id": "task-auth",
            "status": "completed",
            "video_url": "https://ai-api.kkidc.com/v1/videos/task-auth/content",
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model_with_base_url(
        client,
        "video",
        "video-unified-generic",
        "gemini-veo-3.1-generate-preview-8s",
        "https://ai-api.kkidc.com",
    )
    created = client.post(
        "/api/proxy/video/create",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "veo auth content"}},
    )
    conversation_id = created.json()["conversation"]["id"]
    queried = client.post(
        "/api/proxy/video/query",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "conversationId": conversation_id, "taskId": "task-auth"},
    )
    asset = queried.json()["assistantMessage"]["assets"][0]
    from app.database import SessionLocal
    from app.db_models import GeneratedAsset

    with SessionLocal() as db:
        stored_asset = db.get(GeneratedAsset, asset["id"])
        assert stored_asset is not None
        stored_asset.url = "https://apibusiness.bafang.me/v1/videos/legacy-inner-task/content"
        db.commit()

    captured: dict[str, object] = {}

    class FakeStreamResponse:
        status_code = 206
        is_success = True
        headers = {
            "content-type": "video/mp4",
            "content-length": "4",
            "content-range": "bytes 0-3/8",
            "accept-ranges": "bytes",
        }

        async def aiter_bytes(self):
            yield b"ftyp"

        async def aread(self):
            return b""

        async def aclose(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            captured["client_kwargs"] = kwargs

        def build_request(self, method, url, headers=None):
            captured["method"] = method
            captured["url"] = url
            captured["headers"] = headers or {}
            return {"method": method, "url": url, "headers": headers or {}}

        async def send(self, request, stream=False):
            captured["stream"] = stream
            return FakeStreamResponse()

        async def aclose(self):
            captured["closed"] = True

    monkeypatch.setattr(main_module.httpx, "AsyncClient", FakeAsyncClient)

    response = client.get(asset["url"], headers={"Range": "bytes=0-3"})

    assert response.status_code == 206
    assert response.content == b"ftyp"
    assert captured["method"] == "GET"
    assert captured["url"] == "https://ai-api.kkidc.com/v1/videos/task-auth/content"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["headers"]["Range"] == "bytes=0-3"
    assert captured["stream"] is True


def test_video_query_validation_messages_are_readable() -> None:
    client = TestClient(app)
    login(client, "alice")
    response = client.post(
        "/api/proxy/video/query",
        headers=csrf_headers(client),
        json={"config": {"baseUrl": "https://token.example.com", "apiKey": "sk-test"}, "taskId": "task-1"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "缺少视频适配器。"

    response = client.post(
        "/api/proxy/video/query",
        headers=csrf_headers(client),
        json={"config": {"baseUrl": "https://token.example.com", "apiKey": "sk-test"}, "adapter": "video-unified-generic"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "缺少任务 ID。"


def test_video_query_failure_records_retryable_message(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        if method == "POST":
            return httpx.Response(200, json={"id": "task-failed", "status": "processing"}), {
                "id": "task-failed",
                "status": "processing",
            }
        return httpx.Response(500, json={"error": {"message": "Video provider failed"}}), {
            "error": {"message": "Video provider failed"}
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "video", "video-unified-generic", "seedance-2.0")

    created = client.post(
        "/api/proxy/video/create",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "failed video"}},
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation"]["id"]

    queried = client.post(
        "/api/proxy/video/query",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "conversationId": conversation_id,
            "taskId": "task-failed",
        },
    )

    assert queried.status_code == 500
    detail = queried.json()["detail"]
    assert detail["message"] == "Video provider failed"
    assert detail["assistantMessage"]["status"] == "error"
    assert detail["assistantMessage"]["canRetry"] is True
    conversation = client.get(f"/api/conversations/{conversation_id}").json()["conversation"]
    assert conversation["messages"][-1]["errorMessage"] == "Video provider failed"


def test_video_query_failed_task_state_updates_processing_message(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        if method == "POST":
            return httpx.Response(200, json={"id": "task-failed-state", "status": "processing"}), {
                "id": "task-failed-state",
                "status": "processing",
            }
        return httpx.Response(
            200,
            json={
                "code": 0,
                "message": "success",
                "data": {
                    "task_id": "task-failed-state",
                    "status": "failed",
                    "fail_reason": "Upstream task failed in worker",
                },
            },
        ), {
            "code": 0,
            "message": "success",
            "data": {
                "task_id": "task-failed-state",
                "status": "failed",
                "fail_reason": "Upstream task failed in worker",
            },
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "video", "video-unified-generic", "seedance-2.0")

    created = client.post(
        "/api/proxy/video/create",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "failed task state"}},
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation"]["id"]

    queried = client.post(
        "/api/proxy/video/query",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "conversationId": conversation_id,
            "taskId": "task-failed-state",
        },
    )

    assert queried.status_code == 200
    payload = queried.json()
    assert payload["status"] == "failed"
    assert payload["assistantMessage"]["status"] == "error"
    assert payload["assistantMessage"]["canRetry"] is True
    assert payload["assistantMessage"]["errorMessage"] == "Upstream task failed in worker"
    conversation = client.get(f"/api/conversations/{conversation_id}").json()["conversation"]
    assert conversation["messages"][-1]["content"] == "task-failed-state"
    assert conversation["messages"][-1]["status"] == "error"
    assert conversation["messages"][-1]["canRetry"] is True


def test_video_query_unknown_state_with_error_updates_processing_message(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        if method == "POST":
            return httpx.Response(200, json={"id": "task-unknown-error", "status": "processing"}), {
                "id": "task-unknown-error",
                "status": "processing",
            }
        return httpx.Response(
            200,
            json={
                "id": "task-unknown-error",
                "task_id": "task-unknown-error",
                "status": "unknown",
                "progress": 100,
                "error": {"message": "Timed out after 20 minutes", "code": ""},
                "metadata": {"url": "Timed out after 20 minutes"},
            },
        ), {
            "id": "task-unknown-error",
            "task_id": "task-unknown-error",
            "status": "unknown",
            "progress": 100,
            "error": {"message": "Timed out after 20 minutes", "code": ""},
            "metadata": {"url": "Timed out after 20 minutes"},
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "video", "video-unified-generic", "seedance-2.0")

    created = client.post(
        "/api/proxy/video/create",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "unknown failed video"}},
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation"]["id"]

    queried = client.post(
        "/api/proxy/video/query",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "conversationId": conversation_id,
            "taskId": "task-unknown-error",
        },
    )

    assert queried.status_code == 200
    payload = queried.json()
    assert payload["status"] == "failed"
    assert payload["assistantMessage"]["status"] == "error"
    assert payload["assistantMessage"]["canRetry"] is True
    assert payload["assistantMessage"]["errorMessage"] == "Timed out after 20 minutes"


def test_video_query_processing_state_keeps_task_id_for_next_query(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(200, json={"id": "task-still-running", "status": "processing"}), {
            "id": "task-still-running",
            "status": "processing",
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "video", "video-unified-generic", "seedance-2.0")

    created = client.post(
        "/api/proxy/video/create",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "still running video"}},
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation"]["id"]

    queried = client.post(
        "/api/proxy/video/query",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "conversationId": conversation_id,
            "taskId": "task-still-running",
        },
    )

    assert queried.status_code == 200
    assistant = queried.json()["assistantMessage"]
    assert assistant["content"] == "task-still-running"
    assert assistant["status"] == "processing"
    assert assistant["canRetry"] is False


def test_video_query_success_replaces_retryable_message_for_same_task(monkeypatch) -> None:
    query_attempts = {"count": 0}

    async def fake_forward_json(method, url, api_key, body=None):
        if method == "POST":
            return httpx.Response(200, json={"id": "task-retry", "status": "processing"}), {
                "id": "task-retry",
                "status": "processing",
            }
        query_attempts["count"] += 1
        if query_attempts["count"] == 1:
            return httpx.Response(500, json={"error": {"message": "temporary query error"}}), {
                "error": {"message": "temporary query error"}
            }
        return httpx.Response(200, json={"id": "task-retry", "status": "completed", "video_url": "https://cdn.example.com/done.mp4"}), {
            "id": "task-retry",
            "status": "completed",
            "video_url": "https://cdn.example.com/done.mp4",
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "video", "video-unified-generic", "seedance-2.0")

    created = client.post(
        "/api/proxy/video/create",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "requestBody": {"prompt": "retry video"}},
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation"]["id"]

    failed = client.post(
        "/api/proxy/video/query",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "conversationId": conversation_id, "taskId": "task-retry"},
    )
    assert failed.status_code == 500

    recovered = client.post(
        "/api/proxy/video/query",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "conversationId": conversation_id, "taskId": "task-retry"},
    )

    assert recovered.status_code == 200
    messages = recovered.json()["conversation"]["messages"]
    task_messages = [message for message in messages if message["role"] == "assistant" and message["content"] in {"task-retry", "completed"}]
    assert len(task_messages) == 1
    assert task_messages[0]["status"] == "success"
    assert task_messages[0]["canRetry"] is False
    assert task_messages[0]["assets"][0]["url"] == "https://cdn.example.com/done.mp4"


def test_upload_presign_can_use_saved_sub_model_credentials(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        assert method == "POST"
        assert url == "https://token.example.com/api/upload/presign"
        assert api_key == "sk-test"
        assert body["file_name"] == "reference.png"
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "upload_url": "https://upload.example.com/reference.png",
                    "method": "PUT",
                    "public_url": "https://cdn.example.com/reference.png",
                    "object_key": "reference.png",
                    "content_type": "image/png",
                },
            },
        ), {
            "success": True,
            "data": {
                "upload_url": "https://upload.example.com/reference.png",
                "method": "PUT",
                "public_url": "https://cdn.example.com/reference.png",
                "object_key": "reference.png",
                "content_type": "image/png",
            },
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")

    response = client.post(
        "/api/proxy/upload/presign",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "fileName": "reference.png",
            "contentType": "image/png",
        },
    )

    assert response.status_code == 200
    assert response.json()["publicUrl"] == "https://cdn.example.com/reference.png"


def test_upload_presign_marks_object_storage_gap_when_provider_presign_is_unavailable(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        assert method == "POST"
        assert url == "https://token.example.com/api/upload/presign"
        return httpx.Response(404, json={"message": "404 page not found"}), {"message": "404 page not found"}

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    settings = main_module.get_settings()
    monkeypatch.setattr(settings, "object_storage_enabled", False)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")

    response = client.post(
        "/api/proxy/upload/presign",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "fileName": "reference.png",
            "contentType": "image/png",
        },
    )

    assert response.status_code == 404
    assert "object storage" in response.json()["detail"]["message"].lower()


def test_upload_presign_marks_object_storage_gap_when_provider_presign_connects_fail(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        raise httpx.ConnectError("name resolution failed")

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    settings = main_module.get_settings()
    monkeypatch.setattr(settings, "object_storage_enabled", False)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "image", "image-openai", "gpt-image-2")

    response = client.post(
        "/api/proxy/upload/presign",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "fileName": "reference.png",
            "contentType": "image/png",
        },
    )

    assert response.status_code == 503
    assert "object storage" in response.json()["detail"]["message"].lower()


def test_upload_presign_uses_configured_object_storage(monkeypatch) -> None:
    async def fail_if_forwarded(method, url, api_key, body=None):
        raise AssertionError("object storage uploads should not forward to model provider")

    monkeypatch.setattr(main_module, "forward_json", fail_if_forwarded)
    settings = main_module.get_settings()
    monkeypatch.setattr(settings, "object_storage_enabled", True)
    monkeypatch.setattr(settings, "object_storage_endpoint_url", "https://oss.example.com")
    monkeypatch.setattr(settings, "object_storage_bucket", "genstudio")
    monkeypatch.setattr(settings, "object_storage_region", "auto")
    monkeypatch.setattr(settings, "object_storage_access_key_id", "access-key")
    monkeypatch.setattr(settings, "object_storage_secret_access_key", "secret-key")
    monkeypatch.setattr(settings, "object_storage_public_base_url", "https://cdn.example.com/genstudio")
    monkeypatch.setattr(settings, "object_storage_key_prefix", "user-uploads")

    client = TestClient(app)
    login(client, "alice")

    response = client.post(
        "/api/proxy/upload/presign",
        headers=csrf_headers(client),
        json={"fileName": "reference image.png", "contentType": "image/png"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["method"] == "PUT"
    assert payload["contentType"] == "image/png"
    assert payload["objectKey"].startswith("user-uploads/uploads/")
    assert payload["objectKey"].endswith("reference-image.png")
    assert payload["publicUrl"].startswith("https://cdn.example.com/genstudio/user-uploads/uploads/")
    assert payload["uploadUrl"].startswith("https://oss.example.com/genstudio/user-uploads/uploads/")
    assert "X-Amz-Signature=" in payload["uploadUrl"]


def test_local_upload_fallback_stores_reference_file(monkeypatch) -> None:
    settings = main_module.get_settings()
    monkeypatch.setattr(settings, "object_storage_enabled", False)

    client = TestClient(app)

    response = client.post(
        "/api/upload/local",
        files={"file": ("reference.png", b"fake-reference", "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fileName"] == "reference.png"
    assert payload["contentType"] == "image/png"
    assert payload["publicUrl"].startswith("/api/assets/uploads/")
    asset_response = client.get(payload["publicUrl"])
    assert asset_response.status_code == 200
    assert asset_response.content == b"fake-reference"


def test_asset_urls_support_head_for_upstream_validation(monkeypatch) -> None:
    settings = main_module.get_settings()
    monkeypatch.setattr(settings, "object_storage_enabled", False)

    client = TestClient(app)
    upload_response = client.post(
        "/api/upload/local",
        files={"file": ("reference.png", b"fake-reference", "image/png")},
    )
    assert upload_response.status_code == 200

    uploaded_head = client.head(upload_response.json()["publicUrl"])
    assert uploaded_head.status_code == 200
    assert uploaded_head.headers["content-type"].startswith("image/png")
    assert uploaded_head.headers["content-length"] == str(len(b"fake-reference"))
    assert uploaded_head.content == b""

    generated_name = "head-check.png"
    (main_module.GENERATED_ASSET_DIR / generated_name).write_bytes(b"fake-generated")
    generated_head = client.head(f"/api/assets/generated/{generated_name}")
    assert generated_head.status_code == 200
    assert generated_head.headers["content-type"].startswith("image/png")
    assert generated_head.headers["content-length"] == str(len(b"fake-generated"))
    assert generated_head.content == b""


def test_protected_asset_content_and_thumbnail_authorize_owner_or_admin(monkeypatch) -> None:
    owner = TestClient(app)
    login(owner, "asset-owner")
    outsider = TestClient(app)
    login(outsider, "asset-outsider")
    admin = TestClient(app)
    login(admin, "asset-admin")
    settings = main_module.get_settings()
    monkeypatch.setattr(settings, "admin_identifiers", ["asset-admin"])

    original_path = main_module.GENERATED_ASSET_DIR / "protected-original.png"
    thumbnail_path = main_module.GENERATED_ASSET_DIR / "protected-thumbnail.webp"
    original_path.write_bytes(b"protected-original")
    thumbnail_path.write_bytes(b"protected-thumbnail")
    with main_module.SessionLocal() as db:
        user = db.query(main_module.User).filter(main_module.User.external_user_id == "asset-owner").one()
        conversation = main_module.Conversation(user_id=user.id, title="Protected", capability="image")
        db.add(conversation)
        db.flush()
        message = main_module.ConversationMessage(
            conversation_id=conversation.id,
            user_id=user.id,
            role="assistant",
            capability="image",
            content="done",
        )
        db.add(message)
        db.flush()
        asset = main_module.GeneratedAsset(
            user_id=user.id,
            conversation_id=conversation.id,
            message_id=message.id,
            capability="image",
            asset_type="image",
            url="/api/assets/generated/protected-original.png",
            local_path=str(original_path.resolve()),
            local_thumbnail_path=str(thumbnail_path.resolve()),
            storage_status="local_pending",
            content_type="image/png",
        )
        db.add(asset)
        db.commit()
        asset_id = asset.id

    assert TestClient(app).get(f"/api/assets/{asset_id}/content").status_code == 401
    assert outsider.get(f"/api/assets/{asset_id}/content").status_code == 404
    assert owner.get(f"/api/assets/{asset_id}/content").content == b"protected-original"
    assert owner.get(f"/api/assets/{asset_id}/thumbnail").content == b"protected-thumbnail"
    assert owner.head(f"/api/assets/{asset_id}/thumbnail").headers["content-length"] == str(len(b"protected-thumbnail"))
    assert admin.get(f"/api/assets/{asset_id}/content").content == b"protected-original"


def test_seedance_video_prompt_uses_text_content_for_title(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        return httpx.Response(200, json={"id": "task-2", "status": "processing"}), {
            "id": "task-2",
            "status": "processing",
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_model(client, "video", "video-seedance", "doubao-seedance-2-0-260128")

    created = client.post(
        "/api/proxy/video/create",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "requestBody": {
                "model": "doubao-seedance-2-0-260128",
                "content": [{"type": "text", "text": "一杯茶旋转"}],
            },
        },
    )

    assert created.status_code == 200
    conversation = created.json()["conversation"]
    assert conversation["title"] == "一杯茶旋转"
    assert conversation["messages"][0]["content"] == "一杯茶旋转"


def test_proxy_models_returns_friendly_error_on_upstream_connect_failure(monkeypatch) -> None:
    # A custom-provider baseURL that is genuinely unreachable (wrong network/DNS/wall)
    # must not crash the request into a bare 500 that browsers report as "Failed to fetch" -
    # it should surface a clean 502 with a helpful message instead.
    async def fake_forward_json(method, url, api_key, body=None):
        raise httpx.ConnectError("All connection attempts failed")

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")

    response = client.post(
        "/api/proxy/models",
        headers=csrf_headers(client),
        json={"config": {"baseUrl": "https://unreachable.example.com", "apiKey": "sk-test"}, "capability": "text"},
    )

    assert response.status_code == 502
    assert "message" in response.json()["detail"]


def test_proxy_models_returns_friendly_error_on_upstream_timeout(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        raise httpx.ConnectTimeout("Connection timed out")

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")

    response = client.post(
        "/api/proxy/models",
        headers=csrf_headers(client),
        json={"config": {"baseUrl": "https://slow.example.com", "apiKey": "sk-test"}, "capability": "text"},
    )

    assert response.status_code == 504
    assert "message" in response.json()["detail"]


def test_proxy_test_returns_friendly_error_on_upstream_connect_failure(monkeypatch) -> None:
    async def fake_forward_json(method, url, api_key, body=None):
        raise httpx.ConnectError("All connection attempts failed")

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")

    response = client.post(
        "/api/proxy/test",
        headers=csrf_headers(client),
        json={
            "config": {"baseUrl": "https://unreachable.example.com", "apiKey": "sk-test"},
            "capability": "text",
            "model": "gpt-4o",
        },
    )

    assert response.status_code == 502
    assert "message" in response.json()["detail"]


def test_sync_model_list_returns_friendly_error_on_upstream_connect_failure(monkeypatch) -> None:
    # The "获取模型" button on an already-saved model hits /api/models/{id}/sync,
    # which shares the same forward_json call and must not crash on connect errors either.
    client = TestClient(app)
    login(client, "alice")
    create_text_model(client)
    model_id = client.get("/api/models").json()["models"][0]["id"]
    assert model_id

    async def fake_forward_json(method, url, api_key=None, body=None):
        raise httpx.ConnectError("All connection attempts failed")

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)

    response = client.post(f"/api/models/{model_id}/sync", headers=csrf_headers(client))

    assert response.status_code == 502
    assert "message" in response.json()["detail"]
