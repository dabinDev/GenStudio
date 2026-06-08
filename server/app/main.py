from __future__ import annotations

import base64
import binascii
import copy
import json
from pathlib import Path
import time
from uuid import uuid4
from typing import Any
from urllib.parse import quote, urlparse

import httpx
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
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
    is_admin_user,
    register_local_user,
    require_admin_user,
    require_csrf,
    serialize_user,
    update_user_profile,
    upsert_user,
)
from app.admin_service import (
    admin_delete_user,
    admin_disable_user,
    admin_enable_user,
    admin_overview,
    admin_restore_user,
    get_prompt_template_for_scope,
    list_admin_audit_logs,
    list_admin_creation_records,
    list_admin_models,
    list_admin_users,
    list_prompt_templates,
    publish_model,
    render_prompt_template,
    serialize_admin_user,
    serialize_prompt_template,
    unpublish_model,
    update_admin_model,
    update_admin_user,
    upsert_prompt_template,
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
)
from app.catalog_service import (
    fetch_kkyi_catalog_details,
    list_catalog_models,
    normalize_existing_catalog_icons,
    serialize_catalog_model,
    sync_catalog_details,
)
from app.database import get_db, init_db
from app.db_models import CallLog, Conversation, ConversationMessage, GeneratedAsset, User, utcnow
from app.model_service import (
    create_model_group,
    delete_model_group,
    elapsed_ms,
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
from app.proxy_utils import (
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
from app.schemas import (
    AdminModelUpdate,
    AdminUserUpdate,
    ConversationCreate,
    DevLoginRequest,
    LoginRequest,
    KkyiCatalogSyncRequest,
    ModelCreate,
    ModelUpdate,
    PromptOptimizeRequest,
    PromptTemplateUpdate,
    ProfileUpdateRequest,
    RegisterRequest,
)
from app.security import decrypt_secret
from app.storage import create_presigned_put_url

app = FastAPI(title="塞隆studio Server")
GENERATED_ASSET_DIR = Path(__file__).resolve().parents[2] / "generated_assets"
GENERATED_ASSET_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploaded_assets"
LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_INLINE_REFERENCE_LENGTH = 10 * 1024 * 1024
FRONTEND_ROUTES = {"auth", "auth-error", "text", "images", "videos", "settings", "profile", "admin"}
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
                "你是塞隆studio的专业提示词优化助手。请把用户的简短需求扩写成更准确、可执行的创作提示词。"
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
            "content": "你是塞隆studio的专业提示词优化助手，只输出优化后的提示词正文。",
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


def normalize_kkyi_video_body(request_body: dict[str, Any], model_name: str, sub_model: Any | None = None) -> dict[str, Any]:
    prompt = extract_video_prompt(request_body)
    normalized: dict[str, Any] = {
        "model": str(request_body.get("model") or model_name).strip(),
        "prompt": prompt,
    }
    field_map = {
        "ratio": ("ratio", "aspect_ratio"),
        "duration": ("duration",),
        "resolution": ("resolution", "size"),
        "generate_audio": ("generate_audio", "audio"),
        "quantity": ("quantity", "n", "count"),
        "video_mode": ("video_mode", "mode"),
        "img_url": ("img_url",),
        "first_frame": ("first_frame",),
        "last_frame": ("last_frame",),
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
        try:
            response = json.loads(message.response_json or "{}")
        except ValueError:
            response = {}
        if isinstance(response, dict) and pick_nested_task_id(response) == task_id:
            return message
    return None


def delete_duplicate_image_task_messages(db: Session, conversation: Conversation, keep_message: ConversationMessage, task_id: str) -> None:
    for message in list(conversation.messages):
        if message.id == keep_message.id:
            continue
        if message.role == "assistant" and message.capability == "image" and message.content in {task_id, "completed"}:
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


def persist_generated_image_from_b64(value: str) -> str:
    try:
        image_bytes = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return f"data:image/png;base64,{value}"
    file_name = f"{uuid4().hex}.png"
    (GENERATED_ASSET_DIR / file_name).write_bytes(image_bytes)
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


def expand_local_image_references(body: dict[str, Any]) -> dict[str, Any]:
    reference_key = "image" if "image" in body else "images" if "images" in body else "image"
    references = body.get(reference_key)
    if isinstance(references, str):
        body[reference_key] = local_asset_data_url(references)
        return body
    if isinstance(references, list):
        body[reference_key] = [local_asset_data_url(item) if isinstance(item, str) else item for item in references]
    return body


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
        for key in ("url", "image_url", "imageUrl", "download_url"):
            if isinstance(item.get(key), str) and item[key].strip():
                src = item[key].strip()
                break
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
    return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=exc.headers)


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


@app.get("/api/assets/uploads/{file_name}")
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
    current_user: User | None = Depends(get_optional_current_user),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    is_admin = is_admin_user(current_user, settings)
    return {
        "models": [
            serialize_model(item, current_user, is_admin=is_admin).model_dump()
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
    is_admin = is_admin_user(current_user, settings)
    model = create_model_group(db, current_user, payload, is_admin=is_admin)
    return {"model": serialize_model(model, current_user, is_admin=is_admin).model_dump()}


@app.put("/api/models/{model_id}")
async def update_model(
    model_id: str,
    payload: ModelUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    is_admin = is_admin_user(current_user, settings)
    model = update_model_group(db, current_user, model_id, payload, is_admin=is_admin)
    return {"model": serialize_model(model, current_user, is_admin=is_admin).model_dump()}


@app.delete("/api/models/{model_id}")
async def delete_model(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, bool]:
    delete_model_group(db, current_user, model_id, is_admin=is_admin_user(current_user, settings))
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
    is_admin = is_admin_user(current_user, settings)
    model = set_primary_sub_model(db, current_user, model_id, sub_model_id, is_admin=is_admin)
    return {"model": serialize_model(model, current_user, is_admin=is_admin).model_dump()}


@app.post("/api/models/{model_id}/sync")
async def sync_model_list(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    is_admin = is_admin_user(current_user, settings)
    model = get_model_group(db, current_user, model_id, is_admin=is_admin, require_edit=True)
    api_key = model.api_key
    target_url = resolve_url(api_key.base_url, "/v1/models")
    started_at = time.perf_counter()
    response, raw = await forward_json("GET", target_url, api_key=decrypt_secret(api_key.api_key_ciphertext))
    duration_ms = elapsed_ms(started_at)
    if not response.is_success or not isinstance(raw, dict):
        raise upstream_error(raw, "获取模型列表失败。", response.status_code)
    result = sync_models_from_raw(db, model, raw, duration_ms, user=current_user, is_admin=is_admin)
    return result.model_dump()


@app.get("/api/admin/models")
async def admin_models(
    capability: str = "all",
    search: str = "",
    publicState: str = "all",
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
) -> dict[str, Any]:
    return {
        "models": [
            serialize_model(item, admin, is_admin=True).model_dump()
            for item in list_admin_models(db, capability=capability, search=search, public_state=publicState)
        ]
    }


@app.put("/api/admin/models/{model_id}")
async def admin_update_model(
    model_id: str,
    payload: AdminModelUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    model = update_admin_model(db, admin, model_id, payload)
    return {"model": serialize_model(model, admin, is_admin=True).model_dump()}


@app.post("/api/admin/models/{model_id}/publish")
async def admin_publish_model(
    model_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    model = publish_model(db, admin, model_id)
    return {"model": serialize_model(model, admin, is_admin=True).model_dump()}


@app.post("/api/admin/models/{model_id}/unpublish")
async def admin_unpublish_model(
    model_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    model = unpublish_model(db, admin, model_id)
    return {"model": serialize_model(model, admin, is_admin=True).model_dump()}


@app.get("/api/admin/overview")
async def admin_overview_route(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict[str, Any]:
    return admin_overview(db)


@app.get("/api/admin/overview/users")
async def admin_overview_users_route(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict[str, Any]:
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
            }
        )
    return {"users": rows}


@app.get("/api/admin/overview/models")
async def admin_overview_models_route(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
) -> dict[str, Any]:
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
    _admin: User = Depends(require_admin_user),
) -> dict[str, Any]:
    return {"templates": [serialize_prompt_template(item) for item in list_prompt_templates(db, capability=capability)]}


@app.put("/api/admin/prompt-templates/{template_id}")
async def admin_save_prompt_template(
    template_id: str,
    payload: PromptTemplateUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    _ = template_id
    item = upsert_prompt_template(db, admin, payload)
    return {"template": serialize_prompt_template(item)}


@app.post("/api/admin/prompt-templates/test")
async def admin_test_prompt_template(
    payload: dict[str, Any],
    _admin: User = Depends(require_admin_user),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    content = str(payload.get("content") or "")
    prompt = str(payload.get("prompt") or "")
    rendered = render_prompt_template(content, {"prompt": prompt, "capability": payload.get("capability") or "text"})
    return {"prompt": rendered}


@app.get("/api/admin/users")
async def admin_users(
    search: str = "",
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict[str, Any]:
    return {"users": [serialize_admin_user(item) for item in list_admin_users(db, search=search)]}


@app.put("/api/admin/users/{user_id}")
async def admin_update_user_route(
    user_id: str,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    return {"user": serialize_admin_user(update_admin_user(db, admin, user_id, payload))}


@app.post("/api/admin/users/{user_id}/disable")
async def admin_disable_user_route(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    return {"user": serialize_admin_user(admin_disable_user(db, admin, user_id))}


@app.post("/api/admin/users/{user_id}/enable")
async def admin_enable_user_route(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    return {"user": serialize_admin_user(admin_enable_user(db, admin, user_id))}


@app.post("/api/admin/users/{user_id}/delete")
async def admin_delete_user_route(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    return {"user": serialize_admin_user(admin_delete_user(db, admin, user_id))}


@app.post("/api/admin/users/{user_id}/restore")
async def admin_restore_user_route(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    return {"user": serialize_admin_user(admin_restore_user(db, admin, user_id))}


@app.get("/api/admin/records/text")
async def admin_text_records(
    userId: str = "",
    userSearch: str = "",
    modelGroupId: str = "",
    status: str = "",
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict[str, Any]:
    return {
        "records": list_admin_creation_records(
            db, capability="text", user_id=userId, user_search=userSearch, model_group_id=modelGroupId, status=status
        )
    }


@app.get("/api/admin/records/images")
async def admin_image_records(
    userId: str = "",
    userSearch: str = "",
    modelGroupId: str = "",
    status: str = "",
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict[str, Any]:
    return {
        "records": list_admin_creation_records(
            db, capability="image", user_id=userId, user_search=userSearch, model_group_id=modelGroupId, status=status
        )
    }


@app.get("/api/admin/records/videos")
async def admin_video_records(
    userId: str = "",
    userSearch: str = "",
    modelGroupId: str = "",
    status: str = "",
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict[str, Any]:
    return {
        "records": list_admin_creation_records(
            db, capability="video", user_id=userId, user_search=userSearch, model_group_id=modelGroupId, status=status
        )
    }


@app.get("/api/admin/audit-logs")
async def admin_audit_logs(
    action: str = "",
    adminUserId: str = "",
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict[str, Any]:
    return {"logs": list_admin_audit_logs(db, action=action, admin_user_id=adminUserId)}


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
        target_path = "/v1/video/generations"
        body = normalize_kkyi_video_body(body, sub_model.model_name, sub_model)
    target_url = resolve_url(base_url, target_path)
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
    if payload.get("subModelId"):
        model_group, sub_model, api_key_record, api_key = get_sub_model_for_user(db, current_user, str(payload["subModelId"]))
        base_url = api_key_record.base_url
        model = sub_model.model_name
    else:
        base_url, api_key = validate_config(payload.get("config"))
        model = str(payload.get("model", "")).strip()
    if not model:
        raise HTTPException(status_code=400, detail={"message": "缺少模型标识。"})

    body = {"model": model, **(payload.get("requestBody") or {})}
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
        add_message(
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
    started_at = time.perf_counter()
    try:
        if edit_references:
            edit_data = {
                key: str(value)
                for key, value in body.items()
                if key != "image" and value is not None
            }
            edit_files = [
                ("image", (reference["filename"], reference["content"], reference["content_type"]))
                for reference in edit_references
            ]
            response, raw = await forward_multipart(target_url, api_key, data=edit_data, files=edit_files)
            if (not response.is_success or not isinstance(raw, dict)) and is_non_json_upstream_error(raw):
                body = expand_local_image_references(copy.deepcopy(body))
                target_url = resolve_url(base_url, "/v1/images/generations")
                response, raw = await forward_json("POST", target_url, api_key, body)
        else:
            response, raw = await forward_json("POST", target_url, api_key, body)
    except httpx.TimeoutException:
        response = httpx.Response(504, text="504 Gateway Timeout")
        raw = "504 Gateway Timeout"
    except httpx.HTTPError:
        response = httpx.Response(503, text="502 Bad Gateway")
        raw = "502 Bad Gateway"
    duration_ms = elapsed_ms(started_at)

    if not response.is_success or not isinstance(raw, dict):
        message = pick_error_message(raw, "图片请求失败。")
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
    is_async_image_task = bool(task_id and not images and task_status != "failed")

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
                status="processing" if is_async_image_task else "success",
                can_retry=False,
                model_group_id=model_group.id if model_group else None,
                sub_model_id=sub_model.id if sub_model else None,
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
        if model_group and sub_model:
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

    result = {
        "images": images,
        "raw": safe_raw,
        **({"taskId": task_id, "status": "processing"} if is_async_image_task else {}),
    }
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
        raise HTTPException(status_code=400, detail={"message": "缂哄皯浠诲姟 ID銆?"})

    target_url = resolve_url(base_url, resolve_image_query_path(task_id))
    started_at = time.perf_counter()
    response, raw = await forward_json("GET", target_url, api_key)
    duration_ms = elapsed_ms(started_at)

    if not response.is_success or not isinstance(raw, dict):
        message = pick_error_message(raw, "鍥剧墖浠诲姟鏌ヨ澶辫触銆?")
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
            record_call_log(
                db,
                user=current_user,
                model_group_id=model_group.id,
                sub_model_id=sub_model.id,
                capability="image",
                endpoint="/api/proxy/image/query",
                status="error",
                duration_ms=duration_ms,
                error_message=message,
            )
        detail = upstream_error(raw, "鍥剧墖浠诲姟鏌ヨ澶辫触銆?", response.status_code).detail
        if conversation and failed_message and current_user:
            db.commit()
            refreshed = reload_conversation(db, current_user, conversation.id)
            detail = {
                **detail,
                "conversation": serialize_conversation(refreshed).model_dump(mode="json"),
                "assistantMessage": serialize_message(failed_message).model_dump(mode="json"),
            }
        raise HTTPException(status_code=response.status_code or 500, detail=detail)

    result = pick_image_query_payload(raw, task_id)
    if current_user and model_group and sub_model and conversation_id:
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
            pick_video_task_error_message(raw, "鍥剧墖浠诲姟澶辫触锛岃妫€鏌ユā鍨嬪悗鍙版垨绋嶅悗閲嶈瘯銆?")
            if message_status == "error"
            else ""
        )
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
            request={"taskId": task_id},
            response=raw,
        )
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
        db.commit()
        refreshed = reload_conversation(db, current_user, conversation.id)
        result["conversation"] = serialize_conversation(refreshed).model_dump()
        result["assistantMessage"] = serialize_message(assistant_message).model_dump()
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
    if isinstance(request_body, dict):
        request_body = expand_local_video_references(copy.deepcopy(request_body))
        if is_kkyi_video_model(sub_model, base_url):
            request_body = normalize_kkyi_video_body(request_body, sub_model.model_name, sub_model)
    target_path = "/v1/video/generations" if is_kkyi_video_model(sub_model, base_url) else resolve_video_create_path(adapter)
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
