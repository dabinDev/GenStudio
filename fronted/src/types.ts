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
  isPublic?: boolean;
  canEdit?: boolean;
  primarySubModelId?: string;
  subModels?: SubModelDefinition[];
  catalogModelId?: string | null;
  catalog?: CatalogModelDefinition | null;
  publicDisplayName?: string;
  publicDescription?: string;
  inputHint?: string;
  iconUrl?: string;
  publicTags?: string[];
  promptOptimizeEnabled?: boolean;
  defaultParameters?: Record<string, unknown>;
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
  isAdmin?: boolean;
}

export interface AdminOverview {
  totalCalls: number;
  successCalls: number;
  failedCalls: number;
  failureRate: number;
  averageDurationMs: number;
  publicModelCalls: number;
  privateModelCalls: number;
}

export interface AdminOverviewUserRow {
  user: AdminUserDefinition;
  totalCalls: number;
  publicModelCalls: number;
  privateModelCalls: number;
  failedCalls: number;
}

export interface AdminOverviewModelRow {
  model: ServerModelDefinition;
  totalCalls: number;
  successCalls: number;
  failedCalls: number;
  averageDurationMs: number;
}

export interface AdminUserDefinition extends UserProfile {
  status: string;
  createdAt: string;
  updatedAt: string;
}

export interface PromptTemplateDefinition {
  id: string;
  capability: Capability;
  modelGroupId: string;
  templateType: string;
  name: string;
  content: string;
  enabled: boolean;
  updatedBy: string;
  createdAt: string;
  updatedAt: string;
}

export interface SubModelDefinition {
  id: string;
  modelName: string;
  displayName: string;
  capability: Capability;
  adapter: Adapter;
  isPrimary: boolean;
  status: string;
  catalogModelId?: string | null;
  catalog?: CatalogModelDefinition | null;
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
  isPublic: boolean;
  canEdit: boolean;
  catalogModelId?: string | null;
  catalog?: CatalogModelDefinition | null;
  subModels: SubModelDefinition[];
  publicDisplayName?: string;
  publicDescription?: string;
  inputHint?: string;
  iconUrl?: string;
  publicTags?: string[];
  promptOptimizeEnabled?: boolean;
  defaultParameters?: Record<string, unknown>;
}

export interface CatalogParameterOptionDefinition {
  id: string;
  optionName: string;
  optionValue: string;
  description: string;
  maxCount: number | null;
  isDefault: boolean;
  sortOrder: number;
  priceFactor: string;
}

export interface CatalogParameterDefinition {
  id: string;
  displayName: string;
  paramKey: string;
  description: string;
  widgetType: number;
  isRequired: boolean;
  defaultValue: string;
  functionTag: string;
  maxCount: number | null;
  sortOrder: number;
  options: CatalogParameterOptionDefinition[];
}

export interface CatalogChannelGroupDefinition {
  id: string;
  channelId: string;
  groupName: string;
  billingType: number;
  inputTokenPrice: string;
  outputTokenPrice: string;
  basePrice: string;
  successRate24h: string;
  avgResponseSeconds24h: string;
  totalSuccessCount: string;
  totalFailCount: string;
  sortOrder: number;
  optionPrices: Record<string, unknown>[];
}

export interface CatalogModelDefinition {
  id: string;
  displayName: string;
  modelName: string;
  modelType: number;
  capability: Capability;
  icon: string;
  description: string;
  inputHint: string;
  successRate: string;
  source: string;
  parameters: CatalogParameterDefinition[];
  channelGroups: CatalogChannelGroupDefinition[];
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

export interface AdminCreationRecord {
  id: string;
  user: AdminUserDefinition | null;
  modelName: string;
  capability: Capability;
  status: string;
  prompt: string;
  response: string;
  createdAt: string;
  durationMs?: number;
  taskId?: string;
  assets?: Array<{ type: string; url: string; thumbnailUrl?: string }>;
  requestParams?: Record<string, unknown>;
  responseSummary?: Record<string, unknown>;
  errorMessage?: string;
}

export interface AdminAuditLog {
  id: string;
  adminUserId: string | null;
  action: string;
  targetType: string;
  targetId: string;
  status: string;
  summary: Record<string, unknown>;
  createdAt: string;
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
