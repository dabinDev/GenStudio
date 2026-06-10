from __future__ import annotations

import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.admin_permissions import (
    MODEL_PERMISSIONS,
    RECORD_AUDIT_PERMISSIONS,
    SYSTEM_PERMISSIONS,
    USER_CREDIT_PERMISSIONS,
    can,
    permissions_for_role,
    resolve_admin_role,
)
from app.config import Settings
from app.db_models import User


def make_user(
    *,
    email: str = "user@example.com",
    external_user_id: str = "user-1",
    phone: str = "",
    nickname: str = "User",
) -> User:
    return User(
        external_user_id=external_user_id,
        email=email,
        phone=phone,
        nickname=nickname,
        status="active",
    )


def test_configured_admin_email_resolves_super_admin_permissions() -> None:
    user = make_user(email="OWNER@Example.com")
    settings = Settings(admin_emails=["owner@example.com"], admin_identifiers=[])

    role = resolve_admin_role(user, settings)
    permissions = set(permissions_for_role(role))

    assert role == "super_admin"
    assert permissions == MODEL_PERMISSIONS | USER_CREDIT_PERMISSIONS | RECORD_AUDIT_PERMISSIONS | SYSTEM_PERMISSIONS
    assert can(user, "settings:update", settings) is True
    assert can(user, "model:publish", settings) is True


def test_non_admin_has_no_permissions() -> None:
    user = make_user(email="normal@example.com")
    settings = Settings(admin_emails=[], admin_identifiers=[])

    role = resolve_admin_role(user, settings)

    assert role == "none"
    assert permissions_for_role(role) == []
    assert can(user, "record:view", settings) is False


def test_admin_identifier_resolves_admin_without_settings_update() -> None:
    user = make_user(
        email="normal@example.com",
        external_user_id="cylonai",
        nickname="Operator",
    )
    settings = Settings(admin_emails=[], admin_identifiers=["cylonai"])

    role = resolve_admin_role(user, settings)
    permissions = set(permissions_for_role(role))

    assert role == "admin"
    assert "settings:update" not in permissions
    assert "user:delete" not in permissions
    assert "user:role:update" not in permissions
    assert "credit:settings" not in permissions
    assert "maintenance:user_merge" not in permissions
    assert "model:secret:view_summary" not in permissions
    assert "record:view" in permissions
    assert "credit:adjust" in permissions
    assert "model:publish" in permissions
    assert can(user, "settings:update", settings) is False
    assert can(user, "record:view", settings) is True


def test_permission_groups_are_complete_contract_sets() -> None:
    assert MODEL_PERMISSIONS == {
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
    assert USER_CREDIT_PERMISSIONS == {
        "user:view",
        "user:update",
        "user:disable",
        "user:delete",
        "user:restore",
        "user:role:update",
        "credit:view",
        "credit:adjust",
        "credit:settings",
    }
    assert RECORD_AUDIT_PERMISSIONS == {
        "record:view",
        "record:raw_json",
        "record:export",
        "audit:view",
        "audit:export",
    }
    assert SYSTEM_PERMISSIONS == {"settings:view", "settings:update", "maintenance:user_merge"}


def test_operator_and_viewer_include_read_permissions() -> None:
    operator_permissions = set(permissions_for_role("operator"))
    viewer_permissions = set(permissions_for_role("viewer"))

    assert operator_permissions == {
        "model:view",
        "model:test",
        "user:view",
        "credit:view",
        "record:view",
        "audit:view",
        "settings:view",
    }
    assert viewer_permissions == {
        "model:view",
        "user:view",
        "credit:view",
        "record:view",
        "audit:view",
        "settings:view",
    }
    assert "settings:update" not in operator_permissions
    assert "settings:update" not in viewer_permissions


def test_admin_permissions_me_route_returns_role_and_permissions(monkeypatch) -> None:
    from app.auth import get_current_user
    from app.config import get_settings
    from app.main import app

    user = make_user(email="owner@example.com")
    settings = Settings(admin_emails=["owner@example.com"], admin_identifiers=[])

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)

    response = client.get("/api/admin/permissions/me")

    assert response.status_code == 200
    assert response.json()["role"] == "super_admin"
    assert "settings:update" in response.json()["permissions"]

    app.dependency_overrides.clear()
