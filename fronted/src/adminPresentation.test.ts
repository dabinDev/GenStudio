import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

import {
  ADMIN_PAGE_SUGGESTIONS,
  ADMIN_RECORD_CAPABILITY_BY_TAB,
  adminNavGroups,
  adminTabs,
} from "./adminPresentation";

const adminStyles = readFileSync(new URL("./styles.css", import.meta.url), "utf8");
const appSource = readFileSync(new URL("./App.vue", import.meta.url), "utf8");

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

  it("keeps the final visual refinement layer focused on compact hierarchy", () => {
    expect(adminStyles).toContain("Creative Workshop visual refinement v5");
    const finalLayer = adminStyles.split("Creative Workshop visual refinement v5").pop() || "";

    expect(finalLayer).toContain(".empty-canvas-card");
    expect(finalLayer).toContain('[data-theme="light"] .empty-canvas-card');
    expect(finalLayer).toContain(".hero-model-mark");
    expect(finalLayer).toContain(".admin-insight-strip");
    expect(finalLayer).toMatch(/width:\s*min\(100%,\s*680px\)/);
    expect(finalLayer).toMatch(/max-height:\s*72px/);
  });

  it("uses a cyan focus treatment instead of the old warm theme-toggle ring", () => {
    const finalLayer = adminStyles.split("Creative Workshop visual refinement v5").pop() || "";

    expect(finalLayer).toMatch(/\.theme-toggle-button:focus-visible/);
    expect(finalLayer).not.toMatch(/theme-toggle-button:focus-visible[\s\S]*#ffcc4d/i);
    expect(finalLayer).not.toMatch(/theme-toggle-button:focus-visible[\s\S]*255,\s*204,\s*77/i);
  });

  it("adds theme-aware custom scrollbars in the final visual layer", () => {
    const finalLayer = adminStyles.split("Creative Workshop visual refinement v5").pop() || "";

    expect(finalLayer).toContain("scrollbar-color");
    expect(finalLayer).toContain("::-webkit-scrollbar");
    expect(finalLayer).toContain("::-webkit-scrollbar-thumb");
  });

  it("keeps the admin loading indicator compact in the final visual layer", () => {
    const finalLayer = adminStyles.split("Creative Workshop visual refinement v5").pop() || "";

    expect(finalLayer).toContain(".shell-admin .admin-loading");
    expect(finalLayer).toMatch(/height:\s*24px/);
  });

  it("adds an adaptive composer that can collapse while preserving the chat timeline", () => {
    expect(appSource).toContain("collapsed: false");
    expect(appSource).toContain("studio-panel-composer-collapsed");
    expect(appSource).toContain("composer-collapse-toggle");
    expect(appSource).toContain("composer-compact-bar");
    expect(appSource).toContain("composerSummary");

    expect(adminStyles).toContain("Creative Workshop interaction refinement v6");
    const finalLayer = adminStyles.split("Creative Workshop interaction refinement v6").pop() || "";

    expect(finalLayer).toContain(".studio-panel-composer-collapsed");
    expect(finalLayer).toContain(".composer-card-collapsed");
    expect(finalLayer).toContain(".composer-collapse-toggle");
    expect(finalLayer).toContain(".composer-compact-bar");
    expect(finalLayer).toMatch(/grid-template-rows:\s*minmax\(0,\s*1fr\)\s*auto/);
  });

  it("stops stale generation polling when starting a new conversation", () => {
    const match = appSource.match(/function startNewConversation[\s\S]*?\n}\n/);
    expect(match?.[0] || "").toContain("stopTextPolling()");
    expect(match?.[0] || "").toContain("stopImagePolling()");
    expect(match?.[0] || "").toContain("stopVideoPolling()");
  });

  it("keeps the final interaction layer cool toned without returning to purple accents", () => {
    const finalLayer = adminStyles.split("Creative Workshop interaction refinement v6").pop() || "";

    expect(finalLayer).toContain("radial-gradient");
    expect(finalLayer).toContain("linear-gradient");
    expect(finalLayer).toContain(":root[data-theme=\"dark\"] .studio-canvas::before");
    expect(finalLayer).toContain("[data-theme=\"light\"] .studio-canvas");
    expect(finalLayer).not.toMatch(/#(?:7c3aed|8b5cf6|b78cff|a7a5ff|9333ea|a855f7)/i);
    expect(finalLayer).not.toMatch(/purple|violet/i);
  });

  it("adds a light-mode refinement layer for readable surfaces and compact composer actions", () => {
    expect(adminStyles).toContain("Creative Workshop light productivity refinement v7");
    const finalLayer = adminStyles.split("Creative Workshop light productivity refinement v7").pop() || "";

    expect(finalLayer).toContain("--cw-day-surface-0");
    expect(finalLayer).toContain("[data-theme=\"light\"] .auth-value-panel");
    expect(finalLayer).toContain("[data-theme=\"light\"] .history-item");
    expect(finalLayer).toContain(".composer-action-group");
    expect(finalLayer).toMatch(/grid-template-columns:\s*minmax\(0,\s*1fr\)\s*auto/);
    expect(finalLayer).not.toMatch(/background:\s*#2[0-9a-f]{5}/i);
  });

  it("keeps image and video query buttons wide enough to avoid vertical labels", () => {
    const finalLayer = adminStyles.split("Creative Workshop light productivity refinement v7").pop() || "";

    expect(appSource).toContain("composer-action-group");
    expect(appSource).toContain("composer-query-button");
    expect(finalLayer).toMatch(/\.composer-query-button[\s\S]*min-width:\s*72px/);
    expect(finalLayer).toMatch(/white-space:\s*nowrap/);
  });

  it("uses an integrated media composer layout for reference uploads and prompt input", () => {
    const finalLayer = adminStyles.split("Creative Workshop light productivity refinement v7").pop() || "";

    expect(appSource).toContain("media-composer-grid");
    expect(appSource).toContain("media-composer-upload");
    expect(finalLayer).toContain(".media-composer-grid");
    expect(finalLayer).toMatch(/grid-template-columns:\s*128px\s+minmax\(0,\s*1fr\)/);
  });

  it("keeps the final v8 theme restrained and prevents sticky toolbars from covering content", () => {
    expect(adminStyles).toContain("Creative Workshop visual refinement v8");
    const finalLayer = adminStyles.split("Creative Workshop visual refinement v8").pop() || "";

    expect(finalLayer).toContain(".shell[data-theme=\"light\"]");
    expect(finalLayer).toContain(".shell[data-theme=\"dark\"]");
    expect(finalLayer).toContain("[data-theme=\"light\"] .settings-list-toolbar");
    expect(finalLayer).toContain("[data-theme=\"light\"] .admin-record-toolbar");
    expect(finalLayer).toMatch(/top:\s*auto\s*!important/);
    expect(finalLayer).toContain(".shell[data-theme=\"dark\"] .history-item");
    expect(finalLayer).toContain(".shell[data-theme=\"dark\"] .model-avatar-has-icon");
    expect(finalLayer).toContain(".shell[data-theme=\"dark\"] .admin-denied");
    expect(finalLayer).toContain(".shell[data-theme=\"dark\"] .composer-card-collapsed");
    expect(finalLayer).not.toMatch(/purple|violet/i);
  });

  it("adds a v9 daylight and mobile workbench polish layer", () => {
    expect(adminStyles).toContain("Creative Workshop visual refinement v9");
    const finalLayer = adminStyles.split("Creative Workshop visual refinement v9").pop() || "";

    expect(finalLayer).toContain("--cw-v9-day-bg");
    expect(finalLayer).toContain(".shell:not(.shell-admin) .sidebar");
    expect(finalLayer).toContain("max-height: 184px");
    expect(finalLayer).toContain(".admin-record-toolbar .settings-filter-tab span");
    expect(finalLayer).toContain(".admin-record-json:not([open])");
    expect(finalLayer).toContain(".shell-admin .admin-tab");
    expect(finalLayer).not.toMatch(/purple|violet/i);
  });

  it("adds a v10 light console polish layer with readable admin controls", () => {
    expect(adminStyles).toContain("Creative Workshop visual refinement v10");
    const finalLayer = adminStyles.split("Creative Workshop visual refinement v10").pop() || "";

    expect(finalLayer).toContain("--cw-v10-paper");
    expect(finalLayer).toContain(".shell-admin[data-theme=\"light\"] .admin-sidebar");
    expect(finalLayer).toContain(".shell-admin[data-theme=\"light\"] .admin-record-toolbar");
    expect(finalLayer).toContain(".shell-admin[data-theme=\"light\"] .admin-data-row");
    expect(finalLayer).toContain(".shell-admin[data-theme=\"light\"] .admin-empty");
    expect(finalLayer).toContain(".shell[data-theme=\"light\"] .composer-card");
    expect(finalLayer).toContain(".shell[data-theme=\"dark\"] .studio-canvas");
    expect(finalLayer).toMatch(/top:\s*auto\s*!important/);
    expect(finalLayer).not.toMatch(/purple|violet/i);
    expect(finalLayer).not.toMatch(/#(?:7c3aed|8b5cf6|b78cff|a7a5ff|9333ea|a855f7)/i);
  });

  it("keeps the model picker scrim invisible instead of inheriting button gradients", () => {
    const finalLayer = adminStyles.split("Creative Workshop visual refinement v10").pop() || "";

    expect(finalLayer).toContain(".model-select-scrim");
    expect(finalLayer).toMatch(/\.model-select-scrim[\s\S]*background:\s*transparent\s*!important/);
    expect(finalLayer).toMatch(/\.model-select-scrim[\s\S]*border:\s*0\s*!important/);
    expect(finalLayer).toMatch(/\.model-select-scrim[\s\S]*box-shadow:\s*none\s*!important/);
    expect(finalLayer).toMatch(/\.model-select-scrim[\s\S]*transform:\s*none\s*!important/);
  });

  it("adds a v11 command-center admin layout instead of stacked admin card walls", () => {
    expect(adminStyles).toContain("Creative Workshop admin command center v11");
    expect(appSource).toContain("admin-console-dashboard");
    expect(appSource).toContain("admin-command-panel");
    expect(appSource).toContain("admin-list-shell");
    expect(appSource).toContain("admin-record-preview-clamp");

    const finalLayer = adminStyles.split("Creative Workshop admin command center v11").pop() || "";
    expect(finalLayer).toContain(".admin-console-dashboard");
    expect(finalLayer).toContain(".admin-command-panel");
    expect(finalLayer).toContain(".admin-list-shell");
    expect(finalLayer).toContain(".admin-record-preview-clamp");
    expect(finalLayer).toMatch(/grid-template-columns:\s*minmax\(0,\s*1fr\)\s+minmax\(280px,\s*360px\)/);
    expect(finalLayer).toMatch(/-webkit-line-clamp:\s*3/);
    expect(finalLayer).not.toMatch(/purple|violet/i);
  });
});
