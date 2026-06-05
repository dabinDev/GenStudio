import { computed, reactive, watch } from "vue";

import { BUILTIN_MODELS } from "../catalog";
import type { Capability, HistoryEntry, ModelDefinition, ModelSettingsRecord } from "../types";
import { safeJsonParse } from "../utils";

const SETTINGS_STORAGE_KEY = "creative-pannel:model-settings:v1";
const CUSTOM_MODELS_STORAGE_KEY = "creative-pannel:custom-models:v1";
const HISTORY_STORAGE_KEY = "creative-pannel:history:v1";
const REMOVED_MODELS_STORAGE_KEY = "creative-pannel:removed-models:v1";

const state = reactive({
  modelSettings: safeJsonParse<ModelSettingsRecord>(
    localStorage.getItem(SETTINGS_STORAGE_KEY),
    {},
  ),
  customModels: safeJsonParse<ModelDefinition[]>(
    localStorage.getItem(CUSTOM_MODELS_STORAGE_KEY),
    [],
  ).filter((item) => !item.builtin),
  removedModelIds: safeJsonParse<string[]>(
    localStorage.getItem(REMOVED_MODELS_STORAGE_KEY),
    [],
  ),
  history: safeJsonParse<HistoryEntry[]>(localStorage.getItem(HISTORY_STORAGE_KEY), []),
});

watch(
  () => state.modelSettings,
  (value) => localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(value)),
  { deep: true },
);

watch(
  () => state.customModels,
  (value) => localStorage.setItem(CUSTOM_MODELS_STORAGE_KEY, JSON.stringify(value)),
  { deep: true },
);

watch(
  () => state.history,
  (value) => localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(value)),
  { deep: true },
);

watch(
  () => state.removedModelIds,
  (value) => localStorage.setItem(REMOVED_MODELS_STORAGE_KEY, JSON.stringify(value)),
  { deep: true },
);

export function useWorkbenchStore() {
  const models = computed(() => {
    const removedIds = new Set(state.removedModelIds);
    return [...BUILTIN_MODELS, ...state.customModels].filter((model) => !removedIds.has(model.id));
  });

  function updateModelSetting(
    modelId: string,
    patch: Partial<ModelSettingsRecord[string]>,
  ) {
    state.modelSettings[modelId] = {
      baseUrl: state.modelSettings[modelId]?.baseUrl || "",
      apiKey: state.modelSettings[modelId]?.apiKey || "",
      modelNameOverride: state.modelSettings[modelId]?.modelNameOverride || "",
      ...patch,
    };
  }

  function clearModelSetting(modelId: string) {
    delete state.modelSettings[modelId];
  }

  function addCustomModel(model: Omit<ModelDefinition, "builtin">) {
    state.removedModelIds = state.removedModelIds.filter((modelId) => modelId !== model.id);
    state.customModels.push({ ...model, builtin: false });
  }

  function updateCustomModel(
    modelId: string,
    patch: Partial<Omit<ModelDefinition, "id" | "builtin">>,
  ) {
    const index = state.customModels.findIndex((item) => item.id === modelId);
    if (index >= 0) {
      state.customModels[index] = { ...state.customModels[index], ...patch, builtin: false };
    }
  }

  function removeCustomModel(modelId: string) {
    state.customModels = state.customModels.filter((item) => item.id !== modelId);
    clearModelSetting(modelId);
  }

  function removeModel(modelId: string) {
    const customModel = state.customModels.find((item) => item.id === modelId);
    if (customModel) {
      removeCustomModel(modelId);
      return;
    }

    if (!state.removedModelIds.includes(modelId)) {
      state.removedModelIds.push(modelId);
    }
    clearModelSetting(modelId);
  }

  function addHistory(entry: HistoryEntry) {
    state.history = [entry, ...state.history].slice(0, 24);
  }

  function getModelsByCapability(capability: Capability): ModelDefinition[] {
    return models.value.filter((model) => model.capability === capability);
  }

  return {
    state,
    models,
    updateModelSetting,
    clearModelSetting,
    addCustomModel,
    updateCustomModel,
    removeCustomModel,
    removeModel,
    addHistory,
    getModelsByCapability,
  };
}
