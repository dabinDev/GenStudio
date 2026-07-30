# NewUI Polish and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine every live GenStudio interface, verify multi-reference and R2 workflows across desktop/mobile, and safely publish `newui` to production.

**Architecture:** Preserve the existing application structure and consolidate final visual rules in the established stylesheets. Add deterministic browser smoke coverage around route state and new asset interactions. Release from a traceable commit using the existing backup-first Guangzhou runbook.

**Tech Stack:** Vue 3, CSS, Vitest, Playwright, Node smoke scripts, Docker, FastAPI, Nginx

---

### Task 1: Define complete route and UI-state contracts

**Files:**
- Create: `fronted/src/newuiPresentation.test.ts`
- Create: `admin/src/newuiPresentation.test.ts`
- Modify: `fronted/src/App.vue`
- Modify: `admin/src/router/index.ts`

- [ ] **Step 1: Write failing source contracts**

Frontend contract lists `auth`, `text`, `images`, `videos`, `settings`, and `profile` and asserts each has a page heading, primary action, loading state, empty/error state hook, and stable `data-testid`. Admin contract lists dashboard, models, prompt center, records, credits, system settings, audit logs, and forbidden, asserting a route title and main landmark for each.

- [ ] **Step 2: Run and verify RED**

Run frontend: `npm test -- newuiPresentation.test.ts`

Run admin: `npm test -- newuiPresentation.test.ts`

Expected: failures identify missing stable hooks and states.

- [ ] **Step 3: Add semantic landmarks and stable hooks**

Add `main`, `aria-labelledby`, concise headings, `aria-live` for request feedback, and route-specific `data-testid` values. Do not add visible instructional copy or marketing sections.

- [ ] **Step 4: Run and verify GREEN**

Run both focused tests again.

Expected: all route contracts pass.

- [ ] **Step 5: Commit**

```powershell
git add fronted/src/newuiPresentation.test.ts admin/src/newuiPresentation.test.ts fronted/src/App.vue admin/src/router/index.ts
git commit -m "test: define newui interface contracts"
```

### Task 2: Refine creator interfaces

**Files:**
- Modify: `fronted/src/App.vue`
- Modify: `fronted/src/styles.css`
- Modify: `fronted/src/workbenchRedesign.css`
- Modify: `fronted/src/styleApplication.test.ts`

- [ ] **Step 1: Add failing visual-rule assertions**

Assert the final cascade defines stable min/max sizes for navigation, message media, reference strips, mention menu, composer controls, settings rows, profile form, dialogs, toast, and mobile layouts. Assert `prefers-reduced-motion`, visible focus, text overflow, and safe-area rules exist, and no decorative orb selector is introduced.

- [ ] **Step 2: Run and verify RED**

Run: `npm test -- styleApplication.test.ts newuiPresentation.test.ts`

Expected: FAIL on the missing final rules.

- [ ] **Step 3: Implement creator polish**

Use neutral page surfaces with capability accent only on identity and actions. Keep cards at 8 px or less. Normalize field heights, message spacing, asset aspect ratios, toolbar wrapping, popover placement, upload progress, empty/error states, settings menu layering, profile validation, and 390 px composer stacking. Remove conflicting duplicate declarations only when the focused tests and browser screenshots prove the final cascade.

- [ ] **Step 4: Run focused tests and build**

Run: `npm test -- styleApplication.test.ts newuiPresentation.test.ts referenceMentions.test.ts`

Run: `npm run build`.

Expected: tests and build pass.

- [ ] **Step 5: Commit**

```powershell
git add fronted/src/App.vue fronted/src/styles.css fronted/src/workbenchRedesign.css fronted/src/styleApplication.test.ts
git commit -m "style: refine creator interfaces"
```

### Task 3: Refine admin interfaces

**Files:**
- Modify: `admin/src/layouts/AdminLayout.vue`
- Modify: `admin/src/views/DashboardView.vue`
- Modify: `admin/src/views/ModelCenterView.vue`
- Modify: `admin/src/views/PromptCenterView.vue`
- Modify: `admin/src/views/RecordsView.vue`
- Modify: `admin/src/views/UserCreditsView.vue`
- Modify: `admin/src/views/SystemSettingsView.vue`
- Modify: `admin/src/views/AuditLogsView.vue`
- Modify: `admin/src/views/ForbiddenView.vue`
- Modify: `admin/src/styles/global.css`
- Modify: `admin/src/adminThemePresentation.test.ts`
- Modify: `admin/src/views/adminContent.test.ts`

- [ ] **Step 1: Add failing admin detail assertions**

Assert consistent page headers, filter bars, table empty/loading/error states, row action labels, dialog footer behavior, image thumbnails, long-text truncation, mobile table overflow, reduced motion, and status-only color usage for every listed view.

- [ ] **Step 2: Run and verify RED**

Run: `npm test -- adminThemePresentation.test.ts views/adminContent.test.ts newuiPresentation.test.ts`

Expected: FAIL with concrete missing selectors/markup.

- [ ] **Step 3: Implement admin polish**

Keep the console dense and utilitarian. Use full-width sections, one-level metric items, sticky filter/action zones only where they improve repeated work, predictable table row heights, 6-8 px radii, icon buttons with existing Element Plus icons/tooltips, and mobile horizontal scrolling instead of squeezed unreadable columns.

- [ ] **Step 4: Run focused tests and build**

Run the focused tests, then `npm run build` from `admin/`.

Expected: tests and build pass.

- [ ] **Step 5: Commit**

```powershell
git add admin/src/layouts/AdminLayout.vue admin/src/views admin/src/styles/global.css admin/src/adminThemePresentation.test.ts admin/src/views/adminContent.test.ts
git commit -m "style: refine admin interfaces"
```

### Task 4: Browser workflow and responsive verification

**Files:**
- Create: `scripts/newui-browser-smoke.mjs`
- Create: `scripts/newui-browser-smoke.test.mjs`
- Modify: `docs/OPERATIONS.md`

- [ ] **Step 1: Write the failing smoke-script unit tests**

Test exported route matrices, viewports `[1440x900, 1024x768, 390x844]`, console-error filtering, overflow assertions, reference upload fixtures, `@10` insertion, thumbnail checks, and screenshot naming without launching production.

- [ ] **Step 2: Run and verify RED**

Run: `node --test scripts/newui-browser-smoke.test.mjs`

Expected: FAIL because the script does not exist.

- [ ] **Step 3: Implement deterministic Playwright smoke**

Reuse the existing local dev-login and smoke helpers. Cover creator text/image/video/settings/profile and all admin routes in light/dark themes. For image/video, upload 10 generated fixture images, assert badges 1 and 10, select `@10`, remove image 2, verify rewrite, and confirm no request is sent with invalid tokens. Assert every page has no horizontal document overflow, no visible overlap from bounding boxes, nonblank media pixels, and no unexpected console/page errors.

- [ ] **Step 4: Run local services and smoke**

Start FastAPI on an unused localhost port, frontend on 5175 or next free port, and admin on 5174 or next free port. Run the smoke script and preserve screenshots under ignored `output/newui-smoke/<timestamp>/`.

Expected: every route/viewport/theme passes.

- [ ] **Step 5: Visually inspect screenshots**

Use the local image viewer for representative creator and admin desktop/mobile screenshots. Correct clipping, text overflow, overlap, blank thumbnails, or inconsistent spacing, then rerun the complete smoke.

- [ ] **Step 6: Commit**

```powershell
git add scripts/newui-browser-smoke.mjs scripts/newui-browser-smoke.test.mjs docs/OPERATIONS.md fronted/src admin/src
git commit -m "test: add newui browser smoke coverage"
```

### Task 5: Complete local release gate

**Files:**
- Verify only

- [ ] **Step 1: Run every automated test suite**

Run `npm test` in `fronted/` and `admin/`, `python -m pytest` in `server/`, and `node --test scripts/*.test.mjs` from the repo root.

Expected: zero failures.

- [ ] **Step 2: Run production builds and compilation**

Run `npm run build` in both frontend projects, `python -m compileall server`, and `docker build -f server/Dockerfile -t genstudio-api:newui .`.

Expected: every command exits 0.

- [ ] **Step 3: Run isolated R2 integration**

Using production-compatible credentials from the environment without printing them, upload an original and thumbnail under a unique `genstudio/test/<uuid>/` prefix, HEAD and publicly read both, exercise the 24-hour resolver with a test database row, then delete only the two test objects.

Expected: upload/read/delete checks pass and no production asset is modified.

- [ ] **Step 4: Re-run browser smoke against production builds**

Serve built assets behind the same-domain Docker preview and run all viewport/theme flows.

Expected: zero browser failures and zero unexpected console errors.

- [ ] **Step 5: Verify source state**

Run: `git diff --check`, `git status --short`, and inspect `git diff origin/main...HEAD --stat`.

Expected: only intended source/docs changes; no secrets, build output, logs, databases, or screenshots tracked.

### Task 6: Commit and push the release candidate

**Files:**
- Modify: `RELEASE_VERSION`

- [ ] **Step 1: Record the release version**

Set a date-based version containing `newui` and record the verified commit in operations notes without including credentials.

- [ ] **Step 2: Re-run the smallest proof affected by version metadata**

Run both Vite builds and backend health/config tests.

Expected: builds and tests pass.

- [ ] **Step 3: Commit and push**

```powershell
git add RELEASE_VERSION docs/OPERATIONS.md
git commit -m "chore: prepare newui release"
git push origin newui
```

Expected: remote `newui` equals local HEAD.

### Task 7: Backup-first Guangzhou deployment

**Files:**
- Use: `deploy/remote-brand-deploy.sh`
- Use: `docs/OPERATIONS.md`

- [ ] **Step 1: Resolve exact production state read-only**

Check public health/version, remote disk space, running `genstudio-api` image/container, Nginx config syntax, deployed frontend asset hashes, and migration 009 absence/presence. Do not print `.env`.

- [ ] **Step 2: Create and verify backups**

Back up the production database, secret-key companion metadata, `/opt/genstudio/server`, both static roots, deploy configuration, and current image/version. Verify the database dump is nonempty and can list its schema/catalog before continuing.

- [ ] **Step 3: Apply migration and deploy traceable artifacts**

Build local static assets and backend image/release package from the pushed SHA. Upload with the documented Guangzhou key, verify checksums, apply migration 009 once, and run the existing remote deploy helper. Do not build from an uncommitted remote checkout.

- [ ] **Step 4: Verify production**

Check health/database/storage/version, login, creator and admin static assets, all main routes, no migration/fatal errors, sync worker start, R2 original/thumbnail test object, and a generated asset's local/R2 delivery state. Run the online smoke scripts and inspect desktop/mobile screenshots.

- [ ] **Step 5: Roll back on any gate failure**

Restore previous static/server artifacts and image first. Restore the database only if migration/data integrity is the cause and the verified backup is required. Re-run health/login checks after rollback.

- [ ] **Step 6: Record release evidence**

Append deployment timestamp, commit SHA, backup location, image ID, migration result, health/smoke counts, and rollback identifier to `docs/OPERATIONS.md` without secrets; commit and push the release record to `newui`.
