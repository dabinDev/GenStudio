import { describe, expect, it } from "vitest";

import type { ModelDefinition, ModelSetting } from "./types";
import {
  appendLocalConversationMessages,
  authCodeCallbackNextPath,
  buildImageGenerationRequestBody,
  buildVideoMediaFields,
  filterVideoModeOptionsForModel,
  updateLocalConversationMessage,
  updateLocalConversationTaskMessage,
  markConversationMessageFailed,
  catalogOptionMaxCount,
  catalogReferenceLimit,
  composerShortcutFromKeyboardEvent,
  conversationDisplayTitle,
  generatedAssetReferenceFileName,
  latestConversationForModel,
  findPromptBeforeMessage,
  getModelIdentifierError,
  getMissingModelMessage,
  imageGenerationCreditCost,
  imageGenerationSummary,
  canEditModel,
  deleteConfirmationSummary,
  isPrivateView,
  loginRedirectForView,
  mediaPreviewActionLabels,
  nextMediaPreviewTransform,
  normalizeThemeMode,
  resolveAdminConsoleHref,
  toggleThemeMode,
  unavailableTestedModels,
  filterSettingsModels,
  capabilityFilterForView,
  pickPrimaryModel,
  filterModelOptions,
  catalogDefaultValue,
  catalogOptionItems,
  catalogParameterSignature,
  catalogRequestKey,
  catalogVideoModeValue,
  hasCatalogParameters,
  hasCatalogParameter,
  prioritizeModelOptions,
  modelCatalogInputHint,
  modelCatalogIconUrl,
  modelConnectionLabel,
  modelIdentityAccent,
  modelDisplayNameFromPrimary,
  modelDisplayNameForModel,
  modelParameterSourceLabel,
  publicShareTargetModels,
  publicModelAccent,
  publicModelCardDescription,
  resolvePostAuthTarget,
  resolveSidebarFilter,
  renderMarkdownPreview,
  resolveAuthRedirect,
  resolveModelName,
  safeModelDescription,
  shouldResetConversationForModelSwitch,
  shouldContinuePollingTask,
  supportsImage4k,
  image4kSizeForRatio,
  conversationAssetsFromImageQueryResult,
  mergeImageQueryAssets,
  conversationAssetFromVideoQueryResult,
  supportsCatalogParameter,
  testResultSummary,
  visibleConversationMessages,
  videoDurationFallbackOptions,
  videoDurationOptionItems,
  videoResolutionRequestKey,
  videoGenerationSummary,
  videoMessageStatusFromTaskStatus,
  videoModeParamValue,
  videoModeRequiredUploadCount,
  videoModeUploadLimit,
  filterReferenceImageFiles,
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

function modelWithParameterMax(
  capability: "image" | "video",
  paramKey: string,
  maxCount: number,
): ModelDefinition {
  return {
    ...textModel,
    id: `${capability}-${paramKey}-${maxCount}`,
    capability,
    adapter: capability === "image" ? "image-openai" : "video-unified-generic",
    catalog: {
      id: "catalog-test",
      displayName: "Catalog Test",
      modelName: "catalog-test",
      modelType: 0,
      capability,
      icon: "",
      description: "",
      inputHint: "",
      successRate: "",
      source: "test",
      channelGroups: [],
      parameters: [
        {
          id: `parameter-${paramKey}`,
          displayName: paramKey,
          paramKey,
          description: "",
          widgetType: 0,
          isRequired: false,
          defaultValue: "reference",
          functionTag: "",
          maxCount,
          sortOrder: 0,
          options:
            paramKey === "video_mode"
              ? [
                  {
                    id: "reference",
                    optionName: "reference",
                    optionValue: "reference",
                    description: "",
                    maxCount,
                    isDefault: true,
                    sortOrder: 0,
                    priceFactor: "1",
                  },
                ]
              : [],
        },
      ],
    },
  };
}

describe("reference upload helpers", () => {
  it("keeps only supported image files for reference uploads", () => {
    const files = [
      new File(["png"], "scene.png", { type: "image/png" }),
      new File(["jpg"], "car.JPG", { type: "" }),
      new File(["gif"], "motion.gif", { type: "image/gif" }),
      new File(["pdf"], "brief.pdf", { type: "application/pdf" }),
      new File(["webp"], "texture.webp", { type: "image/webp" }),
    ];

    expect(filterReferenceImageFiles(files).map((file) => file.name)).toEqual(["scene.png", "car.JPG", "texture.webp"]);
  });

  it("caps image and video reference limits at ten", () => {
    expect(
      catalogReferenceLimit(modelWithParameterMax("image", "images", 14), ["images"], 14),
    ).toBe(10);
    expect(videoModeUploadLimit(modelWithParameterMax("video", "video_mode", 14), "reference")).toBe(10);
  });

  it("allows ten reference images for uncataloged video models", () => {
    const model: ModelDefinition = {
      ...textModel,
      id: "seedance-without-catalog",
      capability: "video",
      adapter: "video-seedance",
    };

    expect(videoModeUploadLimit(model, "reference")).toBe(10);
    expect(videoModeUploadLimit(model, "first-frame")).toBe(1);
    expect(videoModeUploadLimit(model, "start-end")).toBe(2);
  });

  it("keeps a lower provider reference limit", () => {
    expect(
      catalogReferenceLimit(modelWithParameterMax("image", "images", 4), ["images"], 10),
    ).toBe(4);
  });
});

describe("image 4K helpers", () => {
  const imageOpenAIModel: ModelDefinition = {
    ...textModel,
    id: "image-openai",
    capability: "image",
    adapter: "image-openai",
    model: "gpt-image-2",
  };

  it("allows 4K only for OpenAI-compatible image models", () => {
    expect(supportsImage4k(imageOpenAIModel)).toBe(true);
    expect(supportsImage4k({ ...imageOpenAIModel, adapter: "video-unified-generic", capability: "video" })).toBe(false);
    expect(supportsImage4k({ ...imageOpenAIModel, adapter: "text-chat", capability: "text" })).toBe(false);
    expect(supportsImage4k(null)).toBe(false);
  });

  it("maps common aspect ratios to explicit 4K sizes", () => {
    expect(image4kSizeForRatio("16:9")).toBe("3840x2160");
    expect(image4kSizeForRatio("9:16")).toBe("2160x3840");
    expect(image4kSizeForRatio("1:1")).toBe("4096x4096");
    expect(image4kSizeForRatio("4:3")).toBe("4096x3072");
    expect(image4kSizeForRatio("3:4")).toBe("3072x4096");
    expect(image4kSizeForRatio("2:1")).toBe("4096x2048");
  });

  it("doubles image credit cost after applying quantity for 4K", () => {
    expect(imageGenerationCreditCost(3, "2", true)).toBe(12);
    expect(imageGenerationCreditCost(3, "2", false)).toBe(6);
    expect(imageGenerationCreditCost(3, "", true)).toBe(6);
  });
});

describe("composer keyboard shortcuts", () => {
  it("maps Ctrl+I to prompt optimization and Ctrl+Enter to submit", () => {
    expect(composerShortcutFromKeyboardEvent({ ctrlKey: true, key: "i" })).toBe("optimize");
    expect(composerShortcutFromKeyboardEvent({ ctrlKey: true, key: "I" })).toBe("optimize");
    expect(composerShortcutFromKeyboardEvent({ ctrlKey: true, key: "Enter" })).toBe("submit");
  });

  it("ignores repeated, composing, and modified shortcuts", () => {
    expect(composerShortcutFromKeyboardEvent({ ctrlKey: true, key: "i", repeat: true })).toBeNull();
    expect(composerShortcutFromKeyboardEvent({ ctrlKey: true, key: "i", isComposing: true })).toBeNull();
    expect(composerShortcutFromKeyboardEvent({ ctrlKey: true, altKey: true, key: "i" })).toBeNull();
    expect(composerShortcutFromKeyboardEvent({ metaKey: true, key: "i" })).toBeNull();
    expect(composerShortcutFromKeyboardEvent({ ctrlKey: false, key: "Enter" })).toBeNull();
  });
});

describe("media preview helpers", () => {
  it("keeps images fully visible at the minimum zoom and resets pan at fit scale", () => {
    expect(nextMediaPreviewTransform({ scale: 1, offsetX: 140, offsetY: -90 }, -0.75)).toEqual({
      scale: 0.5,
      offsetX: 0,
      offsetY: 0,
    });
    expect(nextMediaPreviewTransform({ scale: 1.25, offsetX: 140, offsetY: -90 }, -0.25)).toEqual({
      scale: 1,
      offsetX: 0,
      offsetY: 0,
    });
  });

  it("preserves pan while zooming in and caps maximum zoom", () => {
    expect(nextMediaPreviewTransform({ scale: 5.9, offsetX: 120, offsetY: -80 }, 0.5)).toEqual({
      scale: 6,
      offsetX: 120,
      offsetY: -80,
    });
  });
});

describe("theme helpers", () => {
  it("normalizes unknown theme values to light mode by default", () => {
    expect(normalizeThemeMode("light")).toBe("light");
    expect(normalizeThemeMode("dark")).toBe("dark");
    expect(normalizeThemeMode("system")).toBe("light");
    expect(normalizeThemeMode(null)).toBe("light");
  });

  it("toggles between day and night modes", () => {
    expect(toggleThemeMode("dark")).toBe("light");
    expect(toggleThemeMode("light")).toBe("dark");
  });
});

describe("model identity accents", () => {
  it("uses capability colors for private models", () => {
    expect(modelIdentityAccent({ capability: "text", isPublic: false })).toBe("#16835A");
    expect(modelIdentityAccent({ capability: "image", isPublic: false })).toBe("#D85C63");
    expect(modelIdentityAccent({ capability: "video", isPublic: false })).toBe("#3676D8");
  });

  it("uses the configured public model accent when available", () => {
    expect(modelIdentityAccent({ capability: "image", isPublic: true, publicAccentColor: "#A855F7" })).toBe("#A855F7");
  });
});

describe("settings batch delete helpers", () => {
  it("finds only editable tested models with failed connection state", () => {
    const publicModel = { ...textModel, id: "public", serverManaged: true, isPublic: true, canEdit: false };
    const healthyModel = { ...textModel, id: "healthy", serverManaged: true, canEdit: true };
    const failedModel = { ...textModel, id: "failed", serverManaged: true, canEdit: true };
    const untestedModel = { ...textModel, id: "untested", serverManaged: true, canEdit: true };

    expect(
      unavailableTestedModels(
        [publicModel, healthyModel, failedModel, untestedModel],
        {
          public: { loading: false, error: "公共模型不能删除", result: null },
          healthy: { loading: false, error: "", result: { status: 200 } },
          failed: { loading: false, error: "连接失败", result: null },
        },
        canEditModel,
      ).map((model) => model.id),
    ).toEqual(["failed"]);
  });

  it("builds a clear confirmation message for batch model deletion", () => {
    expect(deleteConfirmationSummary("移除不可用", 3, 2)).toContain("确认移除不可用 3 个模型吗？");
    expect(deleteConfirmationSummary("移除不可用", 3, 2)).toContain("已跳过 2 个不可删除模型");
  });
});

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

  it("maps creation pages to the matching sidebar model capability", () => {
    expect(capabilityFilterForView("text")).toBe("text");
    expect(capabilityFilterForView("images")).toBe("image");
    expect(capabilityFilterForView("videos")).toBe("video");
    expect(capabilityFilterForView("settings")).toBe("all");
  });

  it("does not fall back to unrelated sidebar models when a creation capability is empty", () => {
    expect(resolveSidebarFilter([{ ...textModel, capability: "text" }], "image")).toBe("image");
    expect(resolveSidebarFilter([{ ...textModel, capability: "text" }], "video")).toBe("video");
  });

  it("keeps settings pages unfiltered by default so saved KK models remain visible", () => {
    expect(capabilityFilterForView("settings")).toBe("all");
    expect(capabilityFilterForView("profile")).toBe("all");
  });

  it("treats only creative workspace account pages as private login-gated actions", () => {
    expect(isPrivateView("settings")).toBe(true);
    expect(isPrivateView("profile")).toBe(true);
    expect(isPrivateView("admin")).toBe(false);
    expect(isPrivateView("images")).toBe(false);
    expect(loginRedirectForView("settings")).toBe("/auth?redirect=%2Fsettings");
    expect(loginRedirectForView("profile")).toBe("/auth?redirect=%2Fprofile");
    expect(resolveAuthRedirect("#/auth?redirect=%2Fsettings")).toBe("settings");
    expect(resolveAuthRedirect("#/auth?redirect=%2Fprofile")).toBe("profile");
    expect(resolveAuthRedirect("#/auth?redirect=%2Fadmin")).toBe("admin");
    expect(resolveAuthRedirect("#/auth?redirect=%2Fadmin%2F")).toBe("admin");
    expect(resolveAuthRedirect("#/auth?redirect=https%3A%2F%2Fevil.example")).toBe("images");
  });

  it("separates post-auth admin redirects from creative workspace views", () => {
    expect(resolvePostAuthTarget("#/auth?redirect=%2Fadmin%2F", "http://127.0.0.1:5173")).toEqual({
      type: "external",
      href: "http://127.0.0.1:5174/admin/",
    });
    expect(resolvePostAuthTarget("#/auth?redirect=%2Fsettings", "http://127.0.0.1:5173")).toEqual({
      type: "view",
      view: "settings",
    });
    expect(authCodeCallbackNextPath("#/auth?redirect=%2Fadmin%2F")).toBe("/admin/");
    expect(authCodeCallbackNextPath("#/auth?redirect=%2Fsettings")).toBe("/#/settings");
  });

  it("opens the independent admin dev server from local creative workspace ports", () => {
    expect(resolveAdminConsoleHref("http://127.0.0.1:5175")).toBe("http://127.0.0.1:5174/admin/");
    expect(resolveAdminConsoleHref("http://localhost:5173")).toBe("http://localhost:5174/admin/");
    expect(resolveAdminConsoleHref("https://studio.cylonai.cn")).toBe("/admin/");
  });

  it("carries the current workspace theme into the independent admin app", () => {
    expect(resolveAdminConsoleHref("http://127.0.0.1:5175", "dark")).toBe("http://127.0.0.1:5174/admin/?theme=dark");
    expect(resolveAdminConsoleHref("https://studio.cylonai.cn", "light")).toBe("/admin/?theme=light");
    expect(resolveAdminConsoleHref("https://studio.cylonai.cn", "system")).toBe("/admin/");
  });

  it("does not expose upstream endpoints in model list summaries", () => {
    expect(
      modelConnectionLabel(
        { ...textModel, serverManaged: true, isPublic: true, canEdit: false },
        setting({ baseUrl: "https://ai-api.kkidc.com" }),
      ),
    ).toBe("公共模型");
    expect(
      modelConnectionLabel(
        { ...textModel, serverManaged: true, isPublic: false, canEdit: true },
        setting({ baseUrl: "https://token.example.com" }),
      ),
    ).toBe("平台托管");
    expect(modelConnectionLabel(textModel, setting({ baseUrl: "https://token.example.com" }))).toBe("自定义密钥");
    expect(modelConnectionLabel(textModel, setting({ baseUrl: "" }))).toBe("未配置");
  });

  it("strips upstream urls from readonly public model descriptions", () => {
    expect(
      safeModelDescription(
        {
          ...textModel,
          isPublic: true,
          canEdit: false,
          description: "KK fast provider models from https://ai-api.kkidc.com",
        },
        "fallback",
      ),
    ).toBe("平台公共模型，可直接用于创作。");
    expect(
      safeModelDescription(
        { ...textModel, isPublic: false, canEdit: true, description: "Private https://token.example.com" },
        "fallback",
      ),
    ).toBe("Private");
  });

  it("falls back when model descriptions are broken placeholder text", () => {
    expect(
      safeModelDescription(
        { ...textModel, isPublic: false, canEdit: true, description: "??????" },
        "选择模型并输入需求开始调试。",
      ),
    ).toBe("选择模型并输入需求开始调试。");
  });

  it("replaces legacy generic custom model descriptions with product copy", () => {
    expect(
      safeModelDescription(
        { ...textModel, isPublic: false, canEdit: true, description: "用户自定义模型" },
        "选择模型后即可套用模板、上传素材并开始创作。",
      ),
    ).toBe("专属创作模型");
  });

  it("picks only editable server models when publishing selected models", () => {
    const privateServer = { ...textModel, id: "private-server", serverManaged: true, isPublic: false, canEdit: true };
    const publicServer = { ...textModel, id: "public-server", serverManaged: true, isPublic: true, canEdit: true };
    const readonlyServer = { ...textModel, id: "readonly-server", serverManaged: true, isPublic: false, canEdit: false };
    const localModel = { ...textModel, id: "local-model", serverManaged: false, isPublic: false };

    expect(
      publicShareTargetModels(
        [privateServer, publicServer, readonlyServer, localModel],
        ["private-server", "public-server", "readonly-server", "local-model"],
      ).map((model) => model.id),
    ).toEqual(["private-server"]);
  });

  it("filters settings models by capability and search text", () => {
    const models: ModelDefinition[] = [
      {
        ...textModel,
        id: "kk-claude",
        name: "KK Claude",
        vendor: "KK",
        capability: "text",
        model: "claude-sonnet-4-6",
        subModels: [
          {
            id: "sub-claude",
            modelName: "claude-sonnet-4-6",
            displayName: "Claude Sonnet",
            capability: "text",
            adapter: "text-chat",
            isPrimary: true,
            status: "active",
          },
        ],
      },
      {
        ...textModel,
        id: "kk-image",
        name: "KK Grok Image",
        vendor: "KK",
        capability: "image",
        adapter: "image-openai",
        model: "grok-imagine-image-pro",
      },
      {
        ...textModel,
        id: "kk-video",
        name: "KK Seedance",
        vendor: "KK",
        capability: "video",
        adapter: "video-unified-generic",
        model: "kuaikuai-2-flash-pro",
        subModels: [
          {
            id: "sub-seed",
            modelName: "seed-2",
            displayName: "Seed 2",
            capability: "video",
            adapter: "video-unified-generic",
            isPrimary: false,
            status: "active",
          },
          {
            id: "sub-kuaikuai",
            modelName: "kuaikuai-2-flash-pro",
            displayName: "Kuaikuai 2 Flash Pro",
            capability: "video",
            adapter: "video-unified-generic",
            isPrimary: true,
            status: "active",
          },
        ],
      },
    ];

    expect(filterSettingsModels(models, "text", "").map((item) => item.id)).toEqual(["kk-claude"]);
    expect(filterSettingsModels(models, "all", "image").map((item) => item.id)).toEqual(["kk-image"]);
    expect(filterSettingsModels(models, "video", "seed-2").map((item) => item.id)).toEqual(["kk-video"]);
    expect(filterSettingsModels(models, "image", "claude")).toEqual([]);
    expect(filterSettingsModels(models, "all", "").map((item) => item.id)).toEqual(["kk-claude", "kk-image", "kk-video"]);
  });

  it("hides public models from ordinary settings while preserving public card presentation", () => {
    const privateModel = { ...textModel, id: "private-model" };
    const publicModel = {
      ...textModel,
      id: "public-model",
      capability: "video" as const,
      adapter: "video-unified-generic" as const,
      isPublic: true,
      publicDescription: "Fast product films",
    };

    expect(filterSettingsModels([privateModel, publicModel], "all", "", false).map((model) => model.id)).toEqual(["private-model"]);
    expect(filterSettingsModels([privateModel, publicModel], "all", "", true).map((model) => model.id)).toEqual(["private-model", "public-model"]);
    expect(publicModelAccent({ ...publicModel, publicAccentColor: "#c857f1" })).toBe("#C857F1");
    expect(publicModelAccent({ ...publicModel, publicAccentColor: "" })).toBe("#9EE841");
    expect(publicModelCardDescription(publicModel)).toBe("Fast product films");
  });

  it("keeps the active creation capability even when that capability has no models", () => {
    const models: ModelDefinition[] = [
      { ...textModel, id: "public-gpt55", capability: "text", model: "gpt-5.5" },
    ];

    expect(resolveSidebarFilter(models, "image")).toBe("image");
    expect(resolveSidebarFilter(models, "text")).toBe("text");
    expect(resolveSidebarFilter([], "image")).toBe("image");
    expect(resolveSidebarFilter(models, "all")).toBe("all");
  });

  it("marks public server models readonly while keeping personal models editable", () => {
    expect(canEditModel({ ...textModel, serverManaged: true, isPublic: true, canEdit: false })).toBe(false);
    expect(canEditModel({ ...textModel, serverManaged: true, isPublic: false, canEdit: false })).toBe(false);
    expect(canEditModel({ ...textModel, serverManaged: true, isPublic: false, canEdit: true })).toBe(true);
    expect(canEditModel({ ...textModel, serverManaged: false, isPublic: false })).toBe(true);
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

  it("labels exact catalog models and uses their input hint in composers", () => {
    const catalogModel: ModelDefinition = {
      ...textModel,
      id: "hinted-video-model",
      capability: "video",
      adapter: "video-unified-generic",
      primarySubModelId: "sub-video",
      subModels: [
        {
          id: "sub-video",
          modelName: "kuaikuai-2-flash-pro",
          displayName: "Kuaikuai Video",
          capability: "video",
          adapter: "video-unified-generic",
          isPrimary: true,
          status: "active",
          catalog: {
            id: "10028",
            displayName: "Kuaikuai Video",
            modelName: "kuaikuai-2-flash-pro",
            modelType: 3,
            capability: "video",
            icon: "",
            description: "",
            inputHint: "Describe camera movement, subject action, and ending frame.",
            successRate: "",
            source: "kkyi",
            channelGroups: [],
            parameters: [
              {
                id: "duration",
                displayName: "Duration",
                paramKey: "duration",
                description: "",
                widgetType: 3,
                isRequired: true,
                defaultValue: "5",
                functionTag: "",
                maxCount: null,
                sortOrder: 1,
                options: [
                  { id: "duration-5", optionName: "5s", optionValue: "5", description: "", maxCount: null, isDefault: true, sortOrder: 1, priceFactor: "1" },
                ],
              },
            ],
          },
        },
      ],
      builtin: false,
    };

    expect(modelParameterSourceLabel(catalogModel)).toBe("精确参数");
    expect(modelCatalogInputHint(catalogModel, "Fallback prompt")).toBe("Describe camera movement, subject action, and ending frame.");
    expect(modelParameterSourceLabel({ ...catalogModel, subModels: [] })).toBe("通用参数");
    expect(modelCatalogInputHint({ ...catalogModel, subModels: [] }, "Fallback prompt")).toBe("Fallback prompt");
  });

  it("falls back when catalog input hints are broken encoding placeholders", () => {
    const fallback = "描述你想要生成的内容。";
    const catalogModel: ModelDefinition = {
      ...textModel,
      catalog: {
        id: "broken-hint",
        displayName: "Broken Hint",
        modelName: "broken-hint",
        modelType: 1,
        capability: "text",
        icon: "",
        description: "",
        inputHint: "????????????????????????????????????????????????",
        successRate: "",
        source: "kkyi",
        channelGroups: [],
        parameters: [],
      },
    };

    expect(modelCatalogInputHint(catalogModel, fallback)).toBe(fallback);
  });

  it("falls back when catalog input hints are mostly question marks with preserved english words", () => {
    const fallback = "Fallback prompt";
    const catalogModel: ModelDefinition = {
      ...textModel,
      catalog: {
        id: "mixed-broken-hint",
        displayName: "Mixed Broken Hint",
        modelName: "mixed-broken-hint",
        modelType: 1,
        capability: "text",
        icon: "",
        description: "",
        inputHint: "??????????????????????????????????Agent????????????????????????????????????????????????",
        successRate: "",
        source: "kkyi",
        channelGroups: [],
        parameters: [],
      },
    };

    expect(modelCatalogInputHint(catalogModel, fallback)).toBe(fallback);
  });

  it("prefers admin public metadata over catalog display fallbacks", () => {
    const publicModel: ModelDefinition = {
      ...textModel,
      name: "gpt-5.5 ??",
      publicDisplayName: "GPT 5.5 公用大模型",
      inputHint: "输入你的创作目标，我会帮你补全提示词。",
      iconUrl: "https://example.com/custom.svg",
      catalog: {
        id: "public-catalog",
        displayName: "Broken",
        modelName: "gpt-5.5",
        modelType: 1,
        capability: "text",
        icon: "https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons/OpenAI.svg",
        description: "",
        inputHint: "??????????????????????????????????Agent????????????????????????????????????????????????",
        successRate: "",
        source: "kkyi",
        channelGroups: [],
        parameters: [],
      },
    };

    expect(modelDisplayNameForModel(publicModel, setting({}))).toBe("GPT 5.5 公用大模型");
    expect(modelCatalogInputHint(publicModel, "Fallback prompt")).toBe("输入你的创作目标，我会帮你补全提示词。");
    expect(modelCatalogIconUrl(publicModel)).toBe("https://example.com/custom.svg");
  });

  it("uses the selected sub-model catalog icon when available", () => {
    const iconModel: ModelDefinition = {
      ...textModel,
      id: "gemini-model",
      primarySubModelId: "sub-gemini",
      subModels: [
        {
          id: "sub-gemini",
          modelName: "gemini-3.1-pro-preview",
          displayName: "Gemini",
          capability: "text",
          adapter: "text-chat",
          isPrimary: true,
          status: "active",
          catalog: {
            id: "10025",
            displayName: "Gemini",
            modelName: "gemini-3.1-pro-preview",
            modelType: 1,
            capability: "text",
            icon: "https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons/Gemini-color.svg",
            description: "",
            inputHint: "",
            successRate: "",
            source: "kkyi",
            channelGroups: [],
            parameters: [],
          },
        },
      ],
      catalog: {
        id: "10024",
        displayName: "OpenAI",
        modelName: "gpt-5.4",
        modelType: 1,
        capability: "text",
        icon: "https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons/OpenAI.svg",
        description: "",
        inputHint: "",
        successRate: "",
        source: "kkyi",
        channelGroups: [],
        parameters: [],
      },
    };

    expect(modelCatalogIconUrl(iconModel)).toBe("https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons/Gemini-color.svg");
    expect(modelCatalogIconUrl({ ...iconModel, subModels: [] })).toBe("https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons/OpenAI.svg");
    expect(modelCatalogIconUrl(textModel)).toBe("https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons/OpenAI.svg");
  });

  it("uses stable inferred icons instead of expired catalog OSS URLs", () => {
    const staleCatalogModel: ModelDefinition = {
      ...textModel,
      id: "kk-seed-video",
      vendor: "KK",
      capability: "video",
      adapter: "video-unified-generic",
      model: "kuaikuai-2-flash-pro",
      primarySubModelId: "sub-seed",
      subModels: [
        {
          id: "sub-seed",
          modelName: "kuaikuai-2-flash-pro",
          displayName: "Seed2.0-Fast",
          capability: "video",
          adapter: "video-unified-generic",
          isPrimary: true,
          status: "active",
          catalog: {
            id: "10028",
            displayName: "Seed2.0-Fast",
            modelName: "kuaikuai-2-flash-pro",
            modelType: 3,
            capability: "video",
            icon: "https://ai-apply-resource.kkidc.com/uploads/seed.png?x-oss-credential=expired",
            description: "",
            inputHint: "",
            successRate: "",
            source: "kkyi",
            channelGroups: [],
            parameters: [],
          },
        },
      ],
      builtin: false,
    };

    expect(modelCatalogIconUrl(staleCatalogModel)).toBe("https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons/Doubao-color.svg");
  });

  it("uses inferred icons instead of known missing lobe icon names", () => {
    const oldGrokCatalogModel: ModelDefinition = {
      ...textModel,
      id: "kk-grok-image",
      vendor: "KK",
      capability: "image",
      adapter: "image-openai",
      model: "grok-image-2",
      catalog: {
        id: "10036",
        displayName: "Grok Image",
        modelName: "grok-image-2",
        modelType: 2,
        capability: "image",
        icon: "https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons/Grok-color.svg",
        description: "",
        inputHint: "",
        successRate: "",
        source: "kkyi",
        channelGroups: [],
        parameters: [],
      },
      builtin: false,
    };

    expect(modelCatalogIconUrl(oldGrokCatalogModel)).toBe("https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons/XAI.svg");
  });

  it("infers brand icons for uncataloged KK models from model names", () => {
    expect(modelCatalogIconUrl({ ...textModel, id: "kk-gemini", vendor: "KK", model: "gemini-veo-3.1-generate-preview-8s" })).toContain("Gemini-color.svg");
    expect(modelCatalogIconUrl({ ...textModel, id: "kk-claude", vendor: "KK", model: "claude-sonnet-4-6" })).toContain("Claude-color.svg");
    expect(modelCatalogIconUrl({ ...textModel, id: "kk-deepseek", vendor: "KK", model: "deepseek-v3.1" })).toContain("DeepSeek-color.svg");
    expect(modelCatalogIconUrl({ ...textModel, id: "kk-kimi", vendor: "KK", model: "kimi-k2.5" })).toContain("Kimi-color.svg");
    expect(modelCatalogIconUrl({ ...textModel, id: "kk-grok", vendor: "KK", model: "grok-image-2" })).toContain("XAI.svg");
    expect(modelCatalogIconUrl({ ...textModel, id: "kk-seed2", vendor: "KK", model: "Seed2.0-vision-1080" })).toContain("Doubao-color.svg");
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

  it("builds image request parameters without overwriting the selected size with resolution", () => {
    const imageModel: ModelDefinition = {
      ...textModel,
      id: "gpt-image-catalog",
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
                  { id: "size-wide", optionName: "横图", optionValue: "1536x1024", description: "", maxCount: null, isDefault: false, sortOrder: 2, priceFactor: "1" },
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
              {
                id: "quantity",
                displayName: "数量",
                paramKey: "quantity",
                description: "",
                widgetType: 3,
                isRequired: false,
                defaultValue: "1",
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

    const body = buildImageGenerationRequestBody(
      imageModel,
      {
        references: [],
        count: "1",
        size: "1536x1024",
        ratio: "16:9",
        resolution: "2k",
        quality: "auto",
      },
      "参考图片生成汽车人",
      {},
    );

    expect(body).toMatchObject({
      prompt: "参考图片生成汽车人",
      response_format: "url",
      size: "1536x1024",
      quality: "auto",
      quantity: 1,
    });
    expect(body).not.toHaveProperty("resolution");
    expect(body.size).not.toBe("2k");
  });

  it("writes explicit 4K size while preserving image request parameters", () => {
    const imageModel: ModelDefinition = {
      ...textModel,
      id: "gpt-image-4k",
      capability: "image",
      adapter: "image-openai",
      model: "gpt-image-2",
    };

    const body = buildImageGenerationRequestBody(
      imageModel,
      {
        references: ["/api/assets/uploads/person.jpg"],
        count: "2",
        size: "1024x1024",
        ratio: "16:9",
        resolution: "2k",
        quality: "hd",
        enable4k: true,
      },
      "restore the same person",
      { background: "transparent" },
    );

    expect(body).toMatchObject({
      prompt: "restore the same person",
      response_format: "url",
      image: ["/api/assets/uploads/person.jpg"],
      n: 2,
      size: "3840x2160",
      quality: "hd",
      background: "transparent",
    });
  });

  it("keeps 4K size authoritative over advanced JSON size overrides", () => {
    const imageModel: ModelDefinition = {
      ...textModel,
      id: "gpt-image-4k-extra",
      capability: "image",
      adapter: "image-openai",
      model: "gpt-image-2",
    };

    const body = buildImageGenerationRequestBody(
      imageModel,
      {
        references: [],
        count: "1",
        size: "1024x1024",
        ratio: "9:16",
        resolution: "2k",
        quality: "auto",
        enable4k: true,
      },
      "vertical poster",
      { size: "1024x1024", seed: 42 },
    );

    expect(body.size).toBe("2160x3840");
    expect(body.seed).toBe(42);
  });

  it("sends image-openai reference uploads on the edit image field even when catalog calls it images", () => {
    const imageModel: ModelDefinition = {
      ...textModel,
      id: "gpt-image-catalog-reference",
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
                id: "reference",
                displayName: "Reference",
                paramKey: "images",
                description: "",
                widgetType: 6,
                isRequired: false,
                defaultValue: "",
                functionTag: "",
                maxCount: 4,
                sortOrder: 1,
                options: [],
              },
            ],
          },
        },
      ],
      builtin: false,
    };

    const body = buildImageGenerationRequestBody(
      imageModel,
      {
        references: ["/api/assets/uploads/person.jpg"],
        count: "1",
        size: "auto",
        ratio: "1:1",
        resolution: "2k",
        quality: "auto",
      },
      "restore the same person",
      {},
    );

    expect(body).toMatchObject({
      prompt: "restore the same person",
      image: ["/api/assets/uploads/person.jpg"],
    });
    expect(body).not.toHaveProperty("images");
  });

  it("keeps catalog video modes distinct and reads upload limits from the selected option", () => {
    const videoModel: ModelDefinition = {
      ...textModel,
      id: "seedance-catalog",
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
                id: "mode",
                displayName: "生成模式",
                paramKey: "video_mode",
                description: "",
                widgetType: 3,
                isRequired: true,
                defaultValue: "reference",
                functionTag: "",
                maxCount: null,
                sortOrder: 1,
                options: [
                  { id: "mode-text", optionName: "文生视频", optionValue: "text", description: "", maxCount: 0, isDefault: false, sortOrder: 1, priceFactor: "1" },
                  { id: "mode-reference", optionName: "参考图生成视频", optionValue: "reference", description: "", maxCount: 5, isDefault: true, sortOrder: 2, priceFactor: "1" },
                  { id: "mode-first", optionName: "首帧生成视频", optionValue: "first_frame", description: "", maxCount: 1, isDefault: false, sortOrder: 3, priceFactor: "1" },
                  { id: "mode-first-last", optionName: "首尾帧生成视频", optionValue: "first_last_frame", description: "", maxCount: 2, isDefault: false, sortOrder: 4, priceFactor: "1" },
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
                options: [],
              },
            ],
          },
        },
      ],
      builtin: false,
    };

    expect(catalogVideoModeValue("reference")).toBe("reference");
    expect(catalogVideoModeValue("first_frame")).toBe("first-frame");
    expect(catalogVideoModeValue("first_last_frame")).toBe("start-end");
    expect(videoModeParamValue("first-frame")).toBe("first_frame");
    expect(videoModeParamValue("start-end")).toBe("first_last_frame");
    expect(catalogOptionMaxCount(videoModel, "video_mode", "reference", 1)).toBe(5);
    expect(videoModeUploadLimit(videoModel, "reference")).toBe(5);
    expect(videoModeRequiredUploadCount("reference")).toBe(1);
    expect(videoModeUploadLimit(videoModel, "first-frame")).toBe(1);
    expect(videoModeRequiredUploadCount("first-frame")).toBe(1);
    expect(videoModeUploadLimit(videoModel, "start-end")).toBe(2);
    expect(videoModeRequiredUploadCount("start-end")).toBe(2);
  });

  it("only keeps Seedance 2 image-to-video models eligible for start/end frame modes", () => {
    const modeOptions = [
      { label: "文生视频", value: "text", maxCount: 0 },
      { label: "参考图", value: "reference", maxCount: 5 },
      { label: "首帧", value: "first_frame", maxCount: 1 },
      { label: "首尾帧", value: "first_last_frame", maxCount: 2 },
    ];
    const seedanceModel = (modelName: string): ModelDefinition => ({
      ...textModel,
      id: modelName,
      capability: "video",
      adapter: "video-unified-generic",
      model: modelName,
      primarySubModelId: `sub-${modelName}`,
      subModels: [
        {
          id: `sub-${modelName}`,
          modelName,
          displayName: modelName,
          capability: "video",
          adapter: "video-unified-generic",
          isPrimary: true,
          status: "active",
        },
      ],
      builtin: false,
    });

    expect(filterVideoModeOptionsForModel(seedanceModel("seedance-2.0-fast-image-to-video"), modeOptions).map((item) => item.value)).toEqual([
      "text",
      "reference",
      "first_frame",
      "first_last_frame",
    ]);
    expect(filterVideoModeOptionsForModel(seedanceModel("seedance-2.0-fast-text-to-video"), modeOptions).map((item) => item.value)).toEqual([
      "text",
      "reference",
    ]);
    expect(filterVideoModeOptionsForModel(seedanceModel("seedance-2.0-fast-multimodal-video"), modeOptions).map((item) => item.value)).toEqual([
      "text",
      "reference",
    ]);
  });

  it("places selected video references in catalog-specific request fields", () => {
    const videoModel: ModelDefinition = {
      ...textModel,
      id: "seedance-fields",
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
              { id: "mode", displayName: "生成模式", paramKey: "video_mode", description: "", widgetType: 3, isRequired: true, defaultValue: "reference", functionTag: "", maxCount: null, sortOrder: 1, options: [] },
              { id: "img", displayName: "参考图", paramKey: "img_url", description: "", widgetType: 6, isRequired: false, defaultValue: "", functionTag: "", maxCount: 5, sortOrder: 2, options: [] },
              { id: "first", displayName: "首帧", paramKey: "first_frame", description: "", widgetType: 6, isRequired: false, defaultValue: "", functionTag: "", maxCount: 1, sortOrder: 3, options: [] },
              { id: "last", displayName: "尾帧", paramKey: "last_frame", description: "", widgetType: 6, isRequired: false, defaultValue: "", functionTag: "", maxCount: 1, sortOrder: 4, options: [] },
            ],
          },
        },
      ],
      builtin: false,
    };

    expect(buildVideoMediaFields(videoModel, "reference", ["/a.png", "/b.png"])).toEqual({
      img_url: ["/a.png", "/b.png"],
    });
    expect(buildVideoMediaFields(videoModel, "first-frame", ["/first.png"])).toEqual({
      first_frame: "/first.png",
    });
    expect(buildVideoMediaFields(videoModel, "start-end", ["/first.png", "/last.png"])).toEqual({
      first_frame: "/first.png",
      last_frame: "/last.png",
    });
  });

  it("keeps uncataloged generic video references on the stable images field", () => {
    const genericVideoModel: ModelDefinition = {
      ...textModel,
      id: "generic-video",
      capability: "video",
      adapter: "video-unified-generic",
      model: "custom-video-model",
    };

    expect(buildVideoMediaFields(genericVideoModel, "reference", ["/a.png", "/b.png"])).toEqual({
      images: ["/a.png", "/b.png"],
    });
    expect(buildVideoMediaFields(genericVideoModel, "start-end", ["/first.png", "/last.png"])).toEqual({
      images: ["/first.png", "/last.png"],
    });
  });

  it("keeps Veo fallback duration options capped at 8 seconds", () => {
    expect(videoDurationFallbackOptions("video-unified-veo")).toEqual(["4", "5", "8"]);
    expect(videoDurationFallbackOptions("video-unified-generic")).toContain("15");
  });

  it("filters catalog Veo duration choices above 8 seconds", () => {
    const veoModel: ModelDefinition = {
      ...textModel,
      id: "veo-catalog",
      capability: "video",
      adapter: "video-unified-veo",
      primarySubModelId: "sub-veo",
      subModels: [
        {
          id: "sub-veo",
          modelName: "veo3.1-fast-components",
          displayName: "Veo",
          capability: "video",
          adapter: "video-unified-veo",
          isPrimary: true,
          status: "active",
          catalog: {
            id: "10088",
            displayName: "Veo",
            modelName: "veo3.1-fast-components",
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
                id: "duration",
                displayName: "视频时长",
                paramKey: "duration",
                description: "",
                widgetType: 3,
                isRequired: true,
                defaultValue: "8",
                functionTag: "",
                maxCount: null,
                sortOrder: 1,
                options: [
                  { id: "duration-4", optionName: "4秒", optionValue: "4", description: "", maxCount: null, isDefault: false, sortOrder: 1, priceFactor: "1" },
                  { id: "duration-8", optionName: "8秒", optionValue: "8", description: "", maxCount: null, isDefault: true, sortOrder: 2, priceFactor: "1" },
                  { id: "duration-10", optionName: "10秒", optionValue: "10", description: "", maxCount: null, isDefault: false, sortOrder: 3, priceFactor: "1" },
                ],
              },
            ],
          },
        },
      ],
      builtin: false,
    };

    expect(videoDurationOptionItems(veoModel).map((item) => item.value)).toEqual(["4", "8"]);
  });

  it("filters generic KK Veo model duration choices above 8 seconds by model name", () => {
    const kkVeoModel: ModelDefinition = {
      ...textModel,
      id: "kk-veo",
      capability: "video",
      adapter: "video-unified-generic",
      model: "gemini-veo-3.1-generate-preview-8s",
    };

    expect(videoDurationOptionItems(kkVeoModel).map((item) => item.value)).toEqual(["4", "5", "8"]);
  });

  it("does not send p-based video resolution values through the size field", () => {
    const sizeOnlyVideoModel: ModelDefinition = {
      ...textModel,
      id: "size-only-video",
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
                id: "size",
                displayName: "清晰度",
                paramKey: "size",
                description: "",
                widgetType: 3,
                isRequired: true,
                defaultValue: "720p",
                functionTag: "",
                maxCount: null,
                sortOrder: 1,
                options: [
                  { id: "size-480", optionName: "480p", optionValue: "480p", description: "", maxCount: null, isDefault: false, sortOrder: 1, priceFactor: "1" },
                  { id: "size-720", optionName: "720p", optionValue: "720p", description: "", maxCount: null, isDefault: true, sortOrder: 2, priceFactor: "1" },
                ],
              },
            ],
          },
        },
      ],
      builtin: false,
    };

    expect(videoResolutionRequestKey(sizeOnlyVideoModel, "480p")).toBe("resolution");
    expect(videoResolutionRequestKey(sizeOnlyVideoModel, "1280x720")).toBe("size");
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

  it("resets the visible conversation when switching to a different model context", () => {
    expect(shouldResetConversationForModelSwitch({ capability: "image" }, { capability: "video" })).toBe(true);
    expect(shouldResetConversationForModelSwitch({ capability: "video", subModelId: "sub-veo" }, { capability: "video", subModelId: "sub-happyhorse" })).toBe(true);
    expect(shouldResetConversationForModelSwitch({ capability: "video", modelGroupId: "mdl-veo" }, { capability: "video", modelGroupId: "mdl-happyhorse" })).toBe(true);
    expect(shouldResetConversationForModelSwitch({ capability: "image", subModelId: "sub-image" }, { capability: "image", subModelId: "sub-image" })).toBe(false);
    expect(shouldResetConversationForModelSwitch(null, { capability: "text" })).toBe(false);
  });

  it("finds the newest conversation for the selected model context", () => {
    const conversations = [
      conversation({
        id: "old-image",
        capability: "image",
        modelGroupId: "mdl-image",
        subModelId: "sub-image",
        updatedAt: "2026-06-01T10:00:00Z",
      }),
      conversation({
        id: "new-image",
        capability: "image",
        modelGroupId: "mdl-image",
        subModelId: "sub-image",
        updatedAt: "2026-06-02T10:00:00Z",
      }),
      conversation({
        id: "other-submodel",
        capability: "image",
        modelGroupId: "mdl-image",
        subModelId: "sub-other",
        updatedAt: "2026-06-03T10:00:00Z",
      }),
      conversation({
        id: "video",
        capability: "video",
        modelGroupId: "mdl-image",
        subModelId: "sub-image",
        updatedAt: "2026-06-04T10:00:00Z",
      }),
    ];

    expect(
      latestConversationForModel(conversations, {
        capability: "image",
        modelGroupId: "mdl-image",
        subModelId: "sub-image",
      })?.id,
    ).toBe("new-image");
    expect(
      latestConversationForModel(conversations, {
        capability: "image",
        modelGroupId: "mdl-image",
        subModelId: "",
      })?.id,
    ).toBe("other-submodel");
  });

  it("hides the current conversation when it belongs to another active creation type", () => {
    const textConversation = conversation({
      id: "cnv_text",
      capability: "text",
      messages: [message({ id: "m1", role: "user", capability: "text", content: "文案消息" })],
    });

    expect(visibleConversationMessages(textConversation, "text").map((item) => item.content)).toEqual(["文案消息"]);
    expect(visibleConversationMessages(textConversation, "video")).toEqual([]);
    expect(visibleConversationMessages(textConversation, null)).toEqual([]);
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
    const imageSummaryWith4k = imageGenerationSummary({ ratio: "16:9", resolution: "2k", count: "1", enable4k: true });
    const videoSummary = videoGenerationSummary({
      mode: "reference",
      aspectRatio: "9:16",
      resolution: "720p",
      duration: "5",
      count: "1",
    });

    expect(imageSummaryWith4k).toContain("4K");

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

  it("falls back from broken model display names to the primary model name", () => {
    expect(
      modelDisplayNameForModel(
        { ...textModel, name: "????????????????Agent????????????????" },
        setting({ modelNameOverride: "gemini-3.1-pro-preview" }),
      ),
    ).toBe("gemini-3.1-pro-preview \u6587\u6848");
  });

  it("removes broken question mark suffixes from otherwise readable model names", () => {
    expect(
      modelDisplayNameForModel(
        { ...textModel, name: "gpt-5.5 ??" },
        setting({ modelNameOverride: "gpt-5.5" }),
      ),
    ).toBe("gpt-5.5");
    expect(
      modelDisplayNameForModel(
        { ...textModel, capability: "image", name: "gpt-image-2 ??" },
        setting({ modelNameOverride: "gpt-image-2" }),
      ),
    ).toBe("gpt-image-2");
  });

  it("falls back from short broken database names to readable catalog names", () => {
    expect(
      modelDisplayNameForModel(
        {
          ...textModel,
          name: "??????",
          publicDisplayName: "???",
          catalog: {
            id: "10030",
            displayName: "GPT-5.5",
            modelName: "gpt-5.5",
            modelType: 1,
            capability: "text",
            icon: "",
            description: "",
            inputHint: "",
            successRate: "",
            source: "kkyi",
            channelGroups: [],
            parameters: [],
          },
        },
        setting({ modelNameOverride: "gpt-5.5" }),
      ),
    ).toBe("GPT-5.5");
  });

  it("uses readable fallback titles for broken conversation history names", () => {
    expect(conversationDisplayTitle({ title: "????????????????????", capability: "image" })).toBe("图片创作历史");
    expect(conversationDisplayTitle({ title: "hello ???", capability: "text" })).toBe("hello");
    expect(conversationDisplayTitle({ title: "?? SU7", capability: "video" })).toBe("SU7");
    expect(conversationDisplayTitle({ title: "4 ?", capability: "image" })).toBe("图片创作历史");
    expect(conversationDisplayTitle({ title: "真实标题", capability: "video" })).toBe("真实标题");
    expect(conversationDisplayTitle({ title: "", capability: "video" })).toBe("视频创作历史");
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

  it("updates an existing task message with generated media instead of appending a duplicate", () => {
    const pending = appendLocalConversationMessages(null, {
      capability: "video",
      titleSeed: "生成视频",
      modelGroupId: "video-model",
      subModelId: "sub-video",
      now: "2026-06-06T01:05:00.000Z",
      messages: [
        { role: "user", content: "生成视频" },
        { role: "assistant", content: "task-1", status: "processing" },
      ],
    });

    const completed = updateLocalConversationTaskMessage(pending, "task-1", {
      content: "completed",
      status: "success",
      assets: [
        {
          id: "asset-video",
          capability: "video",
          assetType: "video",
          url: "https://cdn.example.com/video.mp4",
          thumbnailUrl: "",
          metadata: { taskId: "task-1" },
          createdAt: "2026-06-06T01:06:00.000Z",
        },
      ],
    });

    expect(completed?.messages).toHaveLength(2);
    expect(completed?.messages[1]).toMatchObject({
      role: "assistant",
      content: "completed",
      status: "success",
      assets: [expect.objectContaining({ url: "https://cdn.example.com/video.mp4" })],
    });
  });

  it("maps video task statuses to local message statuses", () => {
    expect(videoMessageStatusFromTaskStatus("completed")).toBe("success");
    expect(videoMessageStatusFromTaskStatus("task_succeeded")).toBe("success");
    expect(videoMessageStatusFromTaskStatus("failed")).toBe("error");
    expect(videoMessageStatusFromTaskStatus("cancelled")).toBe("error");
    expect(videoMessageStatusFromTaskStatus("processing")).toBe("processing");
    expect(videoMessageStatusFromTaskStatus("queued")).toBe("processing");
  });

  it("keeps polling only while media tasks are still running", () => {
    expect(shouldContinuePollingTask("processing")).toBe(true);
    expect(shouldContinuePollingTask("queued")).toBe(true);
    expect(shouldContinuePollingTask("completed")).toBe(false);
    expect(shouldContinuePollingTask("failed")).toBe(false);
  });

  it("creates a playable video asset from query results", () => {
    expect(
      conversationAssetFromVideoQueryResult({
        taskId: "task-veo",
        status: "completed",
        progress: "100%",
        videoUrl: "https://cdn.example.com/veo.mp4",
        thumbnailUrl: "https://cdn.example.com/veo.jpg",
      }),
    ).toEqual({
      assetType: "video",
      url: "https://cdn.example.com/veo.mp4",
      thumbnailUrl: "https://cdn.example.com/veo.jpg",
      metadata: {
        taskId: "task-veo",
        status: "completed",
        progress: "100%",
      },
    });
    expect(conversationAssetFromVideoQueryResult({ taskId: "task-veo", status: "processing", videoUrl: null })).toBeNull();
  });

  it("creates image assets from async image query results", () => {
    expect(
      conversationAssetsFromImageQueryResult({
        taskId: "image-task-1",
        status: "completed",
        progress: "100%",
        images: [
          { src: "https://cdn.example.com/one.png", revisedPrompt: "one revised" },
          { src: "https://cdn.example.com/two.png" },
        ],
      }),
    ).toEqual([
      {
        assetType: "image",
        url: "https://cdn.example.com/one.png",
        thumbnailUrl: "",
        metadata: {
          taskId: "image-task-1",
          status: "completed",
          progress: "100%",
          revisedPrompt: "one revised",
        },
      },
      {
        assetType: "image",
        url: "https://cdn.example.com/two.png",
        thumbnailUrl: "",
        metadata: {
          taskId: "image-task-1",
          status: "completed",
          progress: "100%",
          revisedPrompt: "",
        },
      },
    ]);
  });

  it("merges every backend assistant asset with image query results for four-image batches", () => {
    const merged = mergeImageQueryAssets({
      taskId: "local-image-task-four",
      status: "completed",
      progress: "4/4",
      images: [
        { src: "https://cdn.example.com/one.png" },
        { src: "https://cdn.example.com/two.png" },
        { src: "https://cdn.example.com/three.png" },
        { src: "https://cdn.example.com/four.png" },
      ],
      assistantAssets: [
        {
          id: "server-asset-one",
          capability: "image",
          assetType: "image",
          url: "https://cdn.example.com/one.png",
          thumbnailUrl: "",
          metadata: { batchIndex: 1 },
          createdAt: "2026-06-14T01:00:00.000Z",
        },
        {
          id: "server-asset-two",
          capability: "image",
          assetType: "image",
          url: "https://cdn.example.com/two.png",
          thumbnailUrl: "",
          metadata: { batchIndex: 2 },
          createdAt: "2026-06-14T01:00:01.000Z",
        },
        {
          id: "server-asset-three",
          capability: "image",
          assetType: "image",
          url: "https://cdn.example.com/three.png",
          thumbnailUrl: "",
          metadata: { batchIndex: 3 },
          createdAt: "2026-06-14T01:00:02.000Z",
        },
        {
          id: "server-asset-four",
          capability: "image",
          assetType: "image",
          url: "https://cdn.example.com/four.png",
          thumbnailUrl: "",
          metadata: { batchIndex: 4 },
          createdAt: "2026-06-14T01:00:03.000Z",
        },
      ],
      now: "2026-06-14T01:00:04.000Z",
    });

    expect(merged).toHaveLength(4);
    expect(merged.map((asset) => asset.url)).toEqual([
      "https://cdn.example.com/one.png",
      "https://cdn.example.com/two.png",
      "https://cdn.example.com/three.png",
      "https://cdn.example.com/four.png",
    ]);
    expect(merged[3]).toMatchObject({
      id: "server-asset-four",
      metadata: { batchIndex: 4 },
    });
  });

  it("keeps image query assets scoped to the current task id", () => {
    const merged = mergeImageQueryAssets({
      taskId: "local-image-task-second",
      status: "completed",
      progress: "2/2",
      images: [],
      assistantAssets: [
        {
          id: "server-asset-first-one",
          capability: "image",
          assetType: "image",
          url: "https://cdn.example.com/first-one.png",
          thumbnailUrl: "",
          metadata: { taskId: "local-image-task-first", batchIndex: 1 },
          createdAt: "2026-06-14T01:00:00.000Z",
        },
        {
          id: "server-asset-second-one",
          capability: "image",
          assetType: "image",
          url: "https://cdn.example.com/second-one.png",
          thumbnailUrl: "",
          metadata: { taskId: "local-image-task-second", batchIndex: 1 },
          createdAt: "2026-06-14T01:02:00.000Z",
        },
        {
          id: "server-asset-second-two",
          capability: "image",
          assetType: "image",
          url: "https://cdn.example.com/second-two.png",
          thumbnailUrl: "",
          metadata: { taskId: "local-image-task-second", batchIndex: 2 },
          createdAt: "2026-06-14T01:02:01.000Z",
        },
      ],
      now: "2026-06-14T01:02:02.000Z",
    });

    expect(merged.map((asset) => asset.url)).toEqual([
      "https://cdn.example.com/second-one.png",
      "https://cdn.example.com/second-two.png",
    ]);
  });

  it("updates image task messages by metadata when content no longer equals the task id", () => {
    const pending = appendLocalConversationMessages(null, {
      capability: "image",
      titleSeed: "batch images",
      modelGroupId: "image-model",
      subModelId: "sub-image",
      now: "2026-06-14T01:05:00.000Z",
      messages: [
        { role: "user", content: "batch images" },
        {
          role: "assistant",
          content: "completed",
          status: "processing",
          assets: [
            {
              assetType: "image",
              url: "https://cdn.example.com/one.png",
              metadata: { taskId: "local-image-task-four" },
            },
          ],
        },
      ],
    });

    const completed = updateLocalConversationTaskMessage(pending, "local-image-task-four", {
      content: "completed",
      status: "success",
      assets: [
        {
          id: "asset-four",
          capability: "image",
          assetType: "image",
          url: "https://cdn.example.com/four.png",
          thumbnailUrl: "",
          metadata: { taskId: "local-image-task-four" },
          createdAt: "2026-06-14T01:06:00.000Z",
        },
      ],
    });

    expect(completed?.messages).toHaveLength(2);
    expect(completed?.messages[1]).toMatchObject({
      role: "assistant",
      status: "success",
      assets: [expect.objectContaining({ url: "https://cdn.example.com/four.png" })],
    });
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
