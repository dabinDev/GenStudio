from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.db_models import (
    AdminOperationLog,
    AdminRoleAssignment,
    ApiKey,
    CallLog,
    CreditPricingRule,
    CreditTransaction,
    Conversation,
    ConversationMessage,
    GeneratedAsset,
    ModelHealthCheck,
    ModelGroup,
    PromptTemplate,
    SessionRecord,
    SystemSetting,
    TaskEvent,
    User,
    UserCreditAccount,
    UserCredential,
    utcnow,
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
        (UserCreditAccount, "user_id"),
        (CreditTransaction, "user_id"),
        (TaskEvent, "user_id"),
        (AdminRoleAssignment, "user_id"),
    ):
        total += db.query(model).filter(getattr(model, column_name) == user_id).count()
    total += db.query(AdminOperationLog).filter(AdminOperationLog.admin_user_id == user_id).count()
    total += db.query(PromptTemplate).filter(PromptTemplate.updated_by == user_id).count()
    total += db.query(CreditTransaction).filter(CreditTransaction.operator_user_id == user_id).count()
    total += db.query(CreditPricingRule).filter(CreditPricingRule.created_by == user_id).count()
    total += db.query(CreditPricingRule).filter(CreditPricingRule.updated_by == user_id).count()
    total += db.query(SystemSetting).filter(SystemSetting.updated_by == user_id).count()
    total += db.query(AdminRoleAssignment).filter(AdminRoleAssignment.assigned_by == user_id).count()
    total += db.query(ModelHealthCheck).filter(ModelHealthCheck.admin_user_id == user_id).count()
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


def _merge_credit_accounts(db: Session, target: User, source_ids: list[str]) -> int:
    moved = 0
    target_account = db.query(UserCreditAccount).filter(UserCreditAccount.user_id == target.id).first()
    source_accounts = db.query(UserCreditAccount).filter(UserCreditAccount.user_id.in_(source_ids)).all()
    for source_account in source_accounts:
        if not target_account:
            source_account.user_id = target.id
            source_account.updated_at = utcnow()
            target_account = source_account
            moved += 1
            continue

        target_account.balance += source_account.balance
        target_account.reserved_balance += source_account.reserved_balance
        target_account.total_recharged += source_account.total_recharged
        target_account.total_spent += source_account.total_spent
        target_account.total_refunded += source_account.total_refunded
        target_account.updated_at = utcnow()
        db.delete(source_account)
        moved += 1
    return moved


def _admin_role_payload(role: AdminRoleAssignment) -> dict[str, Any]:
    return {
        "assignmentId": role.id,
        "userId": role.user_id,
        "role": role.role,
        "assignedBy": role.assigned_by,
        "note": role.note,
    }


def _collect_admin_role_conflicts(db: Session, target: User, source_ids: list[str]) -> list[dict[str, Any]]:
    target_role = db.query(AdminRoleAssignment).filter(AdminRoleAssignment.user_id == target.id).first()
    if not target_role:
        return []
    source_roles = db.query(AdminRoleAssignment).filter(AdminRoleAssignment.user_id.in_(source_ids)).all()
    return [
        {
            "sourceUserId": source_role.user_id,
            "targetUserId": target.id,
            "targetRole": target_role.role,
            "discardedRole": source_role.role,
            "resolution": "kept_target_role",
            "targetAssignment": _admin_role_payload(target_role),
            "discardedAssignment": _admin_role_payload(source_role),
        }
        for source_role in source_roles
    ]


def _move_admin_role_assignments(
    db: Session,
    target: User,
    source_ids: list[str],
) -> int:
    moved = 0
    moved += (
        db.query(AdminRoleAssignment)
        .filter(AdminRoleAssignment.assigned_by.in_(source_ids))
        .update({AdminRoleAssignment.assigned_by.key: target.id}, synchronize_session=False)
    )
    target_role = db.query(AdminRoleAssignment).filter(AdminRoleAssignment.user_id == target.id).first()
    source_roles = db.query(AdminRoleAssignment).filter(AdminRoleAssignment.user_id.in_(source_ids)).all()
    for source_role in source_roles:
        if not target_role:
            source_role.user_id = target.id
            source_role.assigned_by = target.id if source_role.assigned_by in source_ids else source_role.assigned_by
            target_role = source_role
            moved += 1
            continue
        db.delete(source_role)
    return moved


def _bulk_move_user_id(
    db: Session,
    target: User,
    source_ids: list[str],
) -> int:
    moved = 0
    moved += _merge_credit_accounts(db, target, source_ids)
    moved += _move_admin_role_assignments(db, target, source_ids)
    for model, column in (
        (SessionRecord, SessionRecord.user_id),
        (ApiKey, ApiKey.user_id),
        (ModelGroup, ModelGroup.user_id),
        (CallLog, CallLog.user_id),
        (Conversation, Conversation.user_id),
        (ConversationMessage, ConversationMessage.user_id),
        (GeneratedAsset, GeneratedAsset.user_id),
        (CreditTransaction, CreditTransaction.user_id),
        (TaskEvent, TaskEvent.user_id),
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
        db.query(CreditTransaction)
        .filter(CreditTransaction.operator_user_id.in_(source_ids))
        .update({CreditTransaction.operator_user_id.key: target.id}, synchronize_session=False)
    )
    moved += (
        db.query(PromptTemplate)
        .filter(PromptTemplate.updated_by.in_(source_ids))
        .update({PromptTemplate.updated_by.key: target.id}, synchronize_session=False)
    )
    moved += (
        db.query(CreditPricingRule)
        .filter(CreditPricingRule.created_by.in_(source_ids))
        .update({CreditPricingRule.created_by.key: target.id}, synchronize_session=False)
    )
    moved += (
        db.query(CreditPricingRule)
        .filter(CreditPricingRule.updated_by.in_(source_ids))
        .update({CreditPricingRule.updated_by.key: target.id}, synchronize_session=False)
    )
    moved += (
        db.query(SystemSetting)
        .filter(SystemSetting.updated_by.in_(source_ids))
        .update({SystemSetting.updated_by.key: target.id}, synchronize_session=False)
    )
    moved += (
        db.query(ModelHealthCheck)
        .filter(ModelHealthCheck.admin_user_id.in_(source_ids))
        .update({ModelHealthCheck.admin_user_id.key: target.id}, synchronize_session=False)
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
        "roleConflicts": [],
    }
    summary["roleConflicts"] = _collect_admin_role_conflicts(db, target, source_ids)
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
        "roleConflictCount": sum(len(group.get("roleConflicts") or []) for group in groups),
    }
