import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

import {
  ADMIN_PAGE_SUGGESTIONS,
  ADMIN_RECORD_CAPABILITY_BY_TAB,
  adminNavGroups,
  adminTabs,
} from "./adminPresentation";

const adminStyles = readFileSync(new URL("./styles.css", import.meta.url), "utf8");

describe("admin presentation metadata", () => {
  it("groups each admin tab exactly once", () => {
    const groupedTabs = adminNavGroups.flatMap((group) => group.tabs);

    expect(groupedTabs).toHaveLength(adminTabs.length);
    expect(new Set(groupedTabs).size).toBe(adminTabs.length);
    expect(groupedTabs.sort()).toEqual(adminTabs.map((tab) => tab.value).sort());
  });

  it("provides at least three optimization suggestions for every page", () => {
    for (const tab of adminTabs) {
      expect(ADMIN_PAGE_SUGGESTIONS[tab.value], tab.value).toHaveLength(3);
    }
  });

  it("keeps admin labels and suggestions readable Chinese without mojibake", () => {
    const suspectPattern = /[�]|(?:鍒|绠|鐢|鎿|璋|妯|瑙|浣|闈|杩|瀹|宸|褰|澧|嗘|傛)/;
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

  it("maps record tabs to the correct creative capability", () => {
    expect(ADMIN_RECORD_CAPABILITY_BY_TAB["text-records"]).toBe("text");
    expect(ADMIN_RECORD_CAPABILITY_BY_TAB["image-records"]).toBe("image");
    expect(ADMIN_RECORD_CAPABILITY_BY_TAB["video-records"]).toBe("video");
  });

  it("does not promote every admin button into a primary gradient action", () => {
    expect(adminStyles).not.toContain(
      ".shell-admin button:not(.button-secondary):not(.button-danger):not(:disabled)",
    );
  });

  it("keeps admin failed-model rows readable on light panels", () => {
    expect(adminStyles).toContain(".shell-admin .admin-failed-model");
    expect(adminStyles).toContain("color: var(--admin-text)");
  });

  it("keeps admin search toolbars in normal document flow", () => {
    expect(adminStyles).not.toMatch(/\.shell-admin\s+\.admin-toolbar\s*\{[^}]*position:\s*sticky/s);
  });

  it("does not use purple as the final video/admin progress accent", () => {
    const finalLayer = adminStyles.split("Creative Workshop visual system v4").pop() || "";
    expect(finalLayer).not.toMatch(/#(?:7c3aed|8b5cf6|b78cff|a7a5ff)/i);
    expect(finalLayer).not.toMatch(/--studio-violet/);
  });
});
