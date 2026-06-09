# Site Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the Creative Workshop UI into a clean white-first technology workspace with a restrained night mode, no purple-dominant styling, and clearer creative, settings, admin, and media preview surfaces.

**Architecture:** Keep the existing Vue single-file app and current routes. Refactor the visual system inside `fronted/src/styles.css` by adding a final tokenized design layer and replacing conflicting color accents, then make only small template/text adjustments in `fronted/src/App.vue` and `fronted/src/adminPresentation.ts` where visual structure or mojibake text blocks require it.

**Tech Stack:** Vue 3, Vite, TypeScript, CSS, Vitest, in-app browser verification.

---

## File Structure

- Modify `fronted/src/styles.css`: primary work. Add a final `Creative Workshop visual system v4` section that defines theme tokens, component styling, page styling, responsive rules, and removes purple visual dominance.
- Modify `fronted/src/App.vue`: only if needed for visible mojibake text, semantic labels, or small class hooks that make CSS cleaner. Do not change request logic.
- Modify `fronted/src/adminPresentation.ts`: repair admin tab labels, hints, nav group titles, and page suggestions if source text is mojibake.
- Modify `fronted/src/adminPresentation.test.ts`: add assertions that admin metadata is readable Chinese and does not contain mojibake placeholders.
- Modify `fronted/src/utils.test.ts` only if existing helper tests need a visual-contract assertion for theme naming or media preview sizing.
- Do not modify backend code for this visual pass.

---

### Task 1: Add Visual Contract Tests

**Files:**
- Modify: `fronted/src/adminPresentation.test.ts`
- Optional Modify: `fronted/src/utils.test.ts`

- [ ] **Step 1: Add a failing admin metadata readability test**

Append this test to `fronted/src/adminPresentation.test.ts`:

```ts
it("keeps admin labels and suggestions readable Chinese without mojibake", () => {
  const suspectPattern = /[�]|(?:鍒|绠|鐢|鎿|璋|妯|瑙|浣|闈|杩|瀹|宸|褰|澧|涓|嗘|傛)/;
  for (const tab of adminTabs) {
    expect(tab.label).not.toMatch(suspectPattern);
    expect(tab.hint).not.toMatch(suspectPattern);
  }
  for (const group of adminNavGroups) {
    expect(group.title).not.toMatch(suspectPattern);
  }
  for (const suggestions of Object.values(ADMIN_PAGE_SUGGESTIONS)) {
    expect(suggestions).toHaveLength(3);
    for (const suggestion of suggestions) {
      expect(suggestion).not.toMatch(suspectPattern);
      expect(suggestion.length).toBeGreaterThan(8);
    }
  }
});
```

- [ ] **Step 2: Run the focused test**

Run:

```powershell
cd fronted
npm test -- adminPresentation.test.ts
```

Expected before fixing metadata: fail if mojibake remains in `adminPresentation.ts`; pass if already repaired.

- [ ] **Step 3: Add a CSS source guard for purple accents**

Add this test to `fronted/src/adminPresentation.test.ts` so the visual pass cannot reintroduce purple progress colors:

```ts
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

it("does not use purple as the final video/admin progress accent", () => {
  const here = dirname(fileURLToPath(import.meta.url));
  const css = readFileSync(resolve(here, "styles.css"), "utf8");
  const finalLayer = css.split("Creative Workshop visual system v4").pop() || "";
  expect(finalLayer).not.toMatch(/#(?:7c3aed|8b5cf6|b78cff|a7a5ff)/i);
  expect(finalLayer).not.toMatch(/--studio-violet/);
});
```

- [ ] **Step 4: Run the focused test again**

Run:

```powershell
cd fronted
npm test -- adminPresentation.test.ts
```

Expected: fail until the final CSS layer is added and metadata is readable.

---

### Task 2: Repair Admin Presentation Metadata

**Files:**
- Modify: `fronted/src/adminPresentation.ts`
- Test: `fronted/src/adminPresentation.test.ts`

- [ ] **Step 1: Replace mojibake admin tab metadata**

Replace the `adminTabs`, `adminCapabilityTabs`, `adminRecordCapabilityTabs`, and `adminNavGroups` text with readable Chinese:

```ts
export const adminTabs: AdminTabDefinition[] = [
  { value: "overview", label: "运营面板", hint: "调用、失败率、公私模型分布", icon: "chart", tone: "blue" },
  { value: "models", label: "公用模型配置", hint: "发布、取消公用、图标、提示语", icon: "model", tone: "green" },
  { value: "prompts", label: "提示语模板", hint: "AI 文案优化模板", icon: "spark", tone: "cyan" },
  { value: "users", label: "用户管理", hint: "启用、禁用、删除、恢复", icon: "user", tone: "cyan" },
  { value: "text-records", label: "文案记录", hint: "提示词与响应追踪", icon: "text", tone: "slate" },
  { value: "image-records", label: "生图记录", hint: "图片结果与参数", icon: "image", tone: "amber" },
  { value: "video-records", label: "视频记录", hint: "任务、视频、失败原因", icon: "video", tone: "blue" },
  { value: "audit", label: "操作记录", hint: "管理员变更审计", icon: "audit", tone: "slate" },
];

export const adminCapabilityTabs: Array<{ value: Capability | "all"; label: string }> = [
  { value: "all", label: "全部" },
  { value: "text", label: "文案创作" },
  { value: "image", label: "图片创作" },
  { value: "video", label: "视频创作" },
];

export const adminRecordCapabilityTabs: Array<{ value: Capability; label: string; hint: string }> = [
  { value: "text", label: "文案", hint: "提问 / 回答" },
  { value: "image", label: "图片/图文", hint: "提示词 / 图片结果" },
  { value: "video", label: "视频", hint: "提示词 / 视频结果" },
];

export const adminNavGroups: Array<{ title: string; tabs: AdminTab[] }> = [
  { title: "总览", tabs: ["overview"] },
  { title: "模型资产", tabs: ["models", "prompts"] },
  { title: "用户与权限", tabs: ["users"] },
  { title: "创作记录", tabs: ["text-records", "image-records", "video-records"] },
  { title: "安全审计", tabs: ["audit"] },
];
```

- [ ] **Step 2: Replace `ADMIN_PAGE_SUGGESTIONS` with readable Chinese**

Keep exactly three suggestions per tab. Use this content:

```ts
export const ADMIN_PAGE_SUGGESTIONS: Record<AdminTab, string[]> = {
  overview: [
    "补充按日、按周、按月趋势，方便判断增长和异常波动。",
    "把失败率最高的模型联动到记录页，减少排查路径。",
    "增加额度消耗、平均排队时间和任务超时率，形成健康分。",
  ],
  models: [
    "支持批量设为公用、取消公用和批量启用提示优化。",
    "为图标 URL 增加预览和失败提示，避免上线后静默失效。",
    "把默认参数 JSON 改成结构化表单，同时保留高级模式。",
  ],
  prompts: [
    "增加模板版本历史，方便回滚效果不佳的提示语修改。",
    "把测试预览扩展为多样例测试，覆盖三类短提示词。",
    "增加模型级启用状态总览，避免模板存在但模型未启用。",
  ],
  users: [
    "增加用户详情侧栏，集中展示模型数、调用数和失败率。",
    "增加角色筛选和管理员变更确认，降低误操作风险。",
    "增加用户导出和最近登录 IP，便于运营和风控。",
  ],
  "text-records": [
    "支持提示词和回答关键词搜索，快速定位内容。",
    "支持保存常用筛选条件，方便重复排查同类问题。",
    "增加 Markdown 渲染开关，直接查看文案最终展示效果。",
  ],
  "image-records": [
    "增加图片瀑布流模式，快速扫描生成质量和失败样本。",
    "支持图片详情抽屉，展示原图、引用图和完整参数。",
    "增加按尺寸、比例、参考图数量筛选，定位参数异常。",
  ],
  "video-records": [
    "增加任务状态时间线，展示创建、轮询、成功或失败节点。",
    "支持视频在线播放和复制任务 ID，减少排查成本。",
    "增加按时长、分辨率、模式筛选，定位模型参数限制。",
  ],
  audit: [
    "增加高风险操作标记，例如删除用户和取消公用模型。",
    "增加按目标对象筛选，快速查看单个模型或用户变更历史。",
    "增加审计日志导出，满足上线后的追踪和备份需求。",
  ],
};
```

- [ ] **Step 3: Run focused tests**

Run:

```powershell
cd fronted
npm test -- adminPresentation.test.ts
```

Expected: admin metadata readability tests pass, CSS source guard may still fail until Task 3.

---

### Task 3: Create the Final Tokenized CSS Layer

**Files:**
- Modify: `fronted/src/styles.css`
- Test: `fronted/src/adminPresentation.test.ts`

- [ ] **Step 1: Add the final CSS layer marker and tokens**

Append a new final section to `fronted/src/styles.css` beginning with this exact marker:

```css
/* Creative Workshop visual system v4: white-first technology workspace. */
```

Add these root and light-mode tokens:

```css
:root {
  --cw-bg: #07111d;
  --cw-bg-soft: #0b1726;
  --cw-panel: rgba(13, 26, 42, 0.94);
  --cw-panel-solid: #0d1a2a;
  --cw-panel-soft: #112235;
  --cw-line: rgba(148, 188, 214, 0.18);
  --cw-line-strong: rgba(94, 234, 212, 0.34);
  --cw-text: #edf7ff;
  --cw-muted: #9fb3c8;
  --cw-muted-strong: #c7d8e8;
  --cw-brand: #12aaa2;
  --cw-brand-2: #1677f2;
  --cw-text-accent: #15c8bc;
  --cw-success: #13875c;
  --cw-warn: #a96904;
  --cw-danger: #cf344d;
  --cw-radius: 8px;
  --cw-shadow: 0 18px 48px rgba(0, 0, 0, 0.28);
  --cw-shadow-soft: 0 10px 26px rgba(0, 0, 0, 0.18);
}

:root[data-theme="light"] {
  color-scheme: light;
  --bg: #eef5f8;
  --panel: #ffffff;
  --panel-strong: #ffffff;
  --line: #dce6ef;
  --line-strong: #b8c9d8;
  --text: #122033;
  --muted: #667589;
  --muted-strong: #33495f;
  --accent: #12aaa2;
  --accent-strong: #1677f2;
  --danger: #cf344d;
  --cw-bg: #eef5f8;
  --cw-bg-soft: #f6f9fc;
  --cw-panel: #ffffff;
  --cw-panel-solid: #ffffff;
  --cw-panel-soft: #f8fbfd;
  --cw-line: #dce6ef;
  --cw-line-strong: #b8c9d8;
  --cw-text: #122033;
  --cw-muted: #667589;
  --cw-muted-strong: #33495f;
  --cw-shadow: 0 18px 48px rgba(31, 58, 85, 0.12);
  --cw-shadow-soft: 0 10px 26px rgba(31, 58, 85, 0.08);
}
```

- [ ] **Step 2: Normalize global background and button styling**

In the same final CSS section, add rules for `body`, `.shell`, `.shell-admin`, `button`, `.button-secondary`, `.button-danger`, `.badge`, `.parameter-source-chip`, `.model-tag`, `input`, `select`, and `textarea`. Keep the visual effect restrained:

```css
body {
  color: var(--cw-text);
  background: var(--cw-bg);
}

.shell,
.shell-admin {
  color: var(--cw-text);
  background:
    linear-gradient(90deg, rgba(22, 119, 242, 0.05) 1px, transparent 1px),
    linear-gradient(rgba(18, 170, 162, 0.035) 1px, transparent 1px),
    linear-gradient(135deg, var(--cw-bg-soft), var(--cw-bg));
  background-size: 40px 40px, 40px 40px, auto;
}

[data-theme="light"].shell,
[data-theme="light"].shell-admin {
  background:
    linear-gradient(90deg, rgba(32, 68, 105, 0.035) 1px, transparent 1px),
    linear-gradient(rgba(32, 68, 105, 0.026) 1px, transparent 1px),
    linear-gradient(135deg, #fbfdff 0%, #eef5f8 48%, #f6fbfa 100%);
  background-size: 40px 40px, 40px 40px, auto;
}
```

- [ ] **Step 3: Replace purple final accents**

In the new final section, explicitly override video/admin purple accents:

```css
.admin-progress-video,
[data-theme="light"] .admin-progress-video,
.admin-record-card-video::after {
  background: linear-gradient(90deg, #1677f2, #12aaa2) !important;
}

.history-kind-video {
  color: #0f4f73 !important;
  border-color: rgba(22, 119, 242, 0.28) !important;
  background: rgba(22, 119, 242, 0.1) !important;
}

[data-theme="light"] .history-kind-video {
  color: #155aa8 !important;
  border-color: #cfe0ff !important;
  background: #edf4ff !important;
}
```

- [ ] **Step 4: Run CSS guard test**

Run:

```powershell
cd fronted
npm test -- adminPresentation.test.ts
```

Expected: purple guard passes because the final layer contains no forbidden purple colors.

---

### Task 4: Restyle Creative Workspace and Composer

**Files:**
- Modify: `fronted/src/styles.css`

- [ ] **Step 1: Restyle sidebar and model rows**

In the final CSS layer, add rules for `.sidebar`, `.sidebar-logo`, `.logo-mark`, `.model-list`, `.sidebar-model-item`, `.sidebar-model-active`, `.sidebar-model-public`, `.model-avatar`, `.model-info`, `.sidebar-account`.

Use:

```css
.sidebar,
.admin-sidebar {
  border-color: var(--cw-line) !important;
  background: color-mix(in srgb, var(--cw-panel-solid) 94%, transparent) !important;
  box-shadow: 14px 0 34px rgba(31, 58, 85, 0.08) !important;
}

.sidebar-model-item {
  border-color: transparent !important;
  background: transparent !important;
  box-shadow: none !important;
}

.sidebar-model-active,
.sidebar-model-item:hover {
  border-color: rgba(18, 170, 162, 0.28) !important;
  background: color-mix(in srgb, var(--cw-panel-soft) 86%, white 14%) !important;
  box-shadow: inset 3px 0 0 var(--cw-brand) !important;
}
```

- [ ] **Step 2: Restyle canvas, empty state, messages**

Add final rules for `.studio-canvas`, `.empty-canvas-card`, `.conversation-header`, `.message-card`, `.message-user`, `.message-assistant`, `.message-assets`, `.message-asset-card`.

Ensure:
- empty title is no larger than 42px desktop and 30px mobile.
- message text uses `var(--cw-text)`.
- user message uses a light teal background in light mode, not saturated green.

- [ ] **Step 3: Restyle composer as a floating workbar**

Add final rules for `.composer-card`, `.composer-surface`, `.composer-toolbar`, `.composer-footer-bar`, `.composer-input`, `.prompt-ai-button`, `.composer-pill`, `.segmented-option`, `.reference-thumb`.

Ensure:
- desktop width remains `min(100%, 900px)`.
- border uses `rgba(18, 170, 162, 0.18)`.
- `.prompt-ai-button` is square-ish, does not dominate send button.
- `.composer-popover` is white/light in light mode and readable in night mode.

- [ ] **Step 4: Browser-check creative routes**

Use the in-app browser to inspect:

```text
https://studio.cylonai.cn/#/text
https://studio.cylonai.cn/#/images
https://studio.cylonai.cn/#/videos
```

Expected:
- no purple-dominant accents.
- input panel does not overpower the conversation area.
- model list remains readable with many models.

---

### Task 5: Restyle Settings Page

**Files:**
- Modify: `fronted/src/styles.css`
- Optional Modify: `fronted/src/App.vue`

- [ ] **Step 1: Make settings hero compact**

Add final rules for `.settings-page`, `.settings-hero`, `.settings-hero-stats`:

```css
.settings-hero {
  min-height: auto !important;
  padding: 22px 24px !important;
  border-color: var(--cw-line) !important;
  background: var(--cw-panel) !important;
  box-shadow: var(--cw-shadow-soft) !important;
}

.settings-hero h2 {
  font-size: clamp(28px, 3vw, 38px) !important;
  letter-spacing: 0 !important;
}
```

- [ ] **Step 2: Combine toolbar visual language**

Add rules for `.settings-list-toolbar`, `.settings-filter-bar`, `.settings-filter-tabs`, `.settings-filter-tab`, `.settings-search-box`, `.settings-bulk-actions`.

Expected:
- search and batch actions look like one tool system.
- no sticky toolbar overlays content.
- buttons have stable height.

- [ ] **Step 3: Simplify model row scanability**

Add rules for `.settings-model-board`, `.settings-board-head`, `.settings-model-row`, `.settings-model-row-public`, `.settings-model-main`, `.settings-model-meta-row`, `.settings-model-hint`, `.settings-row-actions`.

Expected:
- public model uses left accent and tag, not full teal fill.
- hint truncates to two lines.
- row actions wrap without horizontal overflow.

- [ ] **Step 4: Browser-check settings**

Use the in-app browser:

```text
https://studio.cylonai.cn/#/settings
```

Expected:
- top area is shorter.
- model rows are scannable.
- search and batch controls are not obscured.

---

### Task 6: Restyle Admin Console

**Files:**
- Modify: `fronted/src/styles.css`

- [ ] **Step 1: Constrain admin topbar height**

Add final rules:

```css
.admin-topbar {
  min-height: 72px !important;
  max-height: 88px !important;
  padding: 14px 24px !important;
  border-color: var(--cw-line) !important;
  background: color-mix(in srgb, var(--cw-panel-solid) 92%, transparent) !important;
  box-shadow: var(--cw-shadow-soft) !important;
}

.admin-content {
  padding-top: 18px !important;
}
```

- [ ] **Step 2: Restyle admin navigation**

Add final rules for `.admin-console`, `.admin-sidebar`, `.admin-sidebar-brand`, `.admin-sidebar-status`, `.admin-tabs`, `.admin-tab`, `.admin-tab-active`, `.admin-nav-icon`.

Expected:
- nav groups are clear.
- active item uses teal left accent.
- no purple icon tone.

- [ ] **Step 3: Restyle dashboard and cards**

Add rules for `.admin-section-head`, `.admin-insight-strip`, `.admin-metrics`, `.admin-metric`, `.admin-subpanel`, `.admin-mini-metrics`, `.admin-data-table`, `.admin-record-card`, `.admin-record-qa`, `.admin-record-json`.

Expected:
- KPI cards are calmer.
- record pages show prompt/response first.
- JSON stays visually secondary.

- [ ] **Step 4: Browser-check all admin tabs**

Use the in-app browser to open `https://studio.cylonai.cn/#/admin`, then inspect these tabs:

- 运营面板
- 公用模型配置
- 提示语模板
- 用户管理
- 文案记录
- 生图记录
- 视频记录
- 操作记录

Expected:
- topbar does not cover filters.
- record filters are readable.
- no page has text on too-similar backgrounds.

---

### Task 7: Restyle Media Preview and Theme Toggle

**Files:**
- Modify: `fronted/src/styles.css`
- Test: `fronted/src/utils.test.ts`

- [ ] **Step 1: Keep media preview full-screen and clean**

Add final rules for `.media-preview-backdrop`, `.media-preview-panel`, `.media-preview-actions`, `.media-preview-button-row`, `.media-preview-stage`, `.media-icon-button`, `.media-action-button`, `.media-scale-button`.

Expected:
- panel is full viewport.
- controls are in a top strip.
- SVG icons stay square with `width`, `height`, `aspect-ratio`, and `flex: 0 0`.
- image area is not blocked by the composer.

- [ ] **Step 2: Restyle theme toggle**

Add final rules for `.theme-toggle-button`, `.theme-toggle-track`, `.theme-toggle-light`, `.theme-toggle-dark`.

Expected:
- light mode toggle reads as a small utility control.
- night mode toggle does not use purple.

- [ ] **Step 3: Run existing media preview helper tests**

Run:

```powershell
cd fronted
npm test -- utils.test.ts -t "media preview helpers"
```

Expected: pass.

---

### Task 8: Responsive and Accessibility Pass

**Files:**
- Modify: `fronted/src/styles.css`

- [ ] **Step 1: Add mobile layout rules**

Add final `@media (max-width: 980px)` and `@media (max-width: 640px)` rules covering:

- `.shell`
- `.sidebar`
- `.workspace-topbar`
- `.studio-canvas`
- `.composer-card`
- `.settings-board-head`
- `.settings-model-row`
- `.admin-console`
- `.admin-topbar`
- `.admin-content`
- `.admin-record-toolbar`
- `.media-preview-actions`

Expected:
- no horizontal overflow on 390px width.
- toolbar controls wrap.
- composer remains usable.

- [ ] **Step 2: Add reduced motion guard**

Ensure decorative background movement is disabled:

```css
@media (prefers-reduced-motion: reduce) {
  .shell::before,
  .shell-admin .admin-page::before {
    animation: none !important;
  }
}
```

- [ ] **Step 3: Browser-check mobile**

Use the browser viewport capability or Playwright viewport if available to inspect:

- `#/images` at 390x844
- `#/settings` at 390x844
- `#/admin` at 390x844

Expected:
- no incoherent overlap.
- no horizontal scroll caused by rows or toolbars.

---

### Task 9: Full Verification

**Files:**
- No code changes unless verification reveals a defect.

- [ ] **Step 1: Run frontend tests**

Run:

```powershell
cd fronted
npm test
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend production build**

Run:

```powershell
cd fronted
npm run build
```

Expected: build succeeds.

- [ ] **Step 3: Start or reuse local frontend**

If no dev server is running, run:

```powershell
cd fronted
npm run dev -- --host 127.0.0.1
```

Expected: Vite prints a local URL.

- [ ] **Step 4: Browser-check desktop routes**

Inspect:

- `http://127.0.0.1:5175/#/text`
- `http://127.0.0.1:5175/#/images`
- `http://127.0.0.1:5175/#/videos`
- `http://127.0.0.1:5175/#/settings`
- `http://127.0.0.1:5175/#/admin`

Expected:
- white mode looks professional and readable.
- night mode remains readable.
- no purple-dominant final accents.
- admin topbar does not obscure filters.
- media preview controls are not distorted.

- [ ] **Step 5: Commit implementation**

Run:

```powershell
git status --short
git add fronted/src/styles.css fronted/src/App.vue fronted/src/adminPresentation.ts fronted/src/adminPresentation.test.ts fronted/src/utils.test.ts
git commit -m "Polish Creative Workshop visual system"
```

Only include files actually changed. Do not add `tmp/`.

---

## Self-Review

- Spec coverage: tasks cover tokens, purple removal, creative pages, settings, admin, media preview, responsive checks, metadata readability, and verification.
- Placeholder scan: no task asks for unspecified "nice styling"; each task names files, selectors, and expected outcomes.
- Type consistency: metadata tests use existing `adminTabs`, `adminNavGroups`, and `ADMIN_PAGE_SUGGESTIONS`; CSS guard reads the final layer marker introduced in Task 3.
