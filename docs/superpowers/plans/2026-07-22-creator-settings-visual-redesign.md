# Creator Settings Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the settings model action menu stacking defect and deliver a cohesive dual-theme visual redesign for settings, text, image, and video creation surfaces.

**Architecture:** Keep the existing Vue business state and API flow intact. Extract deterministic floating-menu decisions into a small tested utility, bind explicit menu state and model accent variables in `App.vue`, and load a dedicated `workbenchRedesign.css` after the legacy stylesheet so the redesign has one clear ownership layer.

**Tech Stack:** Vue 3 Composition API, TypeScript, CSS custom properties, Vitest, Vite, Playwright CLI, Docker Compose/Nginx.

---

## File Map

- Create `fronted/src/modelActionMenu.ts`: pure helpers for menu toggle and vertical placement.
- Create `fronted/src/modelActionMenu.test.ts`: unit tests for action-menu behavior.
- Create `fronted/src/workbenchRedesign.css`: final visual ownership layer for settings and creator pages.
- Modify `fronted/src/App.vue`: explicit action-menu state, active model accent binding, and semantic creator/settings markup.
- Modify `fronted/src/main.ts`: load the redesign stylesheet after `styles.css`.
- Modify `fronted/src/utils.ts`: expose the default/private model accent resolver.
- Modify `fronted/src/utils.test.ts`: test public and private model color resolution.
- Modify `fronted/src/styleApplication.test.ts`: structural and stylesheet contract tests for the redesigned UI.

### Task 1: Test and Implement Floating Menu Decisions

**Files:**
- Create: `fronted/src/modelActionMenu.test.ts`
- Create: `fronted/src/modelActionMenu.ts`

- [ ] **Step 1: Write failing tests for toggle and placement behavior**

```ts
import { describe, expect, it } from "vitest";

import { modelActionMenuPlacement, toggledModelActionMenuId } from "./modelActionMenu";

describe("model action menu", () => {
  it("opens one model and closes it when the same trigger is pressed again", () => {
    expect(toggledModelActionMenuId("", "image-flux")).toBe("image-flux");
    expect(toggledModelActionMenuId("image-flux", "image-flux")).toBe("");
    expect(toggledModelActionMenuId("image-flux", "video-veo")).toBe("video-veo");
  });

  it("opens upward only when the lower viewport cannot fit the menu", () => {
    expect(modelActionMenuPlacement({ top: 680, bottom: 716 }, 800, 180)).toBe("up");
    expect(modelActionMenuPlacement({ top: 220, bottom: 256 }, 800, 180)).toBe("down");
    expect(modelActionMenuPlacement({ top: 80, bottom: 116 }, 240, 180)).toBe("down");
  });
});
```

- [ ] **Step 2: Run the new test and verify RED**

Run: `npm test -- modelActionMenu.test.ts`

Expected: FAIL because `./modelActionMenu` does not exist.

- [ ] **Step 3: Implement the pure helpers**

```ts
export type ModelActionMenuPlacement = "down" | "up";

export type TriggerBounds = Pick<DOMRect, "bottom" | "top">;

export function toggledModelActionMenuId(currentId: string, targetId: string): string {
  return currentId === targetId ? "" : targetId;
}

export function modelActionMenuPlacement(
  trigger: TriggerBounds,
  viewportHeight: number,
  menuHeight = 180,
): ModelActionMenuPlacement {
  const spaceBelow = viewportHeight - trigger.bottom;
  const spaceAbove = trigger.top;
  return spaceBelow < menuHeight && spaceAbove > spaceBelow ? "up" : "down";
}
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `npm test -- modelActionMenu.test.ts`

Expected: 3 assertions pass with no warnings.

- [ ] **Step 5: Commit the menu helper**

```powershell
git add fronted/src/modelActionMenu.ts fronted/src/modelActionMenu.test.ts
git commit -m "test: define settings action menu behavior"
```

### Task 2: Bind Explicit Action Menu State and Fix Stacking

**Files:**
- Modify: `fronted/src/App.vue:130-150,400-410,1020-1040,1270-1305,4929-5040`
- Modify: `fronted/src/styleApplication.test.ts`

- [ ] **Step 1: Add a failing structural contract test**

Add to `fronted/src/styleApplication.test.ts`:

```ts
it("uses explicit model action menu state instead of an untracked details popup", () => {
  const source = appVue();

  expect(source).toContain("modelActionMenuState.openId");
  expect(source).toContain("settings-model-row-action-open");
  expect(source).toContain("toggleModelActionMenu(model.id, event)");
  expect(source).toContain('aria-label="关闭模型操作"');
  expect(source).not.toContain('<details class="settings-row-actions-more">');
});
```

- [ ] **Step 2: Run the contract test and verify RED**

Run: `npm test -- styleApplication.test.ts -t "uses explicit model action menu state"`

Expected: FAIL because the explicit state and open-row class are absent.

- [ ] **Step 3: Add the state and event handlers to `App.vue`**

Import the helpers and add:

```ts
const modelActionMenuState = reactive({
  openId: "",
  placement: "down" as ModelActionMenuPlacement,
});

function closeModelActionMenu() {
  modelActionMenuState.openId = "";
  modelActionMenuState.placement = "down";
}

function toggleModelActionMenu(modelId: string, event: MouseEvent) {
  const nextId = toggledModelActionMenuId(modelActionMenuState.openId, modelId);
  modelActionMenuState.openId = nextId;
  if (!nextId) return;
  const trigger = event.currentTarget as HTMLElement;
  modelActionMenuState.placement = modelActionMenuPlacement(trigger.getBoundingClientRect(), window.innerHeight);
}
```

Call `closeModelActionMenu()` from navigation, settings-dialog open, filtering paths that replace the visible list, and Escape handling.

- [ ] **Step 4: Replace the model-row `details` menu with controlled markup**

Add `settings-model-row-action-open` to the row when `modelActionMenuState.openId === model.id`, then replace the `details` block with:

```vue
<div :class="['settings-row-actions-more', modelActionMenuState.placement === 'up' ? 'settings-row-actions-more-up' : '']">
  <button
    type="button"
    class="button-secondary settings-action-button"
    :aria-expanded="modelActionMenuState.openId === model.id"
    @click.stop="(event) => toggleModelActionMenu(model.id, event)"
  >操作</button>
  <button
    v-if="modelActionMenuState.openId === model.id"
    type="button"
    class="settings-row-action-scrim"
    aria-label="关闭模型操作"
    @click="closeModelActionMenu"
  ></button>
  <div v-if="modelActionMenuState.openId === model.id" class="settings-row-action-menu" @click.stop>
    <button class="button-secondary settings-action-button" :disabled="!canEditModel(model)" @click="openEditDialog(model); closeModelActionMenu()">编辑</button>
    <button class="button-danger settings-action-button" :disabled="!canEditModel(model)" @click="removeModelFromWorkbench(model.id); closeModelActionMenu()">删除</button>
  </div>
</div>
```

- [ ] **Step 5: Run focused and full unit tests**

Run: `npm test -- styleApplication.test.ts modelActionMenu.test.ts`

Expected: both test files pass.

- [ ] **Step 6: Commit the stacking fix**

```powershell
git add fronted/src/App.vue fronted/src/styleApplication.test.ts
git commit -m "fix: lift model action menus above settings rows"
```

### Task 3: Define and Bind Model Identity Colors

**Files:**
- Modify: `fronted/src/utils.test.ts`
- Modify: `fronted/src/utils.ts`
- Modify: `fronted/src/App.vue:80-110,540-550,3450-3465,3900-3935,4002-4007,4135-4160,4929-4960`

- [ ] **Step 1: Write failing tests for private and public accent resolution**

Add imports and tests in `fronted/src/utils.test.ts`:

```ts
describe("model identity accents", () => {
  it("uses capability colors for private models", () => {
    expect(modelIdentityAccent({ capability: "text", isPublic: false })).toBe("#16835A");
    expect(modelIdentityAccent({ capability: "image", isPublic: false })).toBe("#D85C63");
    expect(modelIdentityAccent({ capability: "video", isPublic: false })).toBe("#3676D8");
  });

  it("uses the configured public model accent when available", () => {
    expect(modelIdentityAccent({ capability: "image", isPublic: true, publicAccentColor: "#A855F7" })).toBe("#A855F7");
  });
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `npm test -- utils.test.ts -t "model identity accents"`

Expected: FAIL because `modelIdentityAccent` is not exported.

- [ ] **Step 3: Implement `modelIdentityAccent` in `utils.ts`**

```ts
const PRIVATE_MODEL_ACCENT_BY_CAPABILITY: Record<Capability, string> = {
  text: "#16835A",
  image: "#D85C63",
  video: "#3676D8",
};

export function modelIdentityAccent(
  model: Pick<ModelDefinition, "capability" | "isPublic" | "publicAccentColor">,
): string {
  return model.isPublic ? publicModelAccent(model) : PRIVATE_MODEL_ACCENT_BY_CAPABILITY[model.capability];
}
```

- [ ] **Step 4: Bind the accent to every model-facing surface**

Add an `activeModelIdentityStyle` computed and a reusable row style:

```ts
const activeModelIdentityStyle = computed<Record<string, string> | undefined>(() =>
  activeModel.value ? { "--model-accent": modelIdentityAccent(activeModel.value) } : undefined,
);

function modelIdentityStyle(model: ModelDefinition): Record<string, string> {
  return {
    "--model-accent": modelIdentityAccent(model),
    "--public-model-accent": modelIdentityAccent(model),
  };
}
```

Apply `:style="activeModelIdentityStyle"` to `.studio-panel`, and `:style="modelIdentityStyle(model)"` to sidebar and settings model rows. Add `creator-model-identity` to the top model strip and keep the existing name, capability, public status, price, description, and parameter source content.

- [ ] **Step 5: Run unit tests**

Run: `npm test -- utils.test.ts styleApplication.test.ts`

Expected: all tests pass.

- [ ] **Step 6: Commit model identity behavior**

```powershell
git add fronted/src/utils.ts fronted/src/utils.test.ts fronted/src/App.vue
git commit -m "feat: bind model identity colors across creator views"
```

### Task 4: Build the Settings Visual Ownership Layer

**Files:**
- Create: `fronted/src/workbenchRedesign.css`
- Modify: `fronted/src/main.ts`
- Modify: `fronted/src/styleApplication.test.ts`

- [ ] **Step 1: Add failing stylesheet ownership tests**

Update the test helper to read `workbenchRedesign.css`, then add:

```ts
it("loads one final redesign layer after the legacy stylesheet", () => {
  const main = readFileSync(resolve(__dirname, "main.ts"), "utf8");
  expect(main.indexOf('./styles.css')).toBeLessThan(main.indexOf('./workbenchRedesign.css'));
});

it("gives open settings action rows and menus an explicit layer", () => {
  const styles = redesignCss();
  expect(styles).toContain(".settings-model-row-action-open");
  expect(styles).toContain("z-index: 320 !important");
  expect(styles).toContain(".settings-row-action-scrim");
  expect(styles).toContain(".settings-row-actions-more-up .settings-row-action-menu");
});
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `npm test -- styleApplication.test.ts -t "final redesign layer|open settings action rows"`

Expected: FAIL because the stylesheet and import do not exist.

- [ ] **Step 3: Create the settings theme tokens and list layout**

Start `workbenchRedesign.css` with scoped dual-theme tokens and settings rules:

```css
/* GenStudio creator and settings visual ownership layer. */
.shell {
  --surface-page: #f3f6f8;
  --surface-panel: #ffffff;
  --surface-soft: #f7f9fa;
  --surface-float: #ffffff;
  --text-main: #17212b;
  --text-subtle: #5d6b78;
  --line-soft: #dce3e8;
  --line-strong: #b8c5ce;
  --capability-text: #16835a;
  --capability-image: #d85c63;
  --capability-video: #3676d8;
  --radius-control: 6px;
  --radius-panel: 8px;
}

.shell[data-theme="dark"] {
  --surface-page: #101418;
  --surface-panel: #171c21;
  --surface-soft: #1d2329;
  --surface-float: #20262c;
  --text-main: #edf1f4;
  --text-subtle: #a8b2bb;
  --line-soft: #303941;
  --line-strong: #4a5863;
}
```

Continue with selectors for `.settings-page`, `.settings-hero`, `.settings-list-panel`, `.settings-model-board`, `.settings-model-row`, `.settings-model-main`, `.settings-model-meta-row`, `.settings-primary-model`, `.settings-status-cell`, and `.settings-row-actions`. Use an 8px maximum card radius, neutral surfaces, stable grid tracks, and `border-left: 3px solid var(--model-accent)` for identity.

- [ ] **Step 4: Implement the desktop and mobile menu layers**

```css
.shell .settings-model-row-action-open {
  position: relative !important;
  z-index: 320 !important;
}

.shell .settings-row-action-scrim {
  position: fixed !important;
  inset: 0 !important;
  z-index: 300 !important;
  background: transparent !important;
  box-shadow: none !important;
}

.shell .settings-row-action-menu {
  z-index: 340 !important;
  border: 1px solid var(--line-soft) !important;
  border-radius: var(--radius-panel) !important;
  background: var(--surface-float) !important;
}

.shell .settings-row-actions-more-up .settings-row-action-menu {
  top: auto !important;
  bottom: calc(100% + 6px) !important;
}

@media (max-width: 720px) {
  .shell .settings-model-row-action-open .settings-row-action-menu {
    position: fixed !important;
    inset: auto 10px calc(env(safe-area-inset-bottom, 0px) + 12px) 10px !important;
    width: auto !important;
  }
}
```

- [ ] **Step 5: Import the new stylesheet last and run tests**

Append to `fronted/src/main.ts` after `styles.css`:

```ts
import "./workbenchRedesign.css";
```

Run: `npm test -- styleApplication.test.ts`

Expected: all style contracts pass.

- [ ] **Step 6: Commit the settings redesign**

```powershell
git add fronted/src/workbenchRedesign.css fronted/src/main.ts fronted/src/styleApplication.test.ts
git commit -m "style: redesign model settings workspace"
```

### Task 5: Redesign Text, Image, and Video Creation Surfaces

**Files:**
- Modify: `fronted/src/App.vue:4002-4200,4200-4715`
- Modify: `fronted/src/workbenchRedesign.css`
- Modify: `fronted/src/styleApplication.test.ts`

- [ ] **Step 1: Add failing creator-surface contract tests**

```ts
it("uses one model-aware frame for all creator capabilities", () => {
  const source = appVue();
  const styles = redesignCss();

  expect(source).toContain("creator-model-identity");
  expect(source).toContain(':style="activeModelIdentityStyle"');
  expect(styles).toContain('.studio-panel[data-view="text"]');
  expect(styles).toContain('.studio-panel[data-view="images"]');
  expect(styles).toContain('.studio-panel[data-view="videos"]');
  expect(styles).toContain("var(--model-accent)");
});

it("keeps media controls and creator text contained on mobile", () => {
  const styles = redesignCss();
  expect(styles).toContain("@media (max-width: 720px)");
  expect(styles).toContain("overflow-wrap: anywhere");
  expect(styles).toContain("grid-template-columns: minmax(0, 1fr)");
});
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `npm test -- styleApplication.test.ts -t "model-aware frame|creator text contained"`

Expected: FAIL until the creator rules exist.

- [ ] **Step 3: Add the shared creator frame styles**

Implement a neutral page surface, compact model identity band, bounded conversation width, and stable bottom composer. Drive only key identity points from `--model-accent`:

```css
.shell .studio-panel {
  --model-accent: var(--capability-image);
  background: var(--surface-page) !important;
}

.shell .studio-panel[data-view="text"] { --model-accent: var(--capability-text); }
.shell .studio-panel[data-view="images"] { --model-accent: var(--capability-image); }
.shell .studio-panel[data-view="videos"] { --model-accent: var(--capability-video); }

.shell .creator-model-identity {
  border-left: 3px solid var(--model-accent) !important;
}

.shell .studio-panel .composer-surface:focus-within {
  border-color: var(--model-accent) !important;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--model-accent) 14%, transparent) !important;
}

.shell .studio-panel .composer-submit-button {
  background: var(--model-accent) !important;
}
```

- [ ] **Step 4: Add capability-specific control composition**

Style text history for reading width and message rhythm; image reference controls as a clear upload rail plus compact ratio/quality groups; video reference slots as stable aspect-ratio tiles with grouped mode, duration, resolution, audio, and quantity controls. Avoid nested card borders and keep each control height stable.

Required selectors:

```css
.shell .studio-panel[data-view="text"] .conversation-timeline { max-width: 860px !important; }
.shell .studio-panel[data-view="images"] .composer-attach-row { grid-template-columns: minmax(180px, .7fr) minmax(0, 1.3fr) !important; }
.shell .studio-panel[data-view="videos"] .composer-video-attach-row { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
.shell .reference-thumb { aspect-ratio: 4 / 3; }
.shell .composer-input,
.shell .settings-model-main,
.shell .settings-model-hint { overflow-wrap: anywhere; }
```

- [ ] **Step 5: Add responsive rules for 1024px and 720px**

At `1024px`, collapse the settings action grid and media parameter groups without changing creator order. At `720px`, use a single-column creator, full-width composer controls, horizontally scrollable compact model navigation, and fixed bottom sheets for parameter/menu overlays.

- [ ] **Step 6: Run all frontend tests and build**

Run: `npm test`

Expected: all Vitest files pass.

Run: `npm run build`

Expected: `vue-tsc -b` and `vite build` exit 0 and produce `fronted/dist`.

- [ ] **Step 7: Commit the creator redesign**

```powershell
git add fronted/src/App.vue fronted/src/workbenchRedesign.css fronted/src/styleApplication.test.ts
git commit -m "style: unify creator workbench surfaces"
```

### Task 6: Browser QA and Docker Verification

**Files:**
- Create: `output/playwright/creator-settings-light-1440.png`
- Create: `output/playwright/creator-settings-dark-1440.png`
- Create: `output/playwright/creator-images-mobile-390.png`
- Create: `output/playwright/creator-video-tablet-1024.png`
- Modify only if QA finds a verified defect: `fronted/src/App.vue`, `fronted/src/workbenchRedesign.css`, relevant tests

- [ ] **Step 1: Start the local application stack**

Run from the repository root:

```powershell
docker compose up -d mysql
Start-Process -FilePath ".\server\.venv\Scripts\python.exe" -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000" -WorkingDirectory ".\server" -WindowStyle Hidden
Start-Process -FilePath "npm.cmd" -ArgumentList "run","dev" -WorkingDirectory ".\fronted" -WindowStyle Hidden
Invoke-WebRequest http://127.0.0.1:8000/api/health -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:5175 -UseBasicParsing
```

Expected: creator UI loads without console errors and test/admin authentication can access settings.

- [ ] **Step 2: Reproduce and verify the action-menu bug in a real browser**

Use Playwright CLI to open settings as an administrator, open the first model's “操作” menu, and measure the menu and next-row rectangles.

Expected: menu remains visible, its sampled center is the menu element, and it is not clipped by the next model row. Repeat with a near-bottom row to verify upward placement and at 390px to verify the bottom sheet.

- [ ] **Step 3: Capture the required visual states**

Capture settings and all three creator views in both themes. Save the four named representative screenshots under `output/playwright/`; inspect at 1440 x 900, 1024 x 768, and 390 x 844.

Expected: no overlapping text, horizontal overflow, blank asset surfaces, clipped menus, or layout shifts when controls open.

- [ ] **Step 4: Run final frontend verification**

Run: `npm test`

Expected: all tests pass.

Run: `npm run build`

Expected: TypeScript and Vite build succeed.

- [ ] **Step 5: Build and serve with local Docker**

From the repository root, build both frontends inside pinned Node containers, then serve their output through the repository's Nginx Compose service:

```powershell
docker run --rm -v "${PWD}:/workspace" -w /workspace/fronted node:22-alpine npm run build
docker run --rm -v "${PWD}:/workspace" -w /workspace/admin node:22-alpine npm run build
docker compose --profile app up -d --build web
docker compose ps
```

Expected: both containerized Vite builds exit 0, `genstudio-web` is running, and `http://127.0.0.1:8080/` serves GenStudio assets from this repository.

- [ ] **Step 6: Smoke-test the Docker-served app**

Open `http://127.0.0.1:8080/` with Playwright, check the settings and creator routes, and inspect browser console/network failures.

Expected: static routes load, assets return 200, and the redesigned surfaces match the Vite verification.

- [ ] **Step 7: Commit any QA-only fixes**

If browser QA required code changes, add a regression test first, verify it fails, apply the minimal fix, rerun the checks, then commit:

```powershell
git add fronted/src/App.vue fronted/src/workbenchRedesign.css fronted/src/*.test.ts
git commit -m "fix: resolve creator workspace visual regressions"
```

Do not deploy or push as part of this task. Report local Docker and browser evidence and wait for explicit release authorization.
