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
});
