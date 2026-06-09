from __future__ import annotations

import os
import sys
import tempfile
import base64
import asyncio
import time

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
    assert user_message["assets"][0]["url"] == reference_url
    assert user_message["assets"][0]["metadata"]["role"] == "reference"
    assert user_message["assets"][0]["metadata"]["source"] == "input"


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
    assert payload["assistantMessage"]["assets"][0]["url"] == image_url
    conversation = client.get(f"/api/conversations/{payload['conversation']['id']}").json()["conversation"]
    assert conversation["messages"][-1]["assets"][0]["url"] == image_url

    asset_response = client.get(image_url)
    assert asset_response.status_code == 200
    assert asset_response.content == b"fake-png"


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
