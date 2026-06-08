# Admin Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a separate administrator backend for GenStudio with public model governance, prompt-template management, user management, operational statistics, creation records, and audit logs while preserving the current normal user settings page.

**Architecture:** Add focused backend admin services and schemas behind `/api/admin/*`, guarded by a single admin dependency. Extend existing model, user, call log, and conversation data instead of creating a parallel record system. Add a dedicated `#/admin` frontend view with tabbed admin state, leaving `#/settings` as the normal user model configuration surface.

**Tech Stack:** FastAPI, SQLAlchemy, MySQL/SQLite test database, Pydantic, Vue 3 Composition API, Pinia, Vitest, pytest.

---

## File Structure

Backend:

- Modify `server/app/db_models.py`: add admin metadata fields to `ModelGroup`, add `PromptTemplate` and `AdminOperationLog`, and extend `CallLog` with safe request/response summary fields.
- Modify `server/app/database.py`: add transitional schema creation for new columns/tables so local and deployed environments keep starting.
- Modify `server/app/auth.py`: add reusable `require_admin_user` and enforce disabled/deleted user status.
- Create `server/app/admin_service.py`: admin-only queries and mutations for overview, models, templates, users, records, and audit logs.
- Modify `server/app/schemas.py`: add admin request/response schemas.
- Modify `server/app/model_service.py`: serialize public metadata and record safe call-log summaries.
- Modify `server/app/main.py`: wire `/api/admin/*` endpoints and use prompt templates for prompt optimization.
- Add/modify tests in `server/tests/test_admin_backend.py` and `server/tests/test_conversations.py`.

Frontend:

- Modify `fronted/src/types.ts`: add admin types and model public metadata fields.
- Modify `fronted/src/api.ts`: add admin API helpers.
- Modify `fronted/src/utils.ts`: include `admin` routing and admin helper functions.
- Modify `fronted/src/App.vue`: add `admin` view, admin state, actions, and admin-only navigation.
- Modify `fronted/src/styles.css`: add admin dashboard styles.
- Add/modify tests in `fronted/src/api.test.ts` and `fronted/src/utils.test.ts`.

---

## Task 1: Backend Admin Data Model and Auth Boundary

**Files:**
- Modify: `server/app/db_models.py`
- Modify: `server/app/database.py`
- Modify: `server/app/auth.py`
- Modify: `server/app/schemas.py`
- Test: `server/tests/test_admin_backend.py`

- [ ] **Step 1: Write failing tests**

Create `server/tests/test_admin_backend.py` with tests that verify:

- `require_admin_user` allows the configured admin email.
- `require_admin_user` rejects a normal user with 403.
- disabled/deleted users are rejected by authenticated dependencies.
- `ModelGroup` accepts these new fields:
  - `public_display_name`
  - `public_description`
  - `input_hint`
  - `icon_url`
  - `public_tags_json`
  - `prompt_optimize_enabled`
  - `default_parameters_json`

Use an in-memory SQLite session and `Base.metadata.create_all(engine)` like existing backend tests.

- [ ] **Step 2: Run the failing test**

Run:

```powershell
python -m pytest server/tests/test_admin_backend.py -q
```

Expected: FAIL because the admin dependency and new database fields do not exist yet.

- [ ] **Step 3: Add database fields and tables**

In `server/app/db_models.py`:

- Add the model metadata fields listed in Step 1 to `ModelGroup`.
- Add to `CallLog`:
  - `request_params_json`
  - `response_summary_json`
  - `conversation_id`
  - `message_id`
  - `is_public_model`
- Add `PromptTemplate` with unique scope on `capability`, `model_group_id`, `template_type`.
- Add `AdminOperationLog` with action, target, status, safe summary JSON, and timestamp.

- [ ] **Step 4: Add startup schema compatibility**

In `server/app/database.py`, extend the existing compatibility/backfill logic so these columns and new tables exist when `AUTO_CREATE_TABLES=true`.

Required `models` columns:

```text
public_display_name, public_description, input_hint, icon_url,
public_tags_json, prompt_optimize_enabled, default_parameters_json
```

Required `call_logs` columns:

```text
request_params_json, response_summary_json, conversation_id, message_id, is_public_model
```

- [ ] **Step 5: Add admin auth boundary**

In `server/app/auth.py`, add:

- `ensure_user_active(user)`
- `require_admin_user(current_user, settings)`

`ensure_user_active` rejects `disabled` and `deleted` users with 403. `require_admin_user` calls `is_admin_user` and rejects non-admin users with 403.

- [ ] **Step 6: Add base schemas**

In `server/app/schemas.py`, add:

- `AdminModelUpdate`
- `PromptTemplateOut`
- `PromptTemplateUpdate`
- `AdminUserOut`
- `AdminUserUpdate`
- `AdminOverviewOut`
- `AdminCreationRecordOut`
- `AdminAuditLogOut`

- [ ] **Step 7: Run the task test**

Run:

```powershell
python -m pytest server/tests/test_admin_backend.py -q
```

Expected: PASS for auth boundary and schema/model field tests.

- [ ] **Step 8: Commit**

```powershell
git add server/app/db_models.py server/app/database.py server/app/auth.py server/app/schemas.py server/tests/test_admin_backend.py
git commit -m "feat: add admin data model boundary"
```

---

## Task 2: Public Model Governance API

**Files:**
- Create: `server/app/admin_service.py`
- Modify: `server/app/main.py`
- Modify: `server/app/model_service.py`
- Modify: `server/app/schemas.py`
- Test: `server/tests/test_admin_backend.py`

- [ ] **Step 1: Write failing tests**

Extend `server/tests/test_admin_backend.py` with service tests for:

- admin can publish a model.
- admin can unpublish a model.
- admin can update public display name, description, input hint, icon URL, public tags, prompt optimization enabled state, and default parameters.
- admin model list filters by capability, public/private state, and search text.

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
python -m pytest server/tests/test_admin_backend.py -q
```

Expected: FAIL because `server/app/admin_service.py` and routes do not exist yet.

- [ ] **Step 3: Create `admin_service.py` model functions**

Create functions:

- `json_dumps_safe(value)`
- `parse_json_object(value, fallback)`
- `write_admin_log(db, admin, action, target_type, target_id='', status='success', summary=None)`
- `list_admin_models(db, capability='all', search='', public_state='all')`
- `get_admin_model(db, model_id)`
- `update_admin_model(db, admin, model_id, payload)`
- `publish_model(db, admin, model_id)`
- `unpublish_model(db, admin, model_id)`

All write operations must create `AdminOperationLog`.

- [ ] **Step 4: Extend model serialization**

In `server/app/schemas.py`, extend `ModelOut` with:

```python
publicDisplayName: str = ""
publicDescription: str = ""
inputHint: str = ""
iconUrl: str = ""
publicTags: list[str] = Field(default_factory=list)
promptOptimizeEnabled: bool = True
defaultParameters: dict[str, Any] = Field(default_factory=dict)
```

In `server/app/model_service.py`, populate those fields from `ModelGroup`.

- [ ] **Step 5: Add admin model routes**

In `server/app/main.py`, add:

- `GET /api/admin/models`
- `PUT /api/admin/models/{model_id}`
- `POST /api/admin/models/{model_id}/publish`
- `POST /api/admin/models/{model_id}/unpublish`

All routes use `admin: User = Depends(require_admin_user)`.

- [ ] **Step 6: Run tests**

```powershell
python -m pytest server/tests/test_admin_backend.py -q
```

Expected: PASS for model governance tests.

- [ ] **Step 7: Commit**

```powershell
git add server/app/admin_service.py server/app/main.py server/app/model_service.py server/app/schemas.py server/tests/test_admin_backend.py
git commit -m "feat: add admin model governance api"
```

---

## Task 3: Prompt Templates, Users, Overview, Records, and Audit APIs

**Files:**
- Modify: `server/app/admin_service.py`
- Modify: `server/app/main.py`
- Modify: `server/app/model_service.py`
- Modify: `server/app/schemas.py`
- Test: `server/tests/test_admin_backend.py`
- Test: `server/tests/test_conversations.py`

- [ ] **Step 1: Write failing tests**

Add tests for:

- model-specific prompt template takes precedence over the capability default template.
- capability default prompt template is used when model-specific template is missing.
- disabled template is not used.
- admin can list users.
- admin can edit a normal user.
- admin can disable, enable, soft delete, and restore a normal user.
- admin cannot disable/delete their own account.
- admin record endpoints return text/image/video records without API keys.
- audit log endpoint returns publish/unpublish/template/user actions.

- [ ] **Step 2: Run failing tests**

```powershell
python -m pytest server/tests/test_admin_backend.py server/tests/test_conversations.py -q
```

Expected: FAIL because the service functions and routes do not exist yet.

- [ ] **Step 3: Implement prompt template functions**

In `admin_service.py`, add:

- `list_prompt_templates(db, capability='all')`
- `upsert_prompt_template(db, admin, payload)`
- `get_prompt_template_for_scope(db, capability, model_group_id='', template_type='prompt_optimize')`
- `render_prompt_template(template, values)`

Resolution order:

1. enabled model-specific template
2. enabled capability default template
3. current hardcoded fallback behavior in `/api/proxy/prompt/optimize`

- [ ] **Step 4: Implement user management functions**

In `admin_service.py`, add:

- `list_admin_users(db, search='')`
- `get_admin_user(db, user_id)`
- `ensure_can_manage_user(admin, target)`
- `update_admin_user(db, admin, user_id, payload)`
- `admin_disable_user(db, admin, user_id)`
- `admin_enable_user(db, admin, user_id)`
- `admin_delete_user(db, admin, user_id)`
- `admin_restore_user(db, admin, user_id)`

Disable and soft-delete must remove existing sessions for that user.

- [ ] **Step 5: Implement overview and record functions**

In `admin_service.py`, add:

- `admin_overview(db)`
- `admin_overview_users(db, start=None, end=None)`
- `admin_overview_models(db, start=None, end=None)`
- `list_admin_creation_records(db, capability, user_id='', model_group_id='', status='', limit=100)`
- `list_admin_audit_logs(db, action='', admin_user_id='', limit=100)`

Creation records should be built from existing `Conversation`, `ConversationMessage`, `GeneratedAsset`, and `CallLog` data.

- [ ] **Step 6: Extend call log summaries**

In `model_service.record_call_log`, add optional parameters:

- `request_params`
- `response_summary`
- `conversation_id`
- `message_id`
- `is_public_model`

Update text/image/video proxy call sites to pass safe summaries. Do not pass API keys, cookies, or full upstream auth config.

- [ ] **Step 7: Add admin routes**

In `main.py`, add:

- `GET /api/admin/overview`
- `GET /api/admin/overview/users`
- `GET /api/admin/overview/models`
- `GET /api/admin/prompt-templates`
- `PUT /api/admin/prompt-templates/{template_id}`
- `POST /api/admin/prompt-templates/test`
- `GET /api/admin/users`
- `PUT /api/admin/users/{user_id}`
- `POST /api/admin/users/{user_id}/disable`
- `POST /api/admin/users/{user_id}/enable`
- `POST /api/admin/users/{user_id}/delete`
- `POST /api/admin/users/{user_id}/restore`
- `GET /api/admin/records/text`
- `GET /api/admin/records/images`
- `GET /api/admin/records/videos`
- `GET /api/admin/audit-logs`

All routes use `require_admin_user`.

- [ ] **Step 8: Use prompt templates in prompt optimization**

Update `/api/proxy/prompt/optimize` to resolve and render the admin-configured template for the current capability/model. If no template exists, keep the current hardcoded optimization prompt.

- [ ] **Step 9: Run tests**

```powershell
python -m pytest server/tests/test_admin_backend.py server/tests/test_conversations.py -q
```

Expected: PASS for admin prompt, user, overview, record, and audit tests; existing conversation tests still pass.

- [ ] **Step 10: Commit**

```powershell
git add server/app/admin_service.py server/app/main.py server/app/model_service.py server/app/schemas.py server/tests/test_admin_backend.py server/tests/test_conversations.py
git commit -m "feat: add admin operations api"
```

---

## Task 4: Frontend Types, API Helpers, and Route Gating

**Files:**
- Modify: `fronted/src/types.ts`
- Modify: `fronted/src/api.ts`
- Modify: `fronted/src/utils.ts`
- Test: `fronted/src/api.test.ts`
- Test: `fronted/src/utils.test.ts`

- [ ] **Step 1: Write failing tests**

In `fronted/src/utils.test.ts`, add a test that verifies:

- `admin` is a private view.
- `loginRedirectForView('admin')` returns `/auth?redirect=%2Fadmin`.
- `resolveAuthRedirect('#/auth?redirect=%2Fadmin')` returns `admin`.

In `fronted/src/api.test.ts`, add a test that:

- fetches CSRF
- calls `publishAdminModel('mdl_1')`
- verifies it POSTs to `/api/admin/models/mdl_1/publish`
- verifies the CSRF header is attached

- [ ] **Step 2: Run failing frontend tests**

```powershell
cd fronted
cmd.exe /c npm run test -- --run src/utils.test.ts src/api.test.ts
```

Expected: FAIL because admin route and admin API helpers do not exist yet.

- [ ] **Step 3: Extend frontend types**

In `fronted/src/types.ts`, add public metadata fields to model types:

- `publicDisplayName`
- `publicDescription`
- `inputHint`
- `iconUrl`
- `publicTags`
- `promptOptimizeEnabled`
- `defaultParameters`

Add admin types:

- `AdminOverview`
- `AdminUserDefinition`
- `PromptTemplateDefinition`
- `AdminCreationRecord`
- `AdminAuditLog`

- [ ] **Step 4: Add admin API helpers**

In `fronted/src/api.ts`, add:

- `fetchAdminOverview`
- `fetchAdminOverviewUsers`
- `fetchAdminOverviewModels`
- `fetchAdminModels`
- `updateAdminModel`
- `publishAdminModel`
- `unpublishAdminModel`
- `fetchPromptTemplates`
- `savePromptTemplate`
- `testPromptTemplate`
- `fetchAdminUsers`
- `updateAdminUser`
- `enableAdminUser`
- `disableAdminUser`
- `deleteAdminUser`
- `restoreAdminUser`
- `fetchAdminRecords`
- `fetchAdminAuditLogs`

- [ ] **Step 5: Update route helpers**

In `fronted/src/utils.ts`, include `admin` in private route and auth redirect handling.

- [ ] **Step 6: Run tests**

```powershell
cd fronted
cmd.exe /c npm run test -- --run src/utils.test.ts src/api.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add fronted/src/types.ts fronted/src/api.ts fronted/src/utils.ts fronted/src/api.test.ts fronted/src/utils.test.ts
git commit -m "feat: add admin frontend api boundary"
```

---

## Task 5: Admin Frontend View, Tabs, and Actions

**Files:**
- Modify: `fronted/src/App.vue`
- Modify: `fronted/src/styles.css`

- [ ] **Step 1: Add admin route and state**

In `App.vue`:

- Add `admin` to `ViewName`.
- Add `AdminTab` with:
  - `overview`
  - `models`
  - `prompts`
  - `users`
  - `text-records`
  - `image-records`
  - `video-records`
  - `audit`
- Add `adminState` for active tab, filters, loading flags, errors, overview, models, templates, users, records, and audit logs.

- [ ] **Step 2: Add admin navigation**

Add a topbar/sidebar button visible only when `auth.state.user?.isAdmin`:

```vue
<button v-if="auth.state.user?.isAdmin" class="topbar-icon-button" @click="navigate('admin')">后台</button>
```

Ensure the creation panel is hidden when `view === 'admin'`.

- [ ] **Step 3: Add admin load and mutation actions**

Add functions:

- `loadAdminOverview`
- `loadAdminModels`
- `saveAdminModel`
- `toggleAdminPublicModel`
- `loadPromptTemplates`
- `savePromptTemplate`
- `testAdminPromptTemplate`
- `loadAdminUsers`
- `setAdminUserStatus`
- `loadAdminRecords`
- `loadAdminAuditLogs`

After public model mutations, call `store.loadServerModels()`.

- [ ] **Step 4: Add admin template**

Add an `v-else-if="view === 'admin'"` section with:

- denied state for non-admin users
- hero header
- left tab navigation
- active tab panel

Tab content:

- Overview: metric cards, user/model summary tables, recent failures.
- Public model config: model rows, filters, publish/unpublish, metadata fields, prompt optimize toggle, icon URL, tags.
- Prompt templates: capability/model selector, textarea, enabled toggle, test preview.
- Users: search, editable fields, enable/disable/delete/restore.
- Text/image/video records: filters, record list, detail drawer with prompt, response, assets.
- Audit logs: filters and log table.

- [ ] **Step 5: Add CSS**

In `styles.css`, add admin classes:

- `.admin-page`
- `.admin-hero`
- `.admin-shell`
- `.admin-tabs`
- `.admin-tab`
- `.admin-tab-active`
- `.admin-panel`
- `.admin-toolbar`
- `.admin-metrics`
- `.admin-metric`
- `.admin-table`
- `.admin-row`
- `.admin-record-detail`
- `.admin-denied`

Add mobile responsive styles so the sidebar tabs stack above content on narrow screens.

- [ ] **Step 6: Run frontend tests and build**

```powershell
cd fronted
cmd.exe /c npm run test -- --run src/utils.test.ts src/api.test.ts
cmd.exe /c npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add fronted/src/App.vue fronted/src/styles.css
git commit -m "feat: add admin dashboard view"
```

---

## Task 6: Full Verification and Browser Check

**Files:**
- No planned source changes unless verification finds bugs.

- [ ] **Step 1: Run full backend tests**

```powershell
python -m pytest server/tests -q
```

Expected: all backend tests pass.

- [ ] **Step 2: Run full frontend tests and build**

```powershell
cd fronted
cmd.exe /c npm run test
cmd.exe /c npm run build
```

Expected: all frontend tests pass and production build succeeds.

- [ ] **Step 3: Start local backend and frontend**

Use the existing project startup commands. If a frontend port is occupied, use the next available Vite port.

- [ ] **Step 4: Browser verify normal user**

Using the in-app browser:

1. Log in as a normal user.
2. Confirm no “后台” entry appears.
3. Open `#/settings`.
4. Confirm private models are editable.
5. Confirm public models are tagged and readonly.

- [ ] **Step 5: Browser verify admin**

Using the in-app browser:

1. Log in as the configured admin.
2. Confirm “后台” entry appears.
3. Open `#/admin`.
4. Click all 8 tabs.
5. Publish and unpublish one model.
6. Save a prompt template.
7. Open user management and verify user rows load.
8. Open text/image/video records and verify record details render.
9. Open audit logs and verify admin actions appear.

- [ ] **Step 6: Browser verify prompt optimization**

Using the in-app browser:

1. Text page: enter short prompt, click AI optimize, confirm rewritten prompt.
2. Image page: enter short prompt, click AI optimize, confirm rewritten prompt.
3. Video page: enter short prompt, click AI optimize, confirm rewritten prompt.

- [ ] **Step 7: Check git state**

```powershell
git status --short --branch
```

Expected: clean except ignored runtime/generated directories.

- [ ] **Step 8: Final report**

Report:

- backend admin APIs added
- frontend admin dashboard added
- tests and build results
- browser verification results
- known non-goals still deferred
