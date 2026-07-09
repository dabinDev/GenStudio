import { beforeEach, describe, expect, it, vi } from "vitest";

import { BUILTIN_MODELS } from "../catalog";

function installLocalStorageMock() {
  const values = new Map<string, string>();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      clear: () => values.clear(),
      getItem: (key: string) => values.get(key) ?? null,
      removeItem: (key: string) => values.delete(key),
      setItem: (key: string, value: string) => values.set(key, value),
    },
  });
}

describe("useWorkbenchStore", () => {
  beforeEach(() => {
    vi.resetModules();
    installLocalStorageMock();
    localStorage.clear();
  });

  it("removes builtin and custom models from the visible model list", async () => {
    const { useWorkbenchStore } = await import("./workbench");
    const store = useWorkbenchStore();
    const builtinId = BUILTIN_MODELS[0].id;
    const customId = "custom-test-video";

    store.addCustomModel({
      id: customId,
      name: "测试视频模型",
      vendor: "测试",
      capability: "video",
      adapter: "video-unified-generic",
      model: "test-video-model",
      description: "用于验证删除同步",
    });
    store.updateModelSetting(builtinId, {
      baseUrl: "https://example.com",
      apiKey: "test-key",
    });

    store.removeModel(builtinId);
    store.removeModel(customId);

    expect(store.models.value.some((model) => model.id === builtinId)).toBe(false);
    expect(store.models.value.some((model) => model.id === customId)).toBe(false);
    expect(store.state.modelSettings[builtinId]).toBeUndefined();
    expect(store.state.modelSettings[customId]).toBeUndefined();
  });

  it("preserves fetched model choices when updating a saved model setting", async () => {
    const { useWorkbenchStore } = await import("./workbench");
    const store = useWorkbenchStore();
    const modelId = BUILTIN_MODELS[0].id;

    store.updateModelSetting(modelId, {
      baseUrl: "https://token.example.com",
      apiKey: "test-key",
      modelNameOverride: "gpt-4.1",
      availableModels: ["gpt-4o", "gpt-4.1"],
    });
    store.updateModelSetting(modelId, {
      baseUrl: "https://token.example.com/v2",
    });

    expect(store.state.modelSettings[modelId]).toMatchObject({
      baseUrl: "https://token.example.com/v2",
      apiKey: "test-key",
      modelNameOverride: "gpt-4.1",
      availableModels: ["gpt-4o", "gpt-4.1"],
    });
  });

  it("maps server models to selectable primary sub-model choices", async () => {
    const { useWorkbenchStore } = await import("./workbench");
    const store = useWorkbenchStore();

    store.applyServerModels([
      {
        id: "mdl-server",
        name: "GPT Gateway",
        vendor: "OpenAI",
        capability: "text",
        adapter: "text-chat",
        description: "服务端托管模型",
        apiKeyId: "key-server",
        baseUrl: "https://token.example.com",
        primarySubModelId: "sub-gpt-4o",
        primaryModelName: "gpt-4o",
        isPublic: false,
        canEdit: true,
        subModels: [
          {
            id: "sub-gpt-4o",
            modelName: "gpt-4o",
            displayName: "gpt-4o",
            capability: "text",
            adapter: "text-chat",
            isPrimary: true,
            status: "active",
          },
          {
            id: "sub-gpt-4.1",
            modelName: "gpt-4.1",
            displayName: "gpt-4.1",
            capability: "text",
            adapter: "text-chat",
            isPrimary: false,
            status: "active",
          },
        ],
      },
    ]);

    expect(store.models.value).toHaveLength(1);
    expect(store.models.value[0]).toMatchObject({
      id: "mdl-server",
      serverManaged: true,
      model: "gpt-4o",
      primarySubModelId: "sub-gpt-4o",
    });
    expect(store.state.modelSettings["mdl-server"]).toMatchObject({
      baseUrl: "https://token.example.com",
      apiKey: "",
      modelNameOverride: "gpt-4o",
      availableModels: ["gpt-4o", "gpt-4.1"],
    });
  });

  it("keeps user-owned private model alongside same-named public model", async () => {
    // canEdit=true means the current user owns this private model — it must stay visible
    // even when a public model shares the same primary model name
    const { useWorkbenchStore } = await import("./workbench");
    const store = useWorkbenchStore();

    store.applyServerModels([
      {
        id: "mdl-private-gpt55",
        name: "gpt-5.5 文案",
        vendor: "OpenAI",
        capability: "text",
        adapter: "text-chat",
        description: "个人模型",
        apiKeyId: "key-private",
        baseUrl: "https://token.example.com",
        primarySubModelId: "sub-private-gpt55",
        primaryModelName: "gpt-5.5",
        isPublic: false,
        canEdit: true,
        subModels: [
          {
            id: "sub-private-gpt55",
            modelName: "gpt-5.5",
            displayName: "gpt-5.5",
            capability: "text",
            adapter: "text-chat",
            isPrimary: true,
            status: "active",
          },
        ],
      },
      {
        id: "mdl-public-gpt55",
        name: "gpt-5.5 文案",
        vendor: "OpenAI",
        capability: "text",
        adapter: "text-chat",
        description: "公共模型",
        apiKeyId: "key-public",
        baseUrl: "",
        primarySubModelId: "sub-public-gpt55",
        primaryModelName: "gpt-5.5",
        isPublic: true,
        canEdit: false,
        publicDisplayName: "GPT 5.5 公用大模型",
        subModels: [
          {
            id: "sub-public-gpt55",
            modelName: "gpt-5.5",
            displayName: "gpt-5.5",
            capability: "text",
            adapter: "text-chat",
            isPrimary: true,
            status: "active",
          },
        ],
      },
    ]);

    // Both models should be visible: the public one for general use, and the user's
    // own private model because they created it (canEdit=true)
    expect(store.models.value.map((model) => model.id)).toEqual(["mdl-private-gpt55", "mdl-public-gpt55"]);
    const publicModel = store.models.value.find((m) => m.id === "mdl-public-gpt55");
    expect(publicModel).toMatchObject({ isPublic: true, publicDisplayName: "GPT 5.5 公用大模型" });
    const privateModel = store.models.value.find((m) => m.id === "mdl-private-gpt55");
    expect(privateModel).toMatchObject({ isPublic: false, canEdit: true });
  });

  it("deduplicates non-owned private models that share a name with a public model", async () => {
    // canEdit=false, isPublic=false: a private model the current user cannot edit
    // (e.g. another user's read-only model returned via some future shared flow)
    // should still be removed when a public model covers the same name
    const { useWorkbenchStore } = await import("./workbench");
    const store = useWorkbenchStore();

    store.applyServerModels([
      {
        id: "mdl-readonly-gpt55",
        name: "gpt-5.5 文案",
        vendor: "OpenAI",
        capability: "text",
        adapter: "text-chat",
        description: "只读模型",
        apiKeyId: "key-readonly",
        baseUrl: "",
        primarySubModelId: "sub-readonly-gpt55",
        primaryModelName: "gpt-5.5",
        isPublic: false,
        canEdit: false,
        subModels: [
          {
            id: "sub-readonly-gpt55",
            modelName: "gpt-5.5",
            displayName: "gpt-5.5",
            capability: "text",
            adapter: "text-chat",
            isPrimary: true,
            status: "active",
          },
        ],
      },
      {
        id: "mdl-public-gpt55",
        name: "gpt-5.5 文案",
        vendor: "OpenAI",
        capability: "text",
        adapter: "text-chat",
        description: "公共模型",
        apiKeyId: "key-public",
        baseUrl: "",
        primarySubModelId: "sub-public-gpt55",
        primaryModelName: "gpt-5.5",
        isPublic: true,
        canEdit: false,
        publicDisplayName: "GPT 5.5 公用大模型",
        subModels: [
          {
            id: "sub-public-gpt55",
            modelName: "gpt-5.5",
            displayName: "gpt-5.5",
            capability: "text",
            adapter: "text-chat",
            isPrimary: true,
            status: "active",
          },
        ],
      },
    ]);

    expect(store.models.value.map((model) => model.id)).toEqual(["mdl-public-gpt55"]);
    expect(store.models.value[0]).toMatchObject({
      isPublic: true,
      publicDisplayName: "GPT 5.5 公用大模型",
    });
  });

  it("keeps separate private server models even when they use the same primary model name", async () => {
    const { useWorkbenchStore } = await import("./workbench");
    const store = useWorkbenchStore();

    store.applyServerModels([
      {
        id: "mdl-private-a",
        name: "工作区 A",
        vendor: "OpenAI",
        capability: "text",
        adapter: "text-chat",
        description: "个人模型 A",
        apiKeyId: "key-a",
        baseUrl: "https://token-a.example.com",
        primarySubModelId: "sub-private-a",
        primaryModelName: "gpt-5.5",
        isPublic: false,
        canEdit: true,
        subModels: [
          {
            id: "sub-private-a",
            modelName: "gpt-5.5",
            displayName: "gpt-5.5",
            capability: "text",
            adapter: "text-chat",
            isPrimary: true,
            status: "active",
          },
        ],
      },
      {
        id: "mdl-private-b",
        name: "工作区 B",
        vendor: "OpenAI",
        capability: "text",
        adapter: "text-chat",
        description: "个人模型 B",
        apiKeyId: "key-b",
        baseUrl: "https://token-b.example.com",
        primarySubModelId: "sub-private-b",
        primaryModelName: "gpt-5.5",
        isPublic: false,
        canEdit: true,
        subModels: [
          {
            id: "sub-private-b",
            modelName: "gpt-5.5",
            displayName: "gpt-5.5",
            capability: "text",
            adapter: "text-chat",
            isPrimary: true,
            status: "active",
          },
        ],
      },
    ]);

    expect(store.models.value.map((model) => model.id)).toEqual(["mdl-private-a", "mdl-private-b"]);
  });

  it("stays in server-managed mode even when the signed-in user has no models", async () => {
    const { useWorkbenchStore } = await import("./workbench");
    const store = useWorkbenchStore();

    store.addCustomModel({
      id: "local-only-model",
      name: "Local Only",
      vendor: "Local",
      capability: "text",
      adapter: "text-chat",
      model: "local-model",
      description: "Should not appear after server sync",
    });

    store.applyServerModels([]);

    expect(store.models.value).toEqual([]);
  });
});
