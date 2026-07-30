# Image Reference, Conversation Layout, and Settings Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make R2 image references reach image editing models, prevent duplicate generated images, align conversations to both sides of the workspace, keep multi-image results horizontal, and flatten the crowded settings model list.

**Architecture:** The backend will only hydrate image references from the configured object-storage public origin and will send those bytes through the existing multipart edit path. The frontend will merge query results by logical output position, treat persisted assistant assets as authoritative, and use explicit message/layout classes for stable responsive styling.

**Tech Stack:** FastAPI, boto3/S3-compatible R2, pytest, Vue 3, TypeScript, Vitest, CSS, Playwright.

---

### Task 1: Read configured R2 objects safely

**Files:**
- Modify: `server/app/storage.py`
- Test: `server/tests/test_storage.py`

- [ ] **Step 1: Write the failing storage tests**

Add tests that require `ObjectStorageClient.object_key_from_public_url()` to accept only the configured public origin/path, decode escaped path segments, and reject a different origin. Add a fake streaming body and require `read_image()` to return bytes plus `image/png`, while rejecting empty, non-image, and oversized objects.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/test_storage.py -q` from `server/`.

Expected: FAIL because the URL parser and bounded image reader do not exist.

- [ ] **Step 3: Implement the minimal storage API**

Implement these public methods without exposing credentials or allowing arbitrary network fetches:

```python
def object_key_from_public_url(self, value: str) -> str | None: ...

def read_image(self, key: str, *, max_bytes: int) -> dict[str, Any]:
    # Return {"content": bytes, "content_type": str, "filename": str}.
```

Use `urlparse`, `unquote`, exact scheme/netloc matching, public-base path containment, `get_object`, declared `ContentLength`, a bounded `Body.read(max_bytes + 1)`, and an `image/` content-type check.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `python -m pytest tests/test_storage.py -q` from `server/`.

Expected: all storage tests pass.

### Task 2: Route R2 references through multipart image edits

**Files:**
- Modify: `server/app/main.py`
- Test: `server/tests/test_kkyi_catalog.py`

- [ ] **Step 1: Write failing proxy tests**

Add an authenticated `image-openai` route test whose request contains a configured R2 public URL. Stub `ObjectStorageClient` to resolve/read the object and assert:

```python
assert captured["url"].endswith("/v1/images/edits")
assert captured["files"] == [
    ("image", ("reference.png", PNG_BYTES, "image/png")),
]
```

Add tests proving a configured R2 read failure returns 400 and does not call generations, while an unrelated external URL is never downloaded by the server.

- [ ] **Step 2: Run the focused proxy tests and verify RED**

Run: `python -m pytest tests/test_kkyi_catalog.py -q -k "r2_reference or local_references"` from `server/`.

Expected: the R2 case fails because it still targets generations.

- [ ] **Step 3: Implement R2 reference collection**

Add a bounded R2 reference collector for `image-openai`. Preserve the existing local/Data URL collector, hydrate configured R2 references with `await asyncio.to_thread(...)`, and choose `/v1/images/edits` whenever at least one editable reference was collected. Return a clear 400 error if a URL belongs to configured storage but cannot be read as an image; do not silently generate without the requested reference.

- [ ] **Step 4: Run focused and related backend tests**

Run:

```powershell
python -m pytest tests/test_kkyi_catalog.py -q -k "image_model or reference"
python -m pytest tests/test_storage.py -q
```

Expected: both commands pass.

### Task 3: Merge image query assets by logical position

**Files:**
- Modify: `fronted/src/utils.ts`
- Test: `fronted/src/utils.test.ts`

- [ ] **Step 1: Write failing merge tests**

Add a regression test where `assistantAssets[0].url` is an R2 URL and `images[0].src` is an upstream URL for the same output position; expect one persisted asset. Add a partial four-image test where backend assets at `batchIndex` 1 and 3 are combined with query images to produce exactly four ordered outputs.

- [ ] **Step 2: Run the focused Vitest and verify RED**

Run: `npm run test -- --run src/utils.test.ts` from `fronted/`.

Expected: the R2/upstream regression returns two assets before the fix.

- [ ] **Step 3: Implement positional merging**

Update `mergeImageQueryAssets()` so filtered assistant assets occupy their `batchIndex` or array position first. Fill only missing positions from query images. Preserve backend asset IDs, thumbnail URLs, metadata, and task scoping. Fall back to all query images when no assistant assets exist.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `npm run test -- --run src/utils.test.ts` from `fronted/`.

Expected: all utility tests pass.

### Task 4: Apply full-width conversation and horizontal media layout

**Files:**
- Modify: `fronted/src/App.vue`
- Modify: `fronted/src/workbenchRedesign.css`
- Test: `fronted/src/styleApplication.test.ts`

- [ ] **Step 1: Write failing markup/style contract tests**

Require the message card to expose a multiple-assets class and require the final redesign cascade to contain:

```css
.shell .conversation-timeline { width: 100% !important; }
.shell .message-user { grid-template-columns: minmax(0, 1fr) 32px !important; }
.shell .message-assets-multiple { grid-auto-flow: column !important; overflow-x: auto !important; }
```

Also assert single-image messages retain a bounded preview width.

- [ ] **Step 2: Run the focused style test and verify RED**

Run: `npm run test -- --run src/styleApplication.test.ts` from `fronted/`.

Expected: FAIL because the timeline is still centered at 1080px and multiple assets auto-wrap.

- [ ] **Step 3: Implement the layout**

Add `message-has-multiple-assets` to message cards when needed. Make the timeline fill the studio canvas with stable gutters, keep assistant avatar/bubble left, move the user avatar and bubble to the right, and widen only media-heavy bubbles. Use a non-wrapping horizontal grid with stable card widths and scroll snapping on narrow viewports.

- [ ] **Step 4: Run the focused style test and verify GREEN**

Run: `npm run test -- --run src/styleApplication.test.ts` from `fronted/`.

Expected: the style contract passes.

### Task 5: Flatten the settings model list

**Files:**
- Modify: `fronted/src/workbenchRedesign.css`
- Test: `fronted/src/styleApplication.test.ts`

- [ ] **Step 1: Extend the failing settings style contract**

Require a named final settings-polish block where the model board owns the outer surface, normal rows use `border: 0`, rows use only `border-bottom`, hover does not add a shadow, public rows do not add an inset outline, and the primary-model control uses a subtle background rather than another framed card.

- [ ] **Step 2: Run the style test and verify RED**

Run: `npm run test -- --run src/styleApplication.test.ts` from `fronted/`.

Expected: FAIL against the current per-row borders and shadows.

- [ ] **Step 3: Implement restrained settings styling**

Append a final cascade block in `workbenchRedesign.css` that removes row card borders/shadows/gradients, adds one board surface and row separators, preserves the capability side marker, reduces nested primary-model framing, and retains the existing mobile single-column action sheet behavior.

- [ ] **Step 4: Run the style test and verify GREEN**

Run: `npm run test -- --run src/styleApplication.test.ts` from `fronted/`.

Expected: all style contracts pass.

### Task 6: Full verification and production release

**Files:**
- Modify only if verification exposes a regression.

- [ ] **Step 1: Run complete backend verification**

Run: `python -m pytest` from `server/` and `python -m compileall server` from the repository root.

Expected: all tests pass and compilation exits 0.

- [ ] **Step 2: Run complete frontend verification**

Run from `fronted/`:

```powershell
npm run test
npm run build
```

Expected: Vitest, TypeScript, and Vite production build all pass.

- [ ] **Step 3: Run browser visual regression**

Use Playwright against the local production build at wide desktop, 1440px desktop, and 390px mobile. Verify image conversations, two/four-image rows, the settings list, both themes, overflow, media controls, and console/page errors. Save screenshots outside tracked source paths.

- [ ] **Step 4: Commit and push `newui`**

Review `git diff`, run `git diff --check`, commit the implementation and tests, and push `newui` to origin.

- [ ] **Step 5: Publish using the existing verified-image GenStudio procedure**

Follow `docs/OPERATIONS.md`: build and verify the production image locally, create production rollback assets, upload the exact image, recreate only `genstudio-api` with the prebuilt image, and leave `genstudio-mysql` unchanged.

- [ ] **Step 6: Verify production**

Confirm health, database/storage status, container restart counts, strict startup logs, R2 reference editing, single-image de-duplication, horizontal multi-image display, left/right alignment, settings-page visual quality, and public desktop/mobile behavior.
