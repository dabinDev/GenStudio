import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchImagePromptRecommendations, recordPromptLibraryEvent, setCsrfToken } from "./api";

function okJson(payload: unknown) {
  return Response.json(payload);
}

describe("prompt library API", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    setCsrfToken("");
  });

  it("requests image prompt recommendations and records tag clicks with csrf", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => okJson({
      recommendations: [
        {
          id: "pst_1",
          label: "电影感头像",
          promptText: "生成电影感头像",
          clickCount: 0,
        },
      ],
      reason: "ok",
      template: {
        id: "pst_1",
        label: "电影感头像",
        promptText: "生成电影感头像",
        clickCount: 1,
      },
    }));
    vi.stubGlobal("fetch", fetchMock);
    setCsrfToken("csrf-token");

    await fetchImagePromptRecommendations("https://cdn.example.com/reference.png", 6);
    await recordPromptLibraryEvent("pst_1", "click", "https://cdn.example.com/reference.png");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/prompt-library/image-recommendations",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ imageUrl: "https://cdn.example.com/reference.png", limit: 6 }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/prompt-library/events",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          templateId: "pst_1",
          eventType: "click",
          imageUrl: "https://cdn.example.com/reference.png",
        }),
      }),
    );
    for (const call of fetchMock.mock.calls) {
      const headers = (call[1] as RequestInit).headers as Record<string, string>;
      expect(headers["X-CSRF-Token"]).toBe("csrf-token");
    }
  });
});
