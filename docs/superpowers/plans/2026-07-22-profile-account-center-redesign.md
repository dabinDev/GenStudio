# Profile Account Center Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat profile view with a compact, responsive account center while preserving all existing account behavior.

**Architecture:** Keep the current Vue state and event handlers in `App.vue`, but reorganize the profile template into identity, metrics, details, security, danger, and callback regions. Give those regions dedicated `profile-account-*` selectors in the final ownership stylesheet so generic settings/model rules cannot control profile layout.

**Tech Stack:** Vue 3 SFC template, CSS, Vitest source-contract tests, Vite, Docker, browser-based responsive QA.

---

### Task 1: Lock The Structure With A Failing Test

**Files:**
- Modify: `fronted/src/styleApplication.test.ts`
- Test: `fronted/src/styleApplication.test.ts`

- [ ] **Step 1: Replace the narrow button test with an account-center contract**

```ts
it("gives the profile view a dedicated responsive account-center layout", () => {
  const source = appVue();
  const styles = redesignCss();

  expect(source).toContain("profile-account-header");
  expect(source).toContain("profile-account-metrics");
  expect(source).toContain("profile-account-workspace");
  expect(source).toContain("profile-account-details");
  expect(source).toContain("profile-account-security");
  expect(source).toContain("profile-account-danger");
  expect(source).not.toContain('class="settings-row-actions profile-editor-actions"');
  expect(styles).toContain("Profile account center v1");
  expect(styles).toContain("grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.75fr) !important");
  expect(styles).toContain("white-space: nowrap !important");
  expect(styles).toContain("@media (max-width: 860px)");
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `npm test -- src/styleApplication.test.ts`

Expected: FAIL because the new structure and stylesheet marker do not exist.

### Task 2: Reorganize The Profile Template

**Files:**
- Modify: `fronted/src/App.vue:4771`
- Test: `fronted/src/styleApplication.test.ts`

- [ ] **Step 1: Replace the profile hero and stat panels with identity and metric regions**

```vue
<header class="profile-account-header">
  <div class="profile-account-identity">
    <div class="profile-avatar">{{ profileAvatarLabel }}</div>
    <div class="profile-account-copy">
      <p class="eyebrow">账户中心</p>
      <h2>个人信息</h2>
      <strong>{{ profileDisplayName }}</strong>
      <span>{{ userAccountLabel }}</span>
    </div>
  </div>
  <div class="profile-account-credit credit-balance">
    <span>可用积分</span>
    <strong>{{ auth.state.user ? formatCredits(availableCredits) : "-" }}</strong>
    <small v-if="reservedCredits">预扣 {{ formatCredits(reservedCredits) }}</small>
  </div>
</header>
<section class="profile-account-metrics" aria-label="账户概览">
  <!-- Preserve the existing user ID, saved models, configured models, and history values. -->
</section>
```

- [ ] **Step 2: Create a two-column workspace with independent actions**

```vue
<section class="profile-account-workspace">
  <section class="profile-account-panel profile-account-details">
    <!-- Preserve the existing profile fields, messages, and save handler. -->
    <div class="profile-account-panel-actions">
      <button :disabled="!auth.state.user || auth.state.loading" @click="handleProfileSave">保存资料</button>
    </div>
  </section>
  <aside class="profile-account-side">
    <section class="profile-account-panel profile-account-security">
      <!-- Preserve the password fields, messages, and handler. -->
    </section>
    <section class="profile-account-danger">
      <div><strong>退出当前账号</strong><span>退出后需要重新授权登录。</span></div>
      <button v-if="auth.state.user" class="button-danger" :disabled="auth.state.loading" @click="handleLogout">退出登录</button>
      <button v-else @click="navigate('auth')">去登录</button>
    </section>
  </aside>
</section>
```

- [ ] **Step 3: Preserve callback behavior below the workspace**

Change only its wrapper to `profile-account-callback`; retain `showDevAuth`, `handleAuthCodeLogin`, and `refreshConversations`.

- [ ] **Step 4: Run the focused test**

Run: `npm test -- src/styleApplication.test.ts`

Expected: template assertions pass; stylesheet assertions remain red.

### Task 3: Add The Dedicated Responsive Visual Layer

**Files:**
- Modify: `fronted/src/workbenchRedesign.css`
- Test: `fronted/src/styleApplication.test.ts`

- [ ] **Step 1: Add desktop account-center rules after generic settings rules**

```css
/* Profile account center v1 */
.shell .profile-page {
  gap: 14px !important;
  padding: 18px 20px 30px !important;
}

.shell .profile-account-header,
.shell .profile-account-metrics,
.shell .profile-account-workspace,
.shell .profile-account-callback {
  width: min(1180px, 100%) !important;
  margin: 0 auto !important;
}

.shell .profile-account-workspace {
  display: grid !important;
  grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.75fr) !important;
  gap: 14px !important;
  align-items: start !important;
}

.shell .profile-account-panel-actions button,
.shell .profile-account-security button,
.shell .profile-account-danger button {
  white-space: nowrap !important;
}
```

Complete the section with restrained borders, neutral surfaces, 8px radii, clear typography, a four-column metric strip, a distinct credit balance, a two-column details form, and a separated danger area. Use existing variables for dark theme compatibility.

- [ ] **Step 2: Add tablet and mobile rules**

```css
@media (max-width: 860px) {
  .shell .profile-account-workspace {
    grid-template-columns: minmax(0, 1fr) !important;
  }

  .shell .profile-account-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  }
}
```

At `720px`, stack header content and form fields, keep the compact 2-by-2 metric grid, make commands full-width where needed, and prevent horizontal overflow.

- [ ] **Step 3: Run the focused test and verify GREEN**

Run: `npm test -- src/styleApplication.test.ts`

Expected: all tests in the file pass.

### Task 4: Verify The Real Page And Regressions

**Files:**
- Modify only after a reproduced defect: `fronted/src/App.vue`, `fronted/src/workbenchRedesign.css`, `fronted/src/styleApplication.test.ts`

- [ ] **Step 1: Run complete frontend tests and build**

Run: `npm test`

Expected: all frontend tests pass.

Run: `npm run build`

Expected: TypeScript and Vite production build complete without errors.

- [ ] **Step 2: Inspect the real page**

Check the profile route at 1440x900 and 390x844 in light and dark themes. Confirm hierarchy, no wrapped actions, no overlap, no horizontal overflow, and functional fields/buttons.

- [ ] **Step 3: Run the required local Docker build**

Build the existing frontend production image as `genstudio-fronted:qa` and confirm the production assets exist in the image.

### Task 5: Review, Commit, Publish, And Verify

**Files:**
- Commit: `fronted/src/App.vue`
- Commit: `fronted/src/workbenchRedesign.css`
- Commit: `fronted/src/styleApplication.test.ts`

- [ ] **Step 1: Review and verify the scoped diff**

Run: `git diff --check`

Expected: no whitespace errors.

Run: `npm test -- src/styleApplication.test.ts`

Expected: focused tests pass.

- [ ] **Step 2: Commit and push**

```powershell
git add -- fronted/src/App.vue fronted/src/workbenchRedesign.css fronted/src/styleApplication.test.ts
git commit -m "style: redesign profile account center"
git push origin codex/v3-admin-console-redesign
```

- [ ] **Step 3: Publish only frontend static assets**

Back up the production frontend directory, upload the new `fronted/dist`, and leave `genstudio-api` and `genstudio-mysql` untouched.

- [ ] **Step 4: Verify production**

Confirm new asset hashes from `https://studio.cylonai.cn`, inspect the live profile route, check `/api/health`, and confirm API/MySQL restart counts did not change.
