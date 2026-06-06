import { describe, expect, it } from "vitest";

import type { ModelDefinition, ModelSetting } from "./types";
import {
  appendLocalConversationMessages,
  generatedAssetReferenceFileName,
  findPromptBeforeMessage,
  getModelIdentifierError,
  getMissingModelMessage,
  imageGenerationSummary,
  mediaPreviewActionLabels,
  pickPrimaryModel,
  renderMarkdownPreview,
  resolveModelName,
  shouldResetConversationForModelSwitch,
  videoGenerationSummary,
} from "./utils";
import type { ConversationDefinition, ConversationMessage } from "./types";

const textModel: ModelDefinition = {
  id: "custom-text",
  name: "Custom Text",
  vendor: "Test",
  capability: "text",
  adapter: "text-chat",
  model: "gpt-4o",
  description: "Test model",
  builtin: false,
};

function setting(patch: Partial<ModelSetting>): ModelSetting {
  return {
    baseUrl: "https://token.example.com",
    apiKey: "test-key",
    modelNameOverride: "",
    availableModels: [],
    ...patch,
  };
}

describe("model selection helpers", () => {
  it("uses the saved primary model when generating requests", () => {
    expect(
      resolveModelName(
        textModel,
        setting({
          modelNameOverride: "gpt-4.1",
          availableModels: ["gpt-4o", "gpt-4.1"],
        }),
      ),
    ).toBe("gpt-4.1");
  });

  it("keeps a valid primary model and otherwise picks the first fetched model", () => {
    expect(pickPrimaryModel(["gpt-4o", "gpt-4.1"], "gpt-4.1")).toBe("gpt-4.1");
    expect(pickPrimaryModel(["gpt-4o", "gpt-4.1"], "missing-model")).toBe("gpt-4o");
    expect(pickPrimaryModel([], "manual-model")).toBe("manual-model");
  });

  it("rejects URL-shaped model identifiers before saving or testing", () => {
    expect(getModelIdentifierError("https://token.example.com")).toContain("baseURL");
    expect(getModelIdentifierError("gpt-4o")).toBe("");
  });

  it("explains why a send action cannot run without a matching model", () => {
    expect(getMissingModelMessage("text")).toContain("文案创作模型");
    expect(getMissingModelMessage("image")).toContain("图片创作模型");
    expect(getMissingModelMessage("video")).toContain("视频创作模型");
  });
});

describe("conversation helpers", () => {
  it("renders markdown previews while escaping raw html", () => {
    const html = renderMarkdownPreview([
      "# 标题",
      "",
      "这是 **重点**",
      "",
      "- 第一项",
      "- 第二项",
      "",
      "```js",
      "console.log('<x>')",
      "```",
      "",
      "<script>alert(1)</script>",
    ].join("\n"));

    expect(html).toContain("<h1>标题</h1>");
    expect(html).toContain("<strong>重点</strong>");
    expect(html).toContain("<ul><li>第一项</li><li>第二项</li></ul>");
    expect(html).toContain("<pre><code>console.log(&#39;&lt;x&gt;&#39;)</code></pre>");
    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(html).not.toContain("<script>");
  });

  it("finds the nearest user prompt before a failed assistant message", () => {
    const messages = [
      message({ id: "m1", role: "user", content: "第一次" }),
      message({ id: "m2", role: "assistant", content: "成功" }),
      message({ id: "m3", role: "user", content: "第二次" }),
      message({ id: "m4", role: "assistant", status: "error", canRetry: true }),
    ];

    expect(findPromptBeforeMessage(messages, "m4")).toBe("第二次");
  });

  it("resets the visible conversation when switching to a different capability model", () => {
    expect(shouldResetConversationForModelSwitch({ capability: "image" }, "video")).toBe(true);
    expect(shouldResetConversationForModelSwitch({ capability: "image" }, "image")).toBe(false);
    expect(shouldResetConversationForModelSwitch(null, "text")).toBe(false);
  });

  it("uses readable filenames for generated data-url references", () => {
    expect(
      generatedAssetReferenceFileName({
        assetType: "image",
        url: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAE=",
      }),
    ).toBe("generated-image.png");
    expect(
      generatedAssetReferenceFileName({
        assetType: "video",
        url: "https://cdn.example.com/clip.mp4?download=1",
      }),
    ).toBe("clip.mp4");
  });

  it("keeps generated image previews in the creation workflow with editing actions", () => {
    expect(mediaPreviewActionLabels("image")).toEqual(["保存", "引用编辑", "选取编辑", "关闭"]);
    expect(mediaPreviewActionLabels("video")).toEqual(["保存", "关闭"]);
  });

  it("summarizes generation controls without scheduler priority labels", () => {
    const imageSummary = imageGenerationSummary({ ratio: "16:9", resolution: "2k", count: "1" });
    const videoSummary = videoGenerationSummary({
      mode: "reference",
      aspectRatio: "9:16",
      resolution: "720p",
      duration: "5",
      count: "1",
    });

    expect(imageSummary).toBe("16:9  2k  1张");
    expect(videoSummary).toBe("全能参考  9:16  720p  5秒  1条");
    expect(`${imageSummary} ${videoSummary}`).not.toContain("价格优先");
    expect(`${imageSummary} ${videoSummary}`).not.toContain("质量优先");
  });

  it("creates a visible local conversation when a proxy response has no server conversation", () => {
    const conversation = appendLocalConversationMessages(null, {
      capability: "text",
      titleSeed: "你好",
      modelGroupId: "local-gpt",
      now: "2026-06-06T01:00:00.000Z",
      messages: [
        { role: "user", content: "你好" },
        { role: "assistant", content: "# 你好\n\n我在。", status: "success" },
      ],
    });

    expect(conversation.title).toBe("你好");
    expect(conversation.capability).toBe("text");
    expect(conversation.modelGroupId).toBe("local-gpt");
    expect(conversation.messages.map((item) => [item.role, item.content])).toEqual([
      ["user", "你好"],
      ["assistant", "# 你好\n\n我在。"],
    ]);
  });

  it("appends local messages to the current conversation for the same capability", () => {
    const existing = conversation({
      id: "local-conversation",
      capability: "text",
      messages: [message({ id: "m1", role: "user", content: "第一次" })],
    });

    const next = appendLocalConversationMessages(existing, {
      capability: "text",
      titleSeed: "第二次",
      modelGroupId: "local-gpt",
      now: "2026-06-06T01:02:00.000Z",
      messages: [
        { role: "user", content: "第二次" },
        { role: "assistant", content: "第二次回复", status: "success" },
      ],
    });

    expect(next.id).toBe("local-conversation");
    expect(next.messages.map((item) => item.content)).toEqual(["第一次", "第二次", "第二次回复"]);
    expect(next.updatedAt).toBe("2026-06-06T01:02:00.000Z");
  });

  it("keeps local generated assets on assistant messages", () => {
    const conversation = appendLocalConversationMessages(null, {
      capability: "image",
      titleSeed: "生成海报",
      modelGroupId: "local-image",
      now: "2026-06-06T01:03:00.000Z",
      messages: [
        { role: "user", content: "生成海报" },
        {
          role: "assistant",
          content: "已生成 1 张图片。",
          assets: [{ assetType: "image", url: "https://cdn.example.com/image.png" }],
        },
      ],
    });

    expect(conversation.messages[1].assets).toEqual([
      expect.objectContaining({
        assetType: "image",
        url: "https://cdn.example.com/image.png",
        capability: "image",
      }),
    ]);
  });
});

function message(patch: Partial<ConversationMessage>): ConversationMessage {
  return {
    id: "",
    role: "assistant",
    capability: "text",
    content: "",
    status: "success",
    errorMessage: "",
    canRetry: false,
    modelGroupId: null,
    subModelId: null,
    assets: [],
    createdAt: "2026-01-01T00:00:00",
    ...patch,
  };
}

function conversation(patch: Partial<ConversationDefinition>): ConversationDefinition {
  return {
    id: "conversation-id",
    title: "本地对话",
    capability: "text",
    modelGroupId: null,
    subModelId: null,
    status: "active",
    createdAt: "2026-01-01T00:00:00",
    updatedAt: "2026-01-01T00:00:00",
    messages: [],
    ...patch,
  };
}
