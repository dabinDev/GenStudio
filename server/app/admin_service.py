from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.auth import is_admin_user
from app.config import Settings, get_settings
from app.db_models import (
    AdminOperationLog,
    CallLog,
    Conversation,
    ConversationMessage,
    GeneratedAsset,
    ModelGroup,
    PromptTemplate,
    SessionRecord,
    User,
)
from app.model_service import catalog_loader_options
from app.schemas import AdminModelUpdate, AdminUserUpdate, PromptTemplateUpdate


def json_dumps_safe(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def parse_json_object(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except Exception:
        return fallback


def write_admin_log(
    db: Session,
    admin: User,
    *,
    action: str,
    target_type: str,
    target_id: str = "",
    status: str = "success",
    summary: dict[str, Any] | None = None,
) -> AdminOperationLog:
    item = AdminOperationLog(
        admin_user_id=admin.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        status=status,
        summary_json=json_dumps_safe(summary or {}),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_admin_models(
    db: Session,
    *,
    capability: str = "all",
    search: str = "",
    public_state: str = "all",
) -> list[ModelGroup]:
    query = db.query(ModelGroup).options(*catalog_loader_options())
    if capability in {"text", "image", "video"}:
        query = query.filter(ModelGroup.capability == capability)
    if public_state == "public":
        query = query.filter(ModelGroup.is_public.is_(True))
    elif public_state == "private":
        query = query.filter(ModelGroup.is_public.is_(False))
    clean_search = search.strip()
    if clean_search:
        like = f"%{clean_search}%"
        query = query.filter(
            or_(
                ModelGroup.name.ilike(like),
                ModelGroup.vendor.ilike(like),
                ModelGroup.description.ilike(like),
                ModelGroup.public_display_name.ilike(like),
            )
        )
    return query.order_by(ModelGroup.updated_at.desc()).limit(200).all()


def get_admin_model(db: Session, model_id: str) -> ModelGroup:
    model = db.query(ModelGroup).options(*catalog_loader_options()).filter(ModelGroup.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail={"message": "模型不存在。"})
    return model


def update_admin_model(db: Session, admin: User, model_id: str, payload: AdminModelUpdate) -> ModelGroup:
    model = get_admin_model(db, model_id)
    if payload.publicDisplayName is not None:
        model.public_display_name = payload.publicDisplayName.strip()
    if payload.publicDescription is not None:
        model.public_description = payload.publicDescription.strip()
    if payload.inputHint is not None:
        model.input_hint = payload.inputHint.strip()
    if payload.iconUrl is not None:
        model.icon_url = payload.iconUrl.strip()
    if payload.publicTags is not None:
        model.public_tags_json = json_dumps_safe([item.strip() for item in payload.publicTags if item.strip()])
    if payload.promptOptimizeEnabled is not None:
        model.prompt_optimize_enabled = payload.promptOptimizeEnabled
    if payload.defaultParameters is not None:
        model.default_parameters_json = json_dumps_safe(payload.defaultParameters)
    if payload.isPublic is not None:
        model.is_public = payload.isPublic
    db.commit()
    db.refresh(model)
    write_admin_log(
        db,
        admin,
        action="update_model",
        target_type="model",
        target_id=model.id,
        summary={"isPublic": model.is_public},
    )
    return get_admin_model(db, model.id)


def publish_model(db: Session, admin: User, model_id: str) -> ModelGroup:
    model = get_admin_model(db, model_id)
    model.is_public = True
    db.commit()
    db.refresh(model)
    write_admin_log(db, admin, action="publish_model", target_type="model", target_id=model.id)
    return get_admin_model(db, model.id)


def unpublish_model(db: Session, admin: User, model_id: str) -> ModelGroup:
    model = get_admin_model(db, model_id)
    model.is_public = False
    db.commit()
    db.refresh(model)
    write_admin_log(db, admin, action="unpublish_model", target_type="model", target_id=model.id)
    return get_admin_model(db, model.id)


def list_prompt_templates(db: Session, *, capability: str = "all") -> list[PromptTemplate]:
    query = db.query(PromptTemplate)
    if capability in {"text", "image", "video"}:
        query = query.filter(PromptTemplate.capability == capability)
    return query.order_by(PromptTemplate.capability, PromptTemplate.model_group_id, PromptTemplate.updated_at.desc()).all()


def upsert_prompt_template(db: Session, admin: User, payload: PromptTemplateUpdate) -> PromptTemplate:
    capability = (payload.capability or "text").strip().lower()
    if capability not in {"text", "image", "video"}:
        raise HTTPException(status_code=400, detail={"message": "不支持的创作类型。"})
    model_group_id = (payload.modelGroupId or "").strip()
    template_type = (payload.templateType or "prompt_optimize").strip() or "prompt_optimize"
    item = (
        db.query(PromptTemplate)
        .filter(
            PromptTemplate.capability == capability,
            PromptTemplate.model_group_id == model_group_id,
            PromptTemplate.template_type == template_type,
        )
        .first()
    )
    if not item:
        item = PromptTemplate(capability=capability, model_group_id=model_group_id, template_type=template_type)
        db.add(item)
    if payload.name is not None:
        item.name = payload.name.strip()
    if payload.content is not None:
        item.content = payload.content
    if payload.enabled is not None:
        item.enabled = payload.enabled
    item.updated_by = admin.id
    db.commit()
    db.refresh(item)
    write_admin_log(db, admin, action="save_prompt_template", target_type="prompt_template", target_id=item.id)
    return item


def get_prompt_template_for_scope(
    db: Session,
    capability: str,
    model_group_id: str = "",
    template_type: str = "prompt_optimize",
) -> PromptTemplate:
    clean_capability = capability.strip().lower()
    clean_model_id = model_group_id.strip()
    if clean_model_id:
        item = (
            db.query(PromptTemplate)
            .filter(
                PromptTemplate.capability == clean_capability,
                PromptTemplate.model_group_id == clean_model_id,
                PromptTemplate.template_type == template_type,
                PromptTemplate.enabled.is_(True),
            )
            .first()
        )
        if item:
            return item
    item = (
        db.query(PromptTemplate)
        .filter(
            PromptTemplate.capability == clean_capability,
            PromptTemplate.model_group_id == "",
            PromptTemplate.template_type == template_type,
            PromptTemplate.enabled.is_(True),
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail={"message": "未配置可用的提示语模板。"})
    return item


def render_prompt_template(template: str, values: dict[str, Any]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    return rendered


def list_admin_users(db: Session, *, search: str = "") -> list[User]:
    query = db.query(User)
    clean_search = search.strip()
    if clean_search:
        like = f"%{clean_search}%"
        query = query.filter(
            or_(
                User.email.ilike(like),
                User.nickname.ilike(like),
                User.phone.ilike(like),
                User.id.ilike(like),
                User.external_user_id.ilike(like),
            )
        )
    return query.order_by(User.created_at.desc()).limit(200).all()


def get_admin_user(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"message": "用户不存在。"})
    return user


def ensure_can_manage_user(admin: User, target: User, settings: Settings | None = None) -> None:
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail={"message": "不能操作自己的管理员账号。"})
    resolved_settings = settings or get_settings()
    if is_admin_user(target, resolved_settings):
        raise HTTPException(status_code=400, detail={"message": "不能操作管理员账号。"})


def update_admin_user(db: Session, admin: User, user_id: str, payload: AdminUserUpdate) -> User:
    user = get_admin_user(db, user_id)
    ensure_can_manage_user(admin, user)
    if payload.email is not None:
        user.email = payload.email.strip().lower()
    if payload.phone is not None:
        user.phone = payload.phone.strip()
    if payload.nickname is not None:
        user.nickname = payload.nickname.strip()
    if payload.avatarUrl is not None:
        user.avatar_url = payload.avatarUrl.strip()
    if payload.status is not None:
        user.status = payload.status.strip()
    db.commit()
    db.refresh(user)
    write_admin_log(db, admin, action="update_user", target_type="user", target_id=user.id)
    return user


def set_user_status(db: Session, admin: User, user_id: str, status: str, action: str) -> User:
    user = get_admin_user(db, user_id)
    ensure_can_manage_user(admin, user)
    user.status = status
    if status in {"disabled", "deleted"}:
        db.query(SessionRecord).filter(SessionRecord.user_id == user.id).delete()
    db.commit()
    db.refresh(user)
    write_admin_log(db, admin, action=action, target_type="user", target_id=user.id, summary={"status": status})
    return user


def admin_disable_user(db: Session, admin: User, user_id: str) -> User:
    return set_user_status(db, admin, user_id, "disabled", "disable_user")


def admin_enable_user(db: Session, admin: User, user_id: str) -> User:
    return set_user_status(db, admin, user_id, "active", "enable_user")


def admin_delete_user(db: Session, admin: User, user_id: str) -> User:
    return set_user_status(db, admin, user_id, "deleted", "delete_user")


def admin_restore_user(db: Session, admin: User, user_id: str) -> User:
    return set_user_status(db, admin, user_id, "active", "restore_user")


def _safe_number(value: Any) -> float:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return 0
    return 0


def _find_first_number(value: Any, keys: set[str]) -> float:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized_key in keys:
                number = _safe_number(item)
                if number:
                    return number
        for item in value.values():
            number = _find_first_number(item, keys)
            if number:
                return number
    if isinstance(value, list):
        for item in value:
            number = _find_first_number(item, keys)
            if number:
                return number
    return 0


def _usage_units(item: CallLog) -> float:
    usage = parse_json_object(item.raw_usage_json, {})
    if not isinstance(usage, dict):
        return 0
    token_units = _find_first_number(
        usage,
        {
            "totaltokens",
            "totalTokens".lower(),
            "tokens",
            "tokencount",
            "totalcount",
        },
    )
    if token_units:
        return token_units
    return _find_first_number(
        usage,
        {
            "credits",
            "credit",
            "quota",
            "cost",
            "amount",
            "totalprice",
            "price",
            "bill",
        },
    )


def _queue_time_ms(item: CallLog) -> int:
    request_params = parse_json_object(item.request_params_json, {})
    response_summary = parse_json_object(item.response_summary_json, {})
    queue_ms = _find_first_number(
        {"request": request_params, "response": response_summary},
        {
            "queuems",
            "queuetimems",
            "waitingms",
            "waitms",
            "pendingms",
        },
    )
    if queue_ms:
        return int(queue_ms)
    queue_seconds = _find_first_number(
        {"request": request_params, "response": response_summary},
        {
            "queueseconds",
            "queuetime",
            "waitingseconds",
            "waitseconds",
        },
    )
    return int(queue_seconds * 1000) if queue_seconds else 0


def _is_timeout_log(item: CallLog) -> bool:
    text = f"{item.status} {item.error_message} {item.prompt_summary}".lower()
    if any(word in text for word in ["timeout", "timed out", "超时", "504", "gateway time-out"]):
        return True
    return item.status != "success" and item.duration_ms >= 120_000


def _bucket_start(value: datetime, period: str) -> datetime:
    if period == "week":
        start = value - timedelta(days=value.weekday())
        return datetime(start.year, start.month, start.day)
    if period == "month":
        return datetime(value.year, value.month, 1)
    return datetime(value.year, value.month, value.day)


def _trend_buckets(logs: list[CallLog], *, period: str, count: int) -> list[dict[str, Any]]:
    now = datetime.utcnow()
    if period == "month":
        starts = []
        year = now.year
        month = now.month
        for offset in range(count - 1, -1, -1):
            target_month = month - offset
            target_year = year
            while target_month <= 0:
                target_month += 12
                target_year -= 1
            starts.append(datetime(target_year, target_month, 1))
    else:
        step = timedelta(weeks=1 if period == "week" else 0, days=0 if period == "week" else 1)
        current = _bucket_start(now, period)
        starts = [current - (step * offset) for offset in range(count - 1, -1, -1)]

    rows: list[dict[str, Any]] = []
    for start in starts:
        if period == "month":
            next_month = start.month + 1
            next_year = start.year
            if next_month > 12:
                next_month = 1
                next_year += 1
            end = datetime(next_year, next_month, 1)
            label = start.strftime("%Y-%m")
        elif period == "week":
            end = start + timedelta(days=7)
            label = f"{start.strftime('%m-%d')}~{(end - timedelta(days=1)).strftime('%m-%d')}"
        else:
            end = start + timedelta(days=1)
            label = start.strftime("%m-%d")
        bucket = [item for item in logs if start <= item.created_at < end]
        total = len(bucket)
        failed = len([item for item in bucket if item.status != "success"])
        duration_total = sum(item.duration_ms for item in bucket)
        rows.append(
            {
                "label": label,
                "totalCalls": total,
                "successCalls": total - failed,
                "failedCalls": failed,
                "quotaUnits": round(sum(_usage_units(item) for item in bucket), 2),
                "averageDurationMs": int(duration_total / total) if total else 0,
            }
        )
    return rows


def admin_overview(db: Session) -> dict[str, Any]:
    logs = db.query(CallLog).all()
    total = len(logs)
    failed = len([item for item in logs if item.status != "success"])
    success = total - failed
    average_duration_ms = int(sum(item.duration_ms for item in logs) / total) if total else 0
    public_calls = len([item for item in logs if item.is_public_model])
    queue_values = [_queue_time_ms(item) for item in logs]
    queue_samples = [item for item in queue_values if item > 0]
    timeout_calls = len([item for item in logs if _is_timeout_log(item)])
    by_model: dict[str, list[CallLog]] = {}
    for item in logs:
        by_model.setdefault(item.model_group_id or "", []).append(item)
    failed_models: list[dict[str, Any]] = []
    for model_id, model_logs in by_model.items():
        if not model_id:
            continue
        model_failed = [item for item in model_logs if item.status != "success"]
        if not model_failed:
            continue
        model = db.get(ModelGroup, model_id)
        failed_models.append(
            {
                "modelGroupId": model_id,
                "modelName": model.public_display_name or model.name if model else model_id,
                "capability": model.capability if model else "",
                "failedCalls": len(model_failed),
                "totalCalls": len(model_logs),
                "failureRate": len(model_failed) / len(model_logs) if model_logs else 0,
                "lastError": model_failed[-1].error_message,
            }
        )
    failed_models.sort(key=lambda item: (item["failedCalls"], item["failureRate"]), reverse=True)
    return {
        "totalCalls": total,
        "successCalls": success,
        "failedCalls": failed,
        "failureRate": failed / total if total else 0,
        "averageDurationMs": average_duration_ms,
        "publicModelCalls": public_calls,
        "privateModelCalls": total - public_calls,
        "quotaUnits": round(sum(_usage_units(item) for item in logs), 2),
        "averageQueueMs": int(sum(queue_samples) / len(queue_samples)) if queue_samples else 0,
        "timeoutCalls": timeout_calls,
        "timeoutRate": timeout_calls / total if total else 0,
        "trend": {
            "day": _trend_buckets(logs, period="day", count=14),
            "week": _trend_buckets(logs, period="week", count=8),
            "month": _trend_buckets(logs, period="month", count=6),
        },
        "failedModels": failed_models[:8],
    }


def _load_json(value: str, fallback: Any) -> Any:
    try:
        parsed = json.loads(value or "")
    except Exception:
        return fallback
    return parsed if isinstance(parsed, type(fallback)) else fallback


BROKEN_HISTORY_PLACEHOLDER = "历史内容编码异常，无法还原。"


def _is_broken_history_text(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    compact = re.sub(r"\s+", "", text)
    question_marks = compact.count("?")
    if question_marks >= 4:
        return True
    if "??" in compact:
        return True
    if len(compact) >= 2 and question_marks / len(compact) > 0.2:
        return True
    mojibake_chars = len(re.findall(r"[锟�鐢瑙鍥閸缂闈瑕鐞绠妯鍚彴鎿浣濉殕荤]", text))
    if len(text) >= 12 and mojibake_chars / len(text) > 0.28:
        return True
    latin_mojibake_chars = len(re.findall(r"[ÃÂåæçèéêïð¤¥¦§¨©ª«¬®¯°±²³´µ¶·¸¹º»¼½¾¿-]", text))
    return len(text) >= 6 and latin_mojibake_chars / len(text) > 0.18


def _restore_latin1_mojibake(value: str) -> str:
    try:
        restored = value.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    return restored if restored and not _is_broken_history_text(restored) else value


def _clean_history_value(value: Any) -> Any:
    if isinstance(value, str):
        restored = _restore_latin1_mojibake(value)
        return BROKEN_HISTORY_PLACEHOLDER if _is_broken_history_text(restored) else restored
    if isinstance(value, list):
        return [_clean_history_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _clean_history_value(item) for key, item in value.items()}
    return value


def _nested_value(value: Any, keys: set[str]) -> Any:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).strip().lower() in keys:
                return item
        for item in value.values():
            nested = _nested_value(item, keys)
            if nested not in (None, ""):
                return nested
    if isinstance(value, list):
        for item in value:
            nested = _nested_value(item, keys)
            if nested not in (None, ""):
                return nested
    return None


def _normalized_filter_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else str(value)
    return str(value).strip().lower()


def _count_reference_assets(params: dict[str, Any]) -> int:
    candidates = [
        params.get("images"),
        params.get("image"),
        params.get("referenceImages"),
        params.get("reference_images"),
        params.get("attachments"),
        params.get("firstFrame"),
        params.get("lastFrame"),
    ]
    count = 0
    for item in candidates:
        if isinstance(item, list):
            count += len([entry for entry in item if entry])
        elif item:
            count += 1
    return count


def _record_matches_filters(
    *,
    prompt: str,
    response: str,
    error_message: str,
    request_params: dict[str, Any],
    response_summary: dict[str, Any],
    keyword: str,
    size: str,
    ratio: str,
    ref_count: str,
    duration: str,
    resolution: str,
    mode: str,
) -> bool:
    clean_keyword = keyword.strip().lower()
    if clean_keyword:
        haystack = json_dumps_safe(
            {
                "prompt": prompt,
                "response": response,
                "error": error_message,
                "request": request_params,
                "responseSummary": response_summary,
            }
        ).lower()
        if clean_keyword not in haystack:
            return False
    expected = {
        "size": size,
        "ratio": ratio,
        "duration": duration,
        "resolution": resolution,
        "mode": mode,
    }
    key_groups = {
        "size": {"size", "image_size"},
        "ratio": {"ratio", "aspect_ratio", "aspectratio"},
        "duration": {"duration", "seconds", "length"},
        "resolution": {"resolution", "quality"},
        "mode": {"mode", "video_mode", "videomode"},
    }
    for key, expected_value in expected.items():
        if not expected_value:
            continue
        actual = _nested_value(request_params, key_groups[key])
        if _normalized_filter_value(actual) != _normalized_filter_value(expected_value):
            return False
    if ref_count:
        try:
            expected_count = int(ref_count)
        except ValueError:
            expected_count = 0
        actual_count = _count_reference_assets(request_params)
        if expected_count <= 0:
            if actual_count != 0:
                return False
        elif actual_count != expected_count:
            return False
    return True


def _previous_user_message_for_record(db: Session, message: ConversationMessage, capability: str) -> ConversationMessage | None:
    same_conversation = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.conversation_id == message.conversation_id,
            ConversationMessage.role == "user",
            ConversationMessage.created_at <= message.created_at,
        )
        .order_by(ConversationMessage.created_at.desc())
        .first()
    )
    if same_conversation:
        return same_conversation
    return (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.user_id == message.user_id,
            ConversationMessage.role == "user",
            ConversationMessage.capability == capability,
            ConversationMessage.created_at >= message.created_at - timedelta(minutes=30),
            ConversationMessage.created_at <= message.created_at,
        )
        .order_by(ConversationMessage.created_at.desc())
        .first()
    )


def _has_following_assistant_record(db: Session, message: ConversationMessage, capability: str) -> bool:
    same_conversation = (
        db.query(ConversationMessage.id)
        .filter(
            ConversationMessage.conversation_id == message.conversation_id,
            ConversationMessage.role == "assistant",
            ConversationMessage.capability == capability,
            ConversationMessage.created_at >= message.created_at,
        )
        .first()
    )
    if same_conversation:
        return True
    return (
        db.query(ConversationMessage.id)
        .filter(
            ConversationMessage.user_id == message.user_id,
            ConversationMessage.role == "assistant",
            ConversationMessage.capability == capability,
            ConversationMessage.created_at >= message.created_at,
            ConversationMessage.created_at <= message.created_at + timedelta(minutes=30),
        )
        .first()
        is not None
    )


def list_admin_creation_records(
    db: Session,
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
    limit: int = 100,
) -> list[dict[str, Any]]:
    query = (
        db.query(ConversationMessage)
        .options(selectinload(ConversationMessage.assets))
        .filter(ConversationMessage.capability == capability)
    )
    if user_id:
        query = query.filter(ConversationMessage.user_id == user_id)
    clean_user_search = user_search.strip()
    if clean_user_search:
        like = f"%{clean_user_search}%"
        query = query.join(User, User.id == ConversationMessage.user_id).filter(
            or_(
                User.id.like(like),
                User.email.like(like),
                User.nickname.like(like),
                User.phone.like(like),
            )
        )
    if model_group_id:
        query = query.filter(ConversationMessage.model_group_id == model_group_id)
    if status:
        query = query.filter(ConversationMessage.status == status)
    max_limit = min(max(limit, 1), 200)
    messages = query.order_by(ConversationMessage.created_at.desc()).limit(max_limit * 4).all()
    records: list[dict[str, Any]] = []
    for message in messages:
        if message.role != "assistant" and _has_following_assistant_record(db, message, capability):
            continue
        user = db.get(User, message.user_id)
        model = db.get(ModelGroup, message.model_group_id) if message.model_group_id else None
        prompt = message.content if message.role == "user" else ""
        if message.role == "assistant":
            previous_prompt = _previous_user_message_for_record(db, message, capability)
            prompt = previous_prompt.content if previous_prompt else ""
        request_params = _clean_history_value(_load_json(message.request_json, {}))
        response_summary = _clean_history_value(_load_json(message.response_json, {}))
        error_message = _clean_history_value(message.error_message)
        response = _clean_history_value(message.content) if message.role == "assistant" else ""
        prompt = _clean_history_value(prompt)
        call_log = (
            db.query(CallLog)
            .filter(or_(CallLog.message_id == message.id, CallLog.conversation_id == message.conversation_id))
            .order_by(CallLog.created_at.desc())
            .first()
        )
        if call_log:
            request_params = request_params or _clean_history_value(_load_json(call_log.request_params_json, {}))
            response_summary = response_summary or _clean_history_value(_load_json(call_log.response_summary_json, {}))
            if not error_message:
                error_message = _clean_history_value(call_log.error_message)
        if not _record_matches_filters(
            prompt=str(prompt or ""),
            response=str(response or ""),
            error_message=str(error_message or ""),
            request_params=request_params if isinstance(request_params, dict) else {},
            response_summary=response_summary if isinstance(response_summary, dict) else {},
            keyword=keyword,
            size=size,
            ratio=ratio,
            ref_count=ref_count,
            duration=duration,
            resolution=resolution,
            mode=mode,
        ):
            continue
        records.append(
            {
                "id": message.id,
                "user": serialize_admin_user(user) if user else None,
                "modelName": model.public_display_name or model.name if model else "",
                "capability": message.capability,
                "role": message.role,
                "status": message.status,
                "prompt": prompt,
                "response": response,
                "createdAt": message.created_at,
                "durationMs": call_log.duration_ms if call_log else 0,
                "taskId": response_summary.get("taskId", "") if isinstance(response_summary, dict) else "",
                "assets": [
                    {"type": asset.asset_type, "url": asset.url, "thumbnailUrl": asset.thumbnail_url}
                    for asset in message.assets
                ],
                "requestParams": request_params,
                "responseSummary": response_summary,
                "errorMessage": error_message,
            }
        )
        if len(records) >= max_limit:
            break
    return records


def serialize_admin_user(user: User, settings: Settings | None = None) -> dict[str, Any]:
    active_sessions = [item for item in getattr(user, "sessions", []) if item.expires_at > datetime.utcnow()]
    last_seen = max((item.last_seen_at for item in getattr(user, "sessions", [])), default=None)
    return {
        "id": user.id,
        "externalUserId": user.external_user_id,
        "email": user.email,
        "phone": user.phone,
        "nickname": user.nickname,
        "avatarUrl": user.avatar_url,
        "status": user.status,
        "isAdmin": is_admin_user(user, settings),
        "createdAt": user.created_at,
        "updatedAt": user.updated_at,
        "sessionCount": len(active_sessions),
        "lastSeenAt": last_seen,
        "recentLoginIp": "未记录",
    }


def serialize_prompt_template(item: PromptTemplate) -> dict[str, Any]:
    return {
        "id": item.id,
        "capability": item.capability,
        "modelGroupId": item.model_group_id,
        "templateType": item.template_type,
        "name": item.name,
        "content": item.content,
        "enabled": item.enabled,
        "updatedBy": item.updated_by,
        "createdAt": item.created_at,
        "updatedAt": item.updated_at,
    }


HIGH_RISK_ADMIN_ACTIONS = {
    "delete_user",
    "disable_user",
    "restore_user",
    "unpublish_model",
    "publish_model",
    "update_model",
    "save_prompt_template",
}


def _audit_risk_level(item: AdminOperationLog) -> str:
    if item.status == "error":
        return "high"
    if item.action in HIGH_RISK_ADMIN_ACTIONS:
        return "high" if item.action in {"delete_user", "disable_user", "unpublish_model"} else "medium"
    return "normal"


def list_admin_audit_logs(
    db: Session,
    *,
    action: str = "",
    admin_user_id: str = "",
    target_type: str = "",
    target_id: str = "",
    risk: str = "",
    limit: int = 100,
) -> list[dict[str, Any]]:
    query = db.query(AdminOperationLog)
    if action:
        query = query.filter(AdminOperationLog.action.ilike(f"%{action}%"))
    if admin_user_id:
        query = query.filter(AdminOperationLog.admin_user_id == admin_user_id)
    if target_type:
        query = query.filter(AdminOperationLog.target_type == target_type)
    if target_id:
        query = query.filter(AdminOperationLog.target_id.ilike(f"%{target_id}%"))
    logs = query.order_by(AdminOperationLog.created_at.desc()).limit(min(max(limit, 1), 300)).all()
    clean_risk = risk.strip().lower()
    if clean_risk:
        logs = [item for item in logs if _audit_risk_level(item) == clean_risk]
    return [
        {
            "id": item.id,
            "adminUserId": item.admin_user_id,
            "action": item.action,
            "targetType": item.target_type,
            "targetId": item.target_id,
            "status": item.status,
            "riskLevel": _audit_risk_level(item),
            "summary": _load_json(item.summary_json, {}),
            "createdAt": item.created_at,
        }
        for item in logs
    ]
