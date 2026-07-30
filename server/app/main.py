from __future__ import annotations

import base64
import binascii
import asyncio
import copy
import ipaddress
import json
from contextlib import asynccontextmanager
from pathlib import Path
import time
from uuid import uuid4
from typing import Any
from urllib.parse import quote, unquote, urlparse

import httpx
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import (
    authenticate_local_user,
    clear_session,
    client_ip_from_request,
    create_session,
    exchange_official_code,
    get_current_user,
    get_optional_current_user,
    issue_csrf_token,
    is_admin_user,
    register_local_user,
    require_admin_user,
    require_csrf,
    serialize_user,
    update_user_profile,
    upsert_user,
)
from app.admin_service import (
    admin_dashboard_metrics,
    admin_delete_user,
    admin_disable_user,
    admin_duplicate_identity_map,
    admin_enable_user,
    admin_overview,
    admin_record_detail,
    admin_restore_user,
    admin_audit_risk_summary,
    admin_task_timeline,
    admin_users_summary,
    build_admin_audit_logs_csv,
    build_admin_creation_records_csv,
    build_admin_users_csv,
    count_admin_audit_logs,
    count_admin_models,
    count_admin_users,
    get_model_health,
    get_prompt_template_for_scope,
    list_prompt_template_versions,
    restore_prompt_template_version,
    list_admin_audit_logs,
    list_admin_creation_records,
    list_admin_models,
    list_admin_users,
    list_prompt_templates,
    prompt_template_model_status_overview,
    publish_model,
    record_model_health_check,
    record_task_event,
    render_prompt_template_samples,
    render_prompt_template,
    serialize_admin_user,
    serialize_admin_user_with_duplicate_identity,
    serialize_prompt_template,
    set_admin_user_role,
    unpublish_model,
    update_admin_model,
    update_admin_user,
    upsert_prompt_template,
    write_admin_log,
)
from app.admin_permissions import can, permissions_for_role, resolve_admin_role
from app.asset_cleanup import (
    asset_cleanup_settings,
    build_cleanup_targets,
    maybe_run_scheduled_asset_cleanup,
    preview_asset_cleanup,
    run_asset_cleanup,
    update_asset_cleanup_settings,
)
from app.config import Settings, get_settings
from app.conversation_service import (
    add_asset,
    add_message,
    create_conversation,
    dumps_for_storage,
    ensure_conversation,
    get_conversation,
    list_conversations,
    make_title,
    reload_conversation,
    serialize_conversation,
    serialize_message,
    update_conversation_title,
)
from app.catalog_service import (
    fetch_kkyi_catalog_details,
    list_catalog_models,
    normalize_existing_catalog_icons,
    serialize_catalog_model,
    sync_catalog_details,
)
from app.credit_service import (
    admin_adjust_credits,
    clear_model_price,
    dismiss_credit_grant_notification,
    estimate_credit_price,
    grant_signup_bonus,
    get_credit_settings,
    get_or_create_credit_account,
    capture_generation_credits,
    find_reserved_transaction,
    list_credit_transactions,
    refund_generation_credits,
    reserve_generation_credits,
    serialize_credit_account,
    serialize_credit_transaction,
    serialize_price_estimate,
    set_model_price,
    update_reserved_transaction_refs,
    update_credit_settings,
)
from app.database import SessionLocal, get_db, init_db
from app.db_models import CallLog, Conversation, ConversationMessage, GeneratedAsset, ModelGroup, SubModel, User, UserCredential, utcnow
from app.model_service import (
    create_model_group,
    delete_model_group,
    elapsed_ms,
    find_gpt55_prompt_optimizer_sub_model,
    get_model_group,
    find_prompt_optimizer_sub_model,
    get_sub_model_for_user,
    list_api_keys,
    list_model_groups,
    backfill_all_catalog_links,
    record_call_log,
    serialize_api_key,
    serialize_call_log,
    serialize_model,
    set_primary_sub_model,
    sync_models_from_raw,
    update_model_group,
)
from app.prompt_library_service import (
    batch_update_scene_templates,
    build_recommendation_messages,
    import_prompt_scene_templates,
    list_scene_templates,
    scene_template_summary,
    parse_recommendation_payload,
    recommendation_candidates,
    record_scene_template_event,
    record_scene_template_event_by_id,
    serialize_scene_template,
    update_scene_template,
)
from app.proxy_utils import (
    auth_headers,
    build_test_body,
    coerce_json_object,
    forward_json,
    first_string_at_paths,
    normalize_task_status,
    parse_model_ids,
    pick_nested_task_id,
    pick_task_id,
    pick_error_message,
    pick_text_content,
    pick_video_task_error_message,
    pick_video_query_payload,
    is_non_json_upstream_error,
    resolve_test_path,
    resolve_url,
    resolve_video_create_path,
    resolve_video_query_path,
    sanitize_error_raw,
    upstream_error,
    validate_config,
    filter_model_ids_for_capability,
    forward_multipart,
)
from app.rate_limit import InMemoryRateLimiter, check_rate_limit
from app.reference_assets import (
    collect_reference_image_assets,
    indexed_reference_metadata,
    validate_reference_limit,
)
from app.asset_storage import backfill_asset_storage
from app.schemas import (
    AdminBatchCreditAdjustRequest,
    AdminCreditAdjustRequest,
    AdminCreditSettingsUpdate,
    AdminDashboardMetricOut,
    AdminModelBatchRequest,
    AdminModelCreditPricingUpdate,
    AdminModelUpdate,
    AdminPermissionOut,
    AdminResetPasswordRequest,
    AdminUserMergeRequest,
    AdminUserRoleUpdate,
    AdminUserUpdate,
    ConversationCreate,
    ConversationUpdate,
    DevLoginRequest,
    LoginRequest,
    KkyiCatalogSyncRequest,
    ModelCreate,
    ModelUpdate,
    PromptOptimizeRequest,
    PromptTemplateUpdate,
    ChangePasswordRequest,
    ProfileUpdateRequest,
    RegisterRequest,
)
from app.security import decrypt_secret, hash_password, verify_password
from app.storage import create_presigned_put_url
from app.user_maintenance import merge_duplicate_users_by_identity


ASSET_CLEANUP_LOOP_INTERVAL_SECONDS = 3600


def run_scheduled_asset_cleanup_once() -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        return maybe_run_scheduled_asset_cleanup(db, targets=asset_cleanup_targets())
    finally:
        db.close()


async def asset_cleanup_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(run_scheduled_asset_cleanup_once)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Automatic cleanup should never block application startup or request handling.
            pass
        await asyncio.sleep(ASSET_CLEANUP_LOOP_INTERVAL_SECONDS)


def backfill_asset_storage_once() -> int:
    db = SessionLocal()
    try:
        count = backfill_asset_storage(db, GENERATED_ASSET_DIR, LOCAL_UPLOAD_DIR, get_settings(), batch_size=100)
        db.commit()
        return count
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    settings.validate_startup()
    if settings.auto_create_tables:
        init_db()
    await asyncio.to_thread(backfill_asset_storage_once)
    cleanup_task = asyncio.create_task(asset_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="创意工坊 Server", lifespan=lifespan)
GENERATED_ASSET_DIR = Path(__file__).resolve().parents[2] / "generated_assets"
GENERATED_ASSET_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploaded_assets"
LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_INLINE_REFERENCE_LENGTH = 10 * 1024 * 1024
FRONTEND_ROUTES = {"auth", "auth-error", "text", "images", "videos", "settings", "profile"}
rate_limiter = InMemoryRateLimiter()
TEXT_LONG_TASK_PREFIX = "text-task-"
IMAGE_LONG_TASK_PREFIX = "local-image-task-"
IMAGE_BATCH_MAX_COUNT = 10
GENERATION_FAILED_MESSAGE = "生成失败，请稍后重试。"
GENERATION_POLICY_MESSAGE = "内容未通过安全审核，请调整提示词或参考图后重试。"
GENERATION_REFERENCE_INVALID_MESSAGE = "参考图无法识别或格式不支持，请重新上传清晰图片后再试。"
GENERATION_REFERENCE_TOO_LARGE_MESSAGE = "参考图过大，请压缩或更换图片后再试。"
GENERATION_RATE_LIMIT_MESSAGE = "请求过于频繁，请稍后再试。"
GENERATION_QUOTA_MESSAGE = "模型额度不足，请检查密钥余额或更换模型。"
GENERATION_AUTH_MESSAGE = "模型密钥不可用，请检查配置后再试。"
GENERATION_PARAMETER_MESSAGE = "当前模型不支持所选参数，请调整尺寸、比例、分辨率或时长后再试。"
GENERATION_MODEL_MESSAGE = "模型不存在或未开通，请检查模型配置。"
GENERATION_IMAGE_MODEL_UNSUPPORTED_MESSAGE = "当前模型不支持图片生成，请更换模型或检查模型配置。"
NO_IMAGE_RETURNED_MESSAGE = "模型没有返回可展示的图片，请稍后重试或更换模型。"


def _flatten_error_text(value: Any) -> str:
    chunks: list[str] = []

    def collect(item: Any) -> None:
        if isinstance(item, str):
            chunks.append(item)
            return
        if isinstance(item, dict):
            for key in ("message", "msg", "detail", "error", "type", "code", "reason", "status", "raw", "upstream"):
                if key in item:
                    collect(item[key])
            return
        if isinstance(item, list):
            for child in item[:20]:
                collect(child)

    collect(value)
    return " ".join(chunks).strip().lower()


def generation_public_error_message(raw: Any, status_code: int = 500) -> str:
    text = _flatten_error_text(raw)
    if not text:
        text = str(raw or "").strip().lower()

    if any(token in text for token in ("<html", "<body", "invalid character '<'", "bad_response_body", "non json", "non-json")):
        return GENERATION_FAILED_MESSAGE
    if status_code in {502, 503, 504} or any(
        token in text
        for token in (
            "timeout",
            "timed out",
            "time-out",
            "deadline",
            "gateway",
            "bad gateway",
            "service unavailable",
            "internal server error",
            "bad_response_status_code",
            "openai_error",
        )
    ):
        return GENERATION_FAILED_MESSAGE

    if any(token in text for token in ("policy", "policies", "safety", "moderation", "content_filter", "content filter", "unsafe", "nsfw", "审核", "安全")):
        return GENERATION_POLICY_MESSAGE
    if status_code == 413 or any(token in text for token in ("too large", "payload too large", "file too large", "image too large", "exceeds", "max file size", "413")):
        return GENERATION_REFERENCE_TOO_LARGE_MESSAGE
    if any(
        token in text
        for token in (
            "invalid image",
            "unsupported image",
            "image format",
            "file format",
            "could not decode",
            "decode image",
            "not a valid image",
            "invalid base64",
            "reference image",
        )
    ):
        return GENERATION_REFERENCE_INVALID_MESSAGE
    if status_code == 429 or any(token in text for token in ("rate limit", "rate_limit", "too many requests", "429")):
        return GENERATION_RATE_LIMIT_MESSAGE
    if any(token in text for token in ("quota", "billing", "balance", "credit", "insufficient", "余额", "额度")):
        return GENERATION_QUOTA_MESSAGE
    if status_code in {401, 403} or any(
        token in text
        for token in (
            "invalid api key",
            "incorrect api key",
            "unauthorized",
            "forbidden",
            "permission denied",
            "login required",
            "not logged in",
            "请先登录",
            "未登录",
            "无权限",
        )
    ):
        return GENERATION_AUTH_MESSAGE
    if any(token in text for token in ("model not found", "model does not exist", "unknown model", "模型不存在")):
        return GENERATION_MODEL_MESSAGE
    if any(
        token in text
        for token in (
            "not supported model for image generation",
            "only imagen models are supported",
            "model does not support image generation",
            "model not support image",
            "不支持图片生成",
        )
    ):
        return GENERATION_IMAGE_MODEL_UNSUPPORTED_MESSAGE
    if any(
        token in text
        for token in (
            "invalid_request",
            "invalid request",
            "invalid parameter",
            "unsupported parameter",
            "not supported",
            "unsupported value",
            "size",
            "resolution",
            "duration",
            "aspect_ratio",
            "ratio",
        )
    ):
        return GENERATION_PARAMETER_MESSAGE

    return GENERATION_FAILED_MESSAGE


def add_reference_assets(
    db: Session,
    message: ConversationMessage,
    user: User,
    *,
    capability: str,
    references: list[dict[str, str]],
) -> None:
    for index, reference in enumerate(references):
        add_asset(
            db,
            message,
            user,
            capability=capability,
            asset_type="image",
            url=reference["url"],
            metadata=indexed_reference_metadata(
                index,
                reference.get("role") or "reference",
                reference.get("label") or "参考图",
            ),
        )


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


def safe_frontend_path(value: str, fallback: str = "#/settings") -> str:
    candidate = (value or "").strip()
    if not candidate:
        return fallback
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc or candidate.startswith("//"):
        return fallback
    clean = candidate if candidate.startswith(("#/", "/#/", "/")) else f"/{candidate.lstrip('/')}"
    if clean.rstrip("/") == "/admin":
        return "/admin/"
    return safe_frontend_hash_path(candidate, fallback)


def frontend_redirect_url(settings: Settings, path: str = "#/settings") -> str:
    safe_path = safe_frontend_path(path)
    separator = "" if safe_path.startswith("/") else "/"
    return f"{settings.frontend_url.rstrip('/')}{separator}{safe_path}"


def require_admin_permission(admin: User, permission: str, settings: Settings) -> None:
    if not can(admin, permission, settings):
        raise HTTPException(status_code=403, detail={"message": "当前账号没有执行该后台操作的权限。"})


def require_any_admin_permission(admin: User, permissions: list[str], settings: Settings) -> None:
    if not any(can(admin, permission, settings) for permission in permissions):
        raise HTTPException(status_code=403, detail={"message": "当前账号没有执行该后台操作的权限。"})


def parse_prompt_recommendation_limit(value: Any) -> int:
    try:
        requested = int(value or 8)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail={"message": "推荐数量必须是整数。"})
    return max(1, min(requested, 12))


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


def build_prompt_optimize_messages(payload: PromptOptimizeRequest) -> list[dict[str, str]]:
    capability_labels = {"text": "文案创作", "image": "图片创作", "video": "视频创作"}
    parameter_lines = [
        f"- {key}: {value}"
        for key, value in payload.parameters.items()
        if value not in (None, "", [])
    ]
    context = [
        f"创作类型：{capability_labels.get(payload.capability, payload.capability)}",
        f"原始提示词：{payload.prompt}",
    ]
    if payload.keywords:
        context.append(f"关键词：{payload.keywords}")
    if payload.referenceCount:
        context.append(f"参考素材数量：{payload.referenceCount}")
    if parameter_lines:
        context.append("已选参数：\n" + "\n".join(parameter_lines))
    return [
        {
            "role": "system",
            "content": (
                "你是创意工坊的专业提示词优化助手。请把用户的简短需求扩写成更准确、可执行的创作提示词。"
                "必须保留用户原意和主体，不要添加无关品牌、网址、上游平台信息。"
                "只输出优化后的提示词正文，不要解释过程，不要使用标题。"
            ),
        },
        {"role": "user", "content": "\n\n".join(context)},
    ]


def build_prompt_optimize_messages_from_template(payload: PromptOptimizeRequest, template: str) -> list[dict[str, str]]:
    rendered = render_prompt_template(
        template,
        {
            "prompt": payload.prompt,
            "capability": payload.capability,
            "keywords": payload.keywords,
            "referenceCount": payload.referenceCount,
            "parameters": json.dumps(payload.parameters, ensure_ascii=False),
        },
    )
    return [
        {
            "role": "system",
            "content": "你是创意工坊的专业提示词优化助手，只输出优化后的提示词正文。",
        },
        {"role": "user", "content": rendered},
    ]


def is_kkyi_catalog_video_model(sub_model: Any) -> bool:
    catalog_model = getattr(sub_model, "catalog_model", None)
    return bool(catalog_model and getattr(catalog_model, "source", "") == "kkyi" and getattr(catalog_model, "capability", "") == "video")


def is_kkyi_base_url(base_url: str) -> bool:
    host = urlparse(base_url.strip()).netloc.lower()
    return host in {"ai-api.kkidc.com", "www.kkyi.com", "kkyi.com"}


def is_kkyi_video_model(sub_model: Any, base_url: str) -> bool:
    if not sub_model or getattr(sub_model, "capability", "") != "video":
        return False
    return is_kkyi_catalog_video_model(sub_model) or is_kkyi_base_url(base_url)


def is_veo_video_model_name(model_name: str) -> bool:
    return "veo" in model_name.strip().lower()


def is_seedance_2_video_model_name(model_name: str) -> bool:
    return model_name.strip().lower().startswith("seedance-2.0-")


def kkyi_video_request_model_name(request_body: dict[str, Any], model_name: str, sub_model: Any | None) -> str:
    requested_model = str(request_body.get("model") or "").strip()
    if is_seedance_2_video_model_name(requested_model):
        return requested_model
    if is_seedance_2_video_model_name(model_name):
        return model_name
    sub_model_name = str(getattr(sub_model, "model_name", "") or "").strip()
    if is_seedance_2_video_model_name(sub_model_name):
        return sub_model_name
    catalog_model = getattr(sub_model, "catalog_model", None)
    catalog_model_name = str(getattr(catalog_model, "model_name", "") or "").strip()
    return catalog_model_name or requested_model or model_name


def normalize_veo_duration(value: Any) -> Any:
    try:
        duration = int(value)
    except (TypeError, ValueError):
        return value
    return min(duration, 8)


def catalog_parameter_for_key(sub_model: Any, keys: tuple[str, ...]) -> Any | None:
    catalog_model = getattr(sub_model, "catalog_model", None)
    parameters = getattr(catalog_model, "parameters", []) if catalog_model else []
    for parameter in parameters:
        if getattr(parameter, "param_key", "") in keys:
            return parameter
    return None


def sorted_catalog_option_values(parameter: Any) -> list[str]:
    options = sorted(getattr(parameter, "options", []) or [], key=lambda item: getattr(item, "sort_order", 0))
    return [str(getattr(option, "option_value", "")).strip() for option in options if str(getattr(option, "option_value", "")).strip()]


def coerce_catalog_video_value(key: str, value: Any) -> Any:
    if key in {"duration", "quantity"}:
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    return value


def default_catalog_video_value(parameter: Any, options: list[str]) -> str:
    default_value = str(getattr(parameter, "default_value", "") or "").strip()
    if options:
        return default_value if default_value in options else options[0]
    return default_value


def apply_catalog_video_constraints(normalized: dict[str, Any], sub_model: Any) -> dict[str, Any]:
    if not sub_model:
        return normalized
    field_keys = {
        "ratio": ("ratio", "aspect_ratio"),
        "duration": ("duration",),
        "resolution": ("resolution", "size"),
        "generate_audio": ("generate_audio", "audio"),
        "quantity": ("quantity", "n", "count"),
        "video_mode": ("video_mode", "mode"),
    }
    for target_key, catalog_keys in field_keys.items():
        parameter = catalog_parameter_for_key(sub_model, catalog_keys)
        if not parameter:
            continue
        options = sorted_catalog_option_values(parameter)
        fallback = default_catalog_video_value(parameter, options)
        current = normalized.get(target_key)
        if current in (None, ""):
            if fallback and bool(getattr(parameter, "is_required", False)):
                normalized[target_key] = coerce_catalog_video_value(target_key, fallback)
            continue
        if options and str(current).strip() not in options:
            normalized[target_key] = coerce_catalog_video_value(target_key, fallback)
    return normalized


KKYI_VIDEO_PUBLIC_URL_FIELDS = {
    "img_url",
    "first_frame",
    "last_frame",
    "firstFrameUrl",
    "lastFrameUrl",
    "video_url",
    "audio_url",
}


def local_asset_public_url(value: str, settings: Settings | None = None) -> str:
    candidate = value.strip()
    if not candidate:
        return value
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc or candidate.startswith("//"):
        return value
    path_prefixes = {
        "/api/assets/uploads/": LOCAL_UPLOAD_DIR,
        "/api/assets/generated/": GENERATED_ASSET_DIR,
    }
    for prefix, directory in path_prefixes.items():
        if not candidate.startswith(prefix):
            continue
        file_name = Path(unquote(Path(candidate.removeprefix(prefix)).name)).name
        file_path = directory / file_name
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail={"message": "Reference image not found."})
        app_settings = settings or get_settings()
        return f"{app_settings.frontend_url.rstrip('/')}{prefix}{quote(file_name)}"
    return value


def local_asset_public_urls(value: Any, settings: Settings) -> Any:
    if isinstance(value, str):
        return local_asset_public_url(value, settings)
    if isinstance(value, list):
        return [local_asset_public_urls(item, settings) for item in value]
    if isinstance(value, dict):
        return {key: local_asset_public_urls(item, settings) for key, item in value.items()}
    return value


def normalize_kkyi_video_url_fields(normalized: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    for key in KKYI_VIDEO_PUBLIC_URL_FIELDS:
        if key in normalized:
            normalized[key] = local_asset_public_urls(normalized[key], settings)
    return normalized


def normalize_seedance_2_openapi_video_body(normalized: dict[str, Any], request_body: dict[str, Any]) -> dict[str, Any]:
    metadata = copy.deepcopy(request_body.get("metadata")) if isinstance(request_body.get("metadata"), dict) else {}
    for key in ("seed", "watermark", "camera_fixed", "callback_url", "realPersonMode"):
        if key in request_body and request_body[key] not in (None, ""):
            metadata[key] = request_body[key]
    metadata.setdefault("realPersonMode", True)
    first_frame = normalized.get("firstFrameUrl") or normalized.get("first_frame")
    last_frame = normalized.get("lastFrameUrl") or normalized.get("last_frame")
    if first_frame not in (None, ""):
        metadata["firstFrameUrl"] = local_asset_public_urls(first_frame, get_settings())
    if last_frame not in (None, ""):
        metadata["lastFrameUrl"] = local_asset_public_urls(last_frame, get_settings())

    body: dict[str, Any] = {
        "model": normalized.get("model"),
        "prompt": normalized.get("prompt"),
    }
    if normalized.get("duration") not in (None, ""):
        body["duration"] = normalized["duration"]
    size = normalized.get("size") or normalized.get("resolution")
    if size not in (None, ""):
        body["size"] = size
    image = normalized.get("image")
    images = normalized.get("images") or normalized.get("img_url")
    if image not in (None, ""):
        body["image"] = local_asset_public_urls(image, get_settings())
    elif isinstance(images, list) and images:
        body["images"] = local_asset_public_urls(images, get_settings())
    elif isinstance(images, str) and images:
        body["image"] = local_asset_public_urls(images, get_settings())
    video_url = normalized.get("video_url") or normalized.get("input_reference")
    if video_url not in (None, ""):
        body["input_reference"] = local_asset_public_urls(video_url, get_settings())
    if metadata:
        body["metadata"] = local_asset_public_urls(metadata, get_settings())
    return {key: value for key, value in body.items() if value not in (None, "")}


def normalize_kkyi_video_body(request_body: dict[str, Any], model_name: str, sub_model: Any | None = None) -> dict[str, Any]:
    prompt = extract_video_prompt(request_body)
    normalized: dict[str, Any] = {
        "model": kkyi_video_request_model_name(request_body, model_name, sub_model),
        "prompt": prompt,
    }
    first_frame_key = "first_frame" if catalog_parameter_for_key(sub_model, ("first_frame",)) else "firstFrameUrl"
    last_frame_key = "last_frame" if catalog_parameter_for_key(sub_model, ("last_frame",)) else "lastFrameUrl"
    field_map = {
        "ratio": ("ratio", "aspect_ratio"),
        "duration": ("duration",),
        "resolution": ("resolution", "size"),
        "generate_audio": ("generate_audio", "audio"),
        "quantity": ("quantity", "n", "count"),
        "video_mode": ("video_mode", "mode"),
        "img_url": ("img_url",),
        first_frame_key: ("firstFrameUrl", "first_frame"),
        last_frame_key: ("lastFrameUrl", "last_frame"),
        "video_url": ("video_url",),
        "audio_url": ("audio_url",),
        "material": ("material",),
    }
    for target_key, source_keys in field_map.items():
        for source_key in source_keys:
            if source_key in request_body and request_body[source_key] not in (None, ""):
                normalized[target_key] = request_body[source_key]
                break
    if "images" in request_body and request_body["images"]:
        normalized["img_url"] = request_body["images"]
    if "image" in request_body and request_body["image"]:
        normalized["img_url"] = request_body["image"]
    if not normalized.get("model"):
        normalized["model"] = model_name
    normalized = apply_catalog_video_constraints(normalized, sub_model)
    if is_veo_video_model_name(str(normalized.get("model") or model_name)) and "duration" in normalized:
        normalized["duration"] = normalize_veo_duration(normalized["duration"])
    normalized = normalize_kkyi_video_url_fields(normalized)
    if is_seedance_2_video_model_name(str(normalized.get("model") or "")):
        return normalize_seedance_2_openapi_video_body(normalized, request_body)
    normalized.setdefault("quantity", 1)
    return {key: value for key, value in normalized.items() if value not in (None, "")}


def find_video_task_message(conversation: Conversation, task_id: str) -> ConversationMessage | None:
    for message in conversation.messages:
        if message.role == "assistant" and message.capability == "video" and message.content == task_id:
            return message
    for message in conversation.messages:
        if message.role != "assistant" or message.capability != "video":
            continue
        try:
            response = json.loads(message.response_json or "{}")
        except ValueError:
            response = {}
        if isinstance(response, dict) and (
            response.get("id") == task_id
            or response.get("task_id") == task_id
            or response.get("taskId") == task_id
        ):
            return message
    return None


def delete_duplicate_video_task_messages(db: Session, conversation: Conversation, keep_message: ConversationMessage, task_id: str) -> None:
    for message in list(conversation.messages):
        if message.id == keep_message.id:
            continue
        if message.role == "assistant" and message.capability == "video" and message.content in {task_id, "completed"}:
            db.delete(message)


def mark_video_task_message(
    db: Session,
    conversation: Conversation,
    user: User,
    *,
    task_id: str,
    model_group_id: str,
    sub_model_id: str,
    status: str,
    content: str,
    error_message: str = "",
    can_retry: bool = False,
    request: Any = None,
    response: Any = None,
) -> ConversationMessage:
    message = find_video_task_message(conversation, task_id)
    if message is None:
        message = add_message(
            db,
            conversation,
            user,
            role="assistant",
            capability="video",
            content=content,
            status=status,
            error_message=error_message,
            can_retry=can_retry,
            model_group_id=model_group_id,
            sub_model_id=sub_model_id,
            request=request,
            response=response,
        )
        return message

    message.model_group_id = model_group_id
    message.sub_model_id = sub_model_id
    message.content = content
    message.status = status
    message.error_message = error_message
    message.can_retry = can_retry
    message.request_json = dumps_for_storage(request)
    message.response_json = dumps_for_storage(response)
    conversation.capability = "video"
    conversation.model_group_id = model_group_id or conversation.model_group_id
    conversation.sub_model_id = sub_model_id or conversation.sub_model_id
    conversation.updated_at = utcnow()
    delete_duplicate_video_task_messages(db, conversation, message, task_id)
    db.flush()
    return message


def find_image_task_message(conversation: Conversation, task_id: str) -> ConversationMessage | None:
    for message in conversation.messages:
        if message.role == "assistant" and message.capability == "image" and message.content == task_id:
            return message
    for message in conversation.messages:
        if message.role != "assistant" or message.capability != "image":
            continue
        response = load_message_response(message)
        if response_matches_task(response, task_id) or pick_nested_task_id(response) == task_id:
            return message
    return None


def find_legacy_local_image_task_message(conversation: Conversation) -> ConversationMessage | None:
    candidates = [
        message
        for message in conversation.messages
        if message.role == "assistant"
        and message.capability == "image"
        and message.status in {"error", "processing"}
    ]
    return candidates[0] if len(candidates) == 1 else None


def delete_duplicate_image_task_messages(db: Session, conversation: Conversation, keep_message: ConversationMessage, task_id: str) -> None:
    for message in list(conversation.messages):
        if message.id == keep_message.id:
            continue
        if message.role != "assistant" or message.capability != "image":
            continue
        response = load_message_response(message)
        if message.content == task_id or response_matches_task(response, task_id) or pick_nested_task_id(response) == task_id:
            db.delete(message)


def mark_image_task_message(
    db: Session,
    conversation: Conversation,
    user: User,
    *,
    task_id: str,
    model_group_id: str,
    sub_model_id: str,
    status: str,
    content: str,
    error_message: str = "",
    can_retry: bool = False,
    request: Any = None,
    response: Any = None,
) -> ConversationMessage:
    message = find_image_task_message(conversation, task_id)
    if message is None:
        message = add_message(
            db,
            conversation,
            user,
            role="assistant",
            capability="image",
            content=content,
            status=status,
            error_message=error_message,
            can_retry=can_retry,
            model_group_id=model_group_id,
            sub_model_id=sub_model_id,
            request=request,
            response=response,
        )
        return message

    message.model_group_id = model_group_id
    message.sub_model_id = sub_model_id
    message.content = content
    message.status = status
    message.error_message = error_message
    message.can_retry = can_retry
    message.request_json = dumps_for_storage(request)
    message.response_json = dumps_for_storage(response)
    conversation.capability = "image"
    conversation.model_group_id = model_group_id or conversation.model_group_id
    conversation.sub_model_id = sub_model_id or conversation.sub_model_id
    conversation.updated_at = utcnow()
    delete_duplicate_image_task_messages(db, conversation, message, task_id)
    db.flush()
    return message


def new_long_task_id(prefix: str) -> str:
    return f"{prefix}{uuid4().hex}"


def is_text_long_task_id(task_id: str) -> bool:
    return task_id.startswith(TEXT_LONG_TASK_PREFIX)


def is_image_long_task_id(task_id: str) -> bool:
    return task_id.startswith(IMAGE_LONG_TASK_PREFIX)


def load_message_response(message: ConversationMessage) -> dict[str, Any]:
    try:
        parsed = json.loads(message.response_json or "{}")
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def load_message_request(message: ConversationMessage | None) -> dict[str, Any]:
    if not message:
        return {}
    try:
        parsed = json.loads(message.request_json or "{}")
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def response_matches_task(response: dict[str, Any], task_id: str) -> bool:
    return task_id in {
        str(response.get("taskId") or ""),
        str(response.get("localTaskId") or ""),
        str(response.get("providerTaskId") or ""),
    }


def find_text_task_message(conversation: Conversation, task_id: str) -> ConversationMessage | None:
    for message in conversation.messages:
        if message.role == "assistant" and message.capability == "text" and message.content == task_id:
            return message
    for message in conversation.messages:
        if message.role != "assistant" or message.capability != "text":
            continue
        if response_matches_task(load_message_response(message), task_id):
            return message
    return None


def serialize_text_task_result(conversation: Conversation, message: ConversationMessage, task_id: str) -> dict[str, Any]:
    status = "completed" if message.status == "success" else "failed" if message.status == "error" else "processing"
    raw = load_message_response(message) or {"taskId": task_id, "status": status}
    return {
        "taskId": task_id,
        "status": status,
        "content": message.content if message.status == "success" else "",
        "usage": raw.get("usage") if isinstance(raw.get("usage"), dict) else None,
        "raw": raw,
        "conversation": serialize_conversation(conversation).model_dump(),
        "assistantMessage": serialize_message(message).model_dump(),
    }


def serialize_local_image_task_result(conversation: Conversation, message: ConversationMessage, task_id: str) -> dict[str, Any]:
    status = "completed" if message.status == "success" else "failed" if message.status == "error" else "processing"
    raw = load_message_response(message) or {"taskId": task_id, "status": status}
    next_task_id = message.content if message.status == "processing" and message.content and message.content != task_id else task_id
    images = []
    for asset in message.assets:
        if asset.asset_type != "image" or not asset.url:
            continue
        try:
            metadata = json.loads(asset.metadata_json or "{}")
        except ValueError:
            metadata = {}
        images.append(
            {
                "src": asset.url,
                "revisedPrompt": metadata.get("revisedPrompt") or raw.get("revisedPrompt", ""),
            }
        )
    result = {
        "taskId": next_task_id,
        "status": status,
        "progress": raw.get("progress") if isinstance(raw.get("progress"), (str, int, float)) else None,
        "images": images,
        "conversation": serialize_conversation(conversation).model_dump(),
        "assistantMessage": serialize_message(message).model_dump(),
    }
    if status != "failed":
        result["raw"] = raw
    return result


def credit_payload(db: Session, user: User) -> dict[str, Any]:
    return {"account": serialize_credit_account(get_or_create_credit_account(db, user.id))}


def attach_credit_payload(result: dict[str, Any], db: Session, user: User | None) -> dict[str, Any]:
    if user:
        result["credits"] = credit_payload(db, user)
    return result


def summarize_task_payload(raw: Any, *, task_id: str, status: str = "", video_url: str = "", images: list[Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"taskId": task_id}
    if status:
        payload["status"] = status
    if video_url:
        payload["videoUrl"] = video_url
    if images:
        payload["images"] = images[:3]
    if isinstance(raw, dict):
        for key in ("id", "task_id", "status", "code", "message", "progress"):
            if key in raw and key not in payload:
                payload[key] = raw[key]
    return payload


def record_generation_task_event(
    db: Session,
    *,
    task_id: str,
    event_type: str,
    status: str,
    user: User | None,
    model_group: Any | None,
    sub_model: Any | None,
    capability: str,
    endpoint: str,
    conversation_id: str = "",
    message_id: str = "",
    duration_ms: int = 0,
    message: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    if not task_id:
        return
    record_task_event(
        db,
        task_id=task_id,
        event_type=event_type,
        status=status,
        user_id=user.id if user else None,
        model_group_id=getattr(model_group, "id", None) if model_group else None,
        sub_model_id=getattr(sub_model, "id", None) if sub_model else None,
        capability=capability,
        endpoint=endpoint,
        conversation_id=conversation_id,
        message_id=message_id,
        duration_ms=duration_ms,
        message=message,
        payload=payload or {},
    )


def prepare_generation_credit(
    db: Session,
    *,
    user: User | None,
    capability: str,
    model_group: Any | None,
    sub_model: Any | None,
    conversation_id: str = "",
    message_id: str = "",
    task_id: str = "",
    quantity: int = 1,
    multiplier: int = 1,
    metadata: dict[str, Any] | None = None,
) -> Any | None:
    estimate = estimate_credit_price(
        db,
        user=user,
        capability=capability,
        model_group=model_group,
        sub_model=sub_model,
    )
    if not estimate.enabled or estimate.price <= 0:
        return None
    if not user:
        raise HTTPException(status_code=401, detail={"message": "请先登录后再使用该模型。"})
    clean_quantity = max(1, int(quantity or 1))
    clean_multiplier = max(1, int(multiplier or 1))
    reserve_metadata = {
        "priceSource": estimate.source,
        "unitPrice": estimate.price,
        "quantity": clean_quantity,
        **(metadata or {}),
    }
    if clean_multiplier > 1:
        reserve_metadata["multiplier"] = clean_multiplier
        reserve_metadata["effectiveUnitPrice"] = estimate.price * clean_multiplier
    return reserve_generation_credits(
        db,
        user=user,
        capability=capability,
        price=estimate.price * clean_quantity * clean_multiplier,
        model_group_id=getattr(model_group, "id", "") if model_group else "",
        sub_model_id=getattr(sub_model, "id", "") if sub_model else "",
        conversation_id=conversation_id,
        message_id=message_id,
        task_id=task_id,
        metadata=reserve_metadata,
    )


def reserve_id_from_message(message: ConversationMessage | None) -> str:
    if not message:
        return ""
    return str(load_message_response(message).get("creditReserveId") or "")


def find_credit_reserve_for_task(
    db: Session,
    *,
    message: ConversationMessage | None = None,
    task_id: str = "",
    conversation_id: str = "",
) -> Any | None:
    reserve_id = reserve_id_from_message(message)
    return find_reserved_transaction(
        db,
        transaction_id=reserve_id,
        task_id=task_id,
        conversation_id=conversation_id,
        message_id=message.id if message else "",
    )


def capture_credit_for_message(db: Session, message: ConversationMessage | None, *, task_id: str = "", conversation_id: str = "") -> None:
    reserve = find_credit_reserve_for_task(db, message=message, task_id=task_id, conversation_id=conversation_id)
    if reserve:
        capture_generation_credits(db, reserve.id)


def refund_credit_for_message(
    db: Session,
    message: ConversationMessage | None,
    *,
    task_id: str = "",
    conversation_id: str = "",
    reason: str = "生成失败自动退款",
) -> None:
    reserve = find_credit_reserve_for_task(db, message=message, task_id=task_id, conversation_id=conversation_id)
    if reserve:
        refund_generation_credits(db, reserve.id, reason=reason)


async def wait_for_forward_or_handoff(
    task: asyncio.Task[tuple[httpx.Response, dict[str, Any] | str]],
    settings: Settings,
) -> tuple[bool, tuple[httpx.Response, dict[str, Any] | str] | None]:
    timeout = max(0.0, settings.long_request_handoff_seconds)
    done, _pending = await asyncio.wait({task}, timeout=timeout)
    if task not in done:
        return False, None
    return True, await task


def update_async_message_error(
    db: Session,
    conversation: Conversation,
    message: ConversationMessage,
    *,
    raw: Any,
    fallback: str,
    public_message: str | None = None,
) -> str:
    error_message = public_message or pick_error_message(raw, fallback)
    message.content = ""
    message.status = "error"
    message.error_message = error_message
    message.can_retry = True
    message.response_json = dumps_for_storage(raw)
    conversation.updated_at = utcnow()
    db.flush()
    return error_message


def should_return_generation_failure_payload(response: httpx.Response) -> bool:
    return response.status_code in {502, 503, 504}


def fail_async_message_after_exception(
    db: Session,
    *,
    user_id: str,
    conversation_id: str,
    message_id: str,
    capability: str,
    endpoint: str,
    started_at: float,
    model_group_id: str | None,
    sub_model_id: str | None,
    request_payload: dict[str, Any],
    task_id: str,
    exc: Exception,
) -> None:
    try:
        db.rollback()
        user = db.get(User, user_id)
        message = db.get(ConversationMessage, message_id)
        conversation = db.get(Conversation, conversation_id)
        if not user or not message or not conversation:
            return
        raw = {
            "taskId": task_id,
            "status": "failed",
            "error": {
                "message": "Background task failed.",
                "type": exc.__class__.__name__,
            },
        }
        error_message = update_async_message_error(
            db,
            conversation,
            message,
            raw=raw,
            fallback=f"{capability} request failed.",
            public_message=GENERATION_FAILED_MESSAGE,
        )
        refund_credit_for_message(db, message, task_id=task_id, conversation_id=conversation_id)
        message.request_json = dumps_for_storage(request_payload)
        record_task_event(
            db,
            task_id=task_id,
            event_type="failed",
            status="error",
            user_id=user.id,
            model_group_id=model_group_id,
            sub_model_id=sub_model_id,
            capability=capability,
            endpoint=endpoint,
            conversation_id=conversation_id,
            message_id=message_id,
            duration_ms=elapsed_ms(started_at),
            message=error_message,
            payload=raw,
        )
        if model_group_id and sub_model_id:
            record_call_log(
                db,
                user=user,
                model_group_id=model_group_id,
                sub_model_id=sub_model_id,
                capability=capability,
                endpoint=endpoint,
                status="error",
                duration_ms=elapsed_ms(started_at),
                error_message=error_message,
                conversation_id=conversation_id,
                message_id=message_id,
            )
        else:
            db.commit()
    except Exception:
        db.rollback()


async def complete_text_long_task(
    forward_task: asyncio.Task[tuple[httpx.Response, dict[str, Any] | str]],
    *,
    started_at: float,
    user_id: str,
    conversation_id: str,
    message_id: str,
    model_group_id: str,
    sub_model_id: str,
    body: dict[str, Any],
    task_id: str,
) -> None:
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        message = db.get(ConversationMessage, message_id)
        if not user or not message:
            return
        conversation = db.get(Conversation, conversation_id)
        if not conversation:
            return
        try:
            response, raw = await forward_task
        except httpx.TimeoutException:
            response, raw = httpx.Response(504, text="504 Gateway Timeout"), "504 Gateway Timeout"
        except httpx.HTTPError:
            response, raw = httpx.Response(503, text="502 Bad Gateway"), "502 Bad Gateway"
        duration_ms = elapsed_ms(started_at)
        if not response.is_success or not isinstance(raw, dict):
            error_message = update_async_message_error(
                db,
                conversation,
                message,
                raw=raw,
                fallback="文案请求失败。",
                public_message=GENERATION_FAILED_MESSAGE,
            )
            refund_credit_for_message(db, message, task_id=task_id, conversation_id=conversation_id)
            record_call_log(
                db,
                user=user,
                model_group_id=model_group_id,
                sub_model_id=sub_model_id,
                capability="text",
                endpoint="/api/proxy/text",
                status="error",
                duration_ms=duration_ms,
                error_message=error_message,
                conversation_id=conversation_id,
                message_id=message_id,
            )
            return
        content = pick_text_content(raw)
        message.content = content
        message.status = "success"
        message.error_message = ""
        message.can_retry = False
        message.request_json = dumps_for_storage(body)
        message.response_json = dumps_for_storage({"taskId": task_id, "status": "completed", **raw})
        capture_credit_for_message(db, message, task_id=task_id, conversation_id=conversation_id)
        conversation.updated_at = utcnow()
        db.flush()
        record_call_log(
            db,
            user=user,
            model_group_id=model_group_id,
            sub_model_id=sub_model_id,
            capability="text",
            endpoint="/api/proxy/text",
            status="success",
            duration_ms=duration_ms,
            prompt_summary=str(body.get("messages", ""))[:512],
            usage=raw.get("usage"),
            conversation_id=conversation_id,
            message_id=message_id,
        )
    except Exception as exc:
        fail_async_message_after_exception(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            capability="text",
            endpoint="/api/proxy/text",
            started_at=started_at,
            model_group_id=model_group_id,
            sub_model_id=sub_model_id,
            request_payload=body,
            task_id=task_id,
            exc=exc,
        )
    finally:
        db.close()


async def complete_image_long_task(
    forward_task: asyncio.Task[tuple[httpx.Response, dict[str, Any] | str]],
    *,
    started_at: float,
    user_id: str,
    conversation_id: str,
    message_id: str,
    model_group_id: str | None,
    sub_model_id: str | None,
    body: dict[str, Any],
    task_id: str,
) -> None:
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        message = db.get(ConversationMessage, message_id)
        if not user or not message:
            return
        conversation = db.get(Conversation, conversation_id)
        if not conversation:
            return
        try:
            response, raw = await forward_task
        except httpx.TimeoutException:
            response, raw = httpx.Response(504, text="504 Gateway Timeout"), "504 Gateway Timeout"
        except httpx.HTTPError:
            response, raw = httpx.Response(503, text="502 Bad Gateway"), "502 Bad Gateway"
        duration_ms = elapsed_ms(started_at)
        if not response.is_success or not isinstance(raw, dict):
            public_message = generation_public_error_message(raw, response.status_code)
            failure_raw = {
                "taskId": task_id,
                "localTaskId": task_id,
                "status": "failed",
                "upstream": sanitize_error_raw(raw),
            }
            error_message = update_async_message_error(
                db,
                conversation,
                message,
                raw=failure_raw,
                fallback="图片请求失败。",
                public_message=public_message,
            )
            refund_credit_for_message(db, message, task_id=task_id, conversation_id=conversation_id)
            record_task_event(
                db,
                task_id=task_id,
                event_type="failed",
                status="error",
                user_id=user.id,
                model_group_id=model_group_id,
                sub_model_id=sub_model_id,
                capability="image",
                endpoint="/api/proxy/image",
                conversation_id=conversation_id,
                message_id=message_id,
                duration_ms=duration_ms,
                message=error_message,
                payload=failure_raw,
            )
            if model_group_id and sub_model_id:
                record_call_log(
                    db,
                    user=user,
                    model_group_id=model_group_id,
                    sub_model_id=sub_model_id,
                    capability="image",
                    endpoint="/api/proxy/image",
                    status="error",
                    duration_ms=duration_ms,
                    error_message=error_message,
                    conversation_id=conversation_id,
                    message_id=message_id,
                )
            else:
                db.commit()
            return
        images, safe_raw = extract_images_from_response(raw)
        provider_task_id = pick_nested_task_id(raw)
        task_status_source = first_string_at_paths(
            raw,
            [("status",), ("data", "status"), ("data", "data", "status"), ("result", "status"), ("output", "status")],
        )
        task_status = normalize_task_status(str(task_status_source or "processing"))
        if provider_task_id and not images and task_status != "failed":
            message.content = provider_task_id
            message.status = "processing"
            message.error_message = ""
            message.can_retry = False
            message.response_json = dumps_for_storage({
                "taskId": task_id,
                "localTaskId": task_id,
                "providerTaskId": provider_task_id,
                "status": "processing",
                "upstream": safe_raw,
            })
        else:
            failures: list[dict[str, Any]] = []
            if images and image_request_is_4k(body):
                images, failures = await validate_4k_images(images, str(body.get("size") or ""))
            message.content = "completed" if images else ""
            message.status = "success" if images else "error"
            message.error_message = "" if images else "图片请求没有返回有效图片。"
            if failures and not images:
                message.error_message = failures[0]["message"]
            message.can_retry = not images
            message.response_json = dumps_for_storage({"taskId": task_id, "status": "completed" if images else "failed", "upstream": safe_raw})
            if failures:
                message.response_json = dumps_for_storage({
                    "taskId": task_id,
                    "status": "completed" if images else "failed",
                    "upstream": safe_raw,
                    "failures": failures[:5],
                })
            if images:
                capture_credit_for_message(db, message, task_id=task_id, conversation_id=conversation_id)
            else:
                refund_credit_for_message(db, message, task_id=task_id, conversation_id=conversation_id)
            db.query(GeneratedAsset).filter(GeneratedAsset.message_id == message.id).delete()
            for image in images:
                add_asset(
                    db,
                    message,
                    user,
                    capability="image",
                    asset_type="image",
                    url=image["src"],
                    metadata={"taskId": task_id, "revisedPrompt": image.get("revisedPrompt")},
                )
        event_type = "completed" if message.status == "success" else "failed" if message.status == "error" else "updated"
        record_task_event(
            db,
            task_id=task_id,
            event_type=event_type,
            status=message.status if message.status != "error" else "error",
            user_id=user.id,
            model_group_id=model_group_id,
            sub_model_id=sub_model_id,
            capability="image",
            endpoint="/api/proxy/image",
            conversation_id=conversation_id,
            message_id=message_id,
            duration_ms=duration_ms,
            message=message.error_message or message.status,
            payload=summarize_task_payload(
                safe_raw,
                task_id=task_id,
                status="completed" if message.status == "success" else "failed" if message.status == "error" else "processing",
                images=images,
            ),
        )
        message.request_json = dumps_for_storage(body)
        conversation.updated_at = utcnow()
        db.flush()
        if model_group_id and sub_model_id:
            record_call_log(
                db,
                user=user,
                model_group_id=model_group_id,
                sub_model_id=sub_model_id,
                capability="image",
                endpoint="/api/proxy/image",
                status="success" if message.status != "error" else "error",
                duration_ms=duration_ms,
                prompt_summary=str(body.get("prompt", ""))[:512],
                usage=raw.get("usage"),
                conversation_id=conversation_id,
                message_id=message_id,
            )
        else:
            db.commit()
    except Exception as exc:
        fail_async_message_after_exception(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            capability="image",
            endpoint="/api/proxy/image",
            started_at=started_at,
            model_group_id=model_group_id,
            sub_model_id=sub_model_id,
            request_payload=body,
            task_id=task_id,
            exc=exc,
        )
    finally:
        db.close()


async def complete_image_batch_task(
    *,
    started_at: float,
    user_id: str,
    conversation_id: str,
    message_id: str,
    model_group_id: str | None,
    sub_model_id: str | None,
    body: dict[str, Any],
    task_id: str,
    requested_count: int,
    base_url: str,
    target_url: str,
    api_key: str,
    edit_references: list[dict[str, Any]],
) -> None:
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        message = db.get(ConversationMessage, message_id)
        conversation = db.get(Conversation, conversation_id)
        if not user or not message or not conversation:
            return
        db.query(GeneratedAsset).filter(GeneratedAsset.message_id == message.id).delete()
        images: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        upstream_summaries: list[dict[str, Any]] = []

        for index in range(max(1, requested_count)):
            single_body = single_image_request_body(body)
            try:
                response, raw = await forward_image_request(
                    base_url=base_url,
                    target_url=target_url,
                    api_key=api_key,
                    body=single_body,
                    edit_references=edit_references,
                )
            except httpx.TimeoutException:
                response, raw = httpx.Response(504, text="504 Gateway Timeout"), "504 Gateway Timeout"
            except httpx.HTTPError:
                response, raw = httpx.Response(503, text="502 Bad Gateway"), "502 Bad Gateway"

            call_images: list[dict[str, Any]] = []
            safe_raw: Any = sanitize_error_raw(raw)
            if response.is_success and isinstance(raw, dict):
                extracted, safe_raw = extract_images_from_response(raw)
                remaining = max(0, requested_count - len(images))
                call_images = extracted[:remaining]
                validation_failures: list[dict[str, Any]] = []
                if call_images and image_request_is_4k(body):
                    call_images, validation_failures = await validate_4k_images(call_images, str(body.get("size") or ""))
                for image in call_images:
                    images.append(image)
                    add_asset(
                        db,
                        message,
                        user,
                        capability="image",
                        asset_type="image",
                        url=image["src"],
                        metadata={
                            "taskId": task_id,
                            "batchIndex": len(images),
                            "revisedPrompt": image.get("revisedPrompt"),
                        },
                    )
                for failure in validation_failures:
                    failures.append(
                        {
                            "index": index + 1,
                            **failure,
                            "statusCode": response.status_code,
                        }
                    )
                if not call_images and not validation_failures:
                    failures.append(
                        {
                            "index": index + 1,
                            "message": NO_IMAGE_RETURNED_MESSAGE,
                            "statusCode": response.status_code,
                        }
                    )
            else:
                failures.append(
                    {
                        "index": index + 1,
                        "message": generation_public_error_message(raw, response.status_code),
                        "statusCode": response.status_code,
                    }
                )

            upstream_summaries.append(
                {
                    "index": index + 1,
                    "statusCode": response.status_code,
                    "success": bool(call_images),
                    "imageCount": len(call_images),
                    "raw": safe_raw if isinstance(safe_raw, dict) else sanitize_error_raw(safe_raw),
                }
            )
            progress = f"{index + 1}/{requested_count}"
            message.content = task_id
            message.status = "processing"
            message.error_message = ""
            message.can_retry = False
            message.response_json = dumps_for_storage(
                {
                    "taskId": task_id,
                    "localTaskId": task_id,
                    "status": "processing",
                    "progress": progress,
                    "batch": {
                        "requestedCount": requested_count,
                        "completedCount": index + 1,
                        "successCount": len(images),
                        "failedCount": len(failures),
                    },
                    "images": images,
                    "upstream": upstream_summaries[-3:],
                }
            )
            conversation.updated_at = utcnow()
            db.commit()

            if len(images) >= requested_count:
                break

        has_images = bool(images)
        final_status = "completed" if has_images else "failed"
        message.content = "completed" if has_images else ""
        message.status = "success" if has_images else "error"
        message.error_message = "" if has_images else (failures[0]["message"] if failures else NO_IMAGE_RETURNED_MESSAGE)
        message.can_retry = not has_images
        message.request_json = dumps_for_storage(body)
        message.response_json = dumps_for_storage(
            {
                "taskId": task_id,
                "localTaskId": task_id,
                "status": final_status,
                "progress": f"{min(requested_count, len(upstream_summaries))}/{requested_count}",
                "batch": {
                    "requestedCount": requested_count,
                    "completedCount": min(requested_count, len(upstream_summaries)),
                    "successCount": len(images),
                    "failedCount": len(failures),
                },
                "images": images,
                "failures": failures[:5],
                "upstream": upstream_summaries[-5:],
            }
        )
        conversation.updated_at = utcnow()
        if has_images:
            capture_credit_for_message(db, message, task_id=task_id, conversation_id=conversation_id)
        else:
            refund_credit_for_message(db, message, task_id=task_id, conversation_id=conversation_id)
        duration_ms = elapsed_ms(started_at)
        record_task_event(
            db,
            task_id=task_id,
            event_type="completed" if has_images else "failed",
            status="success" if has_images else "error",
            user_id=user.id,
            model_group_id=model_group_id,
            sub_model_id=sub_model_id,
            capability="image",
            endpoint="/api/proxy/image",
            conversation_id=conversation_id,
            message_id=message_id,
            duration_ms=duration_ms,
            message=message.error_message or f"Batch image completed: {len(images)}/{requested_count}",
            payload={
                "taskId": task_id,
                "status": final_status,
                "requestedCount": requested_count,
                "successCount": len(images),
                "failedCount": len(failures),
                "images": images,
            },
        )
        db.flush()
        if model_group_id and sub_model_id:
            record_call_log(
                db,
                user=user,
                model_group_id=model_group_id,
                sub_model_id=sub_model_id,
                capability="image",
                endpoint="/api/proxy/image",
                status="success" if has_images else "error",
                duration_ms=duration_ms,
                prompt_summary=str(body.get("prompt", ""))[:512],
                usage=None,
                request_params={"quantity": requested_count},
                response_summary={
                    "taskId": task_id,
                    "successCount": len(images),
                    "failedCount": len(failures),
                },
                conversation_id=conversation_id,
                message_id=message_id,
            )
        else:
            db.commit()
    except Exception as exc:
        fail_async_message_after_exception(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            capability="image",
            endpoint="/api/proxy/image",
            started_at=started_at,
            model_group_id=model_group_id,
            sub_model_id=sub_model_id,
            request_payload=body,
            task_id=task_id,
            exc=exc,
        )
    finally:
        db.close()


def persist_generated_image_from_b64(value: str) -> str:
    try:
        image_bytes = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return persist_generated_image_data_url(value) if value.startswith("data:") else f"data:image/png;base64,{value}"
    file_name = f"{uuid4().hex}.png"
    (GENERATED_ASSET_DIR / file_name).write_bytes(image_bytes)
    return f"/api/assets/generated/{file_name}"


def persist_generated_image_data_url(value: str) -> str:
    reference = data_url_file_reference(value, 0)
    if not reference:
        return value
    suffix = Path(str(reference["filename"])).suffix.lower().lstrip(".") or "png"
    safe_suffix = "".join(char for char in suffix if char.isalnum())[:12] or "png"
    file_name = f"{uuid4().hex}.{safe_suffix}"
    (GENERATED_ASSET_DIR / file_name).write_bytes(reference["content"])
    return f"/api/assets/generated/{file_name}"


def safe_upload_file_name(value: str) -> str:
    raw = value.strip().replace("\\", "/").split("/")[-1] or "upload.bin"
    sanitized = "".join(char if char.isalnum() or char in "._-" else "-" for char in raw).strip(".-")
    return sanitized[:120] or "upload.bin"


def guess_image_media_type(file_name: str, fallback: str = "application/octet-stream") -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return fallback


def local_asset_data_url(value: str) -> str:
    path_prefixes = {
        "/api/assets/uploads/": LOCAL_UPLOAD_DIR,
        "/api/assets/generated/": GENERATED_ASSET_DIR,
    }
    for prefix, directory in path_prefixes.items():
        if not value.startswith(prefix):
            continue
        file_name = Path(value.removeprefix(prefix)).name
        file_path = directory / file_name
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail={"message": "Reference image not found."})
        media_type = guess_image_media_type(file_name, "image/png")
        encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
        return f"data:{media_type};base64,{encoded}"
    return value


def local_asset_file_reference(value: str) -> dict[str, Any] | None:
    path_prefixes = {
        "/api/assets/uploads/": LOCAL_UPLOAD_DIR,
        "/api/assets/generated/": GENERATED_ASSET_DIR,
    }
    for prefix, directory in path_prefixes.items():
        if not value.startswith(prefix):
            continue
        file_name = Path(value.removeprefix(prefix)).name
        file_path = directory / file_name
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail={"message": "Reference image not found."})
        return {
            "filename": file_name,
            "content": file_path.read_bytes(),
            "content_type": guess_image_media_type(file_name, "image/png"),
        }
    return None


def data_url_file_reference(value: str, index: int) -> dict[str, Any] | None:
    if not value.startswith("data:") or ";base64," not in value:
        return None
    header, encoded = value.split(",", 1)
    content_type = header.removeprefix("data:").split(";", 1)[0] or "image/png"
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return None
    suffix = "jpg" if content_type == "image/jpeg" else content_type.split("/")[-1] or "png"
    return {
        "filename": f"reference-{index}.{suffix}",
        "content": content,
        "content_type": content_type,
    }


def collect_image_edit_references(body: dict[str, Any]) -> list[dict[str, Any]]:
    references = body.get("image")
    if isinstance(references, str):
        items = [references]
    elif isinstance(references, list):
        items = [item for item in references if isinstance(item, str)]
    else:
        return []
    collected: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        local_reference = local_asset_file_reference(item)
        if local_reference:
            collected.append(local_reference)
            continue
        data_reference = data_url_file_reference(item, index)
        if data_reference:
            collected.append(data_reference)
    return collected


def normalize_image_reference_fields_for_adapter(body: dict[str, Any], adapter: str) -> dict[str, Any]:
    if adapter != "image-openai" or "image" in body or "images" not in body:
        return body
    normalized = copy.deepcopy(body)
    normalized["image"] = normalized.pop("images")
    return normalized


def expand_local_image_references(body: dict[str, Any]) -> dict[str, Any]:
    reference_key = "image" if "image" in body else "images" if "images" in body else "image"
    references = body.get(reference_key)
    if isinstance(references, str):
        body[reference_key] = local_asset_data_url(references)
        return body
    if isinstance(references, list):
        body[reference_key] = [local_asset_data_url(item) if isinstance(item, str) else item for item in references]
    return body


IMAGE_COUNT_KEYS = ("quantity", "n", "count", "num_images", "numImages")
FOUR_K_MIN_SIDE = 2160
FOUR_K_MIN_LONG_SIDE = 3840
FOUR_K_MAX_SIDE = 4096
FOUR_K_OUTPUT_MISMATCH_MESSAGE = "4K 生成未返回 4K 图片，请检查上游 4K Image API 网关配置。"
FOUR_K_PROBE_TIMEOUT_SECONDS = 6.0
FOUR_K_PROBE_MAX_BYTES = 5 * 1024 * 1024


def parse_image_size(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace(" ", "").replace("*", "x")
    if "x" not in normalized:
        return None
    left, right = normalized.split("x", 1)
    try:
        width = int(float(left))
        height = int(float(right))
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def parse_image_ratio(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace(" ", "").replace("/", ":")
    if ":" not in normalized:
        return None
    left, right = normalized.split(":", 1)
    try:
        width = float(left)
        height = float(right)
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def image_4k_size_for_ratio(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace(" ", "")
    fixed = {
        "16:9": "3840x2160",
        "9:16": "2160x3840",
        "1:1": "4096x4096",
        "4:3": "4096x3072",
        "3:4": "3072x4096",
    }
    if normalized in fixed:
        return fixed[normalized]
    # A value may arrive as an explicit "WxH" size (the frontend already maps the
    # selected ratio to a 4K size before sending). Preserve an already-4K size as-is
    # so we keep the requested aspect ratio instead of collapsing to a 4096 square,
    # otherwise fall back to deriving the aspect ratio from the size.
    explicit = parse_image_size(normalized)
    if explicit and min(explicit) >= FOUR_K_MIN_SIDE and max(explicit) >= FOUR_K_MIN_LONG_SIDE:
        return f"{explicit[0]}x{explicit[1]}"
    ratio = parse_image_ratio(normalized) or explicit
    if not ratio:
        return "4096x4096"
    width, height = ratio
    if width >= height:
        return f"4096x{max(1, round(FOUR_K_MAX_SIDE * height / width))}"
    return f"{max(1, round(FOUR_K_MAX_SIDE * width / height))}x4096"


def image_request_is_4k(body: dict[str, Any]) -> bool:
    size = parse_image_size(body.get("size"))
    if not size:
        return False
    width, height = size
    return max(width, height) >= FOUR_K_MIN_LONG_SIDE and (width * height) >= (FOUR_K_MIN_LONG_SIDE * FOUR_K_MIN_SIDE)


def local_generated_image_path(src: str) -> Path | None:
    prefix = "/api/assets/generated/"
    if not isinstance(src, str) or not src.startswith(prefix):
        return None
    file_name = Path(src.removeprefix(prefix)).name
    if not file_name:
        return None
    path = GENERATED_ASSET_DIR / file_name
    return path if path.is_file() else None


def jpeg_dimensions_from_bytes(data: bytes) -> tuple[int, int] | None:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(data):
            return None
        segment_length = int.from_bytes(data[index:index + 2], "big")
        if segment_length < 2:
            return None
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if index + 7 > len(data):
                return None
            height = int.from_bytes(data[index + 3:index + 5], "big")
            width = int.from_bytes(data[index + 5:index + 7], "big")
            return width, height
        index += segment_length
    return None


def webp_dimensions_from_bytes(data: bytes) -> tuple[int, int] | None:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    fourcc = data[12:16]
    try:
        if fourcc == b"VP8 ":
            if data[23:26] != b"\x9d\x01\x2a":
                return None
            width = int.from_bytes(data[26:28], "little") & 0x3FFF
            height = int.from_bytes(data[28:30], "little") & 0x3FFF
            return width, height
        if fourcc == b"VP8L":
            if data[20] != 0x2F:
                return None
            bits = int.from_bytes(data[21:25], "little")
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
            return width, height
        if fourcc == b"VP8X":
            width = int.from_bytes(data[24:27], "little") + 1
            height = int.from_bytes(data[27:30], "little") + 1
            return width, height
    except (IndexError, ValueError):
        return None
    return None


def image_dimensions_from_bytes(data: bytes) -> tuple[int, int] | None:
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if len(data) >= 4 and data[:2] == b"\xff\xd8":
        return jpeg_dimensions_from_bytes(data)
    if len(data) >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return webp_dimensions_from_bytes(data)
    return None


def local_image_dimensions(src: str) -> tuple[int, int] | None:
    path = local_generated_image_path(src)
    if not path:
        return None
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return image_dimensions_from_bytes(data)


def remote_image_url_is_probeable(url: str) -> bool:
    """Whether a returned image URL is safe to fetch for a 4K dimension check.

    Image URLs come from the operator-configured upstream gateway, but we still
    refuse obviously-internal targets (loopback / private / metadata ranges) given
    as literal IPs so a misconfigured upstream cannot turn the probe into an SSRF
    against the host. Hostnames are trusted (they must be publicly reachable for the
    browser to render them); DNS-rebinding is out of scope for this trusted source.
    """
    if not isinstance(url, str):
        return False
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").strip()
    if not host:
        return False
    if host.lower() in {"localhost", "ip6-localhost", "ip6-loopback"}:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


async def remote_image_dimensions(url: str) -> tuple[int, int] | None:
    if not remote_image_url_is_probeable(url):
        return None
    try:
        async with httpx.AsyncClient(
            timeout=FOUR_K_PROBE_TIMEOUT_SECONDS,
            trust_env=False,
            follow_redirects=True,
        ) as client:
            async with client.stream("GET", url) as response:
                if response.status_code >= 400:
                    return None
                buffer = bytearray()
                async for chunk in response.aiter_bytes():
                    buffer.extend(chunk)
                    if len(buffer) >= FOUR_K_PROBE_MAX_BYTES:
                        break
    except (httpx.HTTPError, OSError, ValueError):
        return None
    return image_dimensions_from_bytes(bytes(buffer))


async def resolve_image_dimensions(src: str) -> tuple[int, int] | None:
    local = local_image_dimensions(src)
    if local:
        return local
    return await remote_image_dimensions(src)


def image_dimensions_match_4k(dimensions: tuple[int, int] | None, target_size: str) -> bool:
    if not dimensions:
        return True
    target = parse_image_size(target_size)
    if not target:
        width, height = dimensions
        return min(width, height) >= FOUR_K_MIN_SIDE and max(width, height) >= FOUR_K_MIN_LONG_SIDE
    width, height = dimensions
    target_width, target_height = target
    return width >= target_width and height >= target_height


async def validate_4k_images(images: list[dict[str, Any]], target_size: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Measure each image and split into (valid, failures). An image whose actual
    resolution is below the requested 4K target is rejected as a failure so the
    caller can fail the generation and refund credits — we never pass a non-4K
    output off as a successful 4K result. Images we cannot measure (probe failed)
    are passed through to avoid nuking a paid generation on a transient infra blip."""
    valid: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for image in images:
        src = str(image.get("src") or "")
        dimensions = await resolve_image_dimensions(src)
        if image_dimensions_match_4k(dimensions, target_size):
            enriched = dict(image)
            if dimensions:
                enriched["width"], enriched["height"] = dimensions
            valid.append(enriched)
            continue
        failures.append(
            {
                "src": src,
                "width": dimensions[0],
                "height": dimensions[1],
                "targetSize": target_size,
                "message": FOUR_K_OUTPUT_MISMATCH_MESSAGE,
            }
        )
    return valid, failures


def normalize_image_4k_request(body: dict[str, Any], *, adapter: str, enable_4k: bool) -> tuple[dict[str, Any], bool, str]:
    if enable_4k and adapter != "image-openai":
        raise HTTPException(status_code=400, detail={"message": "当前图片模型不支持 4K 生成。"})
    normalized = copy.deepcopy(body)
    if enable_4k:
        target_size = image_4k_size_for_ratio(normalized.get("ratio") or normalized.get("aspect_ratio") or normalized.get("size") or "1:1")
        normalized["size"] = target_size
        return normalized, True, target_size
    if adapter == "image-openai" and image_request_is_4k(normalized):
        width, height = parse_image_size(normalized.get("size")) or (0, 0)
        return normalized, True, f"{width}x{height}"
    return normalized, False, ""


def requested_image_count(body: dict[str, Any]) -> int:
    for key in IMAGE_COUNT_KEYS:
        value = body.get(key)
        if isinstance(value, bool) or value in (None, ""):
            continue
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        if count > 1:
            return min(count, IMAGE_BATCH_MAX_COUNT)
    return 1


def single_image_request_body(body: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(body)
    for key in IMAGE_COUNT_KEYS:
        if key in normalized:
            normalized[key] = 1
    return normalized


async def forward_image_request(
    *,
    base_url: str,
    target_url: str,
    api_key: str,
    body: dict[str, Any],
    edit_references: list[dict[str, Any]],
) -> tuple[httpx.Response, dict[str, Any] | str]:
    request_body = copy.deepcopy(body)
    if edit_references:
        edit_data = {
            key: str(value)
            for key, value in request_body.items()
            if key != "image" and value is not None
        }
        edit_files = [
            ("image", (reference["filename"], reference["content"], reference["content_type"]))
            for reference in edit_references
        ]
        response, raw = await forward_multipart(target_url, api_key, data=edit_data, files=edit_files)
        if (not response.is_success or not isinstance(raw, dict)) and is_non_json_upstream_error(raw):
            generation_body = expand_local_image_references(copy.deepcopy(request_body))
            generation_url = resolve_url(base_url, "/v1/images/generations")
            response, raw = await forward_json("POST", generation_url, api_key, generation_body)
        return response, raw
    return await forward_json("POST", target_url, api_key, request_body)


def expand_local_video_references(value: Any) -> Any:
    if isinstance(value, dict):
        expanded: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"url", "image", "image_url", "img_url", "first_frame", "last_frame", "video_url", "audio_url"} and isinstance(item, str):
                expanded[key] = local_asset_data_url(item)
            else:
                expanded[key] = expand_local_video_references(item)
        return expanded
    if isinstance(value, str):
        return local_asset_data_url(value)
    if isinstance(value, list):
        return [expand_local_video_references(item) for item in value]
    return value


def extract_images_from_response(raw: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    safe_raw = copy.deepcopy(raw)
    images: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    def collect(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                collect(item)
            return
        if not isinstance(value, dict):
            return
        if any(isinstance(value.get(key), str) for key in ("url", "image_url", "imageUrl", "b64_json")):
            candidates.append(value)
        for key in ("data", "result", "output", "content", "metadata"):
            nested = value.get(key)
            if isinstance(nested, (dict, list)):
                collect(nested)

    collect(safe_raw.get("data"))
    for key in ("result", "output", "content", "metadata"):
        collect(safe_raw.get(key))
    if not candidates:
        collect(safe_raw)

    seen_sources: set[str] = set()
    for item in candidates:
        if not isinstance(item, dict):
            continue
        src = ""
        src_key = ""
        for key in ("url", "image_url", "imageUrl", "download_url"):
            if isinstance(item.get(key), str) and item[key].strip():
                src = item[key].strip()
                src_key = key
                break
        if src.startswith("data:") and ";base64," in src:
            persisted_src = persist_generated_image_data_url(src)
            if persisted_src != src:
                src = persisted_src
                item[src_key] = src
                item["source"] = "data_url_saved"
        if not src and isinstance(item.get("b64_json"), str):
            src = persist_generated_image_from_b64(item["b64_json"])
            item.pop("b64_json", None)
            item["url"] = src
            item["source"] = "b64_json_saved"
        if src and src not in seen_sources:
            seen_sources.add(src)
            images.append(
                {
                    "src": src,
                    "revisedPrompt": item.get("revised_prompt")
                    if isinstance(item.get("revised_prompt"), str)
                    else None,
                }
            )
    return images, safe_raw


def pick_image_query_payload(raw: dict[str, Any], task_id: str) -> dict[str, Any]:
    task_status = first_string_at_paths(
        raw,
        [
            ("status",),
            ("code",),
            ("data", "status"),
            ("data", "data", "status"),
            ("result", "status"),
            ("output", "status"),
        ],
    ) or ("completed" if extract_images_from_response(raw)[0] else "processing")
    progress = raw.get("progress")
    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    nested_data = data.get("data") if isinstance(data.get("data"), dict) else {}
    if progress is None:
        progress = data.get("progress")
    if progress is None:
        progress = nested_data.get("progress")
    images, safe_raw = extract_images_from_response(raw)
    status = normalize_task_status(str(task_status))
    if images and status not in {"failed", "error"}:
        status = "completed"
    if status not in {"completed", "processing"} and pick_video_task_error_message(raw, ""):
        status = "failed"
    return {
        "taskId": pick_nested_task_id(raw, task_id),
        "status": status,
        "progress": progress if isinstance(progress, (str, int, float)) else None,
        "images": images,
        "raw": safe_raw,
    }


def resolve_image_query_path(task_id: str) -> str:
    return f"/v1/images/generations/{quote(task_id)}"


def has_oversized_inline_reference(body: dict[str, Any]) -> bool:
    references = body.get("image")
    if references is None:
        references = body.get("images")
    if not isinstance(references, list):
        references = [references] if isinstance(references, str) else []
    return any(
        isinstance(item, str)
        and item.startswith("data:")
        and len(item) > MAX_INLINE_REFERENCE_LENGTH
        for item in references
    )


def safe_conversation_id(value: str) -> str:
    candidate = value.strip()
    return candidate if candidate.startswith("cnv_") else ""


def transient_conversation_id(value: str) -> str:
    candidate = value.strip()
    if candidate.startswith("local-conversation-"):
        return candidate
    return f"local-conversation-{uuid4()}"


def transient_error_conversation(
    *,
    conversation_id: str,
    capability: str,
    prompt: str,
    error_message: str,
) -> dict[str, Any]:
    now = utcnow().isoformat()
    resolved_conversation_id = transient_conversation_id(conversation_id)
    user_message = {
        "id": f"local-message-{uuid4()}",
        "role": "user",
        "capability": capability,
        "content": prompt,
        "status": "success",
        "errorMessage": "",
        "canRetry": False,
        "modelGroupId": None,
        "subModelId": None,
        "assets": [],
        "createdAt": now,
    }
    assistant_message = {
        "id": f"local-message-{uuid4()}",
        "role": "assistant",
        "capability": capability,
        "content": "",
        "status": "error",
        "errorMessage": error_message,
        "canRetry": True,
        "modelGroupId": None,
        "subModelId": None,
        "assets": [],
        "createdAt": now,
    }
    return {
        "conversation": {
            "id": resolved_conversation_id,
            "title": make_title(prompt),
            "capability": capability,
            "modelGroupId": None,
            "subModelId": None,
            "status": "active",
            "createdAt": now,
            "updatedAt": now,
            "messages": [user_message, assistant_message],
        },
        "assistantMessage": assistant_message,
    }


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def clean_http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "raw" in detail:
        clean_detail = dict(detail)
        clean_raw = sanitize_error_raw(clean_detail.get("raw"))
        if clean_raw is None:
            clean_detail.pop("raw", None)
        else:
            clean_detail["raw"] = clean_raw
        detail = clean_detail
    return JSONResponse(status_code=exc.status_code, content=jsonable_encoder({"detail": detail}), headers=exc.headers)


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


@app.get("/api/version")
async def version(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {
        "version": settings.build_version,
        "commitSha": settings.commit_sha,
        "buildTime": settings.build_time,
        "environment": settings.environment,
    }


@app.api_route("/api/assets/generated/{file_name}", methods=["GET", "HEAD"])
async def generated_asset(file_name: str) -> FileResponse:
    if "/" in file_name or "\\" in file_name or not file_name.endswith(".png"):
        raise HTTPException(status_code=404, detail={"message": "Asset not found."})
    file_path = GENERATED_ASSET_DIR / file_name
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail={"message": "Asset not found."})
    return FileResponse(file_path, media_type="image/png")


@app.api_route("/api/assets/uploads/{file_name}", methods=["GET", "HEAD"])
async def local_uploaded_asset(file_name: str) -> FileResponse:
    if "/" in file_name or "\\" in file_name:
        raise HTTPException(status_code=404, detail={"message": "Asset not found."})
    file_path = LOCAL_UPLOAD_DIR / file_name
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail={"message": "Asset not found."})
    return FileResponse(file_path, media_type=guess_image_media_type(file_name))


@app.post("/api/upload/local")
async def local_upload(
    request: Request,
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    check_rate_limit(
        limiter=rate_limiter,
        request=request,
        settings=settings,
        bucket="upload-local",
        limit=settings.rate_limit_upload_per_window,
        user_id="",
    )
    content_type = (file.content_type or "application/octet-stream").lower()
    if content_type == "image/jpg":
        content_type = "image/jpeg"
    if content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(status_code=400, detail={"message": "Only image references can be uploaded."})
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail={"message": "Upload file is empty."})
    safe_name = safe_upload_file_name(file.filename or "reference.png")
    file_name = f"{uuid4().hex}-{safe_name}"
    file_path = LOCAL_UPLOAD_DIR / file_name
    file_path.write_bytes(content)
    public_url = f"/api/assets/uploads/{file_name}"
    return {
        "id": f"local-upload-{uuid4()}",
        "fileName": safe_name,
        "publicUrl": public_url,
        "contentType": content_type,
        "localPreviewUrl": public_url,
    }


@app.get("/api/auth/me")
async def auth_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    user_payload = serialize_user(current_user).model_dump()
    user_payload["credits"] = serialize_credit_account(get_or_create_credit_account(db, current_user.id))
    return {"user": user_payload}


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
    grant_signup_bonus(db, user)
    create_session(db, response, user, client_ip_from_request(request))
    db.commit()
    user_payload = serialize_user(user).model_dump()
    user_payload["credits"] = serialize_credit_account(get_or_create_credit_account(db, user.id))
    return {"user": user_payload}


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
    create_session(db, response, user, client_ip_from_request(request))
    db.commit()
    user_payload = serialize_user(user).model_dump()
    user_payload["credits"] = serialize_credit_account(get_or_create_credit_account(db, user.id))
    return {"user": user_payload}


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
    create_session(db, response, user, client_ip_from_request(request))
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
    redirect_target = safe_frontend_path(next_url or state or "#/settings")
    response = RedirectResponse(frontend_redirect_url(settings, redirect_target), status_code=307)
    try:
        profile = await exchange_official_code(code, settings)
        user = upsert_user(db, **profile)
        db.flush()
        create_session(db, response, user, client_ip_from_request(request))
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
    create_session(db, response, user, client_ip_from_request(request))
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


@app.post("/api/users/me/password")
async def change_my_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    new_password = payload.newPassword.strip()
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail={"message": "新密码长度不能少于 6 位。"})
    credential = (
        db.query(UserCredential)
        .filter(UserCredential.user_id == current_user.id, UserCredential.provider == "local")
        .one_or_none()
    )
    if not credential:
        raise HTTPException(status_code=400, detail={"message": "当前账号未使用本地密码登录，无法修改密码。"})
    if not verify_password(payload.currentPassword, credential.password_hash):
        raise HTTPException(status_code=400, detail={"message": "当前密码不正确。"})
    credential.password_hash = hash_password(new_password)
    credential.failed_attempts = 0
    credential.locked_until = None
    db.commit()
    return {"ok": True}


@app.get("/api/credits/me")
async def my_credits(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    account = get_or_create_credit_account(db, current_user.id)
    transactions = list_credit_transactions(db, user_id=current_user.id, limit=30)
    return {
        "account": serialize_credit_account(account),
        "transactions": [serialize_credit_transaction(item) for item in transactions],
    }


@app.post("/api/credits/notifications/{transaction_id}/dismiss")
async def dismiss_my_credit_notification(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    transaction = dismiss_credit_grant_notification(db, user_id=current_user.id, transaction_id=transaction_id)
    return {"transaction": serialize_credit_transaction(transaction)}


@app.get("/api/credits/pricing/estimate")
async def credit_pricing_estimate(
    capability: str,
    modelGroupId: str = "",
    subModelId: str = "",
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> dict[str, Any]:
    model_group = db.get(ModelGroup, modelGroupId) if modelGroupId else None
    sub_model = db.get(SubModel, subModelId) if subModelId else None
    estimate = estimate_credit_price(
        db,
        user=current_user,
        capability=capability,
        model_group=model_group,
        sub_model=sub_model,
    )
    return {"estimate": serialize_price_estimate(estimate)}


@app.get("/api/api-keys")
async def api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"apiKeys": [serialize_api_key(item).model_dump() for item in list_api_keys(db, current_user)]}


@app.get("/api/models")
async def models(
    current_user: User | None = Depends(get_optional_current_user),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    can_edit_public = can(current_user, "model:update", settings)
    return {
        "models": [
            serialize_model(item, current_user, is_admin=can_edit_public).model_dump()
            for item in list_model_groups(db, current_user)
        ]
    }


@app.get("/api/catalog/models")
async def catalog_models(
    capability: str = Query(default=""),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    safe_capability = capability if capability in {"", "text", "image", "video"} else ""
    return {"models": [serialize_catalog_model(item).model_dump() for item in list_catalog_models(db, safe_capability)]}


@app.post("/api/catalog/kkyi/sync")
async def sync_kkyi_catalog(
    payload: KkyiCatalogSyncRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    _ = current_user
    bearer_token = payload.bearerToken.strip() or settings.kkyi_catalog_bearer_token
    if not bearer_token:
        raise HTTPException(status_code=400, detail={"message": "缺少 KKYi 授权 Token。"})
    try:
        details = await fetch_kkyi_catalog_details(
            base_url=settings.kkyi_catalog_base_url,
            bearer_token=bearer_token,
            model_type=payload.modelType,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail={"message": "同步 KKYi 模型目录失败。"}) from exc
    synced = sync_catalog_details(db, details)
    icon_updates = normalize_existing_catalog_icons(db)
    if synced or icon_updates:
        backfill_all_catalog_links(db)
        db.commit()
    return {
        "synced": len(synced),
        "models": [serialize_catalog_model(item).model_dump() for item in synced],
    }


@app.post("/api/models")
async def create_model(
    payload: ModelCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    can_publish_public = can(current_user, "model:publish", settings)
    can_edit_public = can(current_user, "model:update", settings)
    model = create_model_group(db, current_user, payload, is_admin=can_publish_public)
    return {"model": serialize_model(model, current_user, is_admin=can_edit_public).model_dump()}


@app.put("/api/models/{model_id}")
async def update_model(
    model_id: str,
    payload: ModelUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    can_edit_public = can(current_user, "model:update", settings)
    model = update_model_group(
        db,
        current_user,
        model_id,
        payload,
        is_admin=can_edit_public,
        can_publish_public=can(current_user, "model:publish", settings),
        can_unpublish_public=can(current_user, "model:unpublish", settings),
    )
    return {"model": serialize_model(model, current_user, is_admin=can_edit_public).model_dump()}


@app.delete("/api/models/{model_id}")
async def delete_model(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, bool]:
    delete_model_group(db, current_user, model_id, is_admin=can(current_user, "model:delete", settings))
    return {"ok": True}


@app.post("/api/models/{model_id}/primary")
async def set_model_primary(
    model_id: str,
    payload: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    sub_model_id = str(payload.get("subModelId") or "").strip()
    if not sub_model_id:
        raise HTTPException(status_code=400, detail={"message": "缺少子模型 ID。"})
    can_edit_public = can(current_user, "model:update", settings)
    model = set_primary_sub_model(db, current_user, model_id, sub_model_id, is_admin=can_edit_public)
    return {"model": serialize_model(model, current_user, is_admin=can_edit_public).model_dump()}


@app.post("/api/models/{model_id}/sync")
async def sync_model_list(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    can_edit_public = can(current_user, "model:update", settings)
    model = get_model_group(db, current_user, model_id, is_admin=can_edit_public, require_edit=True)
    api_key = model.api_key
    target_url = resolve_url(api_key.base_url, "/v1/models")
    started_at = time.perf_counter()
    try:
        response, raw = await forward_json("GET", target_url, api_key=decrypt_secret(api_key.api_key_ciphertext))
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail={"message": "连接供应商超时，请检查 baseURL 或稍后重试。"})
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail={"message": "无法连接到该供应商，请检查 baseURL 是否正确、网络是否可达。"})
    duration_ms = elapsed_ms(started_at)
    if not response.is_success or not isinstance(raw, dict):
        raise upstream_error(raw, "获取模型列表失败。", response.status_code)
    result = sync_models_from_raw(db, model, raw, duration_ms, user=current_user, is_admin=can_edit_public)
    return result.model_dump()


@app.get("/api/admin/models")
async def admin_models(
    capability: str = "all",
    search: str = "",
    publicState: str = "all",
    page: int = 1,
    pageSize: int = 20,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "model:view", settings)
    safe_page = max(page, 1)
    safe_page_size = min(max(pageSize, 1), 100)
    total = count_admin_models(db, capability=capability, search=search, public_state=publicState)
    return {
        "models": [
            serialize_model(item, admin, is_admin=True).model_dump()
            for item in list_admin_models(
                db,
                capability=capability,
                search=search,
                public_state=publicState,
                page=safe_page,
                page_size=safe_page_size,
            )
        ],
        "total": total,
        "page": safe_page,
        "pageSize": safe_page_size,
    }


def _http_exception_message(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        message = detail.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    if isinstance(detail, str) and detail.strip():
        return detail.strip()
    return str(exc.status_code)


def _health_result_status(health: dict[str, Any]) -> str:
    latest = health.get("latest")
    if isinstance(latest, dict):
        return str(latest.get("status") or "unknown")
    return str(health.get("status") or "unknown")


async def run_admin_model_health_check_for_model(
    model_id: str,
    request: Request,
    db: Session,
    admin: User,
    settings: Settings,
) -> dict[str, Any]:
    check_rate_limit(
        limiter=rate_limiter,
        request=request,
        settings=settings,
        bucket=f"admin-model-health-check:{model_id}",
        limit=settings.rate_limit_model_test_per_window,
        user_id=admin.id,
    )
    model = db.get(ModelGroup, model_id)
    if not model:
        raise HTTPException(status_code=404, detail={"message": "模型不存在。"})
    sub_model = None
    if model.primary_sub_model_id:
        sub_model = db.get(SubModel, model.primary_sub_model_id)
    if not sub_model:
        sub_model = next((item for item in model.sub_models if item.status == "active"), None)
    if not sub_model:
        raise HTTPException(status_code=400, detail={"message": "模型缺少可测试的子模型。"})

    started_at = time.perf_counter()
    try:
        api_key = sub_model.api_key or model.api_key
        if not api_key:
            raise ValueError("API key configuration is missing")
        adapter = sub_model.adapter or model.adapter
        body = build_test_body(model.capability, sub_model.model_name, adapter)
        target_path = resolve_test_path(model.capability, adapter)
        if is_kkyi_video_model(sub_model, api_key.base_url):
            target_path = "/v1/videos"
            body = normalize_kkyi_video_body(body, sub_model.model_name, sub_model)
        target_url = resolve_url(api_key.base_url, target_path)
        response, raw = await forward_json("POST", target_url, decrypt_secret(api_key.api_key_ciphertext), body)
        duration_ms = elapsed_ms(started_at)
        status_value = "success" if response.is_success and isinstance(raw, dict) else "failed"
        message = "连接正常。" if status_value == "success" else pick_error_message(raw, "模型测试失败。")
        record_model_health_check(
            db,
            admin=admin,
            model=model,
            status=status_value,
            duration_ms=duration_ms,
            message=message,
            raw={"statusCode": response.status_code, "body": raw if isinstance(raw, dict) else str(raw)[:500]},
            sub_model_id=sub_model.id,
        )
    except Exception as exc:
        db.rollback()
        duration_ms = elapsed_ms(started_at)
        raw_error = {"error": exc.__class__.__name__}
        if str(exc):
            raw_error["message"] = str(exc)[:300]
        record_model_health_check(
            db,
            admin=admin,
            model=model,
            status="failed",
            duration_ms=duration_ms,
            message="模型测试失败，请检查接口配置。",
            raw=raw_error,
            sub_model_id=sub_model.id,
        )
    health = get_model_health(db, model_id, include_raw_json=can(admin, "record:raw_json", settings))
    return {"modelId": model_id, "status": _health_result_status(health), "health": health}


def _model_batch_error_result(model_id: str, exc: HTTPException) -> dict[str, Any]:
    return {
        "modelId": model_id,
        "status": "error",
        "error": {"statusCode": exc.status_code, "message": _http_exception_message(exc)},
    }


@app.post("/api/admin/models/batch-health-check")
async def admin_batch_model_health_check(
    payload: AdminModelBatchRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "model:test", settings)
    results: list[dict[str, Any]] = []
    for model_id in payload.modelIds:
        try:
            results.append(await run_admin_model_health_check_for_model(model_id, request, db, admin, settings))
        except HTTPException as exc:
            results.append(_model_batch_error_result(model_id, exc))
        except Exception as exc:
            db.rollback()
            results.append(
                {
                    "modelId": model_id,
                    "status": "error",
                    "error": {"statusCode": 500, "message": str(exc)[:300] or exc.__class__.__name__},
                }
            )
    return {"results": results}


@app.post("/api/admin/models/remove-unavailable")
async def admin_remove_unavailable_models(
    payload: AdminModelBatchRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "model:delete", settings)
    removed_ids: list[str] = []
    skipped: list[dict[str, Any]] = []
    is_admin = is_admin_user(admin, settings)

    for model_id in payload.modelIds:
        model = db.get(ModelGroup, model_id)
        if not model:
            skipped.append({"modelId": model_id, "reason": "not_found"})
            continue
        health = get_model_health(db, model_id, include_raw_json=False)
        latest = health.get("latest")
        if not isinstance(latest, dict):
            skipped.append({"modelId": model_id, "reason": "no_health_check"})
            continue
        latest_status = str(latest.get("status") or "").strip().lower()
        if latest_status == "success":
            skipped.append({"modelId": model_id, "reason": "latest_health_success"})
            continue
        if latest_status not in {"failed", "error"}:
            skipped.append({"modelId": model_id, "reason": "latest_health_not_failed"})
            continue
        try:
            delete_model_group(db, admin, model_id, is_admin=is_admin)
            removed_ids.append(model_id)
        except HTTPException as exc:
            db.rollback()
            skipped.append(
                {
                    "modelId": model_id,
                    "reason": "delete_forbidden" if exc.status_code == 403 else "delete_failed",
                    "statusCode": exc.status_code,
                    "message": _http_exception_message(exc),
                }
            )
        except Exception as exc:
            db.rollback()
            skipped.append(
                {
                    "modelId": model_id,
                    "reason": "delete_failed",
                    "message": str(exc)[:300] or exc.__class__.__name__,
                }
            )

    write_admin_log(
        db,
        admin,
        action="remove_unavailable_models",
        target_type="model",
        status="success",
        summary={"requestedIds": payload.modelIds, "removedIds": removed_ids, "skipped": skipped},
    )
    return {
        "removedIds": removed_ids,
        "skipped": skipped,
        "models": [serialize_model(item, admin, is_admin=True).model_dump() for item in list_admin_models(db)],
    }


@app.get("/api/admin/permissions/me", response_model=AdminPermissionOut)
async def admin_permissions_me(
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> AdminPermissionOut:
    role = resolve_admin_role(admin, settings)
    return AdminPermissionOut(role=role, permissions=permissions_for_role(role))


@app.post("/api/admin/maintenance/user-merge")
async def admin_user_merge_maintenance(
    payload: AdminUserMergeRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "maintenance:user_merge", settings)
    if payload.apply:
        require_csrf(request, db, settings)
    summary = merge_duplicate_users_by_identity(
        db,
        apply=payload.apply,
        identity_filter=payload.identityFilter,
    )
    if payload.apply:
        actor_user_id = admin.id
        for group in summary.get("groups", []):
            if admin.id == group.get("targetUserId"):
                actor_user_id = admin.id
                break
            if admin.id in (group.get("sourceUserIds") or []):
                actor_user_id = str(group.get("targetUserId") or admin.id)
                break
        audit_admin = db.get(User, actor_user_id) or admin
        db.commit()
        write_admin_log(
            db,
            audit_admin,
            action="merge_duplicate_users",
            target_type="maintenance",
            summary={
                "apply": payload.apply,
                "identityFilter": payload.identityFilter,
                "actorUserId": actor_user_id,
                "groupCount": summary.get("groupCount", 0),
                "mergedUsers": summary.get("mergedUsers", 0),
                "movedRecords": summary.get("movedRecords", 0),
                "roleConflictCount": summary.get("roleConflictCount", 0),
                "roleConflicts": [
                    conflict
                    for group in summary.get("groups", [])
                    for conflict in (group.get("roleConflicts") or [])
                ],
            },
        )
    return {"summary": summary}


def asset_cleanup_targets() -> list[Any]:
    return build_cleanup_targets(GENERATED_ASSET_DIR, LOCAL_UPLOAD_DIR)


def redact_asset_cleanup_paths(summary: dict[str, Any]) -> dict[str, Any]:
    targets = summary.get("targets")
    if not isinstance(targets, list):
        return summary
    return {
        **summary,
        "targets": [
            {**target, "path": ""} if isinstance(target, dict) else target
            for target in targets
        ],
    }


@app.get("/api/admin/asset-cleanup/settings")
async def admin_asset_cleanup_settings(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_any_admin_permission(admin, ["settings:view", "maintenance:asset_cleanup"], settings)
    return {"settings": asset_cleanup_settings(db)}


@app.put("/api/admin/asset-cleanup/settings")
async def admin_update_asset_cleanup_settings(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "maintenance:asset_cleanup", settings)
    updated = update_asset_cleanup_settings(
        db,
        admin=admin,
        enabled=payload.get("enabled") if "enabled" in payload else None,
        retention_days=payload.get("retentionDays") if "retentionDays" in payload else None,
    )
    write_admin_log(
        db,
        admin,
        action="update_asset_cleanup_settings",
        target_type="maintenance",
        summary=updated,
    )
    return {"settings": updated}


@app.get("/api/admin/asset-cleanup/preview")
async def admin_asset_cleanup_preview(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_any_admin_permission(admin, ["settings:view", "maintenance:asset_cleanup"], settings)
    cleanup_settings = asset_cleanup_settings(db)
    summary = preview_asset_cleanup(
        targets=asset_cleanup_targets(),
        retention_days=int(cleanup_settings["retentionDays"]),
    )
    if not can(admin, "maintenance:asset_cleanup", settings):
        summary = redact_asset_cleanup_paths(summary)
    return {
        "settings": cleanup_settings,
        "summary": summary,
    }


@app.post("/api/admin/asset-cleanup/run")
async def admin_run_asset_cleanup(
    payload: dict[str, Any] | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "maintenance:asset_cleanup", settings)
    cleanup_settings = asset_cleanup_settings(db)
    retention_days = (
        payload.get("retentionDays")
        if isinstance(payload, dict) and "retentionDays" in payload
        else cleanup_settings["retentionDays"]
    )
    summary = run_asset_cleanup(
        db,
        targets=asset_cleanup_targets(),
        retention_days=retention_days,
        admin=admin,
    )
    write_admin_log(
        db,
        admin,
        action="asset_cache_cleanup",
        target_type="maintenance",
        summary=summary,
    )
    return {"settings": asset_cleanup_settings(db), "summary": summary}


@app.put("/api/admin/models/{model_id}")
async def admin_update_model(
    model_id: str,
    payload: AdminModelUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "model:update", settings)
    model = update_admin_model(db, admin, model_id, payload)
    return {"model": serialize_model(model, admin, is_admin=True).model_dump()}


@app.put("/api/admin/models/{model_id}/credit-pricing")
async def admin_update_model_credit_pricing(
    model_id: str,
    payload: AdminModelCreditPricingUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "model:pricing", settings)
    if payload.useDefault:
        clear_model_price(db, admin, model_id)
    elif payload.price is not None:
        set_model_price(db, admin, model_id, payload.price)
    model = db.get(ModelGroup, model_id)
    if not model:
        raise HTTPException(status_code=404, detail={"message": "模型不存在。"})
    return {"model": serialize_model(model, admin, is_admin=True).model_dump()}


@app.get("/api/admin/models/{model_id}/health")
async def admin_model_health(
    model_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "model:view", settings)
    if not db.get(ModelGroup, model_id):
        raise HTTPException(status_code=404, detail={"message": "模型不存在。"})
    return {"health": get_model_health(db, model_id, include_raw_json=can(admin, "record:raw_json", settings))}


@app.post("/api/admin/models/{model_id}/health-check")
async def admin_run_model_health_check(
    model_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "model:test", settings)
    result = await run_admin_model_health_check_for_model(model_id, request, db, admin, settings)
    return {"health": result["health"]}


@app.post("/api/admin/models/{model_id}/publish")
async def admin_publish_model(
    model_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "model:publish", settings)
    model = publish_model(db, admin, model_id)
    return {"model": serialize_model(model, admin, is_admin=True).model_dump()}


@app.post("/api/admin/models/{model_id}/unpublish")
async def admin_unpublish_model(
    model_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "model:unpublish", settings)
    model = unpublish_model(db, admin, model_id)
    return {"model": serialize_model(model, admin, is_admin=True).model_dump()}


@app.get("/api/admin/overview")
async def admin_overview_route(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "record:view", settings)
    return admin_overview(db)


@app.get("/api/admin/dashboard/metrics", response_model=AdminDashboardMetricOut)
async def admin_dashboard_metrics_route(
    range: str = Query("30d"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "record:view", settings)
    return admin_dashboard_metrics(db, range_key=range)


@app.get("/api/admin/credits/settings")
async def admin_credit_settings(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "credit:view", settings)
    return {"settings": get_credit_settings(db)}


@app.put("/api/admin/credits/settings")
async def admin_update_credit_settings(
    payload: AdminCreditSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "credit:settings", settings)
    updated_settings = update_credit_settings(
        db,
        admin,
        defaults=payload.defaults,
        signup_bonus_enabled=payload.signupBonusEnabled,
        signup_bonus_amount=payload.signupBonusAmount,
    )
    return {"settings": updated_settings}


@app.get("/api/admin/credits/transactions")
async def admin_credit_transactions(
    userId: str = "",
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "credit:view", settings)
    transactions = list_credit_transactions(db, user_id=userId, limit=200)
    return {"transactions": [serialize_credit_transaction(item) for item in transactions]}


@app.get("/api/admin/overview/users")
async def admin_overview_users_route(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "user:view", settings)
    rows = []
    for user in list_admin_users(db):
        logs = db.query(CallLog).filter(CallLog.user_id == user.id).all()
        rows.append(
            {
                "user": serialize_admin_user(user),
                "totalCalls": len(logs),
                "publicModelCalls": len([item for item in logs if item.is_public_model]),
                "privateModelCalls": len([item for item in logs if not item.is_public_model]),
                "failedCalls": len([item for item in logs if item.status != "success"]),
                "successCalls": len([item for item in logs if item.status == "success"]),
                "averageDurationMs": int(sum(item.duration_ms for item in logs) / len(logs)) if logs else 0,
            }
        )
    return {"users": rows}


@app.get("/api/admin/overview/models")
async def admin_overview_models_route(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "model:view", settings)
    rows = []
    for model in list_admin_models(db):
        logs = db.query(CallLog).filter(CallLog.model_group_id == model.id).all()
        rows.append(
            {
                "model": serialize_model(model, admin, is_admin=True).model_dump(),
                "totalCalls": len(logs),
                "successCalls": len([item for item in logs if item.status == "success"]),
                "failedCalls": len([item for item in logs if item.status != "success"]),
                "averageDurationMs": int(sum(item.duration_ms for item in logs) / len(logs)) if logs else 0,
            }
        )
    return {"models": rows}


@app.get("/api/admin/prompt-templates")
async def admin_prompt_templates(
    capability: str = "all",
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "settings:view", settings)
    return {"templates": [serialize_prompt_template(item) for item in list_prompt_templates(db, capability=capability)]}


@app.get("/api/admin/prompt-library")
async def admin_prompt_library(
    capability: str = "image",
    search: str = "",
    categoryId: str = "",
    enabled: str = "",
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "settings:view", settings)
    if capability not in {"", "image", "all"}:
        return {"templates": [], "total": 0}
    rows, total = list_scene_templates(
        db,
        search=search,
        category_id=categoryId,
        enabled=enabled,
        limit=limit,
        offset=offset,
    )
    return {
        "templates": [serialize_scene_template(item) for item in rows],
        "total": total,
        "summary": scene_template_summary(db, search=search, category_id=categoryId),
    }


@app.post("/api/admin/prompt-library/import")
async def admin_import_prompt_library(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "settings:update", settings)
    index = payload.get("index")
    if not isinstance(index, dict):
        raise HTTPException(status_code=400, detail={"message": "缺少 index 对象。"})
    summary = import_prompt_scene_templates(db, admin, index, replace=bool(payload.get("replace")))
    return {"summary": summary}


@app.put("/api/admin/prompt-library/{template_id}")
async def admin_update_prompt_library_template(
    template_id: str,
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "settings:update", settings)
    return {"template": serialize_scene_template(update_scene_template(db, admin, template_id, payload))}


@app.post("/api/admin/prompt-library/batch")
async def admin_batch_prompt_library_templates(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "settings:update", settings)
    template_ids = payload.get("templateIds")
    if not isinstance(template_ids, list):
        raise HTTPException(status_code=400, detail={"message": "templateIds must be a list."})
    updated = batch_update_scene_templates(
        db,
        admin,
        [str(item) for item in template_ids],
        enabled=bool(payload["enabled"]) if "enabled" in payload else None,
    )
    return {"updated": updated}


@app.put("/api/admin/prompt-templates/{template_id}")
async def admin_save_prompt_template(
    template_id: str,
    payload: PromptTemplateUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "settings:update", settings)
    _ = template_id
    item = upsert_prompt_template(db, admin, payload)
    return {"template": serialize_prompt_template(item)}


@app.get("/api/admin/prompt-templates/{template_id}/versions")
async def admin_prompt_template_versions(
    template_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "settings:view", settings)
    return {"versions": list_prompt_template_versions(db, template_id)}


@app.post("/api/admin/prompt-templates/{template_id}/versions/{version}/restore")
async def admin_restore_prompt_template_version(
    template_id: str,
    version: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "settings:update", settings)
    item = restore_prompt_template_version(db, admin, template_id, version)
    return {"template": serialize_prompt_template(item)}


@app.get("/api/admin/prompt-templates/model-status")
async def admin_prompt_template_model_status(
    capability: str = "all",
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "settings:view", settings)
    return {"models": prompt_template_model_status_overview(db, capability=capability)}


@app.post("/api/admin/prompt-templates/test")
async def admin_test_prompt_template(
    payload: dict[str, Any],
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "settings:view", settings)
    content = str(payload.get("content") or "")
    prompt = str(payload.get("prompt") or "")
    prompts = payload.get("prompts")
    if isinstance(prompts, list):
        return {
            "results": render_prompt_template_samples(
                content,
                capability=str(payload.get("capability") or "text"),
                prompts=[str(item) for item in prompts],
            )
        }
    rendered = render_prompt_template(content, {"prompt": prompt, "capability": payload.get("capability") or "text"})
    return {"prompt": rendered}


@app.get("/api/admin/users")
async def admin_users(
    search: str = "",
    role: str = "",
    status: str = "",
    page: int = 1,
    pageSize: int = 20,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "user:view", settings)
    safe_page = max(page, 1)
    safe_page_size = min(max(pageSize, 1), 100)
    duplicate_map = admin_duplicate_identity_map(db)
    total = count_admin_users(db, search=search, role=role, status=status, settings=settings)
    return {
        "users": [
            serialize_admin_user(item, settings, duplicate_identity=duplicate_map.get(item.id))
            for item in list_admin_users(
                db,
                search=search,
                role=role,
                status=status,
                settings=settings,
                page=safe_page,
                page_size=safe_page_size,
            )
        ],
        "total": total,
        "page": safe_page,
        "pageSize": safe_page_size,
        "summary": admin_users_summary(db, search=search, role=role, status=status, settings=settings),
    }


@app.get("/api/admin/users/export")
async def admin_users_export(
    search: str = "",
    role: str = "",
    status: str = "",
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    require_admin_permission(admin, "user:export", settings)
    users = list_admin_users(db, search=search, role=role, status=status, settings=settings, limit=None)
    write_admin_log(
        db,
        admin,
        action="export_users",
        target_type="user",
        target_id="export",
        summary={
            "count": len(users),
            "filters": {
                "search": search,
                "role": role,
                "status": status,
            },
        },
    )
    return Response(
        content="\ufeff" + build_admin_users_csv(users, settings),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="users.csv"'},
    )


@app.put("/api/admin/users/{user_id}")
async def admin_update_user_route(
    user_id: str,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "user:update", settings)
    user = update_admin_user(db, admin, user_id, payload)
    return {"user": serialize_admin_user_with_duplicate_identity(db, user, settings)}


@app.put("/api/admin/users/{user_id}/role")
async def admin_update_user_role_route(
    user_id: str,
    payload: AdminUserRoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "user:role:update", settings)
    set_admin_user_role(db, admin, user_id, payload.role, note=payload.note)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail={"message": "用户不存在。"})
    return {"user": serialize_admin_user_with_duplicate_identity(db, user, settings)}


@app.get("/api/admin/users/{user_id}/credits")
async def admin_user_credits(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "credit:view", settings)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail={"message": "用户不存在。"})
    account = get_or_create_credit_account(db, user.id)
    transactions = list_credit_transactions(db, user_id=user.id, limit=100)
    return {
        "account": serialize_credit_account(account),
        "transactions": [serialize_credit_transaction(item) for item in transactions],
    }


@app.post("/api/admin/users/{user_id}/credits/adjust")
async def admin_adjust_user_credits(
    user_id: str,
    payload: AdminCreditAdjustRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "credit:adjust", settings)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail={"message": "用户不存在。"})
    transaction = admin_adjust_credits(
        db,
        admin=admin,
        target_user=user,
        amount=payload.amount,
        reason=payload.reason,
        notification_delivery="single",
    )
    account = get_or_create_credit_account(db, user.id)
    return {
        "account": serialize_credit_account(account),
        "transaction": serialize_credit_transaction(transaction),
        "user": serialize_admin_user_with_duplicate_identity(db, user, settings),
    }


@app.post("/api/admin/users/{user_id}/disable")
async def admin_disable_user_route(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "user:disable", settings)
    user = admin_disable_user(db, admin, user_id)
    return {"user": serialize_admin_user_with_duplicate_identity(db, user, settings)}


@app.post("/api/admin/users/{user_id}/enable")
async def admin_enable_user_route(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "user:update", settings)
    user = admin_enable_user(db, admin, user_id)
    return {"user": serialize_admin_user_with_duplicate_identity(db, user, settings)}


@app.post("/api/admin/users/{user_id}/delete")
async def admin_delete_user_route(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "user:delete", settings)
    user = admin_delete_user(db, admin, user_id)
    return {"user": serialize_admin_user_with_duplicate_identity(db, user, settings)}


@app.post("/api/admin/users/{user_id}/restore")
async def admin_restore_user_route(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "user:restore", settings)
    user = admin_restore_user(db, admin, user_id)
    return {"user": serialize_admin_user_with_duplicate_identity(db, user, settings)}


@app.post("/api/admin/users/{user_id}/reset-password")
async def admin_reset_user_password(
    user_id: str,
    payload: AdminResetPasswordRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "user:update", settings)
    user = get_admin_user(db, user_id)
    ensure_can_manage_user(admin, user)
    credential = (
        db.query(UserCredential)
        .filter(UserCredential.user_id == user.id, UserCredential.provider == "local")
        .one_or_none()
    )
    if not credential:
        raise HTTPException(status_code=400, detail={"message": "该用户未使用本地账号登录，无法重置密码。"})
    credential.password_hash = hash_password(payload.password)
    credential.failed_attempts = 0
    credential.locked_until = None
    db.commit()
    write_admin_log(db, admin, action="reset_password", target_type="user", target_id=user.id)
    return {"ok": True}


@app.post("/api/admin/credits/batch-adjust")
async def admin_batch_adjust_credits(
    payload: AdminBatchCreditAdjustRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    require_admin_permission(admin, "credit:adjust", settings)
    results: list[dict[str, Any]] = []
    for user_id in payload.userIds:
        user = db.get(User, user_id)
        if not user:
            results.append({"userId": user_id, "ok": False, "message": "用户不存在"})
            continue
        try:
            admin_adjust_credits(
                db,
                admin=admin,
                target_user=user,
                amount=payload.amount,
                reason=payload.reason,
                notification_delivery="batch",
            )
            results.append({"userId": user_id, "ok": True})
        except HTTPException as exc:
            db.rollback()
            results.append({"userId": user_id, "ok": False, "message": _http_exception_message(exc)})
    return {"results": results, "successCount": sum(1 for r in results if r["ok"])}


@app.get("/api/admin/records/text")
async def admin_text_records(
    userId: str = "",
    userSearch: str = "",
    modelGroupId: str = "",
    status: str = "",
    keyword: str = "",
    size: str = "",
    ratio: str = "",
    refCount: str = "",
    duration: str = "",
    resolution: str = "",
    mode: str = "",
    startAt: str = "",
    endAt: str = "",
    page: int = 1,
    pageSize: int = 30,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "record:view", settings)
    include_raw_json = can(admin, "record:raw_json", settings)
    safe_page = max(page, 1)
    safe_page_size = min(max(pageSize, 1), 100)
    records = list_admin_creation_records(
        db,
        capability="text",
        user_id=userId,
        user_search=userSearch,
        model_group_id=modelGroupId,
        status=status,
        keyword=keyword,
        size=size,
        ratio=ratio,
        ref_count=refCount,
        duration=duration,
        resolution=resolution,
        mode=mode,
        start_at=startAt,
        end_at=endAt,
        page=safe_page,
        page_size=safe_page_size,
        include_raw_json=include_raw_json,
    )
    return {
        "records": records,
        "page": safe_page,
        "pageSize": safe_page_size,
        "hasMore": len(records) >= safe_page_size,
    }


def _export_admin_records_response(
    db: Session,
    admin: User,
    *,
    capability: str,
    user_id: str = "",
    user_search: str = "",
    model_group_id: str = "",
    status: str = "",
    keyword: str = "",
    size: str = "",
    ratio: str = "",
    ref_count: str = "",
    duration: str = "",
    resolution: str = "",
    mode: str = "",
    include_raw_json: bool = False,
) -> Response:
    records = list_admin_creation_records(
        db,
        capability=capability,
        user_id=user_id,
        user_search=user_search,
        model_group_id=model_group_id,
        status=status,
        keyword=keyword,
        size=size,
        ratio=ratio,
        ref_count=ref_count,
        duration=duration,
        resolution=resolution,
        mode=mode,
        unlimited=True,
        include_raw_json=include_raw_json,
    )
    write_admin_log(
        db,
        admin,
        action="export_records",
        target_type="record",
        target_id=capability,
        summary={
            "capability": capability,
            "count": len(records),
            "filters": {
                "userId": user_id,
                "userSearch": user_search,
                "modelGroupId": model_group_id,
                "status": status,
                "keyword": keyword,
                "size": size,
                "ratio": ratio,
                "refCount": ref_count,
                "duration": duration,
                "resolution": resolution,
                "mode": mode,
            },
        },
    )
    return Response(
        content="\ufeff" + build_admin_creation_records_csv(records),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="records-{capability}.csv"'},
    )


@app.get("/api/admin/records/text/export")
async def admin_text_records_export(
    userId: str = "",
    userSearch: str = "",
    modelGroupId: str = "",
    status: str = "",
    keyword: str = "",
    size: str = "",
    ratio: str = "",
    refCount: str = "",
    duration: str = "",
    resolution: str = "",
    mode: str = "",
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    require_admin_permission(admin, "record:export", settings)
    return _export_admin_records_response(
        db,
        admin,
        capability="text",
        user_id=userId,
        user_search=userSearch,
        model_group_id=modelGroupId,
        status=status,
        keyword=keyword,
        size=size,
        ratio=ratio,
        ref_count=refCount,
        duration=duration,
        resolution=resolution,
        mode=mode,
        include_raw_json=can(admin, "record:raw_json", settings),
    )


@app.get("/api/admin/records/images")
async def admin_image_records(
    userId: str = "",
    userSearch: str = "",
    modelGroupId: str = "",
    status: str = "",
    keyword: str = "",
    size: str = "",
    ratio: str = "",
    refCount: str = "",
    duration: str = "",
    resolution: str = "",
    mode: str = "",
    startAt: str = "",
    endAt: str = "",
    page: int = 1,
    pageSize: int = 30,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "record:view", settings)
    include_raw_json = can(admin, "record:raw_json", settings)
    safe_page = max(page, 1)
    safe_page_size = min(max(pageSize, 1), 100)
    records = list_admin_creation_records(
        db,
        capability="image",
        user_id=userId,
        user_search=userSearch,
        model_group_id=modelGroupId,
        status=status,
        keyword=keyword,
        size=size,
        ratio=ratio,
        ref_count=refCount,
        duration=duration,
        resolution=resolution,
        mode=mode,
        start_at=startAt,
        end_at=endAt,
        page=safe_page,
        page_size=safe_page_size,
        include_raw_json=include_raw_json,
    )
    return {
        "records": records,
        "page": safe_page,
        "pageSize": safe_page_size,
        "hasMore": len(records) >= safe_page_size,
    }


@app.get("/api/admin/records/images/export")
async def admin_image_records_export(
    userId: str = "",
    userSearch: str = "",
    modelGroupId: str = "",
    status: str = "",
    keyword: str = "",
    size: str = "",
    ratio: str = "",
    refCount: str = "",
    duration: str = "",
    resolution: str = "",
    mode: str = "",
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    require_admin_permission(admin, "record:export", settings)
    return _export_admin_records_response(
        db,
        admin,
        capability="image",
        user_id=userId,
        user_search=userSearch,
        model_group_id=modelGroupId,
        status=status,
        keyword=keyword,
        size=size,
        ratio=ratio,
        ref_count=refCount,
        duration=duration,
        resolution=resolution,
        mode=mode,
        include_raw_json=can(admin, "record:raw_json", settings),
    )


@app.get("/api/admin/records/videos")
async def admin_video_records(
    userId: str = "",
    userSearch: str = "",
    modelGroupId: str = "",
    status: str = "",
    keyword: str = "",
    size: str = "",
    ratio: str = "",
    refCount: str = "",
    duration: str = "",
    resolution: str = "",
    mode: str = "",
    startAt: str = "",
    endAt: str = "",
    page: int = 1,
    pageSize: int = 30,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "record:view", settings)
    include_raw_json = can(admin, "record:raw_json", settings)
    safe_page = max(page, 1)
    safe_page_size = min(max(pageSize, 1), 100)
    records = list_admin_creation_records(
        db,
        capability="video",
        user_id=userId,
        user_search=userSearch,
        model_group_id=modelGroupId,
        status=status,
        keyword=keyword,
        size=size,
        ratio=ratio,
        ref_count=refCount,
        duration=duration,
        resolution=resolution,
        mode=mode,
        start_at=startAt,
        end_at=endAt,
        page=safe_page,
        page_size=safe_page_size,
        include_raw_json=include_raw_json,
    )
    return {
        "records": records,
        "page": safe_page,
        "pageSize": safe_page_size,
        "hasMore": len(records) >= safe_page_size,
    }


@app.get("/api/admin/records/videos/export")
async def admin_video_records_export(
    userId: str = "",
    userSearch: str = "",
    modelGroupId: str = "",
    status: str = "",
    keyword: str = "",
    size: str = "",
    ratio: str = "",
    refCount: str = "",
    duration: str = "",
    resolution: str = "",
    mode: str = "",
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    require_admin_permission(admin, "record:export", settings)
    return _export_admin_records_response(
        db,
        admin,
        capability="video",
        user_id=userId,
        user_search=userSearch,
        model_group_id=modelGroupId,
        status=status,
        keyword=keyword,
        size=size,
        ratio=ratio,
        ref_count=refCount,
        duration=duration,
        resolution=resolution,
        mode=mode,
        include_raw_json=can(admin, "record:raw_json", settings),
    )


@app.get("/api/admin/records/detail/{message_id}")
async def admin_record_detail_route(
    message_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "record:view", settings)
    return {"record": admin_record_detail(db, message_id, include_raw_json=can(admin, "record:raw_json", settings))}


@app.get("/api/admin/tasks/{task_id}/timeline")
async def admin_task_timeline_route(
    task_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "record:view", settings)
    return admin_task_timeline(db, task_id, include_raw_json=can(admin, "record:raw_json", settings))


@app.get("/api/admin/audit-logs")
async def admin_audit_logs(
    action: str = "",
    adminUserId: str = "",
    targetType: str = "",
    targetId: str = "",
    status: str = "",
    risk: str = "",
    startAt: str = "",
    endAt: str = "",
    page: int = 1,
    pageSize: int = 20,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_admin_permission(admin, "audit:view", settings)
    safe_page = max(page, 1)
    safe_page_size = min(max(pageSize, 1), 300)
    total = count_admin_audit_logs(
        db,
        action=action,
        admin_user_id=adminUserId,
        target_type=targetType,
        target_id=targetId,
        status=status,
        risk=risk,
        start_at=startAt,
        end_at=endAt,
    )
    return {
        "logs": list_admin_audit_logs(
            db,
            action=action,
            admin_user_id=adminUserId,
            target_type=targetType,
            target_id=targetId,
            status=status,
            risk=risk,
            start_at=startAt,
            end_at=endAt,
            page=safe_page,
            page_size=safe_page_size,
        ),
        "total": total,
        "page": safe_page,
        "pageSize": safe_page_size,
        "riskSummary": admin_audit_risk_summary(
            db,
            action=action,
            admin_user_id=adminUserId,
            target_type=targetType,
            target_id=targetId,
            status=status,
            start_at=startAt,
            end_at=endAt,
        ),
    }


@app.get("/api/admin/audit-logs/export")
async def admin_audit_logs_export(
    action: str = "",
    adminUserId: str = "",
    targetType: str = "",
    targetId: str = "",
    status: str = "",
    risk: str = "",
    startAt: str = "",
    endAt: str = "",
    limit: int = 300,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    require_admin_permission(admin, "audit:export", settings)
    rows = list_admin_audit_logs(
        db,
        action=action,
        admin_user_id=adminUserId,
        target_type=targetType,
        target_id=targetId,
        status=status,
        risk=risk,
        start_at=startAt,
        end_at=endAt,
        unlimited=True,
    )
    return Response(
        content="\ufeff" + build_admin_audit_logs_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit-logs.csv"'},
    )


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


@app.put("/api/conversations/{conversation_id}")
async def update_conversation_route(
    conversation_id: str,
    payload: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    conversation = update_conversation_title(db, current_user, conversation_id, payload.title)
    return {"conversation": serialize_conversation(conversation).model_dump()}


@app.post("/api/conversations/{conversation_id}/rename")
async def rename_conversation_route(
    conversation_id: str,
    payload: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    conversation = update_conversation_title(db, current_user, conversation_id, payload.title)
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
    try:
        response, raw = await forward_json("GET", target_url, api_key)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail={"message": "连接供应商超时，请检查 baseURL 或稍后重试。"})
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail={"message": "无法连接到该供应商，请检查 baseURL 是否正确、网络是否可达。"})
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
    sub_model = None
    if payload.get("subModelId"):
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

    body = build_test_body(str(capability), model, str(adapter) if adapter else None)
    target_path = resolve_test_path(str(capability), str(adapter) if adapter else None)
    if is_kkyi_video_model(sub_model, base_url):
        target_path = "/v1/videos"
        body = normalize_kkyi_video_body(body, sub_model.model_name, sub_model)
    target_url = resolve_url(base_url, target_path)
    started_at = time.perf_counter()
    try:
        response, raw = await forward_json("POST", target_url, api_key, body)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail={"message": "连接供应商超时，请检查 baseURL 或稍后重试。"})
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail={"message": "无法连接到该供应商，请检查 baseURL 是否正确、网络是否可达。"})
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


@app.post("/api/proxy/prompt/optimize")
async def proxy_prompt_optimize(
    payload: PromptOptimizeRequest,
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
        bucket="prompt-optimize",
        limit=settings.rate_limit_generation_per_window,
        user_id=current_user.id if current_user else "",
    )
    if not payload.prompt:
        raise HTTPException(status_code=400, detail={"message": "请先输入需要优化的提示词。"})
    optimizer = find_prompt_optimizer_sub_model(db, current_user, payload.subModelId)
    if not optimizer:
        raise HTTPException(status_code=404, detail={"message": "当前没有可用的公共文案模型用于优化提示词。"})

    model_group, sub_model, api_key_record, api_key = optimizer
    messages = build_prompt_optimize_messages(payload)
    try:
        if model_group.prompt_optimize_enabled:
            template = get_prompt_template_for_scope(db, payload.capability, model_group.id)
            messages = build_prompt_optimize_messages_from_template(payload, template.content)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
    body = {
        "model": sub_model.model_name,
        "messages": messages,
        "stream": False,
        "temperature": 0.35,
        "max_tokens": 1200,
    }
    response, raw = await forward_json("POST", resolve_url(api_key_record.base_url, "/v1/chat/completions"), api_key, body)
    if not response.is_success or not isinstance(raw, dict):
        raise upstream_error(raw, "提示词优化失败。", response.status_code)
    optimized = pick_text_content(raw).strip()
    if not optimized:
        raise HTTPException(status_code=502, detail={"message": "提示词优化没有返回有效内容。"})
    return {"prompt": optimized, "raw": raw}


@app.post("/api/prompt-library/image-recommendations")
async def image_prompt_recommendations(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    check_rate_limit(
        limiter=rate_limiter,
        request=request,
        settings=settings,
        bucket="prompt-library-recommend",
        limit=settings.rate_limit_generation_per_window,
        user_id=current_user.id,
    )
    image_url = str(payload.get("imageUrl") or "").strip()
    if not image_url:
        raise HTTPException(status_code=400, detail={"message": "缺少参考图地址。"})
    model_image_url = local_asset_data_url(image_url)
    limit = parse_prompt_recommendation_limit(payload.get("limit"))
    optimizer = find_gpt55_prompt_optimizer_sub_model(db, current_user)
    if not optimizer:
        return {"recommendations": [], "reason": "gpt55_not_configured"}
    model_group, sub_model, api_key_record, api_key = optimizer
    candidates = recommendation_candidates(db, limit=80)
    if not candidates:
        return {
            "recommendations": [],
            "reason": "prompt_library_empty",
            "modelGroupId": model_group.id,
            "subModelId": sub_model.id,
        }
    messages = build_recommendation_messages(model_image_url, candidates)
    body = {
        "model": sub_model.model_name,
        "messages": messages,
        "stream": False,
        "temperature": 0.2,
        "max_tokens": 1200,
    }
    response, raw = await forward_json("POST", resolve_url(api_key_record.base_url, "/v1/chat/completions"), api_key, body)
    if not response.is_success or not isinstance(raw, dict):
        raise upstream_error(raw, "图片提示词推荐失败。", response.status_code)
    selected = parse_recommendation_payload(pick_text_content(raw))
    templates_by_id = {item.id: item for item in candidates}
    recommendations: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in selected:
        template = templates_by_id.get(item["templateId"])
        if not template or template.id in seen_ids:
            continue
        seen_ids.add(template.id)
        record_scene_template_event(
            db,
            template=template,
            user=current_user,
            event_type="impression",
            image_url=image_url,
            metadata={"label": item.get("label", ""), "reason": item.get("reason", "")},
        )
        recommendations.append(
            {
                **serialize_scene_template(template),
                "label": item.get("label") or template.title[:18],
                "reason": item.get("reason") or "",
                **({"promptText": item["promptText"]} if item.get("promptText") else {}),
            }
        )
        if len(recommendations) >= limit:
            break
    db.commit()
    return {
        "recommendations": recommendations,
        "reason": "ok" if recommendations else "no_match",
        "modelGroupId": model_group.id,
        "subModelId": sub_model.id,
    }


@app.post("/api/prompt-library/events")
async def prompt_library_event(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    template_id = str(payload.get("templateId") or "").strip()
    event_type = str(payload.get("eventType") or "").strip()
    if not template_id:
        raise HTTPException(status_code=400, detail={"message": "缺少提示词模板 ID。"})
    template = record_scene_template_event_by_id(
        db,
        template_id=template_id,
        user=current_user,
        event_type=event_type,
        image_url=str(payload.get("imageUrl") or ""),
        metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
    )
    return {"template": serialize_scene_template(template)}


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
    credit_reserve = None
    user_prompt = ""
    if payload.get("subModelId"):
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
    if model_group and sub_model:
        credit_reserve = prepare_generation_credit(
            db,
            user=current_user,
            capability="text",
            model_group=model_group,
            sub_model=sub_model,
        )
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
    forward_task = asyncio.create_task(forward_json("POST", target_url, api_key, body))
    if current_user and model_group and sub_model and conversation:
        completed, result = await wait_for_forward_or_handoff(forward_task, settings)
        if not completed:
            task_id = new_long_task_id(TEXT_LONG_TASK_PREFIX)
            assistant_message = add_message(
                db,
                conversation,
                current_user,
                role="assistant",
                capability="text",
                content=task_id,
                status="processing",
                can_retry=False,
                model_group_id=model_group.id,
                sub_model_id=sub_model.id,
                request=body,
                response={
                    "taskId": task_id,
                    "status": "processing",
                    **({"creditReserveId": credit_reserve.id} if credit_reserve else {}),
                },
            )
            update_reserved_transaction_refs(
                db,
                credit_reserve,
                conversation_id=conversation.id,
                message_id=assistant_message.id,
                task_id=task_id,
            )
            db.commit()
            refreshed = reload_conversation(db, current_user, conversation.id)
            asyncio.create_task(
                complete_text_long_task(
                    forward_task,
                    started_at=started_at,
                    user_id=current_user.id,
                    conversation_id=conversation.id,
                    message_id=assistant_message.id,
                    model_group_id=model_group.id,
                    sub_model_id=sub_model.id,
                    body=body,
                    task_id=task_id,
                )
            )
            return attach_credit_payload({
                "content": "",
                "taskId": task_id,
                "status": "processing",
                "usage": None,
                "raw": {
                    "taskId": task_id,
                    "status": "processing",
                    **({"creditReserveId": credit_reserve.id} if credit_reserve else {}),
                },
                "conversation": serialize_conversation(refreshed).model_dump(),
                "assistantMessage": serialize_message(assistant_message).model_dump(),
            }, db, current_user)
        response, raw = result if result is not None else await forward_task
    else:
        response, raw = await forward_task
    duration_ms = elapsed_ms(started_at)

    if not response.is_success or not isinstance(raw, dict):
        if credit_reserve:
            refund_generation_credits(db, credit_reserve.id, reason="文案生成失败自动退款")
        upstream_message = pick_error_message(raw, "文案请求失败。")
        message = GENERATION_FAILED_MESSAGE
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
                error_message=upstream_message,
            )
        detail = {"message": message}
        if conversation and failed_message and current_user and should_return_generation_failure_payload(response):
            db.commit()
            refreshed = reload_conversation(db, current_user, conversation.id)
            return attach_credit_payload({
                "content": "",
                "status": "failed",
                "usage": None,
                "conversation": serialize_conversation(refreshed).model_dump(mode="json"),
                "assistantMessage": serialize_message(failed_message).model_dump(mode="json"),
            }, db, current_user)
        if conversation and failed_message and current_user:
            db.commit()
            refreshed = reload_conversation(db, current_user, conversation.id)
            detail = {
                **detail,
                "conversation": serialize_conversation(refreshed).model_dump(mode="json"),
                "assistantMessage": serialize_message(failed_message).model_dump(mode="json"),
            }
        raise HTTPException(status_code=response.status_code or 500, detail=detail)

    content = pick_text_content(raw)
    if credit_reserve:
        capture_generation_credits(db, credit_reserve.id)

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
    attach_credit_payload(result, db, current_user)
    if conversation and current_user:
        db.commit()
        refreshed = reload_conversation(db, current_user, conversation.id)
        result["conversation"] = serialize_conversation(refreshed).model_dump()
        if assistant_message:
            result["assistantMessage"] = serialize_message(assistant_message).model_dump()
    return result


@app.post("/api/proxy/text/query")
async def proxy_text_query(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    check_rate_limit(
        limiter=rate_limiter,
        request=request,
        settings=settings,
        bucket="generation-text-query",
        limit=settings.rate_limit_generation_per_window,
        user_id=current_user.id,
    )
    conversation_id = str(payload.get("conversationId") or "").strip()
    task_id = str(payload.get("taskId") or "").strip()
    if not conversation_id:
        raise HTTPException(status_code=400, detail={"message": "缺少会话 ID。"})
    if not task_id:
        raise HTTPException(status_code=400, detail={"message": "缺少任务 ID。"})
    conversation = get_conversation(db, current_user, conversation_id)
    message = find_text_task_message(conversation, task_id)
    if not message:
        raise HTTPException(status_code=404, detail={"message": "文本任务不存在或已被清理。"})
    return attach_credit_payload(serialize_text_task_result(conversation, message, task_id), db, current_user)


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
    credit_reserve = None
    if payload.get("subModelId"):
        model_group, sub_model, api_key_record, api_key = get_sub_model_for_user(db, current_user, str(payload["subModelId"]))
        base_url = api_key_record.base_url
        model = sub_model.model_name
        adapter = sub_model.adapter
    else:
        base_url, api_key = validate_config(payload.get("config"))
        model = str(payload.get("model", "")).strip()
        adapter = str(payload.get("adapter") or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail={"message": "缺少模型标识。"})

    request_body = copy.deepcopy(payload.get("requestBody") or {})
    body = {"model": model, **request_body}
    body = normalize_image_reference_fields_for_adapter(body, adapter)
    validate_reference_limit(body)
    body, is_4k_image, image_4k_target_size = normalize_image_4k_request(
        body,
        adapter=adapter,
        enable_4k=payload.get("enable4k") is True,
    )
    image_count = requested_image_count(body)
    reference_assets = collect_reference_image_assets(body)
    edit_references = collect_image_edit_references(body)
    target_url = resolve_url(base_url, "/v1/images/edits" if edit_references else "/v1/images/generations")
    if not edit_references:
        body = expand_local_image_references(body)
    prompt = str(body.get("prompt") or "")
    if has_oversized_inline_reference(body):
        message = "参考图过大，请重新上传参考图后再生成。"
        detail: dict[str, Any] = {"message": message}
        detail.update(
            transient_error_conversation(
                conversation_id=str(payload.get("conversationId") or ""),
                capability="image",
                prompt=prompt,
                error_message=message,
            )
        )
        raise HTTPException(status_code=413, detail=detail)
    if current_user:
        conversation = ensure_conversation(
            db,
            current_user,
            conversation_id=safe_conversation_id(str(payload.get("conversationId") or "")),
            title_seed=prompt,
            capability="image",
            model_group_id=model_group.id if model_group else None,
            sub_model_id=sub_model.id if sub_model else None,
        )
        user_message = add_message(
            db,
            conversation,
            current_user,
            role="user",
            capability="image",
            content=prompt,
            model_group_id=model_group.id if model_group else None,
            sub_model_id=sub_model.id if sub_model else None,
            request=body,
        )
        add_reference_assets(db, user_message, current_user, capability="image", references=reference_assets)
    if model_group and sub_model:
        credit_reserve = prepare_generation_credit(
            db,
            user=current_user,
            capability="image",
            model_group=model_group,
            sub_model=sub_model,
            conversation_id=conversation.id if conversation else "",
            quantity=image_count,
            multiplier=2 if is_4k_image else 1,
            metadata={
                **({"is4k": True, "targetSize": image_4k_target_size} if is_4k_image else {}),
            },
        )
    if current_user and conversation and image_count > 1:
        task_id = new_long_task_id(IMAGE_LONG_TASK_PREFIX)
        assistant_message = add_message(
            db,
            conversation,
            current_user,
            role="assistant",
            capability="image",
            content=task_id,
            status="processing",
            can_retry=False,
            model_group_id=model_group.id if model_group else None,
            sub_model_id=sub_model.id if sub_model else None,
            request=body,
            response={
                "taskId": task_id,
                "localTaskId": task_id,
                "status": "processing",
                "progress": f"0/{image_count}",
                "batch": {
                    "requestedCount": image_count,
                    "completedCount": 0,
                    "successCount": 0,
                    "failedCount": 0,
                },
                **({"creditReserveId": credit_reserve.id} if credit_reserve else {}),
            },
        )
        update_reserved_transaction_refs(
            db,
            credit_reserve,
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            task_id=task_id,
            metadata={
                "quantity": image_count,
                **({"is4k": True, "targetSize": image_4k_target_size, "multiplier": 2} if is_4k_image else {}),
            },
        )
        record_generation_task_event(
            db,
            task_id=task_id,
            event_type="submitted",
            status="processing",
            user=current_user,
            model_group=model_group,
            sub_model=sub_model,
            capability="image",
            endpoint="/api/proxy/image",
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            message="Batch image task submitted.",
            payload={
                "taskId": task_id,
                "localTaskId": task_id,
                "status": "processing",
                "requestedCount": image_count,
                "conversationId": conversation.id,
                "messageId": assistant_message.id,
            },
        )
        db.commit()
        refreshed = reload_conversation(db, current_user, conversation.id)
        asyncio.create_task(
            complete_image_batch_task(
                started_at=time.perf_counter(),
                user_id=current_user.id,
                conversation_id=conversation.id,
                message_id=assistant_message.id,
                model_group_id=model_group.id if model_group else None,
                sub_model_id=sub_model.id if sub_model else None,
                body=body,
                task_id=task_id,
                requested_count=image_count,
                base_url=base_url,
                target_url=target_url,
                api_key=api_key,
                edit_references=edit_references,
            )
        )
        return attach_credit_payload({
            "images": [],
            "taskId": task_id,
            "status": "processing",
            "progress": f"0/{image_count}",
            "raw": {
                "taskId": task_id,
                "localTaskId": task_id,
                "status": "processing",
                "progress": f"0/{image_count}",
                "batch": {
                    "requestedCount": image_count,
                    "completedCount": 0,
                    "successCount": 0,
                    "failedCount": 0,
                },
                **({"creditReserveId": credit_reserve.id} if credit_reserve else {}),
            },
            "conversation": serialize_conversation(refreshed).model_dump(),
            "assistantMessage": serialize_message(assistant_message).model_dump(),
        }, db, current_user)

    async def send_image_request() -> tuple[httpx.Response, dict[str, Any] | str]:
        return await forward_image_request(
            base_url=base_url,
            target_url=target_url,
            api_key=api_key,
            body=body,
            edit_references=edit_references,
        )

    started_at = time.perf_counter()
    try:
        forward_task = asyncio.create_task(send_image_request())
        if current_user and conversation:
            completed, result = await wait_for_forward_or_handoff(forward_task, settings)
            if not completed:
                task_id = new_long_task_id(IMAGE_LONG_TASK_PREFIX)
                assistant_message = add_message(
                    db,
                    conversation,
                    current_user,
                    role="assistant",
                    capability="image",
                    content=task_id,
                    status="processing",
                    can_retry=False,
                    model_group_id=model_group.id if model_group else None,
                    sub_model_id=sub_model.id if sub_model else None,
                    request=body,
                    response={
                        "taskId": task_id,
                        "status": "processing",
                        **({"creditReserveId": credit_reserve.id} if credit_reserve else {}),
                    },
                )
                update_reserved_transaction_refs(
                    db,
                    credit_reserve,
                    conversation_id=conversation.id,
                    message_id=assistant_message.id,
                    task_id=task_id,
                )
                record_generation_task_event(
                    db,
                    task_id=task_id,
                    event_type="submitted",
                    status="processing",
                    user=current_user,
                    model_group=model_group,
                    sub_model=sub_model,
                    capability="image",
                    endpoint="/api/proxy/image",
                    conversation_id=conversation.id,
                    message_id=assistant_message.id,
                    message="Image task submitted.",
                    payload={
                        "taskId": task_id,
                        "localTaskId": task_id,
                        "status": "processing",
                        "conversationId": conversation.id,
                        "messageId": assistant_message.id,
                    },
                )
                db.commit()
                refreshed = reload_conversation(db, current_user, conversation.id)
                asyncio.create_task(
                    complete_image_long_task(
                        forward_task,
                        started_at=started_at,
                        user_id=current_user.id,
                        conversation_id=conversation.id,
                        message_id=assistant_message.id,
                        model_group_id=model_group.id if model_group else None,
                        sub_model_id=sub_model.id if sub_model else None,
                        body=body,
                        task_id=task_id,
                    )
                )
                return attach_credit_payload({
                    "images": [],
                    "taskId": task_id,
                    "status": "processing",
                    "progress": None,
                    "raw": {
                        "taskId": task_id,
                        "status": "processing",
                        **({"creditReserveId": credit_reserve.id} if credit_reserve else {}),
                    },
                    "conversation": serialize_conversation(refreshed).model_dump(),
                    "assistantMessage": serialize_message(assistant_message).model_dump(),
                }, db, current_user)
            response, raw = result if result is not None else await forward_task
        else:
            response, raw = await forward_task
    except httpx.TimeoutException:
        response = httpx.Response(504, text="504 Gateway Timeout")
        raw = "504 Gateway Timeout"
    except httpx.HTTPError:
        response = httpx.Response(503, text="502 Bad Gateway")
        raw = "502 Bad Gateway"
    duration_ms = elapsed_ms(started_at)

    if not response.is_success or not isinstance(raw, dict):
        if credit_reserve:
            refund_generation_credits(db, credit_reserve.id, reason="图片生成失败自动退款")
        upstream_message = pick_error_message(raw, "图片请求失败。")
        message = generation_public_error_message(raw, response.status_code)
        failed_message = None
        if current_user:
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
                    model_group_id=model_group.id if model_group else None,
                    sub_model_id=sub_model.id if sub_model else None,
                    request=body,
                    response=raw,
                )
            if model_group and sub_model:
                record_call_log(
                    db,
                    user=current_user,
                    model_group_id=model_group.id,
                    sub_model_id=sub_model.id,
                    capability="image",
                    endpoint="/api/proxy/image",
                    status="error",
                    duration_ms=duration_ms,
                    error_message=upstream_message,
                )
        detail = {"message": message}
        if conversation and failed_message and current_user and should_return_generation_failure_payload(response):
            db.commit()
            refreshed = reload_conversation(db, current_user, conversation.id)
            return attach_credit_payload({
                "images": [],
                "status": "failed",
                "progress": None,
                "conversation": serialize_conversation(refreshed).model_dump(mode="json"),
                "assistantMessage": serialize_message(failed_message).model_dump(mode="json"),
            }, db, current_user)
        if conversation and failed_message and current_user:
            db.commit()
            refreshed = reload_conversation(db, current_user, conversation.id)
            detail = {
                **detail,
                "conversation": serialize_conversation(refreshed).model_dump(mode="json"),
                "assistantMessage": serialize_message(failed_message).model_dump(mode="json"),
            }
        elif not current_user and not payload.get("subModelId"):
            detail = {
                **detail,
                **transient_error_conversation(
                    conversation_id=str(payload.get("conversationId") or ""),
                    capability="image",
                    prompt=prompt,
                    error_message=message,
                ),
            }
        raise HTTPException(status_code=response.status_code or 500, detail=detail)

    images, safe_raw = extract_images_from_response(raw)
    task_id = pick_nested_task_id(raw)
    task_status_source = first_string_at_paths(
        raw,
        [
            ("status",),
            ("data", "status"),
            ("data", "data", "status"),
            ("result", "status"),
            ("output", "status"),
        ],
    )
    task_status = normalize_task_status(str(task_status_source or "processing"))
    validation_failures: list[dict[str, Any]] = []
    if images and image_request_is_4k(body):
        images, validation_failures = await validate_4k_images(images, str(body.get("size") or ""))
        if validation_failures and isinstance(safe_raw, dict):
            safe_raw = {**safe_raw, "status": "failed", "failures": validation_failures[:5]}
        if validation_failures:
            task_status = "failed"
    is_async_image_task = bool(task_id and not images and task_status != "failed")
    if credit_reserve and not is_async_image_task:
        if images:
            capture_generation_credits(db, credit_reserve.id)
        else:
            refund_generation_credits(db, credit_reserve.id, reason="图片生成失败自动退款")

    assistant_message = None
    if current_user:
        if conversation:
            assistant_message = add_message(
                db,
                conversation,
                current_user,
                role="assistant",
                capability="image",
                content=task_id if is_async_image_task else "",
                status="processing" if is_async_image_task else "error" if validation_failures else "success",
                error_message=validation_failures[0]["message"] if validation_failures else "",
                can_retry=bool(validation_failures),
                model_group_id=model_group.id if model_group else None,
                sub_model_id=sub_model.id if sub_model else None,
                request=body,
                response={
                    **safe_raw,
                    **({"creditReserveId": credit_reserve.id} if credit_reserve else {}),
                },
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
            if is_async_image_task:
                record_generation_task_event(
                    db,
                    task_id=task_id,
                    event_type="submitted",
                    status="processing",
                    user=current_user,
                    model_group=model_group,
                    sub_model=sub_model,
                    capability="image",
                    endpoint="/api/proxy/image",
                    conversation_id=conversation.id if conversation else "",
                    message_id=assistant_message.id if assistant_message else "",
                    duration_ms=duration_ms,
                    message="Image task submitted.",
                    payload={
                        **summarize_task_payload(safe_raw, task_id=task_id, status="processing"),
                        "providerTaskId": task_id,
                        "conversationId": conversation.id if conversation else "",
                        "messageId": assistant_message.id if assistant_message else "",
                    },
                )
        if model_group and sub_model:
            record_call_log(
                db,
                user=current_user,
                model_group_id=model_group.id,
                sub_model_id=sub_model.id,
                capability="image",
                endpoint="/api/proxy/image",
                status="error" if validation_failures else "success",
                duration_ms=duration_ms,
                error_message=validation_failures[0]["message"] if validation_failures else "",
                prompt_summary=str(body.get("prompt", ""))[:512],
                usage=raw.get("usage"),
            )

    result = {
        "images": images,
        "raw": safe_raw,
        **({"taskId": task_id, "status": "processing"} if is_async_image_task else {}),
        **({"status": "failed", "failures": validation_failures[:5]} if validation_failures else {}),
    }
    attach_credit_payload(result, db, current_user)
    if conversation and current_user:
        db.commit()
        refreshed = reload_conversation(db, current_user, conversation.id)
        result["conversation"] = serialize_conversation(refreshed).model_dump()
        if assistant_message:
            result["assistantMessage"] = serialize_message(assistant_message).model_dump()
    return result


@app.post("/api/proxy/image/query")
async def proxy_image_query(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    validate_reference_limit(payload.get("requestBody") or {})
    check_rate_limit(
        limiter=rate_limiter,
        request=request,
        settings=settings,
        bucket="generation-image-query",
        limit=settings.rate_limit_generation_per_window,
        user_id=current_user.id if current_user else "",
    )
    model_group = None
    sub_model = None
    conversation_id = str(payload.get("conversationId") or "").strip()
    if payload.get("subModelId"):
        model_group, sub_model, api_key_record, api_key = get_sub_model_for_user(db, current_user, str(payload["subModelId"]))
        base_url = api_key_record.base_url
    else:
        base_url, api_key = validate_config(payload.get("config"))
    task_id = str(payload.get("taskId", "")).strip()
    if not task_id:
        raise HTTPException(status_code=400, detail={"message": "缺少任务 ID。"})

    if current_user and conversation_id and is_image_long_task_id(task_id):
        conversation = get_conversation(db, current_user, conversation_id)
        message = find_image_task_message(conversation, task_id)
        if not message:
            message = find_legacy_local_image_task_message(conversation)
        if not message:
            raise HTTPException(status_code=404, detail={"message": "图片任务不存在或已被清理。"})
        return attach_credit_payload(serialize_local_image_task_result(conversation, message, task_id), db, current_user)

    target_url = resolve_url(base_url, resolve_image_query_path(task_id))
    started_at = time.perf_counter()
    response, raw = await forward_json("GET", target_url, api_key)
    duration_ms = elapsed_ms(started_at)

    if not response.is_success or not isinstance(raw, dict):
        upstream_message = pick_error_message(raw, "图片任务查询失败。")
        message = generation_public_error_message(raw, response.status_code)
        failed_message = None
        conversation = None
        if current_user and model_group and sub_model:
            if conversation_id:
                conversation = get_conversation(db, current_user, conversation_id)
                failed_message = mark_image_task_message(
                    db,
                    conversation,
                    current_user,
                    task_id=task_id,
                    model_group_id=model_group.id,
                    sub_model_id=sub_model.id,
                    status="error",
                    content=task_id,
                    error_message=message,
                    can_retry=True,
                    request={"taskId": task_id},
                    response=raw,
                )
                refund_credit_for_message(db, failed_message, task_id=task_id, conversation_id=conversation.id, reason="图片任务查询失败自动退款")
            record_call_log(
                db,
                user=current_user,
                model_group_id=model_group.id,
                sub_model_id=sub_model.id,
                capability="image",
                endpoint="/api/proxy/image/query",
                status="error",
                duration_ms=duration_ms,
                error_message=upstream_message,
            )
        detail = {"message": message}
        if conversation and failed_message and current_user:
            db.commit()
            refreshed = reload_conversation(db, current_user, conversation.id)
            detail = {
                **detail,
                "conversation": serialize_conversation(refreshed).model_dump(mode="json"),
                "assistantMessage": serialize_message(failed_message).model_dump(mode="json"),
                "credits": credit_payload(db, current_user),
            }
        raise HTTPException(status_code=response.status_code or 500, detail=detail)

    result = pick_image_query_payload(raw, task_id)
    if current_user and model_group and sub_model and conversation_id:
        conversation = get_conversation(db, current_user, conversation_id)
        existing_message = find_image_task_message(conversation, task_id)
        original_request = load_message_request(existing_message)
        query_validation_failures: list[dict[str, Any]] = []
        if result.get("images") and image_request_is_4k(original_request):
            valid_images, query_validation_failures = await validate_4k_images(
                result["images"] if isinstance(result["images"], list) else [],
                str(original_request.get("size") or ""),
            )
            result["images"] = valid_images
            if query_validation_failures:
                result["status"] = "failed"
                result["failures"] = query_validation_failures[:5]
                if isinstance(result.get("raw"), dict):
                    result["raw"] = {**result["raw"], "status": "failed", "failures": query_validation_failures[:5]}
        task_status = str(result.get("status") or "")
        message_status = (
            "success"
            if task_status == "completed"
            else "error"
            if task_status == "failed"
            else "processing"
        )
        task_error_message = (
            generation_public_error_message(raw)
            if message_status == "error"
            else ""
        )
        if query_validation_failures:
            task_error_message = query_validation_failures[0]["message"]
        assistant_message = mark_image_task_message(
            db,
            conversation,
            current_user,
            task_id=task_id,
            model_group_id=model_group.id,
            sub_model_id=sub_model.id,
            status=message_status,
            content=str(result.get("status") or task_id) if message_status == "success" else task_id,
            error_message=task_error_message,
            can_retry=message_status == "error",
            request=original_request or {"taskId": task_id},
            response=result.get("raw") if isinstance(result.get("raw"), dict) else raw,
        )
        if message_status == "success":
            capture_credit_for_message(db, assistant_message, task_id=task_id, conversation_id=conversation.id)
        elif message_status == "error":
            refund_credit_for_message(db, assistant_message, task_id=task_id, conversation_id=conversation.id, reason="图片任务失败自动退款")
        if result.get("images") and message_status == "success":
            db.query(GeneratedAsset).filter(GeneratedAsset.message_id == assistant_message.id).delete()
            for image in result["images"]:
                add_asset(
                    db,
                    assistant_message,
                    current_user,
                    capability="image",
                    asset_type="image",
                    url=str(image.get("src") or ""),
                    metadata={
                        "taskId": task_id,
                        "status": result.get("status"),
                        "progress": result.get("progress"),
                        "revisedPrompt": image.get("revisedPrompt"),
                    },
                )
        event_type = "completed" if message_status == "success" else "failed" if message_status == "error" else "updated"
        event_status = "success" if message_status == "success" else "error" if message_status == "error" else "processing"
        record_generation_task_event(
            db,
            task_id=task_id,
            event_type=event_type,
            status=event_status,
            user=current_user,
            model_group=model_group,
            sub_model=sub_model,
            capability="image",
            endpoint="/api/proxy/image/query",
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            duration_ms=duration_ms,
            message=task_error_message or str(result.get("status") or ""),
            payload=summarize_task_payload(
                result.get("raw") if isinstance(result.get("raw"), dict) else raw,
                task_id=task_id,
                status=str(result.get("status") or ""),
                images=result.get("images") if isinstance(result.get("images"), list) else None,
            ),
        )
        db.commit()
        refreshed = reload_conversation(db, current_user, conversation.id)
        result["conversation"] = serialize_conversation(refreshed).model_dump()
        result["assistantMessage"] = serialize_message(assistant_message).model_dump()
        attach_credit_payload(result, db, current_user)
        record_call_log(
            db,
            user=current_user,
            model_group_id=model_group.id,
            sub_model_id=sub_model.id,
            capability="image",
            endpoint="/api/proxy/image/query",
            status="error" if message_status == "error" else "success",
            duration_ms=duration_ms,
            prompt_summary=task_id,
            usage=None,
            error_message=task_error_message,
        )

    return result


@app.get("/api/assets/video-content/{asset_id}")
async def generated_video_content(
    asset_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    asset = db.get(GeneratedAsset, asset_id)
    if not asset or asset.user_id != current_user.id or asset.asset_type != "video":
        raise HTTPException(status_code=404, detail={"message": "视频资源不存在或已被清理。"})
    source_url = asset.url
    if not source_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail={"message": "视频资源地址不可用。"})

    message = db.get(ConversationMessage, asset.message_id)
    if not message or not message.sub_model_id:
        raise HTTPException(status_code=400, detail={"message": "视频资源缺少模型配置，无法播放。"})
    if urlparse(source_url).path.rstrip("/").endswith("/content") and message.response_json:
        try:
            raw_response = json.loads(message.response_json)
        except ValueError:
            raw_response = None
        if isinstance(raw_response, dict):
            refreshed_url = pick_video_query_payload(raw_response, message.content).get("videoUrl")
            if isinstance(refreshed_url, str) and refreshed_url.startswith(("http://", "https://")):
                source_url = refreshed_url

    _model_group, _sub_model, _api_key_record, api_key = get_sub_model_for_user(db, current_user, message.sub_model_id)
    upstream_headers = auth_headers(api_key)
    range_header = request.headers.get("range")
    if range_header:
        upstream_headers["Range"] = range_header
    upstream_headers["Accept"] = "video/*,*/*"

    client = httpx.AsyncClient(timeout=settings.request_timeout_seconds, follow_redirects=True, trust_env=False)
    upstream_response = await client.send(
        client.build_request("GET", source_url, headers=upstream_headers),
        stream=True,
    )
    if not upstream_response.is_success:
        await upstream_response.aread()
        await upstream_response.aclose()
        await client.aclose()
        raise HTTPException(status_code=502, detail={"message": "视频文件获取失败，请稍后重试。"})

    response_headers: dict[str, str] = {
        "Cache-Control": "private, max-age=300",
    }
    for header in ("content-length", "content-range", "accept-ranges", "etag", "last-modified"):
        value = upstream_response.headers.get(header)
        if value:
            response_headers[header.title()] = value

    async def body_iterator():
        try:
            async for chunk in upstream_response.aiter_bytes():
                yield chunk
        finally:
            await upstream_response.aclose()
            await client.aclose()

    return StreamingResponse(
        body_iterator(),
        status_code=upstream_response.status_code,
        media_type=upstream_response.headers.get("content-type") or "video/mp4",
        headers=response_headers,
    )


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
    credit_reserve = None
    if payload.get("subModelId"):
        model_group, sub_model, api_key_record, api_key = get_sub_model_for_user(db, current_user, str(payload["subModelId"]))
        base_url = api_key_record.base_url
        adapter = sub_model.adapter
    else:
        base_url, api_key = validate_config(payload.get("config"))
        adapter = str(payload.get("adapter", "")).strip()
    if not adapter:
        raise HTTPException(status_code=400, detail={"message": "缺少视频适配器。"})

    request_body = payload.get("requestBody") or {}
    validate_reference_limit(request_body)
    reference_assets = collect_reference_image_assets(request_body if isinstance(request_body, dict) else {})
    kkyi_video = is_kkyi_video_model(sub_model, base_url)
    if isinstance(request_body, dict):
        if kkyi_video:
            request_body = normalize_kkyi_video_body(request_body, sub_model.model_name, sub_model)
        else:
            request_body = expand_local_video_references(copy.deepcopy(request_body))
    target_path = "/v1/videos" if kkyi_video else resolve_video_create_path(adapter)
    target_url = resolve_url(base_url, target_path)
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
        user_message = add_message(
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
        add_reference_assets(db, user_message, current_user, capability="video", references=reference_assets)
    if model_group and sub_model:
        credit_reserve = prepare_generation_credit(
            db,
            user=current_user,
            capability="video",
            model_group=model_group,
            sub_model=sub_model,
            conversation_id=conversation.id if conversation else "",
        )
    started_at = time.perf_counter()
    response, raw = await forward_json("POST", target_url, api_key, request_body)
    duration_ms = elapsed_ms(started_at)

    if not response.is_success or not isinstance(raw, dict):
        if credit_reserve:
            refund_generation_credits(db, credit_reserve.id, reason="视频任务提交失败自动退款")
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
                "credits": credit_payload(db, current_user),
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
                response={
                    **raw,
                    **({"creditReserveId": credit_reserve.id} if credit_reserve else {}),
                },
            )
            update_reserved_transaction_refs(
                db,
                credit_reserve,
                conversation_id=conversation.id,
                message_id=assistant_message.id,
                task_id=task_id,
            )
            record_generation_task_event(
                db,
                task_id=task_id,
                event_type="submitted",
                status="processing",
                user=current_user,
                model_group=model_group,
                sub_model=sub_model,
                capability="video",
                endpoint="/api/proxy/video/create",
                conversation_id=conversation.id,
                message_id=assistant_message.id,
                duration_ms=duration_ms,
                message="Video task submitted.",
                payload={
                    **summarize_task_payload(raw, task_id=task_id, status="processing"),
                    "providerTaskId": task_id,
                    "conversationId": conversation.id,
                    "messageId": assistant_message.id,
                },
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
    attach_credit_payload(result, db, current_user)
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
    validate_reference_limit(payload.get("requestBody") or {})
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
    if payload.get("subModelId"):
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

    target_path = (
        f"/v1/video/generations/{quote(task_id)}"
        if is_kkyi_video_model(sub_model, base_url)
        else resolve_video_query_path(adapter, task_id)
    )
    target_url = resolve_url(base_url, target_path)
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
                failed_message = mark_video_task_message(
                    db,
                    conversation,
                    current_user,
                    task_id=task_id,
                    model_group_id=model_group.id,
                    sub_model_id=sub_model.id,
                    status="error",
                    content=task_id,
                    error_message=message,
                    can_retry=True,
                    request={"taskId": task_id},
                    response=raw,
                )
                refund_credit_for_message(db, failed_message, task_id=task_id, conversation_id=conversation.id, reason="视频任务查询失败自动退款")
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
            if conversation and failed_message:
                record_generation_task_event(
                    db,
                    task_id=task_id,
                    event_type="failed",
                    status="error",
                    user=current_user,
                    model_group=model_group,
                    sub_model=sub_model,
                    capability="video",
                    endpoint="/api/proxy/video/query",
                    conversation_id=conversation.id,
                    message_id=failed_message.id,
                    duration_ms=duration_ms,
                    message=message,
                    payload=summarize_task_payload(raw, task_id=task_id, status="failed"),
                )
        detail = upstream_error(raw, "任务查询失败。", response.status_code).detail
        if conversation and failed_message and current_user:
            db.commit()
            refreshed = reload_conversation(db, current_user, conversation.id)
            detail = {
                **detail,
                "conversation": serialize_conversation(refreshed).model_dump(mode="json"),
                "assistantMessage": serialize_message(failed_message).model_dump(mode="json"),
                "credits": credit_payload(db, current_user),
            }
        raise HTTPException(status_code=response.status_code or 500, detail=detail)

    result = pick_video_query_payload(raw, task_id)
    if (
        current_user
        and model_group
        and sub_model
        and conversation_id
    ):
        conversation = get_conversation(db, current_user, conversation_id)
        task_status = str(result.get("status") or "")
        message_status = (
            "success"
            if task_status == "completed"
            else "error"
            if task_status == "failed"
            else "processing"
        )
        task_error_message = (
            pick_video_task_error_message(raw, "视频任务失败，请检查模型后台或稍后重试。")
            if message_status == "error"
            else ""
        )
        assistant_message = mark_video_task_message(
            db,
            conversation,
            current_user,
            task_id=task_id,
            model_group_id=model_group.id,
            sub_model_id=sub_model.id,
            status=message_status,
            content=str(result.get("status") or task_id) if message_status == "success" else task_id,
            error_message=task_error_message,
            can_retry=message_status == "error",
            request={"taskId": task_id},
            response=raw,
        )
        if message_status == "success":
            capture_credit_for_message(db, assistant_message, task_id=task_id, conversation_id=conversation.id)
        elif message_status == "error":
            refund_credit_for_message(db, assistant_message, task_id=task_id, conversation_id=conversation.id, reason="视频任务失败自动退款")
        if result.get("videoUrl") and message_status == "success":
            db.query(GeneratedAsset).filter(GeneratedAsset.message_id == assistant_message.id).delete()
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
        event_type = "completed" if message_status == "success" else "failed" if message_status == "error" else "updated"
        event_status = "success" if message_status == "success" else "error" if message_status == "error" else "processing"
        record_generation_task_event(
            db,
            task_id=task_id,
            event_type=event_type,
            status=event_status,
            user=current_user,
            model_group=model_group,
            sub_model=sub_model,
            capability="video",
            endpoint="/api/proxy/video/query",
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            duration_ms=duration_ms,
            message=task_error_message or str(result.get("status") or ""),
            payload=summarize_task_payload(
                result.get("raw") if isinstance(result.get("raw"), dict) else raw,
                task_id=task_id,
                status=str(result.get("status") or ""),
                video_url=str(result.get("videoUrl") or ""),
            ),
        )
        db.commit()
        refreshed = reload_conversation(db, current_user, conversation.id)
        result["conversation"] = serialize_conversation(refreshed).model_dump()
        result["assistantMessage"] = serialize_message(assistant_message).model_dump()
        attach_credit_payload(result, db, current_user)
        record_call_log(
            db,
            user=current_user,
            model_group_id=model_group.id,
            sub_model_id=sub_model.id,
            capability="video",
            endpoint="/api/proxy/video/query",
            status="error" if message_status == "error" else "success",
            duration_ms=duration_ms,
            prompt_summary=task_id,
            usage=None,
            error_message=task_error_message,
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
    file_name = str(payload.get("fileName") or "upload.bin")
    content_type = str(payload.get("contentType") or "application/octet-stream")
    if settings.object_storage_enabled:
        return create_presigned_put_url(
            settings=settings,
            file_name=file_name,
            content_type=content_type,
            expires_in=900,
        )

    if payload.get("subModelId"):
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
    try:
        response, raw = await forward_json("POST", target_url, api_key, body)
    except httpx.HTTPError as exc:
        if not settings.object_storage_enabled:
            raise HTTPException(
                status_code=503,
                detail={
                    "message": f"object storage not configured; upstream upload presign failed: {exc}",
                },
            ) from exc
        raise upstream_error(str(exc), "获取上传地址失败。", 503) from exc

    if not response.is_success or not isinstance(raw, dict):
        error = upstream_error(raw, "获取上传地址失败。", response.status_code)
        if not settings.object_storage_enabled:
            detail = error.detail if isinstance(error.detail, dict) else {"message": str(error.detail)}
            upstream_message = str(detail.get("message") or "upload presign failed")
            detail["message"] = f"object storage not configured; upstream upload presign failed: {upstream_message}"
            raise HTTPException(status_code=error.status_code, detail=detail)
        raise error

    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    if not raw.get("success") or not data:
        error = upstream_error(raw, "上传服务未正确返回预签名地址。", 500)
        if not settings.object_storage_enabled:
            detail = error.detail if isinstance(error.detail, dict) else {"message": str(error.detail)}
            upstream_message = str(detail.get("message") or "upload presign failed")
            detail["message"] = f"object storage not configured; upstream upload presign failed: {upstream_message}"
            raise HTTPException(status_code=error.status_code, detail=detail)
        raise error

    return {
        "uploadUrl": data.get("upload_url") if isinstance(data.get("upload_url"), str) else "",
        "method": data.get("method") if isinstance(data.get("method"), str) else "PUT",
        "publicUrl": data.get("public_url") if isinstance(data.get("public_url"), str) else "",
        "objectKey": data.get("object_key") if isinstance(data.get("object_key"), str) else "",
        "contentType": data.get("content_type") if isinstance(data.get("content_type"), str) else body["content_type"],
    }
