# Public Model Security and Creator Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent unauthorized public-model mutations and make administrator-configured public models clearly distinct in the creator workspace.

**Architecture:** Generic model routes resolve individual public-model permissions from the existing role permission system and pass explicit boolean capabilities into the model service. Public model metadata gains a validated accent color and safe public descriptions are serialized for all creators. The creator Settings view filters public models for ordinary users while the shared sidebar renders public models as compact, color-coded cards.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3 Composition API, TypeScript, Vitest, pytest, Playwright.

---

## File Structure

- `server/app/main.py`: Resolve per-operation public-model permissions in generic routes and pass them to model service functions.
- `server/app/model_service.py`: Enforce explicit public-model capabilities and serialize public presentation metadata safely.
- `server/app/db_models.py`: Persist `public_accent_color` on `ModelGroup`.
- `server/app/schemas.py`: Add the color to model API schemas and validate admin updates.
- `server/app/admin_service.py`: Save the validated public color.
- `server/migrations/008_public_model_accent_color.sql`: Add the persistent MySQL column.
- `server/tests/test_admin_backend.py`: Exercise operator/viewer generic-route denial and public metadata behavior.
- `fronted/src/types.ts`: Carry `publicAccentColor` through server model types.
- `fronted/src/utils.ts`: Provide settings filtering and public-card presentation helpers.
- `fronted/src/utils.test.ts`: Cover filtering, color fallbacks, and public card copy.
- `fronted/src/App.vue`: Apply settings visibility rules and render public-card metadata.
- `fronted/src/styles.css`: Add compact public-card and mobile presentation styles.
- `admin/src/types.ts`: Carry `publicAccentColor` through admin API types.
- `admin/src/views/modelCenterState.ts`: Add swatch form state and payload mapping.
- `admin/src/views/modelCenterState.test.ts`: Cover the accent-color form payload.
- `admin/src/views/ModelCenterView.vue`: Render the constrained administrator swatch picker.

### Task 1: Reproduce the Public-Model Role Escalation

**Files:**
- Modify: `server/tests/test_admin_backend.py`
- Test: `server/tests/test_admin_backend.py`

- [ ] **Step 1: Write the failing role regression test**

Add a test that creates a public model owned by a super-admin, assigns a viewer and an operator role, overrides `get_current_user`, and verifies the generic model route does not grant edit access. The core assertions are:

```python
app.dependency_overrides[get_current_user] = lambda: viewer
listed = client.get("/api/models")
assert listed.status_code == 200
assert listed.json()["models"][0]["canEdit"] is False
assert client.put(f"/api/models/{model.id}", json={"name": "Viewer edit"}).status_code == 403

app.dependency_overrides[get_current_user] = lambda: operator
assert client.put(f"/api/models/{model.id}", json={"name": "Operator edit"}).status_code == 403

app.dependency_overrides[get_current_user] = lambda: admin
assert client.put(f"/api/models/{model.id}", json={"name": "Admin edit"}).status_code == 200
```

Use the existing `make_db`, `make_user`, `make_model`, `AdminRoleAssignment`, `get_db`, `get_current_user`, and `main_module.rate_limiter.clear()` patterns in this file. Set `model.is_public = True` and commit it before sending requests.

- [ ] **Step 2: Run the regression test and verify it fails**

Run: `pytest server/tests/test_admin_backend.py -k generic_public_model_routes -q`

Expected: FAIL because the generic route currently treats viewer and operator roles as `is_admin` and returns `canEdit: true` or a 200 update response.

- [ ] **Step 3: Commit the failing regression test**

```powershell
git add server/tests/test_admin_backend.py
git commit -m "test: cover generic public model role escalation"
```

### Task 2: Enforce Per-Operation Public-Model Permissions

**Files:**
- Modify: `server/app/main.py:2910-3045`
- Modify: `server/app/model_service.py:120-495`
- Modify: `server/tests/test_admin_backend.py`
- Test: `server/tests/test_admin_backend.py`

- [ ] **Step 1: Add explicit public-model permission arguments to the model service**

Replace broad `is_admin` authorization inputs with operation-specific flags. Keep private ownership behavior unchanged. The key authorization rule is:

```python
def can_edit_model(model: ModelGroup, user: User | None = None, *, can_edit_public: bool = False) -> bool:
    if not user:
        return False
    if model.is_public:
        return can_edit_public
    return model.user_id == user.id
```

Make `get_model_group`, `update_model_group`, `delete_model_group`, and `set_primary_sub_model` accept only the flag needed for their operation. For a visibility transition in `update_model_group`, reject publication unless `can_publish_public` is true and reject unpublication unless `can_unpublish_public` is true. A private owner can still edit or delete only its own private model.

- [ ] **Step 2: Resolve permissions at every generic model route**

In `server/app/main.py`, use the already imported `can` helper with `get_settings` to pass the narrow capability into the service:

```python
can_edit_public = can(current_user, "model:update", settings)
can_publish_public = can(current_user, "model:publish", settings)
can_unpublish_public = can(current_user, "model:unpublish", settings)
can_delete_public = can(current_user, "model:delete", settings)
```

Apply these to `GET /api/models` serialization, `POST /api/models`, `PUT /api/models/{model_id}`, `DELETE /api/models/{model_id}`, `POST /api/models/{model_id}/primary`, and `POST /api/models/{model_id}/sync`. A public model create needs `model:publish`; public primary changes and synchronization need `model:update`.

For the admin API serializer, pass `can(admin, "model:update", settings)` instead of unconditional editable access so viewer and operator console rows remain read-only unless their permission grants editing.

- [ ] **Step 3: Run the regression test and verify it passes**

Run: `pytest server/tests/test_admin_backend.py -k generic_public_model_routes -q`

Expected: PASS with viewer/operator 403 responses and an authorized admin 200 response.

- [ ] **Step 4: Run existing public model tests**

Run: `pytest server/tests/test_auth_models.py -k "public_model or non_admin_cannot_edit_delete_or_switch_public_model" -q`

Expected: PASS; public models remain usable for non-admin creators but cannot be changed by them.

- [ ] **Step 5: Commit the permission fix**

```powershell
git add server/app/main.py server/app/model_service.py server/tests/test_admin_backend.py
git commit -m "fix: enforce public model operation permissions"
```

### Task 3: Persist and Expose Safe Public Presentation Metadata

**Files:**
- Create: `server/migrations/008_public_model_accent_color.sql`
- Modify: `server/app/db_models.py:270-295`
- Modify: `server/app/schemas.py:242-275`
- Modify: `server/app/model_service.py:145-190`
- Modify: `server/app/admin_service.py:200-230`
- Modify: `server/tests/test_admin_backend.py`
- Test: `server/tests/test_admin_backend.py`

- [ ] **Step 1: Write the failing metadata test**

Extend the existing admin metadata test so it supplies `publicAccentColor="#28C5FF"`, then serialize the model as a non-editor. Assert that public display data is safe and useful while secrets remain hidden:

```python
assert payload["publicDescription"] == "Platform model for long-form writing"
assert payload["publicAccentColor"] == "#28C5FF"
assert payload["baseUrl"] == ""
assert "token.example.com" not in payload["description"]
```

- [ ] **Step 2: Run the metadata test and verify it fails**

Run: `pytest server/tests/test_admin_backend.py -k public_model_metadata -q`

Expected: FAIL because `publicAccentColor` does not exist and non-editors currently receive an empty `publicDescription`.

- [ ] **Step 3: Add the migration, model field, schema fields, and validation**

Create the migration with the same direct MySQL style as prior migrations:

```sql
ALTER TABLE models ADD COLUMN public_accent_color VARCHAR(7) NOT NULL DEFAULT '';
```

Add `public_accent_color` to `ModelGroup`, `publicAccentColor` to `ModelOut` and `AdminModelUpdate`, and a Pydantic validator that accepts only an empty value or an uppercase normalized `#RRGGBB` color. `update_admin_model` stores the normalized value. `serialize_model` always returns the public description, tags, icon URL, and accent color for public models, while retaining empty credentials and sanitized private descriptions for non-editors.

- [ ] **Step 4: Run the metadata test and verify it passes**

Run: `pytest server/tests/test_admin_backend.py -k public_model_metadata -q`

Expected: PASS with color and public description visible to a non-editor, but no base URL or API key exposed.

- [ ] **Step 5: Commit the public metadata contract**

```powershell
git add server/migrations/008_public_model_accent_color.sql server/app/db_models.py server/app/schemas.py server/app/model_service.py server/app/admin_service.py server/tests/test_admin_backend.py
git commit -m "feat: add public model accent metadata"
```

### Task 4: Add Creator Visibility and Card Presentation Helpers

**Files:**
- Modify: `fronted/src/types.ts:8-145`
- Modify: `fronted/src/utils.ts:141-225`
- Modify: `fronted/src/utils.test.ts`
- Test: `fronted/src/utils.test.ts`

- [ ] **Step 1: Write failing frontend helper tests**

Add tests for the explicit settings visibility argument and public card helpers:

```typescript
expect(filterSettingsModels([privateModel, publicModel], "all", "", false).map((model) => model.id)).toEqual([privateModel.id]);
expect(filterSettingsModels([privateModel, publicModel], "all", "", true).map((model) => model.id)).toEqual([privateModel.id, publicModel.id]);
expect(publicModelAccent({ ...publicModel, publicAccentColor: "#C857F1" })).toBe("#C857F1");
expect(publicModelAccent({ ...publicModel, capability: "video", publicAccentColor: "" })).toBe("#9EE841");
expect(publicModelCardDescription({ ...publicModel, publicDescription: "Fast product film" })).toBe("Fast product film");
```

- [ ] **Step 2: Run the helper tests and verify they fail**

Run: `npm test -- --run src/utils.test.ts`

Working directory: `fronted`

Expected: FAIL because the visibility argument and public-card helper exports do not exist.

- [ ] **Step 3: Implement the minimal typed helpers**

Add `publicAccentColor?: string` to both server and creator model types. Change the filtering signature to:

```typescript
export function filterSettingsModels(
  models: ModelDefinition[],
  capability: Capability | "all",
  query: string,
  includePublic = false,
): ModelDefinition[] {
  return models.filter((model) => {
    if (model.isPublic && !includePublic) return false;
    // retain existing capability and query checks
  });
}
```

Export `publicModelAccent` with the documented text, image, and video fallbacks and `publicModelCardDescription` that prefers the public description, then the safe model description, then a stable platform-model fallback.

- [ ] **Step 4: Run the helper tests and verify they pass**

Run: `npm test -- --run src/utils.test.ts`

Working directory: `fronted`

Expected: PASS.

- [ ] **Step 5: Commit creator presentation helpers**

```powershell
git add fronted/src/types.ts fronted/src/utils.ts fronted/src/utils.test.ts
git commit -m "feat: add public model creator presentation helpers"
```

### Task 5: Add the Administrator Swatches and Creator Public Cards

**Files:**
- Modify: `admin/src/types.ts:145-185`
- Modify: `admin/src/views/modelCenterState.ts:28-120`
- Modify: `admin/src/views/modelCenterState.test.ts`
- Modify: `admin/src/views/ModelCenterView.vue:240-315`
- Modify: `fronted/src/App.vue:470-490,1795-1845,3845-3895`
- Modify: `fronted/src/styles.css`
- Test: `admin/src/views/modelCenterState.test.ts`
- Test: `fronted/src/styleApplication.test.ts`

- [ ] **Step 1: Write failing admin form and creator template tests**

Add a `modelCenterState` test asserting color round-trips through the edit form:

```typescript
const form = createEditForm({ ...model, publicAccentColor: "#FF6B8A" });
expect(buildAdminModelUpdatePayload(form)).toMatchObject({ publicAccentColor: "#FF6B8A" });
```

Add a creator source test that expects the public card to use `publicModelAccent`, `publicModelCardDescription`, `model.publicTags`, and `model.creditPrice`.

- [ ] **Step 2: Run the frontend tests and verify they fail**

Run: `npm test -- --run src/views/modelCenterState.test.ts src/styleApplication.test.ts`

Working directory: `admin` for the first test and `fronted` for the second test.

Expected: FAIL because the form payload and creator template do not reference the accent and card metadata.

- [ ] **Step 3: Implement admin swatches and creator rendering**

Add `publicAccentColor` to the admin types and `ModelEditForm`. In the model center drawer, render a stable swatch set using color buttons with `aria-label` and visible selection state; do not use a free-form text field. Bind the selection to `editForm.publicAccentColor` and preserve it in `buildAdminModelUpdatePayload`.

In `App.vue`, map `item.publicAccentColor`, call `filterSettingsModels(..., Boolean(auth.state.user?.isAdmin))`, and add a `publicModelCardStyle` helper returning `{ "--public-model-accent": publicModelAccent(model) }`. Extend the shared sidebar public item with platform label, safe description, tag chips limited to two, and a credit-price label. Keep standard private items compact.

At the end of `styles.css`, add scoped overrides that use the custom property for a left rail, icon ring, active outline, tags, and card footer. Keep card dimensions stable, give the list a mobile-safe minimum height, and use `overflow: hidden` plus line clamps so long names and tags do not shift layout.

- [ ] **Step 4: Run frontend tests and production builds**

Run: `npm test -- --run src/views/modelCenterState.test.ts`

Working directory: `admin`

Expected: PASS.

Run: `npm test -- --run src/styleApplication.test.ts src/utils.test.ts`

Working directory: `fronted`

Expected: PASS.

Run: `npm run build`

Working directories: `admin`, then `fronted`

Expected: both builds exit 0.

- [ ] **Step 5: Commit public card presentation**

```powershell
git add admin/src/types.ts admin/src/views/modelCenterState.ts admin/src/views/modelCenterState.test.ts admin/src/views/ModelCenterView.vue fronted/src/App.vue fronted/src/styles.css fronted/src/styleApplication.test.ts
git commit -m "feat: distinguish public models in creator workspace"
```

### Task 6: Browser Verification

**Files:**
- Modify only if verification reveals a defect: files named in Task 5

- [ ] **Step 1: Start the existing server and both Vite applications**

Run the server on port 8000, the admin app on port 5174, and the creator app on port 5175. Reuse an already-running healthy process instead of starting a duplicate.

- [ ] **Step 2: Verify desktop and mobile behavior with Playwright**

At 1440x960 and 390x844, log in as an ordinary user and verify public models are selectable in the creator sidebar but absent from Settings. Log in as an administrator and verify public models remain visible in Settings. Create text, image, and video public models with distinct swatches and verify their cards have visible, non-overlapping color rails, labels, descriptions, tags, and price labels.

- [ ] **Step 3: Run the final focused regression suites**

Run: `pytest server/tests/test_admin_backend.py server/tests/test_auth_models.py -q`

Run: `npm test -- --run src/utils.test.ts src/styleApplication.test.ts`

Working directory: `fronted`

Run: `npm test -- --run src/views/modelCenterState.test.ts`

Working directory: `admin`

Expected: every command exits 0.

- [ ] **Step 4: Commit any browser-verified correction**

```powershell
git add server admin fronted
git commit -m "fix: polish public model creator cards"
```
