from __future__ import annotations

from app.config import Settings, get_settings
from app.db_models import User

ROLE_SUPER_ADMIN = "super_admin"
ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"
ROLE_NONE = "none"

MODEL_PERMISSIONS = {
    "model:view",
    "model:create",
    "model:update",
    "model:delete",
    "model:publish",
    "model:unpublish",
    "model:test",
    "model:pricing",
    "model:secret:view_summary",
}
USER_CREDIT_PERMISSIONS = {
    "user:view",
    "user:export",
    "user:update",
    "user:disable",
    "user:delete",
    "user:restore",
    "user:role:update",
    "credit:view",
    "credit:adjust",
    "credit:settings",
}
RECORD_AUDIT_PERMISSIONS = {
    "record:view",
    "record:raw_json",
    "record:export",
    "audit:view",
    "audit:export",
}
SYSTEM_PERMISSIONS = {"settings:view", "settings:update", "maintenance:user_merge"}

SUPER_ADMIN_PERMISSIONS = frozenset(
    MODEL_PERMISSIONS | USER_CREDIT_PERMISSIONS | RECORD_AUDIT_PERMISSIONS | SYSTEM_PERMISSIONS
)
ADMIN_PERMISSIONS = frozenset(
    (MODEL_PERMISSIONS - {"model:secret:view_summary"})
    | RECORD_AUDIT_PERMISSIONS
    | {
        "user:view",
        "user:export",
        "user:update",
        "user:disable",
        "user:restore",
        "credit:view",
        "credit:adjust",
        "settings:view",
    }
)
OPERATOR_PERMISSIONS = frozenset(
    {
        "model:view",
        "model:test",
        "user:view",
        "credit:view",
        "record:view",
        "audit:view",
        "settings:view",
    }
)
VIEWER_PERMISSIONS = frozenset(
    {
        "model:view",
        "user:view",
        "credit:view",
        "record:view",
        "audit:view",
        "settings:view",
    }
)

PERMISSIONS_BY_ROLE = {
    ROLE_SUPER_ADMIN: SUPER_ADMIN_PERMISSIONS,
    ROLE_ADMIN: ADMIN_PERMISSIONS,
    ROLE_OPERATOR: OPERATOR_PERMISSIONS,
    ROLE_VIEWER: VIEWER_PERMISSIONS,
}


def _normalized_set(values: list[str]) -> set[str]:
    return {item.strip().lower() for item in values if item.strip()}


def resolve_admin_role(user: User | None, settings: Settings | None = None) -> str:
    if not user:
        return ROLE_NONE
    resolved_settings = settings or get_settings()
    email = (user.email or "").strip().lower()
    if email and email in _normalized_set(resolved_settings.admin_emails):
        return ROLE_SUPER_ADMIN

    assigned_role = getattr(getattr(user, "admin_role_assignment", None), "role", "")
    if assigned_role in PERMISSIONS_BY_ROLE:
        return assigned_role

    identities = {
        (user.external_user_id or "").strip().lower(),
        email,
        (user.phone or "").strip().lower(),
        (user.nickname or "").strip().lower(),
    }
    admin_identifiers = _normalized_set(resolved_settings.admin_identifiers)
    if admin_identifiers.intersection(identity for identity in identities if identity):
        return ROLE_ADMIN
    return ROLE_NONE


def permissions_for_role(role: str) -> list[str]:
    return sorted(PERMISSIONS_BY_ROLE.get(role, frozenset()))


def can(user: User | None, permission: str, settings: Settings | None = None) -> bool:
    role = resolve_admin_role(user, settings)
    return permission in PERMISSIONS_BY_ROLE.get(role, frozenset())
