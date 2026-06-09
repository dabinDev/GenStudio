from __future__ import annotations

import json
import re
import time
from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.catalog_service import find_catalog_model_by_name, get_catalog_model_by_external_id, serialize_catalog_model
from app.db_models import ApiKey, CallLog, CatalogModel, CatalogModelParameter, ModelGroup, SubModel, User
from app.proxy_utils import filter_model_ids_for_capability, parse_model_ids
from app.schemas import ApiKeyOut, CallLogOut, ModelCreate, ModelOut, ModelUpdate, SubModelOut, SyncModelsResult
from app.security import SecretDecryptionError, decrypt_secret, encrypt_secret


MODEL_UNAVAILABLE_MESSAGE = "模型不存在或未开通，请检查模型配置。"


def serialize_api_key(api_key: ApiKey) -> ApiKeyOut:
    return ApiKeyOut(
        id=api_key.id,
        name=api_key.name,
        baseUrl=api_key.base_url,
        status=api_key.status,
        createdAt=api_key.created_at,
    )


def catalog_external_id(catalog_model: CatalogModel | None) -> str | None:
    return catalog_model.external_id if catalog_model else None


def catalog_loader_options() -> tuple:
    return (
        selectinload(ModelGroup.api_key),
        selectinload(ModelGroup.catalog_model).selectinload(CatalogModel.parameters).selectinload(CatalogModelParameter.options),
        selectinload(ModelGroup.catalog_model).selectinload(CatalogModel.channel_groups),
        selectinload(ModelGroup.sub_models)
        .selectinload(SubModel.catalog_model)
        .selectinload(CatalogModel.parameters)
        .selectinload(CatalogModelParameter.options),
        selectinload(ModelGroup.sub_models).selectinload(SubModel.catalog_model).selectinload(CatalogModel.channel_groups),
    )


def is_broken_display_text(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    compact = re.sub(r"\s+", "", text)
    question_marks = compact.count("?")
    if len(compact) >= 2 and question_marks / len(compact) > 0.65:
        return True
    mojibake_chars = len(re.findall(r"[锟�鐢瑙鍥閸缂闈瑕鐞绠妯鍚彴鎿浣濉殕荤]", text))
    return len(text) >= 12 and mojibake_chars / len(text) > 0.28


def clean_display_text(value: str) -> str:
    return re.sub(r"\s+\?{2,}$", "", value.strip()).strip()


def readable_text(value: str | None) -> str:
    text = clean_display_text(value or "")
    return "" if is_broken_display_text(text) else text


def readable_sub_model_display_name(sub_model: SubModel) -> str:
    for candidate in (
        sub_model.display_name,
        sub_model.catalog_model.display_name if sub_model.catalog_model else "",
        sub_model.model_name,
    ):
        text = readable_text(candidate)
        if text:
            return text
    return sub_model.model_name


def readable_model_group_name(model: ModelGroup, primary: SubModel | None = None) -> str:
    selected = primary or next((item for item in model.sub_models if item.id == model.primary_sub_model_id), None)
    if not selected:
        selected = next((item for item in model.sub_models if item.is_primary), None)
    for candidate in (
        model.public_display_name,
        model.name,
        selected.catalog_model.display_name if selected and selected.catalog_model else "",
        model.catalog_model.display_name if model.catalog_model else "",
        selected.display_name if selected else "",
        selected.model_name if selected else "",
    ):
        text = readable_text(candidate)
        if text:
            return text
    return model.name


def serialize_sub_model(sub_model: SubModel, primary_id: str = "") -> SubModelOut:
    return SubModelOut(
        id=sub_model.id,
        modelName=sub_model.model_name,
        displayName=readable_sub_model_display_name(sub_model),
        capability=sub_model.capability,
        adapter=sub_model.adapter,
        isPrimary=sub_model.is_primary or sub_model.id == primary_id,
        status=sub_model.status,
        catalogModelId=catalog_external_id(sub_model.catalog_model),
        catalog=serialize_catalog_model(sub_model.catalog_model) if sub_model.catalog_model else None,
    )


def can_edit_model(model: ModelGroup, user: User | None = None, *, is_admin: bool = False) -> bool:
    if not user:
        return False
    if is_admin:
        return True
    return model.user_id == user.id and not model.is_public


def safe_model_description(model: ModelGroup, *, editable: bool) -> str:
    if editable:
        description = readable_text(model.description)
        return description or readable_text(model.catalog_model.description if model.catalog_model else "") or model.description
    if model.is_public:
        return "平台公共模型，可直接用于创作。"
    return re.sub(r"https?://[^\s)）]+", "", readable_text(model.description) or "").strip()


def parse_model_json(value: str, fallback: Any) -> Any:
    try:
        parsed = json.loads(value or "")
    except Exception:
        return fallback
    return parsed if isinstance(parsed, type(fallback)) else fallback


def serialize_model(model: ModelGroup, user: User | None = None, *, is_admin: bool = False) -> ModelOut:
    primary = next((item for item in model.sub_models if item.id == model.primary_sub_model_id), None)
    if not primary:
        primary = next((item for item in model.sub_models if item.is_primary), None)
    editable = can_edit_model(model, user, is_admin=is_admin)
    input_hint = readable_text(model.input_hint)
    if not input_hint and primary and primary.catalog_model:
        input_hint = readable_text(primary.catalog_model.input_hint)
    if not input_hint and model.catalog_model:
        input_hint = readable_text(model.catalog_model.input_hint)
    return ModelOut(
        id=model.id,
        name=readable_model_group_name(model, primary),
        vendor=readable_text(model.vendor) or model.vendor,
        capability=model.capability,
        adapter=model.adapter,
        description=safe_model_description(model, editable=editable),
        apiKeyId=model.api_key_id,
        baseUrl=model.api_key.base_url if editable else "",
        primarySubModelId=model.primary_sub_model_id,
        primaryModelName=primary.model_name if primary else "",
        isPublic=bool(model.is_public),
        canEdit=editable,
        catalogModelId=catalog_external_id(model.catalog_model),
        catalog=serialize_catalog_model(model.catalog_model) if model.catalog_model else None,
        subModels=[serialize_sub_model(item, model.primary_sub_model_id) for item in model.sub_models],
        publicDisplayName=readable_text(model.public_display_name),
        publicDescription=readable_text(model.public_description) if editable else "",
        inputHint=input_hint,
        iconUrl=model.icon_url,
        publicTags=parse_model_json(model.public_tags_json, []),
        promptOptimizeEnabled=bool(model.prompt_optimize_enabled),
        defaultParameters=parse_model_json(model.default_parameters_json, {}),
    )


def normalize_model_names(primary_model_name: str, available_model_names: list[str] | None = None) -> list[str]:
    names: list[str] = []
    for model_name in [*(available_model_names or []), primary_model_name]:
        value = model_name.strip()
        if value and value not in names:
            names.append(value)
    return names


def backfill_catalog_links(db: Session, models: list[ModelGroup]) -> bool:
    changed = False
    for model in models:
        if not model.catalog_model:
            primary = next((item for item in model.sub_models if item.id == model.primary_sub_model_id), None)
            if primary:
                catalog_model = find_catalog_model_by_name(db, primary.model_name, model.capability)
                if catalog_model:
                    model.catalog_model_id = catalog_model.id
                    changed = True
        for sub_model in model.sub_models:
            if sub_model.catalog_model:
                continue
            catalog_model = find_catalog_model_by_name(db, sub_model.model_name, sub_model.capability)
            if catalog_model:
                sub_model.catalog_model_id = catalog_model.id
                changed = True
    if changed:
        db.flush()
    return changed


def backfill_all_catalog_links(db: Session) -> int:
    models = db.query(ModelGroup).options(*catalog_loader_options()).all()
    if not backfill_catalog_links(db, models):
        return 0
    return len(models)


def should_default_public_model(payload: ModelCreate) -> bool:
    names = normalize_model_names(payload.primaryModelName, payload.availableModelNames)
    candidates = [payload.name, payload.primaryModelName, *names]
    return payload.capability == "text" and any("gpt-5.5" in item.strip().lower() for item in candidates)


def create_model_group(db: Session, user: User, payload: ModelCreate, *, is_admin: bool = False) -> ModelGroup:
    catalog_model = get_catalog_model_by_external_id(db, payload.catalogModelId)
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
        catalog_model_id=catalog_model.id if catalog_model else None,
        is_public=bool(is_admin and (payload.isPublic or should_default_public_model(payload))),
    )
    db.add(model)
    db.flush()
    primary_model_name = payload.primaryModelName.strip()
    for model_name in normalize_model_names(primary_model_name, payload.availableModelNames):
        sub_catalog_model = (
            catalog_model
            if catalog_model and catalog_model.model_name == model_name
            else find_catalog_model_by_name(db, model_name, payload.capability)
        )
        sub_model = SubModel(
            model_group_id=model.id,
            api_key_id=api_key.id,
            catalog_model_id=sub_catalog_model.id if sub_catalog_model else None,
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
    return get_model_group(db, user, model.id, is_admin=is_admin)


def get_model_group(
    db: Session,
    user: User,
    model_id: str,
    *,
    is_admin: bool = False,
    require_edit: bool = False,
    forbidden_message: str = "公共模型只有管理员可以编辑。",
) -> ModelGroup:
    return get_model_group_for_user_id(
        db,
        user.id,
        model_id,
        is_admin=is_admin,
        require_edit=require_edit,
        forbidden_message=forbidden_message,
    )


def get_model_group_for_user_id(
    db: Session,
    user_id: str,
    model_id: str,
    *,
    is_admin: bool = False,
    require_edit: bool = False,
    forbidden_message: str = "公共模型只有管理员可以编辑。",
) -> ModelGroup:
    model = (
        db.query(ModelGroup)
        .options(*catalog_loader_options())
        .filter(ModelGroup.id == model_id, or_(ModelGroup.user_id == user_id, ModelGroup.is_public.is_(True)))
        .one_or_none()
    )
    if not model:
        raise HTTPException(status_code=404, detail={"message": "模型不存在。"})
    if require_edit and not (is_admin or (model.user_id == user_id and not model.is_public)):
        raise HTTPException(status_code=403, detail={"message": forbidden_message})
    if backfill_catalog_links(db, [model]):
        db.commit()
        db.expire_all()
        model = (
            db.query(ModelGroup)
            .options(*catalog_loader_options())
            .filter(ModelGroup.id == model_id)
            .one()
        )
    return model


def list_model_groups(db: Session, user: User | None = None) -> list[ModelGroup]:
    query = db.query(ModelGroup).options(*catalog_loader_options())
    if user:
        query = query.filter(or_(ModelGroup.user_id == user.id, ModelGroup.is_public.is_(True)))
    else:
        query = query.filter(ModelGroup.is_public.is_(True))
    models = (
        query
        .order_by(ModelGroup.created_at.desc())
        .all()
    )
    if backfill_catalog_links(db, models):
        db.commit()
        db.expire_all()
        models = (
            query
            .order_by(ModelGroup.created_at.desc())
            .all()
        )
    return models


def list_api_keys(db: Session, user: User) -> list[ApiKey]:
    return db.query(ApiKey).filter(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc()).all()


def update_model_group(db: Session, user: User, model_id: str, payload: ModelUpdate, *, is_admin: bool = False) -> ModelGroup:
    model = get_model_group(db, user, model_id, is_admin=is_admin, require_edit=True)
    selected_catalog_model = model.catalog_model
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
    if payload.catalogModelId is not None:
        selected_catalog_model = get_catalog_model_by_external_id(db, payload.catalogModelId)
        model.catalog_model_id = selected_catalog_model.id if selected_catalog_model else None
    if payload.isPublic is not None:
        if not is_admin:
            raise HTTPException(status_code=403, detail={"message": "只有管理员可以调整公共模型。"})
        model.is_public = bool(payload.isPublic)
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
            sub_catalog_model = (
                selected_catalog_model
                if selected_catalog_model and selected_catalog_model.model_name == model_name
                else find_catalog_model_by_name(db, model_name, model.capability)
            )
            if not existing:
                existing = SubModel(
                    model_group_id=model.id,
                    api_key_id=model.api_key_id,
                    catalog_model_id=sub_catalog_model.id if sub_catalog_model else None,
                    model_name=model_name,
                    display_name=model_name,
                    capability=model.capability,
                    adapter=model.adapter,
                    is_primary=False,
                )
                db.add(existing)
                db.flush()
                model.sub_models.append(existing)
            elif sub_catalog_model:
                existing.catalog_model_id = sub_catalog_model.id
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
                catalog_model_id=model.catalog_model_id,
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
    return get_model_group(db, user, model_id, is_admin=is_admin)


def delete_model_group(db: Session, user: User, model_id: str, *, is_admin: bool = False) -> None:
    model = get_model_group(
        db,
        user,
        model_id,
        is_admin=is_admin,
        require_edit=True,
        forbidden_message="公共模型只有管理员可以删除。",
    )
    api_key = model.api_key
    db.delete(model)
    if api_key and len(api_key.model_groups) <= 1:
        db.delete(api_key)
    db.commit()


def set_primary_sub_model(db: Session, user: User, model_id: str, sub_model_id: str, *, is_admin: bool = False) -> ModelGroup:
    model = get_model_group(db, user, model_id, is_admin=is_admin, require_edit=True)
    target = next((item for item in model.sub_models if item.id == sub_model_id), None)
    if not target:
        raise HTTPException(status_code=404, detail={"message": "子模型不存在。"})
    for item in model.sub_models:
        item.is_primary = item.id == target.id
    model.primary_sub_model_id = target.id
    db.commit()
    return get_model_group(db, user, model_id, is_admin=is_admin)


def upsert_fetched_sub_models(
    db: Session,
    model: ModelGroup,
    model_names: list[str],
    primary_model_name: str,
) -> None:
    existing = {item.model_name: item for item in model.sub_models}
    for model_name in model_names:
        sub_model = existing.get(model_name)
        catalog_model = (
            model.catalog_model
            if model.catalog_model and model.catalog_model.model_name == model_name
            else find_catalog_model_by_name(db, model_name, model.capability)
        )
        if not sub_model:
            sub_model = SubModel(
                model_group_id=model.id,
                api_key_id=model.api_key_id,
                catalog_model_id=catalog_model.id if catalog_model else None,
                model_name=model_name,
                display_name=model_name,
                capability=model.capability,
                adapter=model.adapter,
            )
            db.add(sub_model)
        elif catalog_model:
            sub_model.catalog_model_id = catalog_model.id
        sub_model.is_primary = model_name == primary_model_name
    db.flush()
    primary = next((item for item in model.sub_models if item.model_name == primary_model_name), None)
    if primary:
        model.primary_sub_model_id = primary.id


def get_sub_model_for_user(db: Session, user: User | None, sub_model_id: str) -> tuple[ModelGroup, SubModel, ApiKey, str]:
    visibility_filter = (
        or_(ModelGroup.user_id == user.id, ModelGroup.is_public.is_(True))
        if user
        else ModelGroup.is_public.is_(True)
    )
    sub_model = (
        db.query(SubModel)
        .options(selectinload(SubModel.model_group), selectinload(SubModel.api_key))
        .join(ModelGroup, ModelGroup.id == SubModel.model_group_id)
        .filter(SubModel.id == sub_model_id, visibility_filter)
        .one_or_none()
    )
    if not sub_model:
        message = MODEL_UNAVAILABLE_MESSAGE if user else "请先登录。"
        raise HTTPException(status_code=404 if user else 401, detail={"message": message})
    api_key = sub_model.api_key
    try:
        decrypted_api_key = decrypt_secret(api_key.api_key_ciphertext)
    except SecretDecryptionError:
        raise HTTPException(
            status_code=503,
            detail={"message": "模型密钥无法解密，请管理员重新保存或重新配置该模型。"},
        ) from None
    return sub_model.model_group, sub_model, api_key, decrypted_api_key


def find_prompt_optimizer_sub_model(
    db: Session,
    user: User | None,
    requested_sub_model_id: str | None = None,
) -> tuple[ModelGroup, SubModel, ApiKey, str] | None:
    if requested_sub_model_id:
        try:
            model_group, sub_model, api_key_record, api_key = get_sub_model_for_user(db, user, requested_sub_model_id)
        except HTTPException:
            model_group = sub_model = api_key_record = api_key = None
        if sub_model and sub_model.capability == "text":
            return model_group, sub_model, api_key_record, api_key

    visibility_filter = (
        or_(ModelGroup.user_id == user.id, ModelGroup.is_public.is_(True))
        if user
        else ModelGroup.is_public.is_(True)
    )
    sub_models = (
        db.query(SubModel)
        .options(selectinload(SubModel.model_group), selectinload(SubModel.api_key))
        .join(ModelGroup, ModelGroup.id == SubModel.model_group_id)
        .filter(SubModel.capability == "text", visibility_filter, SubModel.status == "active")
        .all()
    )
    if not sub_models:
        return None

    def rank(item: SubModel) -> tuple[int, int, str]:
        source = f"{item.model_name} {item.display_name} {item.model_group.name}".lower()
        return (
            0 if "gpt-5.5" in source else 1,
            0 if item.model_group.is_public else 1,
            source,
        )

    sub_model = sorted(sub_models, key=rank)[0]
    api_key_record = sub_model.api_key
    return sub_model.model_group, sub_model, api_key_record, decrypt_secret(api_key_record.api_key_ciphertext)


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
    request_params: dict[str, Any] | None = None,
    response_summary: dict[str, Any] | None = None,
    conversation_id: str = "",
    message_id: str = "",
    is_public_model: bool = False,
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
            request_params_json=json.dumps(request_params or {}, ensure_ascii=False),
            response_summary_json=json.dumps(response_summary or {}, ensure_ascii=False),
            conversation_id=conversation_id,
            message_id=message_id,
            is_public_model=is_public_model,
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


def sync_models_from_raw(db: Session, model: ModelGroup, raw: dict[str, Any], duration_ms: int, *, user: User | None = None, is_admin: bool = False) -> SyncModelsResult:
    model_names = filter_model_ids_for_capability(parse_model_ids(raw), model.capability)
    current = next((item.model_name for item in model.sub_models if item.id == model.primary_sub_model_id), "")
    primary = current if current in model_names else model_names[0] if model_names else current
    upsert_fetched_sub_models(db, model, model_names, primary)
    db.commit()
    refreshed = get_model_group_for_user_id(db, model.user_id, model.id)
    return SyncModelsResult(model=serialize_model(refreshed, user, is_admin=is_admin), models=model_names, durationMs=duration_ms, raw=raw)


def elapsed_ms(started_at: float) -> int:
    return round((time.perf_counter() - started_at) * 1000)
