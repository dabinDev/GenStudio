# v3-admin-vite Independent Admin Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independent `/admin/` management console based on v3-admin-vite conventions while preserving all existing GenStudio user-facing functionality and strengthening backend metrics, permissions, records, and audit capabilities.

**Architecture:** Keep `fronted/` as the creative workspace and create a new `admin/` Vue 3/Vite/Element Plus app for management. The new admin app shares the existing FastAPI auth/session/CSRF/user system and consumes expanded `/api/admin/*` contracts. Existing backend generation, conversation, model, credit, asset, and catalog flows remain intact.

**Tech Stack:** FastAPI, SQLAlchemy, MySQL/SQLite-compatible schema upgrades, pytest, Vue 3, Vite, TypeScript, Pinia, Vue Router, Element Plus, ECharts, Vitest.

---

## File Structure

### Backend

- Modify: `server/app/auth.py`
  Fix shared auth/admin Chinese messages and keep `require_admin_user` as the coarse gate.
- Create: `server/app/admin_permissions.py`
  Define admin roles, permission constants, role resolution, permission checks, and serialization for `/api/admin/permissions/me`.
- Modify: `server/app/db_models.py`
  Add tables for admin roles, model health checks, and task events if they are not already present.
- Modify: `server/app/database.py`
  Add idempotent startup migrations for new columns/tables.
- Modify: `server/app/schemas.py`
  Add admin response models for permissions, dashboard metrics, model health, task timelines, record detail, and system settings.
- Modify: `server/app/admin_service.py`
  Add aggregation helpers for dashboard, model health, user activity, unified records, record detail, task timeline, system settings, and user merge admin wrappers.
- Modify: `server/app/main.py`
  Wire new `/api/admin/*` routes, preserve existing routes, and enforce permission checks on sensitive operations.
- Modify: `server/app/model_service.py`
  Keep public/private model visibility semantics and expose health metadata where needed.
- Modify: `server/app/credit_service.py`
  Reuse existing settings and transactions for dashboard metrics; ensure admin adjustments remain audited.
- Test: `server/tests/test_admin_backend.py`
  Extend existing admin backend coverage.
- Test: `server/tests/test_admin_permissions.py`
  New focused permission tests.
- Test: `server/tests/test_admin_dashboard.py`
  New focused metrics and record-detail tests.

### New Admin Frontend

- Create: `admin/package.json`
- Create: `admin/index.html`
- Create: `admin/tsconfig.json`
- Create: `admin/vite.config.ts`
- Create: `admin/src/main.ts`
- Create: `admin/src/App.vue`
- Create: `admin/src/router/index.ts`
- Create: `admin/src/api/http.ts`
- Create: `admin/src/api/admin.ts`
- Create: `admin/src/stores/auth.ts`
- Create: `admin/src/stores/theme.ts`
- Create: `admin/src/layouts/AdminLayout.vue`
- Create: `admin/src/components/AdminPageHeader.vue`
- Create: `admin/src/components/AdminSearchPanel.vue`
- Create: `admin/src/components/AdminDataTable.vue`
- Create: `admin/src/components/AdminConfirmDialog.vue`
- Create: `admin/src/components/AdminDetailDrawer.vue`
- Create: `admin/src/components/AdminMetricCard.vue`
- Create: `admin/src/views/DashboardView.vue`
- Create: `admin/src/views/ModelCenterView.vue`
- Create: `admin/src/views/PromptCenterView.vue`
- Create: `admin/src/views/UserCreditsView.vue`
- Create: `admin/src/views/RecordsView.vue`
- Create: `admin/src/views/AuditLogsView.vue`
- Create: `admin/src/views/SystemSettingsView.vue`
- Create: `admin/src/views/ForbiddenView.vue`
- Create: `admin/src/styles/tokens.css`
- Create: `admin/src/styles/global.css`
- Create: `admin/src/types.ts`
- Create: `admin/src/utils/format.ts`
- Test: `admin/src/api/admin.test.ts`
- Test: `admin/src/router/guards.test.ts`
- Test: `admin/src/views/dashboard.test.ts`

### Existing Frontend Cleanup

- Modify: `fronted/src/App.vue`
  Remove old `admin` view, admin state, admin functions, and admin template sections.
- Modify: `fronted/src/api.ts`
  Keep shared auth/user-facing APIs; remove admin-only API helpers after the new admin app has its own client.
- Modify: `fronted/src/types.ts`
  Keep user-facing types; move admin-only types to `admin/src/types.ts`.
- Modify: `fronted/src/styles.css`
  Remove `.shell-admin`, `.admin-*` old backend UI CSS while keeping creative workspace styles.
- Delete: `fronted/src/adminPresentation.ts`
- Modify or delete: `fronted/src/adminPresentation.test.ts`
  Delete if it only verifies old embedded admin UI.
- Modify: `fronted/src/api.test.ts`
  Remove expectations for embedded admin API helpers that move to `admin/`.
- Modify: `fronted/src/styleApplication.test.ts`
  Remove assertions tied to `.shell-admin`.

### Deployment

- Modify: `docker-compose.yml`
  Build or mount both `fronted/dist` and `admin/dist`.
- Create or modify: `deploy/nginx.conf`
  Route `/` to creative workspace, `/admin/` to admin app, and `/api/` to FastAPI.
- Modify: project deployment notes or memory file used by this repo if present.

---

## Task 1: Backend Permission Foundation

**Files:**
- Create: `server/app/admin_permissions.py`
- Modify: `server/app/auth.py`
- Modify: `server/app/schemas.py`
- Modify: `server/app/main.py`
- Test: `server/tests/test_admin_permissions.py`

- [ ] **Step 1: Write failing tests for admin permission serialization**

Create `server/tests/test_admin_permissions.py` with:

```python
from app.admin_permissions import (
    ROLE_SUPER_ADMIN,
    can,
    permissions_for_role,
    resolve_admin_role,
)
from app.config import Settings
from app.db_models import User


def test_configured_admin_email_is_super_admin():
    user = User(id="usr_admin", external_user_id="ext-admin", email="cage_ben@sina.com", status="active")
    settings = Settings(admin_emails=["cage_ben@sina.com"], admin_identifiers=[])

    role = resolve_admin_role(user, settings)

    assert role == ROLE_SUPER_ADMIN
    assert can(user, "settings:update", settings)
    assert can(user, "model:publish", settings)


def test_non_admin_has_no_admin_permissions():
    user = User(id="usr_user", external_user_id="ext-user", email="user@example.com", status="active")
    settings = Settings(admin_emails=["cage_ben@sina.com"], admin_identifiers=[])

    assert resolve_admin_role(user, settings) == ""
    assert permissions_for_role("") == []
    assert not can(user, "record:view", settings)
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```powershell
python -m pytest server/tests/test_admin_permissions.py -q
```

Expected: FAIL because `app.admin_permissions` does not exist.

- [ ] **Step 3: Implement permission constants and helpers**

Create `server/app/admin_permissions.py`:

```python
from __future__ import annotations

from app.auth import is_admin_user
from app.config import Settings, get_settings
from app.db_models import User

ROLE_SUPER_ADMIN = "super_admin"
ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"

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
SYSTEM_PERMISSIONS = {
    "settings:view",
    "settings:update",
    "maintenance:user_merge",
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    ROLE_SUPER_ADMIN: MODEL_PERMISSIONS | USER_CREDIT_PERMISSIONS | RECORD_AUDIT_PERMISSIONS | SYSTEM_PERMISSIONS,
    ROLE_ADMIN: (
        MODEL_PERMISSIONS
        | {"user:view", "user:update", "user:disable", "user:restore", "credit:view", "credit:adjust"}
        | RECORD_AUDIT_PERMISSIONS
        | {"settings:view"}
    ),
    ROLE_OPERATOR: {
        "model:view",
        "model:test",
        "user:view",
        "credit:view",
        "record:view",
        "audit:view",
        "settings:view",
    },
    ROLE_VIEWER: {"model:view", "user:view", "credit:view", "record:view", "audit:view", "settings:view"},
}


def resolve_admin_role(user: User | None, settings: Settings | None = None) -> str:
    if not user:
        return ""
    resolved = settings or get_settings()
    if not is_admin_user(user, resolved):
        return ""
    email = (user.email or "").strip().lower()
    if email and email in {item.strip().lower() for item in resolved.admin_emails}:
        return ROLE_SUPER_ADMIN
    return ROLE_ADMIN


def permissions_for_role(role: str) -> list[str]:
    return sorted(ROLE_PERMISSIONS.get(role, set()))


def can(user: User | None, permission: str, settings: Settings | None = None) -> bool:
    role = resolve_admin_role(user, settings)
    return permission in ROLE_PERMISSIONS.get(role, set())
```

- [ ] **Step 4: Add schema for current admin permissions**

Add to `server/app/schemas.py`:

```python
class AdminPermissionOut(BaseModel):
    role: str
    permissions: list[str] = Field(default_factory=list)
```

- [ ] **Step 5: Add `/api/admin/permissions/me` route**

Import helpers in `server/app/main.py`:

```python
from app.admin_permissions import permissions_for_role, resolve_admin_role
```

Add route near existing admin routes:

```python
@app.get("/api/admin/permissions/me")
async def admin_permissions_me(
    admin: User = Depends(require_admin_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    role = resolve_admin_role(admin, settings)
    return {"role": role, "permissions": permissions_for_role(role)}
```

- [ ] **Step 6: Fix shared admin forbidden message**

In `server/app/auth.py`, replace the garbled admin denial message inside `require_admin_user` with:

```python
raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"message": "褰撳墠璐﹀彿娌℃湁绠＄悊鍛樻潈闄愩€?})
```

- [ ] **Step 7: Run permission tests**

Run:

```powershell
python -m pytest server/tests/test_admin_permissions.py -q
```

Expected: PASS.

- [ ] **Step 8: Run existing auth/admin tests**

Run:

```powershell
python -m pytest server/tests/test_auth_models.py server/tests/test_admin_backend.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add server/app/admin_permissions.py server/app/auth.py server/app/schemas.py server/app/main.py server/tests/test_admin_permissions.py
git commit -m "feat: add admin permission contract"
```

---

## Task 2: Backend Dashboard Metrics API

**Files:**
- Modify: `server/app/schemas.py`
- Modify: `server/app/admin_service.py`
- Modify: `server/app/main.py`
- Test: `server/tests/test_admin_dashboard.py`

- [ ] **Step 1: Write failing tests for dashboard metrics**

Create `server/tests/test_admin_dashboard.py` with:

```python
from datetime import timedelta

from app.admin_service import admin_dashboard_metrics
from app.db_models import CallLog, CreditTransaction, ModelGroup, User, utcnow


def test_dashboard_metrics_groups_calls_and_credits(db_session):
    user = User(external_user_id="metrics-user", email="metrics@example.com", nickname="Metrics", status="active")
    admin = User(external_user_id="metrics-admin", email="admin@example.com", nickname="Admin", status="active")
    db_session.add_all([user, admin])
    db_session.flush()
    public_model = ModelGroup(
        user_id=admin.id,
        api_key_id="key_missing",
        name="Public Image",
        vendor="test",
        capability="image",
        adapter="image-openai",
        is_public=True,
    )
    db_session.add(public_model)
    db_session.flush()
    now = utcnow()
    db_session.add_all(
        [
            CallLog(
                user_id=user.id,
                model_group_id=public_model.id,
                capability="image",
                endpoint="/api/proxy/image",
                status="success",
                duration_ms=1200,
                is_public_model=True,
                created_at=now - timedelta(days=1),
            ),
            CallLog(
                user_id=user.id,
                model_group_id=public_model.id,
                capability="image",
                endpoint="/api/proxy/image",
                status="error",
                duration_ms=130000,
                error_message="timeout",
                is_public_model=True,
                created_at=now,
            ),
            CreditTransaction(
                user_id=user.id,
                type="generation_reserve",
                amount=-1,
                balance_after=9,
                reserved_after=1,
                status="reserved",
                capability="image",
                model_group_id=public_model.id,
                created_at=now,
            ),
        ]
    )
    db_session.commit()

    metrics = admin_dashboard_metrics(db_session, range_key="30d")

    assert metrics["totals"]["totalCalls"] == 2
    assert metrics["totals"]["failedCalls"] == 1
    assert metrics["totals"]["timeoutCalls"] == 1
    assert metrics["capabilityBreakdown"][0]["capability"] == "image"
    assert metrics["creditSummary"]["reserved"] == 1
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```powershell
python -m pytest server/tests/test_admin_dashboard.py::test_dashboard_metrics_groups_calls_and_credits -q
```

Expected: FAIL because `admin_dashboard_metrics` does not exist.

- [ ] **Step 3: Add dashboard schema types**

Add to `server/app/schemas.py`:

```python
class AdminDashboardTotalsOut(BaseModel):
    totalCalls: int
    successCalls: int
    failedCalls: int
    timeoutCalls: int
    failureRate: float
    timeoutRate: float
    averageDurationMs: int
    publicModelCalls: int
    privateModelCalls: int


class AdminDashboardBucketOut(BaseModel):
    label: str
    totalCalls: int
    successCalls: int
    failedCalls: int
    timeoutCalls: int
    quotaUnits: float = 0
    averageDurationMs: int = 0


class AdminDashboardMetricOut(BaseModel):
    totals: AdminDashboardTotalsOut
    trends: dict[str, list[AdminDashboardBucketOut]]
    capabilityBreakdown: list[dict[str, Any]] = Field(default_factory=list)
    ownershipBreakdown: list[dict[str, Any]] = Field(default_factory=list)
    creditSummary: dict[str, int] = Field(default_factory=dict)
    failedModels: list[dict[str, Any]] = Field(default_factory=list)
    slowModels: list[dict[str, Any]] = Field(default_factory=list)
    activeUsers: list[dict[str, Any]] = Field(default_factory=list)
```

- [ ] **Step 4: Implement dashboard aggregation**

Add to `server/app/admin_service.py`:

```python
def _range_start(range_key: str) -> datetime:
    now = datetime.utcnow()
    if range_key == "90d":
        return now - timedelta(days=90)
    if range_key == "7d":
        return now - timedelta(days=7)
    return now - timedelta(days=30)


def _breakdown(rows: list[CallLog], key_fn) -> list[dict[str, Any]]:
    grouped: dict[str, list[CallLog]] = {}
    for item in rows:
        grouped.setdefault(key_fn(item), []).append(item)
    result = []
    for key, items in grouped.items():
        total = len(items)
        failed = len([item for item in items if item.status != "success"])
        result.append(
            {
                "key": key,
                "capability": key,
                "label": key,
                "totalCalls": total,
                "successCalls": total - failed,
                "failedCalls": failed,
                "failureRate": failed / total if total else 0,
            }
        )
    return sorted(result, key=lambda item: item["totalCalls"], reverse=True)


def admin_dashboard_metrics(db: Session, *, range_key: str = "30d") -> dict[str, Any]:
    start = _range_start(range_key)
    logs = db.query(CallLog).filter(CallLog.created_at >= start).all()
    total = len(logs)
    failed = len([item for item in logs if item.status != "success"])
    timeout = len([item for item in logs if _is_timeout_log(item)])
    public_calls = len([item for item in logs if item.is_public_model])
    average_duration_ms = int(sum(item.duration_ms for item in logs) / total) if total else 0
    credit_rows = db.query(CreditTransaction).filter(CreditTransaction.created_at >= start).all()
    credit_summary = {
        "reserved": abs(sum(item.amount for item in credit_rows if item.type == "generation_reserve")),
        "spent": sum(abs(item.amount) for item in credit_rows if item.type == "generation_capture"),
        "refunded": sum(item.amount for item in credit_rows if item.type == "generation_refund"),
        "adminAdjusted": sum(item.amount for item in credit_rows if item.type == "admin_adjustment"),
    }
    active_users = []
    by_user: dict[str, list[CallLog]] = {}
    for item in logs:
        by_user.setdefault(item.user_id, []).append(item)
    for user_id, items in by_user.items():
        user = db.get(User, user_id)
        active_users.append(
            {
                "userId": user_id,
                "label": user.email or user.nickname or user_id if user else user_id,
                "totalCalls": len(items),
                "publicModelCalls": len([item for item in items if item.is_public_model]),
                "privateModelCalls": len([item for item in items if not item.is_public_model]),
            }
        )
    active_users.sort(key=lambda item: item["totalCalls"], reverse=True)
    return {
        "totals": {
            "totalCalls": total,
            "successCalls": total - failed,
            "failedCalls": failed,
            "timeoutCalls": timeout,
            "failureRate": failed / total if total else 0,
            "timeoutRate": timeout / total if total else 0,
            "averageDurationMs": average_duration_ms,
            "publicModelCalls": public_calls,
            "privateModelCalls": total - public_calls,
        },
        "trends": {
            "day": _trend_buckets(logs, period="day", count=14),
            "week": _trend_buckets(logs, period="week", count=8),
            "month": _trend_buckets(logs, period="month", count=6),
        },
        "capabilityBreakdown": _breakdown(logs, lambda item: item.capability or "unknown"),
        "ownershipBreakdown": [
            {"key": "public", "label": "鍏敤妯″瀷", "totalCalls": public_calls},
            {"key": "private", "label": "绉佹湁妯″瀷", "totalCalls": total - public_calls},
        ],
        "creditSummary": credit_summary,
        "failedModels": admin_overview(db).get("failedModels", []),
        "slowModels": sorted(
            [
                {
                    "modelGroupId": model_id,
                    "averageDurationMs": int(sum(item.duration_ms for item in items) / len(items)),
                    "totalCalls": len(items),
                }
                for model_id, items in {
                    item.model_group_id or "": [row for row in logs if (row.model_group_id or "") == (item.model_group_id or "")]
                    for item in logs
                    if item.model_group_id
                }.items()
                if items
            ],
            key=lambda item: item["averageDurationMs"],
            reverse=True,
        )[:10],
        "activeUsers": active_users[:10],
    }
```

- [ ] **Step 5: Add dashboard routes**

In `server/app/main.py`, import `admin_dashboard_metrics` and add:

```python
@app.get("/api/admin/dashboard/metrics")
async def admin_dashboard_metrics_route(
    range: str = "30d",
    _admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return admin_dashboard_metrics(db, range_key=range)
```

- [ ] **Step 6: Run dashboard tests**

Run:

```powershell
python -m pytest server/tests/test_admin_dashboard.py -q
```

Expected: PASS.

- [ ] **Step 7: Run admin backend tests**

Run:

```powershell
python -m pytest server/tests/test_admin_backend.py server/tests/test_admin_dashboard.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add server/app/schemas.py server/app/admin_service.py server/app/main.py server/tests/test_admin_dashboard.py
git commit -m "feat: add admin dashboard metrics"
```

---

## Task 3: Backend Unified Records, Details, and Task Timeline

**Files:**
- Modify: `server/app/schemas.py`
- Modify: `server/app/admin_service.py`
- Modify: `server/app/main.py`
- Test: `server/tests/test_admin_dashboard.py`

- [ ] **Step 1: Write failing tests for record detail and timeline**

Add to `server/tests/test_admin_dashboard.py`:

```python
from app.admin_service import admin_record_detail, admin_task_timeline
from app.db_models import Conversation, ConversationMessage, GeneratedAsset


def test_admin_record_detail_includes_message_assets_and_call_log(db_session):
    user = User(external_user_id="record-user", email="record@example.com", nickname="Record", status="active")
    db_session.add(user)
    db_session.flush()
    conversation = Conversation(user_id=user.id, title="Image test", capability="image")
    db_session.add(conversation)
    db_session.flush()
    message = ConversationMessage(
        conversation_id=conversation.id,
        user_id=user.id,
        role="assistant",
        capability="image",
        content="completed",
        status="success",
        request_json='{"prompt":"鐢熸垚鍥剧墖"}',
        response_json='{"taskId":"task_123"}',
    )
    db_session.add(message)
    db_session.flush()
    db_session.add(
        GeneratedAsset(
            user_id=user.id,
            conversation_id=conversation.id,
            message_id=message.id,
            capability="image",
            asset_type="image",
            url="/api/assets/generated/result.png",
        )
    )
    db_session.add(
        CallLog(
            user_id=user.id,
            capability="image",
            endpoint="/api/proxy/image/query",
            status="success",
            duration_ms=800,
            conversation_id=conversation.id,
            message_id=message.id,
            response_summary_json='{"taskId":"task_123","status":"completed"}',
        )
    )
    db_session.commit()

    detail = admin_record_detail(db_session, message.id)

    assert detail["id"] == message.id
    assert detail["assets"][0]["url"] == "/api/assets/generated/result.png"
    assert detail["timeline"][-1]["status"] == "success"


def test_admin_task_timeline_uses_task_id(db_session):
    user = User(external_user_id="timeline-user", email="timeline@example.com", nickname="Timeline", status="active")
    db_session.add(user)
    db_session.flush()
    db_session.add(
        CallLog(
            user_id=user.id,
            capability="video",
            endpoint="/api/proxy/video/query",
            status="error",
            duration_ms=500,
            error_message="浠诲姟澶辫触",
            response_summary_json='{"taskId":"task_timeline","status":"failed"}',
        )
    )
    db_session.commit()

    timeline = admin_task_timeline(db_session, "task_timeline")

    assert timeline["taskId"] == "task_timeline"
    assert timeline["events"][0]["status"] == "error"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest server/tests/test_admin_dashboard.py::test_admin_record_detail_includes_message_assets_and_call_log server/tests/test_admin_dashboard.py::test_admin_task_timeline_uses_task_id -q
```

Expected: FAIL because the service functions do not exist.

- [ ] **Step 3: Add detail helper functions**

Add to `server/app/admin_service.py`:

```python
def _call_log_mentions_task(item: CallLog, task_id: str) -> bool:
    if not task_id:
        return False
    return task_id in (item.response_summary_json or "") or task_id in (item.request_params_json or "") or task_id in (item.error_message or "")


def _timeline_row(item: CallLog) -> dict[str, Any]:
    response_summary = parse_json_object(item.response_summary_json, {})
    return {
        "id": item.id,
        "endpoint": item.endpoint,
        "status": item.status,
        "durationMs": item.duration_ms,
        "errorMessage": item.error_message,
        "createdAt": item.created_at,
        "responseSummary": response_summary if isinstance(response_summary, dict) else {},
    }


def admin_record_detail(db: Session, message_id: str) -> dict[str, Any]:
    message = db.query(ConversationMessage).filter(ConversationMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail={"message": "璁板綍涓嶅瓨鍦ㄣ€?})
    conversation = db.get(Conversation, message.conversation_id)
    user = db.get(User, message.user_id)
    logs = (
        db.query(CallLog)
        .filter(
            or_(
                CallLog.message_id == message.id,
                CallLog.conversation_id == message.conversation_id,
            )
        )
        .order_by(CallLog.created_at.asc())
        .all()
    )
    assets = [
        {
            "type": item.asset_type,
            "url": item.url,
            "thumbnailUrl": item.thumbnail_url,
        }
        for item in message.assets
    ]
    return {
        "id": message.id,
        "conversationId": message.conversation_id,
        "conversationTitle": conversation.title if conversation else "",
        "user": serialize_admin_user(user) if user else None,
        "role": message.role,
        "capability": message.capability,
        "status": message.status,
        "content": _clean_history_value(message.content),
        "request": parse_json_object(message.request_json, {}),
        "response": parse_json_object(message.response_json, {}),
        "errorMessage": message.error_message,
        "assets": assets,
        "timeline": [_timeline_row(item) for item in logs],
        "createdAt": message.created_at,
    }


def admin_task_timeline(db: Session, task_id: str) -> dict[str, Any]:
    clean_task_id = task_id.strip()
    if not clean_task_id:
        raise HTTPException(status_code=400, detail={"message": "缂哄皯浠诲姟 ID銆?})
    logs = db.query(CallLog).order_by(CallLog.created_at.asc()).all()
    events = [_timeline_row(item) for item in logs if _call_log_mentions_task(item, clean_task_id)]
    return {"taskId": clean_task_id, "events": events}
```

- [ ] **Step 4: Add routes**

In `server/app/main.py`, import `admin_record_detail` and `admin_task_timeline`, then add:

```python
@app.get("/api/admin/records/detail/{message_id}")
async def admin_record_detail_route(
    message_id: str,
    _admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"record": admin_record_detail(db, message_id)}


@app.get("/api/admin/tasks/{task_id}/timeline")
async def admin_task_timeline_route(
    task_id: str,
    _admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return admin_task_timeline(db, task_id)
```

- [ ] **Step 5: Run record tests**

Run:

```powershell
python -m pytest server/tests/test_admin_dashboard.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add server/app/admin_service.py server/app/main.py server/tests/test_admin_dashboard.py
git commit -m "feat: add admin record details and task timeline"
```

---

## Task 4: Backend Model Health and Batch Test Results

**Files:**
- Modify: `server/app/db_models.py`
- Modify: `server/app/database.py`
- Modify: `server/app/schemas.py`
- Modify: `server/app/admin_service.py`
- Modify: `server/app/main.py`
- Test: `server/tests/test_admin_backend.py`

- [ ] **Step 1: Write failing model health service test**

Add to `server/tests/test_admin_backend.py`:

```python
def test_admin_model_health_records_latest_result(db_session, admin_user, model_group):
    from app.admin_service import record_model_health_check, get_model_health

    record_model_health_check(
        db_session,
        admin=admin_user,
        model=model_group,
        status="failed",
        duration_ms=3210,
        message="杩炴帴澶辫触",
        raw={"status": 502},
    )

    health = get_model_health(db_session, model_group.id)

    assert health["modelGroupId"] == model_group.id
    assert health["latest"]["status"] == "failed"
    assert health["latest"]["message"] == "杩炴帴澶辫触"
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
python -m pytest server/tests/test_admin_backend.py::test_admin_model_health_records_latest_result -q
```

Expected: FAIL because model health helpers do not exist.

- [ ] **Step 3: Add database model**

Add to `server/app/db_models.py`:

```python
class ModelHealthCheck(Base):
    __tablename__ = "model_health_checks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("mhc"))
    model_group_id: Mapped[str] = mapped_column(String(64), ForeignKey("models.id", ondelete="CASCADE"), index=True)
    sub_model_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    admin_user_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(String(512), default="")
    raw_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
```

- [ ] **Step 4: Add idempotent migration**

In `server/app/database.py`, after existing table upgrade blocks:

```python
if not inspector.has_table("model_health_checks"):
    connection.execute(
        text(
            """
            CREATE TABLE model_health_checks (
                id VARCHAR(64) PRIMARY KEY,
                model_group_id VARCHAR(64) NOT NULL,
                sub_model_id VARCHAR(64) NOT NULL DEFAULT '',
                admin_user_id VARCHAR(64),
                status VARCHAR(32) NOT NULL,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                message VARCHAR(512) NOT NULL DEFAULT '',
                raw_json TEXT,
                created_at DATETIME NOT NULL
            )
            """
        )
    )
    _create_index_if_missing(connection, "ix_model_health_checks_model_group_id", "model_health_checks", "model_group_id")
    _create_index_if_missing(connection, "ix_model_health_checks_created_at", "model_health_checks", "created_at")
```

- [ ] **Step 5: Add health service helpers**

Add to imports in `server/app/admin_service.py`:

```python
ModelHealthCheck,
```

Add functions:

```python
def record_model_health_check(
    db: Session,
    *,
    admin: User,
    model: ModelGroup,
    status: str,
    duration_ms: int,
    message: str = "",
    raw: dict[str, Any] | None = None,
    sub_model_id: str = "",
) -> ModelHealthCheck:
    item = ModelHealthCheck(
        model_group_id=model.id,
        sub_model_id=sub_model_id,
        admin_user_id=admin.id,
        status=status,
        duration_ms=duration_ms,
        message=message[:512],
        raw_json=json_dumps_safe(raw or {}),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    write_admin_log(
        db,
        admin,
        action="model_health_check",
        target_type="model",
        target_id=model.id,
        status="success" if status == "success" else "error",
        summary={"status": status, "durationMs": duration_ms, "message": message[:160]},
    )
    return item


def serialize_model_health_check(item: ModelHealthCheck) -> dict[str, Any]:
    return {
        "id": item.id,
        "modelGroupId": item.model_group_id,
        "subModelId": item.sub_model_id,
        "adminUserId": item.admin_user_id,
        "status": item.status,
        "durationMs": item.duration_ms,
        "message": item.message,
        "raw": parse_json_object(item.raw_json, {}),
        "createdAt": item.created_at,
    }


def get_model_health(db: Session, model_id: str) -> dict[str, Any]:
    checks = (
        db.query(ModelHealthCheck)
        .filter(ModelHealthCheck.model_group_id == model_id)
        .order_by(ModelHealthCheck.created_at.desc())
        .limit(20)
        .all()
    )
    latest = serialize_model_health_check(checks[0]) if checks else None
    total = len(checks)
    failed = len([item for item in checks if item.status != "success"])
    return {
        "modelGroupId": model_id,
        "latest": latest,
        "recent": [serialize_model_health_check(item) for item in checks],
        "failureRate": failed / total if total else 0,
    }
```

- [ ] **Step 6: Add route for model health**

In `server/app/main.py`:

```python
@app.get("/api/admin/models/{model_id}/health")
async def admin_model_health_route(
    model_id: str,
    _admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"health": get_model_health(db, model_id)}
```

- [ ] **Step 7: Run model health test**

Run:

```powershell
python -m pytest server/tests/test_admin_backend.py::test_admin_model_health_records_latest_result -q
```

Expected: PASS.

- [ ] **Step 8: Run backend tests**

Run:

```powershell
python -m pytest server/tests -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add server/app/db_models.py server/app/database.py server/app/schemas.py server/app/admin_service.py server/app/main.py server/tests/test_admin_backend.py
git commit -m "feat: persist admin model health checks"
```

---

## Task 5: Scaffold Independent Admin App

**Files:**
- Create: `admin/package.json`
- Create: `admin/index.html`
- Create: `admin/tsconfig.json`
- Create: `admin/vite.config.ts`
- Create: `admin/src/main.ts`
- Create: `admin/src/App.vue`
- Create: `admin/src/styles/tokens.css`
- Create: `admin/src/styles/global.css`
- Create: `admin/src/types.ts`

- [ ] **Step 1: Create admin package manifest**

Create `admin/package.json`:

```json
{
  "name": "genstudio-admin",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1 --port 5174",
    "build": "vue-tsc -b && vite build",
    "test": "vitest run",
    "preview": "vite preview --host 127.0.0.1 --port 4174"
  },
  "dependencies": {
    "@element-plus/icons-vue": "^2.3.2",
    "@vitejs/plugin-vue": "^6.0.3",
    "echarts": "^6.0.0",
    "element-plus": "^2.11.8",
    "pinia": "^3.0.4",
    "vue": "^3.5.26",
    "vue-router": "^4.6.4"
  },
  "devDependencies": {
    "typescript": "^5.9.3",
    "vite": "^7.3.0",
    "vitest": "^4.1.8",
    "vue-tsc": "^3.1.8"
  }
}
```

- [ ] **Step 2: Create Vite config**

Create `admin/vite.config.ts`:

```ts
import { fileURLToPath, URL } from "node:url";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  base: "/admin/",
  plugins: [vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5174,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
```

- [ ] **Step 3: Create TypeScript config**

Create `admin/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "moduleResolution": "Bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "preserve",
    "strict": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.vue"]
}
```

- [ ] **Step 4: Create HTML and app entry**

Create `admin/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>鍒涙剰宸ュ潑绠＄悊鍚庡彴</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

Create `admin/src/main.ts`:

```ts
import "element-plus/dist/index.css";
import "./styles/tokens.css";
import "./styles/global.css";

import { createPinia } from "pinia";
import { createApp } from "vue";
import App from "./App.vue";
import { router } from "./router";

createApp(App).use(createPinia()).use(router).mount("#app");
```

- [ ] **Step 5: Create minimal app shell**

Create `admin/src/App.vue`:

```vue
<template>
  <router-view />
</template>
```

Create `admin/src/styles/tokens.css`:

```css
:root {
  --admin-bg: #f5f7fb;
  --admin-surface: #ffffff;
  --admin-surface-soft: #f9fbff;
  --admin-border: #dfe6f2;
  --admin-text: #182230;
  --admin-muted: #667085;
  --admin-primary: #2563eb;
  --admin-success: #16a34a;
  --admin-warning: #d97706;
  --admin-danger: #dc2626;
  --admin-radius: 8px;
}

[data-theme="dark"] {
  --admin-bg: #0f172a;
  --admin-surface: #111c31;
  --admin-surface-soft: #16243d;
  --admin-border: #26364f;
  --admin-text: #eef4ff;
  --admin-muted: #9fb0c7;
  --admin-primary: #38bdf8;
}
```

Create `admin/src/styles/global.css`:

```css
* {
  box-sizing: border-box;
}

html,
body,
#app {
  width: 100%;
  height: 100%;
  margin: 0;
}

body {
  font-family: Inter, "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
  color: var(--admin-text);
  background: var(--admin-bg);
}
```

- [ ] **Step 6: Create starter types**

Create `admin/src/types.ts`:

```ts
export type Capability = "text" | "image" | "video";

export interface AdminPermissionBundle {
  role: string;
  permissions: string[];
}

export interface AdminUser {
  id: string;
  email: string;
  phone: string;
  nickname: string;
  avatarUrl: string;
  status: string;
  isAdmin: boolean;
}
```

- [ ] **Step 7: Install dependencies**

Run:

```powershell
cd admin
cmd.exe /c npm install
```

Expected: `admin/package-lock.json` is created and install exits with code 0.

- [ ] **Step 8: Build starter app**

Run:

```powershell
cd admin
cmd.exe /c npm run build
```

Expected: Vite build succeeds and creates `admin/dist`.

- [ ] **Step 9: Commit**

```powershell
git add admin
git commit -m "feat: scaffold independent admin app"
```

---

## Task 6: Admin Auth, API Client, Router, and Layout

**Files:**
- Create: `admin/src/api/http.ts`
- Create: `admin/src/api/admin.ts`
- Create: `admin/src/stores/auth.ts`
- Create: `admin/src/stores/theme.ts`
- Create: `admin/src/router/index.ts`
- Create: `admin/src/layouts/AdminLayout.vue`
- Create: `admin/src/views/ForbiddenView.vue`
- Test: `admin/src/api/admin.test.ts`
- Test: `admin/src/router/guards.test.ts`

- [ ] **Step 1: Write API error parsing tests**

Create `admin/src/api/admin.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { extractApiMessage } from "./http";

describe("admin http helpers", () => {
  it("extracts nested backend messages", () => {
    expect(extractApiMessage({ detail: { message: "褰撳墠璐﹀彿娌℃湁绠＄悊鍛樻潈闄愩€? } })).toBe("褰撳墠璐﹀彿娌℃湁绠＄悊鍛樻潈闄愩€?);
  });

  it("uses a safe generic message for non-json upstream errors", () => {
    expect(extractApiMessage("<html>bad gateway</html>")).toBe("璇锋眰澶辫触锛岃绋嶅悗閲嶈瘯銆?);
  });
});
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
cd admin
cmd.exe /c npm run test -- admin/src/api/admin.test.ts
```

Expected: FAIL because `extractApiMessage` does not exist.

- [ ] **Step 3: Implement HTTP client**

Create `admin/src/api/http.ts`:

```ts
let csrfToken = "";

export class AdminApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "AdminApiError";
  }
}

export function extractApiMessage(payload: unknown): string {
  if (!payload || typeof payload !== "object") return "璇锋眰澶辫触锛岃绋嶅悗閲嶈瘯銆?;
  const record = payload as Record<string, unknown>;
  const detail = record.detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    const message = String((detail as Record<string, unknown>).message || "").trim();
    if (message) return message;
  }
  if (typeof record.message === "string" && record.message.trim()) return record.message.trim();
  return "璇锋眰澶辫触锛岃绋嶅悗閲嶈瘯銆?;
}

export function setAdminCsrfToken(token: string) {
  csrfToken = token;
}

async function parseResponse(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export async function adminRequest<T>(endpoint: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method || "GET").toUpperCase();
  const headers = new Headers(init.headers || {});
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && csrfToken) headers.set("X-CSRF-Token", csrfToken);
  const response = await fetch(endpoint, {
    ...init,
    method,
    headers,
    credentials: "include",
  });
  const payload = await parseResponse(response);
  if (!response.ok) throw new AdminApiError(extractApiMessage(payload), response.status);
  return payload as T;
}
```

- [ ] **Step 4: Implement admin API wrappers**

Create `admin/src/api/admin.ts`:

```ts
import type { AdminPermissionBundle, AdminUser } from "@/types";
import { adminRequest, setAdminCsrfToken } from "./http";

export interface CurrentUserResponse {
  user: AdminUser;
}

export async function fetchCurrentUser(): Promise<AdminUser> {
  const payload = await adminRequest<CurrentUserResponse>("/api/auth/me");
  return payload.user;
}

export async function fetchCsrfToken(): Promise<string> {
  const payload = await adminRequest<{ csrfToken: string }>("/api/auth/csrf");
  setAdminCsrfToken(payload.csrfToken);
  return payload.csrfToken;
}

export async function fetchAdminPermissions(): Promise<AdminPermissionBundle> {
  return adminRequest<AdminPermissionBundle>("/api/admin/permissions/me");
}

export async function logoutAdmin(): Promise<void> {
  await adminRequest<{ ok: boolean }>("/api/auth/logout", { method: "POST", body: "{}" });
  setAdminCsrfToken("");
}
```

- [ ] **Step 5: Implement auth store**

Create `admin/src/stores/auth.ts`:

```ts
import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { fetchAdminPermissions, fetchCsrfToken, fetchCurrentUser, logoutAdmin } from "@/api/admin";
import type { AdminPermissionBundle, AdminUser } from "@/types";

export const useAdminAuthStore = defineStore("admin-auth", () => {
  const loading = ref(false);
  const user = ref<AdminUser | null>(null);
  const permissions = ref<AdminPermissionBundle>({ role: "", permissions: [] });
  const error = ref("");
  const isAdmin = computed(() => Boolean(user.value?.isAdmin));

  function can(permission: string): boolean {
    return permissions.value.permissions.includes(permission);
  }

  async function bootstrap() {
    loading.value = true;
    error.value = "";
    try {
      user.value = await fetchCurrentUser();
      await fetchCsrfToken();
      permissions.value = await fetchAdminPermissions();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "鐧诲綍鐘舵€佽鍙栧け璐ャ€?;
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function logout() {
    await logoutAdmin();
    user.value = null;
    permissions.value = { role: "", permissions: [] };
  }

  return { loading, user, permissions, error, isAdmin, can, bootstrap, logout };
});
```

- [ ] **Step 6: Implement theme store**

Create `admin/src/stores/theme.ts`:

```ts
import { defineStore } from "pinia";
import { ref, watch } from "vue";

export const useAdminThemeStore = defineStore("admin-theme", () => {
  const theme = ref(localStorage.getItem("genstudio-admin-theme") || "light");
  watch(
    theme,
    (value) => {
      document.documentElement.dataset.theme = value;
      localStorage.setItem("genstudio-admin-theme", value);
    },
    { immediate: true },
  );
  function toggleTheme() {
    theme.value = theme.value === "dark" ? "light" : "dark";
  }
  return { theme, toggleTheme };
});
```

- [ ] **Step 7: Implement router guard**

Create `admin/src/router/index.ts`:

```ts
import { createRouter, createWebHistory } from "vue-router";
import { AdminApiError } from "@/api/http";
import AdminLayout from "@/layouts/AdminLayout.vue";
import ForbiddenView from "@/views/ForbiddenView.vue";
import { useAdminAuthStore } from "@/stores/auth";

export const router = createRouter({
  history: createWebHistory("/admin/"),
  routes: [
    {
      path: "/",
      component: AdminLayout,
      children: [
        { path: "", redirect: "/dashboard" },
        { path: "dashboard", component: () => import("@/views/DashboardView.vue"), meta: { permission: "record:view" } },
        { path: "models", component: () => import("@/views/ModelCenterView.vue"), meta: { permission: "model:view" } },
        { path: "prompts", component: () => import("@/views/PromptCenterView.vue"), meta: { permission: "model:view" } },
        { path: "users", component: () => import("@/views/UserCreditsView.vue"), meta: { permission: "user:view" } },
        { path: "records", component: () => import("@/views/RecordsView.vue"), meta: { permission: "record:view" } },
        { path: "audit", component: () => import("@/views/AuditLogsView.vue"), meta: { permission: "audit:view" } },
        { path: "settings", component: () => import("@/views/SystemSettingsView.vue"), meta: { permission: "settings:view" } },
      ],
    },
    { path: "/forbidden", component: ForbiddenView },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAdminAuthStore();
  if (!auth.user) {
    try {
      await auth.bootstrap();
    } catch (error) {
      if (error instanceof AdminApiError && error.status === 401) {
        window.location.href = `/#/auth?redirect=${encodeURIComponent("/admin/")}`;
        return false;
      }
      return "/forbidden";
    }
  }
  if (!auth.isAdmin) return "/forbidden";
  const permission = String(to.meta.permission || "");
  if (permission && !auth.can(permission)) return "/forbidden";
  return true;
});
```

- [ ] **Step 8: Implement admin layout**

Create `admin/src/layouts/AdminLayout.vue`:

```vue
<template>
  <div class="admin-layout">
    <aside class="admin-sidebar">
      <div class="admin-brand">鍒涙剰宸ュ潑鍚庡彴</div>
      <router-link v-for="item in menu" :key="item.path" class="admin-menu-item" :to="item.path">
        <span>{{ item.icon }}</span>
        <strong>{{ item.label }}</strong>
      </router-link>
    </aside>
    <section class="admin-main">
      <header class="admin-topbar">
        <div>
          <strong>{{ currentTitle }}</strong>
          <span>{{ auth.user?.email || auth.user?.nickname }}</span>
        </div>
        <div class="admin-topbar-actions">
          <el-button @click="theme.toggleTheme">{{ theme.theme === "dark" ? "鐧藉ぉ妯″紡" : "澶滈棿妯″紡" }}</el-button>
          <el-button @click="handleLogout">閫€鍑?/el-button>
        </div>
      </header>
      <main class="admin-content">
        <router-view />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { useAdminAuthStore } from "@/stores/auth";
import { useAdminThemeStore } from "@/stores/theme";

const auth = useAdminAuthStore();
const theme = useAdminThemeStore();
const route = useRoute();

const menu = [
  { path: "/dashboard", label: "杩愯惀椹鹃┒鑸?, icon: "馃搳" },
  { path: "/models", label: "妯″瀷涓績", icon: "馃З" },
  { path: "/prompts", label: "鎻愮ず璇嶄腑蹇?, icon: "鉁? },
  { path: "/users", label: "鐢ㄦ埛涓庣Н鍒?, icon: "馃懁" },
  { path: "/records", label: "鍒涗綔璁板綍", icon: "馃梻" },
  { path: "/audit", label: "瀹¤鏃ュ織", icon: "馃洝" },
  { path: "/settings", label: "绯荤粺璁剧疆", icon: "鈿? },
];

const currentTitle = computed(() => menu.find((item) => route.path.startsWith(item.path))?.label || "绠＄悊鍚庡彴");

async function handleLogout() {
  await auth.logout();
  window.location.href = "/";
}
</script>
```

- [ ] **Step 9: Add layout CSS**

Append to `admin/src/styles/global.css`:

```css
.admin-layout {
  display: grid;
  grid-template-columns: 236px minmax(0, 1fr);
  min-height: 100%;
}

.admin-sidebar {
  padding: 18px 14px;
  background: var(--admin-surface);
  border-right: 1px solid var(--admin-border);
}

.admin-brand {
  height: 44px;
  display: flex;
  align-items: center;
  padding: 0 12px;
  font-size: 18px;
  font-weight: 800;
}

.admin-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 42px;
  margin-top: 6px;
  padding: 0 12px;
  color: var(--admin-muted);
  text-decoration: none;
  border-radius: var(--admin-radius);
}

.admin-menu-item.router-link-active {
  color: var(--admin-primary);
  background: rgba(37, 99, 235, 0.1);
}

.admin-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.admin-topbar {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: rgba(255, 255, 255, 0.86);
  border-bottom: 1px solid var(--admin-border);
  backdrop-filter: blur(16px);
}

.admin-content {
  padding: 24px;
}
```

- [ ] **Step 10: Create forbidden view**

Create `admin/src/views/ForbiddenView.vue`:

```vue
<template>
  <main class="admin-forbidden">
    <h1>鏃犳潈璁块棶绠＄悊鍚庡彴</h1>
    <p>褰撳墠璐﹀彿涓嶆槸绠＄悊鍛橈紝鎴栫己灏戣闂椤甸潰鐨勬潈闄愩€?/p>
    <el-button type="primary" @click="goHome">杩斿洖棣栭〉</el-button>
  </main>
</template>

<script setup lang="ts">
function goHome() {
  window.location.href = "/";
}
</script>
```

- [ ] **Step 11: Run admin tests and build**

Run:

```powershell
cd admin
cmd.exe /c npm run test
cmd.exe /c npm run build
```

Expected: tests and build pass.

- [ ] **Step 12: Commit**

```powershell
git add admin
git commit -m "feat: add admin auth layout and routing"
```

---

## Task 7: Admin Dashboard View

**Files:**
- Create: `admin/src/components/AdminMetricCard.vue`
- Create: `admin/src/views/DashboardView.vue`
- Modify: `admin/src/api/admin.ts`
- Modify: `admin/src/types.ts`
- Test: `admin/src/views/dashboard.test.ts`

- [ ] **Step 1: Add dashboard types and API**

Add to `admin/src/types.ts`:

```ts
export interface AdminDashboardTotals {
  totalCalls: number;
  successCalls: number;
  failedCalls: number;
  timeoutCalls: number;
  failureRate: number;
  timeoutRate: number;
  averageDurationMs: number;
  publicModelCalls: number;
  privateModelCalls: number;
}

export interface AdminDashboardMetrics {
  totals: AdminDashboardTotals;
  trends: Record<string, Array<Record<string, number | string>>>;
  capabilityBreakdown: Array<Record<string, number | string>>;
  ownershipBreakdown: Array<Record<string, number | string>>;
  creditSummary: Record<string, number>;
  failedModels: Array<Record<string, number | string>>;
  slowModels: Array<Record<string, number | string>>;
  activeUsers: Array<Record<string, number | string>>;
}
```

Add to `admin/src/api/admin.ts`:

```ts
import type { AdminDashboardMetrics } from "@/types";

export async function fetchDashboardMetrics(range = "30d"): Promise<AdminDashboardMetrics> {
  return adminRequest<AdminDashboardMetrics>(`/api/admin/dashboard/metrics?range=${encodeURIComponent(range)}`);
}
```

- [ ] **Step 2: Create metric card**

Create `admin/src/components/AdminMetricCard.vue`:

```vue
<template>
  <article class="admin-metric-card">
    <span>{{ label }}</span>
    <strong>{{ value }}</strong>
    <small>{{ hint }}</small>
  </article>
</template>

<script setup lang="ts">
defineProps<{ label: string; value: string | number; hint?: string }>();
</script>
```

- [ ] **Step 3: Create dashboard view**

Create `admin/src/views/DashboardView.vue`:

```vue
<template>
  <section class="admin-page">
    <div class="admin-page-head">
      <div>
        <h1>杩愯惀椹鹃┒鑸?/h1>
        <p>鏌ョ湅璋冪敤銆佸け璐ャ€佺Н鍒嗐€佹ā鍨嬪仴搴峰拰鐢ㄦ埛娲昏穬銆?/p>
      </div>
      <el-segmented v-model="range" :options="rangeOptions" @change="load" />
    </div>

    <div class="admin-metric-grid">
      <AdminMetricCard label="鎬昏皟鐢? :value="metrics?.totals.totalCalls || 0" hint="褰撳墠鍛ㄦ湡鍐呭叏閮ㄨ皟鐢? />
      <AdminMetricCard label="澶辫触鐜? :value="percent(metrics?.totals.failureRate)" hint="澶辫触璋冪敤 / 鎬昏皟鐢? />
      <AdminMetricCard label="瓒呮椂鐜? :value="percent(metrics?.totals.timeoutRate)" hint="瓒呮椂浠诲姟鍗犳瘮" />
      <AdminMetricCard label="骞冲潎鑰楁椂" :value="duration(metrics?.totals.averageDurationMs)" hint="鍏ㄩ儴妯″瀷骞冲潎鍝嶅簲" />
    </div>

    <div class="admin-dashboard-grid">
      <el-card>
        <template #header>鏃ヨ秼鍔?/template>
        <div ref="trendEl" class="admin-chart"></div>
      </el-card>
      <el-card>
        <template #header>绉垎姒傝</template>
        <div class="admin-credit-list">
          <span>棰勬墸 {{ metrics?.creditSummary.reserved || 0 }}</span>
          <span>娑堣垂 {{ metrics?.creditSummary.spent || 0 }}</span>
          <span>閫€娆?{{ metrics?.creditSummary.refunded || 0 }}</span>
          <span>浜哄伐璋冩暣 {{ metrics?.creditSummary.adminAdjusted || 0 }}</span>
        </div>
      </el-card>
      <el-card>
        <template #header>澶辫触妯″瀷</template>
        <el-table :data="metrics?.failedModels || []" size="small">
          <el-table-column prop="modelName" label="妯″瀷" />
          <el-table-column prop="failedCalls" label="澶辫触" width="90" />
          <el-table-column prop="failureRate" label="澶辫触鐜? width="110">
            <template #default="{ row }">{{ percent(row.failureRate) }}</template>
          </el-table-column>
        </el-table>
      </el-card>
      <el-card>
        <template #header>娲昏穬鐢ㄦ埛</template>
        <el-table :data="metrics?.activeUsers || []" size="small">
          <el-table-column prop="label" label="鐢ㄦ埛" />
          <el-table-column prop="totalCalls" label="璋冪敤" width="90" />
        </el-table>
      </el-card>
    </div>
  </section>
</template>

<script setup lang="ts">
import * as echarts from "echarts";
import { nextTick, onMounted, ref } from "vue";
import { fetchDashboardMetrics } from "@/api/admin";
import AdminMetricCard from "@/components/AdminMetricCard.vue";
import type { AdminDashboardMetrics } from "@/types";

const range = ref("30d");
const rangeOptions = ["7d", "30d", "90d"];
const metrics = ref<AdminDashboardMetrics | null>(null);
const trendEl = ref<HTMLDivElement | null>(null);

function percent(value: unknown): string {
  const number = typeof value === "number" ? value : 0;
  return `${(number * 100).toFixed(1)}%`;
}

function duration(value: unknown): string {
  const number = typeof value === "number" ? value : 0;
  return number >= 1000 ? `${(number / 1000).toFixed(1)}s` : `${number}ms`;
}

function renderTrend() {
  if (!trendEl.value || !metrics.value) return;
  const rows = metrics.value.trends.day || [];
  const chart = echarts.init(trendEl.value);
  chart.setOption({
    tooltip: { trigger: "axis" },
    grid: { left: 36, right: 16, top: 24, bottom: 28 },
    xAxis: { type: "category", data: rows.map((row) => row.label) },
    yAxis: { type: "value" },
    series: [
      { name: "鎴愬姛", type: "line", smooth: true, data: rows.map((row) => row.successCalls) },
      { name: "澶辫触", type: "line", smooth: true, data: rows.map((row) => row.failedCalls) },
    ],
  });
}

async function load() {
  metrics.value = await fetchDashboardMetrics(range.value);
  await nextTick();
  renderTrend();
}

onMounted(load);
</script>
```

- [ ] **Step 4: Add dashboard styles**

Append to `admin/src/styles/global.css`:

```css
.admin-page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.admin-page-head h1 {
  margin: 0;
  font-size: 24px;
}

.admin-page-head p {
  margin: 6px 0 0;
  color: var(--admin-muted);
}

.admin-metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.admin-metric-card {
  padding: 18px;
  background: var(--admin-surface);
  border: 1px solid var(--admin-border);
  border-radius: var(--admin-radius);
}

.admin-metric-card span,
.admin-metric-card small {
  color: var(--admin-muted);
}

.admin-metric-card strong {
  display: block;
  margin: 8px 0;
  font-size: 28px;
}

.admin-dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
  gap: 16px;
}

.admin-chart {
  height: 300px;
}

.admin-credit-list {
  display: grid;
  gap: 12px;
}
```

- [ ] **Step 5: Build and inspect dashboard**

Run:

```powershell
cd admin
cmd.exe /c npm run build
```

Expected: build passes.

- [ ] **Step 6: Commit**

```powershell
git add admin/src
git commit -m "feat: build admin dashboard view"
```

---

## Task 8: Admin Model Center

**Files:**
- Create: `admin/src/views/ModelCenterView.vue`
- Modify: `admin/src/api/admin.ts`
- Modify: `admin/src/types.ts`
- Modify: `server/app/main.py`
- Test: existing admin build and backend tests

- [ ] **Step 1: Add model types and API functions**

Add to `admin/src/types.ts`:

```ts
export interface AdminModel {
  id: string;
  name: string;
  vendor: string;
  capability: Capability;
  adapter: string;
  description: string;
  baseUrl: string;
  primaryModelName: string;
  isPublic: boolean;
  canEdit: boolean;
  publicDisplayName: string;
  publicDescription: string;
  inputHint: string;
  iconUrl: string;
  publicTags: string[];
  promptOptimizeEnabled: boolean;
  defaultParameters: Record<string, unknown>;
  creditPrice: number;
  creditPriceSource: string;
}
```

Add to `admin/src/api/admin.ts`:

```ts
import type { AdminModel, Capability } from "@/types";

export async function fetchAdminModels(query: { capability?: Capability | "all"; search?: string; publicState?: string } = {}) {
  const params = new URLSearchParams();
  if (query.capability) params.set("capability", query.capability);
  if (query.search) params.set("search", query.search);
  if (query.publicState) params.set("publicState", query.publicState);
  const suffix = params.toString() ? `?${params}` : "";
  const payload = await adminRequest<{ models: AdminModel[] }>(`/api/admin/models${suffix}`);
  return payload.models;
}

export async function updateAdminModel(modelId: string, body: Partial<AdminModel>) {
  const payload = await adminRequest<{ model: AdminModel }>(`/api/admin/models/${modelId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
  return payload.model;
}

export async function publishAdminModel(modelId: string) {
  const payload = await adminRequest<{ model: AdminModel }>(`/api/admin/models/${modelId}/publish`, {
    method: "POST",
    body: "{}",
  });
  return payload.model;
}

export async function unpublishAdminModel(modelId: string) {
  const payload = await adminRequest<{ model: AdminModel }>(`/api/admin/models/${modelId}/unpublish`, {
    method: "POST",
    body: "{}",
  });
  return payload.model;
}

export async function updateModelCreditPricing(modelId: string, body: { price?: number; useDefault?: boolean }) {
  const payload = await adminRequest<{ model: AdminModel }>(`/api/admin/models/${modelId}/credit-pricing`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
  return payload.model;
}
```

- [ ] **Step 2: Create model center view**

Create `admin/src/views/ModelCenterView.vue` with a search panel, table, right drawer, and batch operation toolbar:

```vue
<template>
  <section class="admin-page">
    <div class="admin-page-head">
      <div>
        <h1>妯″瀷涓績</h1>
        <p>绠＄悊鍏敤妯″瀷銆佺鏈夋ā鍨嬪彲瑙佹€с€侀粯璁ゅ弬鏁板拰绉垎鎵ｉ櫎銆?/p>
      </div>
      <el-button type="primary" :disabled="!selected.length" @click="batchPublish(true)">鎵归噺鍏敤</el-button>
    </div>

    <el-card class="admin-search-card">
      <el-form :inline="true">
        <el-form-item label="绫诲瀷">
          <el-select v-model="filters.capability" style="width: 140px" @change="load">
            <el-option label="鍏ㄩ儴" value="all" />
            <el-option label="鏂囨" value="text" />
            <el-option label="鍥剧墖" value="image" />
            <el-option label="瑙嗛" value="video" />
          </el-select>
        </el-form-item>
        <el-form-item label="鍏敤鐘舵€?>
          <el-select v-model="filters.publicState" style="width: 140px" @change="load">
            <el-option label="鍏ㄩ儴" value="all" />
            <el-option label="鍏敤" value="public" />
            <el-option label="绉佹湁" value="private" />
          </el-select>
        </el-form-item>
        <el-form-item label="鎼滅储">
          <el-input v-model="filters.search" placeholder="妯″瀷鍚?/ 渚涘簲鍟? clearable @keyup.enter="load" />
        </el-form-item>
        <el-form-item>
          <el-button @click="load">鏌ヨ</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <el-table :data="models" @selection-change="selected = $event" row-key="id">
        <el-table-column type="selection" width="44" />
        <el-table-column label="妯″瀷" min-width="240">
          <template #default="{ row }">
            <div class="admin-model-cell">
              <img v-if="row.iconUrl" :src="row.iconUrl" alt="" />
              <div>
                <strong>{{ row.publicDisplayName || row.name }}</strong>
                <span>{{ row.primaryModelName }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="capability" label="绫诲瀷" width="90" />
        <el-table-column prop="vendor" label="渚涘簲鍟? width="140" />
        <el-table-column label="鍏敤" width="90">
          <template #default="{ row }">
            <el-tag :type="row.isPublic ? 'success' : 'info'">{{ row.isPublic ? "鍏敤" : "绉佹湁" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="绉垎" width="90">
          <template #default="{ row }">{{ row.creditPrice }}</template>
        </el-table-column>
        <el-table-column label="鎿嶄綔" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openDrawer(row)">璇︽儏</el-button>
            <el-dropdown>
              <el-button size="small">鎿嶄綔</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="togglePublic(row)">{{ row.isPublic ? "鍙栨秷鍏敤" : "璁句负鍏敤" }}</el-dropdown-item>
                  <el-dropdown-item @click="openDrawer(row)">缂栬緫鍙傛暟</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="drawerOpen" title="妯″瀷璇︽儏" size="520px">
      <el-form v-if="draft" label-position="top">
        <el-form-item label="鍏敤灞曠ず鍚?><el-input v-model="draft.publicDisplayName" /></el-form-item>
        <el-form-item label="鎻忚堪"><el-input v-model="draft.publicDescription" type="textarea" /></el-form-item>
        <el-form-item label="榛樿鎻愮ず璇?><el-input v-model="draft.inputHint" type="textarea" /></el-form-item>
        <el-form-item label="鍥炬爣 URL"><el-input v-model="draft.iconUrl" /></el-form-item>
        <el-form-item label="绉垎浠锋牸"><el-input-number v-model="creditPrice" :min="0" /></el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveDraft">淇濆瓨</el-button>
        </el-form-item>
      </el-form>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { fetchAdminModels, publishAdminModel, unpublishAdminModel, updateAdminModel, updateModelCreditPricing } from "@/api/admin";
import type { AdminModel, Capability } from "@/types";

const filters = reactive<{ capability: Capability | "all"; search: string; publicState: string }>({ capability: "all", search: "", publicState: "all" });
const models = ref<AdminModel[]>([]);
const selected = ref<AdminModel[]>([]);
const drawerOpen = ref(false);
const draft = ref<AdminModel | null>(null);
const creditPrice = ref(0);

async function load() {
  models.value = await fetchAdminModels(filters);
}

function openDrawer(row: AdminModel) {
  draft.value = { ...row, publicTags: [...row.publicTags], defaultParameters: { ...row.defaultParameters } };
  creditPrice.value = row.creditPrice;
  drawerOpen.value = true;
}

async function saveDraft() {
  if (!draft.value) return;
  const updated = await updateAdminModel(draft.value.id, draft.value);
  await updateModelCreditPricing(draft.value.id, { price: creditPrice.value });
  const index = models.value.findIndex((item) => item.id === updated.id);
  if (index >= 0) models.value[index] = updated;
  drawerOpen.value = false;
  await load();
}

async function togglePublic(row: AdminModel) {
  row.isPublic ? await unpublishAdminModel(row.id) : await publishAdminModel(row.id);
  await load();
}

async function batchPublish(isPublic: boolean) {
  for (const model of selected.value) {
    if (isPublic && !model.isPublic) await publishAdminModel(model.id);
    if (!isPublic && model.isPublic) await unpublishAdminModel(model.id);
  }
  await load();
}

onMounted(load);
</script>
```

- [ ] **Step 3: Build admin app**

Run:

```powershell
cd admin
cmd.exe /c npm run build
```

Expected: PASS.

- [ ] **Step 4: Run backend admin tests**

Run:

```powershell
python -m pytest server/tests/test_admin_backend.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add admin/src server/app/main.py
git commit -m "feat: build admin model center"
```

---

## Task 9: Admin Users and Credits

**Files:**
- Create: `admin/src/views/UserCreditsView.vue`
- Modify: `admin/src/api/admin.ts`
- Modify: `admin/src/types.ts`
- Backend tests: existing credit/admin tests

- [ ] **Step 1: Add user and credit types**

Add to `admin/src/types.ts`:

```ts
export interface CreditAccount {
  id: string;
  userId: string;
  balance: number;
  reservedBalance: number;
  totalRecharged: number;
  totalSpent: number;
  totalRefunded: number;
}

export interface AdminUserWithCredits extends AdminUser {
  credits: CreditAccount | null;
}
```

- [ ] **Step 2: Add API functions**

Add to `admin/src/api/admin.ts`:

```ts
import type { AdminUserWithCredits } from "@/types";

export async function fetchAdminUsers(search = "") {
  const suffix = search ? `?search=${encodeURIComponent(search)}` : "";
  const payload = await adminRequest<{ users: AdminUserWithCredits[] }>(`/api/admin/users${suffix}`);
  return payload.users;
}

export async function updateAdminUser(userId: string, body: Partial<AdminUserWithCredits>) {
  const payload = await adminRequest<{ user: AdminUserWithCredits }>(`/api/admin/users/${userId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
  return payload.user;
}

export async function setAdminUserStatus(userId: string, action: "enable" | "disable" | "delete" | "restore") {
  const payload = await adminRequest<{ user: AdminUserWithCredits }>(`/api/admin/users/${userId}/${action}`, {
    method: "POST",
    body: "{}",
  });
  return payload.user;
}

export async function adjustUserCredits(userId: string, amount: number, reason: string) {
  return adminRequest(`/api/admin/users/${userId}/credits/adjust`, {
    method: "POST",
    body: JSON.stringify({ amount, reason }),
  });
}
```

- [ ] **Step 3: Create user credits view**

Create `admin/src/views/UserCreditsView.vue` with user table, role/status filters, detail drawer, and credit adjustment form:

```vue
<template>
  <section class="admin-page">
    <div class="admin-page-head">
      <div>
        <h1>鐢ㄦ埛涓庣Н鍒?/h1>
        <p>绠＄悊鐢ㄦ埛鐘舵€併€佹煡鐪嬬Н鍒嗕綑棰濄€佹墽琛屽厖鍊兼垨鎵ｅ噺銆?/p>
      </div>
    </div>
    <el-card class="admin-search-card">
      <el-form :inline="true">
        <el-form-item label="鎼滅储"><el-input v-model="search" placeholder="閭 / 鏄电О / 鎵嬫満" clearable @keyup.enter="load" /></el-form-item>
        <el-form-item label="瑙掕壊">
          <el-select v-model="roleFilter" style="width: 130px">
            <el-option label="鍏ㄩ儴" value="all" />
            <el-option label="绠＄悊鍛? value="admin" />
            <el-option label="鏅€氱敤鎴? value="user" />
          </el-select>
        </el-form-item>
        <el-form-item><el-button @click="load">鏌ヨ</el-button></el-form-item>
      </el-form>
    </el-card>
    <el-card>
      <el-table :data="filteredUsers" row-key="id">
        <el-table-column prop="email" label="閭" min-width="220" />
        <el-table-column prop="nickname" label="鏄电О" width="160" />
        <el-table-column prop="status" label="鐘舵€? width="100" />
        <el-table-column label="瑙掕壊" width="110">
          <template #default="{ row }"><el-tag :type="row.isAdmin ? 'warning' : 'info'">{{ row.isAdmin ? "绠＄悊鍛? : "鐢ㄦ埛" }}</el-tag></template>
        </el-table-column>
        <el-table-column label="绉垎" width="120">
          <template #default="{ row }">{{ row.credits?.balance || 0 }}</template>
        </el-table-column>
        <el-table-column label="鎿嶄綔" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openDrawer(row)">璇︽儏</el-button>
            <el-dropdown>
              <el-button size="small">鎿嶄綔</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="changeStatus(row, row.status === 'active' ? 'disable' : 'enable')">
                    {{ row.status === "active" ? "绂佺敤" : "鍚敤" }}
                  </el-dropdown-item>
                  <el-dropdown-item @click="changeStatus(row, 'delete')">鍒犻櫎</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    <el-drawer v-model="drawerOpen" title="鐢ㄦ埛璇︽儏" size="520px">
      <template v-if="selectedUser">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="閭">{{ selectedUser.email }}</el-descriptions-item>
          <el-descriptions-item label="鏄电О">{{ selectedUser.nickname }}</el-descriptions-item>
          <el-descriptions-item label="浣欓">{{ selectedUser.credits?.balance || 0 }}</el-descriptions-item>
          <el-descriptions-item label="鍐荤粨">{{ selectedUser.credits?.reservedBalance || 0 }}</el-descriptions-item>
        </el-descriptions>
        <el-divider />
        <el-form label-position="top">
          <el-form-item label="璋冩暣绉垎"><el-input-number v-model="adjustAmount" /></el-form-item>
          <el-form-item label="鍘熷洜"><el-input v-model="adjustReason" type="textarea" /></el-form-item>
          <el-button type="primary" @click="adjustCredits">鎻愪氦璋冩暣</el-button>
        </el-form>
      </template>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { adjustUserCredits, fetchAdminUsers, setAdminUserStatus } from "@/api/admin";
import type { AdminUserWithCredits } from "@/types";

const users = ref<AdminUserWithCredits[]>([]);
const search = ref("");
const roleFilter = ref("all");
const drawerOpen = ref(false);
const selectedUser = ref<AdminUserWithCredits | null>(null);
const adjustAmount = ref(0);
const adjustReason = ref("");

const filteredUsers = computed(() =>
  users.value.filter((user) => {
    if (roleFilter.value === "admin") return user.isAdmin;
    if (roleFilter.value === "user") return !user.isAdmin;
    return true;
  }),
);

async function load() {
  users.value = await fetchAdminUsers(search.value);
}

function openDrawer(user: AdminUserWithCredits) {
  selectedUser.value = user;
  drawerOpen.value = true;
}

async function changeStatus(user: AdminUserWithCredits, action: "enable" | "disable" | "delete" | "restore") {
  await ElMessageBox.confirm(`纭${action}璇ョ敤鎴凤紵`, "纭鎿嶄綔", { type: "warning" });
  await setAdminUserStatus(user.id, action);
  await load();
}

async function adjustCredits() {
  if (!selectedUser.value) return;
  await adjustUserCredits(selectedUser.value.id, adjustAmount.value, adjustReason.value);
  adjustAmount.value = 0;
  adjustReason.value = "";
  await load();
}

onMounted(load);
</script>
```

- [ ] **Step 4: Build and test**

Run:

```powershell
cd admin
cmd.exe /c npm run build
cd ..
python -m pytest server/tests/test_credit_service.py server/tests/test_admin_backend.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add admin/src
git commit -m "feat: build admin users and credits"
```

---

## Task 10: Prompt Center, Records Center, Audit, and Settings Views

**Files:**
- Create: `admin/src/views/PromptCenterView.vue`
- Create: `admin/src/views/RecordsView.vue`
- Create: `admin/src/views/AuditLogsView.vue`
- Create: `admin/src/views/SystemSettingsView.vue`
- Modify: `admin/src/api/admin.ts`
- Modify: `admin/src/types.ts`

- [ ] **Step 1: Add prompt, record, and audit API functions**

Add to `admin/src/types.ts`:

```ts
export interface PromptTemplate {
  id: string;
  capability: Capability;
  modelGroupId: string;
  templateType: string;
  name: string;
  content: string;
  enabled: boolean;
}

export interface AdminCreationRecord {
  id: string;
  user: AdminUserWithCredits | null;
  modelName: string;
  capability: Capability;
  status: string;
  prompt: string;
  response: string;
  taskId: string;
  errorMessage: string;
  assets: Array<{ type: string; url: string; thumbnailUrl?: string }>;
}

export interface AdminAuditLog {
  id: string;
  adminUserId: string | null;
  action: string;
  targetType: string;
  targetId: string;
  status: string;
  riskLevel?: string;
  summary: Record<string, unknown>;
  createdAt: string;
}
```

Add to `admin/src/api/admin.ts`:

```ts
import type { AdminAuditLog, AdminCreationRecord, PromptTemplate } from "@/types";

export async function fetchPromptTemplates(capability = "all") {
  const payload = await adminRequest<{ templates: PromptTemplate[] }>(`/api/admin/prompt-templates?capability=${encodeURIComponent(capability)}`);
  return payload.templates;
}

export async function savePromptTemplate(templateId: string, body: Partial<PromptTemplate>) {
  const payload = await adminRequest<{ template: PromptTemplate }>(`/api/admin/prompt-templates/${templateId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
  return payload.template;
}

export async function fetchAdminRecords(capability: Capability, query: Record<string, string> = {}) {
  const params = new URLSearchParams(query);
  const suffix = params.toString() ? `?${params}` : "";
  const payload = await adminRequest<{ records: AdminCreationRecord[] }>(`/api/admin/records/${capability}${suffix}`);
  return payload.records;
}

export async function fetchAuditLogs(query: Record<string, string> = {}) {
  const params = new URLSearchParams(query);
  const suffix = params.toString() ? `?${params}` : "";
  const payload = await adminRequest<{ logs: AdminAuditLog[] }>(`/api/admin/audit-logs${suffix}`);
  return payload.logs;
}
```

- [ ] **Step 2: Implement each view with table plus drawer**

Create the four views using the same pattern:

```vue
<template>
  <section class="admin-page">
    <div class="admin-page-head">
      <div>
        <h1>{{ title }}</h1>
        <p>{{ subtitle }}</p>
      </div>
    </div>
    <el-card class="admin-search-card">
      <slot name="filters" />
    </el-card>
    <el-card>
      <slot name="table" />
    </el-card>
  </section>
</template>
```

For `RecordsView.vue`, do not use the slot shell above; implement explicit tabs:

```vue
<template>
  <section class="admin-page">
    <div class="admin-page-head">
      <div>
        <h1>鍒涗綔璁板綍</h1>
        <p>鏌ョ湅鏂囨銆佸浘鐗囥€佽棰戠殑璇锋眰銆佸搷搴斻€佽祫浜у拰浠诲姟鐘舵€併€?/p>
      </div>
    </div>
    <el-tabs v-model="capability" @tab-change="load">
      <el-tab-pane label="鏂囨" name="text" />
      <el-tab-pane label="鍥剧墖" name="image" />
      <el-tab-pane label="瑙嗛" name="video" />
    </el-tabs>
    <el-card>
      <el-table :data="records">
        <el-table-column prop="prompt" label="璇锋眰" min-width="260" show-overflow-tooltip />
        <el-table-column prop="response" label="鍝嶅簲" min-width="260" show-overflow-tooltip />
        <el-table-column prop="status" label="鐘舵€? width="100" />
        <el-table-column label="绱犳潗" width="120">
          <template #default="{ row }">{{ row.assets.length }}</template>
        </el-table-column>
        <el-table-column label="鎿嶄綔" width="120">
          <template #default="{ row }"><el-button size="small" @click="selected = row">璇︽儏</el-button></template>
        </el-table-column>
      </el-table>
    </el-card>
    <el-drawer v-model="detailOpen" title="璁板綍璇︽儏" size="640px">
      <pre>{{ selected }}</pre>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { fetchAdminRecords } from "@/api/admin";
import type { AdminCreationRecord, Capability } from "@/types";

const capability = ref<Capability>("text");
const records = ref<AdminCreationRecord[]>([]);
const selected = ref<AdminCreationRecord | null>(null);
const detailOpen = computed({
  get: () => Boolean(selected.value),
  set: (value) => {
    if (!value) selected.value = null;
  },
});

async function load() {
  records.value = await fetchAdminRecords(capability.value);
}

watch(capability, load);
onMounted(load);
</script>
```

- [ ] **Step 3: Build admin app**

Run:

```powershell
cd admin
cmd.exe /c npm run build
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add admin/src
git commit -m "feat: add admin records prompts audit settings"
```

---

## Task 11: Remove Embedded Admin from Creative Frontend

**Files:**
- Modify: `fronted/src/App.vue`
- Modify: `fronted/src/api.ts`
- Modify: `fronted/src/types.ts`
- Modify: `fronted/src/styles.css`
- Delete: `fronted/src/adminPresentation.ts`
- Delete or modify: `fronted/src/adminPresentation.test.ts`
- Modify: `fronted/src/api.test.ts`
- Modify: `fronted/src/styleApplication.test.ts`

- [ ] **Step 1: Add a regression test that the old admin route is absent**

Modify `fronted/src/styleApplication.test.ts` or add a new test:

```ts
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const appSource = readFileSync(new URL("./App.vue", import.meta.url), "utf8");
const styles = readFileSync(new URL("./styles.css", import.meta.url), "utf8");

describe("embedded admin removal", () => {
  it("does not keep the old embedded admin shell", () => {
    expect(appSource).not.toContain('"admin"');
    expect(appSource).not.toContain("shell-admin");
    expect(styles).not.toContain(".shell-admin");
  });
});
```

- [ ] **Step 2: Run frontend tests and verify failure**

Run:

```powershell
cd fronted
cmd.exe /c npm run test -- src/styleApplication.test.ts
```

Expected: FAIL because the old admin code still exists.

- [ ] **Step 3: Remove admin imports and view union**

In `fronted/src/App.vue`:

- Remove import from `./adminPresentation`.
- Change:

```ts
type ViewName = "auth" | "auth-error" | "text" | "images" | "videos" | "settings" | "profile" | "admin";
```

to:

```ts
type ViewName = "auth" | "auth-error" | "text" | "images" | "videos" | "settings" | "profile";
```

- Remove `"admin"` from route parsing:

```ts
if (route === "auth" || route === "auth-error" || route === "images" || route === "videos" || route === "settings" || route === "profile" || route === "text") {
  return route;
}
```

- [ ] **Step 4: Remove admin state/functions/template sections**

In `fronted/src/App.vue`, remove:

- `adminState`
- `adminActiveTab` and all `admin*` computed values.
- `loadAdmin*`, `saveAdmin*`, `switchAdminTab`, `openAdmin*`, `exportAdmin*` functions.
- The template branch that renders the old admin page.
- Any topbar or sidebar link that navigates to `admin`.

Keep:

- Settings page for ordinary model management.
- Profile page.
- Public model display.
- Credit display.
- Auth redirect handling.

- [ ] **Step 5: Move or remove admin-only API helpers**

In `fronted/src/api.ts`, remove admin-only exports:

- `fetchAdminOverview`
- `fetchAdminOverviewUsers`
- `fetchAdminOverviewModels`
- `fetchAdminModels`
- `updateAdminModel`
- `publishAdminModel`
- `unpublishAdminModel`
- `fetchAdminPromptTemplates`
- `saveAdminPromptTemplate`
- `testAdminPromptTemplate`
- `fetchAdminUsers`
- `updateAdminUser`
- `enableAdminUser`
- `disableAdminUser`
- `deleteAdminUser`
- `restoreAdminUser`
- `fetchAdminRecords`
- `fetchAdminAuditLogs`
- admin credit settings and user credit adjustment helpers

Do not remove user-facing credit helpers:

- `fetchMyCredits`
- `fetchCreditPricingEstimate`

- [ ] **Step 6: Move or remove admin-only types**

In `fronted/src/types.ts`, remove types that now live in `admin/src/types.ts`:

- `AdminOverview`
- `AdminOverviewUserRow`
- `AdminOverviewModelRow`
- `AdminUserDefinition`
- `AdminCreationRecord`
- `AdminAuditLog`
- `PromptTemplateDefinition` if no longer used by user-facing prompt optimize code.

Keep shared user-facing model, conversation, asset, catalog, and credit types.

- [ ] **Step 7: Remove old admin CSS**

In `fronted/src/styles.css`, remove blocks that target:

- `.shell-admin`
- `.admin-sidebar`
- `.admin-record-*`
- `.admin-model-*`
- `.admin-user-*`
- `.admin-credit-settings`
- `.admin-action-drawer`
- `.admin-btn`

Keep `.shell:not(.shell-admin)` blocks by converting them to `.shell` where they are still needed for the creative workspace.

- [ ] **Step 8: Delete old presentation metadata**

Delete:

```powershell
git rm fronted/src/adminPresentation.ts fronted/src/adminPresentation.test.ts
```

- [ ] **Step 9: Run frontend tests**

Run:

```powershell
cd fronted
cmd.exe /c npm run test
cmd.exe /c npm run build
```

Expected: tests and build pass.

- [ ] **Step 10: Commit**

```powershell
git add fronted/src/App.vue fronted/src/api.ts fronted/src/types.ts fronted/src/styles.css fronted/src/api.test.ts fronted/src/styleApplication.test.ts
git add -u fronted/src/adminPresentation.ts fronted/src/adminPresentation.test.ts
git commit -m "refactor: remove embedded admin console"
```

---

## Task 12: Deployment for `/admin/`

**Files:**
- Modify: `docker-compose.yml`
- Create or modify: `deploy/nginx.conf`
- Modify: project deployment documentation file if present

- [ ] **Step 1: Add admin build command to deployment notes**

Document local build sequence:

```powershell
cd fronted
cmd.exe /c npm run build
cd ..\admin
cmd.exe /c npm run build
cd ..
```

- [ ] **Step 2: Add Nginx routing**

Create or update `deploy/nginx.conf`:

```nginx
server {
    listen 80;
    server_name studio.cylonai.cn;

    root /usr/share/nginx/html/fronted;
    index index.html;

    location /api/ {
        proxy_pass http://server:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /admin/ {
        alias /usr/share/nginx/html/admin/;
        try_files $uri $uri/ /admin/index.html;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 3: Adjust Docker build or release packaging**

If the current Docker image copies only `fronted/dist`, change it to copy both:

```dockerfile
COPY fronted/dist/ /usr/share/nginx/html/fronted/
COPY admin/dist/ /usr/share/nginx/html/admin/
```

If the project uses a shell deploy process instead of Dockerfile, update that process to upload both dist folders.

- [ ] **Step 4: Verify local preview**

Run both previews:

```powershell
cd fronted
cmd.exe /c npm run preview -- --port 4173
cd ..\admin
cmd.exe /c npm run preview -- --port 4174
```

Expected:

- Main app opens at `http://127.0.0.1:4173/`.
- Admin app opens at `http://127.0.0.1:4174/admin/` or Vite preview equivalent.

- [ ] **Step 5: Commit**

```powershell
git add docker-compose.yml deploy/nginx.conf README.md
git commit -m "chore: route independent admin app"
```

---

## Task 13: Full Verification

**Files:**
- No source changes unless a verification failure requires a fix.

- [ ] **Step 1: Run backend test suite**

Run:

```powershell
python -m pytest server/tests -q
```

Expected: all tests pass.

- [ ] **Step 2: Run creative frontend tests and build**

Run:

```powershell
cd fronted
cmd.exe /c npm run test
cmd.exe /c npm run build
```

Expected: tests and build pass.

- [ ] **Step 3: Run admin tests and build**

Run:

```powershell
cd admin
cmd.exe /c npm run test
cmd.exe /c npm run build
```

Expected: tests and build pass.

- [ ] **Step 4: Start local backend and frontends**

Use the repo's established local startup commands. If no process is running:

```powershell
python -m uvicorn app.main:app --app-dir server --host 127.0.0.1 --port 8000
cd fronted
cmd.exe /c npm run dev -- --port 5175
cd ..\admin
cmd.exe /c npm run dev -- --port 5174
```

Expected:

- Backend health: `http://127.0.0.1:8000/api/health`.
- Creative workspace: `http://127.0.0.1:5175/`.
- Admin console: `http://127.0.0.1:5174/admin/`.

- [ ] **Step 5: Browser verification**

Use Browser plugin to verify:

- Unauthenticated `/admin/` redirects to login.
- Admin user can open dashboard.
- Model center loads and public/private tags are visible.
- Users and credits page loads.
- Prompt center loads.
- Records page loads text/image/video tabs.
- Audit logs load.
- Creative workspace still opens text/image/video pages.
- Old `/#/admin` no longer renders old admin.

- [ ] **Step 6: Commit verification fixes**

If fixes were required:

```powershell
git add <fixed-files>
git commit -m "fix: stabilize independent admin console"
```

If no fixes were required, do not create an empty commit.

---

## Self-Review

- Spec coverage: The plan covers backend permission foundation, dashboard metrics, record detail, task timeline, model health, independent `admin/` app, shared auth, all main admin pages, old embedded admin removal, deployment routing, and verification.
- Existing functionality preservation: User-facing auth, creative generation, conversations, assets, public/private models, catalog, credits, and polling are explicitly preserved.
- Placeholder scan: The plan avoids unresolved markers and vague implementation instructions.
- Type consistency: Admin frontend types are introduced before API wrappers and views consume them. Backend service functions are introduced before routes consume them.
- Scope control: The plan does not migrate the creative workspace and does not replace backend generation services.
