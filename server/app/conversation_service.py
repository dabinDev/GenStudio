from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.db_models import Conversation, ConversationMessage, GeneratedAsset, User, utcnow
from app.schemas import (
    ConversationCreate,
    ConversationMessageOut,
    ConversationOut,
    GeneratedAssetOut,
)


def _json_loads(value: str) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def make_title(value: str, fallback: str = "新的创作") -> str:
    normalized = " ".join(value.split()).strip()
    return (normalized[:60] or fallback)


def serialize_asset(asset: GeneratedAsset) -> GeneratedAssetOut:
    return GeneratedAssetOut(
        id=asset.id,
        capability=asset.capability,
        assetType=asset.asset_type,
        url=asset.url,
        thumbnailUrl=asset.thumbnail_url,
        metadata=_json_loads(asset.metadata_json),
        createdAt=asset.created_at,
    )


def serialize_message(message: ConversationMessage) -> ConversationMessageOut:
    return ConversationMessageOut(
        id=message.id,
        role=message.role,
        capability=message.capability,
        content=message.content,
        status=message.status,
        errorMessage=message.error_message,
        canRetry=message.can_retry,
        modelGroupId=message.model_group_id,
        subModelId=message.sub_model_id,
        assets=[serialize_asset(asset) for asset in message.assets],
        createdAt=message.created_at,
    )


def serialize_conversation(conversation: Conversation, include_messages: bool = True) -> ConversationOut:
    return ConversationOut(
        id=conversation.id,
        title=conversation.title,
        capability=conversation.capability,
        modelGroupId=conversation.model_group_id,
        subModelId=conversation.sub_model_id,
        status=conversation.status,
        createdAt=conversation.created_at,
        updatedAt=conversation.updated_at,
        messages=[serialize_message(message) for message in conversation.messages] if include_messages else [],
    )


def list_conversations(db: Session, user: User) -> list[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


def get_conversation(db: Session, user: User, conversation_id: str) -> Conversation:
    conversation = (
        db.query(Conversation)
        .options(selectinload(Conversation.messages).selectinload(ConversationMessage.assets))
        .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .one_or_none()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail={"message": "会话不存在。"})
    return conversation


def create_conversation(db: Session, user: User, payload: ConversationCreate) -> Conversation:
    conversation = Conversation(
        user_id=user.id,
        title=make_title(payload.title),
        capability=payload.capability,
        model_group_id=payload.modelGroupId,
        sub_model_id=payload.subModelId,
    )
    db.add(conversation)
    db.commit()
    return get_conversation(db, user, conversation.id)


def ensure_conversation(
    db: Session,
    user: User,
    *,
    conversation_id: str = "",
    title_seed: str = "",
    capability: str,
    model_group_id: str | None = None,
    sub_model_id: str | None = None,
) -> Conversation:
    if conversation_id:
        return get_conversation(db, user, conversation_id)
    conversation = Conversation(
        user_id=user.id,
        title=make_title(title_seed),
        capability=capability,
        model_group_id=model_group_id,
        sub_model_id=sub_model_id,
    )
    db.add(conversation)
    db.flush()
    return conversation


def add_message(
    db: Session,
    conversation: Conversation,
    user: User,
    *,
    role: str,
    capability: str,
    content: str = "",
    status: str = "success",
    error_message: str = "",
    can_retry: bool = False,
    model_group_id: str | None = None,
    sub_model_id: str | None = None,
    request: Any = None,
    response: Any = None,
) -> ConversationMessage:
    message = ConversationMessage(
        conversation_id=conversation.id,
        user_id=user.id,
        role=role,
        capability=capability,
        content=content,
        status=status,
        error_message=error_message,
        can_retry=can_retry,
        model_group_id=model_group_id,
        sub_model_id=sub_model_id,
        request_json=json.dumps(request, ensure_ascii=False) if request is not None else "",
        response_json=json.dumps(response, ensure_ascii=False) if response is not None else "",
    )
    db.add(message)
    conversation.capability = capability
    conversation.model_group_id = model_group_id or conversation.model_group_id
    conversation.sub_model_id = sub_model_id or conversation.sub_model_id
    conversation.updated_at = utcnow()
    db.flush()
    return message


def reload_conversation(db: Session, user: User, conversation_id: str) -> Conversation:
    db.expire_all()
    return get_conversation(db, user, conversation_id)


def add_asset(
    db: Session,
    message: ConversationMessage,
    user: User,
    *,
    capability: str,
    asset_type: str,
    url: str,
    thumbnail_url: str = "",
    metadata: Any = None,
) -> GeneratedAsset:
    asset = GeneratedAsset(
        user_id=user.id,
        conversation_id=message.conversation_id,
        message_id=message.id,
        capability=capability,
        asset_type=asset_type,
        url=url,
        thumbnail_url=thumbnail_url,
        metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata is not None else "",
    )
    db.add(asset)
    db.flush()
    return asset
