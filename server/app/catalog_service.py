from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.db_models import (
    CatalogModel,
    CatalogModelChannelGroup,
    CatalogModelParameter,
    CatalogModelParameterOption,
)
from app.schemas import (
    CatalogChannelGroupOut,
    CatalogModelOut,
    CatalogParameterOptionOut,
    CatalogParameterOut,
)


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def text_value(value: Any) -> str:
    return value.strip() if isinstance(value, str) else "" if value is None else str(value)


def is_broken_text(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    compact = "".join(text.split())
    question_marks = compact.count("?")
    if len(compact) >= 2 and question_marks / len(compact) > 0.65:
        return True
    return False


def readable_text(value: Any, fallback: str = "") -> str:
    text = text_value(value)
    if "??" in text:
        text = text.replace("???", "").replace("??", "").strip()
    return fallback if is_broken_text(text) else text


def clean_catalog_value(value: Any) -> Any:
    if isinstance(value, str):
        return readable_text(value)
    if isinstance(value, list):
        return [clean_catalog_value(item) for item in value]
    if isinstance(value, dict):
        return {key: clean_catalog_value(item) for key, item in value.items()}
    return value


LOBE_ICON_BASE_URL = "https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons"
LOBE_ICON_BY_BRAND = {
    "anthropic": "Claude-color.svg",
    "banana": "Gemini-color.svg",
    "chatglm": "Zhipu-color.svg",
    "claude": "Claude-color.svg",
    "codex": "OpenAI.svg",
    "deepseek": "DeepSeek-color.svg",
    "doubao": "Doubao-color.svg",
    "gemini": "Gemini-color.svg",
    "glm": "Zhipu-color.svg",
    "gpt": "OpenAI.svg",
    "grok": "XAI.svg",
    "kimi": "Kimi-color.svg",
    "kuaikuai": "Doubao-color.svg",
    "minimax": "Minimax-color.svg",
    "openai": "OpenAI.svg",
    "qvq": "Qwen-color.svg",
    "qwen": "Qwen-color.svg",
    "seed2.0": "Doubao-color.svg",
    "seed2": "Doubao-color.svg",
    "seedance": "Doubao-color.svg",
    "seedream": "Doubao-color.svg",
    "veo": "Gemini-color.svg",
    "wanxiang": "Qwen-color.svg",
    "xai": "XAI.svg",
    "zhipu": "Zhipu-color.svg",
}


def lobe_icon(file_name: str) -> str:
    return f"{LOBE_ICON_BASE_URL}/{file_name}"


def inferred_lobe_icon_from_text(*values: Any) -> str:
    source = " ".join(text_value(value) for value in values if text_value(value)).lower()
    if not source:
        return ""
    for keyword, file_name in LOBE_ICON_BY_BRAND.items():
        if keyword in source:
            return lobe_icon(file_name)
    return ""


def normalize_catalog_icon(value: Any) -> str:
    icon = text_value(value)
    if not icon:
        return ""
    inferred = inferred_lobe_icon_from_text(icon)
    if inferred:
        return inferred
    if icon.startswith(("http://", "https://", "/")):
        return icon
    file_name = icon
    if not file_name.lower().endswith((".svg", ".png", ".jpg", ".jpeg", ".webp")):
        file_name = f"{file_name}.svg"
    return lobe_icon(file_name)


def infer_catalog_icon(detail_or_icon: Any, *values: Any) -> str:
    if isinstance(detail_or_icon, dict):
        detail = detail_or_icon
        icon = text_value(detail.get("icon"))
        inferred = inferred_lobe_icon_from_text(
            icon,
            detail.get("display_name"),
            detail.get("model_name"),
        )
        return inferred or normalize_catalog_icon(icon)
    icon = text_value(detail_or_icon)
    inferred = inferred_lobe_icon_from_text(icon, *values)
    return inferred or normalize_catalog_icon(icon)


def int_value(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def optional_int_value(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int_value(value)


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def model_type_to_capability(model_type: int) -> str:
    return {1: "text", 2: "image", 3: "video"}.get(model_type, "text")


def catalog_lookup_id(value: str | None) -> str:
    return (value or "").strip()


def get_catalog_model_by_external_id(db: Session, external_id: str | None) -> CatalogModel | None:
    lookup = catalog_lookup_id(external_id)
    if not lookup:
        return None
    return (
        db.query(CatalogModel)
        .options(
            selectinload(CatalogModel.parameters).selectinload(CatalogModelParameter.options),
            selectinload(CatalogModel.channel_groups),
        )
        .filter(CatalogModel.external_id == lookup)
        .one_or_none()
    )


def find_catalog_model_by_name(db: Session, model_name: str, capability: str = "") -> CatalogModel | None:
    query = (
        db.query(CatalogModel)
        .options(
            selectinload(CatalogModel.parameters).selectinload(CatalogModelParameter.options),
            selectinload(CatalogModel.channel_groups),
        )
        .filter(CatalogModel.model_name == model_name)
    )
    if capability:
        query = query.filter(CatalogModel.capability == capability)
    return query.order_by(CatalogModel.updated_at.desc()).first()


def list_catalog_models(db: Session, capability: str = "") -> list[CatalogModel]:
    query = db.query(CatalogModel).options(
        selectinload(CatalogModel.parameters).selectinload(CatalogModelParameter.options),
        selectinload(CatalogModel.channel_groups),
    )
    if capability:
        query = query.filter(CatalogModel.capability == capability)
    return query.order_by(CatalogModel.model_type.asc(), CatalogModel.display_name.asc()).all()


def serialize_catalog_option(option: CatalogModelParameterOption) -> CatalogParameterOptionOut:
    return CatalogParameterOptionOut(
        id=option.external_id or option.id,
        optionName=readable_text(option.option_name, option.option_value),
        optionValue=option.option_value,
        description=readable_text(option.description),
        maxCount=option.max_count,
        isDefault=option.is_default,
        sortOrder=option.sort_order,
        priceFactor=option.price_factor,
    )


def serialize_catalog_parameter(parameter: CatalogModelParameter) -> CatalogParameterOut:
    return CatalogParameterOut(
        id=parameter.external_id or parameter.id,
        displayName=readable_text(parameter.display_name, parameter.param_key),
        paramKey=parameter.param_key,
        description=readable_text(parameter.description),
        widgetType=parameter.widget_type,
        isRequired=parameter.is_required,
        defaultValue=parameter.default_value,
        functionTag=readable_text(parameter.function_tag),
        maxCount=parameter.max_count,
        sortOrder=parameter.sort_order,
        options=[serialize_catalog_option(option) for option in parameter.options],
    )


def serialize_catalog_channel_group(group: CatalogModelChannelGroup) -> CatalogChannelGroupOut:
    try:
        option_prices = json.loads(group.option_prices_json or "[]")
    except json.JSONDecodeError:
        option_prices = []
    return CatalogChannelGroupOut(
        id=group.external_id or group.id,
        channelId=group.channel_id,
        groupName=readable_text(group.group_name, "默认分组"),
        billingType=group.billing_type,
        inputTokenPrice=group.input_token_price,
        outputTokenPrice=group.output_token_price,
        basePrice=group.base_price,
        successRate24h=group.success_rate_24h,
        avgResponseSeconds24h=group.avg_response_seconds_24h,
        totalSuccessCount=group.total_success_count,
        totalFailCount=group.total_fail_count,
        sortOrder=group.sort_order,
        optionPrices=clean_catalog_value(option_prices) if isinstance(option_prices, list) else [],
    )


def serialize_catalog_model(model: CatalogModel) -> CatalogModelOut:
    return CatalogModelOut(
        id=model.external_id,
        displayName=model.display_name,
        modelName=model.model_name,
        modelType=model.model_type,
        capability=model.capability,
        icon=model.icon,
        description=model.description,
        inputHint=model.input_hint,
        successRate=model.success_rate,
        source=model.source,
        parameters=[serialize_catalog_parameter(parameter) for parameter in model.parameters],
        channelGroups=[serialize_catalog_channel_group(group) for group in model.channel_groups],
    )


def upsert_catalog_model_detail(db: Session, detail: dict[str, Any], source: str = "kkyi") -> CatalogModel:
    external_id = text_value(detail.get("id"))
    if not external_id:
        raise HTTPException(status_code=400, detail={"message": "Catalog model id is required."})
    model_type = int_value(detail.get("model_type"))
    model = db.query(CatalogModel).filter(CatalogModel.external_id == external_id).one_or_none()
    if not model:
        model = CatalogModel(
            external_id=external_id,
            display_name="",
            model_name="",
            model_type=model_type,
            capability=model_type_to_capability(model_type),
        )
        db.add(model)
        db.flush()

    model.display_name = text_value(detail.get("display_name"))
    model.model_name = text_value(detail.get("model_name"))
    model.model_type = model_type
    model.capability = model_type_to_capability(model_type)
    model.icon = infer_catalog_icon(detail)
    model.description = text_value(detail.get("description"))
    model.input_hint = text_value(detail.get("input_hint"))
    model.success_rate = text_value(detail.get("success_rate"))
    model.raw_json = json_text(detail)
    model.source = source

    model.parameters.clear()
    for raw_parameter in detail.get("parameters") if isinstance(detail.get("parameters"), list) else []:
        if not isinstance(raw_parameter, dict):
            continue
        parameter = CatalogModelParameter(
            external_id=text_value(raw_parameter.get("id")),
            display_name=text_value(raw_parameter.get("display_name")),
            param_key=text_value(raw_parameter.get("param_key")),
            description=text_value(raw_parameter.get("description")),
            widget_type=int_value(raw_parameter.get("widget_type")),
            is_required=bool_value(raw_parameter.get("is_required")),
            default_value=text_value(raw_parameter.get("default_value")),
            function_tag=text_value(raw_parameter.get("function_tag")),
            max_count=optional_int_value(raw_parameter.get("max_count")),
            sort_order=int_value(raw_parameter.get("sort_order")),
            raw_json=json_text(raw_parameter),
        )
        for raw_option in raw_parameter.get("options") if isinstance(raw_parameter.get("options"), list) else []:
            if not isinstance(raw_option, dict):
                continue
            parameter.options.append(
                CatalogModelParameterOption(
                    external_id=text_value(raw_option.get("id")),
                    option_name=text_value(raw_option.get("option_name")),
                    option_value=text_value(raw_option.get("option_value")),
                    description=text_value(raw_option.get("description")),
                    max_count=optional_int_value(raw_option.get("max_count")),
                    is_default=bool_value(raw_option.get("is_default")),
                    sort_order=int_value(raw_option.get("sort_order")),
                    price_factor=text_value(raw_option.get("price_factor")),
                    raw_json=json_text(raw_option),
                )
            )
        model.parameters.append(parameter)

    model.channel_groups.clear()
    for raw_channel in detail.get("channel_groups") if isinstance(detail.get("channel_groups"), list) else []:
        if not isinstance(raw_channel, dict):
            continue
        channel_id = text_value(raw_channel.get("channel_id"))
        for raw_group in raw_channel.get("groups") if isinstance(raw_channel.get("groups"), list) else []:
            if not isinstance(raw_group, dict):
                continue
            model.channel_groups.append(
                CatalogModelChannelGroup(
                    external_id=text_value(raw_group.get("id")),
                    channel_id=text_value(raw_group.get("channel_id")) or channel_id,
                    group_name=text_value(raw_group.get("group_name")),
                    billing_type=int_value(raw_group.get("billing_type")),
                    input_token_price=text_value(raw_group.get("input_token_price")),
                    output_token_price=text_value(raw_group.get("output_token_price")),
                    base_price=text_value(raw_group.get("base_price")),
                    success_rate_24h=text_value(raw_group.get("success_rate_24h")),
                    avg_response_seconds_24h=text_value(raw_group.get("avg_response_seconds_24h")),
                    total_success_count=text_value(raw_group.get("total_success_count")),
                    total_fail_count=text_value(raw_group.get("total_fail_count")),
                    sort_order=int_value(raw_group.get("sort_order")),
                    option_prices_json=json_text(raw_group.get("option_prices") if isinstance(raw_group.get("option_prices"), list) else []),
                    raw_json=json_text(raw_group),
                )
            )
    db.flush()
    return model


def normalize_existing_catalog_icons(db: Session) -> int:
    changed = 0
    for model in db.query(CatalogModel).all():
        normalized = infer_catalog_icon(model.icon, model.display_name, model.model_name, model.description)
        if normalized and normalized != model.icon:
            model.icon = normalized
            changed += 1
    if changed:
        db.flush()
    return changed


async def fetch_kkyi_catalog_details(*, base_url: str, bearer_token: str, model_type: int = 0) -> list[dict[str, Any]]:
    headers = {"Accept": "application/json"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    details: list[dict[str, Any]] = []
    page = 1
    async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
        while True:
            list_response = await client.get(
                f"{base_url.rstrip() .rstrip('/')}/api/llm/model",
                params={"modelType": model_type, "page": page},
                headers=headers,
            )
            list_response.raise_for_status()
            payload = list_response.json()
            rows = payload.get("list") if isinstance(payload, dict) else []
            if not isinstance(rows, list) or not rows:
                break
            for row in rows:
                if not isinstance(row, dict) or not row.get("id"):
                    continue
                detail_response = await client.get(f"{base_url.rstrip().rstrip('/')}/api/llm/model/{row['id']}", headers=headers)
                detail_response.raise_for_status()
                detail = detail_response.json()
                if isinstance(detail, dict):
                    details.append(detail)
            total = int_value(payload.get("total") if isinstance(payload, dict) else 0)
            if total <= len(details) or len(rows) == 0:
                break
            page += 1
    return details


def sync_catalog_details(db: Session, details: list[dict[str, Any]]) -> list[CatalogModel]:
    models = [upsert_catalog_model_detail(db, detail) for detail in details]
    db.commit()
    external_ids = [model.external_id for model in models]
    if not external_ids:
        return []
    return (
        db.query(CatalogModel)
        .options(
            selectinload(CatalogModel.parameters).selectinload(CatalogModelParameter.options),
            selectinload(CatalogModel.channel_groups),
        )
        .filter(CatalogModel.external_id.in_(external_ids))
        .order_by(CatalogModel.model_type.asc(), CatalogModel.display_name.asc())
        .all()
    )
