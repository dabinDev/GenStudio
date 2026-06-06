from __future__ import annotations

import os
import sys
import tempfile
import base64

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
    assert detail["message"] == "Invalid API key"
    assert detail["assistantMessage"]["status"] == "error"
    assert detail["assistantMessage"]["canRetry"] is True
    messages = client.get(f"/api/conversations/{detail['conversation']['id']}").json()["conversation"]["messages"]
    assert messages[-1]["errorMessage"] == "Invalid API key"


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
    assert payload["assistantMessage"]["assets"][0]["url"] == image_url
    conversation = client.get(f"/api/conversations/{payload['conversation']['id']}").json()["conversation"]
    assert conversation["messages"][-1]["assets"][0]["url"] == image_url

    asset_response = client.get(image_url)
    assert asset_response.status_code == 200
    assert asset_response.content == b"fake-png"


def test_image_proxy_sanitizes_large_reference_data_urls_before_storing(monkeypatch) -> None:
    reference_data_url = f"data:image/jpeg;base64,{'a' * 70000}"

    async def fake_forward_json(method, url, api_key, body=None):
        assert body["image"] == [reference_data_url]
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/generated.png"}]}), {
            "data": [{"url": "https://cdn.example.com/generated.png"}]
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
