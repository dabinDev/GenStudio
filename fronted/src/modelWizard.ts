import type { Capability, ModelSetting } from "./types";
import { getModelIdentifierError, pickPrimaryModel } from "./utils";

export type ModelWizardStep = "connect" | "models" | "review";

export interface ModelWizardDraft {
  name: string;
  capability: Capability;
  model: string;
  baseUrl: string;
  apiKey: string;
  modelNameOverride: string;
  availableModels: string[];
}

export interface ModelWizardProgress {
  step: ModelWizardStep;
  index: number;
  label: string;
  description: string;
  complete: boolean;
}

export const MODEL_WIZARD_STEPS: Array<Omit<ModelWizardProgress, "complete">> = [
  {
    step: "connect",
    index: 1,
    label: "连接密钥",
    description: "填写名称、能力、baseURL 和 API Key。",
  },
  {
    step: "models",
    index: 2,
    label: "获取模型",
    description: "从密钥同步可用模型，并选择主模型。",
  },
  {
    step: "review",
    index: 3,
    label: "保存确认",
    description: "确认保存后，创作时会使用当前主模型。",
  },
];

export function getModelWizardStep(draft: ModelWizardDraft): ModelWizardStep {
  if (!hasConnectionFields(draft)) return "connect";
  if (!draft.availableModels.length) return "models";
  return "review";
}

export function getModelWizardProgress(draft: ModelWizardDraft): ModelWizardProgress[] {
  const connected = hasConnectionFields(draft);
  const hasModels = draft.availableModels.length > 0;
  const hasPrimary = Boolean(resolveDraftPrimaryModel(draft));

  return MODEL_WIZARD_STEPS.map((item) => ({
    ...item,
    complete:
      item.step === "connect"
        ? connected
        : item.step === "models"
          ? connected && hasModels && hasPrimary
          : connected && hasPrimary,
  }));
}

export function resolveDraftPrimaryModel(draft: ModelWizardDraft): string {
  const manual = draft.modelNameOverride.trim() || draft.model.trim();
  return pickPrimaryModel(draft.availableModels, manual);
}

export function applyFetchedModelsToDraft<T extends ModelWizardDraft>(draft: T, models: string[]): T {
  const primary = pickPrimaryModel(models, draft.modelNameOverride || draft.model);
  return {
    ...draft,
    availableModels: models,
    model: primary,
    modelNameOverride: primary,
  };
}

export function canSaveModelDraft(
  draft: ModelWizardDraft,
  setting: Pick<ModelSetting, "baseUrl" | "apiKey">,
  signedIn: boolean,
): boolean {
  const primaryModel = resolveDraftPrimaryModel(draft);
  if (!draft.name.trim() || !primaryModel) return false;
  if (getModelIdentifierError(draft.model) || getModelIdentifierError(draft.modelNameOverride)) return false;
  if (signedIn && (!setting.baseUrl.trim() || !setting.apiKey.trim())) return false;
  return true;
}

function hasConnectionFields(draft: ModelWizardDraft): boolean {
  return Boolean(draft.name.trim() && draft.baseUrl.trim() && draft.apiKey.trim());
}
