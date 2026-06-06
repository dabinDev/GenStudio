from __future__ import annotations

import base64
import binascii
import copy
from pathlib import Path
import time
from uuid import uuid4
from typing import Any
from urllib.parse import quote, urlparse

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import (
    authenticate_local_user,
    clear_session,
    create_session,
    exchange_official_code,
    get_current_user,
    get_optional_current_user,
    issue_csrf_token,
    register_local_user,
    require_csrf,
    serialize_user,
    update_user_profile,
    upsert_user,
)
from app.config import Settings, get_settings
from app.conversation_service import (
    add_asset,
    add_message,
    create_conversation,
    ensure_conversation,
    get_conversation,
    list_conversations,
    reload_conversation,
    serialize_conversation,
    serialize_message,
)
from app.database import get_db, init_db
from app.db_models import CallLog, User
from app.model_service import (
    create_model_group,
    delete_model_group,
    elapsed_ms,
    get_model_group,
    get_sub_model_for_user,
    list_api_keys,
    list_model_groups,
    record_call_log,
    serialize_api_key,
    serialize_call_log,
    serialize_model,
    set_primary_sub_model,
    sync_models_from_raw,
    update_model_group,
)
from app.proxy_utils import (
    build_test_body,
    coerce_json_object,
    forward_json,
    parse_model_ids,
    pick_task_id,
    pick_error_message,
    pick_text_content,
    pick_video_query_payload,
    resolve_test_path,
    resolve_url,
    resolve_video_create_path,
    resolve_video_query_path,
    upstream_error,
    validate_config,
    filter_model_ids_for_capability,
)
from app.rate_limit import InMemoryRateLimiter, check_rate_limit
from app.schemas import (
    ConversationCreate,
    DevLoginRequest,
    LoginRequest,
    ModelCreate,
    ModelUpdate,
    ProfileUpdateRequest,
    RegisterRequest,
)
from app.security import decrypt_secret
from app.storage import create_presigned_put_url

app = FastAPI(title="GenStudio Server")
GENERATED_ASSET_DIR = Path(__file__).resolve().parents[2] / "generated_assets"
GENERATED_ASSET_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_ROUTES = {"auth", "auth-error", "text", "images", "videos", "settings", "profile"}
rate_limiter = InMemoryRateLimiter()


def safe_frontend_hash_path(value: str, fallback: str = "#/settings") -> str:
    candidate = (value or "").strip()
    if not candidate:
        return fallback
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc or candidate.startswith("//"):
        return fallback
    if candidate.startswith("/#/"):
        candidate = candidate[1:]
    elif candidate.startswith("#/"):
        candidate = candidate
    elif candidate.startswith("/"):
        candidate = f"#{candidate}"
    else:
        candidate = f"#/{candidate.lstrip('#/')}"
    route = candidate.removeprefix("#/").split("?", 1)[0].strip("/")
    if route not in FRONTEND_ROUTES:
        return fallback
    return candidate


def frontend_redirect_url(settings: Settings, hash_path: str = "#/settings") -> str:
    return f"{settings.frontend_url.rstrip('/')}/{safe_frontend_hash_path(hash_path)}"


def auth_error_redirect_url(settings: Settings, message: str) -> str:
    safe_message = quote(message[:160] or "授权登录失败，请返回官网重新进入。")
    return frontend_redirect_url(settings, f"#/auth-error?message={safe_message}")


def extract_video_prompt(request_body: dict[str, Any]) -> str:
    prompt = request_body.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        return prompt
    content = request_body.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                return item["text"]
    if isinstance(content, str):
        return content
    return ""


def persist_generated_image_from_b64(value: str) -> str:
    try:
        image_bytes = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return f"data:image/png;base64,{value}"
    file_name = f"{uuid4().hex}.png"
    (GENERATED_ASSET_DIR / file_name).write_bytes(image_bytes)
    return f"/api/assets/generated/{file_name}"


def extract_images_from_response(raw: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    safe_raw = copy.deepcopy(raw)
    images: list[dict[str, Any]] = []
    data = safe_raw.get("data") if isinstance(safe_raw.get("data"), list) else []
    for item in data:
        if not isinstance(item, dict):
            continue
        src = item.get("url") if isinstance(item.get("url"), str) else ""
        if not src and isinstance(item.get("b64_json"), str):
            src = persist_generated_image_from_b64(item["b64_json"])
            item.pop("b64_json", None)
            item["url"] = src
            item["source"] = "b64_json_saved"
        if src:
            images.append(
                {
                    "src": src,
                    "revisedPrompt": item.get("revised_prompt")
                    if isinstance(item.get("revised_prompt"), str)
                    else None,
                }
            )
    return images, safe_raw

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    settings = get_settings()
    settings.validate_startup()
    if settings.auto_create_tables:
        init_db()


@app.get("/api/health")
async def health(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict[str, str]:
    database_status = "ok"
    try:
        db.execute(text("select 1"))
    except Exception:
        database_status = "error"
    return {
        "status": "ok" if database_status == "ok" else "degraded",
        "database": database_status,
        "storage": "configured" if settings.object_storage_enabled else "not_configured",
    }


@app.get("/api/assets/generated/{file_name}")
async def generated_asset(file_name: str) -> FileResponse:
    if "/" in file_name or "\\" in file_name or not file_name.endswith(".png"):
        raise HTTPException(status_code=404, detail={"message": "Asset not found."})
    file_path = GENERATED_ASSET_DIR / file_name
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail={"message": "Asset not found."})
    return FileResponse(file_path, media_type="image/png")


@app.get("/api/auth/me")
async def auth_me(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {"user": serialize_user(current_user).model_dump()}


@app.get("/api/auth/csrf")
async def auth_csrf(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return {"csrfToken": issue_csrf_token(request, db, settings)}


@app.post("/api/auth/register")
async def auth_register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    check_rate_limit(
        limiter=rate_limiter,
        request=request,
        settings=settings,
        bucket="auth",
        limit=settings.rate_limit_login_per_window,
    )
    user = register_local_user(db, payload)
    db.flush()
    create_session(db, response, user)
    db.commit()
    return {"user": serialize_user(user).model_dump()}


@app.post("/api/auth/login")
async def auth_login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    check_rate_limit(
        limiter=rate_limiter,
        request=request,
        settings=settings,
        bucket="auth",
        limit=settings.rate_limit_login_per_window,
    )
    user = authenticate_local_user(db, payload, settings)
    db.flush()
    create_session(db, response, user)
    db.commit()
    return {"user": serialize_user(user).model_dump()}


@app.get("/api/auth/callback")
async def auth_callback(
    request: Request,
    response: Response,
    code: str = Query(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    check_rate_limit(
        limiter=rate_limiter,
        request=request,
        settings=settings,
        bucket="auth-callback",
        limit=settings.rate_limit_login_per_window,
    )
    profile = await exchange_official_code(code, settings)
    user = upsert_user(db, **profile)
    db.flush()
    create_session(db, response, user)
    db.commit()
    return {"user": serialize_user(user).model_dump(), "redirectUrl": settings.frontend_url}


@app.get("/auth/callback")
async def public_auth_callback(
    request: Request,
    code: str = Query(...),
    next_url: str = Query("", alias="next"),
    state: str = Query(""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    check_rate_limit(
        limiter=rate_limiter,
        request=request,
        settings=settings,
        bucket="auth-callback",
        limit=settings.rate_limit_login_per_window,
    )
    redirect_target = safe_frontend_hash_path(next_url or state or "#/settings")
    response = RedirectResponse(frontend_redirect_url(settings, redirect_target), status_code=307)
    try:
        profile = await exchange_official_code(code, settings)
        user = upsert_user(db, **profile)
        db.flush()
        create_session(db, response, user)
        db.commit()
    except HTTPException as exc:
        db.rollback()
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        message = str(detail.get("message") or "授权登录失败，请返回官网重新进入。")
        return RedirectResponse(auth_error_redirect_url(settings, message), status_code=307)
    return response


@app.post("/api/auth/dev-login")
async def auth_dev_login(
    payload: DevLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    check_rate_limit(
        limiter=rate_limiter,
        request=request,
        settings=settings,
        bucket="auth",
        limit=settings.rate_limit_login_per_window,
    )
    if not settings.enable_dev_login:
        raise HTTPException(status_code=404, detail={"message": "开发登录未启用。"})
    user = upsert_user(
        db,
        external_user_id=payload.externalUserId,
        email=payload.email,
        phone=payload.phone,
        nickname=payload.nickname,
        avatar_url=payload.avatarUrl,
    )
    db.flush()
    create_session(db, response, user)
    db.commit()
    return {"user": serialize_user(user).model_dump()}


@app.post("/api/auth/logout")
async def auth_logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, bool]:
    clear_session(request, response, db, settings)
    return {"ok": True}


@app.put("/api/users/me")
async def update_me(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    update_user_profile(current_user, payload)
    db.commit()
    db.refresh(current_user)
    return {"user": serialize_user(current_user).model_dump()}


@app.get("/api/api-keys")
async def api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"apiKeys": [serialize_api_key(item).model_dump() for item in list_api_keys(db, current_user)]}


@app.get("/api/models")
async def models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"models": [serialize_model(item).model_dump() for item in list_model_groups(db, current_user)]}


@app.post("/api/models")
async def create_model(
    payload: ModelCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    model = create_model_group(db, current_user, payload)
    return {"model": serialize_model(model).model_dump()}


@app.put("/api/models/{model_id}")
async def update_model(
    model_id: str,
    payload: ModelUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    model = update_model_group(db, current_user, model_id, payload)
    return {"model": serialize_model(model).model_dump()}


@app.delete("/api/models/{model_id}")
async def delete_model(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> dict[str, bool]:
    delete_model_group(db, current_user, model_id)
    return {"ok": True}


@app.post("/api/models/{model_id}/primary")
async def set_model_primary(
    model_id: str,
    payload: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    sub_model_id = str(payload.get("subModelId") or "").strip()
    if not sub_model_id:
        raise HTTPException(status_code=400, detail={"message": "缺少子模型 ID。"})
    model = set_primary_sub_model(db, current_user, model_id, sub_model_id)
    return {"model": serialize_model(model).model_dump()}


@app.post("/api/models/{model_id}/sync")
async def sync_model_list(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    model = get_model_group(db, current_user, model_id)
    api_key = model.api_key
    target_url = resolve_url(api_key.base_url, "/v1/models")
    started_at = time.perf_counter()
    response, raw = await forward_json("GET", target_url, api_key=decrypt_secret(api_key.api_key_ciphertext))
    duration_ms = elapsed_ms(started_at)
    if not response.is_success or not isinstance(raw, dict):
        raise upstream_error(raw, "获取模型列表失败。", response.status_code)
    result = sync_models_from_raw(db, model, raw, duration_ms)
    return result.model_dump()


@app.get("/api/calls")
async def call_logs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        db.query(CallLog)
        .filter(CallLog.user_id == current_user.id)
        .order_by(CallLog.created_at.desc())
        .limit(50)
        .all()
    )
    return {"calls": [serialize_call_log(item).model_dump() for item in rows]}


@app.get("/api/calls/summary")
async def call_logs_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = db.query(CallLog).filter(CallLog.user_id == current_user.id).all()
    summary: dict[str, Any] = {
        "total": len(rows),
        "success": 0,
        "error": 0,
        "failureRate": 0,
        "byCapability": {},
    }
    for row in rows:
        status_key = "success" if row.status == "success" else "error"
        summary[status_key] += 1
        capability = row.capability or "unknown"
        bucket = summary["byCapability"].setdefault(
            capability,
            {"total": 0, "success": 0, "error": 0, "failureRate": 0},
        )
        bucket["total"] += 1
        bucket[status_key] += 1
    if summary["total"]:
        summary["failureRate"] = round(summary["error"] / summary["total"], 4)
    for bucket in summary["byCapability"].values():
        if bucket["total"]:
            bucket["failureRate"] = round(bucket["error"] / bucket["total"], 4)
    return {"summary": summary}


@app.get("/api/conversations")
async def conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "conversations": [
            serialize_conversation(item, include_messages=False).model_dump()
            for item in list_conversations(db, current_user)
        ]
    }


@app.post("/api/conversations")
async def create_conversation_route(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    conversation = create_conversation(db, current_user, payload)
    return {"conversation": serialize_conversation(conversation).model_dump()}


@app.get("/api/conversations/{conversation_id}")
async def conversation_detail(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    conversation = get_conversation(db, current_user, conversation_id)
    return {"conversation": serialize_conversation(conversation).model_dump()}


@app.post("/api/proxy/models")
async def proxy_models(
    payload: dict[str, Any],
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    check_rate_limit(
        limiter=rate_limiter,
        request=request,
        settings=settings,
        bucket="models",
        limit=settings.rate_limit_model_test_per_window,
    )
    base_url, api_key = validate_config(payload.get("config"))
    target_url = resolve_url(base_url, "/v1/models")
    started_at = time.perf_counter()
    response, raw = await forward_json("GET", target_url, api_key)
    duration_ms = round((time.perf_counter() - started_at) * 1000)

    if not response.is_success or not isinstance(raw, dict):
        raise upstream_error(raw, "获取模型列表失败。", response.status_code)

    return {
        "models": filter_model_ids_for_capability(parse_model_ids(raw), str(payload.get("capability") or "")),
        "durationMs": duration_ms,
        "raw": raw,
    }


@app.post("/api/proxy/test")
async def proxy_test(
    payload: dict[str, Any],
    request: Request,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    check_rate_limit(
        limiter=rate_limiter,
        request=request,
        settings=settings,
        bucket="model-test",
        limit=settings.rate_limit_model_test_per_window,
        user_id=current_user.id if current_user else "",
    )
    if payload.get("subModelId") and not current_user:
        raise HTTPException(status_code=401, detail={"message": "请先登录。"})
    if payload.get("subModelId") and current_user:
        model_group, sub_model, api_key_record, api_key = get_sub_model_for_user(db, current_user, str(payload["subModelId"]))
        base_url = api_key_record.base_url
        capability = sub_model.capability
        model = sub_model.model_name
        adapter = sub_model.adapter
    else:
        base_url, api_key = validate_config(payload.get("config"))
        capability = payload.get("capability")
        model = str(payload.get("model", "")).strip()
        adapter = payload.get("adapter")

    if not capability:
        raise HTTPException(status_code=400, detail={"message": "缺少模型能力类型。"})
    if not model:
        raise HTTPException(status_code=400, detail={"message": "缺少模型标识。"})

    target_url = resolve_url(base_url, resolve_test_path(str(capability), str(adapter) if adapter else None))
    body = build_test_body(str(capability), model, str(adapter) if adapter else None)
    started_at = time.perf_counter()
    response, raw = await forward_json("POST", target_url, api_key, body)
    raw = coerce_json_object(raw)
    duration_ms = round((time.perf_counter() - started_at) * 1000)
    request = {"url": target_url, "body": body}

    if not response.is_success or not isinstance(raw, dict):
        raise HTTPException(
            status_code=response.status_code or 500,
            detail={
                "message": pick_error_message(raw, "测试请求失败。"),
                "request": request,
                "durationMs": duration_ms,
                "raw": raw,
            },
        )

    return {
        "ok": True,
        "status": response.status_code,
        "request": request,
        "durationMs": duration_ms,
        "raw": raw,
    }


@app.post("/api/proxy/text")
async def proxy_text(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    check_rate_limit(
        limiter=rate_limiter,
        request=request,
        settings=settings,
        bucket="generation-text",
        limit=settings.rate_limit_generation_per_window,
        user_id=current_user.id if current_user else "",
    )
    model_group = sub_model = None
    conversation = None
    user_prompt = ""
    if payload.get("subModelId") and not current_user:
        raise HTTPException(status_code=401, detail={"message": "请先登录。"})
    if payload.get("subModelId") and current_user:
        model_group, sub_model, api_key_record, api_key = get_sub_model_for_user(db, current_user, str(payload["subModelId"]))
        base_url = api_key_record.base_url
        model = sub_model.model_name
    else:
        base_url, api_key = validate_config(payload.get("config"))
        model = str(payload.get("model", "")).strip()
    if not model:
        raise HTTPException(status_code=400, detail={"message": "缺少模型标识。"})

    target_url = resolve_url(base_url, "/v1/chat/completions")
    body = {"model": model, **(payload.get("requestBody") or {})}
    messages = body.get("messages") if isinstance(body.get("messages"), list) else []
    for item in reversed(messages):
        if isinstance(item, dict) and item.get("role") == "user" and isinstance(item.get("content"), str):
            user_prompt = item["content"]
            break
    if current_user and model_group and sub_model:
        conversation = ensure_conversation(
            db,
            current_user,
            conversation_id=str(payload.get("conversationId") or ""),
            title_seed=user_prompt,
            capability="text",
            model_group_id=model_group.id,
            sub_model_id=sub_model.id,
        )
        add_message(
            db,
            conversation,
            current_user,
            role="user",
            capability="text",
            content=user_prompt,
            model_group_id=model_group.id,
            sub_model_id=sub_model.id,
            request=body,
        )
    started_at = time.perf_counter()
    response, raw = await forward_json("POST", target_url, api_key, body)
    duration_ms = elapsed_ms(started_at)

    if not response.is_success or not isinstance(raw, dict):
        message = pick_error_message(raw, "文案请求失败。")
        failed_message = None
        if current_user and model_group and sub_model:
            if conversation:
                failed_message = add_message(
                    db,
                    conversation,
                    current_user,
                    role="assistant",
                    capability="text",
                    content="",
                    status="error",
                    error_message=message,
                    can_retry=True,
                    model_group_id=model_group.id,
                    sub_model_id=sub_model.id,
                    request=body,
                    response=raw,
                )
            record_call_log(
                db,
                user=current_user,
                model_group_id=model_group.id,
                sub_model_id=sub_model.id,
                capability="text",
                endpoint="/api/proxy/text",
                status="error",
                duration_ms=duration_ms,
                error_message=message,
            )
        detail = upstream_error(raw, "文案请求失败。", response.status_code).detail
        if conversation and failed_message:
            db.commit()
            refreshed = reload_conversation(db, current_user, conversation.id) if current_user else conversation
            detail = {
                **detail,
                "conversation": serialize_conversation(refreshed).model_dump(mode="json"),
                "assistantMessage": serialize_message(failed_message).model_dump(mode="json"),
            }
        raise HTTPException(status_code=response.status_code or 500, detail=detail)

    content = pick_text_content(raw)

    assistant_message = None
    if current_user and model_group and sub_model:
        if conversation:
            assistant_message = add_message(
                db,
                conversation,
                current_user,
                role="assistant",
                capability="text",
                content=content,
                status="success",
                model_group_id=model_group.id,
                sub_model_id=sub_model.id,
                request=body,
                response=raw,
            )
        record_call_log(
            db,
            user=current_user,
            model_group_id=model_group.id,
            sub_model_id=sub_model.id,
            capability="text",
            endpoint="/api/proxy/text",
            status="success",
            duration_ms=duration_ms,
            prompt_summary=str(body.get("messages", ""))[:512],
            usage=raw.get("usage"),
        )
    elif conversation:
        db.commit()

    result = {
        "content": content,
        "usage": raw.get("usage"),
        "raw": raw,
    }
    if conversation and current_user:
        db.commit()
        refreshed = reload_conversation(db, current_user, conversation.id)
        result["conversation"] = serialize_conversation(refreshed).model_dump()
        if assistant_message:
            result["assistantMessage"] = serialize_message(assistant_message).model_dump()
    return result


@app.post("/api/proxy/image")
async def proxy_image(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    check_rate_limit(
        limiter=rate_limiter,
        request=request,
        settings=settings,
        bucket="generation-image",
        limit=settings.rate_limit_generation_per_window,
        user_id=current_user.id if current_user else "",
    )
    model_group = sub_model = None
    conversation = None
    if payload.get("subModelId") and not current_user:
        raise HTTPException(status_code=401, detail={"message": "请先登录。"})
    if payload.get("subModelId") and current_user:
        model_group, sub_model, api_key_record, api_key = get_sub_model_for_user(db, current_user, str(payload["subModelId"]))
        base_url = api_key_record.base_url
        model = sub_model.model_name
    else:
        base_url, api_key = validate_config(payload.get("config"))
        model = str(payload.get("model", "")).strip()
    if not model:
        raise HTTPException(status_code=400, detail={"message": "缺少模型标识。"})

    target_url = resolve_url(base_url, "/v1/images/generations")
    body = {"model": model, **(payload.get("requestBody") or {})}
    prompt = str(body.get("prompt") or "")
    if current_user and model_group and sub_model:
        conversation = ensure_conversation(
            db,
            current_user,
            conversation_id=str(payload.get("conversationId") or ""),
            title_seed=prompt,
            capability="image",
            model_group_id=model_group.id,
            sub_model_id=sub_model.id,
        )
        add_message(
            db,
            conversation,
            current_user,
            role="user",
            capability="image",
            content=prompt,
            model_group_id=model_group.id,
            sub_model_id=sub_model.id,
            request=body,
        )
    started_at = time.perf_counter()
    response, raw = await forward_json("POST", target_url, api_key, body)
    duration_ms = elapsed_ms(started_at)

    if not response.is_success or not isinstance(raw, dict):
        message = pick_error_message(raw, "图片请求失败。")
        failed_message = None
        if current_user and model_group and sub_model:
            if conversation:
                failed_message = add_message(
                    db,
                    conversation,
                    current_user,
                    role="assistant",
                    capability="image",
                    status="error",
                    error_message=message,
                    can_retry=True,
                    model_group_id=model_group.id,
                    sub_model_id=sub_model.id,
                    request=body,
                    response=raw,
                )
            record_call_log(
                db,
                user=current_user,
                model_group_id=model_group.id,
                sub_model_id=sub_model.id,
                capability="image",
                endpoint="/api/proxy/image",
                status="error",
                duration_ms=duration_ms,
                error_message=message,
            )
        detail = upstream_error(raw, "图片请求失败。", response.status_code).detail
        if conversation and failed_message and current_user:
            db.commit()
            refreshed = reload_conversation(db, current_user, conversation.id)
            detail = {
                **detail,
                "conversation": serialize_conversation(refreshed).model_dump(mode="json"),
                "assistantMessage": serialize_message(failed_message).model_dump(mode="json"),
            }
        raise HTTPException(status_code=response.status_code or 500, detail=detail)

    images, safe_raw = extract_images_from_response(raw)

    assistant_message = None
    if current_user and model_group and sub_model:
        if conversation:
            assistant_message = add_message(
                db,
                conversation,
                current_user,
                role="assistant",
                capability="image",
                content="",
                status="success",
                model_group_id=model_group.id,
                sub_model_id=sub_model.id,
                request=body,
                response=safe_raw,
            )
            for image in images:
                add_asset(
                    db,
                    assistant_message,
                    current_user,
                    capability="image",
                    asset_type="image",
                    url=image["src"],
                    metadata={"revisedPrompt": image.get("revisedPrompt")},
                )
        record_call_log(
            db,
            user=current_user,
            model_group_id=model_group.id,
            sub_model_id=sub_model.id,
            capability="image",
            endpoint="/api/proxy/image",
            status="success",
            duration_ms=duration_ms,
            prompt_summary=str(body.get("prompt", ""))[:512],
            usage=raw.get("usage"),
        )

    result = {"images": images, "raw": safe_raw}
    if conversation and current_user:
        db.commit()
        refreshed = reload_conversation(db, current_user, conversation.id)
        result["conversation"] = serialize_conversation(refreshed).model_dump()
        if assistant_message:
            result["assistantMessage"] = serialize_message(assistant_message).model_dump()
    return result


@app.post("/api/proxy/video/create")
async def proxy_video_create(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    check_rate_limit(
        limiter=rate_limiter,
        request=request,
        settings=settings,
        bucket="generation-video",
        limit=settings.rate_limit_generation_per_window,
        user_id=current_user.id if current_user else "",
    )
    model_group = sub_model = None
    conversation = None
    if payload.get("subModelId") and not current_user:
        raise HTTPException(status_code=401, detail={"message": "请先登录。"})
    if payload.get("subModelId") and current_user:
        model_group, sub_model, api_key_record, api_key = get_sub_model_for_user(db, current_user, str(payload["subModelId"]))
        base_url = api_key_record.base_url
        adapter = sub_model.adapter
    else:
        base_url, api_key = validate_config(payload.get("config"))
        adapter = str(payload.get("adapter", "")).strip()
    if not adapter:
        raise HTTPException(status_code=400, detail={"message": "缺少视频适配器。"})

    target_url = resolve_url(base_url, resolve_video_create_path(adapter))
    request_body = payload.get("requestBody") or {}
    prompt = extract_video_prompt(request_body if isinstance(request_body, dict) else {})
    if current_user and model_group and sub_model:
        conversation = ensure_conversation(
            db,
            current_user,
            conversation_id=str(payload.get("conversationId") or ""),
            title_seed=prompt,
            capability="video",
            model_group_id=model_group.id,
            sub_model_id=sub_model.id,
        )
        add_message(
            db,
            conversation,
            current_user,
            role="user",
            capability="video",
            content=prompt,
            model_group_id=model_group.id,
            sub_model_id=sub_model.id,
            request=request_body,
        )
    started_at = time.perf_counter()
    response, raw = await forward_json("POST", target_url, api_key, request_body)
    duration_ms = elapsed_ms(started_at)

    if not response.is_success or not isinstance(raw, dict):
        message = pick_error_message(raw, "视频任务提交失败。")
        failed_message = None
        if current_user and model_group and sub_model:
            if conversation:
                failed_message = add_message(
                    db,
                    conversation,
                    current_user,
                    role="assistant",
                    capability="video",
                    content="",
                    status="error",
                    error_message=message,
                    can_retry=True,
                    model_group_id=model_group.id,
                    sub_model_id=sub_model.id,
                    request=request_body,
                    response=raw,
                )
            record_call_log(
                db,
                user=current_user,
                model_group_id=model_group.id,
                sub_model_id=sub_model.id,
                capability="video",
                endpoint="/api/proxy/video/create",
                status="error",
                duration_ms=duration_ms,
                error_message=message,
            )
        detail = upstream_error(raw, "视频任务提交失败。", response.status_code).detail
        if conversation and failed_message and current_user:
            db.commit()
            refreshed = reload_conversation(db, current_user, conversation.id)
            detail = {
                **detail,
                "conversation": serialize_conversation(refreshed).model_dump(mode="json"),
                "assistantMessage": serialize_message(failed_message).model_dump(mode="json"),
            }
        raise HTTPException(status_code=response.status_code or 500, detail=detail)

    task_id = pick_task_id(raw)
    assistant_message = None
    if current_user and model_group and sub_model:
        if conversation:
            assistant_message = add_message(
                db,
                conversation,
                current_user,
                role="assistant",
                capability="video",
                content=task_id,
                status="processing",
                can_retry=False,
                model_group_id=model_group.id,
                sub_model_id=sub_model.id,
                request=request_body,
                response=raw,
            )
        record_call_log(
            db,
            user=current_user,
            model_group_id=model_group.id,
            sub_model_id=sub_model.id,
            capability="video",
            endpoint="/api/proxy/video/create",
            status="success",
            duration_ms=duration_ms,
            prompt_summary=str((payload.get("requestBody") or {}).get("prompt", ""))[:512],
            usage=None,
        )

    result = {
        "taskId": task_id,
        "status": raw.get("status") if isinstance(raw.get("status"), str) else raw.get("code") if isinstance(raw.get("code"), str) else "submitted",
        "raw": raw,
    }
    if conversation and current_user:
        db.commit()
        refreshed = reload_conversation(db, current_user, conversation.id)
        result["conversation"] = serialize_conversation(refreshed).model_dump()
        if assistant_message:
            result["assistantMessage"] = serialize_message(assistant_message).model_dump()
    return result


@app.post("/api/proxy/video/query")
async def proxy_video_query(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    check_rate_limit(
        limiter=rate_limiter,
        request=request,
        settings=settings,
        bucket="generation-video-query",
        limit=settings.rate_limit_generation_per_window,
        user_id=current_user.id if current_user else "",
    )
    model_group = None
    sub_model = None
    conversation_id = str(payload.get("conversationId") or "").strip()
    if payload.get("subModelId") and not current_user:
        raise HTTPException(status_code=401, detail={"message": "请先登录。"})
    if payload.get("subModelId") and current_user:
        model_group, sub_model, api_key_record, api_key = get_sub_model_for_user(db, current_user, str(payload["subModelId"]))
        base_url = api_key_record.base_url
        adapter = sub_model.adapter
    else:
        base_url, api_key = validate_config(payload.get("config"))
        adapter = str(payload.get("adapter", "")).strip()
    task_id = str(payload.get("taskId", "")).strip()
    if not adapter:
        raise HTTPException(status_code=400, detail={"message": "缺少视频适配器。"})
    if not task_id:
        raise HTTPException(status_code=400, detail={"message": "缺少任务 ID。"})

    target_url = resolve_url(base_url, resolve_video_query_path(adapter, task_id))
    started_at = time.perf_counter()
    response, raw = await forward_json("GET", target_url, api_key)
    duration_ms = elapsed_ms(started_at)

    if not response.is_success or not isinstance(raw, dict):
        message = pick_error_message(raw, "任务查询失败。")
        failed_message = None
        conversation = None
        if current_user and model_group and sub_model:
            if conversation_id:
                conversation = get_conversation(db, current_user, conversation_id)
                failed_message = add_message(
                    db,
                    conversation,
                    current_user,
                    role="assistant",
                    capability="video",
                    content=task_id,
                    status="error",
                    error_message=message,
                    can_retry=True,
                    model_group_id=model_group.id,
                    sub_model_id=sub_model.id,
                    request={"taskId": task_id},
                    response=raw,
                )
            record_call_log(
                db,
                user=current_user,
                model_group_id=model_group.id,
                sub_model_id=sub_model.id,
                capability="video",
                endpoint="/api/proxy/video/query",
                status="error",
                duration_ms=duration_ms,
                error_message=message,
            )
        detail = upstream_error(raw, "任务查询失败。", response.status_code).detail
        if conversation and failed_message and current_user:
            db.commit()
            refreshed = reload_conversation(db, current_user, conversation.id)
            detail = {
                **detail,
                "conversation": serialize_conversation(refreshed).model_dump(mode="json"),
                "assistantMessage": serialize_message(failed_message).model_dump(mode="json"),
            }
        raise HTTPException(status_code=response.status_code or 500, detail=detail)

    result = pick_video_query_payload(raw, task_id)
    if (
        current_user
        and model_group
        and sub_model
        and conversation_id
        and result.get("videoUrl")
    ):
        conversation = get_conversation(db, current_user, conversation_id)
        assistant_message = add_message(
            db,
            conversation,
            current_user,
            role="assistant",
            capability="video",
            content=str(result.get("status") or ""),
            status="success" if result.get("status") == "completed" else "processing",
            model_group_id=model_group.id,
            sub_model_id=sub_model.id,
            request={"taskId": task_id},
            response=raw,
        )
        add_asset(
            db,
            assistant_message,
            current_user,
            capability="video",
            asset_type="video",
            url=str(result["videoUrl"]),
            thumbnail_url=str(result.get("thumbnailUrl") or ""),
            metadata={"taskId": task_id, "status": result.get("status"), "progress": result.get("progress")},
        )
        db.commit()
        refreshed = reload_conversation(db, current_user, conversation.id)
        result["conversation"] = serialize_conversation(refreshed).model_dump()
        result["assistantMessage"] = serialize_message(assistant_message).model_dump()
        record_call_log(
            db,
            user=current_user,
            model_group_id=model_group.id,
            sub_model_id=sub_model.id,
            capability="video",
            endpoint="/api/proxy/video/query",
            status="success",
            duration_ms=duration_ms,
            prompt_summary=task_id,
            usage=None,
        )

    return result


@app.post("/api/proxy/upload/presign")
async def proxy_upload_presign(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    check_rate_limit(
        limiter=rate_limiter,
        request=request,
        settings=settings,
        bucket="upload",
        limit=settings.rate_limit_upload_per_window,
        user_id=current_user.id if current_user else "",
    )
    if payload.get("subModelId") and not current_user:
        raise HTTPException(status_code=401, detail={"message": "请先登录。"})
    file_name = str(payload.get("fileName") or "upload.bin")
    content_type = str(payload.get("contentType") or "application/octet-stream")
    if settings.object_storage_enabled:
        return create_presigned_put_url(
            settings=settings,
            file_name=file_name,
            content_type=content_type,
            expires_in=900,
        )

    if payload.get("subModelId") and current_user:
        _model_group, _sub_model, api_key_record, api_key = get_sub_model_for_user(db, current_user, str(payload["subModelId"]))
        base_url = api_key_record.base_url
    else:
        base_url, api_key = validate_config(payload.get("config"))
    target_url = resolve_url(base_url, "/api/upload/presign")
    body = {
        "file_name": file_name,
        "content_type": content_type,
        "expires_in": 900,
    }
    response, raw = await forward_json("POST", target_url, api_key, body)

    if not response.is_success or not isinstance(raw, dict):
        raise upstream_error(raw, "获取上传地址失败。", response.status_code)

    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    if not raw.get("success") or not data:
        raise upstream_error(raw, "上传服务未正确返回预签名地址。", 500)

    return {
        "uploadUrl": data.get("upload_url") if isinstance(data.get("upload_url"), str) else "",
        "method": data.get("method") if isinstance(data.get("method"), str) else "PUT",
        "publicUrl": data.get("public_url") if isinstance(data.get("public_url"), str) else "",
        "objectKey": data.get("object_key") if isinstance(data.get("object_key"), str) else "",
        "contentType": data.get("content_type") if isinstance(data.get("content_type"), str) else body["content_type"],
    }
