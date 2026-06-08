from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db_models import AdminOperationLog, ModelGroup, User
from app.model_service import catalog_loader_options
from app.schemas import AdminModelUpdate


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
