from __future__ import annotations

import json
import csv
import io
import re
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.auth import is_admin_user
from app.config import Settings, get_settings
from app.credit_service import get_or_create_credit_account, serialize_credit_account
from app.db_models import (
    AdminOperationLog,
    AdminRoleAssignment,
    CallLog,
    Conversation,
    ConversationMessage,
    CreditTransaction,
    GeneratedAsset,
    ModelGroup,
    ModelHealthCheck,
    PromptTemplate,
    PromptTemplateVersion,
    SessionRecord,
    TaskEvent,
    User,
    utcnow,
)
from app.model_service import catalog_loader_options
from app.schemas import AdminModelUpdate, AdminUserUpdate, PromptTemplateUpdate


def json_dumps_safe(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def bounded_json_dumps_safe(value: Any, max_bytes: int = 3800) -> str:
    text = json_dumps_safe(value)
    if len(text.encode("utf-8")) <= max_bytes:
        return text

    envelope = {
        "truncated": True,
        "maxBytes": max_bytes,
        "originalBytes": len(text.encode("utf-8")),
        "preview": "",
    }
    preview_budget = max(max_bytes - len(json_dumps_safe(envelope).encode("utf-8")) - 64, 128)
    preview = text.encode("utf-8")[:preview_budget].decode("utf-8", errors="ignore")
    envelope["preview"] = preview
    bounded = json_dumps_safe(envelope)
    while len(bounded.encode("utf-8")) > max_bytes and envelope["preview"]:
        envelope["preview"] = envelope["preview"][:-128]
        bounded = json_dumps_safe(envelope)
    return bounded


def parse_json_object(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except Exception:
        return fallback


def hidden_raw_json_payload() -> dict[str, Any]:
    return {"hidden": True, "reason": "record:raw_json required"}


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


def set_admin_user_role(
    db: Session,
    admin: User,
    user_id: str,
    role: str,
    *,
    note: str = "",
) -> AdminRoleAssignment:
    user = get_admin_user(db, user_id)
    normalized_role = role.strip()
    if normalized_role not in {"admin", "operator", "viewer"}:
        raise HTTPException(status_code=400, detail={"message": "后台角色无效。"})
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail={"message": "不能修改自己的后台角色。"})
    assignment = db.query(AdminRoleAssignment).filter(AdminRoleAssignment.user_id == user.id).first()
    if not assignment:
        assignment = AdminRoleAssignment(user_id=user.id)
        db.add(assignment)
    assignment.role = normalized_role
    assignment.assigned_by = admin.id
    assignment.note = note.strip()[:512]
    db.commit()
    db.refresh(assignment)
    write_admin_log(
        db,
        admin,
        action="update_admin_role",
        target_type="user",
        target_id=user.id,
        summary={"role": normalized_role, "note": assignment.note},
    )
    return assignment


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


def record_model_health_check(
    db: Session,
    *,
    admin: User,
    model: ModelGroup,
    status: str,
    duration_ms: int,
    message: str = "",
    raw: dict[str, Any] | None = None,
    sub_model_id: str = "",
) -> ModelHealthCheck:
    clean_status = status.strip() or "unknown"
    clean_message = message.strip()[:512]
    item = ModelHealthCheck(
        model_group_id=model.id,
        sub_model_id=sub_model_id.strip(),
        admin_user_id=admin.id,
        status=clean_status,
        duration_ms=max(int(duration_ms or 0), 0),
        message=clean_message,
        raw_json=bounded_json_dumps_safe(raw or {}),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    write_admin_log(
        db,
        admin,
        action="model_health_check",
        target_type="model",
        target_id=model.id,
        status="success" if clean_status == "success" else "error",
        summary={"status": clean_status, "durationMs": item.duration_ms, "message": clean_message},
    )
    return item


def serialize_model_health_check(item: ModelHealthCheck, *, include_raw_json: bool = True) -> dict[str, Any]:
    return {
        "id": item.id,
        "modelGroupId": item.model_group_id,
        "subModelId": item.sub_model_id,
        "adminUserId": item.admin_user_id,
        "status": item.status,
        "durationMs": item.duration_ms,
        "message": item.message,
        "raw": parse_json_object(item.raw_json, {}) if include_raw_json else hidden_raw_json_payload(),
        "createdAt": item.created_at,
    }


def get_model_health(db: Session, model_id: str, *, include_raw_json: bool = True) -> dict[str, Any]:
    rows = (
        db.query(ModelHealthCheck)
        .filter(ModelHealthCheck.model_group_id == model_id)
        .order_by(ModelHealthCheck.created_at.desc(), ModelHealthCheck.id.desc())
        .limit(20)
        .all()
    )
    recent = [serialize_model_health_check(item, include_raw_json=include_raw_json) for item in rows]
    failures = len([item for item in rows if item.status != "success"])
    return {
        "modelGroupId": model_id,
        "latest": recent[0] if recent else None,
        "recent": recent,
        "failureRate": failures / len(rows) if rows else 0,
    }


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
    db.flush()
    next_version = (
        db.query(func.max(PromptTemplateVersion.version))
        .filter(PromptTemplateVersion.template_id == item.id)
        .scalar()
        or 0
    ) + 1
    db.add(
        PromptTemplateVersion(
            template_id=item.id,
            version=next_version,
            name=item.name,
            content=item.content,
            enabled=item.enabled,
            updated_by=admin.id,
        )
    )
    db.commit()
    db.refresh(item)
    write_admin_log(db, admin, action="save_prompt_template", target_type="prompt_template", target_id=item.id)
    return item


def list_prompt_template_versions(db: Session, template_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    rows = (
        db.query(PromptTemplateVersion)
        .filter(PromptTemplateVersion.template_id == template_id.strip())
        .order_by(PromptTemplateVersion.version.desc(), PromptTemplateVersion.created_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return [serialize_prompt_template_version(item) for item in rows]


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


def render_prompt_template_samples(
    template: str,
    *,
    capability: str,
    prompts: list[str],
) -> list[dict[str, str]]:
    results = []
    for prompt in prompts:
        clean_prompt = str(prompt or "").strip()
        if not clean_prompt:
            continue
        results.append(
            {
                "prompt": clean_prompt,
                "rendered": render_prompt_template(
                    template,
                    {"prompt": clean_prompt, "capability": capability or "text"},
                ),
            }
        )
    return results


def prompt_template_model_status_overview(db: Session, *, capability: str = "all") -> list[dict[str, Any]]:
    clean_capability = capability.strip().lower()
    query = db.query(ModelGroup)
    if clean_capability in {"text", "image", "video"}:
        query = query.filter(ModelGroup.capability == clean_capability)
    models = query.order_by(ModelGroup.capability.asc(), ModelGroup.name.asc()).limit(500).all()
    template_rows = db.query(PromptTemplate).all()
    templates_by_scope = {
        (item.capability, item.model_group_id, item.template_type): item
        for item in template_rows
        if item.template_type == "prompt_optimize"
    }
    rows: list[dict[str, Any]] = []
    for model in models:
        default_template = templates_by_scope.get((model.capability, "", "prompt_optimize"))
        model_template = templates_by_scope.get((model.capability, model.id, "prompt_optimize"))
        rows.append(
            {
                "modelGroupId": model.id,
                "modelName": model.public_display_name or model.name,
                "capability": model.capability,
                "promptOptimizeEnabled": bool(model.prompt_optimize_enabled),
                "usesDefault": bool(default_template and default_template.enabled),
                "defaultTemplateId": default_template.id if default_template else "",
                "defaultTemplateEnabled": bool(default_template.enabled) if default_template else False,
                "hasModelTemplate": model_template is not None,
                "modelTemplateId": model_template.id if model_template else "",
                "modelTemplateEnabled": bool(model_template.enabled) if model_template else False,
            }
        )
    return rows


def _config_admin_filter(settings: Settings | None):
    if not settings:
        return None
    filters = []
    config_admin_emails = {item.strip().lower() for item in settings.admin_emails if item.strip()}
    config_admin_identifiers = {item.strip().lower() for item in settings.admin_identifiers if item.strip()}
    if config_admin_emails:
        filters.append(func.lower(func.trim(User.email)).in_(config_admin_emails))
    if config_admin_identifiers:
        filters.extend(
            [
                func.lower(func.trim(User.external_user_id)).in_(config_admin_identifiers),
                func.lower(func.trim(User.phone)).in_(config_admin_identifiers),
                func.lower(func.trim(User.nickname)).in_(config_admin_identifiers),
            ]
        )
    return or_(*filters) if filters else None


def list_admin_users(
    db: Session,
    *,
    search: str = "",
    role: str = "",
    status: str = "",
    settings: Settings | None = None,
) -> list[User]:
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
    clean_status = status.strip().lower()
    if clean_status and clean_status != "all":
        query = query.filter(User.status == clean_status)
    clean_role = role.strip().lower()
    if clean_role and clean_role != "all":
        if clean_role == "user":
            admin_ids = [item[0] for item in db.query(AdminRoleAssignment.user_id).all()]
            config_filter = _config_admin_filter(settings)
            if config_filter is not None:
                config_admins = db.query(User.id).filter(config_filter)
                admin_ids.extend(item[0] for item in config_admins.all())
            if admin_ids:
                query = query.filter(~User.id.in_(set(admin_ids)))
        elif clean_role == "admin" and settings:
            role_filters = [AdminRoleAssignment.role == clean_role]
            config_filter = _config_admin_filter(settings)
            if config_filter is not None:
                role_filters.append(config_filter)
            query = query.outerjoin(AdminRoleAssignment).filter(or_(*role_filters))
        else:
            query = query.join(AdminRoleAssignment).filter(AdminRoleAssignment.role == clean_role)
    return query.order_by(User.created_at.desc()).limit(200).all()


def _admin_user_identity(user: User) -> str:
    email = (user.email or "").strip().lower()
    if email:
        return f"email:{email}"
    phone = (user.phone or "").strip()
    if phone:
        return f"phone:{phone}"
    return ""


def admin_duplicate_identity_map(db: Session) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[User]] = {}
    for user in db.query(User).order_by(User.created_at.asc(), User.id.asc()).all():
        identity = _admin_user_identity(user)
        if not identity:
            continue
        grouped.setdefault(identity, []).append(user)
    duplicate_map: dict[str, dict[str, Any]] = {}
    for identity, users in grouped.items():
        if len(users) <= 1:
            continue
        target = users[0]
        user_ids = [item.id for item in users]
        payload = {
            "identity": identity,
            "duplicateCount": len(users),
            "targetUserId": target.id,
            "userIds": user_ids,
        }
        for item in users:
            duplicate_map[item.id] = payload
    return duplicate_map


def build_admin_users_csv(users: list[User], settings: Settings | None = None) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "用户ID",
            "外部用户ID",
            "邮箱",
            "昵称",
            "手机号",
            "后台角色",
            "角色来源",
            "状态",
            "可用积分",
            "冻结积分",
            "累计充值",
            "累计消耗",
            "累计退回",
            "会话数",
            "最近登录IP",
            "最近活跃",
            "创建时间",
        ]
    )
    for user in users:
        row = serialize_admin_user(user, settings)
        credits = row.get("credits") or {}
        writer.writerow(
            [
                row.get("id", ""),
                row.get("externalUserId", ""),
                row.get("email", ""),
                row.get("nickname", ""),
                row.get("phone", ""),
                row.get("adminRole", "") or ("admin" if row.get("isAdmin") else "user"),
                row.get("adminRoleSource", ""),
                row.get("status", ""),
                credits.get("balance", 0),
                credits.get("reservedBalance", 0),
                credits.get("totalRecharged", 0),
                credits.get("totalSpent", 0),
                credits.get("totalRefunded", 0),
                row.get("sessionCount", 0),
                row.get("recentLoginIp", ""),
                row.get("lastSeenAt", ""),
                row.get("createdAt", ""),
            ]
        )
    return output.getvalue().strip("\r\n")


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
    now = utcnow()
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
        timeout = len([item for item in bucket if _is_timeout_log(item)])
        duration_total = sum(item.duration_ms for item in bucket)
        rows.append(
            {
                "label": label,
                "totalCalls": total,
                "successCalls": total - failed,
                "failedCalls": failed,
                "timeoutCalls": timeout,
                "quotaUnits": round(sum(_usage_units(item) for item in bucket), 2),
                "averageDurationMs": int(duration_total / total) if total else 0,
            }
        )
    return rows


def _metrics_range_start(range_key: str) -> datetime:
    days = {"7d": 7, "30d": 30, "90d": 90}.get((range_key or "").strip().lower(), 30)
    return utcnow() - timedelta(days=days)


def _metrics_trend_counts(range_key: str) -> dict[str, int]:
    days = {"7d": 7, "30d": 30, "90d": 90}.get((range_key or "").strip().lower(), 30)
    return {
        "day": days,
        "week": max(1, (days + 6) // 7),
        "month": max(1, (days + 29) // 30),
    }


def _model_label(model: ModelGroup | None, fallback: str = "") -> str:
    if not model:
        return fallback
    return model.public_display_name or model.name or fallback


def _user_label(user: User | None, fallback: str = "") -> str:
    if not user:
        return fallback
    return user.email or user.nickname or user.id or fallback


def _failure_rate(failed: int, total: int) -> float:
    return failed / total if total else 0


def admin_dashboard_metrics(db: Session, *, range_key: str = "30d") -> dict[str, Any]:
    start_at = _metrics_range_start(range_key)
    trend_counts = _metrics_trend_counts(range_key)
    logs = db.query(CallLog).filter(CallLog.created_at >= start_at).all()
    transactions = db.query(CreditTransaction).filter(CreditTransaction.created_at >= start_at).all()

    total = len(logs)
    failed = len([item for item in logs if item.status != "success"])
    success = total - failed
    timeout_calls = len([item for item in logs if _is_timeout_log(item)])
    public_calls = len([item for item in logs if item.is_public_model])
    duration_total = sum(item.duration_ms for item in logs)
    queue_values = [_queue_time_ms(item) for item in logs]
    queue_samples = [item for item in queue_values if item > 0]

    capability_rows: list[dict[str, Any]] = []
    by_capability: dict[str, list[CallLog]] = {}
    for item in logs:
        key = item.capability or "unknown"
        by_capability.setdefault(key, []).append(item)
    for capability, rows in by_capability.items():
        row_total = len(rows)
        row_failed = len([item for item in rows if item.status != "success"])
        capability_rows.append(
            {
                "capability": capability,
                "key": capability,
                "label": capability,
                "totalCalls": row_total,
                "successCalls": row_total - row_failed,
                "failedCalls": row_failed,
                "failureRate": _failure_rate(row_failed, row_total),
            }
        )
    capability_rows.sort(key=lambda item: (item["totalCalls"], item["capability"]), reverse=True)

    ownership_rows = []
    for ownership, owned_logs in (
        ("public", [item for item in logs if item.is_public_model]),
        ("private", [item for item in logs if not item.is_public_model]),
    ):
        row_total = len(owned_logs)
        row_failed = len([item for item in owned_logs if item.status != "success"])
        ownership_rows.append(
            {
                "ownership": ownership,
                "key": ownership,
                "label": "Public" if ownership == "public" else "Private",
                "totalCalls": row_total,
                "successCalls": row_total - row_failed,
                "failedCalls": row_failed,
                "failureRate": _failure_rate(row_failed, row_total),
            }
        )

    credit_summary = {
        "reserved": 0,
        "spent": 0,
        "refunded": 0,
        "adminAdjusted": 0,
    }
    transactions_by_id = {item.id: item for item in transactions}
    for item in transactions:
        if item.type == "generation_reserve":
            if item.status not in {"captured", "refunded"}:
                credit_summary["reserved"] += abs(item.amount) if item.amount < 0 else item.reserved_after
        elif item.type in {"generation_capture", "generation_spend"}:
            amount = abs(item.amount)
            if item.type == "generation_capture" and amount == 0 and item.related_transaction_id:
                reserve = transactions_by_id.get(item.related_transaction_id) or db.get(
                    CreditTransaction,
                    item.related_transaction_id,
                )
                if reserve and reserve.type == "generation_reserve":
                    amount = abs(reserve.amount)
            credit_summary["spent"] += amount
        elif item.type in {"generation_refund", "refund"}:
            credit_summary["refunded"] += abs(item.amount)
        elif item.type == "admin_adjustment":
            credit_summary["adminAdjusted"] += item.amount

    by_model: dict[str, list[CallLog]] = {}
    for item in logs:
        if item.model_group_id:
            by_model.setdefault(item.model_group_id, []).append(item)

    failed_models: list[dict[str, Any]] = []
    slow_models: list[dict[str, Any]] = []
    for model_id, model_logs in by_model.items():
        model = db.get(ModelGroup, model_id)
        model_failed = [item for item in model_logs if item.status != "success"]
        if model_failed:
            failed_models.append(
                {
                    "modelGroupId": model_id,
                    "modelName": _model_label(model, model_id),
                    "capability": model.capability if model else (model_logs[0].capability if model_logs else ""),
                    "failedCalls": len(model_failed),
                    "totalCalls": len(model_logs),
                    "failureRate": _failure_rate(len(model_failed), len(model_logs)),
                    "lastError": model_failed[-1].error_message,
                }
            )
        slow_models.append(
            {
                "modelGroupId": model_id,
                "modelName": _model_label(model, model_id),
                "capability": model.capability if model else (model_logs[0].capability if model_logs else ""),
                "totalCalls": len(model_logs),
                "averageDurationMs": int(sum(item.duration_ms for item in model_logs) / len(model_logs)) if model_logs else 0,
            }
        )
    failed_models.sort(key=lambda item: (item["failedCalls"], item["failureRate"]), reverse=True)
    slow_models.sort(key=lambda item: item["averageDurationMs"], reverse=True)

    by_user: dict[str, list[CallLog]] = {}
    for item in logs:
        if item.user_id:
            by_user.setdefault(item.user_id, []).append(item)
    active_users: list[dict[str, Any]] = []
    for user_id, user_logs in by_user.items():
        user = db.get(User, user_id)
        public_user_calls = len([item for item in user_logs if item.is_public_model])
        active_users.append(
            {
                "userId": user_id,
                "label": _user_label(user, user_id),
                "totalCalls": len(user_logs),
                "publicModelCalls": public_user_calls,
                "privateModelCalls": len(user_logs) - public_user_calls,
            }
        )
    active_users.sort(key=lambda item: item["totalCalls"], reverse=True)

    return {
        "totals": {
            "totalCalls": total,
            "successCalls": success,
            "failedCalls": failed,
            "timeoutCalls": timeout_calls,
            "failureRate": _failure_rate(failed, total),
            "timeoutRate": _failure_rate(timeout_calls, total),
            "averageDurationMs": int(duration_total / total) if total else 0,
            "averageQueueMs": int(sum(queue_samples) / len(queue_samples)) if queue_samples else 0,
            "quotaUnits": round(sum(_usage_units(item) for item in logs), 2),
            "publicModelCalls": public_calls,
            "privateModelCalls": total - public_calls,
        },
        "trends": {
            "day": _trend_buckets(logs, period="day", count=trend_counts["day"]),
            "week": _trend_buckets(logs, period="week", count=trend_counts["week"]),
            "month": _trend_buckets(logs, period="month", count=trend_counts["month"]),
        },
        "capabilityBreakdown": capability_rows,
        "ownershipBreakdown": ownership_rows,
        "creditSummary": credit_summary,
        "failedModels": failed_models[:10],
        "slowModels": slow_models[:10],
        "activeUsers": active_users[:10],
    }


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
    mojibake_markers = "闁跨噦鎷烽柣銏㈡喆搞儵鏌涚紓鍌炴閻熸洟鎮剁紒鐘参熼柛姘叡规寧呭┑澶嬬暦閼筋槂"
    mojibake_chars = sum(1 for char in text if char in mojibake_markers)
    if len(text) >= 12 and mojibake_chars / len(text) > 0.28:
        return True
    latin_mojibake_markers = "鑴欒剹姘撳繖鑾界尗鑼呴敋鑼傚啋闄囨ゼ濞勬悅绡撴紡闄嬭姦鍗㈠簮鐐夋幊鍗よ檹椴侀簱纰岄湶璺祩楣挎綖绂勫綍闄嗘埉椹磋仚鑱糫"
    latin_mojibake_chars = sum(1 for char in text if char in latin_mojibake_markers)
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


def _task_id_from_payload(*payloads: Any) -> str:
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for key, value in payload.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in TASK_ID_KEYS and str(value).strip():
                return str(value).strip()
    return ""


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
    include_raw_json: bool = True,
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
    if status == "non_success":
        query = query.filter(ConversationMessage.status != "success")
    elif status:
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
        visible_request_params = request_params if include_raw_json else hidden_raw_json_payload()
        visible_response_summary = response_summary if include_raw_json else hidden_raw_json_payload()
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
                "taskId": _task_id_from_payload(response_summary, request_params),
                "assets": [
                    {"type": asset.asset_type, "url": asset.url, "thumbnailUrl": asset.thumbnail_url}
                    for asset in message.assets
                ],
                "requestParams": visible_request_params,
                "responseSummary": visible_response_summary,
                "errorMessage": error_message,
            }
        )
        if len(records) >= max_limit:
            break
    return records


def build_admin_creation_records_csv(records: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "消息ID",
            "用户",
            "类型",
            "模型",
            "状态",
            "提示词",
            "响应",
            "错误信息",
            "资源数",
            "任务ID",
            "耗时ms",
            "创建时间",
        ]
    )
    for record in records:
        user = record.get("user") if isinstance(record.get("user"), dict) else {}
        writer.writerow(
            [
                record.get("id", ""),
                user.get("email") or user.get("nickname") or user.get("id") or "",
                record.get("capability", ""),
                record.get("modelName", ""),
                record.get("status", ""),
                record.get("prompt", ""),
                record.get("response", ""),
                record.get("errorMessage", ""),
                len(record.get("assets") or []),
                record.get("taskId", ""),
                record.get("durationMs", 0),
                record.get("createdAt", ""),
            ]
        )
    return output.getvalue()


TASK_ID_KEYS = {"taskid", "task_id", "localtaskid", "providertaskid"}


def _json_mentions_task_id(value: Any, task_id: str) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in TASK_ID_KEYS and str(item).strip() == task_id:
                return True
            if isinstance(item, (dict, list)) and _json_mentions_task_id(item, task_id):
                return True
    if isinstance(value, list):
        return any(_json_mentions_task_id(item, task_id) for item in value)
    return False


def _call_log_mentions_task(item: CallLog, task_id: str) -> bool:
    clean_task_id = task_id.strip()
    if not clean_task_id:
        return False
    request_params = parse_json_object(item.request_params_json, {})
    response_summary = parse_json_object(item.response_summary_json, {})
    return _json_mentions_task_id(request_params, clean_task_id) or _json_mentions_task_id(response_summary, clean_task_id)


def _timeline_row(item: CallLog, *, include_raw_json: bool = True) -> dict[str, Any]:
    response_summary = parse_json_object(item.response_summary_json, {})
    if not isinstance(response_summary, dict):
        response_summary = {}
    row = {
        "id": item.id,
        "source": "call_log",
        "eventType": "call",
        "endpoint": item.endpoint,
        "status": item.status,
        "durationMs": item.duration_ms,
        "errorMessage": _clean_history_value(item.error_message),
        "createdAt": item.created_at,
    }
    if include_raw_json:
        row["responseSummary"] = _clean_history_value(response_summary)
    return row


def record_task_event(
    db: Session,
    *,
    task_id: str,
    event_type: str,
    status: str = "",
    user_id: str | None = None,
    model_group_id: str | None = None,
    sub_model_id: str | None = None,
    capability: str = "",
    endpoint: str = "",
    conversation_id: str = "",
    message_id: str = "",
    duration_ms: int = 0,
    message: str = "",
    payload: dict[str, Any] | None = None,
) -> TaskEvent:
    clean_task_id = task_id.strip()
    if not clean_task_id:
        raise HTTPException(status_code=400, detail={"message": "缺少任务 ID。"})
    item = TaskEvent(
        task_id=clean_task_id,
        event_type=event_type.strip() or "event",
        status=status.strip(),
        user_id=user_id or None,
        model_group_id=model_group_id or None,
        sub_model_id=sub_model_id or None,
        capability=capability.strip(),
        endpoint=endpoint.strip(),
        conversation_id=conversation_id.strip(),
        message_id=message_id.strip(),
        duration_ms=max(int(duration_ms or 0), 0),
        message=message.strip()[:512],
        payload_json=json_dumps_safe(payload or {}),
    )
    db.add(item)
    db.flush()
    return item


def _task_event_row(item: TaskEvent, *, include_raw_json: bool = True) -> dict[str, Any]:
    row = {
        "id": item.id,
        "source": "task_event",
        "eventType": item.event_type,
        "endpoint": item.endpoint,
        "status": item.status,
        "durationMs": item.duration_ms,
        "errorMessage": "",
        "message": _clean_history_value(item.message),
        "createdAt": item.created_at,
    }
    if include_raw_json:
        row["payload"] = _clean_history_value(parse_json_object(item.payload_json, {}))
    return row


TASK_EVENT_SORT_ORDER = {
    "submitted": 10,
    "queued": 20,
    "started": 30,
    "query": 40,
    "updated": 50,
    "completed": 90,
    "failed": 90,
}


def _timeline_sort_key(item: dict[str, Any]) -> tuple[Any, int, str]:
    order = TASK_EVENT_SORT_ORDER.get(str(item.get("eventType") or ""), 60)
    return item.get("createdAt"), order, str(item.get("id") or "")


def admin_record_detail(db: Session, message_id: str, *, include_raw_json: bool = True) -> dict[str, Any]:
    message = (
        db.query(ConversationMessage)
        .options(selectinload(ConversationMessage.assets))
        .filter(ConversationMessage.id == message_id)
        .first()
    )
    if not message:
        raise HTTPException(status_code=404, detail={"message": "消息不存在。"})
    conversation = db.get(Conversation, message.conversation_id)
    user = db.get(User, message.user_id)
    request_params = _clean_history_value(_load_json(message.request_json, {}))
    response_summary = _clean_history_value(_load_json(message.response_json, {}))
    timeline = (
        db.query(CallLog)
        .filter(or_(CallLog.message_id == message.id, CallLog.conversation_id == message.conversation_id))
        .order_by(CallLog.created_at.asc())
        .all()
    )
    task_events = (
        db.query(TaskEvent)
        .filter(or_(TaskEvent.message_id == message.id, TaskEvent.conversation_id == message.conversation_id))
        .order_by(TaskEvent.created_at.asc())
        .all()
    )
    if timeline:
        latest = timeline[-1]
        request_params = request_params or _clean_history_value(_load_json(latest.request_params_json, {}))
        response_summary = response_summary or _clean_history_value(_load_json(latest.response_summary_json, {}))
    visible_request_params = request_params if include_raw_json else hidden_raw_json_payload()
    visible_response_summary = response_summary if include_raw_json else hidden_raw_json_payload()
    return {
        "id": message.id,
        "conversationId": message.conversation_id,
        "conversationTitle": conversation.title if conversation else "",
        "user": serialize_admin_user(user) if user else None,
        "role": message.role,
        "capability": message.capability,
        "status": message.status,
        "content": _clean_history_value(message.content),
        "request": visible_request_params,
        "response": visible_response_summary,
        "errorMessage": _clean_history_value(message.error_message),
        "assets": [
            {"type": asset.asset_type, "url": asset.url, "thumbnailUrl": asset.thumbnail_url}
            for asset in message.assets
        ],
        "timeline": sorted(
            [_timeline_row(item, include_raw_json=include_raw_json) for item in timeline]
            + [_task_event_row(item, include_raw_json=include_raw_json) for item in task_events],
            key=_timeline_sort_key,
        ),
        "createdAt": message.created_at,
    }


def admin_task_timeline(db: Session, task_id: str, *, include_raw_json: bool = True) -> dict[str, Any]:
    clean_task_id = task_id.strip()
    if not clean_task_id:
        raise HTTPException(status_code=400, detail={"message": "缺少任务 ID。"})
    task_events = (
        db.query(TaskEvent)
        .filter(TaskEvent.task_id == clean_task_id)
        .order_by(TaskEvent.created_at.asc(), TaskEvent.id.asc())
        .all()
    )
    logs = db.query(CallLog).order_by(CallLog.created_at.asc()).all()
    return {
        "taskId": clean_task_id,
        "events": sorted(
            [_task_event_row(item, include_raw_json=include_raw_json) for item in task_events]
            + [
                _timeline_row(item, include_raw_json=include_raw_json)
                for item in logs
                if _call_log_mentions_task(item, clean_task_id)
            ],
            key=_timeline_sort_key,
        ),
    }


def serialize_admin_user(
    user: User,
    settings: Settings | None = None,
    duplicate_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active_sessions = [item for item in getattr(user, "sessions", []) if item.expires_at > utcnow()]
    last_seen = max((item.last_seen_at for item in getattr(user, "sessions", [])), default=None)
    recent_session = max(
        getattr(user, "sessions", []),
        key=lambda item: item.last_seen_at or item.created_at or datetime.min,
        default=None,
    )
    recent_login_ip = getattr(recent_session, "client_ip", "") if recent_session else ""
    account = None
    try:
        session = getattr(user, "_sa_instance_state").session
        if session:
            account = get_or_create_credit_account(session, user.id)
    except Exception:
        account = None
    return {
        "id": user.id,
        "externalUserId": user.external_user_id,
        "email": user.email,
        "phone": user.phone,
        "nickname": user.nickname,
        "avatarUrl": user.avatar_url,
        "status": user.status,
        "adminRole": getattr(getattr(user, "admin_role_assignment", None), "role", ""),
        "adminRoleSource": "database" if getattr(user, "admin_role_assignment", None) else "config" if is_admin_user(user, settings) else "",
        "isAdmin": is_admin_user(user, settings),
        "createdAt": user.created_at,
        "updatedAt": user.updated_at,
        "sessionCount": len(active_sessions),
        "lastSeenAt": last_seen,
        "recentLoginIp": recent_login_ip,
        "credits": serialize_credit_account(account),
        "duplicateIdentity": duplicate_identity,
    }


def serialize_admin_user_with_duplicate_identity(
    db: Session,
    user: User,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return serialize_admin_user(
        user,
        settings,
        duplicate_identity=admin_duplicate_identity_map(db).get(user.id),
    )


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


def serialize_prompt_template_version(item: PromptTemplateVersion) -> dict[str, Any]:
    return {
        "id": item.id,
        "templateId": item.template_id,
        "version": item.version,
        "name": item.name,
        "content": item.content,
        "enabled": item.enabled,
        "updatedBy": item.updated_by,
        "createdAt": item.created_at,
    }


HIGH_RISK_ADMIN_ACTIONS = {
    "delete_user",
    "disable_user",
    "update_admin_role",
    "merge_duplicate_users",
    "unpublish_model",
    "delete_model",
}

MEDIUM_RISK_ADMIN_ACTIONS = {
    "restore_user",
    "publish_model",
    "update_model",
    "save_prompt_template",
    "adjust_credits",
    "update_credit_settings",
}


def _audit_risk_level(item: AdminOperationLog) -> str:
    if item.status == "error":
        return "high"
    if item.action in HIGH_RISK_ADMIN_ACTIONS:
        return "high"
    if item.action in MEDIUM_RISK_ADMIN_ACTIONS:
        return "medium"
    return "normal"


def _parse_audit_datetime(value: str) -> datetime | None:
    clean = value.strip()
    if not clean:
        return None
    if clean.endswith("Z"):
        clean = f"{clean[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(clean)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def list_admin_audit_logs(
    db: Session,
    *,
    action: str = "",
    admin_user_id: str = "",
    target_type: str = "",
    target_id: str = "",
    status: str = "",
    risk: str = "",
    start_at: str = "",
    end_at: str = "",
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
    if status:
        query = query.filter(AdminOperationLog.status == status)
    parsed_start = _parse_audit_datetime(start_at)
    if parsed_start:
        query = query.filter(AdminOperationLog.created_at >= parsed_start)
    parsed_end = _parse_audit_datetime(end_at)
    if parsed_end:
        query = query.filter(AdminOperationLog.created_at <= parsed_end)
    max_limit = min(max(limit, 1), 300)
    clean_risk = risk.strip().lower()
    ordered_query = query.order_by(AdminOperationLog.created_at.desc())
    logs = ordered_query.all() if clean_risk else ordered_query.limit(max_limit).all()
    if clean_risk:
        logs = [item for item in logs if _audit_risk_level(item) == clean_risk]
    logs = logs[:max_limit]
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


def build_admin_audit_logs_csv(rows: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["日志ID", "管理员", "操作", "目标类型", "目标ID", "风险等级", "状态", "摘要", "创建时间"])
    for item in rows:
        writer.writerow(
            [
                item.get("id") or "",
                item.get("adminUserId") or "",
                item.get("action") or "",
                item.get("targetType") or "",
                item.get("targetId") or "",
                item.get("riskLevel") or "normal",
                item.get("status") or "",
                json_dumps_safe(item.get("summary") or {}),
                item.get("createdAt") or "",
            ]
        )
    return output.getvalue()
