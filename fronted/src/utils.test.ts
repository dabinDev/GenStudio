import { describe, expect, it } from "vitest";

import type { ModelDefinition, ModelSetting } from "./types";
import {
  appendLocalConversationMessages,
  updateLocalConversationMessage,
  markConversationMessageFailed,
  generatedAssetReferenceFileName,
  findPromptBeforeMessage,
  getModelIdentifierError,
  getMissingModelMessage,
  imageGenerationSummary,
  mediaPreviewActionLabels,
  pickPrimaryModel,
  filterModelOptions,
  catalogDefaultValue,
  catalogOptionItems,
  catalogParameterSignature,
  catalogRequestKey,
  hasCatalogParameters,
  hasCatalogParameter,
  prioritizeModelOptions,
  modelDisplayNameFromPrimary,
  modelDisplayNameForModel,
  renderMarkdownPreview,
  resolveModelName,
  shouldResetConversationForModelSwitch,
  supportsCatalogParameter,
  testResultSummary,
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

  it("filters model options without changing the original order for empty searches", () => {
    const options = ["gpt-5.5", "gpt-image-2", "doubao-seedance-2-0"];

    expect(filterModelOptions(options, "")).toEqual(options);
    expect(filterModelOptions(options, "GPT")).toEqual(["gpt-5.5", "gpt-image-2"]);
    expect(filterModelOptions(options, "seed")).toEqual(["doubao-seedance-2-0"]);
  });

  it("pins the selected model at the top without dropping other options", () => {
    expect(
      prioritizeModelOptions(
        ["claude-haiku", "doubao-seedance-2-0-fast", "gpt-image-2"],
        "doubao-seedance-2-0-fast",
      ),
    ).toEqual(["doubao-seedance-2-0-fast", "claude-haiku", "gpt-image-2"]);
    expect(prioritizeModelOptions(["gpt-5.5", "gpt-image-2"], "missing")).toEqual(["gpt-5.5", "gpt-image-2"]);
  });

  it("reads generation controls from the selected sub-model catalog", () => {
    const catalogModel: ModelDefinition = {
      ...textModel,
      id: "video-model",
      capability: "video",
      adapter: "video-unified-generic",
      primarySubModelId: "sub-video",
      subModels: [
        {
          id: "sub-video",
          modelName: "kuaikuai-2-flash-pro",
          displayName: "Seed Video",
          capability: "video",
          adapter: "video-unified-generic",
          isPrimary: true,
          status: "active",
          catalog: {
            id: "10028",
            displayName: "Seed Video",
            modelName: "kuaikuai-2-flash-pro",
            modelType: 3,
            capability: "video",
            icon: "",
            description: "",
            inputHint: "",
            successRate: "",
            source: "kkyi",
            channelGroups: [],
            parameters: [
              {
                id: "ratio",
                displayName: "视频比例",
                paramKey: "ratio",
                description: "",
                widgetType: 3,
                isRequired: true,
                defaultValue: "16:9",
                functionTag: "",
                maxCount: null,
                sortOrder: 1,
                options: [
                  { id: "ratio-1", optionName: "竖屏 9:16", optionValue: "9:16", description: "", maxCount: null, isDefault: false, sortOrder: 1, priceFactor: "1" },
                  { id: "ratio-2", optionName: "横屏 16:9", optionValue: "16:9", description: "", maxCount: null, isDefault: true, sortOrder: 2, priceFactor: "1" },
                ],
              },
              {
                id: "duration",
                displayName: "视频时长",
                paramKey: "duration",
                description: "",
                widgetType: 3,
                isRequired: true,
                defaultValue: "5",
                functionTag: "",
                maxCount: null,
                sortOrder: 2,
                options: [
                  { id: "duration-1", optionName: "4秒", optionValue: "4", description: "", maxCount: null, isDefault: false, sortOrder: 1, priceFactor: "1" },
                  { id: "duration-2", optionName: "5秒", optionValue: "5", description: "", maxCount: null, isDefault: true, sortOrder: 2, priceFactor: "1" },
                ],
              },
            ],
          },
        },
      ],
      builtin: false,
    };

    expect(hasCatalogParameter(catalogModel, "ratio")).toBe(true);
    expect(catalogDefaultValue(catalogModel, "ratio", "1:1")).toBe("16:9");
    expect(catalogOptionItems(catalogModel, "ratio", ["1:1"]).map((item) => item.value)).toEqual(["9:16", "16:9"]);
    expect(catalogOptionItems(catalogModel, "ratio", ["1:1"])[1].label).toBe("横屏 16:9");
    expect(catalogDefaultValue(catalogModel, "duration", "8")).toBe("5");
  });

  it("uses catalog parameters as the supported composer parameter contract", () => {
    const catalogModel: ModelDefinition = {
      ...textModel,
      id: "image-model",
      capability: "image",
      adapter: "image-openai",
      primarySubModelId: "sub-image",
      subModels: [
        {
          id: "sub-image",
          modelName: "gpt-image-2",
          displayName: "GPT Image 2",
          capability: "image",
          adapter: "image-openai",
          isPrimary: true,
          status: "active",
          catalog: {
            id: "10029",
            displayName: "GPT Image 2",
            modelName: "gpt-image-2",
            modelType: 2,
            capability: "image",
            icon: "",
            description: "",
            inputHint: "",
            successRate: "",
            source: "kkyi",
            channelGroups: [],
            parameters: [
              {
                id: "size",
                displayName: "尺寸",
                paramKey: "size",
                description: "",
                widgetType: 3,
                isRequired: true,
                defaultValue: "auto",
                functionTag: "",
                maxCount: null,
                sortOrder: 1,
                options: [
                  { id: "size-auto", optionName: "自动", optionValue: "auto", description: "", maxCount: null, isDefault: true, sortOrder: 1, priceFactor: "1" },
                  { id: "size-square", optionName: "正方形", optionValue: "1024x1024", description: "", maxCount: null, isDefault: false, sortOrder: 2, priceFactor: "1" },
                ],
              },
              {
                id: "quality",
                displayName: "质量",
                paramKey: "quality",
                description: "",
                widgetType: 3,
                isRequired: false,
                defaultValue: "auto",
                functionTag: "",
                maxCount: null,
                sortOrder: 2,
                options: [],
              },
            ],
          },
        },
      ],
      builtin: false,
    };

    expect(hasCatalogParameters(catalogModel)).toBe(true);
    expect(supportsCatalogParameter(catalogModel, "size")).toBe(true);
    expect(supportsCatalogParameter(catalogModel, "ratio")).toBe(false);
    expect(supportsCatalogParameter({ ...catalogModel, subModels: [] }, "ratio")).toBe(true);
    expect(catalogParameterSignature(catalogModel)).toContain("size:auto");
    expect(catalogParameterSignature(catalogModel)).not.toBe(catalogParameterSignature({
      ...catalogModel,
      subModels: catalogModel.subModels?.map((subModel) => ({
        ...subModel,
        catalog: subModel.catalog ? {
          ...subModel.catalog,
          parameters: subModel.catalog.parameters.map((parameter) =>
            parameter.paramKey === "size" ? { ...parameter, defaultValue: "1024x1024" } : parameter,
          ),
        } : null,
      })),
    }));
  });

  it("reads aliased catalog parameter names and preserves the request key from the selected model", () => {
    const catalogModel: ModelDefinition = {
      ...textModel,
      id: "alias-video-model",
      capability: "video",
      adapter: "video-unified-generic",
      primarySubModelId: "sub-video-alias",
      subModels: [
        {
          id: "sub-video-alias",
          modelName: "alias-video",
          displayName: "Alias Video",
          capability: "video",
          adapter: "video-unified-generic",
          isPrimary: true,
          status: "active",
          catalog: {
            id: "90001",
            displayName: "Alias Video",
            modelName: "alias-video",
            modelType: 3,
            capability: "video",
            icon: "",
            description: "",
            inputHint: "",
            successRate: "",
            source: "kkyi",
            channelGroups: [],
            parameters: [
              {
                id: "aspect",
                displayName: "Aspect Ratio",
                paramKey: "aspect_ratio",
                description: "",
                widgetType: 3,
                isRequired: true,
                defaultValue: "9:16",
                functionTag: "",
                maxCount: null,
                sortOrder: 1,
                options: [
                  { id: "aspect-1", optionName: "Vertical", optionValue: "9:16", description: "", maxCount: null, isDefault: true, sortOrder: 1, priceFactor: "1" },
                  { id: "aspect-2", optionName: "Wide", optionValue: "16:9", description: "", maxCount: null, isDefault: false, sortOrder: 2, priceFactor: "1" },
                ],
              },
              {
                id: "size",
                displayName: "Size",
                paramKey: "size",
                description: "",
                widgetType: 3,
                isRequired: false,
                defaultValue: "1080p",
                functionTag: "",
                maxCount: null,
                sortOrder: 2,
                options: [
                  { id: "size-1", optionName: "720p", optionValue: "720p", description: "", maxCount: null, isDefault: false, sortOrder: 1, priceFactor: "1" },
                  { id: "size-2", optionName: "1080p", optionValue: "1080p", description: "", maxCount: null, isDefault: true, sortOrder: 2, priceFactor: "1" },
                ],
              },
              {
                id: "audio",
                displayName: "Audio",
                paramKey: "audio",
                description: "",
                widgetType: 5,
                isRequired: false,
                defaultValue: "false",
                functionTag: "",
                maxCount: null,
                sortOrder: 3,
                options: [],
              },
            ],
          },
        },
      ],
      builtin: false,
    };

    expect(hasCatalogParameter(catalogModel, ["ratio", "aspect_ratio"])).toBe(true);
    expect(catalogDefaultValue(catalogModel, ["ratio", "aspect_ratio"], "16:9")).toBe("9:16");
    expect(catalogOptionItems(catalogModel, ["resolution", "size"], ["720p"]).map((item) => item.value)).toEqual(["720p", "1080p"]);
    expect(catalogRequestKey(catalogModel, ["generate_audio", "audio"], "audio")).toBe("audio");
    expect(catalogRequestKey(catalogModel, ["resolution", "size"], "resolution")).toBe("size");
    expect(catalogRequestKey({ ...catalogModel, subModels: [] }, ["resolution", "size"], "resolution")).toBe("resolution");
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

  it("uses the selected primary model for default display names", () => {
    expect(modelDisplayNameFromPrimary("text", "gpt-5.5")).toBe("gpt-5.5 文案");
    expect(modelDisplayNameFromPrimary("image", "gpt-image-2")).toBe("gpt-image-2 图片");
    expect(modelDisplayNameFromPrimary("video", "doubao-seedance-2-0-fast-260128")).toBe("doubao-seedance-2-0-fast-260128 视频");
    expect(modelDisplayNameFromPrimary("video", "")).toBe("视频模型");
  });

  it("replaces generic saved model names with the selected primary model in lists", () => {
    const genericVideoModel: ModelDefinition = {
      ...textModel,
      id: "custom-video",
      name: "视频模型配置",
      capability: "video",
      adapter: "video-unified-generic",
      model: "video-placeholder",
    };

    expect(
      modelDisplayNameForModel(
        genericVideoModel,
        setting({ modelNameOverride: "doubao-seedance-2-0-fast-260128" }),
      ),
    ).toBe("doubao-seedance-2-0-fast-260128 视频");
    expect(modelDisplayNameForModel({ ...genericVideoModel, name: "我的视频号脚本模型" }, setting({}))).toBe(
      "我的视频号脚本模型",
    );
  });

  it("formats test results without empty status or duration placeholders", () => {
    expect(
      testResultSummary({
        ok: true,
        status: 200,
        durationMs: 1234,
        request: { url: "https://token.example.com/v1/chat/completions" },
        raw: { id: "chatcmpl-test", model: "gpt-5.5" },
      }),
    ).toEqual({
      status: "200",
      duration: "1234ms",
      requestUrl: "https://token.example.com/v1/chat/completions",
      rawPreview: '{\n  "id": "chatcmpl-test",\n  "model": "gpt-5.5"\n}',
    });

    expect(testResultSummary({ raw: {} })).toEqual({
      status: "未知",
      duration: "未知",
      requestUrl: "未知",
      rawPreview: "{}",
    });

    expect(
      testResultSummary({
        status: "",
        durationMs: "",
        request: { url: "" },
        raw: {},
      }),
    ).toMatchObject({
      status: "未知",
      duration: "未知",
      requestUrl: "未知",
    });
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

  it("updates a pending assistant message in the local conversation flow", () => {
    const pending = appendLocalConversationMessages(null, {
      capability: "image",
      titleSeed: "生成汽车海报",
      modelGroupId: "image-model",
      subModelId: "sub-image",
      now: "2026-06-06T01:04:00.000Z",
      messages: [
        { role: "user", content: "生成汽车海报" },
        { role: "assistant", content: "", status: "processing" },
      ],
    });
    const pendingAssistant = pending.messages[1];

    const failed = updateLocalConversationMessage(pending, pendingAssistant.id, {
      status: "error",
      errorMessage: "上游服务超时，请稍后重试。",
      canRetry: true,
      content: "",
    });

    expect(failed.messages[0]).toMatchObject({ role: "user", content: "生成汽车海报", status: "success" });
    expect(failed.messages[1]).toMatchObject({
      role: "assistant",
      status: "error",
      errorMessage: "上游服务超时，请稍后重试。",
      canRetry: true,
    });
    expect(failed.updatedAt).not.toBe(pending.updatedAt);
  });

  it("keeps the local request visible when an image proxy error has no server conversation", () => {
    const pending = appendLocalConversationMessages(null, {
      capability: "image",
      titleSeed: "生成汽车人",
      modelGroupId: "image-model",
      subModelId: null,
      now: "2026-06-06T01:04:00.000Z",
      messages: [
        { role: "user", content: "生成汽车人" },
        { role: "assistant", content: "", status: "processing" },
      ],
    });

    const failed = markConversationMessageFailed(pending, pending.messages[1].id, "上游服务超时，请稍后重试。");

    expect(failed?.messages.map((item) => item.role)).toEqual(["user", "assistant"]);
    expect(failed?.messages[0]).toMatchObject({ content: "生成汽车人", status: "success" });
    expect(failed?.messages[1]).toMatchObject({
      role: "assistant",
      status: "error",
      errorMessage: "上游服务超时，请稍后重试。",
      canRetry: true,
      content: "",
    });
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
