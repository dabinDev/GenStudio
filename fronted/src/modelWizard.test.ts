import { describe, expect, it } from "vitest";

import type { Capability, ModelSetting } from "./types";
import {
  applyFetchedModelsToDraft,
  canFetchModelListForDraft,
  canSaveModelDraft,
  canTestModelDraft,
  getModelDraftMissingFieldLabels,
  getModelWizardProgress,
  getModelWizardStep,
  resolveDraftPrimaryModel,
  type ModelWizardDraft,
} from "./modelWizard";

function draft(patch: Partial<ModelWizardDraft> = {}): ModelWizardDraft {
  return {
    name: "",
    capability: "text" as Capability,
    model: "",
    baseUrl: "",
    apiKey: "",
    modelNameOverride: "",
    availableModels: [],
    ...patch,
  };
}

function setting(patch: Partial<ModelSetting> = {}): ModelSetting {
  return {
    baseUrl: "",
    apiKey: "",
    modelNameOverride: "",
    availableModels: [],
    ...patch,
  };
}

describe("model wizard helpers", () => {
  it("moves through connect, models, and review steps from the draft state", () => {
    expect(getModelWizardStep(draft())).toBe("connect");
    expect(
      getModelWizardStep(
        draft({
          name: "GPT Image",
          baseUrl: "https://token.example.com",
          apiKey: "sk-test",
        }),
      ),
    ).toBe("models");
    expect(
      getModelWizardStep(
        draft({
          name: "GPT Image",
          baseUrl: "https://token.example.com",
          apiKey: "sk-test",
          model: "gpt-image-2",
          modelNameOverride: "gpt-image-2",
          availableModels: ["gpt-image-2", "gpt-5.5"],
        }),
      ),
    ).toBe("review");
  });

  it("marks connection and model-selection progress independently", () => {
    const progress = getModelWizardProgress(
      draft({
        name: "Seedance",
        baseUrl: "https://token.example.com",
        apiKey: "sk-test",
        model: "doubao-seedance-2-0",
        availableModels: ["doubao-seedance-2-0", "gpt-image-2"],
      }),
    );

    expect(progress.map((item) => [item.step, item.complete])).toEqual([
      ["connect", true],
      ["models", true],
      ["review", true],
    ]);
  });

  it("keeps the current primary model when fetched models include it", () => {
    const next = applyFetchedModelsToDraft(
      draft({
        model: "gpt-image-2",
        modelNameOverride: "gpt-image-2",
      }),
      ["gpt-5.5", "gpt-image-2"],
    );

    expect(next.model).toBe("gpt-image-2");
    expect(next.modelNameOverride).toBe("gpt-image-2");
    expect(next.availableModels).toEqual(["gpt-5.5", "gpt-image-2"]);
  });

  it("falls back to the first fetched model when the current primary is missing", () => {
    const next = applyFetchedModelsToDraft(
      draft({
        model: "missing-model",
        modelNameOverride: "missing-model",
      }),
      ["gpt-5.5", "gpt-image-2"],
    );

    expect(resolveDraftPrimaryModel(next)).toBe("gpt-5.5");
  });

  it("requires server-saved models to include connection credentials before save", () => {
    const readyDraft = draft({
      name: "GPT Image",
      baseUrl: "https://token.example.com",
      apiKey: "sk-test",
      model: "gpt-image-2",
      modelNameOverride: "gpt-image-2",
      availableModels: ["gpt-image-2"],
    });

    expect(canSaveModelDraft(readyDraft, setting(), true)).toBe(false);
    expect(
      canSaveModelDraft(
        readyDraft,
        setting({ baseUrl: "https://token.example.com", apiKey: "sk-test" }),
        true,
      ),
    ).toBe(true);
  });

  it("rejects URL-shaped model identifiers before saving", () => {
    expect(
      canSaveModelDraft(
        draft({
          name: "Bad Model",
          baseUrl: "https://token.example.com",
          apiKey: "sk-test",
          model: "https://token.example.com",
          modelNameOverride: "https://token.example.com",
        }),
        setting({ baseUrl: "https://token.example.com", apiKey: "sk-test" }),
        true,
      ),
    ).toBe(false);
  });

  it("summarizes missing required fields for a new server-saved model", () => {
    expect(getModelDraftMissingFieldLabels(draft(), setting(), true)).toEqual([
      "名称",
      "baseURL",
      "API Key",
      "主模型",
    ]);
  });

  it("requires credentials before fetching models", () => {
    expect(canFetchModelListForDraft(draft({ baseUrl: "https://token.example.com" }))).toBe(false);
    expect(canFetchModelListForDraft(draft({ apiKey: "sk-test" }))).toBe(false);
    expect(
      canFetchModelListForDraft(
        draft({
          baseUrl: "https://token.example.com",
          apiKey: "sk-test",
        }),
      ),
    ).toBe(true);
  });

  it("requires fetched models and a selected primary model before testing", () => {
    expect(
      canTestModelDraft(
        draft({
          baseUrl: "https://token.example.com",
          apiKey: "sk-test",
        }),
      ),
    ).toBe(false);
    expect(
      canTestModelDraft(
        draft({
          baseUrl: "https://token.example.com",
          apiKey: "sk-test",
          model: "gpt-5.5",
        }),
      ),
    ).toBe(false);
    expect(
      canTestModelDraft(
        draft({
          baseUrl: "https://token.example.com",
          apiKey: "sk-test",
          model: "gpt-5.5",
          modelNameOverride: "gpt-5.5",
          availableModels: ["gpt-5.5", "gpt-image-2"],
        }),
      ),
    ).toBe(true);
  });
});
