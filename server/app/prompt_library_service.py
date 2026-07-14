from __future__ import annotations

import json
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.admin_service import json_dumps_safe, parse_json_object, write_admin_log
from app.db_models import PromptSceneTemplate, PromptSceneTemplateEvent, User, utcnow


def _clean_text(value: Any, max_length: int | None = None) -> str:
    text = str(value or "").strip()
    if max_length and len(text) > max_length:
        return text[:max_length]
    return text


def _clean_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _clean_tags(value: Any) -> list[str]:
    tags: list[str] = []
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, str):
        raw_items = re.split(r"[,，/、\s]+", value)
    else:
        raw_items = []
    for item in raw_items:
        clean = _clean_text(item, 48)
        if clean and clean not in tags:
            tags.append(clean)
    return tags[:12]


def _prompt_summary(prompt_text: str) -> str:
    clean = re.sub(r"\s+", " ", prompt_text).strip()
    return clean[:220]


def template_external_id(entry: dict[str, Any], index: int) -> str:
    source = _clean_text(entry.get("source"), 64) or "yuque"
    original_no = _clean_text(entry.get("originalNo") or entry.get("original_no"), 64)
    category_id = _clean_text(entry.get("categoryId") or entry.get("category_id"), 64)
    title = _clean_text(entry.get("title"), 96)
    if original_no:
        return f"{source}:{category_id}:{original_no}"
    return f"{source}:{category_id}:{index}:{title}"


def serialize_scene_template(item: PromptSceneTemplate) -> dict[str, Any]:
    return {
        "id": item.id,
        "externalId": item.external_id,
        "capability": "image",
        "categoryId": item.category_id,
        "documentTitle": item.document_title,
        "documentUrl": item.document_url,
        "section": item.section,
        "category": item.category,
        "subcategory": item.subcategory,
        "title": item.title,
        "promptText": item.prompt_text,
        "promptSummary": item.prompt_summary,
        "tags": parse_json_object(item.tags_json, []),
        "source": item.source,
        "originalNo": item.original_no,
        "imageUrl": item.image_url,
        "model": item.model,
        "likes": item.likes,
        "views": item.views,
        "weight": item.weight,
        "enabled": item.enabled,
        "useCount": item.use_count,
        "clickCount": item.click_count,
        "impressionCount": item.impression_count,
        "createdAt": item.created_at,
        "updatedAt": item.updated_at,
    }


def upsert_scene_template_from_entry(
    db: Session,
    entry: dict[str, Any],
    *,
    index: int,
) -> tuple[PromptSceneTemplate, bool]:
    prompt_text = _clean_text(entry.get("promptText") or entry.get("prompt_zh"))
    if not prompt_text:
        raise ValueError("promptText is required")
    external_id = template_external_id(entry, index)
    item = db.query(PromptSceneTemplate).filter(PromptSceneTemplate.external_id == external_id).one_or_none()
    created = item is None
    if not item:
        item = PromptSceneTemplate(external_id=external_id)
        db.add(item)

    tags = _clean_tags(entry.get("tags"))
    likes = _clean_int(entry.get("likes"))
    views = _clean_int(entry.get("views"))
    item.category_id = _clean_text(entry.get("categoryId") or entry.get("category_id"), 128)
    item.document_title = _clean_text(entry.get("documentTitle") or entry.get("document_title"), 255)
    item.document_url = _clean_text(entry.get("documentUrl") or entry.get("document_url"))
    item.section = _clean_text(entry.get("section"), 255)
    item.category = _clean_text(entry.get("category"), 255)
    item.subcategory = _clean_text(entry.get("subcategory"), 255)
    item.title = _clean_text(entry.get("title"), 255) or _prompt_summary(prompt_text)[:80]
    item.prompt_text = prompt_text
    item.prompt_summary = _prompt_summary(prompt_text)
    item.tags_json = json_dumps_safe(tags)
    item.source = _clean_text(entry.get("source"), 128)
    item.original_no = _clean_text(entry.get("originalNo") or entry.get("original_no"), 64)
    item.image_url = _clean_text(entry.get("imageUrl") or entry.get("image_url"))
    item.model = _clean_text(entry.get("model"), 128)
    item.likes = likes
    item.views = views
    item.weight = max(likes, min(views // 100, 1000))
    item.enabled = True
    item.raw_json = json_dumps_safe(entry)
    item.imported_at = utcnow()
    return item, created


def import_prompt_scene_templates(
    db: Session,
    admin: User,
    index: dict[str, Any],
    *,
    replace: bool = False,
) -> dict[str, int]:
    prompts = index.get("prompts")
    if not isinstance(prompts, list):
        raise HTTPException(status_code=400, detail={"message": "index.prompts must be a list."})
    imported = 0
    updated = 0
    seen_external_ids: set[str] = set()
    for entry_index, raw_entry in enumerate(prompts, start=1):
        if not isinstance(raw_entry, dict):
            continue
        item, created = upsert_scene_template_from_entry(db, raw_entry, index=entry_index)
        seen_external_ids.add(item.external_id)
        if created:
            imported += 1
        else:
            updated += 1
    disabled = 0
    if replace:
        for item in db.query(PromptSceneTemplate).all():
            if item.external_id not in seen_external_ids and item.enabled:
                item.enabled = False
                disabled += 1
    db.commit()
    summary = {
        "imported": imported,
        "updated": updated,
        "disabled": disabled,
        "total": db.query(PromptSceneTemplate).count(),
    }
    write_admin_log(db, admin, action="import_prompt_library", target_type="prompt_scene_template", summary=summary)
    return summary


def _scene_template_query(
    db: Session,
    *,
    search: str = "",
    category_id: str = "",
    enabled: str = "",
):
    query = db.query(PromptSceneTemplate)
    clean_search = search.strip()
    if clean_search:
        pattern = f"%{clean_search}%"
        query = query.filter(
            or_(
                PromptSceneTemplate.title.like(pattern),
                PromptSceneTemplate.prompt_text.like(pattern),
                PromptSceneTemplate.category.like(pattern),
                PromptSceneTemplate.subcategory.like(pattern),
                PromptSceneTemplate.tags_json.like(pattern),
            )
        )
    if category_id.strip():
        query = query.filter(PromptSceneTemplate.category_id == category_id.strip())
    normalized_enabled = enabled.strip().lower()
    if normalized_enabled in {"true", "1", "yes"}:
        query = query.filter(PromptSceneTemplate.enabled.is_(True))
    if normalized_enabled in {"false", "0", "no"}:
        query = query.filter(PromptSceneTemplate.enabled.is_(False))
    return query


def list_scene_templates(
    db: Session,
    *,
    search: str = "",
    category_id: str = "",
    enabled: str = "",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PromptSceneTemplate], int]:
    query = _scene_template_query(db, search=search, category_id=category_id, enabled=enabled)
    total = query.count()
    rows = (
        query.order_by(PromptSceneTemplate.weight.desc(), PromptSceneTemplate.updated_at.desc())
        .offset(max(offset, 0))
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return rows, total


def scene_template_summary(
    db: Session,
    *,
    search: str = "",
    category_id: str = "",
) -> dict[str, int]:
    base = _scene_template_query(db, search=search, category_id=category_id)
    total = base.count()
    enabled_count = _scene_template_query(
        db, search=search, category_id=category_id, enabled="true"
    ).count()
    aggregate = base.with_entities(
        func.coalesce(func.sum(PromptSceneTemplate.impression_count), 0),
        func.coalesce(func.sum(PromptSceneTemplate.click_count), 0),
        func.coalesce(func.sum(PromptSceneTemplate.use_count), 0),
    ).one()
    return {
        "total": int(total),
        "enabled": int(enabled_count),
        "impressions": int(aggregate[0] or 0),
        "clicks": int(aggregate[1] or 0),
        "uses": int(aggregate[2] or 0),
    }


def update_scene_template(db: Session, admin: User, template_id: str, payload: dict[str, Any]) -> PromptSceneTemplate:
    item = db.get(PromptSceneTemplate, template_id)
    if not item:
        raise HTTPException(status_code=404, detail={"message": "Prompt scene template not found."})
    if "title" in payload:
        item.title = _clean_text(payload.get("title"), 255)
    if "promptText" in payload:
        item.prompt_text = _clean_text(payload.get("promptText"))
        item.prompt_summary = _prompt_summary(item.prompt_text)
    if "tags" in payload:
        item.tags_json = json_dumps_safe(_clean_tags(payload.get("tags")))
    if "categoryId" in payload:
        item.category_id = _clean_text(payload.get("categoryId"), 128)
    if "category" in payload:
        item.category = _clean_text(payload.get("category"), 255)
    if "subcategory" in payload:
        item.subcategory = _clean_text(payload.get("subcategory"), 255)
    if "weight" in payload:
        item.weight = _clean_int(payload.get("weight"))
    if "enabled" in payload:
        item.enabled = bool(payload.get("enabled"))
    db.commit()
    db.refresh(item)
    write_admin_log(db, admin, action="update_prompt_library", target_type="prompt_scene_template", target_id=item.id)
    return item


def batch_update_scene_templates(db: Session, admin: User, template_ids: list[str], *, enabled: bool | None = None) -> int:
    ids = [item.strip() for item in template_ids if item and item.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail={"message": "templateIds is required."})
    rows = db.query(PromptSceneTemplate).filter(PromptSceneTemplate.id.in_(ids)).all()
    for item in rows:
        if enabled is not None:
            item.enabled = enabled
    db.commit()
    write_admin_log(
        db,
        admin,
        action="batch_update_prompt_library",
        target_type="prompt_scene_template",
        summary={"updated": len(rows), "enabled": enabled},
    )
    return len(rows)


def recommendation_candidates(db: Session, *, limit: int = 80) -> list[PromptSceneTemplate]:
    return (
        db.query(PromptSceneTemplate)
        .filter(PromptSceneTemplate.enabled.is_(True))
        .order_by(PromptSceneTemplate.weight.desc(), PromptSceneTemplate.updated_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )


def build_recommendation_messages(image_url: str, candidates: list[PromptSceneTemplate]) -> list[dict[str, Any]]:
    candidate_payload = [
        {
            "id": item.id,
            "title": item.title,
            "category": item.category,
            "subcategory": item.subcategory,
            "tags": parse_json_object(item.tags_json, []),
            "summary": item.prompt_summary,
        }
        for item in candidates
    ]
    return [
        {
            "role": "system",
            "content": (
                "你是图片创作场景提示词推荐器。根据用户上传的参考图，从候选模板中挑选最相关的模板。"
                "同时把被选模板改写成可直接用于图片生成的完整中文提示词："
                "根据参考图补全模板中的方括号占位符，删除所有 [placeholder]，不要原样保留英文占位说明。"
                "只输出 JSON：{\"recommendations\":[{\"templateId\":\"...\",\"label\":\"短标签\",\"reason\":\"推荐原因\",\"promptText\":\"已根据参考图补全的完整提示词\"}]}。"
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "参考图如下，请从候选模板中推荐 8 个以内。候选模板 JSON：" + json.dumps(candidate_payload, ensure_ascii=False)},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        },
    ]


def parse_recommendation_payload(text: str) -> list[dict[str, str]]:
    clean = text.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?", "", clean).strip()
        clean = re.sub(r"```$", "", clean).strip()
    try:
        payload = json.loads(clean)
    except json.JSONDecodeError:
        return []
    recommendations = payload.get("recommendations") if isinstance(payload, dict) else []
    if not isinstance(recommendations, list):
        return []
    rows: list[dict[str, str]] = []
    for item in recommendations:
        if not isinstance(item, dict):
            continue
        template_id = _clean_text(item.get("templateId") or item.get("id"), 64)
        label = _clean_text(item.get("label"), 32)
        reason = _clean_text(item.get("reason"), 160)
        prompt_text = _clean_text(item.get("promptText") or item.get("prompt") or item.get("filledPrompt"))
        if template_id:
            rows.append({"templateId": template_id, "label": label, "reason": reason, "promptText": prompt_text})
    return rows[:12]


def is_gpt55_model(model_group_name: str, sub_model_name: str, display_name: str = "") -> bool:
    source = re.sub(r"[^a-z0-9.]+", "", f"{model_group_name} {sub_model_name} {display_name}".lower())
    return "gpt5.5" in source


def record_scene_template_event(
    db: Session,
    *,
    template: PromptSceneTemplate,
    user: User | None,
    event_type: str,
    image_url: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    if event_type == "impression":
        template.impression_count += 1
    if event_type == "click":
        template.click_count += 1
    if event_type == "use":
        template.use_count += 1
    db.add(
        PromptSceneTemplateEvent(
            template_id=template.id,
            user_id=user.id if user else None,
            event_type=event_type,
            image_url=image_url,
            metadata_json=json_dumps_safe(metadata or {}),
        )
    )


def record_scene_template_event_by_id(
    db: Session,
    *,
    template_id: str,
    user: User,
    event_type: str,
    image_url: str = "",
    metadata: dict[str, Any] | None = None,
) -> PromptSceneTemplate:
    if event_type not in {"impression", "click", "use"}:
        raise HTTPException(status_code=400, detail={"message": "Unsupported prompt library event type."})
    template = db.get(PromptSceneTemplate, template_id)
    if not template or not template.enabled:
        raise HTTPException(status_code=404, detail={"message": "Prompt scene template not found."})
    record_scene_template_event(
        db,
        template=template,
        user=user,
        event_type=event_type,
        image_url=_clean_text(image_url),
        metadata=metadata,
    )
    db.commit()
    db.refresh(template)
    return template
