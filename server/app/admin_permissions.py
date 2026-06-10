from __future__ import annotations

from app.config import Settings, get_settings
from app.db_models import User

ROLE_SUPER_ADMIN = "super_admin"
ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"
ROLE_NONE = "none"

PERMISSION_SETTINGS_UPDATE = "settings:update"
PERMISSION_MODEL_PUBLISH = "model:publish"
PERMISSION_MODEL_MANAGE = "model:manage"
PERMISSION_USER_MANAGE = "user:manage"
PERMISSION_RECORD_VIEW = "record:view"
PERMISSION_AUDIT_VIEW = "audit:view"

SUPER_ADMIN_PERMISSIONS = frozenset(
    {
        PERMISSION_SETTINGS_UPDATE,
        PERMISSION_MODEL_PUBLISH,
        PERMISSION_MODEL_MANAGE,
        PERMISSION_USER_MANAGE,
        PERMISSION_RECORD_VIEW,
        PERMISSION_AUDIT_VIEW,
    }
)
ADMIN_PERMISSIONS = frozenset(
    {
        PERMISSION_MODEL_PUBLISH,
        PERMISSION_MODEL_MANAGE,
        PERMISSION_USER_MANAGE,
        PERMISSION_RECORD_VIEW,
        PERMISSION_AUDIT_VIEW,
    }
)
OPERATOR_PERMISSIONS = frozenset({PERMISSION_RECORD_VIEW})
VIEWER_PERMISSIONS = frozenset({PERMISSION_RECORD_VIEW, PERMISSION_AUDIT_VIEW})

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
