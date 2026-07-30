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
  publicAccentColor?: string;
  inputHint?: string;
  iconUrl?: string;
  publicTags?: string[];
  promptOptimizeEnabled?: boolean;
  defaultParameters?: Record<string, unknown>;
  creditPrice?: number;
  creditPriceSource?: string;
  creditPricingEnabled?: boolean;
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
  credits?: CreditAccount | null;
}

export interface CreditAccount {
  id: string;
  userId: string;
  balance: number;
  reservedBalance: number;
  totalRecharged: number;
  totalSpent: number;
  totalRefunded: number;
  createdAt: string;
  updatedAt: string;
}

export interface CreditTransaction {
  id: string;
  userId: string;
  type: string;
  amount: number;
  balanceAfter: number;
  reservedAfter: number;
  capability: Capability | "";
  modelGroupId: string;
  subModelId: string;
  conversationId: string;
  messageId: string;
  taskId: string;
  relatedTransactionId: string;
  status: string;
  reason: string;
  operatorUserId: string;
  metadata: Record<string, unknown>;
  createdAt: string;
}

export interface CreditPricingEstimate {
  enabled: boolean;
  price: number;
  source: string;
  capability: Capability;
  modelGroupId: string;
  subModelId: string;
}

export interface CreditBundle {
  account: CreditAccount | null;
  transactions: CreditTransaction[];
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
  publicAccentColor?: string;
  inputHint?: string;
  iconUrl?: string;
  publicTags?: string[];
  promptOptimizeEnabled?: boolean;
  defaultParameters?: Record<string, unknown>;
  creditPrice?: number;
  creditPriceSource?: string;
  creditPricingEnabled?: boolean;
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
  category?: string;
  summary?: string;
  example?: string;
}

export interface PromptSceneRecommendation {
  id: string;
  externalId?: string;
  categoryId?: string;
  category?: string;
  subcategory?: string;
  title: string;
  label?: string;
  reason?: string;
  promptText: string;
  promptSummary?: string;
  tags?: string[];
  imageUrl?: string;
  weight?: number;
  enabled?: boolean;
  useCount?: number;
  clickCount?: number;
  impressionCount?: number;
}

export type PromptLibraryEventType = "impression" | "click" | "use";

export interface PromptSceneRecommendationPayload {
  recommendations: PromptSceneRecommendation[];
  reason: "ok" | "gpt55_not_configured" | "prompt_library_empty" | "no_match" | string;
  modelGroupId?: string;
  subModelId?: string;
}

export interface UploadedAsset {
  id: string;
  fileName: string;
  publicUrl: string;
  contentType: string;
  localPreviewUrl: string;
  thumbnailUrl?: string;
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
