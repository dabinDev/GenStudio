export interface AdminUserSession {
  id: string;
  username?: string;
  displayName?: string;
  nickname?: string;
  email?: string;
  avatarUrl?: string;
  isAdmin?: boolean;
  status?: string;
}

export interface AdminPermissions {
  role: string;
  permissions: string[];
}

export type Capability = 'text' | 'image' | 'video' | string;

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
  capability?: string;
  modelGroupId?: string;
  subModelId?: string;
  conversationId?: string;
  messageId?: string;
  taskId?: string;
  relatedTransactionId?: string;
  status: string;
  reason: string;
  operatorUserId?: string;
  metadata?: Record<string, unknown>;
  createdAt: string;
}

export interface AdminUserWithCredits extends AdminUserSession {
  externalUserId: string;
  phone: string;
  status: string;
  isAdmin: boolean;
  adminRole?: string;
  adminRoleSource?: string;
  createdAt: string;
  updatedAt: string;
  sessionCount?: number;
  lastSeenAt?: string | null;
  recentLoginIp?: string;
  credits: CreditAccount | null;
  duplicateIdentity?: AdminUserDuplicateIdentity | null;
}

export interface AdminUserDuplicateIdentity {
  identity: string;
  duplicateCount: number;
  targetUserId: string;
  userIds: string[];
}

export interface AdminUserListQuery {
  search?: string;
  role?: string;
  status?: string;
  page?: number;
  pageSize?: number;
}

export interface AdminUsersSummary {
  totalUsers: number;
  adminCount: number;
  totalBalance: number;
}

export interface AdminListMeta {
  total?: number;
  page?: number;
  pageSize?: number;
  hasMore?: boolean;
  summary?: AdminUsersSummary;
}

export interface AdminUserCreditPayload {
  account: CreditAccount;
  transactions: CreditTransaction[];
}

export interface AdminCreditAdjustmentPayload {
  account: CreditAccount;
  transaction: CreditTransaction;
  user: AdminUserWithCredits;
}

export interface AdminUserUpdatePayload {
  email?: string;
  phone?: string;
  nickname?: string;
  avatarUrl?: string;
  status?: string;
}

export interface AdminUserRoleUpdatePayload {
  role: 'admin' | 'operator' | 'viewer' | string;
  note?: string;
}

export interface AdminCatalogModel {
  id: string;
  modelName?: string;
  displayName?: string;
  capability?: Capability;
  vendor?: string;
  [key: string]: unknown;
}

export interface AdminSubModel {
  id: string;
  modelName: string;
  isPrimary?: boolean;
  catalogModelId?: string | null;
  catalog?: AdminCatalogModel | null;
  [key: string]: unknown;
}

export interface AdminModel {
  id: string;
  name: string;
  vendor: string;
  capability: Capability;
  adapter: string;
  description: string;
  apiKeyId?: string;
  baseUrl: string;
  primarySubModelId?: string;
  primaryModelName: string;
  isPublic: boolean;
  canEdit: boolean;
  catalogModelId?: string | null;
  catalog?: AdminCatalogModel | null;
  subModels?: AdminSubModel[];
  publicDisplayName: string;
  publicDescription: string;
  inputHint: string;
  iconUrl: string;
  publicTags: string[];
  promptOptimizeEnabled: boolean;
  defaultParameters: Record<string, unknown>;
  creditPrice: number;
  creditPriceSource: string;
  creditPricingEnabled?: boolean;
}

export interface AdminModelListQuery {
  capability?: string;
  search?: string;
  publicState?: 'all' | 'public' | 'private' | string;
  page?: number;
  pageSize?: number;
}

export interface AdminModelUpdate {
  publicDisplayName?: string;
  publicDescription?: string;
  inputHint?: string;
  iconUrl?: string;
  publicTags?: string[];
  promptOptimizeEnabled?: boolean;
  defaultParameters?: Record<string, unknown>;
  isPublic?: boolean;
}

export interface AdminModelCreditPricingUpdate {
  price?: number;
  useDefault?: boolean;
}

export interface AdminModelHealth {
  status?: string;
  totalCalls?: number;
  failedCalls?: number;
  failureRate?: number;
  averageDurationMs?: number;
  lastError?: string;
  [key: string]: unknown;
}

export interface AdminBatchModelHealthCheckResult {
  modelId: string;
  status: string;
  health?: AdminModelHealth;
  error?: {
    statusCode?: number;
    message?: string;
  };
}

export interface AdminBatchModelHealthCheckResponse {
  results: AdminBatchModelHealthCheckResult[];
}

export interface AdminRemoveUnavailableSkippedModel {
  modelId: string;
  reason: string;
  statusCode?: number;
  message?: string;
}

export interface AdminRemoveUnavailableModelsResponse {
  removedIds: string[];
  skipped: AdminRemoveUnavailableSkippedModel[];
  models: AdminModel[];
}

export interface AdminDashboardTotals {
  totalCalls: number;
  successCalls: number;
  failedCalls: number;
  timeoutCalls: number;
  failureRate: number;
  timeoutRate: number;
  averageDurationMs: number;
  averageQueueMs?: number;
  quotaUnits?: number;
  publicModelCalls: number;
  privateModelCalls: number;
}

export interface AdminDashboardTrendBucket {
  label: string;
  totalCalls: number;
  successCalls: number;
  failedCalls: number;
  timeoutCalls: number;
  quotaUnits: number;
  averageDurationMs: number;
}

export interface AdminDashboardBreakdownItem {
  key?: string;
  label?: string;
  capability?: string;
  ownership?: string;
  totalCalls: number;
  successCalls: number;
  failedCalls: number;
  failureRate: number;
}

export interface AdminDashboardCreditSummary {
  reserved: number;
  spent: number;
  refunded: number;
  adminAdjusted: number;
}

export interface AdminDashboardModelMetric {
  modelGroupId: string;
  modelName: string;
  capability: string;
  totalCalls: number;
  failedCalls?: number;
  failureRate?: number;
  averageDurationMs?: number;
  lastError?: string;
}

export interface AdminDashboardActiveUser {
  userId: string;
  label: string;
  totalCalls: number;
  publicModelCalls: number;
  privateModelCalls: number;
}

export interface AdminDashboardMetrics {
  totals: AdminDashboardTotals;
  trends: Record<string, AdminDashboardTrendBucket[]>;
  capabilityBreakdown: AdminDashboardBreakdownItem[];
  ownershipBreakdown: AdminDashboardBreakdownItem[];
  creditSummary: AdminDashboardCreditSummary;
  failedModels: AdminDashboardModelMetric[];
  slowModels: AdminDashboardModelMetric[];
  activeUsers: AdminDashboardActiveUser[];
}

export interface PromptTemplate {
  id: string;
  capability: Capability;
  modelGroupId: string;
  templateType: string;
  name: string;
  content: string;
  enabled: boolean;
  updatedBy?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface PromptTemplateUpdatePayload {
  capability?: Capability;
  modelGroupId?: string;
  templateType?: string;
  name?: string;
  content?: string;
  enabled?: boolean;
}

export interface PromptTemplateVersion {
  id: string;
  templateId: string;
  version: number;
  name: string;
  content: string;
  enabled: boolean;
  updatedBy?: string;
  createdAt?: string;
}

export interface PromptTemplateModelStatus {
  modelGroupId: string;
  modelName: string;
  capability: Capability;
  promptOptimizeEnabled: boolean;
  usesDefault: boolean;
  defaultTemplateId?: string;
  defaultTemplateEnabled?: boolean;
  hasModelTemplate: boolean;
  modelTemplateId?: string;
  modelTemplateEnabled?: boolean;
}

export interface PromptTemplateTestResult {
  prompt: string;
  rendered: string;
}

export interface PromptTemplateTestPayload {
  capability: Capability;
  content: string;
  prompt?: string;
  prompts?: string[];
}

export interface PromptSceneTemplate {
  id: string;
  externalId: string;
  capability: 'image';
  categoryId: string;
  documentTitle: string;
  documentUrl: string;
  section: string;
  category: string;
  subcategory: string;
  title: string;
  promptText: string;
  promptSummary: string;
  tags: string[];
  source: string;
  originalNo: string;
  imageUrl: string;
  model: string;
  likes: number;
  views: number;
  weight: number;
  enabled: boolean;
  useCount: number;
  clickCount: number;
  impressionCount: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface PromptSceneTemplateQuery {
  search?: string;
  categoryId?: string;
  enabled?: 'true' | 'false' | '';
  limit?: number;
  offset?: number;
}

export interface PromptSceneTemplateSummary {
  total: number;
  enabled: number;
  impressions: number;
  clicks: number;
  uses: number;
}

export interface PromptSceneTemplateListPayload {
  templates: PromptSceneTemplate[];
  total: number;
  summary?: PromptSceneTemplateSummary;
}

export interface PromptSceneTemplateUpdatePayload {
  title?: string;
  promptText?: string;
  tags?: string[];
  categoryId?: string;
  category?: string;
  subcategory?: string;
  weight?: number;
  enabled?: boolean;
}

export interface PromptSceneTemplateImportSummary {
  imported: number;
  updated: number;
  disabled: number;
  total: number;
}

export interface AdminCreationAsset {
  type: string;
  url: string;
  thumbnailUrl?: string;
}

export interface AdminCreationRecord {
  id: string;
  user: AdminUserWithCredits | null;
  modelName: string;
  capability: Capability;
  status: string;
  prompt: string;
  response: string;
  createdAt: string;
  durationMs: number;
  taskId: string;
  assets: AdminCreationAsset[];
  requestParams: Record<string, unknown>;
  responseSummary: Record<string, unknown>;
  errorMessage: string;
}

export interface AdminCreationRecordDetail {
  id: string;
  conversationId?: string | null;
  conversationTitle?: string | null;
  taskId?: string;
  user: AdminUserWithCredits | null;
  role?: string;
  capability: Capability;
  status: string;
  content?: string;
  request: Record<string, unknown>;
  response: Record<string, unknown> | string | null;
  errorMessage?: string;
  assets: AdminCreationAsset[];
  timeline: AdminTaskTimelineEvent[];
  createdAt: string;
}

export interface AdminTaskTimelineEvent {
  id: string;
  source: string;
  eventType: string;
  endpoint: string;
  status: string;
  durationMs: number;
  errorMessage?: string;
  message?: string;
  payload?: Record<string, unknown>;
  responseSummary?: Record<string, unknown>;
  createdAt: string;
}

export interface AdminTaskTimeline {
  taskId: string;
  events: AdminTaskTimelineEvent[];
}

export interface AdminRecordQuery {
  userId?: string;
  userSearch?: string;
  modelGroupId?: string;
  status?: string;
  keyword?: string;
  size?: string;
  ratio?: string;
  refCount?: string;
  duration?: string;
  resolution?: string;
  mode?: string;
  startAt?: string;
  endAt?: string;
  page?: number;
  pageSize?: number;
}

export interface AdminAuditLog {
  id: string;
  adminUserId: string | null;
  action: string;
  targetType: string;
  targetId: string;
  status: string;
  riskLevel?: string;
  summary: Record<string, unknown>;
  createdAt: string;
}

export interface AdminAuditLogQuery {
  action?: string;
  adminUserId?: string;
  targetType?: string;
  targetId?: string;
  status?: string;
  risk?: string;
  startAt?: string;
  endAt?: string;
  limit?: number;
  page?: number;
  pageSize?: number;
}

export interface CreditSettings {
  defaults: Record<'text' | 'image' | 'video', number>;
  signupBonusEnabled: boolean;
  signupBonusAmount: number;
}

export interface CreditSettingsUpdatePayload {
  defaults?: Partial<Record<'text' | 'image' | 'video', number>>;
  signupBonusEnabled?: boolean;
  signupBonusAmount?: number;
}

export interface UserMergeGroup {
  identity: string;
  targetUserId: string;
  targetExternalUserId?: string;
  sourceUserIds: string[];
  sourceExternalUserIds?: string[];
  movedRecords: number;
  roleConflicts?: UserMergeRoleConflict[];
}

export interface UserMergeRoleConflict {
  sourceUserId: string;
  targetUserId: string;
  targetRole: string;
  discardedRole: string;
  resolution: string;
  targetAssignment?: Record<string, unknown>;
  discardedAssignment?: Record<string, unknown>;
}

export interface UserMergeSummary {
  apply: boolean;
  groupCount: number;
  mergedUsers: number;
  movedRecords: number;
  roleConflictCount?: number;
  groups: UserMergeGroup[];
}

export interface UserMergeMaintenancePayload {
  apply: boolean;
  identityFilter?: string;
}

export interface AssetCleanupSettings {
  enabled: boolean;
  retentionDays: number;
  defaultRetentionDays: number;
  minRetentionDays: number;
  maxRetentionDays: number;
  lastRun: Partial<AssetCleanupSummary> & Record<string, unknown>;
}

export interface AssetCleanupSettingsUpdatePayload {
  enabled?: boolean;
  retentionDays?: number;
}

export interface AssetCleanupTargetSummary {
  key: string;
  label: string;
  path: string;
  totalFiles: number;
  expiredFiles: number;
  totalBytes: number;
  expiredBytes: number;
}

export interface AssetCleanupSummary {
  retentionDays: number;
  cutoffTs: number;
  totalFiles: number;
  expiredFiles: number;
  totalBytes: number;
  expiredBytes: number;
  deletedFiles?: number;
  deletedBytes?: number;
  failedFiles?: number;
  failures?: Array<{ path: string; message: string }>;
  ranAt?: string;
  targets: AssetCleanupTargetSummary[];
}

export interface AssetCleanupPayload {
  settings: AssetCleanupSettings;
  summary: AssetCleanupSummary;
}
