"use client";

import { Cpu, KeyRound } from "lucide-react";

import { CAPABILITY_LABELS } from "@/lib/catalog";
import type { ModelDefinition, ModelSetting } from "@/lib/types";

interface ModelSpotlightProps {
  models: ModelDefinition[];
  selectedModelId: string;
  selectedModel: ModelDefinition | null;
  setting?: ModelSetting;
  onChange: (modelId: string) => void;
}

export function ModelSpotlight({
  models,
  selectedModelId,
  selectedModel,
  setting,
  onChange,
}: ModelSpotlightProps) {
  const configured = Boolean(setting?.baseUrl?.trim() && setting?.apiKey?.trim());

  return (
    <div className="model-spotlight">
      <div className="model-spotlight-icon">
        <Cpu aria-hidden="true" size={22} strokeWidth={2} />
      </div>
      <div className="model-spotlight-copy">
        <div className="model-spotlight-title">
          <span>{selectedModel?.name || "未选择模型"}</span>
          {selectedModel ? (
            <span className={`model-tag tag-${selectedModel.capability}`}>
              {CAPABILITY_LABELS[selectedModel.capability]}
            </span>
          ) : null}
          <span className={`badge ${configured ? "badge-success" : "badge-warn"}`}>
            <KeyRound aria-hidden="true" size={13} strokeWidth={2} />
            {configured ? "已配置" : "待配置"}
          </span>
        </div>
        <p className="muted">
          {selectedModel
            ? `${selectedModel.vendor} · ${selectedModel.description}`
            : "请先添加或选择一个模型。"}
        </p>
      </div>
      <label className="model-spotlight-select">
        <span>切换模型</span>
        <select value={selectedModelId} onChange={(event) => onChange(event.target.value)}>
          {models.map((model) => (
            <option key={model.id} value={model.id}>
              {model.name} · {model.vendor}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
