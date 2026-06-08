from __future__ import annotations

import json
import re
from datetime import timedelta
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


def admin_overview(db: Session) -> dict[str, Any]:
    logs = db.query(CallLog).all()
    total = len(logs)
    failed = len([item for item in logs if item.status != "success"])
    success = total - failed
    average_duration_ms = int(sum(item.duration_ms for item in logs) / total) if total else 0
    public_calls = len([item for item in logs if item.is_public_model])
    return {
        "totalCalls": total,
        "successCalls": success,
        "failedCalls": failed,
        "failureRate": failed / total if total else 0,
        "averageDurationMs": average_duration_ms,
        "publicModelCalls": public_calls,
        "privateModelCalls": total - public_calls,
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
    messages = query.order_by(ConversationMessage.created_at.desc()).limit(max_limit).all()
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
        records.append(
            {
                "id": message.id,
                "user": serialize_admin_user(user) if user else None,
                "modelName": model.public_display_name or model.name if model else "",
                "capability": message.capability,
                "role": message.role,
                "status": message.status,
                "prompt": _clean_history_value(prompt),
                "response": _clean_history_value(message.content) if message.role == "assistant" else "",
                "createdAt": message.created_at,
                "durationMs": 0,
                "taskId": _load_json(message.response_json, {}).get("taskId", ""),
                "assets": [
                    {"type": asset.asset_type, "url": asset.url, "thumbnailUrl": asset.thumbnail_url}
                    for asset in message.assets
                ],
                "requestParams": _clean_history_value(_load_json(message.request_json, {})),
                "responseSummary": _clean_history_value(_load_json(message.response_json, {})),
                "errorMessage": _clean_history_value(message.error_message),
            }
        )
        if len(records) >= max_limit:
            break
    return records


def serialize_admin_user(user: User, settings: Settings | None = None) -> dict[str, Any]:
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


def list_admin_audit_logs(db: Session, *, action: str = "", admin_user_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
    query = db.query(AdminOperationLog)
    if action:
        query = query.filter(AdminOperationLog.action == action)
    if admin_user_id:
        query = query.filter(AdminOperationLog.admin_user_id == admin_user_id)
    logs = query.order_by(AdminOperationLog.created_at.desc()).limit(min(max(limit, 1), 200)).all()
    return [
        {
            "id": item.id,
            "adminUserId": item.admin_user_id,
            "action": item.action,
            "targetType": item.target_type,
            "targetId": item.target_id,
            "status": item.status,
            "summary": _load_json(item.summary_json, {}),
            "createdAt": item.created_at,
        }
        for item in logs
    ]
