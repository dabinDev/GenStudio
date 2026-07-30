import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const appSource = () => readFileSync(resolve(process.cwd(), "src/App.vue"), "utf8").replace(/\r\n/g, "\n");

const VIEW_CONTRACTS = [
  { id: "auth", testId: "auth-view", heading: "登录 创意工坊", primaryAction: "auth-primary-action" },
  { id: "text", testId: "text-view", heading: "文案创作", primaryAction: "text-primary-action" },
  { id: "images", testId: "images-view", heading: "图片创作", primaryAction: "images-primary-action" },
  { id: "videos", testId: "videos-view", heading: "视频创作", primaryAction: "videos-primary-action" },
  { id: "settings", testId: "settings-view", heading: "模型配置", primaryAction: "settings-primary-action" },
  { id: "profile", testId: "profile-view", heading: "个人信息", primaryAction: "profile-primary-action" },
] as const;

describe("newui creator presentation contract", () => {
  it("defines a stable landmark and heading for every live view", () => {
    const source = appSource();

    expect(source).toContain("const VIEW_PRESENTATION");
    expect(source).toContain(':data-testid="viewPresentation.testId"');
    expect(source).toContain(':aria-labelledby="viewPresentation.headingId"');
    expect(source).toContain('<h1 :id="viewPresentation.headingId" class="visually-hidden">');
    for (const view of VIEW_CONTRACTS) {
      expect(source).toContain(`${view.id}: {`);
      expect(source).toContain(`testId: "${view.testId}"`);
      expect(source).toContain(`heading: "${view.heading}"`);
    }
  });

  it("exposes one primary action per view", () => {
    const source = appSource();

    for (const view of VIEW_CONTRACTS) {
      expect(source).toContain(`data-testid="${view.primaryAction}"`);
    }
  });

  it("announces loading, empty, error, and ready states without visible helper copy", () => {
    const source = appSource();

    expect(source).toContain('data-testid="view-state"');
    expect(source).toContain('aria-live="polite"');
    expect(source).toContain(':data-state="viewPresentationState"');
    expect(source).toContain('"loading"');
    expect(source).toContain('"empty"');
    expect(source).toContain('"error"');
    expect(source).toContain('"ready"');
    expect(source).toContain('data-testid="creator-empty-state"');
  });
});
