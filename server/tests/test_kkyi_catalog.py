from __future__ import annotations

import os
import sys
import tempfile

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

db_path = os.path.join(tempfile.gettempdir(), "genstudio-kkyi-catalog-test.sqlite3")
if os.path.exists(db_path):
    os.remove(db_path)

os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["GENSTUDIO_SECRET_KEY"] = "test-secret"

from app.database import Base, SessionLocal, engine  # noqa: E402
import app.main as main_module  # noqa: E402
from app.main import app  # noqa: E402
from app.catalog_service import upsert_catalog_model_detail  # noqa: E402
from app.db_models import CatalogModel  # noqa: E402


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    main_module.rate_limiter.clear()


def csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrfToken"]}


def kkyi_detail() -> dict:
    return {
        "id": "10024",
        "display_name": "GPT-5.4",
        "model_name": "gpt-5.4",
        "model_type": 1,
        "icon": "OpenAI",
        "description": "OpenAI top model",
        "input_hint": "Use for long reports",
        "parameters": [
            {
                "id": "10053",
                "display_name": "Attachments",
                "param_key": "attachments",
                "description": "",
                "widget_type": 6,
                "is_required": False,
                "default_value": "",
                "function_tag": "",
                "max_count": 10,
                "sort_order": 0,
                "options": [
                    {
                        "id": "10118",
                        "option_name": "Image",
                        "option_value": "image",
                        "description": ".jpg,.png",
                        "max_count": 10,
                        "is_default": False,
                        "sort_order": 0,
                        "price_factor": "1",
                    },
                ],
            },
            {
                "id": "10054",
                "display_name": "Web search",
                "param_key": "web_search",
                "description": "Enable web search",
                "widget_type": 5,
                "is_required": False,
                "default_value": "true",
                "function_tag": "",
                "sort_order": 1,
                "options": [],
            },
        ],
        "channel_groups": [
            {
                "channel_id": "10002",
                "groups": [
                    {
                        "id": "10026",
                        "channel_id": "10002",
                        "group_name": "Official",
                        "billing_type": 1,
                        "input_token_price": "14",
                        "output_token_price": "84",
                        "base_price": "0",
                        "success_rate_24h": "95.28",
                        "avg_response_seconds_24h": 63.012,
                        "total_success_count": "828",
                        "total_fail_count": "41",
                        "sort_order": 0,
                        "option_prices": [{"param": "attachments", "price": "1"}],
                    },
                ],
            }
        ],
    }


def kkyi_video_detail() -> dict:
    return {
        "id": "10028",
        "display_name": "Seed2.0-Fast",
        "model_name": "kuaikuai-2-flash-pro",
        "model_type": 3,
        "icon": "Doubao-color",
        "description": "Video model",
        "input_hint": "Use video parameters",
        "parameters": [
            {"id": "10134", "display_name": "生成模式", "param_key": "video_mode", "widget_type": 3, "is_required": False, "default_value": "reference", "options": []},
            {"id": "10122", "display_name": "视频比例", "param_key": "ratio", "widget_type": 3, "is_required": True, "default_value": "16:9", "options": []},
            {"id": "10123", "display_name": "分辨率", "param_key": "resolution", "widget_type": 3, "is_required": True, "default_value": "720p", "options": []},
            {"id": "10124", "display_name": "生成音频", "param_key": "generate_audio", "widget_type": 5, "is_required": False, "default_value": "true", "options": []},
            {"id": "10121", "display_name": "视频时长", "param_key": "duration", "widget_type": 3, "is_required": True, "default_value": "5", "options": []},
            {"id": "10125", "display_name": "生成数量", "param_key": "quantity", "widget_type": 2, "is_required": True, "default_value": "1", "options": []},
        ],
        "channel_groups": [],
    }


def test_upsert_kkyi_catalog_detail_persists_parameters_and_channel_groups() -> None:
    with SessionLocal() as db:
        model = upsert_catalog_model_detail(db, kkyi_detail())
        db.commit()
        db.refresh(model)

        stored = db.query(CatalogModel).filter(CatalogModel.external_id == "10024").one()

        assert stored.display_name == "GPT-5.4"
        assert stored.model_name == "gpt-5.4"
        assert stored.capability == "text"
        assert len(stored.parameters) == 2
        assert stored.parameters[0].param_key == "attachments"
        assert stored.parameters[0].options[0].option_value == "image"
        assert len(stored.channel_groups) == 1
        assert stored.channel_groups[0].group_name == "Official"
        assert stored.channel_groups[0].option_prices_json == '[{"param":"attachments","price":"1"}]'


def test_model_create_can_link_sub_model_to_catalog_parameters() -> None:
    with SessionLocal() as db:
        upsert_catalog_model_detail(db, kkyi_detail())
        db.commit()

    client = TestClient(app)
    client.post("/api/auth/dev-login", json={"externalUserId": "official-1"})

    response = client.post(
        "/api/models",
        headers=csrf_headers(client),
        json={
            "name": "KKYi GPT",
            "vendor": "KKYi",
            "capability": "text",
            "adapter": "text-chat",
            "baseUrl": "https://ai-api.kkidc.com",
            "apiKey": "sk-test",
            "primaryModelName": "gpt-5.4",
            "catalogModelId": "10024",
        },
    )

    assert response.status_code == 200
    model = response.json()["model"]
    assert model["catalogModelId"] == "10024"
    assert model["subModels"][0]["catalogModelId"] == "10024"
    assert model["subModels"][0]["catalog"]["parameters"][0]["paramKey"] == "attachments"
    assert model["subModels"][0]["catalog"]["channelGroups"][0]["groupName"] == "Official"


def test_catalog_sync_api_fetches_list_details_and_returns_models(monkeypatch) -> None:
    async def fake_fetch_kkyi_catalog_details(*, base_url: str, bearer_token: str, model_type: int) -> list[dict]:
        assert base_url == "https://www.kkyi.com"
        assert bearer_token == "token-from-request"
        assert model_type == 0
        return [kkyi_detail()]

    monkeypatch.setattr(main_module, "fetch_kkyi_catalog_details", fake_fetch_kkyi_catalog_details)
    client = TestClient(app)
    client.post("/api/auth/dev-login", json={"externalUserId": "official-1"})

    response = client.post(
        "/api/catalog/kkyi/sync",
        headers=csrf_headers(client),
        json={"bearerToken": "token-from-request", "modelType": 0},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["synced"] == 1
    assert payload["models"][0]["id"] == "10024"
    assert payload["models"][0]["parameters"][0]["paramKey"] == "attachments"

    listed = client.get("/api/catalog/models?capability=text")
    assert listed.status_code == 200
    assert listed.json()["models"][0]["modelName"] == "gpt-5.4"


def test_catalog_video_model_uses_kkyi_generation_path_and_flat_parameters(monkeypatch) -> None:
    with SessionLocal() as db:
        upsert_catalog_model_detail(db, kkyi_video_detail())
        db.commit()

    captured: dict[str, object] = {}

    async def fake_forward_json(method, url, api_key, body=None):
        captured.update({"method": method, "url": url, "body": body})
        return httpx.Response(200, json={"id": "task-1", "status": "queued"}), {"id": "task-1", "status": "queued"}

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    client.post("/api/auth/dev-login", json={"externalUserId": "official-1"})
    created = client.post(
        "/api/models",
        headers=csrf_headers(client),
        json={
            "name": "Seed Video",
            "vendor": "KKYi",
            "capability": "video",
            "adapter": "video-unified-generic",
            "baseUrl": "https://ai-api.kkidc.com",
            "apiKey": "sk-test",
            "primaryModelName": "kuaikuai-2-flash-pro",
            "catalogModelId": "10028",
        },
    )
    assert created.status_code == 200
    sub_model_id = created.json()["model"]["primarySubModelId"]

    response = client.post(
        "/api/proxy/video/create",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "requestBody": {
                "model": "kuaikuai-2-flash-pro",
                "prompt": "video test",
                "aspect_ratio": "16:9",
                "duration": 4,
                "resolution": "720p",
                "audio": False,
                "n": 1,
            },
        },
    )

    assert response.status_code == 200
    assert captured["url"] == "https://ai-api.kkidc.com/v1/video/generations"
    assert captured["body"] == {
        "model": "kuaikuai-2-flash-pro",
        "prompt": "video test",
        "ratio": "16:9",
        "duration": 4,
        "resolution": "720p",
        "generate_audio": False,
        "quantity": 1,
    }


def test_catalog_video_model_test_uses_kkyi_generation_path_and_flat_parameters(monkeypatch) -> None:
    with SessionLocal() as db:
        upsert_catalog_model_detail(db, kkyi_video_detail())
        db.commit()

    captured: dict[str, object] = {}

    async def fake_forward_json(method, url, api_key, body=None):
        captured.update({"method": method, "url": url, "body": body})
        return httpx.Response(200, json={"id": "task-test-1", "status": "queued"}), {"id": "task-test-1", "status": "queued"}

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    client.post("/api/auth/dev-login", json={"externalUserId": "official-1"})
    created = client.post(
        "/api/models",
        headers=csrf_headers(client),
        json={
            "name": "Seed Video",
            "vendor": "KKYi",
            "capability": "video",
            "adapter": "video-unified-generic",
            "baseUrl": "https://ai-api.kkidc.com",
            "apiKey": "sk-test",
            "primaryModelName": "kuaikuai-2-flash-pro",
            "catalogModelId": "10028",
        },
    )
    assert created.status_code == 200
    sub_model_id = created.json()["model"]["primarySubModelId"]

    response = client.post(
        "/api/proxy/test",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id},
    )

    assert response.status_code == 200
    assert captured["url"] == "https://ai-api.kkidc.com/v1/video/generations"
    assert captured["body"] == {
        "model": "kuaikuai-2-flash-pro",
        "prompt": "ping test, one second static shot",
        "ratio": "16:9",
        "duration": 1,
        "resolution": "540p",
        "generate_audio": False,
        "quantity": 1,
    }


def test_catalog_video_model_query_uses_kkyi_generation_detail_path(monkeypatch) -> None:
    with SessionLocal() as db:
        upsert_catalog_model_detail(db, kkyi_video_detail())
        db.commit()

    captured: dict[str, object] = {}

    async def fake_forward_json(method, url, api_key, body=None):
        captured.update({"method": method, "url": url, "body": body})
        return httpx.Response(200, json={"id": "task-1", "status": "processing"}), {"id": "task-1", "status": "processing"}

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    client.post("/api/auth/dev-login", json={"externalUserId": "official-1"})
    created = client.post(
        "/api/models",
        headers=csrf_headers(client),
        json={
            "name": "Seed Video",
            "vendor": "KKYi",
            "capability": "video",
            "adapter": "video-unified-generic",
            "baseUrl": "https://ai-api.kkidc.com",
            "apiKey": "sk-test",
            "primaryModelName": "kuaikuai-2-flash-pro",
            "catalogModelId": "10028",
        },
    )
    assert created.status_code == 200
    sub_model_id = created.json()["model"]["primarySubModelId"]

    response = client.post(
        "/api/proxy/video/query",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "taskId": "task-1"},
    )

    assert response.status_code == 200
    assert captured["method"] == "GET"
    assert captured["url"] == "https://ai-api.kkidc.com/v1/video/generations/task-1"
