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
