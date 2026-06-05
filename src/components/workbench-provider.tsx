"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import { BUILTIN_MODELS } from "@/lib/catalog";
import { safeJsonParse } from "@/lib/utils";
import type {
  Capability,
  HistoryEntry,
  ModelDefinition,
  ModelSetting,
  ModelSettingsRecord,
} from "@/lib/types";

const SETTINGS_STORAGE_KEY = "creative-pannel:model-settings:v1";
const CUSTOM_MODELS_STORAGE_KEY = "creative-pannel:custom-models:v1";
const HISTORY_STORAGE_KEY = "creative-pannel:history:v1";

interface WorkbenchContextValue {
  hydrated: boolean;
  models: ModelDefinition[];
  modelSettings: ModelSettingsRecord;
  history: HistoryEntry[];
  updateModelSetting: (modelId: string, patch: Partial<ModelSetting>) => void;
  clearModelSetting: (modelId: string) => void;
  addCustomModel: (model: Omit<ModelDefinition, "builtin">) => void;
  updateCustomModel: (
    modelId: string,
    patch: Partial<Omit<ModelDefinition, "id" | "builtin">>,
  ) => void;
  removeCustomModel: (modelId: string) => void;
  addHistory: (entry: HistoryEntry) => void;
  getModelsByCapability: (capability: Capability) => ModelDefinition[];
}

const WorkbenchContext = createContext<WorkbenchContextValue | null>(null);

export function WorkbenchProvider({ children }: PropsWithChildren) {
  const [hydrated] = useState(() => typeof window !== "undefined");
  const [modelSettings, setModelSettings] = useState<ModelSettingsRecord>(() => {
    if (typeof window === "undefined") {
      return {};
    }

    const storedSettings = window.localStorage.getItem(SETTINGS_STORAGE_KEY);
    return safeJsonParse<ModelSettingsRecord>(storedSettings || "", {});
  });
  const [customModels, setCustomModels] = useState<ModelDefinition[]>(() => {
    if (typeof window === "undefined") {
      return [];
    }

    const storedModels = window.localStorage.getItem(CUSTOM_MODELS_STORAGE_KEY);
    return safeJsonParse<ModelDefinition[]>(storedModels || "", []).filter(
      (item) => !item.builtin,
    );
  });
  const [history, setHistory] = useState<HistoryEntry[]>(() => {
    if (typeof window === "undefined") {
      return [];
    }

    const storedHistory = window.localStorage.getItem(HISTORY_STORAGE_KEY);
    return safeJsonParse<HistoryEntry[]>(storedHistory || "", []);
  });

  useEffect(() => {
    if (!hydrated) {
      return;
    }

    window.localStorage.setItem(
      SETTINGS_STORAGE_KEY,
      JSON.stringify(modelSettings),
    );
  }, [hydrated, modelSettings]);

  useEffect(() => {
    if (!hydrated) {
      return;
    }

    window.localStorage.setItem(
      CUSTOM_MODELS_STORAGE_KEY,
      JSON.stringify(customModels),
    );
  }, [customModels, hydrated]);

  useEffect(() => {
    if (!hydrated) {
      return;
    }

    window.localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(history));
  }, [history, hydrated]);

  const models = useMemo(
    () => [...BUILTIN_MODELS, ...customModels],
    [customModels],
  );

  const value = useMemo<WorkbenchContextValue>(
    () => ({
      hydrated,
      models,
      modelSettings,
      history,
      updateModelSetting(modelId, patch) {
        setModelSettings((current) => ({
          ...current,
          [modelId]: {
            baseUrl: current[modelId]?.baseUrl || "",
            apiKey: current[modelId]?.apiKey || "",
            modelNameOverride: current[modelId]?.modelNameOverride || "",
            ...patch,
          },
        }));
      },
      clearModelSetting(modelId) {
        setModelSettings((current) => {
          const next = { ...current };
          delete next[modelId];
          return next;
        });
      },
      addCustomModel(model) {
        setCustomModels((current) => [...current, { ...model, builtin: false }]);
      },
      updateCustomModel(modelId, patch) {
        setCustomModels((current) =>
          current.map((item) =>
            item.id === modelId ? { ...item, ...patch, builtin: false } : item,
          ),
        );
      },
      removeCustomModel(modelId) {
        setCustomModels((current) =>
          current.filter((item) => item.id !== modelId),
        );
        setModelSettings((current) => {
          const next = { ...current };
          delete next[modelId];
          return next;
        });
      },
      addHistory(entry) {
        setHistory((current) => [entry, ...current].slice(0, 24));
      },
      getModelsByCapability(capability) {
        return models.filter((item) => item.capability === capability);
      },
    }),
    [history, hydrated, modelSettings, models],
  );

  return (
    <WorkbenchContext.Provider value={value}>
      {children}
    </WorkbenchContext.Provider>
  );
}

export function useWorkbenchStore(): WorkbenchContextValue {
  const context = useContext(WorkbenchContext);

  if (!context) {
    throw new Error("useWorkbenchStore must be used inside WorkbenchProvider.");
  }

  return context;
}
