# Admin Console Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the admin console layout so data, filters, lists, and actions have clear hierarchy without changing backend behavior.

**Architecture:** Keep the current Vue single-file structure and add a final admin-specific visual layer. Use small template class additions for command bars and compact record summaries, while preserving existing state, API calls, and actions.

**Tech Stack:** Vue 3, TypeScript, CSS, Vitest, Vite.

---

### Task 1: Lock Admin Structure Expectations

**Files:**
- Modify: `fronted/src/adminPresentation.test.ts`

- [x] Add tests that assert the admin page has the new command-center classes, compact record cards, and a final v11 CSS layer.
- [x] Run `npm test -- adminPresentation.test.ts` from `fronted`; expected first run fails until implementation is added.

### Task 2: Normalize Admin Presentation Metadata

**Files:**
- Modify: `fronted/src/adminPresentation.ts`

- [x] Replace mojibake labels, hints, group titles, and suggestions with readable Chinese.
- [x] Keep the same `AdminTab` values so routing and data loading stay unchanged.

### Task 3: Rebalance Admin Template Layout

**Files:**
- Modify: `fronted/src/App.vue`

- [x] Add `admin-console-dashboard`, `admin-command-panel`, `admin-list-shell`, and compact record classes.
- [x] Merge model/user/audit filters and secondary actions into command panels.
- [x] Keep all existing buttons and handlers wired to the same functions.
- [x] Clamp record prompt/response previews through CSS classes instead of changing data.

### Task 4: Add Final Admin Visual Layer

**Files:**
- Modify: `fronted/src/styles.css`

- [x] Add `Creative Workshop admin command center v11`.
- [x] Make admin content use a two-tier hierarchy: compact header, command bar, dense list area, optional detail drawer.
- [x] Reduce repeated card weight, shrink metrics, and make records scan-friendly.
- [x] Apply both light and dark mode with readable contrast and no purple accent.

### Task 5: Verify

**Commands:**
- `cd fronted; npm test -- adminPresentation.test.ts`
- `cd fronted; npm test`
- `cd fronted; npm run build`

**Browser Checks:**
- Open `http://127.0.0.1:5175/#/admin`.
- Check overview, public models, users, image records, and audit in light and dark mode.
- Confirm first screen prioritizes the main data area and record cards no longer expand into long prompt blocks.

**Completion Note:** Implemented and verified on 2026-06-10. The production deployment later replaced online data with the cleaned local database and confirmed `https://studio.cylonai.cn/api/health` returned `ok`.
