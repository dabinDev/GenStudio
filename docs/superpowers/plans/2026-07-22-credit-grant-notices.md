# Credit Grant Notices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show credited users a persistent, top-of-workspace snackbar for individual and batch administrator grants until the user dismisses each notice.

**Architecture:** Positive administrator adjustments write a small notification object into the existing `CreditTransaction.metadata_json` field. A recipient-only dismissal route records `dismissedAt` in the same metadata. The creator auth store retains transactions from the existing credits endpoint, and pure frontend notice helpers select and format the next undismissed grant.

**Tech Stack:** FastAPI, SQLAlchemy, Vue 3 Composition API, TypeScript, Vitest, pytest, Playwright.

---

## File Structure

- `server/app/credit_service.py`: Create and dismiss transaction-backed grant notifications.
- `server/app/main.py`: Mark individual/batch adjustments with delivery metadata and expose the dismissal route.
- `server/tests/test_admin_backend.py`: Cover notification metadata, recipient-only dismissal, and batch delivery.
- `fronted/src/api.ts`: Call the dismissal route.
- `fronted/src/api.test.ts`: Assert the CSRF-protected dismissal request.
- `fronted/src/stores/auth.ts`: Retain transaction snapshots and dismiss/reload notices.
- `fronted/src/creditNotices.ts`: Select and format pending grant notices.
- `fronted/src/creditNotices.test.ts`: Test notice selection and wording without rendering Vue.
- `fronted/src/App.vue`: Render and dismiss the top-of-workspace snackbar and refresh credits on an interval.
- `fronted/src/styles.css`: Position the snackbar below the workspace topbar with desktop/mobile constraints.

### Task 1: Add Failing Transaction Notice Tests

**Files:**
- Modify: `server/tests/test_admin_backend.py`
- Test: `server/tests/test_admin_backend.py`

- [ ] **Step 1: Write failing individual and batch notification tests**

After an individual positive `POST /api/admin/users/{user_id}/credits/adjust`, assert:

```python
transaction = response.json()["transaction"]
assert transaction["metadata"]["notification"] == {
    "kind": "admin_credit_grant",
    "delivery": "single",
    "dismissedAt": None,
}
```

Post a batch adjustment and assert each successful recipient has a latest transaction whose notification `delivery` is `"batch"`. Log in as the recipient, dismiss the individual transaction, and assert the latest credit payload now contains a non-empty `dismissedAt`. A second user must receive 404 when attempting to dismiss that transaction.

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `pytest server/tests/test_admin_backend.py -k credit_grant_notification -q`

Expected: FAIL because adjustment metadata lacks notification fields and no dismissal route exists.

- [ ] **Step 3: Commit the failing tests**

```powershell
git add server/tests/test_admin_backend.py
git commit -m "test: cover persistent credit grant notices"
```

### Task 2: Persist and Dismiss Grant Notices

**Files:**
- Modify: `server/app/credit_service.py:336-380,608-630`
- Modify: `server/app/main.py:2868-2880,3915-4035`
- Modify: `server/tests/test_admin_backend.py`
- Test: `server/tests/test_admin_backend.py`

- [ ] **Step 1: Implement notice metadata at the transaction source**

Extend `admin_adjust_credits` with a `notification_delivery` argument. For a positive amount and either `"single"` or `"batch"`, pass this metadata to `_add_transaction`:

```python
metadata={
    "notification": {
        "kind": "admin_credit_grant",
        "delivery": notification_delivery,
        "dismissedAt": None,
    },
}
```

Call the helper with `"single"` in the individual admin route and `"batch"` inside the batch loop. Keep all existing account, audit-log, and failure behavior unchanged.

- [ ] **Step 2: Add a recipient-only dismissal helper and route**

Add `dismiss_credit_grant_notification(db, user_id, transaction_id)` in `credit_service.py`. It must load the transaction, require the matching `user_id`, require a positive `admin_adjustment` with `notification.kind == "admin_credit_grant"`, set an ISO UTC `dismissedAt`, commit, refresh, and return the transaction. Use a 404 response for a missing, foreign, or non-notice transaction.

Add this CSRF-protected route:

```python
@app.post("/api/credits/notifications/{transaction_id}/dismiss")
async def dismiss_my_credit_notification(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    transaction = dismiss_credit_grant_notification(db, user_id=current_user.id, transaction_id=transaction_id)
    return {"transaction": serialize_credit_transaction(transaction)}
```

- [ ] **Step 3: Run the focused tests and verify they pass**

Run: `pytest server/tests/test_admin_backend.py -k credit_grant_notification -q`

Expected: PASS for individual metadata, batch metadata, recipient dismissal, and foreign-user rejection.

- [ ] **Step 4: Commit the server notification behavior**

```powershell
git add server/app/credit_service.py server/app/main.py server/tests/test_admin_backend.py
git commit -m "feat: persist credit grant notices"
```

### Task 3: Add Frontend Notice Selection, API, and Snackbar

**Files:**
- Create: `fronted/src/creditNotices.ts`
- Create: `fronted/src/creditNotices.test.ts`
- Modify: `fronted/src/api.ts:220-245`
- Modify: `fronted/src/api.test.ts`
- Modify: `fronted/src/stores/auth.ts:1-140`
- Modify: `fronted/src/App.vue:1-8,250-280,860-885,1080-1100,1790-1820,5280-5290`
- Modify: `fronted/src/styles.css`
- Test: `fronted/src/creditNotices.test.ts`
- Test: `fronted/src/api.test.ts`

- [ ] **Step 1: Write failing pure-helper and API tests**

Create notice fixtures in `creditNotices.test.ts` and assert:

```typescript
expect(nextCreditGrantNotice([dismissed, pendingBatch, pendingSingle])?.id).toBe(pendingBatch.id);
expect(creditGrantNoticeMessage(pendingSingle)).toBe("管理员赠送了 120 积分：活动奖励");
expect(creditGrantNoticeMessage(pendingBatch)).toBe("管理员批量赠送了 60 积分：补偿额度");
```

In `api.test.ts`, set a CSRF token, call `dismissCreditGrantNotice("credit-1")`, and assert a `POST` to `/api/credits/notifications/credit-1/dismiss` with credentials and the token header.

- [ ] **Step 2: Run the frontend tests and verify they fail**

Run: `npm test -- --run src/creditNotices.test.ts src/api.test.ts`

Working directory: `fronted`

Expected: FAIL because the helper module and dismissal API export do not exist.

- [ ] **Step 3: Implement pure helpers, API, and auth-store state**

Create a pure helper module that recognizes only positive `admin_adjustment` transactions with `metadata.notification.kind === "admin_credit_grant"` and a falsy `dismissedAt`. Sort by `createdAt` descending and return the newest. Format messages from amount, `delivery`, and trimmed reason.

Add `dismissCreditGrantNotice` using `postApi`. Add `creditTransactions` to the auth reactive state. Change `refreshCredits` to retain both `credits.account` and `credits.transactions`; add `dismissCreditGrantNotice(transactionId)` in the store that calls the API and refreshes credits.

- [ ] **Step 4: Render a persistent creator snackbar**

In `App.vue`, compute the current notice from `auth.state.creditTransactions`, add a close handler that awaits the auth-store dismissal action, and render a dedicated snackbar immediately after `.workspace-topbar`. Do not use the existing auto-hiding toast state. The snackbar includes its delivery label, message, and an icon-only close button with `aria-label="Close credit grant notice"`.

After `initializeSession` loads the user, call `auth.refreshCredits()`. Start one `window.setInterval` only for authenticated users at 30 seconds and clear it in the existing `onUnmounted` handler. The interval calls the existing quiet refresh function and must not show an error toast for a failed background poll.

Add styles at the end of `styles.css` that position the notice below the topbar, reserve a stable max width, use a contrast-safe success surface, and stack content at 640px without overlapping topbar actions.

- [ ] **Step 5: Run frontend tests and build**

Run: `npm test -- --run src/creditNotices.test.ts src/api.test.ts`

Working directory: `fronted`

Expected: PASS.

Run: `npm run build`

Working directory: `fronted`

Expected: exit 0.

- [ ] **Step 6: Commit the creator notification flow**

```powershell
git add fronted/src/creditNotices.ts fronted/src/creditNotices.test.ts fronted/src/api.ts fronted/src/api.test.ts fronted/src/stores/auth.ts fronted/src/App.vue fronted/src/styles.css
git commit -m "feat: show persistent credit grant notices"
```

### Task 4: Browser and Regression Verification

**Files:**
- Modify only if verification reveals a defect: files named in Tasks 2 and 3

- [ ] **Step 1: Verify the individual grant journey**

Grant credits in the admin app, sign in as the recipient in the creator app, and verify the top snackbar remains visible after a page interaction and disappears only after its close button is pressed.

- [ ] **Step 2: Verify the batch grant journey**

Grant credits to two recipients in one batch with a distinct reason. Verify each recipient sees batch wording and that the reason matches the administrator entry.

- [ ] **Step 3: Verify desktop and mobile layout with Playwright**

At 1440x960 and 390x844, confirm the snackbar appears below the workspace topbar, has a reachable close control, does not hide model controls, and wraps its text without overflow.

- [ ] **Step 4: Run final regression commands**

Run: `pytest server/tests/test_admin_backend.py -q`

Run: `npm test -- --run src/creditNotices.test.ts src/api.test.ts src/utils.test.ts src/styleApplication.test.ts`

Working directory: `fronted`

Run: `npm run build`

Working directories: `fronted`, then `admin`

Expected: every command exits 0.

- [ ] **Step 5: Commit any browser-verified correction**

```powershell
git add server admin fronted
git commit -m "fix: polish credit grant notice delivery"
```
