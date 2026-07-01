from __future__ import annotations

import json
import os
import sys
import tempfile
import asyncio
from io import BytesIO

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

db_path = os.path.join(tempfile.gettempdir(), "genstudio-prompt-library-test.sqlite3")
if os.path.exists(db_path):
    os.remove(db_path)

os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["GENSTUDIO_SECRET_KEY"] = "test-secret"

from app.auth import get_current_user, require_csrf
from app.database import Base, get_db
from app.db_models import ApiKey, ModelGroup, PromptSceneTemplate, SubModel, User
from app.main import app
from app.security import encrypt_secret


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def admin_user(db: Session) -> User:
    user = User(external_user_id="admin", email="cage_ben@sina.com", nickname="admin")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def regular_user(db: Session) -> User:
    user = User(external_user_id="creator", email="creator@example.com", nickname="creator")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def client(db: Session, admin_user: User) -> TestClient:
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[require_csrf] = lambda: None
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_text_model(
    db: Session,
    user: User,
    *,
    model_name: str,
    is_public: bool = False,
    base_url: str = "https://token.example.com",
) -> tuple[ModelGroup, SubModel]:
    api_key = ApiKey(
        user_id=user.id,
        name=f"key-{model_name}",
        base_url=base_url,
        api_key_ciphertext=encrypt_secret("sk-test"),
        status="active",
    )
    db.add(api_key)
    db.flush()
    group = ModelGroup(
        user_id=user.id,
        api_key_id=api_key.id,
        name=f"{model_name} model",
        vendor="Test",
        capability="text",
        adapter="text-chat",
        primary_sub_model_id="",
        is_public=is_public,
    )
    db.add(group)
    db.flush()
    sub_model = SubModel(
        model_group_id=group.id,
        api_key_id=api_key.id,
        model_name=model_name,
        display_name=model_name,
        capability="text",
        adapter="text-chat",
        is_primary=True,
        status="active",
    )
    db.add(sub_model)
    db.flush()
    group.primary_sub_model_id = sub_model.id
    db.commit()
    db.refresh(group)
    db.refresh(sub_model)
    return group, sub_model


def sample_yuque_index() -> dict:
    return {
        "exportedAt": "2026-06-30T10:16:50.808Z",
        "source": "yuque markdown export",
        "documentCount": 1,
        "prompts": [
            {
                "categoryId": "people-photo-avatar",
                "documentTitle": "1_人物/写真/头像",
                "documentUrl": "https://example.com/doc",
                "section": "人像写真",
                "category": "人物 / 写真 / 头像",
                "subcategory": "人像写真",
                "tags": ["人像写真", "电影感"],
                "source": "nanobanana-trending-prompts",
                "originalNo": "#2",
                "title": "超写实电影感女性明暗光影肖像",
                "imageUrl": "https://cdn.example.com/a.jpg",
                "model": "GPT Image 2",
                "likes": 515,
                "views": 23900,
                "promptText": "超写实电影质感，创作一张 4K 近景肖像。",
            },
            {
                "categoryId": "product-ecommerce-brand-ad",
                "documentTitle": "2_产品/电商/品牌广告",
                "section": "产品海报",
                "category": "产品 / 电商 / 品牌广告",
                "subcategory": "产品海报",
                "tags": ["产品海报", "电商"],
                "source": "awesome-gpt-image-2",
                "originalNo": "#8",
                "title": "高级饮料产品海报",
                "imageUrl": "https://cdn.example.com/b.jpg",
                "model": "GPT Image 2",
                "likes": 40,
                "views": 3000,
                "promptText": "生成一张高端饮料电商海报，突出包装和清爽光影。",
            },
        ],
    }


def test_admin_imports_yuque_prompt_library_and_lists_templates(client: TestClient) -> None:
    response = client.post("/api/admin/prompt-library/import", json={"index": sample_yuque_index(), "replace": True})

    assert response.status_code == 200
    assert response.json()["summary"] == {"imported": 2, "updated": 0, "disabled": 0, "total": 2}

    listed = client.get("/api/admin/prompt-library?capability=image&search=电影感")
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["total"] == 1
    assert payload["templates"][0]["title"] == "超写实电影感女性明暗光影肖像"
    assert payload["templates"][0]["tags"] == ["人像写真", "电影感"]
    assert payload["templates"][0]["enabled"] is True
    assert payload["templates"][0]["weight"] == 515


def test_admin_can_edit_batch_disable_and_rank_scene_templates(client: TestClient) -> None:
    client.post("/api/admin/prompt-library/import", json={"index": sample_yuque_index(), "replace": True})
    first_id = client.get("/api/admin/prompt-library?search=电影感").json()["templates"][0]["id"]

    edited = client.put(
        f"/api/admin/prompt-library/{first_id}",
        json={"title": "电影感头像模板", "tags": ["头像", "强光影"], "weight": 900, "enabled": True},
    )
    assert edited.status_code == 200
    assert edited.json()["template"]["title"] == "电影感头像模板"
    assert edited.json()["template"]["weight"] == 900

    batch = client.post("/api/admin/prompt-library/batch", json={"templateIds": [first_id], "enabled": False})
    assert batch.status_code == 200
    assert batch.json()["updated"] == 1

    listed = client.get("/api/admin/prompt-library?enabled=false")
    assert listed.status_code == 200
    assert listed.json()["templates"][0]["id"] == first_id
    assert listed.json()["templates"][0]["enabled"] is False


def test_image_prompt_recommendations_use_private_gpt55_before_public(
    db: Session,
    regular_user: User,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_text_model(db, admin_user, model_name="gpt-5.5", is_public=True, base_url="https://public.example.com")
    private_group, _private_sub = make_text_model(
        db,
        regular_user,
        model_name="gpt-5.5",
        is_public=False,
        base_url="https://private.example.com",
    )

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: regular_user
    app.dependency_overrides[require_csrf] = lambda: None

    with TestClient(app) as test_client:
        import_response = test_client.post("/api/admin/prompt-library/import", json={"index": sample_yuque_index(), "replace": True})
        assert import_response.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: admin_user
    with TestClient(app) as admin_client:
        assert admin_client.post("/api/admin/prompt-library/import", json={"index": sample_yuque_index(), "replace": True}).status_code == 200

    captured: dict[str, object] = {}

    async def fake_forward_json(method: str, url: str, api_key: str, body=None, **_kwargs):
        captured["url"] = url
        captured["body"] = body
        response_payload = {"choices": [{"message": {"content": json.dumps({
            "recommendations": [
                {
                    "templateId": db.query(PromptSceneTemplate).filter(PromptSceneTemplate.title.like("%电影感%")).first().id,
                    "label": "电影感头像",
                    "reason": "参考图是人像近景",
                }
            ]
        }, ensure_ascii=False)}}]}
        return httpx.Response(200, json=response_payload), response_payload

    monkeypatch.setattr("app.main.forward_json", fake_forward_json)
    app.dependency_overrides[get_current_user] = lambda: regular_user
    with TestClient(app) as user_client:
        response = user_client.post(
            "/api/prompt-library/image-recommendations",
            json={"imageUrl": "https://cdn.example.com/reference.png", "limit": 8},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["url"] == "https://private.example.com/v1/chat/completions"
    assert response.json()["modelGroupId"] == private_group.id
    assert "raw" not in response.json()
    assert response.json()["recommendations"][0]["label"] == "电影感头像"
    assert response.json()["recommendations"][0]["promptText"].startswith("超写实电影质感")


def test_image_prompt_recommendations_return_gpt55_filled_prompt_text(
    db: Session,
    regular_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_text_model(db, regular_user, model_name="gpt-5.5", is_public=False)
    template = PromptSceneTemplate(
        external_id="yuque:filled-prompt-test",
        title="Instagram 相框时尚人像",
        prompt_text=(
            "[Character Description and expression]的超写实时尚上半身人像，身着"
            "[Detailed Outfit Description]。主体被置于图像中央的白色Instagram风格相框内。"
            "[Soft Background Color matching the outfit]"
        ),
        category_id="people-photo-avatar",
        category="人物 / 写真 / 头像",
        subcategory="人像写真",
        tags_json='["人像写真"]',
        enabled=True,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    def override_db():
        yield db

    async def fake_forward_json(method: str, url: str, api_key: str, body=None, **_kwargs):
        content = {
            "recommendations": [
                {
                    "templateId": template.id,
                    "label": "相框时尚人像",
                    "reason": "上传图是一位穿蓝色西装的女性上半身肖像",
                    "promptText": (
                        "一位神情自信、微微侧脸凝视镜头的年轻女性的超写实时尚上半身人像，"
                        "身着剪裁利落的蓝色西装外套和白色丝质内搭。主体被置于图像中央的白色Instagram风格相框内。"
                        "构图与留白：白色边框完美居中，四周保留均衡的留白区域，柔和雾蓝色背景与服装相呼应。"
                    ),
                }
            ]
        }
        response_payload = {"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]}
        return httpx.Response(200, json=response_payload), response_payload

    monkeypatch.setattr("app.main.forward_json", fake_forward_json)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: regular_user
    app.dependency_overrides[require_csrf] = lambda: None

    with TestClient(app) as user_client:
        response = user_client.post(
            "/api/prompt-library/image-recommendations",
            json={"imageUrl": "https://cdn.example.com/reference.png"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    prompt_text = response.json()["recommendations"][0]["promptText"]
    assert "蓝色西装外套" in prompt_text
    assert "[Character Description" not in prompt_text
    assert "[Detailed Outfit" not in prompt_text
    assert "[Soft Background Color" not in prompt_text


def test_image_prompt_recommendations_keeps_remote_url_for_vision_model(
    db: Session,
    regular_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_text_model(db, regular_user, model_name="gpt-5.5", is_public=False)
    template = PromptSceneTemplate(
        external_id="yuque:local-reference-test",
        title="电影感头像模板",
        prompt_text="超写实电影质感",
        category_id="people-photo-avatar",
        category="人物 / 写真 / 头像",
        subcategory="人像写真",
        tags_json='["人像写真"]',
        enabled=True,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    def override_db():
        yield db

    captured: dict[str, object] = {}

    async def fake_forward_json(method: str, url: str, api_key: str, body=None, **_kwargs):
        captured["body"] = body
        response_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"recommendations": [{"templateId": template.id, "label": "电影感头像"}]},
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
        return httpx.Response(200, json=response_payload), response_payload

    monkeypatch.setattr("app.main.forward_json", fake_forward_json)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: regular_user
    app.dependency_overrides[require_csrf] = lambda: None

    with TestClient(app) as user_client:
        response = user_client.post(
            "/api/prompt-library/image-recommendations",
            json={"imageUrl": "https://studio.example.com/api/assets/uploads/reference.png"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    user_content = captured["body"]["messages"][1]["content"]
    assert user_content[1]["image_url"]["url"] == "https://studio.example.com/api/assets/uploads/reference.png"


def test_image_prompt_recommendations_embeds_local_upload_as_data_url_for_vision_model(
    db: Session,
    regular_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_text_model(db, regular_user, model_name="gpt-5.5", is_public=False)
    template = PromptSceneTemplate(
        external_id="yuque:local-reference-data-url-test",
        title="电影感头像模板",
        prompt_text="生成电影感头像",
        category_id="people-photo-avatar",
        category="人物 / 写真 / 头像",
        subcategory="人像写真",
        tags_json='["人像写真"]',
        enabled=True,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    def override_db():
        yield db

    captured: dict[str, object] = {}

    async def fake_forward_json(method: str, url: str, api_key: str, body=None, **_kwargs):
        captured["body"] = body
        response_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"recommendations": [{"templateId": template.id, "label": "电影感头像"}]},
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
        return httpx.Response(200, json=response_payload), response_payload

    def fake_local_asset_data_url(value: str) -> str:
        assert value == "/api/assets/uploads/reference.png"
        return "data:image/png;base64,cmVmZXJlbmNl"

    monkeypatch.setattr("app.main.forward_json", fake_forward_json)
    monkeypatch.setattr("app.main.local_asset_data_url", fake_local_asset_data_url)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: regular_user
    app.dependency_overrides[require_csrf] = lambda: None

    with TestClient(app) as user_client:
        response = user_client.post(
            "/api/prompt-library/image-recommendations",
            json={"imageUrl": "/api/assets/uploads/reference.png"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    user_content = captured["body"]["messages"][1]["content"]
    assert user_content[1]["image_url"]["url"] == "data:image/png;base64,cmVmZXJlbmNl"


def test_image_prompt_recommendations_return_empty_without_gpt55(
    db: Session,
    regular_user: User,
) -> None:
    db.add(
        PromptSceneTemplate(
            external_id="yuque:test",
            title="电影感头像模板",
            prompt_text="超写实电影质感",
            category_id="people-photo-avatar",
            category="人物 / 写真 / 头像",
            subcategory="人像写真",
            tags_json='["人像写真"]',
            enabled=True,
        )
    )
    db.commit()
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: regular_user
    app.dependency_overrides[require_csrf] = lambda: None

    with TestClient(app) as user_client:
        response = user_client.post(
            "/api/prompt-library/image-recommendations",
            json={"imageUrl": "https://cdn.example.com/reference.png"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["recommendations"] == []
    assert response.json()["reason"] == "gpt55_not_configured"


def test_image_prompt_recommendations_reject_invalid_limit(
    db: Session,
    regular_user: User,
) -> None:
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: regular_user
    app.dependency_overrides[require_csrf] = lambda: None

    with TestClient(app) as user_client:
        response = user_client.post(
            "/api/prompt-library/image-recommendations",
            json={"imageUrl": "https://cdn.example.com/reference.png", "limit": "many"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "推荐数量必须是整数。"


def test_image_prompt_recommendations_do_not_use_non_gpt55_text_model(
    db: Session,
    regular_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_text_model(db, regular_user, model_name="gpt-4.1", base_url="https://regular.example.com")
    db.add(
        PromptSceneTemplate(
            external_id="yuque:test",
            title="电影感头像模板",
            prompt_text="超写实电影质感",
            category_id="people-photo-avatar",
            category="人物 / 写真 / 头像",
            subcategory="人像写真",
            tags_json='["人像写真"]',
            enabled=True,
        )
    )
    db.commit()

    def override_db():
        yield db

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("non-gpt-5.5 model should not be called for image recommendations")

    monkeypatch.setattr("app.main.forward_json", fail_if_called)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: regular_user
    app.dependency_overrides[require_csrf] = lambda: None

    with TestClient(app) as user_client:
        response = user_client.post(
            "/api/prompt-library/image-recommendations",
            json={"imageUrl": "https://cdn.example.com/reference.png"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["recommendations"] == []
    assert response.json()["reason"] == "gpt55_not_configured"


def test_image_prompt_recommendations_use_public_gpt55_when_private_text_is_not_gpt55(
    db: Session,
    regular_user: User,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_text_model(db, regular_user, model_name="gpt-4.1", base_url="https://regular.example.com")
    public_group, _public_sub = make_text_model(
        db,
        admin_user,
        model_name="gpt 5.5",
        is_public=True,
        base_url="https://public55.example.com",
    )
    template = PromptSceneTemplate(
        external_id="yuque:test-public55",
        title="电影感头像模板",
        prompt_text="超写实电影质感",
        category_id="people-photo-avatar",
        category="人物 / 写真 / 头像",
        subcategory="人像写真",
        tags_json='["人像写真"]',
        enabled=True,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    def override_db():
        yield db

    captured: dict[str, object] = {}

    async def fake_forward_json(method: str, url: str, api_key: str, body=None, **_kwargs):
        captured["url"] = url
        response_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"recommendations": [{"templateId": template.id, "label": "电影感头像"}]},
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
        return httpx.Response(200, json=response_payload), response_payload

    monkeypatch.setattr("app.main.forward_json", fake_forward_json)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: regular_user
    app.dependency_overrides[require_csrf] = lambda: None

    with TestClient(app) as user_client:
        response = user_client.post(
            "/api/prompt-library/image-recommendations",
            json={"imageUrl": "https://cdn.example.com/reference.png"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["url"] == "https://public55.example.com/v1/chat/completions"
    assert response.json()["modelGroupId"] == public_group.id
    assert response.json()["recommendations"][0]["id"] == template.id


def test_prompt_library_event_records_click_count(
    db: Session,
    regular_user: User,
    admin_user: User,
) -> None:
    template = PromptSceneTemplate(
        external_id="yuque:click-test",
        title="电影感头像模板",
        prompt_text="超写实电影质感",
        category_id="people-photo-avatar",
        category="人物 / 写真 / 头像",
        subcategory="人像写真",
        tags_json='["人像写真"]',
        enabled=True,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: regular_user
    app.dependency_overrides[require_csrf] = lambda: None

    with TestClient(app) as user_client:
        response = user_client.post(
            "/api/prompt-library/events",
            json={
                "templateId": template.id,
                "eventType": "click",
                "imageUrl": "https://cdn.example.com/reference.png",
            },
        )

    assert response.status_code == 200
    assert response.json()["template"]["clickCount"] == 1
    assert response.json()["template"]["useCount"] == 0

    app.dependency_overrides[get_current_user] = lambda: admin_user
    with TestClient(app) as admin_client:
        listed = admin_client.get("/api/admin/prompt-library?search=电影感")

    app.dependency_overrides.clear()

    assert listed.status_code == 200
    assert listed.json()["templates"][0]["clickCount"] == 1


def test_import_prompt_library_script_parses_esm_index() -> None:
    from scripts.import_prompt_library import parse_yuque_index_source

    payload = parse_yuque_index_source(
        'export const yuquePromptFullIndex = {"prompts":[{"title":"电影感","promptText":"生成头像"}]}; export default yuquePromptFullIndex;'
    )

    assert payload == {"prompts": [{"title": "电影感", "promptText": "生成头像"}]}


def test_image_generation_verifier_plan_covers_batches_sizes_and_prompt_templates() -> None:
    from scripts.verify_image_generation_100 import build_generation_plan

    prompts = [
        {"id": f"pst_{index}", "title": f"模板 {index}", "promptText": f"生成第 {index} 张测试图"}
        for index in range(1, 121)
    ]

    plan = build_generation_plan(prompts, target_images=100)

    assert sum(item["count"] for item in plan) == 100
    assert {item["count"] for item in plan}.issuperset({1, 2, 4})
    assert any(item["enable4k"] for item in plan)
    assert {"1024x1024", "1536x1024", "1024x1536"}.issubset({item["size"] for item in plan if item["size"]})
    assert {"1:1", "16:9", "9:16"}.issubset({item["ratio"] for item in plan if item["ratio"]})
    assert len({item["templateId"] for item in plan}) >= 25


def test_image_generation_verifier_sanitizes_concatenated_prompt_records() -> None:
    from scripts.verify_image_generation_100 import build_generation_plan

    dirty_prompt = '{"scene":"cinematic portrait"}" }, { "id": "next", "title": "leaked", "prompt_zh": "do not send" }'

    plan = build_generation_plan(
        [{"id": "pst_dirty", "title": "Dirty prompt", "promptText": dirty_prompt}],
        target_images=1,
    )

    assert plan[0]["prompt"] == '{"scene":"cinematic portrait"}'
    assert "leaked" not in plan[0]["prompt"]
    assert "do not send" not in plan[0]["prompt"]


def test_image_generation_verifier_can_build_single_image_non_4k_top_up_plan() -> None:
    from scripts.verify_image_generation_100 import build_generation_plan

    prompts = [
        {"id": f"pst_{index}", "title": f"Template {index}", "promptText": f"Generate image {index}"}
        for index in range(1, 121)
    ]

    plan = build_generation_plan(prompts, target_images=100, single_image_only=True, enable_4k_every=0)

    assert len(plan) == 100
    assert sum(item["count"] for item in plan) == 100
    assert {item["count"] for item in plan} == {1}
    assert not any(item["enable4k"] for item in plan)
    assert {"1024x1024", "1536x1024", "1024x1536"}.issubset({item["size"] for item in plan if item["size"]})


def test_image_generation_verifier_can_write_json_file(tmp_path) -> None:
    from scripts.verify_image_generation_100 import write_json_file

    output = tmp_path / "plan.json"

    write_json_file(output, {"requestedImages": 1, "plan": [{"prompt": "cinematic portrait"}]})

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["requestedImages"] == 1
    assert payload["plan"][0]["prompt"] == "cinematic portrait"


def test_image_generation_verifier_polls_local_batch_image_tasks() -> None:
    from scripts.verify_image_generation_100 import run_plan

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, dict | None]] = []
            self.query_count = 0

        async def request(self, method: str, path: str, json: dict | None = None) -> FakeResponse:
            self.calls.append((method, path, json))
            if path == "/api/proxy/image":
                return FakeResponse(
                    {
                        "images": [],
                        "taskId": "local-image-task-1",
                        "status": "processing",
                        "conversation": {"id": "conv_1"},
                    }
                )
            self.query_count += 1
            if self.query_count == 1:
                return FakeResponse({"images": [], "taskId": "local-image-task-1", "status": "processing"})
            return FakeResponse(
                {
                    "images": [{"src": "https://cdn.example.com/1.png"}, {"src": "https://cdn.example.com/2.png"}],
                    "taskId": "local-image-task-1",
                    "status": "completed",
                }
            )

    client = FakeClient()

    summary = asyncio.run(
        run_plan(
            client,
            "sub_image",
            [{"index": 1, "templateId": "pst_1", "prompt": "batch", "count": 2, "size": "1024x1024"}],
            poll_interval_seconds=0,
            poll_attempts=3,
        )
    )

    assert summary["generatedImages"] == 2
    assert summary["results"][0]["status"] == "completed"
    assert [call[1] for call in client.calls] == ["/api/proxy/image", "/api/proxy/image/query", "/api/proxy/image/query"]
    assert client.calls[1][2] == {
        "subModelId": "sub_image",
        "taskId": "local-image-task-1",
        "conversationId": "conv_1",
    }


def test_image_generation_verifier_resumes_from_existing_result_file(tmp_path) -> None:
    from scripts.verify_image_generation_100 import run_plan

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class FakeClient:
        def __init__(self) -> None:
            self.requested_prompts: list[str] = []

        async def request(self, method: str, path: str, json: dict | None = None) -> FakeResponse:
            self.requested_prompts.append(str((json or {}).get("requestBody", {}).get("prompt") or ""))
            return FakeResponse({"images": [{"src": "https://cdn.example.com/2.png"}]})

    output = tmp_path / "results.json"
    output.write_text(
        json.dumps(
            {
                "requestedImages": 2,
                "generatedImages": 1,
                "results": [
                    {
                        "index": 1,
                        "templateId": "pst_1",
                        "requested": 1,
                        "generated": 1,
                        "status": "success",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    client = FakeClient()

    summary = asyncio.run(
        run_plan(
            client,
            "sub_image",
            [
                {"index": 1, "templateId": "pst_1", "prompt": "already done", "count": 1, "size": "1024x1024"},
                {"index": 2, "templateId": "pst_2", "prompt": "run me", "count": 1, "size": "1024x1024"},
            ],
            output_path=output,
            resume=True,
            poll_interval_seconds=0,
        )
    )

    assert client.requested_prompts == ["run me"]
    assert summary["generatedImages"] == 2
    assert [item["index"] for item in summary["results"]] == [1, 2]


def test_image_generation_verifier_limits_attempts_per_run(tmp_path) -> None:
    from scripts.verify_image_generation_100 import run_plan

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class FakeClient:
        def __init__(self) -> None:
            self.requested_prompts: list[str] = []

        async def request(self, method: str, path: str, json: dict | None = None) -> FakeResponse:
            self.requested_prompts.append(str((json or {}).get("requestBody", {}).get("prompt") or ""))
            return FakeResponse({"images": [{"src": "https://cdn.example.com/1.png"}]})

    client = FakeClient()

    summary = asyncio.run(
        run_plan(
            client,
            "sub_image",
            [
                {"index": 1, "templateId": "pst_1", "prompt": "first", "count": 1, "size": "1024x1024"},
                {"index": 2, "templateId": "pst_2", "prompt": "second", "count": 1, "size": "1024x1024"},
                {"index": 3, "templateId": "pst_3", "prompt": "third", "count": 1, "size": "1024x1024"},
            ],
            output_path=tmp_path / "results.json",
            max_attempts=2,
        )
    )

    assert client.requested_prompts == ["first", "second"]
    assert summary["generatedImages"] == 2
    assert [item["index"] for item in summary["results"]] == [1, 2]


def test_image_generation_verifier_limits_elapsed_seconds(tmp_path) -> None:
    from scripts.verify_image_generation_100 import run_plan

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class SlowFakeClient:
        def __init__(self) -> None:
            self.requested_prompts: list[str] = []

        async def request(self, method: str, path: str, json: dict | None = None) -> FakeResponse:
            self.requested_prompts.append(str((json or {}).get("requestBody", {}).get("prompt") or ""))
            await asyncio.sleep(0.02)
            return FakeResponse({"images": [{"src": "https://cdn.example.com/1.png"}]})

    client = SlowFakeClient()

    summary = asyncio.run(
        run_plan(
            client,
            "sub_image",
            [
                {"index": 1, "templateId": "pst_1", "prompt": "first", "count": 1, "size": "1024x1024"},
                {"index": 2, "templateId": "pst_2", "prompt": "second", "count": 1, "size": "1024x1024"},
                {"index": 3, "templateId": "pst_3", "prompt": "third", "count": 1, "size": "1024x1024"},
            ],
            output_path=tmp_path / "results.json",
            max_seconds=0.01,
        )
    )

    assert client.requested_prompts == ["first"]
    assert summary["generatedImages"] == 1
    assert [item["index"] for item in summary["results"]] == [1]


def test_image_generation_verifier_records_exception_type_on_errors() -> None:
    from scripts.verify_image_generation_100 import run_plan

    class FailingClient:
        async def request(self, method: str, path: str, json: dict | None = None):
            raise TimeoutError()

    summary = asyncio.run(
        run_plan(
            FailingClient(),
            "sub_image",
            [{"index": 1, "templateId": "pst_1", "prompt": "timeout", "count": 1, "size": "1024x1024"}],
            poll_interval_seconds=0,
        )
    )

    assert summary["generatedImages"] == 0
    assert summary["results"][0]["status"] == "error"
    assert summary["results"][0]["errorType"] == "TimeoutError"
    assert summary["results"][0]["error"]


def test_image_generation_verifier_records_http_error_response_detail_on_errors() -> None:
    from scripts.verify_image_generation_100 import run_plan

    class FailingResponse:
        def raise_for_status(self) -> None:
            request = httpx.Request("POST", "http://testserver/api/proxy/image")
            response = httpx.Response(
                400,
                json={"detail": {"message": "prompt rejected"}},
                request=request,
            )
            raise httpx.HTTPStatusError("bad request", request=request, response=response)

        def json(self) -> dict:
            return {}

    class FailingClient:
        async def request(self, method: str, path: str, json: dict | None = None):
            return FailingResponse()

    summary = asyncio.run(
        run_plan(
            FailingClient(),
            "sub_image",
            [{"index": 1, "templateId": "pst_1", "prompt": "bad", "count": 1, "size": "1024x1024"}],
            poll_interval_seconds=0,
        )
    )

    assert summary["generatedImages"] == 0
    assert summary["results"][0]["status"] == "error"
    assert summary["results"][0]["errorType"] == "HTTPStatusError"
    assert summary["results"][0]["responseStatus"] == 400
    assert summary["results"][0]["responseDetail"] == {"detail": {"message": "prompt rejected"}}


def test_image_generation_verifier_builds_http_timeout_from_seconds() -> None:
    from scripts.verify_image_generation_100 import build_http_timeout

    timeout = build_http_timeout(360)

    assert timeout.connect == 30
    assert timeout.read == 360
    assert timeout.write == 360
    assert timeout.pool == 30


def test_image_generation_verifier_resume_keeps_partial_successes(tmp_path) -> None:
    from scripts.verify_image_generation_100 import run_plan

    class FakeClient:
        async def request(self, method: str, path: str, json: dict | None = None):
            raise AssertionError("partial successes should not be re-submitted during resume")

    output = tmp_path / "results.json"
    output.write_text(
        json.dumps(
            {
                "requestedImages": 4,
                "generatedImages": 1,
                "results": [
                    {
                        "index": 1,
                        "templateId": "pst_1",
                        "requested": 4,
                        "generated": 1,
                        "status": "processing",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = asyncio.run(
        run_plan(
            FakeClient(),
            "sub_image",
            [{"index": 1, "templateId": "pst_1", "prompt": "partial", "count": 4, "size": "1024x1024"}],
            output_path=output,
            resume=True,
            poll_interval_seconds=0,
        )
    )

    assert summary["generatedImages"] == 1
    assert summary["results"][0]["generated"] == 1


def test_image_generation_verifier_can_run_with_direct_config() -> None:
    from scripts.verify_image_generation_100 import run_plan

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class FakeClient:
        def __init__(self) -> None:
            self.payloads: list[dict] = []

        async def request(self, method: str, path: str, json: dict | None = None) -> FakeResponse:
            self.payloads.append(json or {})
            return FakeResponse({"images": [{"src": "https://cdn.example.com/1.png"}]})

    client = FakeClient()

    summary = asyncio.run(
        run_plan(
            client,
            "unused_sub_model",
            [{"index": 1, "templateId": "pst_1", "prompt": "direct", "count": 1, "size": "1024x1024"}],
            direct_config={"baseUrl": "https://token.example.com/", "apiKey": "sk-test"},
            poll_interval_seconds=0,
        )
    )

    assert summary["generatedImages"] == 1
    assert client.payloads[0]["config"] == {"baseUrl": "https://token.example.com/", "apiKey": "sk-test"}
    assert client.payloads[0]["adapter"] == "image-openai"
    assert client.payloads[0]["model"] == "gpt-image-2"
    assert "subModelId" not in client.payloads[0]


def test_image_generation_verifier_writes_utf8_when_stdout_is_gbk() -> None:
    from scripts.verify_image_generation_100 import write_json_stdout

    class GbkStream:
        def __init__(self) -> None:
            self.buffer = BytesIO()

        def write(self, text: str) -> int:
            text.encode("gbk")
            return len(text)

    stream = GbkStream()
    write_json_stdout({"text": "电影感 • 头像"}, stream=stream)

    assert "电影感 • 头像" in stream.buffer.getvalue().decode("utf-8")
