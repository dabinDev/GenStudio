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
  serverManaged?: boolean;
  primarySubModelId?: string;
  subModels?: SubModelDefinition[];
}

export interface ModelSetting {
  baseUrl: string;
  apiKey: string;
  modelNameOverride: string;
  availableModels: string[];
}

export interface UserProfile {
  id: string;
  externalUserId: string;
  email: string;
  phone: string;
  nickname: string;
  avatarUrl: string;
}

export interface SubModelDefinition {
  id: string;
  modelName: string;
  displayName: string;
  capability: Capability;
  adapter: Adapter;
  isPrimary: boolean;
  status: string;
}

export interface ServerModelDefinition {
  id: string;
  name: string;
  vendor: string;
  capability: Capability;
  adapter: Adapter;
  description: string;
  apiKeyId: string;
  baseUrl: string;
  primarySubModelId: string;
  primaryModelName: string;
  subModels: SubModelDefinition[];
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

export interface ConversationAsset {
  id: string;
  capability: Capability;
  assetType: "image" | "video" | string;
  url: string;
  thumbnailUrl: string;
  metadata: Record<string, unknown>;
  createdAt: string;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant" | string;
  capability: Capability;
  content: string;
  status: "success" | "error" | "processing" | string;
  errorMessage: string;
  canRetry: boolean;
  modelGroupId: string | null;
  subModelId: string | null;
  assets: ConversationAsset[];
  createdAt: string;
}

export interface ConversationDefinition {
  id: string;
  title: string;
  capability: Capability;
  modelGroupId: string | null;
  subModelId: string | null;
  status: string;
  createdAt: string;
  updatedAt: string;
  messages: ConversationMessage[];
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
