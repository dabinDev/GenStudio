import { computed, reactive, watch } from "vue";

import { BUILTIN_MODELS } from "../catalog";
import type {
  Capability,
  HistoryEntry,
  ModelDefinition,
  ModelSettingsRecord,
  ServerModelDefinition,
} from "../types";
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
  serverModels: [] as ModelDefinition[],
  serverSynced: false,
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
    if (state.serverSynced) {
      return state.serverModels;
    }
    const removedIds = new Set(state.removedModelIds);
    return [...BUILTIN_MODELS, ...state.customModels].filter((model) => !removedIds.has(model.id));
  });

  function primaryServerModelName(model: ModelDefinition): string {
    return (model.model || model.subModels?.find((item) => item.id === model.primarySubModelId)?.modelName || "").trim().toLowerCase();
  }

  function preferServerModel(candidate: ModelDefinition, current: ModelDefinition): ModelDefinition {
    if (candidate.isPublic !== current.isPublic) {
      return candidate.isPublic ? candidate : current;
    }
    if (candidate.canEdit !== current.canEdit) {
      return candidate.canEdit ? candidate : current;
    }
    return candidate;
  }

  function dedupeServerModels(items: ModelDefinition[]): ModelDefinition[] {
    const indexes = new Map<string, number>();
    const deduped: ModelDefinition[] = [];
    items.forEach((model) => {
      const primaryName = primaryServerModelName(model);
      const key = model.isPublic
        ? `${model.capability}:public:${primaryName || model.id}`
        : `${model.capability}:private:${primaryName || model.id}:${model.id}`;
      const existingIndex = indexes.get(key);
      if (existingIndex === undefined) {
        indexes.set(key, deduped.length);
        deduped.push(model);
        return;
      }
      deduped[existingIndex] = preferServerModel(model, deduped[existingIndex]);
    });
    const publicPrimaryKeys = new Set(
      deduped
        .filter((model) => model.isPublic)
        .map((model) => `${model.capability}:${primaryServerModelName(model)}`),
    );
    if (!publicPrimaryKeys.size) return deduped;
    return deduped.filter((model) => {
      if (model.isPublic) return true;
      if (model.canEdit) return true; // 用户自己创建的私有模型始终显示
      return !publicPrimaryKeys.has(`${model.capability}:${primaryServerModelName(model)}`);
    });
  }

  function applyServerModels(items: ServerModelDefinition[]) {
    state.serverSynced = true;
    state.serverModels = dedupeServerModels(items.map((item) => ({
      id: item.id,
      name: item.name,
      vendor: item.vendor,
      capability: item.capability,
      adapter: item.adapter,
      model: item.primaryModelName || item.subModels[0]?.modelName || item.id,
      description: item.description,
      builtin: false,
      serverManaged: true,
      isPublic: item.isPublic,
      canEdit: item.canEdit,
      primarySubModelId: item.primarySubModelId,
      catalogModelId: item.catalogModelId,
      catalog: item.catalog,
      subModels: item.subModels,
      publicDisplayName: item.publicDisplayName,
      publicDescription: item.publicDescription,
      inputHint: item.inputHint,
      iconUrl: item.iconUrl,
      publicTags: item.publicTags,
      promptOptimizeEnabled: item.promptOptimizeEnabled,
      defaultParameters: item.defaultParameters,
    })));
    items.forEach((item) => {
      state.modelSettings[item.id] = {
        baseUrl: item.canEdit ? item.baseUrl : "",
        apiKey: "",
        modelNameOverride: item.primaryModelName,
        availableModels: item.subModels.map((subModel) => subModel.modelName),
      };
    });
  }

  function clearServerModels() {
    state.serverSynced = false;
    state.serverModels = [];
  }

  function updateModelSetting(
    modelId: string,
    patch: Partial<ModelSettingsRecord[string]>,
  ) {
    state.modelSettings[modelId] = {
      baseUrl: state.modelSettings[modelId]?.baseUrl || "",
      apiKey: state.modelSettings[modelId]?.apiKey || "",
      modelNameOverride: state.modelSettings[modelId]?.modelNameOverride || "",
      availableModels: state.modelSettings[modelId]?.availableModels || [],
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
    applyServerModels,
    clearServerModels,
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
