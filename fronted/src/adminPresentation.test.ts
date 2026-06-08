import { describe, expect, it } from "vitest";

import {
  ADMIN_PAGE_SUGGESTIONS,
  ADMIN_RECORD_CAPABILITY_BY_TAB,
  adminNavGroups,
  adminTabs,
} from "./adminPresentation";

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

  it("maps record tabs to the correct creative capability", () => {
    expect(ADMIN_RECORD_CAPABILITY_BY_TAB["text-records"]).toBe("text");
    expect(ADMIN_RECORD_CAPABILITY_BY_TAB["image-records"]).toBe("image");
    expect(ADMIN_RECORD_CAPABILITY_BY_TAB["video-records"]).toBe("video");
  });
});
