from __future__ import annotations

import json
import time
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.db_models import ApiKey, CallLog, ModelGroup, SubModel, User
from app.proxy_utils import filter_model_ids_for_capability, parse_model_ids
from app.schemas import ApiKeyOut, CallLogOut, ModelCreate, ModelOut, ModelUpdate, SubModelOut, SyncModelsResult
from app.security import decrypt_secret, encrypt_secret


def serialize_api_key(api_key: ApiKey) -> ApiKeyOut:
    return ApiKeyOut(
        id=api_key.id,
        name=api_key.name,
        baseUrl=api_key.base_url,
        status=api_key.status,
        createdAt=api_key.created_at,
    )


def serialize_sub_model(sub_model: SubModel, primary_id: str = "") -> SubModelOut:
    return SubModelOut(
        id=sub_model.id,
        modelName=sub_model.model_name,
        displayName=sub_model.display_name,
        capability=sub_model.capability,
        adapter=sub_model.adapter,
        isPrimary=sub_model.is_primary or sub_model.id == primary_id,
        status=sub_model.status,
    )


def serialize_model(model: ModelGroup) -> ModelOut:
    primary = next((item for item in model.sub_models if item.id == model.primary_sub_model_id), None)
    if not primary:
        primary = next((item for item in model.sub_models if item.is_primary), None)
    return ModelOut(
        id=model.id,
        name=model.name,
        vendor=model.vendor,
        capability=model.capability,
        adapter=model.adapter,
        description=model.description,
        apiKeyId=model.api_key_id,
        baseUrl=model.api_key.base_url,
        primarySubModelId=model.primary_sub_model_id,
        primaryModelName=primary.model_name if primary else "",
        subModels=[serialize_sub_model(item, model.primary_sub_model_id) for item in model.sub_models],
    )


def normalize_model_names(primary_model_name: str, available_model_names: list[str] | None = None) -> list[str]:
    names: list[str] = []
    for model_name in [*(available_model_names or []), primary_model_name]:
        value = model_name.strip()
        if value and value not in names:
            names.append(value)
    return names


def create_model_group(db: Session, user: User, payload: ModelCreate) -> ModelGroup:
    api_key = ApiKey(
        user_id=user.id,
        name=f"{payload.name} 密钥",
        base_url=payload.baseUrl.strip(),
        api_key_ciphertext=encrypt_secret(payload.apiKey.strip()),
    )
    db.add(api_key)
    db.flush()
    model = ModelGroup(
        user_id=user.id,
        api_key_id=api_key.id,
        name=payload.name.strip(),
        vendor=payload.vendor.strip(),
        capability=payload.capability,
        adapter=payload.adapter,
        description=payload.description.strip(),
    )
    db.add(model)
    db.flush()
    primary_model_name = payload.primaryModelName.strip()
    for model_name in normalize_model_names(primary_model_name, payload.availableModelNames):
        sub_model = SubModel(
            model_group_id=model.id,
            api_key_id=api_key.id,
            model_name=model_name,
            display_name=model_name,
            capability=payload.capability,
            adapter=payload.adapter,
            is_primary=model_name == primary_model_name,
        )
        db.add(sub_model)
        db.flush()
        if sub_model.is_primary:
            model.primary_sub_model_id = sub_model.id
    db.commit()
    return get_model_group(db, user, model.id)


def get_model_group(db: Session, user: User, model_id: str) -> ModelGroup:
    return get_model_group_for_user_id(db, user.id, model_id)


def get_model_group_for_user_id(db: Session, user_id: str, model_id: str) -> ModelGroup:
    model = (
        db.query(ModelGroup)
        .options(selectinload(ModelGroup.api_key), selectinload(ModelGroup.sub_models))
        .filter(ModelGroup.id == model_id, ModelGroup.user_id == user_id)
        .one_or_none()
    )
    if not model:
        raise HTTPException(status_code=404, detail={"message": "模型不存在。"})
    return model


def list_model_groups(db: Session, user: User) -> list[ModelGroup]:
    return (
        db.query(ModelGroup)
        .options(selectinload(ModelGroup.api_key), selectinload(ModelGroup.sub_models))
        .filter(ModelGroup.user_id == user.id)
        .order_by(ModelGroup.created_at.desc())
        .all()
    )


def list_api_keys(db: Session, user: User) -> list[ApiKey]:
    return db.query(ApiKey).filter(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc()).all()


def update_model_group(db: Session, user: User, model_id: str, payload: ModelUpdate) -> ModelGroup:
    model = get_model_group(db, user, model_id)
    if payload.name is not None:
        model.name = payload.name.strip()
        model.api_key.name = f"{model.name} 密钥"
    if payload.vendor is not None:
        model.vendor = payload.vendor.strip()
    if payload.capability is not None:
        model.capability = payload.capability
    if payload.adapter is not None:
        model.adapter = payload.adapter
    if payload.description is not None:
        model.description = payload.description.strip()
    if payload.baseUrl is not None:
        model.api_key.base_url = payload.baseUrl.strip()
    if payload.apiKey is not None and payload.apiKey.strip():
        model.api_key.api_key_ciphertext = encrypt_secret(payload.apiKey.strip())

    primary_model_name = (payload.primaryModelName or "").strip()
    model_names = normalize_model_names(primary_model_name, payload.availableModelNames)
    if model_names:
        existing_by_name = {item.model_name: item for item in model.sub_models}
        primary = None
        for model_name in model_names:
            existing = existing_by_name.get(model_name)
            if not existing:
                existing = SubModel(
                    model_group_id=model.id,
                    api_key_id=model.api_key_id,
                    model_name=model_name,
                    display_name=model_name,
                    capability=model.capability,
                    adapter=model.adapter,
                    is_primary=False,
                )
                db.add(existing)
                db.flush()
                model.sub_models.append(existing)
            existing.capability = model.capability
            existing.adapter = model.adapter
            if model_name == primary_model_name:
                primary = existing
        if not primary and model_names:
            primary = existing_by_name.get(model_names[0]) or next(
                (item for item in model.sub_models if item.model_name == model_names[0]),
                None,
            )
        if primary:
            for item in model.sub_models:
                item.capability = model.capability
                item.adapter = model.adapter
                item.is_primary = item.id == primary.id
            model.primary_sub_model_id = primary.id
    elif primary_model_name:
        existing = next((item for item in model.sub_models if item.model_name == primary_model_name), None)
        if not existing:
            existing = SubModel(
                model_group_id=model.id,
                api_key_id=model.api_key_id,
                model_name=primary_model_name,
                display_name=primary_model_name,
                capability=model.capability,
                adapter=model.adapter,
                is_primary=True,
            )
            db.add(existing)
            db.flush()
            model.sub_models.append(existing)
        for item in model.sub_models:
            item.capability = model.capability
            item.adapter = model.adapter
            item.is_primary = item.id == existing.id
        existing.capability = model.capability
        existing.adapter = model.adapter
        model.primary_sub_model_id = existing.id

    db.commit()
    return get_model_group(db, user, model_id)


def delete_model_group(db: Session, user: User, model_id: str) -> None:
    model = get_model_group(db, user, model_id)
    api_key = model.api_key
    db.delete(model)
    if api_key and len(api_key.model_groups) <= 1:
        db.delete(api_key)
    db.commit()


def set_primary_sub_model(db: Session, user: User, model_id: str, sub_model_id: str) -> ModelGroup:
    model = get_model_group(db, user, model_id)
    target = next((item for item in model.sub_models if item.id == sub_model_id), None)
    if not target:
        raise HTTPException(status_code=404, detail={"message": "子模型不存在。"})
    for item in model.sub_models:
        item.is_primary = item.id == target.id
    model.primary_sub_model_id = target.id
    db.commit()
    return get_model_group(db, user, model_id)


def upsert_fetched_sub_models(
    db: Session,
    model: ModelGroup,
    model_names: list[str],
    primary_model_name: str,
) -> None:
    existing = {item.model_name: item for item in model.sub_models}
    for model_name in model_names:
        sub_model = existing.get(model_name)
        if not sub_model:
            sub_model = SubModel(
                model_group_id=model.id,
                api_key_id=model.api_key_id,
                model_name=model_name,
                display_name=model_name,
                capability=model.capability,
                adapter=model.adapter,
            )
            db.add(sub_model)
        sub_model.is_primary = model_name == primary_model_name
    db.flush()
    primary = next((item for item in model.sub_models if item.model_name == primary_model_name), None)
    if primary:
        model.primary_sub_model_id = primary.id


def get_sub_model_for_user(db: Session, user: User, sub_model_id: str) -> tuple[ModelGroup, SubModel, ApiKey, str]:
    sub_model = (
        db.query(SubModel)
        .options(selectinload(SubModel.model_group), selectinload(SubModel.api_key))
        .join(ModelGroup, ModelGroup.id == SubModel.model_group_id)
        .filter(SubModel.id == sub_model_id, ModelGroup.user_id == user.id)
        .one_or_none()
    )
    if not sub_model:
        raise HTTPException(status_code=404, detail={"message": "子模型不存在。"})
    api_key = sub_model.api_key
    return sub_model.model_group, sub_model, api_key, decrypt_secret(api_key.api_key_ciphertext)


def record_call_log(
    db: Session,
    *,
    user: User,
    model_group_id: str,
    sub_model_id: str,
    capability: str,
    endpoint: str,
    status: str,
    duration_ms: int,
    prompt_summary: str = "",
    error_message: str = "",
    usage: Any = None,
) -> None:
    db.add(
        CallLog(
            user_id=user.id,
            model_group_id=model_group_id,
            sub_model_id=sub_model_id,
            capability=capability,
            endpoint=endpoint,
            status=status,
            duration_ms=duration_ms,
            prompt_summary=prompt_summary[:512],
            error_message=error_message[:512],
            raw_usage_json=json.dumps(usage, ensure_ascii=False) if usage is not None else "",
        )
    )
    db.commit()


def serialize_call_log(item: CallLog) -> CallLogOut:
    return CallLogOut(
        id=item.id,
        capability=item.capability,
        endpoint=item.endpoint,
        status=item.status,
        durationMs=item.duration_ms,
        promptSummary=item.prompt_summary,
        errorMessage=item.error_message,
        createdAt=item.created_at,
    )


def sync_models_from_raw(db: Session, model: ModelGroup, raw: dict[str, Any], duration_ms: int) -> SyncModelsResult:
    model_names = filter_model_ids_for_capability(parse_model_ids(raw), model.capability)
    current = next((item.model_name for item in model.sub_models if item.id == model.primary_sub_model_id), "")
    primary = current if current in model_names else model_names[0] if model_names else current
    upsert_fetched_sub_models(db, model, model_names, primary)
    db.commit()
    refreshed = get_model_group_for_user_id(db, model.user_id, model.id)
    return SyncModelsResult(model=serialize_model(refreshed), models=model_names, durationMs=duration_ms, raw=raw)


def elapsed_ms(started_at: float) -> int:
    return round((time.perf_counter() - started_at) * 1000)
