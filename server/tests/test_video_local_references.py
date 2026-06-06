from __future__ import annotations

import os
import sys
import tempfile

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

db_path = os.path.join(tempfile.gettempdir(), "genstudio-video-reference-test.sqlite3")
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


def csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrfToken"]}


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


def create_video_model(client: TestClient) -> str:
    response = client.post(
        "/api/models",
        headers=csrf_headers(client),
        json={
            "name": "Seedance",
            "vendor": "Test",
            "capability": "video",
            "adapter": "video-seedance",
            "baseUrl": "https://token.example.com",
            "apiKey": "sk-test",
            "primaryModelName": "doubao-seedance-2-0-260128",
        },
    )
    assert response.status_code == 200
    return response.json()["model"]["primarySubModelId"]


def test_seedance_video_expands_local_frame_references_before_forwarding(monkeypatch) -> None:
    upload_name = "seedance-first.jpg"
    (main_module.LOCAL_UPLOAD_DIR / upload_name).write_bytes(b"fake-video-frame")
    seen: dict[str, object] = {}

    async def fake_forward_json(method, url, api_key, body=None):
        seen["body"] = body
        return httpx.Response(200, json={"id": "task-local-frame", "status": "submitted"}), {
            "id": "task-local-frame",
            "status": "submitted",
        }

    monkeypatch.setattr(main_module, "forward_json", fake_forward_json)
    client = TestClient(app)
    login(client, "alice")
    sub_model_id = create_video_model(client)

    response = client.post(
        "/api/proxy/video/create",
        headers=csrf_headers(client),
        json={
            "subModelId": sub_model_id,
            "requestBody": {
                "model": "doubao-seedance-2-0-260128",
                "content": [
                    {"type": "text", "text": "Seedance local first frame"},
                    {
                        "type": "image_url",
                        "role": "first_frame",
                        "image_url": {"url": f"/api/assets/uploads/{upload_name}"},
                    },
                ],
                "metadata": {"duration": 5, "resolution": "720p", "ratio": "16:9"},
            },
        },
    )

    assert response.status_code == 200
    content = seen["body"]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert "/api/assets/uploads/" not in content[1]["image_url"]["url"]
