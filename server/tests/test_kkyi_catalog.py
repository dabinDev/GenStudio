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
from app.catalog_service import normalize_existing_catalog_icons, upsert_catalog_model_detail  # noqa: E402
from app.db_models import CatalogModel, SubModel  # noqa: E402


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    main_module.rate_limiter.clear()
    main_module.get_settings.cache_clear()


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


def test_catalog_icons_are_normalized_to_renderable_urls() -> None:
    with SessionLocal() as db:
        openai = upsert_catalog_model_detail(db, kkyi_detail())
        gemini_detail = {
            **kkyi_detail(),
            "id": "10025",
            "display_name": "Gemini 3.1 Pro Preview",
            "model_name": "gemini-3.1-pro-preview",
            "icon": "Gemini",
        }
        gemini = upsert_catalog_model_detail(db, gemini_detail)
        remote_detail = {
            **kkyi_detail(),
            "id": "10026",
            "display_name": "Seed2.0",
            "model_name": "kuaikuai-2-pro",
            "icon": "https://ai-apply-resource.kkidc.com/uploads/seed.png?x-oss-credential=expired",
        }
        remote = upsert_catalog_model_detail(db, remote_detail)
        unknown_remote_detail = {
            **kkyi_detail(),
            "id": "10027",
            "display_name": "Custom Vendor",
            "model_name": "custom-vendor-model",
            "icon": "https://cdn.example.com/custom-vendor.png",
        }
        unknown_remote = upsert_catalog_model_detail(db, unknown_remote_detail)
        grok_detail = {
            **kkyi_detail(),
            "id": "10028",
            "display_name": "Grok Image",
            "model_name": "grok-image-2",
            "icon": "Grok",
        }
        grok = upsert_catalog_model_detail(db, grok_detail)

        assert openai.icon == "https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons/OpenAI.svg"
        assert gemini.icon == "https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons/Gemini-color.svg"
        assert remote.icon == "https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons/Doubao-color.svg"
        assert unknown_remote.icon == "https://cdn.example.com/custom-vendor.png"
        assert grok.icon == "https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons/XAI.svg"


def test_existing_catalog_icons_are_normalized_with_model_context() -> None:
    with SessionLocal() as db:
        gpt_image = upsert_catalog_model_detail(
            db,
            {
                **kkyi_detail(),
                "id": "10034",
                "display_name": "GPT-Image-2",
                "model_name": "gpt-image-2",
                "model_type": 2,
                "icon": "https://ai-apply-resource.kkidc.com/uploads/gpt-image.png?x-oss-credential=expired",
            },
        )
        glm = upsert_catalog_model_detail(
            db,
            {
                **kkyi_detail(),
                "id": "10035",
                "display_name": "GLM-5",
                "model_name": "glm-5",
                "icon": "https://ai-apply-resource.kkidc.com/uploads/zhipu.png?x-oss-credential=expired",
            },
        )
        db.commit()

        gpt_image.icon = "https://ai-apply-resource.kkidc.com/uploads/gpt-image.png?x-oss-credential=expired"
        glm.icon = "https://ai-apply-resource.kkidc.com/uploads/zhipu.png?x-oss-credential=expired"
        changed = normalize_existing_catalog_icons(db)

        assert changed == 2
        assert gpt_image.icon == "https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons/OpenAI.svg"
        assert glm.icon == "https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons/Zhipu-color.svg"


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


def kkyi_video_detail_with_options() -> dict:
    detail = kkyi_video_detail()
    for parameter in detail["parameters"]:
        if parameter["param_key"] == "duration":
            parameter["default_value"] = "5"
            parameter["options"] = [
                {"id": "duration-4", "option_name": "4s", "option_value": "4", "sort_order": 1},
                {"id": "duration-5", "option_name": "5s", "option_value": "5", "sort_order": 2},
                {"id": "duration-8", "option_name": "8s", "option_value": "8", "sort_order": 3},
            ]
        if parameter["param_key"] == "ratio":
            parameter["default_value"] = "16:9"
            parameter["options"] = [
                {"id": "ratio-16-9", "option_name": "16:9", "option_value": "16:9", "sort_order": 1},
                {"id": "ratio-9-16", "option_name": "9:16", "option_value": "9:16", "sort_order": 2},
            ]
        if parameter["param_key"] == "resolution":
            parameter["default_value"] = "720p"
            parameter["options"] = [
                {"id": "resolution-720", "option_name": "720p", "option_value": "720p", "sort_order": 1},
                {"id": "resolution-480", "option_name": "480p", "option_value": "480p", "sort_order": 2},
            ]
    return detail


def kkyi_image_detail() -> dict:
    return {
        "id": "10029",
        "display_name": "GPT-Image-2",
        "model_name": "gpt-image-2",
        "model_type": 2,
        "icon": "OpenAI",
        "description": "Image model",
        "input_hint": "Use image parameters",
        "parameters": [
            {"id": "10201", "display_name": "尺寸", "param_key": "size", "widget_type": 3, "is_required": True, "default_value": "auto", "options": []},
            {"id": "10202", "display_name": "质量", "param_key": "quality", "widget_type": 3, "is_required": False, "default_value": "auto", "options": []},
            {"id": "10203", "display_name": "参考图", "param_key": "images", "widget_type": 6, "is_required": False, "default_value": "", "max_count": 4, "options": []},
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


def test_model_list_backfills_catalog_link_for_existing_sub_models() -> None:
    client = TestClient(app)
    client.post("/api/auth/dev-login", json={"externalUserId": "official-1"})

    created = client.post(
        "/api/models",
        headers=csrf_headers(client),
        json={
            "name": "Legacy GPT",
            "vendor": "KKYi",
            "capability": "text",
            "adapter": "text-chat",
            "baseUrl": "https://ai-api.kkidc.com",
            "apiKey": "sk-test",
            "primaryModelName": "gpt-5.4",
        },
    )
    assert created.status_code == 200
    assert created.json()["model"]["subModels"][0]["catalog"] is None

    with SessionLocal() as db:
        upsert_catalog_model_detail(db, kkyi_detail())
        db.commit()

    listed = client.get("/api/models")

    assert listed.status_code == 200
    model = listed.json()["models"][0]
    assert model["subModels"][0]["catalogModelId"] == "10024"
    assert model["subModels"][0]["catalog"]["parameters"][0]["paramKey"] == "attachments"


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


def test_catalog_sync_backfills_existing_video_sub_model_links(monkeypatch) -> None:
    async def fake_fetch_kkyi_catalog_details(*, base_url: str, bearer_token: str, model_type: int) -> list[dict]:
        return [kkyi_video_detail_with_options()]

    monkeypatch.setattr(main_module, "fetch_kkyi_catalog_details", fake_fetch_kkyi_catalog_details)
    client = TestClient(app)
    client.post("/api/auth/dev-login", json={"externalUserId": "official-1"})
    created = client.post(
        "/api/models",
        headers=csrf_headers(client),
        json={
            "name": "Existing KK Seed",
            "vendor": "KKYi",
            "capability": "video",
            "adapter": "video-unified-generic",
            "baseUrl": "https://ai-api.kkidc.com",
            "apiKey": "sk-test",
            "primaryModelName": "kuaikuai-2-flash-pro",
        },
    )
    assert created.status_code == 200
    assert created.json()["model"]["subModels"][0]["catalogModelId"] is None

    response = client.post(
        "/api/catalog/kkyi/sync",
        headers=csrf_headers(client),
        json={"bearerToken": "token-from-request", "modelType": 3},
    )

    assert response.status_code == 200
    with SessionLocal() as db:
        stored = db.query(CatalogModel).filter(CatalogModel.external_id == "10028").one()
        assert stored.input_hint == "Use video parameters"
        linked = db.query(SubModel).filter(SubModel.model_name == "kuaikuai-2-flash-pro").one()
        assert linked.catalog_model_id == stored.id


def test_catalog_video_parameters_are_clamped_before_forwarding(monkeypatch) -> None:
    with SessionLocal() as db:
        upsert_catalog_model_detail(db, kkyi_video_detail_with_options())
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
                "aspect_ratio": "1:2",
                "duration": 15,
                "resolution": "1080p",
                "audio": False,
                "n": 1,
            },
        },
    )

    assert response.status_code == 200
    assert captured["body"] == {
        "model": "kuaikuai-2-flash-pro",
        "prompt": "video test",
        "ratio": "16:9",
        "duration": 5,
        "resolution": "720p",
        "generate_audio": False,
        "quantity": 1,
    }


def test_catalog_video_start_end_frames_use_runninghub_url_fields(monkeypatch) -> None:
    (main_module.LOCAL_UPLOAD_DIR / "first.png").write_bytes(b"fake-first")
    (main_module.LOCAL_UPLOAD_DIR / "last.png").write_bytes(b"fake-last")
    settings = main_module.get_settings()
    monkeypatch.setattr(settings, "frontend_url", "https://studio.cylonai.cn")
    body = main_module.normalize_kkyi_video_body(
        {
            "model": "seedance-2.0-fast-image-to-video",
            "prompt": "video test",
            "video_mode": "first_last_frame",
            "first_frame": "/api/assets/uploads/first.png",
            "last_frame": "/api/assets/uploads/last.png",
        },
        "seedance-2.0-fast-image-to-video",
    )

    assert body["firstFrameUrl"] == "https://studio.cylonai.cn/api/assets/uploads/first.png"
    assert body["lastFrameUrl"] == "https://studio.cylonai.cn/api/assets/uploads/last.png"
    assert "first_frame" not in body
    assert "last_frame" not in body


def test_catalog_video_model_uses_kkyi_generation_path_and_flat_parameters(monkeypatch) -> None:
    with SessionLocal() as db:
        upsert_catalog_model_detail(db, kkyi_video_detail())
        db.commit()

    first_frame = "kk-first-frame.png"
    last_frame = "kk-last-frame.png"
    (main_module.LOCAL_UPLOAD_DIR / first_frame).write_bytes(b"fake-first-frame")
    (main_module.LOCAL_UPLOAD_DIR / last_frame).write_bytes(b"fake-last-frame")
    captured: dict[str, object] = {}

    async def fake_forward_json(method, url, api_key, body=None):
        captured.update({"method": method, "url": url, "body": body})
        return httpx.Response(200, json={"id": "task-1", "status": "queued"}), {"id": "task-1", "status": "queued"}

    settings = main_module.get_settings()
    monkeypatch.setattr(settings, "frontend_url", "https://studio.cylonai.cn")
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
                "video_mode": "first_last_frame",
                "first_frame": f"/api/assets/uploads/{first_frame}",
                "last_frame": f"/api/assets/uploads/{last_frame}",
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
        "video_mode": "first_last_frame",
        "firstFrameUrl": f"https://studio.cylonai.cn/api/assets/uploads/{first_frame}",
        "lastFrameUrl": f"https://studio.cylonai.cn/api/assets/uploads/{last_frame}",
    }


def test_kkyi_video_model_without_catalog_link_uses_generation_path(monkeypatch) -> None:
    upload_name = "kk-veo-reference.jpg"
    (main_module.LOCAL_UPLOAD_DIR / upload_name).write_bytes(b"fake-kk-reference")
    captured: dict[str, object] = {}

    async def fake_forward_json(method, url, api_key, body=None):
        captured.update({"method": method, "url": url, "body": body})
        return httpx.Response(200, json={"id": "task-kk-veo", "status": "queued"}), {"id": "task-kk-veo", "status": "queued"}

    settings = main_module.get_settings()
    monkeypatch.setattr(settings, "frontend_url", "https://studio.cylonai.cn")
    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    client.post("/api/auth/dev-login", json={"externalUserId": "official-1"})
    created = client.post(
        "/api/models",
        headers=csrf_headers(client),
        json={
            "name": "KK Veo",
            "vendor": "KKYi",
            "capability": "video",
            "adapter": "video-unified-generic",
            "baseUrl": "https://ai-api.kkidc.com",
            "apiKey": "sk-test",
            "primaryModelName": "gemini-veo-3.1-generate-preview-8s",
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
                "model": "gemini-veo-3.1-generate-preview-8s",
                "prompt": "reference video",
                "images": [f"/api/assets/uploads/{upload_name}"],
                "video_mode": "reference",
                "aspect_ratio": "16:9",
                "duration": 15,
                "resolution": "720p",
                "audio": True,
                "quantity": 1,
            },
        },
    )

    assert response.status_code == 200
    assert captured["url"] == "https://ai-api.kkidc.com/v1/video/generations"
    assert captured["body"] == {
        "model": "gemini-veo-3.1-generate-preview-8s",
        "prompt": "reference video",
        "ratio": "16:9",
        "duration": 8,
        "resolution": "720p",
        "generate_audio": True,
        "quantity": 1,
        "video_mode": "reference",
        "img_url": [f"https://studio.cylonai.cn/api/assets/uploads/{upload_name}"],
    }


def test_kkyi_video_model_without_catalog_link_queries_generation_detail_path(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_forward_json(method, url, api_key, body=None):
        captured.update({"method": method, "url": url, "body": body})
        return httpx.Response(200, json={"id": "task-kk-veo", "status": "failed", "error": {"message": "failed in worker"}}), {
            "id": "task-kk-veo",
            "status": "failed",
            "error": {"message": "failed in worker"},
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    client.post("/api/auth/dev-login", json={"externalUserId": "official-1"})
    created = client.post(
        "/api/models",
        headers=csrf_headers(client),
        json={
            "name": "KK Veo",
            "vendor": "KKYi",
            "capability": "video",
            "adapter": "video-unified-generic",
            "baseUrl": "https://ai-api.kkidc.com",
            "apiKey": "sk-test",
            "primaryModelName": "gemini-veo-3.1-generate-preview-8s",
        },
    )
    assert created.status_code == 200
    sub_model_id = created.json()["model"]["primarySubModelId"]

    response = client.post(
        "/api/proxy/video/query",
        headers=csrf_headers(client),
        json={"subModelId": sub_model_id, "taskId": "task-kk-veo"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert captured["method"] == "GET"
    assert captured["url"] == "https://ai-api.kkidc.com/v1/video/generations/task-kk-veo"


def test_catalog_image_model_accepts_catalog_images_parameter(monkeypatch) -> None:
    with SessionLocal() as db:
        upsert_catalog_model_detail(db, kkyi_image_detail())
        db.commit()

    captured: dict[str, object] = {}

    async def fake_forward_json(method, url, api_key, body=None):
        captured.update({"method": method, "url": url, "body": body})
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/image.png"}]}), {"data": [{"url": "https://cdn.example.com/image.png"}]}

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    client.post("/api/auth/dev-login", json={"externalUserId": "official-1"})
    created = client.post(
        "/api/models",
        headers=csrf_headers(client),
        json={
            "name": "GPT Image",
            "vendor": "KKYi",
            "capability": "image",
            "adapter": "image-openai",
            "baseUrl": "https://ai-api.kkidc.com",
            "apiKey": "sk-test",
            "primaryModelName": "gpt-image-2",
            "catalogModelId": "10029",
        },
    )
    assert created.status_code == 200
    sub_model_id = created.json()["model"]["primarySubModelId"]

    response = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "requestBody": {
                "prompt": "image test",
                "size": "auto",
                "quality": "auto",
                "images": ["https://cdn.example.com/reference.png"],
                "response_format": "url",
            },
        },
    )

    assert response.status_code == 200
    assert captured["url"] == "https://ai-api.kkidc.com/v1/images/generations"
    assert captured["body"] == {
        "model": "gpt-image-2",
        "prompt": "image test",
        "size": "auto",
        "quality": "auto",
        "image": ["https://cdn.example.com/reference.png"],
        "response_format": "url",
    }


def test_catalog_image_model_expands_local_references_from_images_parameter(monkeypatch) -> None:
    with SessionLocal() as db:
        upsert_catalog_model_detail(db, kkyi_image_detail())
        db.commit()

    upload_name = "catalog-reference.png"
    upload_path = main_module.LOCAL_UPLOAD_DIR / upload_name
    upload_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    captured: dict[str, object] = {}

    async def fail_forward_json(method, url, api_key, body=None):
        raise AssertionError("local image-openai references should use image edits")

    async def fake_forward_multipart(url, api_key, *, data=None, files=None):
        captured.update({"url": url, "data": data, "files": files})
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/image.png"}]}), {"data": [{"url": "https://cdn.example.com/image.png"}]}

    monkeypatch.setattr(main_module, "forward_json", fail_forward_json)
    monkeypatch.setattr(main_module, "forward_multipart", fake_forward_multipart)
    client = TestClient(app)
    client.post("/api/auth/dev-login", json={"externalUserId": "official-1"})
    created = client.post(
        "/api/models",
        headers=csrf_headers(client),
        json={
            "name": "GPT Image",
            "vendor": "KKYi",
            "capability": "image",
            "adapter": "image-openai",
            "baseUrl": "https://ai-api.kkidc.com",
            "apiKey": "sk-test",
            "primaryModelName": "gpt-image-2",
            "catalogModelId": "10029",
        },
    )
    assert created.status_code == 200
    sub_model_id = created.json()["model"]["primarySubModelId"]

    response = client.post(
        "/api/proxy/image",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "requestBody": {
                "prompt": "image test",
                "images": [f"/api/assets/uploads/{upload_name}"],
                "response_format": "url",
            },
        },
    )

    assert response.status_code == 200
    assert captured["url"] == "https://ai-api.kkidc.com/v1/images/edits"
    assert captured["files"] == [("image", ("catalog-reference.png", b"\x89PNG\r\n\x1a\n", "image/png"))]


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
