from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.db_models import (
    AdminOperationLog,
    ApiKey,
    CallLog,
    Conversation,
    ConversationMessage,
    GeneratedAsset,
    ModelGroup,
    PromptTemplate,
    SessionRecord,
    User,
    UserCredential,
)


def _identity_key(user: User) -> str:
    email = (user.email or "").strip().lower()
    if email:
        return f"email:{email}"
    phone = (user.phone or "").strip()
    if phone:
        return f"phone:{phone}"
    return ""


def _credential_count(db: Session, user_id: str) -> int:
    return db.query(UserCredential).filter(UserCredential.user_id == user_id).count()


def _linked_record_count(db: Session, user_id: str) -> int:
    total = 0
    for model, column_name in (
        (SessionRecord, "user_id"),
        (UserCredential, "user_id"),
        (ApiKey, "user_id"),
        (ModelGroup, "user_id"),
        (CallLog, "user_id"),
        (Conversation, "user_id"),
        (ConversationMessage, "user_id"),
        (GeneratedAsset, "user_id"),
    ):
        total += db.query(model).filter(getattr(model, column_name) == user_id).count()
    total += db.query(AdminOperationLog).filter(AdminOperationLog.admin_user_id == user_id).count()
    total += db.query(PromptTemplate).filter(PromptTemplate.updated_by == user_id).count()
    return total


def _pick_canonical_user(db: Session, users: list[User]) -> User:
    return sorted(
        users,
        key=lambda user: (
            -_credential_count(db, user.id),
            0 if user.status == "active" else 1,
            -_linked_record_count(db, user.id),
            user.created_at,
            user.id,
        ),
    )[0]


def _move_credentials(db: Session, target: User, source_ids: list[str]) -> int:
    moved = 0
    credentials = db.query(UserCredential).filter(UserCredential.user_id.in_(source_ids)).all()
    for credential in credentials:
        conflict = (
            db.query(UserCredential)
            .filter(
                UserCredential.user_id == target.id,
                UserCredential.provider == credential.provider,
                UserCredential.identifier == credential.identifier,
            )
            .first()
        )
        if conflict:
            db.delete(credential)
            continue
        credential.user_id = target.id
        moved += 1
    return moved


def _bulk_move_user_id(db: Session, target: User, source_ids: list[str]) -> int:
    moved = 0
    for model, column in (
        (SessionRecord, SessionRecord.user_id),
        (ApiKey, ApiKey.user_id),
        (ModelGroup, ModelGroup.user_id),
        (CallLog, CallLog.user_id),
        (Conversation, Conversation.user_id),
        (ConversationMessage, ConversationMessage.user_id),
        (GeneratedAsset, GeneratedAsset.user_id),
    ):
        moved += (
            db.query(model)
            .filter(column.in_(source_ids))
            .update({column.key: target.id}, synchronize_session=False)
        )
    moved += (
        db.query(AdminOperationLog)
        .filter(AdminOperationLog.admin_user_id.in_(source_ids))
        .update({AdminOperationLog.admin_user_id.key: target.id}, synchronize_session=False)
    )
    moved += (
        db.query(PromptTemplate)
        .filter(PromptTemplate.updated_by.in_(source_ids))
        .update({PromptTemplate.updated_by.key: target.id}, synchronize_session=False)
    )
    return moved


def _merge_group(db: Session, identity: str, users: list[User], *, apply: bool) -> dict[str, Any]:
    target = _pick_canonical_user(db, users)
    sources = [user for user in users if user.id != target.id]
    source_ids = [user.id for user in sources]
    summary: dict[str, Any] = {
        "identity": identity,
        "targetUserId": target.id,
        "targetExternalUserId": target.external_user_id,
        "sourceUserIds": source_ids,
        "sourceExternalUserIds": [user.external_user_id for user in sources],
        "movedRecords": 0,
    }
    if not apply:
        return summary

    if identity.startswith("email:"):
        target.email = identity.removeprefix("email:")
    elif identity.startswith("phone:"):
        target.phone = identity.removeprefix("phone:")
    for source in sources:
        if not target.phone and source.phone:
            target.phone = source.phone.strip()
        if not target.nickname and source.nickname:
            target.nickname = source.nickname.strip()
        if not target.avatar_url and source.avatar_url:
            target.avatar_url = source.avatar_url.strip()
        if target.status != "active" and source.status == "active":
            target.status = "active"

    moved = _move_credentials(db, target, source_ids)
    moved += _bulk_move_user_id(db, target, source_ids)
    for source in sources:
        db.delete(source)
    summary["movedRecords"] = moved
    return summary


def merge_duplicate_users_by_identity(
    db: Session,
    *,
    apply: bool = False,
    identity_filter: str = "",
) -> dict[str, Any]:
    clean_filter = identity_filter.strip().lower()
    users = db.query(User).order_by(User.created_at.asc()).all()
    grouped: dict[str, list[User]] = defaultdict(list)
    for user in users:
        identity = _identity_key(user)
        if not identity:
            continue
        if clean_filter and clean_filter not in identity:
            continue
        grouped[identity].append(user)

    groups = [
        _merge_group(db, identity, rows, apply=apply)
        for identity, rows in sorted(grouped.items())
        if len(rows) > 1
    ]
    return {
        "apply": apply,
        "groups": groups,
        "groupCount": len(groups),
        "mergedUsers": sum(len(group["sourceUserIds"]) for group in groups),
        "movedRecords": sum(int(group.get("movedRecords") or 0) for group in groups),
    }
