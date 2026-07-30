// @vitest-environment jsdom

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type { UploadedAsset } from "../types";
import ReferenceMentionMenu from "./ReferenceMentionMenu.vue";

const assets: UploadedAsset[] = [1, 2, 3].map((index) => ({
  id: `asset-${index}`,
  fileName: `reference-${index}.png`,
  publicUrl: `https://cdn.example/reference-${index}.png`,
  contentType: "image/png",
  localPreviewUrl: `blob:reference-${index}`,
}));

describe("ReferenceMentionMenu", () => {
  it("renders an accessible option for every visible reference", () => {
    const wrapper = mount(ReferenceMentionMenu, {
      props: { assets, query: "", activeIndex: 0 },
    });

    expect(wrapper.get('[role="listbox"]').attributes("aria-label")).toBe("引用图片");
    expect(wrapper.findAll('[role="option"]').map((item) => item.attributes("aria-label"))).toEqual([
      "引用图片 1",
      "引用图片 2",
      "引用图片 3",
    ]);
  });

  it("filters by number or file name", async () => {
    const wrapper = mount(ReferenceMentionMenu, {
      props: { assets, query: "2", activeIndex: 0 },
    });

    expect(wrapper.findAll('[role="option"]')).toHaveLength(1);
    expect(wrapper.get('[role="option"]').attributes("aria-label")).toBe("引用图片 2");

    await wrapper.setProps({ query: "reference-3" });
    expect(wrapper.findAll('[role="option"]')).toHaveLength(1);
    expect(wrapper.get('[role="option"]').attributes("aria-label")).toBe("引用图片 3");
  });

  it("emits the one-based index and supports Escape", async () => {
    const wrapper = mount(ReferenceMentionMenu, {
      props: { assets, query: "", activeIndex: 1 },
    });

    const options = wrapper.findAll('[role="option"]');
    expect(options[1].attributes("aria-selected")).toBe("true");
    await options[1].trigger("click");
    expect(wrapper.emitted("select")).toEqual([[2]]);

    await wrapper.get('[role="listbox"]').trigger("keydown", { key: "Escape" });
    expect(wrapper.emitted("close")).toHaveLength(1);
  });
});

describe("reference strip integration", () => {
  const appSource = readFileSync(resolve(process.cwd(), "src/App.vue"), "utf8");

  it("renders index badges for image and every video reference role", () => {
    expect(appSource.match(/class="reference-index-badge"/g)).toHaveLength(5);
    expect(appSource).toContain("imageIndex + 1");
    expect(appSource).toContain("unifiedIndex + 1");
    expect(appSource).toContain("seedanceIndex + 1");
  });

  it("tracks mention queries on both prompt editors", () => {
    expect(appSource).toContain('@input="updateMentionMenu(\'image\', $event)"');
    expect(appSource).toContain('@input="updateMentionMenu(\'video\', $event)"');
    expect(appSource).toContain('@keydown="handleMentionMenuKeydown(\'image\', $event)"');
    expect(appSource).toContain('@keydown="handleMentionMenuKeydown(\'video\', $event)"');
  });
});
