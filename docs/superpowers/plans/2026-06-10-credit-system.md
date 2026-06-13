# Credit System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a configurable points system where public model usage can deduct credits, private models remain free, failed generation refunds credits, and admins can configure prices and adjust balances.

**Architecture:** Add focused backend credit models and a `credit_service` that owns account creation, pricing, reservation, capture, refund, and admin adjustments. Wire the service into text/image/video proxy endpoints, then expose user/admin APIs and update Vue state/UI to show balance, pricing, and admin controls.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, SQLite/MySQL-compatible schema bootstrap, Vue 3 Composition API, Pinia-style stores, Vitest, pytest.

---

## File Structure

- `server/app/db_models.py`: add `UserCreditAccount`, `CreditTransaction`, `CreditPricingRule`, and `SystemSetting` ORM models.
- `server/app/database.py`: bootstrap new tables/columns and seed default pricing without requiring Alembic.
- `server/app/credit_service.py`: new single-responsibility service for balances, pricing, reserve/capture/refund, signup bonus, and admin adjustments.
- `server/app/schemas.py`: add credit DTOs and extend user/admin/model DTOs with credit fields.
- `server/app/auth.py`: create account and optional signup bonus during registration; include credits in user serialization.
- `server/app/admin_service.py`: include credit fields in admin users, overview metrics, admin pricing helpers, and audit logs.
- `server/app/model_service.py`: serialize public model effective credit price.
- `server/app/main.py`: add credit APIs and wire reserve/capture/refund into text/image/video flows.
- `server/tests/test_credit_service.py`: new backend unit tests for pricing, adjustments, reserve/capture/refund, and idempotency.
- `server/tests/test_admin_backend.py`: add API-level tests for admin credit settings and user adjustment.
- `fronted/src/types.ts`: add credit account, transaction, pricing, settings, and model effective price types.
- `fronted/src/api.ts`: add credit API wrappers.
- `fronted/src/stores/auth.ts`: keep current user credit snapshot.
- `fronted/src/App.vue`: show balance/estimated cost, block insufficient credit, add admin credit settings and user adjustment UI.
- `fronted/src/api.test.ts` and `fronted/src/adminPresentation.test.ts`: verify new API wrappers and UI markers.

## Task 1: Backend Credit Data Model And Service

**Files:**
- Modify: `server/app/db_models.py`
- Modify: `server/app/database.py`
- Create: `server/app/credit_service.py`
- Test: `server/tests/test_credit_service.py`

- [x] **Step 1: Write failing credit service tests**

Create `server/tests/test_credit_service.py` with tests that use `Base.metadata.create_all(engine)` and assert:

```python
def test_default_account_has_zero_balance() -> None:
    db = make_db()
    user = make_user(db, "artist@example.com")
    account = get_or_create_credit_account(db, user.id)
    assert account.balance == 0
    assert account.reserved_balance == 0

def test_private_model_price_is_zero_even_when_default_is_positive() -> None:
    db = make_db()
    owner = make_user(db, "owner@example.com")
    model = make_model(db, owner, capability="image", is_public=False)
    set_capability_price(db, "image", 3)
    estimate = estimate_credit_price(db, user=owner, capability="image", model_group=model, sub_model=None)
    assert estimate.price == 0
    assert estimate.source == "private_model"

def test_public_model_uses_override_before_default() -> None:
    db = make_db()
    admin = make_user(db, "cage_ben@sina.com")
    model = make_model(db, admin, capability="video", is_public=True)
    set_capability_price(db, "video", 6)
    set_model_price(db, admin, model.id, 9)
    estimate = estimate_credit_price(db, user=admin, capability="video", model_group=model, sub_model=None)
    assert estimate.price == 9
    assert estimate.source == "model_override"

def test_reserve_capture_and_refund_are_idempotent() -> None:
    db = make_db()
    user = make_user(db, "artist@example.com")
    admin_adjust_credits(db, admin=user, target_user=user, amount=5, reason="seed")
    reserve = reserve_generation_credits(db, user=user, capability="image", price=2, model_group_id="mdl_1")
    assert get_or_create_credit_account(db, user.id).balance == 3
    assert get_or_create_credit_account(db, user.id).reserved_balance == 2
    capture_generation_credits(db, reserve.id)
    capture_generation_credits(db, reserve.id)
    account = get_or_create_credit_account(db, user.id)
    assert account.balance == 3
    assert account.reserved_balance == 0
    assert account.total_spent == 2
```

Run: `python -m pytest server/tests/test_credit_service.py -q`

Expected: FAIL because models and service do not exist.

- [x] **Step 2: Add ORM models**

Add SQLAlchemy models with integer balances and indexed user/model/task fields:

```python
class UserCreditAccount(Base):
    __tablename__ = "user_credit_accounts"
    id = mapped_column(String(64), primary_key=True, default=lambda: new_id("credacct"))
    user_id = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    balance = mapped_column(Integer, default=0)
    reserved_balance = mapped_column(Integer, default=0)
    total_recharged = mapped_column(Integer, default=0)
    total_spent = mapped_column(Integer, default=0)
    total_refunded = mapped_column(Integer, default=0)
    created_at = mapped_column(DateTime, default=utcnow)
    updated_at = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
```

Add `CreditTransaction`, `CreditPricingRule`, and `SystemSetting` with the fields from the spec.

- [x] **Step 3: Bootstrap schema and default prices**

Update `init_db()` to call `Base.metadata.create_all()` and then seed missing default pricing rows:

```python
INSERT INTO credit_pricing_rules (id, scope, capability, model_group_id, sub_model_id, price, enabled, created_at, updated_at)
VALUES (... text default 0, image default 1, video default 0 ...)
```

Use dialect-safe Python inserts through ORM if raw SQL gets too branchy.

- [x] **Step 4: Implement `credit_service.py`**

Implement:

- `get_or_create_credit_account`
- `set_capability_price`
- `set_model_price`
- `clear_model_price`
- `get_credit_settings`
- `estimate_credit_price`
- `admin_adjust_credits`
- `reserve_generation_credits`
- `capture_generation_credits`
- `refund_generation_credits`
- `serialize_credit_account`
- `serialize_credit_transaction`

Rules:

- Negative prices are rejected.
- Admin deduction cannot make balance negative.
- Private models return price 0.
- Public model override wins over capability default.
- Capture/refund are idempotent by checking transaction status and related transactions.

- [x] **Step 5: Run service tests**

Run: `python -m pytest server/tests/test_credit_service.py -q`

Expected: PASS.

## Task 2: Backend Schemas And Admin/User APIs

**Files:**
- Modify: `server/app/schemas.py`
- Modify: `server/app/admin_service.py`
- Modify: `server/app/auth.py`
- Modify: `server/app/main.py`
- Test: `server/tests/test_admin_backend.py`

- [x] **Step 1: Write failing API tests**

Add tests:

```python
def test_admin_credit_settings_and_user_adjustment_routes() -> None:
    # override get_db and get_current_user as existing route tests do
    settings = client.get("/api/admin/credits/settings")
    assert settings.status_code == 200
    update = client.put("/api/admin/credits/settings", json={"defaults": {"text": 0, "image": 2, "video": 5}, "signupBonusEnabled": True, "signupBonusAmount": 7})
    assert update.status_code == 200
    adjust = client.post(f"/api/admin/users/{normal.id}/credits/adjust", json={"amount": 10, "reason": "manual recharge"})
    assert adjust.status_code == 200
    assert adjust.json()["account"]["balance"] == 10

def test_non_admin_cannot_adjust_credits() -> None:
    response = client.post(f"/api/admin/users/{target.id}/credits/adjust", json={"amount": 1, "reason": "x"})
    assert response.status_code == 403
```

Run: `python -m pytest server/tests/test_admin_backend.py -q`

Expected: FAIL because routes do not exist.

- [x] **Step 2: Add Pydantic DTOs**

Add:

- `CreditAccountOut`
- `CreditTransactionOut`
- `CreditPricingEstimateOut`
- `AdminCreditSettingsOut`
- `AdminCreditSettingsUpdate`
- `AdminCreditAdjustRequest`
- `AdminModelCreditPricingUpdate`

Extend:

- `UserOut` with `credits: CreditAccountOut | None`
- `AdminUserOut` with `credits: CreditAccountOut | None`
- `ModelOut` with `creditPrice`, `creditPriceSource`, `creditPricingEnabled`

- [x] **Step 3: Wire user serialization**

In `serialize_user`, include a lightweight credit account snapshot. If no DB is available in existing call sites, keep `credits=None`; main/profile routes can fill credits explicitly.

- [x] **Step 4: Add credit API routes**

Add:

- `GET /api/credits/me`
- `GET /api/credits/pricing/estimate`
- `GET /api/admin/credits/settings`
- `PUT /api/admin/credits/settings`
- `GET /api/admin/credits/transactions`
- `GET /api/admin/users/{user_id}/credits`
- `POST /api/admin/users/{user_id}/credits/adjust`
- `PUT /api/admin/models/{model_id}/credit-pricing`

All admin routes require `require_admin_user`.

- [x] **Step 5: Run admin API tests**

Run: `python -m pytest server/tests/test_admin_backend.py server/tests/test_credit_service.py -q`

Expected: PASS.

## Task 3: Generation Reserve, Capture, And Refund

**Files:**
- Modify: `server/app/main.py`
- Modify: `server/app/credit_service.py`
- Test: `server/tests/test_credit_service.py`
- Test: targeted existing proxy tests if available

- [x] **Step 1: Add unit tests for task id binding**

Extend credit service tests:

```python
def test_refund_by_task_id_only_once() -> None:
    reserve = reserve_generation_credits(..., task_id="task_1")
    refund_generation_credits(db, reserve.id, reason="failed")
    refund_generation_credits(db, reserve.id, reason="failed again")
    assert account.balance == original_balance
    assert len(refund_transactions) == 1
```

- [x] **Step 2: Add helper functions in `main.py`**

Add local helpers:

- `prepare_generation_credit(...)`
- `capture_generation_credit_if_needed(...)`
- `refund_generation_credit_if_needed(...)`
- `attach_credit_result(...)`

These helpers call `credit_service` and return serialized credit info for API responses.

- [x] **Step 3: Wire `/api/proxy/text`**

Before forwarding to upstream:

- Resolve `model_group` and `sub_model`.
- Estimate price.
- Reserve if price > 0.

On success:

- Capture.
- Add `credits` result to response.

On exception/failure:

- Refund.
- Preserve existing conversation/error behavior.

- [x] **Step 4: Wire `/api/proxy/image` and `/api/proxy/image/query`**

Create endpoint:

- Reserve before upstream call.
- If synchronous success with final images, capture.
- If task ID returned, keep reserve transaction id in assistant message `response_json` and task metadata.
- If create call fails, refund.

Query endpoint:

- Find pending reserve by task ID/message metadata.
- On completed, capture.
- On failed/not found/cleaned/error, refund.

- [x] **Step 5: Wire `/api/proxy/video/create` and `/api/proxy/video/query`**

Same task pattern as image:

- Reserve on create.
- Store reserve transaction id with assistant processing message.
- Capture when query completes.
- Refund when query fails or task status failed.

- [x] **Step 6: Run backend tests**

Run:

```powershell
python -m pytest server/tests/test_credit_service.py server/tests/test_admin_backend.py server/tests/test_conversations.py server/tests/test_video_local_references.py -q
```

Expected: PASS.

## Task 4: Frontend API Types And Auth Store

**Files:**
- Modify: `fronted/src/types.ts`
- Modify: `fronted/src/api.ts`
- Modify: `fronted/src/stores/auth.ts`
- Test: `fronted/src/api.test.ts`

- [x] **Step 1: Write failing API wrapper tests**

Assert `fetchMyCredits`, `fetchAdminCreditSettings`, `updateAdminCreditSettings`, `adjustAdminUserCredits`, and `updateAdminModelCreditPricing` call the expected endpoints.

Run: `cmd.exe /c npm run test -- --run src/api.test.ts`

Expected: FAIL until wrappers exist.

- [x] **Step 2: Add frontend types**

Add matching TypeScript interfaces for accounts, transactions, pricing estimates, settings, and credit API responses.

- [x] **Step 3: Add API wrappers**

Add typed functions in `api.ts`.

- [x] **Step 4: Add auth credit refresh**

Expose `refreshCredits()` in auth store and keep current profile credit snapshot fresh after generation and admin adjustments.

- [x] **Step 5: Run frontend API tests**

Run: `cmd.exe /c npm run test -- --run src/api.test.ts`

Expected: PASS.

## Task 5: Frontend UI Integration

**Files:**
- Modify: `fronted/src/App.vue`
- Modify: `fronted/src/styles.css`
- Test: `fronted/src/adminPresentation.test.ts`

- [x] **Step 1: Add UI marker tests**

Check source contains:

- `credit-balance`
- `credit-cost-preview`
- `admin-credit-settings`
- `admin-user-credit-panel`
- `adjustAdminUserCredits`

Run: `cmd.exe /c npm run test -- --run src/adminPresentation.test.ts`

Expected: FAIL until UI markers exist.

- [x] **Step 2: Add user credit display**

Show in profile/personal center:

- Available credits.
- Reserved credits.
- Recent transactions.
- Rule text: private models do not consume platform credits.

- [x] **Step 3: Show estimated cost in composer**

For selected model:

- Public paid model: show `棰勮娑堣€?N 绉垎`.
- Public free model: show `鏈涓嶆秷鑰楃Н鍒哷.
- Private model: show `绉佹湁妯″瀷涓嶆秷鑰楃Н鍒哷.

If unauthenticated and cost > 0, send button opens login redirect.

If authenticated and balance < cost, block send and show `绉垎涓嶈冻锛岃鍏呭€煎悗鍐嶇敓鎴愩€俙

- [x] **Step 4: Add admin credit settings**

In admin public model/settings area:

- Defaults for text/image/video.
- Signup bonus toggle and amount.
- Model override price field in model operation drawer.
- Effective price preview in model rows.

- [x] **Step 5: Add admin user adjustment UI**

In user detail/action drawer:

- Balance summary.
- Recent transaction list.
- Add/deduct form with amount and reason.
- Confirmation before submit.

- [x] **Step 6: Refresh balances after generation**

After text/image/video success, failure, or polling final state:

- If response includes `credits`, update auth credit snapshot.
- Otherwise call `refreshCredits()` when logged in.

- [x] **Step 7: Run frontend tests and build**

Run:

```powershell
cd fronted
cmd.exe /c npm run test -- --run src/api.test.ts src/adminPresentation.test.ts
cmd.exe /c npm run build
```

Expected: PASS.

## Task 6: Full Verification And Commit

**Files:**
- All changed files

- [x] **Step 1: Run backend test subset**

Run:

```powershell
python -m pytest server/tests/test_credit_service.py server/tests/test_admin_backend.py server/tests/test_auth_models.py server/tests/test_conversations.py server/tests/test_video_local_references.py -q
```

Expected: PASS.

- [x] **Step 2: Run frontend tests and build**

Run:

```powershell
cd fronted
cmd.exe /c npm run test
cmd.exe /c npm run build
```

Expected: PASS.

- [x] **Step 3: Check git status**

Run: `git status --short`

Expected: only intentional changed files and existing unrelated untracked markdown drafts.

- [x] **Step 4: Commit**

Stage only intentional credit-system files and commit:

```powershell
git add -- server/app/db_models.py server/app/database.py server/app/credit_service.py server/app/schemas.py server/app/auth.py server/app/admin_service.py server/app/model_service.py server/app/main.py server/tests/test_credit_service.py server/tests/test_admin_backend.py fronted/src/types.ts fronted/src/api.ts fronted/src/stores/auth.ts fronted/src/App.vue fronted/src/styles.css fronted/src/api.test.ts fronted/src/adminPresentation.test.ts docs/superpowers/plans/2026-06-10-credit-system.md
git commit -m "feat: add configurable credit system"
```

## Self Review

- Spec coverage: data model, pricing defaults/overrides, private model free usage, insufficient balance blocking, reserve/capture/refund, admin adjustments, signup bonus, user display, and tests all map to tasks.
- Placeholder scan: no TODO/TBD placeholders are required for implementation.
- Type consistency: backend DTOs and frontend types use `credits`, `creditPrice`, `creditPriceSource`, and `creditPricingEnabled` consistently.
