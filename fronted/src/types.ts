export type Capability = "text" | "image" | "video";

export type Adapter =
  | "text-chat"
  | "image-openai"
  | "video-unified-jimeng"
  | "video-unified-vidu"
  | "video-unified-veo"
  | "video-unified-generic"
  | "video-seedance";

export interface ModelDefinition {
  id: string;
  name: string;
  vendor: string;
  capability: Capability;
  adapter: Adapter;
  model: string;
  description: string;
  builtin: boolean;
}

export interface ModelSetting {
  baseUrl: string;
  apiKey: string;
  modelNameOverride: string;
}

export type ModelSettingsRecord = Record<string, ModelSetting>;

export interface PromptTemplate {
  id: string;
  label: string;
  prompt: string;
}

export interface UploadedAsset {
  id: string;
  fileName: string;
  publicUrl: string;
  contentType: string;
  localPreviewUrl: string;
}

export interface HistoryEntry {
  id: string;
  capability: Capability;
  modelId: string;
  modelName: string;
  title: string;
  status: "success" | "error" | "processing";
  createdAt: number;
  summary: string;
}
