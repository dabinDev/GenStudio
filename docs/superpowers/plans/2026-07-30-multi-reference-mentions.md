# Multi-Reference Mentions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add numbered, maximum-10 image references and precise `@number` selection to image and video creation without breaking adapter-specific frame semantics.

**Architecture:** Put all parsing, renumbering, selection, and limit rules in a pure TypeScript module. Keep Vue responsible for cursor/menu state and rendering, and keep existing request builders responsible for adapter fields. Enforce the absolute limit again in FastAPI before any upstream request.

**Tech Stack:** Vue 3, TypeScript, Vitest, FastAPI, Pytest

---

### Task 1: Pure mention parser and renumbering rules

**Files:**
- Create: `fronted/src/referenceMentions.ts`
- Create: `fronted/src/referenceMentions.test.ts`

- [ ] **Step 1: Write the failing parser tests**

```ts
import { describe, expect, it } from "vitest";
import {
  MAX_REFERENCE_ASSETS,
  mentionQueryAtCursor,
  parseReferenceMentions,
  referencesForPrompt,
  replaceMentionQuery,
  rewriteMentionsAfterRemoval,
} from "./referenceMentions";

describe("reference mentions", () => {
  it("parses 1, 9 and 10 without treating @10 as @1", () => {
    expect(parseReferenceMentions("用 @1、@9 和 @10", 10)).toEqual({ indexes: [1, 9, 10], invalid: [] });
  });

  it("deduplicates valid indexes and reports invalid tokens", () => {
    expect(parseReferenceMentions("@2 @2 @0 @11 @[已删除3]", 4)).toEqual({
      indexes: [2],
      invalid: [0, 3, 11],
    });
  });

  it("uses all assets without mentions and selected assets with mentions", () => {
    const assets = ["a", "b", "c"];
    expect(referencesForPrompt("普通提示", assets)).toEqual({ assets, invalid: [] });
    expect(referencesForPrompt("保留 @3 和 @1", assets)).toEqual({ assets: ["a", "c"], invalid: [] });
  });

  it("marks the removed token and decrements later indexes", () => {
    expect(rewriteMentionsAfterRemoval("@1 + @2 + @3", 2)).toBe("@1 + @[已删除2] + @2");
  });

  it("finds and replaces the active query at the cursor", () => {
    expect(mentionQueryAtCursor("参考 @1", 5)).toEqual({ start: 3, end: 5, query: "1" });
    expect(replaceMentionQuery("参考 @1", 5, 10)).toEqual({ value: "参考 @10 ", cursor: 7 });
  });

  it("defines the product hard limit", () => {
    expect(MAX_REFERENCE_ASSETS).toBe(10);
  });
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `npm test -- referenceMentions.test.ts`

Expected: FAIL because `referenceMentions.ts` does not exist.

- [ ] **Step 3: Implement the pure module**

```ts
export const MAX_REFERENCE_ASSETS = 10;

export interface MentionParseResult {
  indexes: number[];
  invalid: number[];
}

export interface MentionQuery {
  start: number;
  end: number;
  query: string;
}

export function parseReferenceMentions(prompt: string, assetCount: number): MentionParseResult {
  const indexes = new Set<number>();
  const invalid = new Set<number>();
  for (const match of prompt.matchAll(/@(\d{1,2})(?!\d)/g)) {
    const index = Number(match[1]);
    if (index >= 1 && index <= assetCount && index <= MAX_REFERENCE_ASSETS) indexes.add(index);
    else invalid.add(index);
  }
  for (const match of prompt.matchAll(/@\[已删除(\d{1,2})\]/g)) invalid.add(Number(match[1]));
  return { indexes: [...indexes].sort((a, b) => a - b), invalid: [...invalid].sort((a, b) => a - b) };
}

export function referencesForPrompt<T>(prompt: string, assets: T[]): { assets: T[]; invalid: number[] } {
  const parsed = parseReferenceMentions(prompt, assets.length);
  return {
    assets: parsed.indexes.length ? assets.filter((_, index) => parsed.indexes.includes(index + 1)) : assets,
    invalid: parsed.invalid,
  };
}

export function rewriteMentionsAfterRemoval(prompt: string, removedIndex: number): string {
  return prompt.replace(/@(\d{1,2})(?!\d)/g, (token, raw: string) => {
    const index = Number(raw);
    if (index === removedIndex) return `@[已删除${removedIndex}]`;
    return index > removedIndex ? `@${index - 1}` : token;
  });
}

export function mentionQueryAtCursor(value: string, cursor: number): MentionQuery | null {
  const before = value.slice(0, cursor);
  const match = /@(\d{0,2})$/.exec(before);
  return match ? { start: cursor - match[0].length, end: cursor, query: match[1] } : null;
}

export function replaceMentionQuery(value: string, cursor: number, index: number): { value: string; cursor: number } {
  const query = mentionQueryAtCursor(value, cursor);
  if (!query) return { value, cursor };
  const inserted = `@${index} `;
  return { value: value.slice(0, query.start) + inserted + value.slice(query.end), cursor: query.start + inserted.length };
}
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `npm test -- referenceMentions.test.ts`

Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```powershell
git add fronted/src/referenceMentions.ts fronted/src/referenceMentions.test.ts
git commit -m "feat: add reference mention parser"
```

### Task 2: Cap model limits and select referenced request assets

**Files:**
- Modify: `fronted/src/utils.ts`
- Modify: `fronted/src/utils.test.ts`
- Modify: `fronted/src/App.vue`

- [ ] **Step 1: Add failing request-limit tests**

Add imports for `MAX_REFERENCE_ASSETS` and assert:

```ts
function modelWithParameterMax(capability: "image" | "video", paramKey: string, maxCount: number): ModelDefinition {
  return {
    ...textModel,
    id: `${capability}-${paramKey}-${maxCount}`,
    capability,
    adapter: capability === "image" ? "image-openai" : "video-unified-generic",
    catalog: {
      id: "catalog-test",
      displayName: "Catalog Test",
      modelName: "catalog-test",
      modelType: 0,
      capability,
      icon: "",
      description: "",
      inputHint: "",
      successRate: "",
      source: "test",
      channelGroups: [],
      parameters: [{
        id: `parameter-${paramKey}`,
        displayName: paramKey,
        paramKey,
        description: "",
        widgetType: 0,
        isRequired: false,
        defaultValue: "reference",
        functionTag: "",
        maxCount,
        sortOrder: 0,
        options: paramKey === "video_mode" ? [{
          id: "reference",
          optionName: "reference",
          optionValue: "reference",
          description: "",
          maxCount,
          isDefault: true,
          sortOrder: 0,
          priceFactor: "1",
        }] : [],
      }],
    },
  };
}

it("caps image and video reference limits at ten", () => {
  expect(catalogReferenceLimit(modelWithParameterMax("image", "images", 14), ["images"], 14)).toBe(10);
  expect(videoModeUploadLimit(modelWithParameterMax("video", "video_mode", 14), "reference")).toBe(10);
});

it("keeps a lower provider limit", () => {
  expect(catalogReferenceLimit(modelWithParameterMax("image", "images", 4), ["images"], 10)).toBe(4);
});
```

Add a request-builder assertion that `buildImageGenerationRequestBody` receives only the URLs returned by `referencesForPrompt`.

- [ ] **Step 2: Run and verify RED**

Run: `npm test -- utils.test.ts`

Expected: FAIL because `catalogReferenceLimit` does not exist and video limit can exceed 10.

- [ ] **Step 3: Implement the cap and prompt selection**

In `utils.ts`, import `MAX_REFERENCE_ASSETS` and add:

```ts
export function catalogReferenceLimit(
  model: ModelDefinition | null | undefined,
  keys: CatalogParameterKeyInput,
  fallback: number,
): number {
  return Math.min(MAX_REFERENCE_ASSETS, Math.max(0, catalogMaxCount(model, keys, fallback)));
}
```

Clamp `videoModeUploadLimit` with the same constant. In `App.vue`, derive image and ordinary video request arrays through `referencesForPrompt(prompt, assets)`. Fixed first/last frame roles remain present regardless of mentions. Before submit, return an inline error when `invalid.length > 0`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `npm test -- utils.test.ts referenceMentions.test.ts`

Expected: all focused tests pass.

- [ ] **Step 5: Commit**

```powershell
git add fronted/src/utils.ts fronted/src/utils.test.ts fronted/src/App.vue
git commit -m "feat: apply numbered reference selection"
```

### Task 3: Numbered strips and `@` suggestion menu

**Files:**
- Modify: `fronted/package.json`
- Modify: `fronted/package-lock.json`
- Create: `fronted/src/components/ReferenceMentionMenu.vue`
- Create: `fronted/src/components/ReferenceMentionMenu.test.ts`
- Modify: `fronted/src/App.vue`
- Modify: `fronted/src/types.ts`
- Modify: `fronted/src/styles.css`
- Modify: `fronted/src/workbenchRedesign.css`

- [ ] **Step 1: Write failing component contract tests**

Run `npm install -D @vue/test-utils jsdom` so component behavior is tested in a DOM environment. Mount the component with three assets and assert it renders buttons with accessible labels `引用图片 1`, `引用图片 2`, `引用图片 3`; filters on query `2`; and emits `select` with `2`. Add source contract assertions that every image/video reference thumbnail renders `.reference-index-badge` and both prompt textareas handle `input`, `keydown`, `click`, and `keyup` cursor updates.

- [ ] **Step 2: Run and verify RED**

Run: `npm test -- ReferenceMentionMenu.test.ts styleApplication.test.ts`

Expected: FAIL because the component and index badge are absent.

- [ ] **Step 3: Implement the component and editor state**

The component accepts:

```ts
defineProps<{
  assets: UploadedAsset[];
  query: string;
  activeIndex: number;
}>();
defineEmits<{ select: [index: number]; close: [] }>();
```

In `App.vue`, keep one reactive mention-menu state (`capability`, `start`, `end`, `query`, `activeIndex`). Open it only when `mentionQueryAtCursor` returns a query and assets exist. Arrow keys change the active item, Enter/Tab inserts it, Escape closes it, and selecting restores textarea focus/cursor. Render `index + 1` in the upper-right badge for all ordinary and frame thumbnails. On removal call `rewriteMentionsAfterRemoval` on the relevant prompt before mutating the asset array.

Use fixed 56 px desktop and 52 px mobile thumbnails, 18 px circular badges, visible focus rings, and a scrollable menu capped at 10 rows. The menu uses an unframed popover surface rather than nested cards.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `npm test -- ReferenceMentionMenu.test.ts styleApplication.test.ts referenceMentions.test.ts`

Expected: all focused tests pass.

- [ ] **Step 5: Commit**

```powershell
git add fronted/package.json fronted/package-lock.json fronted/src/components/ReferenceMentionMenu.vue fronted/src/components/ReferenceMentionMenu.test.ts fronted/src/App.vue fronted/src/types.ts fronted/src/styles.css fronted/src/workbenchRedesign.css
git commit -m "feat: add numbered reference composer"
```

### Task 4: Preserve thumbnails and per-file upload outcomes

**Files:**
- Modify: `fronted/src/types.ts`
- Modify: `fronted/src/api.ts`
- Modify: `fronted/src/api.test.ts`
- Modify: `fronted/src/App.vue`

- [ ] **Step 1: Add failing upload tests**

Assert `UploadedAsset` accepts `thumbnailUrl`, `objectKey`, and `thumbnailObjectKey`; `uploadAsset` returns those fields from the presign response; and `uploadReferenceBatch` uses `Promise.allSettled` so one failed file does not discard successful files.

- [ ] **Step 2: Run and verify RED**

Run: `npm test -- api.test.ts`

Expected: FAIL because thumbnail metadata and settled batch behavior do not exist.

- [ ] **Step 3: Implement batch outcomes**

Add:

```ts
export interface UploadConfig {
  baseUrl?: string;
  apiKey?: string;
  subModelId?: string;
}

export interface UploadBatchResult {
  uploaded: UploadedAsset[];
  failed: Array<{ fileName: string; message: string }>;
}

export async function uploadReferenceBatch(files: File[], config: UploadConfig): Promise<UploadBatchResult> {
  const settled = await Promise.allSettled(files.map((file) => uploadAsset(file, config)));
  return settled.reduce<UploadBatchResult>((result, item, index) => {
    if (item.status === "fulfilled") result.uploaded.push(item.value);
    else result.failed.push({ fileName: files[index].name, message: item.reason instanceof Error ? item.reason.message : "上传失败" });
    return result;
  }, { uploaded: [], failed: [] });
}
```

Update image and video upload handlers to append successful items in selection order, display failed file names, and preserve existing items.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `npm test -- api.test.ts referenceMentions.test.ts`

Expected: focused tests pass.

- [ ] **Step 5: Commit**

```powershell
git add fronted/src/types.ts fronted/src/api.ts fronted/src/api.test.ts fronted/src/App.vue
git commit -m "feat: preserve partial reference uploads"
```

### Task 5: Server-side absolute limit and stored index metadata

**Files:**
- Create: `server/app/reference_assets.py`
- Create: `server/tests/test_reference_assets.py`
- Modify: `server/app/main.py`

- [ ] **Step 1: Write failing backend tests**

```python
def test_validate_reference_limit_accepts_ten_unique_urls():
    refs = [{"url": f"https://cdn.test/{index}.png"} for index in range(10)]
    assert validate_reference_limit({"images": refs}) == 10

def test_validate_reference_limit_rejects_eleven_unique_urls():
    refs = [f"https://cdn.test/{index}.png" for index in range(11)]
    with pytest.raises(HTTPException) as exc:
        validate_reference_limit({"images": refs})
    assert exc.value.status_code == 400

def test_reference_metadata_indexes_from_one():
    assert indexed_reference_metadata(0, "reference", "参考图")["index"] == 1
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_reference_assets.py -q`

Expected: FAIL because `app.reference_assets` does not exist.

- [ ] **Step 3: Implement validation and integrate routes**

Move or reuse the existing recursive reference collector so `validate_reference_limit(payload, maximum=10)` counts unique reference URLs. Call it before image generation, image query/retry payload normalization, video creation, and video retry. Change stored metadata from zero-based `index` to one-based `index`.

- [ ] **Step 4: Run focused backend tests and verify GREEN**

Run: `python -m pytest tests/test_reference_assets.py tests/test_conversations.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add server/app/reference_assets.py server/tests/test_reference_assets.py server/app/main.py
git commit -m "feat: enforce reference image limit"
```

### Task 6: Multi-reference verification checkpoint

**Files:**
- Verify only

- [ ] **Step 1: Run complete frontend tests and build**

Run: `npm test` and `npm run build` from `fronted/`.

Expected: all tests pass and Vite exits 0.

- [ ] **Step 2: Run complete backend tests**

Run: `python -m pytest` from `server/`.

Expected: all tests pass.

- [ ] **Step 3: Inspect the diff and commit any test-only corrections**

Run: `git diff --check` and `git status --short`.

Expected: no whitespace errors and no unplanned generated files.
