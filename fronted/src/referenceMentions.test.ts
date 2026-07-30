import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  MAX_REFERENCE_ASSETS,
  mentionQueryAtCursor,
  normalizeReferenceMentions,
  parseReferenceMentions,
  referencesForPrompt,
  replaceMentionQuery,
  rewriteMentionsAfterRemoval,
} from "./referenceMentions";

describe("reference mentions", () => {
  it("parses 1, 9 and 10 without treating @10 as @1", () => {
    expect(parseReferenceMentions("用 @1、@9 和 @10", 10)).toEqual({
      indexes: [1, 9, 10],
      invalid: [],
    });
  });

  it("deduplicates valid indexes and reports invalid tokens", () => {
    expect(parseReferenceMentions("@2 @2 @0 @11 @[已删除3]", 4)).toEqual({
      indexes: [2],
      invalid: [0, 3, 11],
    });
  });

  it("does not parse numbers longer than two digits as shorter references", () => {
    expect(parseReferenceMentions("忽略 @100 和 @123", 10)).toEqual({
      indexes: [],
      invalid: [],
    });
  });

  it("uses all assets without mentions and selected assets with mentions", () => {
    const assets = ["a", "b", "c"];
    expect(referencesForPrompt("普通提示", assets)).toEqual({ assets, invalid: [] });
    expect(referencesForPrompt("保留 @3 和 @1", assets)).toEqual({
      assets: ["a", "c"],
      invalid: [],
    });
  });

  it("marks the removed token and decrements later indexes", () => {
    expect(rewriteMentionsAfterRemoval("@1 + @2 + @3 + @10", 2)).toBe(
      "@1 + @[已删除2] + @2 + @9",
    );
  });

  it("finds the active query only when the cursor follows a mention prefix", () => {
    expect(mentionQueryAtCursor("参考 @1", 5)).toEqual({ start: 3, end: 5, query: "1" });
    expect(mentionQueryAtCursor("参考 @", 4)).toEqual({ start: 3, end: 4, query: "" });
    expect(mentionQueryAtCursor("参考 @1 后续", 8)).toBeNull();
  });

  it("replaces the active mention query and returns the next cursor", () => {
    expect(replaceMentionQuery("参考 @1", 5, 10)).toEqual({
      value: "参考 @10 ",
      cursor: 7,
    });
    expect(replaceMentionQuery("没有查询", 4, 2)).toEqual({ value: "没有查询", cursor: 4 });
  });

  it("normalizes numbered mentions for upstream model text", () => {
    expect(normalizeReferenceMentions("让 @1 参考 @10 的光线")).toBe(
      "让 参考图1 参考 参考图10 的光线",
    );
  });

  it("defines the product hard limit", () => {
    expect(MAX_REFERENCE_ASSETS).toBe(10);
  });
});

describe("reference mention integration", () => {
  const appSource = readFileSync(new URL("./App.vue", import.meta.url), "utf8");

  it("selects references for both image and video prompts", () => {
    expect(appSource).toContain("referencesForPrompt(finalPrompt, imageState.references)");
    expect(appSource).toContain("referencesForPrompt(finalPrompt, videoState.unifiedImages)");
    expect(appSource).toContain("referencesForPrompt(finalPrompt, videoState.seedanceReferences)");
  });

  it("blocks invalid references before a generation request", () => {
    expect(appSource).toContain("invalidReferenceMessage(referenceSelection.invalid)");
    expect(appSource).toContain("normalizeReferenceMentions(finalPrompt)");
  });
});
