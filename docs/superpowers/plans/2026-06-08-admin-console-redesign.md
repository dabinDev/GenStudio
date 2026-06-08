# Admin Console Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the GenStudio admin console layout into a compact operational backend inspired by Sub2API while preserving existing admin APIs and behavior.

**Architecture:** Keep the existing Vue single-file app structure, but extract admin presentation metadata into a small TypeScript module so navigation and page suggestions are testable. Change only frontend admin template and CSS unless a compile issue reveals a missing type.

**Tech Stack:** Vue 3 SFC, TypeScript, Vite, Vitest, CSS.

---

### Task 1: Admin Presentation Metadata

**Files:**
- Create: `fronted/src/adminPresentation.ts`
- Create: `fronted/src/adminPresentation.test.ts`
- Modify: `fronted/src/App.vue`

- [ ] **Step 1: Write failing metadata tests**

Create `fronted/src/adminPresentation.test.ts` to assert that admin tabs are grouped once, each page has at least three suggestions, and record pages resolve to their capabilities.

- [ ] **Step 2: Run targeted test to verify failure**

Run: `cd fronted; npm test -- adminPresentation.test.ts`
Expected: FAIL because `fronted/src/adminPresentation.ts` does not exist.

- [ ] **Step 3: Create metadata module**

Create `fronted/src/adminPresentation.ts` exporting admin tabs, nav groups, icon keys, page suggestions, and record capability mapping.

- [ ] **Step 4: Run targeted test to verify pass**

Run: `cd fronted; npm test -- adminPresentation.test.ts`
Expected: PASS.

### Task 2: Admin Template Layout

**Files:**
- Modify: `fronted/src/App.vue`

- [ ] **Step 1: Import metadata from `adminPresentation.ts`**

Replace inline admin tab/nav declarations with imports from the tested module.

- [ ] **Step 2: Rework admin shell markup**

Update the admin section to use a standalone console shell with navigation icons, topbar status, page action slot, and per-page suggestion strip.

- [ ] **Step 3: Rework page bodies**

Keep existing API calls and state. Reshape models, prompts, users, records, and audit templates into table/tool/detail structures without changing save, publish, filter, or load handlers.

### Task 3: Admin Console Styling

**Files:**
- Modify: `fronted/src/styles.css`

- [ ] **Step 1: Replace admin CSS block**

Replace the current admin console CSS with a clearer backend visual system: sidebar, topbar, KPI cards, table surfaces, media records, prompt editor, responsive behavior.

- [ ] **Step 2: Check responsive constraints**

Ensure desktop uses dense table layouts and mobile collapses to one-column panels without text overlap.

### Task 4: Verification

**Files:**
- No production files expected unless verification finds a defect.

- [ ] **Step 1: Run frontend tests**

Run: `cd fronted; npm test`
Expected: all tests pass.

- [ ] **Step 2: Run production build**

Run: `cd fronted; npm run build`
Expected: build exits 0.

- [ ] **Step 3: Browser screenshot all admin pages**

Open `http://127.0.0.1:5175/#/admin` or the available local port, log in if needed, and capture overview, models, prompts, users, text records, image records, video records, audit.

- [ ] **Step 4: Report optimization suggestions**

For each admin page, provide at least three next-step optimization suggestions based on screenshots.
