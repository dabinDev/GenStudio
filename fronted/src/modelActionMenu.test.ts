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
