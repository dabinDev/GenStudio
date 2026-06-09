<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";

import {
  ADAPTER_LABELS,
  CAPABILITY_LABELS,
  IMAGE_TEMPLATES,
  TEXT_TEMPLATES,
  VIDEO_TEMPLATES,
  getAdapterOptions,
  getCapabilityDefaultAdapter,
} from "./catalog";
import {
  ApiRequestError,
  createServerModel,
  deleteServerModel,
  disableAdminUser,
  enableAdminUser,
  deleteAdminUser,
  fetchAdminAuditLogs,
  fetchAdminModels,
  fetchAdminOverview,
  fetchAdminOverviewModels,
  fetchAdminOverviewUsers,
  fetchAdminRecords,
  fetchAdminUsers,
  fetchConversation,
  fetchConversations,
  fetchServerModels,
  fetchPromptTemplates,
  optimizePrompt,
  postProxy,
  postProxyWithSignal,
  publishAdminModel,
  restoreAdminUser,
  savePromptTemplate as saveAdminPromptTemplateApi,
  setServerPrimaryModel,
  syncServerModel,
  testPromptTemplate as testAdminPromptTemplateApi,
  unpublishAdminModel,
  updateAdminModel,
  updateAdminUser,
  updateServerModel,
  uploadAsset,
} from "./api";
import { useAuthStore } from "./stores/auth";
import { useWorkbenchStore } from "./stores/workbench";
import type {
  Adapter,
  AdminAuditLog,
  AdminCreationRecord,
  AdminOverview,
  AdminOverviewModelRow,
  AdminOverviewUserRow,
  AdminUserDefinition,
  Capability,
  ConversationAsset,
  ConversationDefinition,
  ConversationMessage,
  ModelDefinition,
  ModelSetting,
  PromptTemplate,
  PromptTemplateDefinition,
  ServerModelDefinition,
  SubModelDefinition,
  UploadedAsset,
} from "./types";
import {
  appendLocalConversationMessages,
  buildImageGenerationRequestBody,
  buildVideoMediaFields,
  capabilityFilterForView,
  catalogDefaultValue,
  catalogMaxCount,
  catalogOptionItems,
  catalogParameterSignature,
  catalogRequestKey,
  catalogVideoModeValue,
  canEditModel,
  combinePrompt,
  conversationAssetsFromImageQueryResult,
  conversationAssetFromVideoQueryResult,
  createLocalId,
  deleteConfirmationSummary,
  filterReferenceImageFiles,
  findPromptBeforeMessage,
  generatedAssetReferenceFileName,
  getPrimarySubModel,
  hasCatalogParameter,
  hasCatalogParameters,
  getModelIdentifierError,
  getMissingModelMessage,
  imageGenerationSummary,
  isGeneratedModelDisplayName,
  isPrivateView,
  loginRedirectForView,
  markConversationMessageFailed,
  mediaPreviewActionLabels,
  modelCatalogIconUrl,
  modelCatalogInputHint,
  modelConnectionLabel,
  modelDisplayNameForModel,
  modelDisplayNameFromPrimary,
  modelParameterSourceLabel,
  nextMediaPreviewTransform,
  normalizeThemeMode,
  filterModelOptions,
  filterSettingsModels,
  pickPrimaryModel,
  prioritizeModelOptions,
  publicShareTargetModels,
  renderMarkdownPreview,
  resolveAuthRedirect,
  resolveModelName,
  resolveSidebarFilter,
  safeModelDescription,
  shouldResetConversationForModelSwitch,
  shouldContinuePollingTask,
  shortText,
  supportsCatalogParameter,
  testResultSummary,
  toggleThemeMode,
  updateLocalConversationMessage,
  updateLocalConversationTaskMessage,
  unavailableTestedModels,
  visibleConversationMessages,
  videoDurationOptionItems,
  videoGenerationSummary,
  videoMessageStatusFromTaskStatus,
  videoModeParamValue,
  videoModeRequiredUploadCount,
  videoModeUploadLimit,
  videoResolutionRequestKey,
  type VideoModeValue,
} from "./utils";
import {
  applyFetchedModelsToDraft,
  canFetchModelListForDraft,
  canSaveModelDraft,
  canTestModelDraft,
  getModelDraftMissingFieldLabels,
  getModelWizardProgress,
  getModelWizardStep,
  resolveDraftPrimaryModel,
} from "./modelWizard";
import { shouldShowDevAuth } from "./env";
import {
  ADMIN_PAGE_SUGGESTIONS,
  ADMIN_RECORD_CAPABILITY_BY_TAB,
  adminCapabilityTabs,
  adminNavGroups,
  adminRecordCapabilityTabs,
  adminTabs,
  type AdminTab,
} from "./adminPresentation";

type ViewName = "auth" | "auth-error" | "text" | "images" | "videos" | "settings" | "profile" | "admin";
type SidebarFilter = Capability | "all";
type VideoMode = VideoModeValue;
type VideoUploadTarget = "unified" | "first" | "last" | "seedanceRef" | "startEnd";
type DialogMode = "create" | "edit";
type ComposerPopover = "image-settings" | "image-advanced" | "video-mode" | "video-settings" | "video-advanced" | null;

interface ImageResult {
  images: Array<{ src: string; revisedPrompt?: string }>;
  taskId?: string;
  status?: string;
  progress?: number | string | null;
  raw?: Record<string, unknown>;
  conversation?: ConversationDefinition;
  assistantMessage?: ConversationMessage;
}

interface TextResult {
  content: string;
  taskId?: string;
  status?: string;
  usage?: Record<string, unknown>;
  raw?: Record<string, unknown>;
  conversation?: ConversationDefinition;
  assistantMessage?: ConversationMessage;
}

interface VideoCreateResult {
  taskId: string;
  status: string;
  raw: Record<string, unknown>;
  conversation?: ConversationDefinition;
  assistantMessage?: ConversationMessage;
}

interface VideoQueryResult {
  taskId: string;
  status: string;
  progress: number | string | null;
  videoUrl: string | null;
  thumbnailUrl: string | null;
  raw: Record<string, unknown>;
  conversation?: ConversationDefinition;
  assistantMessage?: ConversationMessage;
}

interface AvailableModelsResult {
  models: string[];
  durationMs: number;
  raw: Record<string, unknown>;
}

interface TestRequestResult {
  ok: boolean;
  status: number;
  request: { url: string; body: Record<string, unknown> };
  durationMs: number;
  raw: Record<string, unknown>;
}

interface ActionState<T> {
  loading: boolean;
  error: string;
  result: T | null;
}

interface ConfigDraft {
  id: string;
  name: string;
  vendor: string;
  capability: Capability;
  adapter: Adapter;
  model: string;
  description: string;
  baseUrl: string;
  apiKey: string;
  modelNameOverride: string;
  availableModels: string[];
  catalogModelId: string;
}

const UNIFIED_ADAPTERS: Adapter[] = [
  "video-unified-jimeng",
  "video-unified-vidu",
  "video-unified-veo",
  "video-unified-generic",
];
const TASK_POLL_INTERVAL_MS = 5000;
const THEME_STORAGE_KEY = "genstudio-theme";

const store = useWorkbenchStore();
const auth = useAuthStore();
const view = ref<ViewName>(getViewFromHash());
const themeMode = ref(normalizeThemeMode(localStorage.getItem(THEME_STORAGE_KEY)));
const sidebarFilter = ref<SidebarFilter>(capabilityFilterForView(view.value));
const showDevAuth = shouldShowDevAuth();
const devAuthCode = ref("dev:alice");
const authMode = ref<"login" | "register">("login");
const authForm = reactive({
  identifier: "",
  password: "",
  email: "",
  phone: "",
  nickname: "",
  registerPassword: "",
  error: "",
});
const profileForm = reactive({
  nickname: "",
  phone: "",
  avatarUrl: "",
  error: "",
  success: "",
});

const toastState = reactive({
  visible: false,
  message: "",
  type: "success" as "success" | "error" | "info",
});

const textModelId = ref("");
const imageModelId = ref("");
const videoModelId = ref("");

const textState = reactive({
  keywords: "",
  systemPrompt: "你是一个擅长创意表达、结构整理和提示词优化的专业创作助手。",
  prompt: "",
  temperature: "0.8",
  maxTokens: "1200",
  extraJson: "",
  optimizing: false,
  loading: false,
  error: "",
  result: null as TextResult | null,
});

const imageState = reactive({
  keywords: "",
  prompt: "",
  size: "1024x1024",
  ratio: "16:9",
  resolution: "2k",
  quality: "auto",
  count: "1",
  extraJson: "",
  uploading: false,
  optimizing: false,
  loading: false,
  error: "",
  references: [] as UploadedAsset[],
  result: null as ImageResult | null,
});

const videoState = reactive({
  mode: "text" as VideoMode,
  keywords: "",
  prompt: "",
  aspectRatio: "16:9",
  duration: "5",
  count: "1",
  size: "720P",
  resolution: "720p",
  audio: false,
  upsample: false,
  seed: "0",
  extraJson: "",
  autoPoll: true,
  uploading: false,
  optimizing: false,
  loading: false,
  querying: false,
  error: "",
  unifiedImages: [] as UploadedAsset[],
  seedanceFirst: null as UploadedAsset | null,
  seedanceLast: null as UploadedAsset | null,
  seedanceReferences: [] as UploadedAsset[],
  createResult: null as VideoCreateResult | null,
  taskResult: null as VideoQueryResult | null,
});

const referenceDropState = reactive({
  image: false,
  video: false,
});

let textPollTimer: number | null = null;
let textPollTaskId = "";
let imagePollTimer: number | null = null;
let imagePollTaskId = "";
let videoPollTimer: number | null = null;
let videoPollTaskId = "";

const settingsState = reactive({
  selectedIds: [] as string[],
  activeCapability: "all" as Capability | "all",
  searchQuery: "",
  dialogOpen: false,
  dialogMode: "create" as DialogMode,
  draft: createEmptyDraft(),
  modelListState: {} as Record<string, ActionState<AvailableModelsResult>>,
  testState: {} as Record<string, ActionState<TestRequestResult>>,
});

const adminState = reactive({
  activeTab: "overview" as AdminTab,
  loading: false,
  saving: "",
  error: "",
  success: "",
  modelCapability: "all" as Capability | "all",
  modelPublicState: "all" as "all" | "public" | "private",
  modelSearch: "",
  selectedModelIds: [] as string[],
  modelIconErrors: {} as Record<string, string>,
  userSearch: "",
  userRoleFilter: "all" as "all" | "admin" | "user",
  selectedUserId: "",
  recordStatus: "",
  recordUserSearch: "",
  recordModelGroupId: "",
  recordKeyword: "",
  recordSize: "",
  recordRatio: "",
  recordRefCount: "",
  recordDuration: "",
  recordResolution: "",
  recordMode: "",
  recordSavedFilters: [] as Array<{ id: string; name: string; capability: Capability; filters: Record<string, string> }>,
  recordMarkdownPreview: true,
  recordWaterfall: false,
  selectedRecordId: "",
  auditAction: "",
  auditAdminUserId: "",
  auditTargetType: "",
  auditTargetId: "",
  auditRisk: "",
  trendPeriod: "day" as "day" | "week" | "month",
  editingModelId: "",
  editingUserId: "",
  overview: null as AdminOverview | null,
  overviewUsers: [] as AdminOverviewUserRow[],
  overviewModels: [] as AdminOverviewModelRow[],
  models: [] as ModelDefinition[],
  templates: [] as PromptTemplateDefinition[],
  users: [] as AdminUserDefinition[],
  textRecords: [] as AdminCreationRecord[],
  imageRecords: [] as AdminCreationRecord[],
  videoRecords: [] as AdminCreationRecord[],
  auditLogs: [] as AdminAuditLog[],
  modelDrafts: {} as Record<string, {
    publicDisplayName: string;
    publicDescription: string;
    inputHint: string;
    iconUrl: string;
    publicTagsText: string;
    promptOptimizeEnabled: boolean;
    defaultParametersText: string;
  }>,
  templateDraft: {
    id: "",
    capability: "text" as Capability,
    modelGroupId: "",
    name: "默认提示词优化模板",
    enabled: true,
    content: "请将下面的用户提示词优化为更清晰、可执行、细节完整的创作提示词：\n\n{{prompt}}",
    testPrompt: "生成小米 SU7 变形金刚",
    testSamplesText: "生成小米 SU7 变形金刚\n参考图片生成电影级汽车海报\n写一段适合短视频开头的文案",
    previews: [] as Array<{ input: string; output: string }>,
    preview: "",
  },
  templateHistory: [] as Array<{
    id: string;
    templateId: string;
    name: string;
    capability: Capability;
    modelGroupId: string;
    content: string;
    enabled: boolean;
    savedAt: string;
  }>,
});

const adminActiveTab = computed(() => adminTabs.find((tab) => tab.value === adminState.activeTab) || adminTabs[0]);
const adminOverviewTotal = computed(() => Math.max(0, adminState.overview?.totalCalls || 0));
const adminSuccessRate = computed(() => {
  if (!adminOverviewTotal.value) return 0;
  return ((adminState.overview?.successCalls || 0) / adminOverviewTotal.value) * 100;
});
const adminFailurePercent = computed(() => (adminState.overview?.failureRate || 0) * 100);
const adminAverageDuration = computed(() => formatAdminDuration(adminState.overview?.averageDurationMs || 0));
const adminTopUsers = computed(() =>
  [...adminState.overviewUsers].sort((left, right) => right.totalCalls - left.totalCalls).slice(0, 8),
);
const adminTopModels = computed(() =>
  [...adminState.overviewModels].sort((left, right) => right.totalCalls - left.totalCalls).slice(0, 8),
);
const adminSlowModels = computed(() =>
  [...adminState.overviewModels]
    .filter((row) => row.totalCalls > 0)
    .sort((left, right) => right.averageDurationMs - left.averageDurationMs)
    .slice(0, 5),
);
const adminMaxUserCalls = computed(() => Math.max(1, ...adminTopUsers.value.map((row) => row.totalCalls)));
const adminMaxModelCalls = computed(() => Math.max(1, ...adminTopModels.value.map((row) => row.totalCalls)));
const adminStatusDonutSegments = computed(() => [
  { label: "成功", value: adminState.overview?.successCalls || 0, color: "#16a34a" },
  { label: "失败", value: adminState.overview?.failedCalls || 0, color: "#ef4444" },
]);
const adminOwnershipDonutSegments = computed(() => [
  { label: "公用模型", value: adminState.overview?.publicModelCalls || 0, color: "#2563eb" },
  { label: "私有模型", value: adminState.overview?.privateModelCalls || 0, color: "#f59e0b" },
]);
const adminCapabilityRows = computed(() => {
  const totals: Record<Capability, number> = { text: 0, image: 0, video: 0 };
  adminState.overviewModels.forEach((row) => {
    totals[row.model.capability] += row.totalCalls || 0;
  });
  return (Object.keys(totals) as Capability[]).map((capability) => ({
    capability,
    label: CAPABILITY_LABELS[capability],
    total: totals[capability],
    percent: adminRatio(totals[capability], adminOverviewTotal.value),
  }));
});
const adminPublicModelCount = computed(() => adminState.models.filter((model) => model.isPublic).length);
const adminPrivateModelCount = computed(() => Math.max(0, adminState.models.length - adminPublicModelCount.value));
const adminPromptTemplateCount = computed(() => adminState.templates.length);
const adminActiveUserCount = computed(() => adminState.users.filter((user) => user.status === "active").length);
const adminRecordCount = computed(() => adminRecordList(adminState.activeTab).length);
const adminAuditCount = computed(() => adminState.auditLogs.length);
const adminTrendPoints = computed(() => adminState.overview?.trend?.[adminState.trendPeriod] || []);
const adminTrendMax = computed(() => Math.max(1, ...adminTrendPoints.value.map((row) => row.totalCalls)));
const adminFailedModels = computed(() => adminState.overview?.failedModels || []);
const adminTimeoutPercent = computed(() => (adminState.overview?.timeoutRate || 0) * 100);
const adminSelectedModels = computed(() => adminState.models.filter((model) => adminState.selectedModelIds.includes(model.id)));
const adminVisibleModelIds = computed(() => adminState.models.map((model) => model.id));
const adminAllVisibleModelsSelected = computed(
  () => adminVisibleModelIds.value.length > 0 && adminVisibleModelIds.value.every((id) => adminState.selectedModelIds.includes(id)),
);
const adminFilteredUsers = computed(() =>
  adminState.users.filter((user) => {
    if (adminState.userRoleFilter === "admin") return user.isAdmin;
    if (adminState.userRoleFilter === "user") return !user.isAdmin;
    return true;
  }),
);
const adminSelectedUser = computed(() => adminState.users.find((user) => user.id === adminState.selectedUserId) || null);
const adminSelectedRecord = computed(() =>
  adminRecordList(adminState.activeTab).find((record) => record.id === adminState.selectedRecordId) || null,
);
const adminPromptModelOverview = computed(() =>
  adminState.models.map((model) => {
    const modelTemplate = adminState.templates.find(
      (template) => template.modelGroupId === model.id && template.templateType === "prompt_optimize",
    );
    const defaultTemplate = adminState.templates.find(
      (template) => !template.modelGroupId && template.capability === model.capability && template.templateType === "prompt_optimize",
    );
    const template = modelTemplate || defaultTemplate;
    return {
      model,
      template,
      enabled: model.promptOptimizeEnabled !== false && (template?.enabled ?? false),
    };
  }),
);

const conversationState = reactive({
  listOpen: false,
  loading: false,
  error: "",
  conversations: [] as ConversationDefinition[],
  current: null as ConversationDefinition | null,
  activeRequest: null as AbortController | null,
  streamingMessageId: "",
  streamingContent: "",
});

const mediaPreviewState = reactive({
  asset: null as ConversationAsset | null,
  scale: 1,
  offsetX: 0,
  offsetY: 0,
  dragging: false,
  dragStartX: 0,
  dragStartY: 0,
  dragOriginX: 0,
  dragOriginY: 0,
});

const composerUiState = reactive({
  popover: null as ComposerPopover,
  collapsed: false,
});

const modelSelectState = reactive({
  openId: "",
  query: "",
  placement: "down" as "down" | "up",
});

const IMAGE_RATIO_OPTIONS = ["1:1", "16:9", "9:16", "4:3", "3:4"];
const IMAGE_RESOLUTION_OPTIONS = ["1k", "2k", "4k"];
const IMAGE_SIZE_OPTIONS = ["1024x1024"];
const VIDEO_RATIO_OPTIONS = ["21:9", "3:4", "4:3", "1:1", "16:9", "9:16"];
const VIDEO_RESOLUTION_OPTIONS = ["480p", "720p", "1080p"];
const VIDEO_DURATION_OPTIONS = ["4", "5", "8", "10", "12", "15"];
const VIDEO_QUANTITY_OPTIONS = ["1", "2", "3", "4"];
const VIDEO_MODE_OPTIONS: Array<{ value: VideoMode; label: string }> = [
  { value: "text", label: "文生视频" },
  { value: "reference", label: "全能参考" },
  { value: "first-frame", label: "首帧" },
  { value: "start-end", label: "首尾帧" },
];

const activeCapability = computed<Capability | null>(() => {
  if (view.value === "images") return "image";
  if (view.value === "videos") return "video";
  if (view.value === "text") return "text";
  return null;
});

const effectiveSidebarFilter = computed(() => resolveSidebarFilter(store.models.value, sidebarFilter.value));

const filteredModels = computed(() =>
  store.models.value.filter((model) =>
    effectiveSidebarFilter.value === "all" ? true : model.capability === effectiveSidebarFilter.value,
  ),
);

const activeModels = computed(() => ({
  text: store.getModelsByCapability("text"),
  image: store.getModelsByCapability("image"),
  video: store.getModelsByCapability("video"),
}));

const activeModel = computed(() => {
  if (view.value === "text") {
    return activeModels.value.text.find((item) => item.id === textModelId.value) || activeModels.value.text[0] || null;
  }
  if (view.value === "images") {
    return activeModels.value.image.find((item) => item.id === imageModelId.value) || activeModels.value.image[0] || null;
  }
  if (view.value === "videos") {
    return activeModels.value.video.find((item) => item.id === videoModelId.value) || activeModels.value.video[0] || null;
  }
  return null;
});

const activeSetting = computed(() =>
  activeModel.value ? getSetting(activeModel.value.id) : undefined,
);

const settingsCapabilityTabs: Array<{ value: Capability | "all"; label: string }> = [
  { value: "text", label: "文案创作" },
  { value: "image", label: "图片创作" },
  { value: "video", label: "视频创作" },
  { value: "all", label: "全部" },
];

const settingsCapabilityCounts = computed<Record<Capability | "all", number>>(() => ({
  all: store.models.value.length,
  text: store.models.value.filter((model) => model.capability === "text").length,
  image: store.models.value.filter((model) => model.capability === "image").length,
  video: store.models.value.filter((model) => model.capability === "video").length,
}));

const filteredSettingsModels = computed(() =>
  filterSettingsModels(store.models.value, settingsState.activeCapability, settingsState.searchQuery),
);

const selectedVisibleSettingsModels = computed(() =>
  filteredSettingsModels.value.filter((model) => settingsState.selectedIds.includes(model.id)),
);

const publicShareTargets = computed(() =>
  publicShareTargetModels(filteredSettingsModels.value, settingsState.selectedIds),
);

const selectedEditableSettingsModels = computed(() =>
  selectedVisibleSettingsModels.value.filter((model) => canEditModel(model)),
);

const unavailableEditableSettingsModels = computed(() =>
  unavailableTestedModels(filteredSettingsModels.value, settingsState.testState, canEditModel),
);

const configuredCount = computed(() =>
  store.models.value.filter((model) => {
    const setting = getSetting(model.id);
    return isModelConfigured(model, setting);
  }).length,
);

const allSettingsSelected = computed(
  () =>
    filteredSettingsModels.value.length > 0 &&
    filteredSettingsModels.value.every((model) => settingsState.selectedIds.includes(model.id)),
);

const partialSettingsSelected = computed(
  () =>
    selectedVisibleSettingsModels.value.length > 0 &&
    selectedVisibleSettingsModels.value.length < filteredSettingsModels.value.length,
);

const visibleConversations = computed(() => {
  if (!activeCapability.value) return conversationState.conversations;
  return conversationState.conversations.filter((item) => item.capability === activeCapability.value);
});

const currentMessages = computed(() => visibleConversationMessages(conversationState.current, activeCapability.value));

const currentModelLabel = computed(() => {
  const model = activeModel.value;
  const setting = activeSetting.value;
  if (!model || !setting) return "未选择模型";
  return `${modelDisplayName(model)} / ${resolveModelName(model, setting)}`;
});

const activeModelHasCatalogParameters = computed(() => hasCatalogParameters(activeModel.value));
const activeModelParameterSourceLabel = computed(() => modelParameterSourceLabel(activeModel.value));
const textComposerPlaceholder = computed(() =>
  modelCatalogInputHint(activeModel.value, "输入你想生成的文案、脚本、提示词或结构化内容..."),
);
const imageComposerPlaceholder = computed(() =>
  modelCatalogInputHint(activeModel.value, `描述你想要生成的图片内容，支持上传参考图片进行图生图，最多${imageReferenceLimit.value}张`),
);
const videoComposerPlaceholder = computed(() =>
  modelCatalogInputHint(activeModel.value, "描述主体动作、镜头运动、时长、风格和节奏..."),
);

const modelWizardProgress = computed(() => getModelWizardProgress(settingsState.draft));
const modelWizardStep = computed(() => getModelWizardStep(settingsState.draft));
const draftRequiresServerCredentials = computed(
  () => Boolean(auth.state.user && settingsState.dialogMode === "create"),
);
const draftMissingFieldLabels = computed(() =>
  getModelDraftMissingFieldLabels(
    settingsState.draft,
    getDraftSetting(),
    draftRequiresServerCredentials.value,
  ),
);
const draftMissingFieldsText = computed(() => draftMissingFieldLabels.value.join("、"));
const canFetchDraftModels = computed(() => canFetchModelListForDraft(settingsState.draft));
const canTestDraftModel = computed(() => canTestModelDraft(settingsState.draft));
const draftFetchDisabledTitle = computed(() =>
  canFetchDraftModels.value ? "获取当前密钥可用模型" : "请先填写 baseURL 和 API Key",
);
const draftTestDisabledTitle = computed(() =>
  canTestDraftModel.value ? "测试当前主模型" : "请先获取模型列表并选择主模型",
);
const draftSaveDisabledTitle = computed(() =>
  canSaveDraft() ? "保存模型配置" : `请先填写：${draftMissingFieldsText.value || "必填信息"}`,
);

const imageSizeOptions = computed(() => catalogOptionItems(activeModel.value, "size", IMAGE_SIZE_OPTIONS));
const imageQualityOptions = computed(() => catalogOptionItems(activeModel.value, "quality", ["auto", "standard", "hd"]));
const imageQuantityOptions = computed(() => catalogOptionItems(activeModel.value, "quantity", ["1", "2", "3", "4"]));
const imageReferenceLimit = computed(() => catalogMaxCount(activeModel.value, ["images", "image"], 14));
const imageHasCatalogParameters = computed(() => hasCatalogParameters(activeModel.value));
const imageUsesSizeControls = computed(() => hasCatalogParameter(activeModel.value, "size"));
const imageUsesRatioControls = computed(() => !imageUsesSizeControls.value && supportsCatalogParameter(activeModel.value, "ratio", "aspect_ratio"));
const imageUsesResolutionControls = computed(() => !imageUsesSizeControls.value && supportsCatalogParameter(activeModel.value, "resolution", "size"));
const imageUsesQualityControls = computed(() => supportsCatalogParameter(activeModel.value, "quality"));
const imageUsesQuantityControls = computed(() => supportsCatalogParameter(activeModel.value, "quantity"));
const imageRatioOptions = computed(() => catalogOptionItems(activeModel.value, ["ratio", "aspect_ratio"], IMAGE_RATIO_OPTIONS));
const imageResolutionOptions = computed(() => catalogOptionItems(activeModel.value, ["resolution", "size"], IMAGE_RESOLUTION_OPTIONS));
const videoModeOptions = computed(() => {
  if (!hasCatalogParameter(activeModel.value, "video_mode")) return VIDEO_MODE_OPTIONS;
  return catalogOptionItems(activeModel.value, "video_mode", VIDEO_MODE_OPTIONS.map((item) => item.value)).map((item) => ({
    value: catalogVideoModeValue(item.value),
    label: item.label,
  }));
});
const videoHasCatalogParameters = computed(() => hasCatalogParameters(activeModel.value));
const videoUsesModeControls = computed(() => supportsCatalogParameter(activeModel.value, "video_mode"));
const videoUsesRatioControls = computed(() => supportsCatalogParameter(activeModel.value, "ratio", "aspect_ratio"));
const videoUsesResolutionControls = computed(() => supportsCatalogParameter(activeModel.value, "resolution", "size"));
const videoUsesDurationControls = computed(() => supportsCatalogParameter(activeModel.value, "duration"));
const videoUsesQuantityControls = computed(() => supportsCatalogParameter(activeModel.value, "quantity"));
const videoUsesAudioControls = computed(() => supportsCatalogParameter(activeModel.value, "generate_audio", "audio"));
const videoUsesSeedControls = computed(() => supportsCatalogParameter(activeModel.value, "seed"));
const videoRatioOptions = computed(() => catalogOptionItems(activeModel.value, ["ratio", "aspect_ratio"], VIDEO_RATIO_OPTIONS));
const videoResolutionOptions = computed(() => catalogOptionItems(activeModel.value, ["resolution", "size"], VIDEO_RESOLUTION_OPTIONS));
const videoDurationOptions = computed(() => videoDurationOptionItems(activeModel.value));
const videoQuantityOptions = computed(() => catalogOptionItems(activeModel.value, "quantity", VIDEO_QUANTITY_OPTIONS));
const unifiedVideoImageLimit = computed(() => videoModeUploadLimit(activeModel.value, videoState.mode));
const unifiedVideoRequiredImageCount = computed(() => videoModeRequiredUploadCount(videoState.mode));
const unifiedVideoAllowsMultiple = computed(() => unifiedVideoImageLimit.value > 1);
const videoDropHint = computed(() => {
  const target = currentVideoDropTarget();
  if (target === "first") return "松开添加首帧";
  if (target === "last") return "松开添加尾帧";
  if (target === "startEnd") return "松开添加首尾帧";
  return "松开添加参考图";
});

const imageControlSummary = computed(() =>
  imageGenerationSummary({
    ratio: imageUsesSizeControls.value ? imageState.size : imageUsesRatioControls.value ? imageState.ratio : "",
    resolution: imageUsesQualityControls.value ? imageState.quality : imageUsesResolutionControls.value ? imageState.resolution : "",
    count: imageUsesQuantityControls.value ? imageState.count : "",
  }),
);

const videoControlSummary = computed(() =>
  videoGenerationSummary({
    mode: videoUsesModeControls.value ? videoState.mode : "",
    aspectRatio: videoUsesRatioControls.value ? videoState.aspectRatio : "",
    resolution: videoUsesResolutionControls.value ? videoState.resolution : "",
    duration: videoUsesDurationControls.value ? videoState.duration : "",
    count: videoUsesQuantityControls.value ? videoState.count : "",
  }),
);

const composerSummary = computed(() => {
  const prompt =
    view.value === "text" ? textState.prompt : view.value === "images" ? imageState.prompt : view.value === "videos" ? videoState.prompt : "";
  const promptSummary = shortText(prompt.trim() || "点击展开输入提示词", 96);
  const refs =
    view.value === "images"
      ? imageState.references.length
      : view.value === "videos"
        ? videoState.unifiedImages.length +
          videoState.seedanceReferences.length +
          (videoState.seedanceFirst ? 1 : 0) +
          (videoState.seedanceLast ? 1 : 0)
        : 0;
  const controls = view.value === "images" ? imageControlSummary.value : view.value === "videos" ? videoControlSummary.value : "文案创作";
  return {
    prompt: promptSummary,
    refs,
    controls,
  };
});

const userAccountLabel = computed(() => {
  if (!auth.state.user) return auth.state.loading ? "登录状态读取中" : "可使用官网授权或本地账号登录";
  return auth.state.user.email || auth.state.user.phone || "已登录";
});

const themeToggleLabel = computed(() => (themeMode.value === "light" ? "夜间模式" : "白天模式"));
const themeToggleTitle = computed(() => (themeMode.value === "light" ? "切换到夜间模式" : "切换到白天模式"));

function setThemeMode(nextTheme: "dark" | "light") {
  themeMode.value = normalizeThemeMode(nextTheme);
}

function toggleTheme() {
  setThemeMode(toggleThemeMode(themeMode.value));
}

onMounted(async () => {
  await initializeSession();
  syncProfileForm();
  syncInitialModels();
  handleHashChange();
  window.addEventListener("hashchange", handleHashChange);
});

onUnmounted(() => {
  stopTextPolling();
  stopImagePolling();
  stopVideoPolling();
  document.documentElement.classList.remove("media-preview-open");
  window.removeEventListener("hashchange", handleHashChange);
});

watch(
  themeMode,
  (nextTheme) => {
    const normalized = normalizeThemeMode(nextTheme);
    document.documentElement.dataset.theme = normalized;
    localStorage.setItem(THEME_STORAGE_KEY, normalized);
  },
  { immediate: true },
);

watch(
  () => store.models.value.map((model) => model.id).join(","),
  syncInitialModels,
  { immediate: true },
);

watch(
  () => auth.state.user?.id,
  () => {
    syncProfileForm();
    if (view.value === "admin" && auth.state.user?.isAdmin) {
      void loadAdminTab();
    }
  },
);

watch(
  () => view.value,
  (nextView) => {
    if (nextView === "admin" && auth.state.user?.isAdmin) {
      void loadAdminTab();
    }
  },
);

watch(
  () => [
    activeModel.value?.id || "",
    activeModel.value?.primarySubModelId || "",
    activeModel.value ? getPrimarySubModel(activeModel.value)?.catalogModelId || "" : "",
    activeModel.value ? catalogParameterSignature(activeModel.value) : "",
  ].join(":"),
  () => syncComposerParametersFromCatalog(true),
  { immediate: true },
);

function getViewFromHash(): ViewName {
  const hash = window.location.hash.replace(/^#\/?/, "");
  const route = hash.split("?", 1)[0];
  if (route === "auth" || route === "auth-error" || route === "images" || route === "videos" || route === "settings" || route === "profile" || route === "text" || route === "admin") {
    return route;
  }
  return "images";
}

function setView(nextView: ViewName) {
  view.value = nextView;
  sidebarFilter.value = capabilityFilterForView(nextView);
}

function currentReturnView(): ViewName {
  return view.value === "auth" || view.value === "auth-error" ? "images" : view.value;
}

function requireLoginForView(nextView: ViewName): boolean {
  if (auth.state.user || !isPrivateView(nextView)) return true;
  const redirectPath = loginRedirectForView(nextView);
  window.location.hash = redirectPath;
  setView("auth");
  return false;
}

function requireLoginForAction(nextView: ViewName = currentReturnView()): boolean {
  if (auth.state.user) return true;
  const redirectPath = loginRedirectForView(nextView);
  window.location.hash = redirectPath;
  setView("auth");
  return false;
}

function handleHashChange() {
  const nextView = getViewFromHash();
  if (!requireLoginForView(nextView)) return;
  setView(nextView);
}

function navigate(nextView: ViewName) {
  closeComposerPopover();
  closeModelSelect();
  if (!requireLoginForView(nextView)) return;
  window.location.hash = `/${nextView}`;
  setView(nextView);
}

function authErrorMessage(): string {
  const query = window.location.hash.split("?", 2)[1] || "";
  const params = new URLSearchParams(query);
  return params.get("message") || "授权登录失败，请返回官网重新进入创意工坊。";
}

function showToast(message: string, type: "success" | "error" | "info" = "success") {
  toastState.message = message;
  toastState.type = type;
  toastState.visible = true;
  window.setTimeout(() => {
    if (toastState.message === message) {
      toastState.visible = false;
    }
  }, 2600);
}

function syncInitialModels() {
  syncSelectedModel(textModelId, activeModels.value.text);
  syncSelectedModel(imageModelId, activeModels.value.image);
  syncSelectedModel(videoModelId, activeModels.value.video);
}

function syncSelectedModel(modelId: typeof textModelId, models: ModelDefinition[]) {
  if (!models.some((model) => model.id === modelId.value)) {
    modelId.value = models[0]?.id || "";
  }
}

async function refreshConversations() {
  if (!auth.state.user) {
    return;
  }
  conversationState.loading = true;
  conversationState.error = "";
  try {
    conversationState.conversations = await fetchConversations();
  } catch (error) {
    conversationState.error = error instanceof Error ? error.message : "读取历史记录失败。";
  } finally {
    conversationState.loading = false;
  }
}

async function openConversation(conversationId: string) {
  if (!auth.state.user) return;
  conversationState.loading = true;
  conversationState.error = "";
  try {
    const conversation = await fetchConversation(conversationId);
    setCurrentConversation(conversation);
    navigate(capabilityToView(conversation.capability));
    selectConversationModel(conversation);
    conversationState.listOpen = false;
  } catch (error) {
    conversationState.error = error instanceof Error ? error.message : "打开历史记录失败。";
  } finally {
    conversationState.loading = false;
  }
}

function setCurrentConversation(conversation?: ConversationDefinition | null) {
  if (!conversation) return;
  conversationState.current = conversation;
  upsertConversationSummary(conversation);
}

function upsertConversationSummary(conversation: ConversationDefinition) {
  const summary = { ...conversation, messages: [] };
  const index = conversationState.conversations.findIndex((item) => item.id === conversation.id);
  if (index >= 0) {
    conversationState.conversations[index] = summary;
    return;
  }
  conversationState.conversations = [summary, ...conversationState.conversations];
}

function capabilityToView(capability: Capability): ViewName {
  if (capability === "text") return "text";
  if (capability === "video") return "videos";
  return "images";
}

function startNewConversation(nextView: ViewName = view.value) {
  stopActiveRequest();
  stopTextPolling();
  stopImagePolling();
  stopVideoPolling();
  closeComposerPopover();
  composerUiState.collapsed = false;
  conversationState.current = null;
  conversationState.streamingMessageId = "";
  conversationState.streamingContent = "";
  textState.result = null;
  imageState.result = null;
  videoState.createResult = null;
  videoState.taskResult = null;
  if (nextView === "settings" || nextView === "profile" || nextView === "admin") {
    navigate("images");
  }
}

function toggleComposerPopover(popover: Exclude<ComposerPopover, null>) {
  composerUiState.popover = composerUiState.popover === popover ? null : popover;
}

function closeComposerPopover() {
  composerUiState.popover = null;
}

function toggleComposerCollapsed() {
  composerUiState.collapsed = !composerUiState.collapsed;
  closeComposerPopover();
}

function modelSelectKey(kind: "row" | "draft", id = ""): string {
  return kind === "draft" ? "draft" : `row:${id}`;
}

function isModelSelectOpen(key: string): boolean {
  return modelSelectState.openId === key;
}

function getModelSelectPlacement(event?: MouseEvent): "down" | "up" {
  const target = event?.currentTarget instanceof HTMLElement ? event.currentTarget : null;
  if (!target) return "down";
  const rect = target.getBoundingClientRect();
  const spaceBelow = window.innerHeight - rect.bottom;
  return spaceBelow < 320 && rect.top > spaceBelow ? "up" : "down";
}

function toggleModelSelect(key: string, event?: MouseEvent) {
  if (modelSelectState.openId === key) {
    closeModelSelect();
    return;
  }
  modelSelectState.openId = key;
  modelSelectState.query = "";
  modelSelectState.placement = getModelSelectPlacement(event);
}

function closeModelSelect() {
  modelSelectState.openId = "";
  modelSelectState.query = "";
  modelSelectState.placement = "down";
}

function filteredModelSelectOptions(options: string[], selectedModel = ""): string[] {
  return prioritizeModelOptions(filterModelOptions(options, modelSelectState.query), selectedModel);
}

function optionValues(options: Array<{ value: string }>): string[] {
  return options.map((item) => item.value).filter(Boolean);
}

function normalizeOptionValue(current: string, options: Array<{ value: string }>, fallback: string): string {
  const values = optionValues(options);
  if (values.includes(current)) return current;
  return values.includes(fallback) ? fallback : values[0] || fallback;
}

function normalizeVideoMode(current: VideoMode, options: Array<{ value: VideoMode }>, fallback: VideoMode): VideoMode {
  const values = options.map((item) => item.value);
  if (values.includes(current)) return current;
  return values.includes(fallback) ? fallback : values[0] || fallback;
}

function modelSupportsParameter(model: ModelDefinition, ...keys: string[]): boolean {
  return supportsCatalogParameter(model, ...keys);
}

function addPayloadField(
  payload: Record<string, unknown>,
  model: ModelDefinition,
  keys: string[],
  outputKey: string,
  value: unknown,
) {
  if (modelSupportsParameter(model, ...keys)) {
    payload[catalogRequestKey(model, keys, outputKey)] = value;
  }
}

function buildImageRequestBody(model: ModelDefinition, finalPrompt: string, extra: Record<string, unknown>) {
  return buildImageGenerationRequestBody(
    model,
    {
      references: imageState.references.map((item) => item.publicUrl),
      count: imageState.count,
      size: imageState.size,
      ratio: imageState.ratio,
      resolution: imageState.resolution,
      quality: imageState.quality,
    },
    finalPrompt,
    extra,
  );
}

function addSeedParameter(payload: Record<string, unknown>, model: ModelDefinition) {
  if (modelSupportsParameter(model, "seed")) {
    payload.seed = Number(videoState.seed) || 0;
  }
}

function syncComposerParametersFromCatalog(resetToCatalogDefaults = false) {
  const model = activeModel.value;
  if (!model) return;
  if (model.capability === "image") {
    const defaultSize = catalogDefaultValue(model, "size", imageState.size || "1024x1024");
    const defaultQuality = catalogDefaultValue(model, "quality", imageState.quality || "auto");
    const defaultCount = catalogDefaultValue(model, "quantity", imageState.count || "1");
    const defaultRatio = catalogDefaultValue(model, ["ratio", "aspect_ratio"], imageState.ratio || "16:9");
    const defaultResolution = catalogDefaultValue(model, ["resolution", "size"], imageState.resolution || "2k");
    imageState.size = normalizeOptionValue(resetToCatalogDefaults ? defaultSize : imageState.size, imageSizeOptions.value, defaultSize);
    imageState.quality = normalizeOptionValue(resetToCatalogDefaults ? defaultQuality : imageState.quality, imageQualityOptions.value, defaultQuality);
    imageState.count = normalizeOptionValue(resetToCatalogDefaults ? defaultCount : imageState.count, imageQuantityOptions.value, defaultCount);
    imageState.ratio = normalizeOptionValue(resetToCatalogDefaults ? defaultRatio : imageState.ratio, imageRatioOptions.value, defaultRatio);
    imageState.resolution = normalizeOptionValue(resetToCatalogDefaults ? defaultResolution : imageState.resolution, imageResolutionOptions.value, defaultResolution);
    imageState.references = imageState.references.slice(0, imageReferenceLimit.value);
  }
  if (model.capability === "video") {
    const defaultMode = catalogVideoModeValue(catalogDefaultValue(model, "video_mode", videoState.mode));
    const defaultRatio = catalogDefaultValue(model, ["ratio", "aspect_ratio"], videoState.aspectRatio || "16:9");
    const defaultResolution = catalogDefaultValue(model, ["resolution", "size"], videoState.resolution || "720p");
    const defaultDuration = catalogDefaultValue(model, "duration", videoState.duration || "5");
    const defaultCount = catalogDefaultValue(model, "quantity", videoState.count || "1");
    videoState.mode = normalizeVideoMode(resetToCatalogDefaults ? defaultMode : videoState.mode, videoModeOptions.value, defaultMode);
    videoState.aspectRatio = normalizeOptionValue(resetToCatalogDefaults ? defaultRatio : videoState.aspectRatio, videoRatioOptions.value, defaultRatio);
    videoState.resolution = normalizeOptionValue(resetToCatalogDefaults ? defaultResolution : videoState.resolution, videoResolutionOptions.value, defaultResolution);
    videoState.duration = normalizeOptionValue(resetToCatalogDefaults ? defaultDuration : videoState.duration, videoDurationOptions.value, defaultDuration);
    videoState.count = normalizeOptionValue(resetToCatalogDefaults ? defaultCount : videoState.count, videoQuantityOptions.value, defaultCount);
    if (resetToCatalogDefaults || videoHasCatalogParameters.value) {
      videoState.audio = catalogDefaultValue(model, ["generate_audio", "audio"], String(videoState.audio)) === "true";
    }
  }
}

async function chooseRowPrimaryModel(modelId: string, model: ModelDefinition) {
  if (!canEditModel(model)) {
    showToast("公共模型只有管理员可以修改。", "error");
    closeModelSelect();
    return;
  }
  await setPrimaryModel(modelId, model, getSetting(model.id));
  closeModelSelect();
}

function chooseDraftPrimaryModel(modelId: string) {
  settingsState.draft.modelNameOverride = modelId;
  settingsState.draft.model = modelId;
  closeModelSelect();
}

function selectVideoMode(mode: VideoMode) {
  videoState.mode = mode;
  if (mode === "text") {
    videoState.unifiedImages = [];
  }
  if (supportsUnifiedAdapter(activeModel.value?.adapter)) {
    videoState.unifiedImages = videoState.unifiedImages.slice(0, videoModeUploadLimit(activeModel.value, mode));
  }
  closeComposerPopover();
}

function videoModeLabel(mode: VideoMode): string {
  return videoModeOptions.value.find((item) => item.value === mode)?.label || VIDEO_MODE_OPTIONS.find((item) => item.value === mode)?.label || "文生视频";
}

function removeImageReference(assetId: string) {
  imageState.references = imageState.references.filter((asset) => asset.id !== assetId);
}

function removeUnifiedVideoReference(assetId: string) {
  videoState.unifiedImages = videoState.unifiedImages.filter((asset) => asset.id !== assetId);
}

function removeSeedanceReference(assetId: string) {
  videoState.seedanceReferences = videoState.seedanceReferences.filter((asset) => asset.id !== assetId);
}

async function toggleHistoryDrawer() {
  if (!requireLoginForAction(currentReturnView())) return;
  if (!conversationState.listOpen) {
    await refreshConversations();
    composerUiState.collapsed = true;
  }
  conversationState.listOpen = !conversationState.listOpen;
}

function selectConversationModel(conversation: ConversationDefinition) {
  if (!conversation.modelGroupId) return;
  const model = store.models.value.find((item) => item.id === conversation.modelGroupId);
  if (model) selectModel(model);
}

function updateConversationFromUnknown(payload: unknown) {
  if (!payload || typeof payload !== "object") return;
  const maybeConversation = (payload as { conversation?: ConversationDefinition }).conversation;
  if (maybeConversation?.id) {
    setCurrentConversation(maybeConversation);
  }
}

function conversationFromUnknown(payload: unknown): ConversationDefinition | null {
  if (!payload || typeof payload !== "object") return null;
  const maybeConversation = (payload as { conversation?: ConversationDefinition }).conversation;
  return maybeConversation?.id ? maybeConversation : null;
}

function handleRequestError(error: unknown, fallbackMessage: string): string {
  if (error instanceof DOMException && error.name === "AbortError") {
    return "请求已暂停。";
  }
  if (error instanceof ApiRequestError) {
    updateConversationFromUnknown(error.detail);
    return error.message || fallbackMessage;
  }
  return error instanceof Error ? error.message : fallbackMessage;
}

function resolveRequestErrorMessage(error: unknown, fallbackMessage: string): string {
  if (error instanceof DOMException && error.name === "AbortError") {
    return "请求已暂停。";
  }
  if (error instanceof ApiRequestError) {
    return error.message || fallbackMessage;
  }
  return error instanceof Error ? error.message : fallbackMessage;
}

function markLocalAssistantMessageFailed(
  conversation: ConversationDefinition | null,
  messageId: string,
  message: string,
) {
  const failedConversation = markConversationMessageFailed(conversation, messageId, message);
  if (failedConversation) setCurrentConversation(failedConversation);
}

function createRequestController(): AbortController {
  stopActiveRequest();
  const controller = new AbortController();
  conversationState.activeRequest = controller;
  return controller;
}

function clearRequestController(controller: AbortController) {
  if (conversationState.activeRequest === controller) {
    conversationState.activeRequest = null;
  }
}

function stopActiveRequest() {
  stopTextPolling();
  stopImagePolling();
  stopVideoPolling();
  conversationState.activeRequest?.abort();
  conversationState.activeRequest = null;
}

function previewMessageContent(message: ConversationMessage): string {
  if (message.id === conversationState.streamingMessageId && conversationState.streamingContent) {
    return conversationState.streamingContent;
  }
  return message.content;
}

function markdownPreview(value: string): string {
  return renderMarkdownPreview(value || "");
}

function messageStatusLabel(message: ConversationMessage): string {
  if (message.status === "processing") return "生成中";
  if (message.status === "error") return "失败";
  return "完成";
}

function formatAdminNumber(value: number | undefined | null): string {
  return Math.max(0, Number(value || 0)).toLocaleString("zh-CN");
}

function adminRatio(value: number, total: number): number {
  if (!total) return 0;
  return Math.max(0, Math.min(100, (value / total) * 100));
}

function adminPercentLabel(value: number): string {
  return `${value.toFixed(1)}%`;
}

function formatAdminDuration(value: number | undefined | null): string {
  const duration = Math.max(0, Number(value || 0));
  if (duration >= 1000) return `${(duration / 1000).toFixed(1)}s`;
  return `${Math.round(duration)}ms`;
}

function formatAdminQuota(value: number | undefined | null): string {
  const quota = Math.max(0, Number(value || 0));
  if (quota >= 1000000) return `${(quota / 1000000).toFixed(2)}M`;
  if (quota >= 1000) return `${(quota / 1000).toFixed(1)}K`;
  return quota.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

function adminBarWidth(value: number, max: number): string {
  return `${Math.max(4, adminRatio(value, max))}%`;
}

function adminDonutGradient(segments: Array<{ value: number; color: string }>): string {
  const total = segments.reduce((sum, segment) => sum + Math.max(0, segment.value), 0);
  if (!total) return "conic-gradient(#e2e8f0 0deg 360deg)";
  let cursor = 0;
  const stops = segments
    .filter((segment) => segment.value > 0)
    .map((segment) => {
      const start = cursor;
      cursor += (segment.value / total) * 360;
      return `${segment.color} ${start.toFixed(2)}deg ${cursor.toFixed(2)}deg`;
    });
  return `conic-gradient(${stops.join(", ")})`;
}

function adminTrendHeight(value: number): string {
  return `${Math.max(8, adminRatio(value, adminTrendMax.value))}%`;
}

function adminRiskLabel(value: string | undefined): string {
  if (value === "high") return "高风险";
  if (value === "medium") return "需关注";
  return "普通";
}

function adminRiskBadge(value: string | undefined): string {
  if (value === "high") return "badge-danger";
  if (value === "medium") return "badge-warn";
  return "badge-success";
}

function adminCapabilityLabel(value: string | undefined): string {
  if (value === "text" || value === "image" || value === "video") return CAPABILITY_LABELS[value];
  return "未知类型";
}

function jsonRecord(value: Record<string, unknown> | undefined): Record<string, unknown> {
  return value && typeof value === "object" ? value : {};
}

function nestedRecordValue(value: unknown, keys: string[]): unknown {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const record = value as Record<string, unknown>;
    for (const key of Object.keys(record)) {
      if (keys.includes(key.toLowerCase())) return record[key];
    }
    for (const item of Object.values(record)) {
      const nested = nestedRecordValue(item, keys);
      if (nested !== undefined && nested !== "") return nested;
    }
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      const nested = nestedRecordValue(item, keys);
      if (nested !== undefined && nested !== "") return nested;
    }
  }
  return undefined;
}

function adminRecordParam(record: AdminCreationRecord, keys: string[], fallback = "-"): string {
  const value = nestedRecordValue(record.requestParams || {}, keys.map((key) => key.toLowerCase()));
  if (value === undefined || value === null || value === "") return fallback;
  return String(value);
}

function adminRecordReferenceCount(record: AdminCreationRecord): number {
  const params = jsonRecord(record.requestParams);
  const candidates = [
    params.images,
    params.image,
    params.referenceImages,
    params.reference_images,
    params.attachments,
    params.firstFrame,
    params.lastFrame,
  ];
  return candidates.reduce<number>((sum, item) => {
    if (Array.isArray(item)) return sum + item.filter(Boolean).length;
    return item ? sum + 1 : sum;
  }, 0);
}

function adminRecordTimeline(record: AdminCreationRecord): Array<{ label: string; value: string; tone: string }> {
  const rows = [
    { label: "请求创建", value: formatConversationTime(record.createdAt), tone: "normal" },
    {
      label: record.taskId ? "任务 ID" : "处理阶段",
      value: record.taskId || "同步请求",
      tone: record.taskId ? "info" : "normal",
    },
  ];
  if (record.durationMs) rows.push({ label: "服务耗时", value: formatAdminDuration(record.durationMs), tone: "normal" });
  rows.push({
    label: adminStatusLabel(record.status),
    value: record.errorMessage || adminRecordResponse(record),
    tone: record.status === "error" ? "danger" : record.status === "success" ? "success" : "warn",
  });
  return rows;
}

function adminDefaultParameterRows(model: ModelDefinition): Array<{ key: string; value: string }> {
  const draft = adminState.modelDrafts[model.id];
  if (!draft?.defaultParametersText.trim()) return [];
  try {
    const parsed = JSON.parse(draft.defaultParametersText) as Record<string, unknown>;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return [];
    return Object.entries(parsed).map(([key, value]) => ({
      key,
      value: typeof value === "string" ? value : JSON.stringify(value),
    }));
  } catch {
    return [];
  }
}

function setAdminDefaultParameter(model: ModelDefinition, key: string, value: string) {
  const draft = adminState.modelDrafts[model.id];
  if (!draft) return;
  let parsed: Record<string, unknown> = {};
  try {
    parsed = JSON.parse(draft.defaultParametersText || "{}") as Record<string, unknown>;
  } catch {
    parsed = {};
  }
  const trimmed = value.trim();
  if (!trimmed) delete parsed[key];
  else if (trimmed === "true" || trimmed === "false") parsed[key] = trimmed === "true";
  else if (!Number.isNaN(Number(trimmed)) && trimmed !== "") parsed[key] = Number(trimmed);
  else {
    try {
      parsed[key] = JSON.parse(trimmed);
    } catch {
      parsed[key] = value;
    }
  }
  draft.defaultParametersText = JSON.stringify(parsed, null, 2);
}

function setAdminDefaultParameterFromEvent(model: ModelDefinition, key: string, event: Event) {
  const target = event.target;
  setAdminDefaultParameter(model, key, target instanceof HTMLInputElement ? target.value : "");
}

function addAdminDefaultParameter(model: ModelDefinition) {
  const draft = adminState.modelDrafts[model.id];
  if (!draft) return;
  let parsed: Record<string, unknown> = {};
  try {
    parsed = JSON.parse(draft.defaultParametersText || "{}") as Record<string, unknown>;
  } catch {
    parsed = {};
  }
  const base = "param";
  let index = 1;
  while (`${base}${index}` in parsed) index += 1;
  parsed[`${base}${index}`] = "";
  draft.defaultParametersText = JSON.stringify(parsed, null, 2);
}

function adminIconError(model: ModelDefinition): string {
  return adminState.modelIconErrors[model.id] || "";
}

function markAdminIconFailed(model: ModelDefinition, event: Event) {
  hideBrokenModelIcon(event);
  adminState.modelIconErrors[model.id] = "图标加载失败，请检查 URL 或跨域访问。";
}

function clearAdminIconError(model: ModelDefinition) {
  delete adminState.modelIconErrors[model.id];
}

function toggleAdminModelSelection(modelId: string) {
  if (adminState.selectedModelIds.includes(modelId)) {
    adminState.selectedModelIds = adminState.selectedModelIds.filter((id) => id !== modelId);
  } else {
    adminState.selectedModelIds = [...adminState.selectedModelIds, modelId];
  }
}

function toggleAdminSelectAllModels() {
  adminState.selectedModelIds = adminAllVisibleModelsSelected.value ? [] : [...adminVisibleModelIds.value];
}

function adminApplyFailedModelFilter(row: { modelGroupId: string; capability: Capability | "" }) {
  adminState.recordModelGroupId = row.modelGroupId;
  if (row.capability === "image" || row.capability === "video" || row.capability === "text") {
    switchAdminRecordCapability(row.capability);
  }
}

async function bulkSetAdminPublicState(isPublic: boolean) {
  const targets = adminSelectedModels.value.filter((model) => model.isPublic !== isPublic);
  if (!targets.length) {
    showToast("没有需要变更的模型", "info");
    return;
  }
  if (!window.confirm(`确认批量${isPublic ? "设为公用" : "取消公用"} ${targets.length} 个模型吗？`)) return;
  adminState.saving = "bulk-public";
  adminState.error = "";
  try {
    for (const model of targets) {
      const updated = isPublic ? await publishAdminModel(model.id) : await unpublishAdminModel(model.id);
      const nextModel = mapServerModel(updated);
      const index = adminState.models.findIndex((item) => item.id === model.id);
      if (index >= 0) adminState.models[index] = nextModel;
      delete adminState.modelDrafts[model.id];
      ensureAdminModelDraft(nextModel);
    }
    await refreshServerModels();
    showToast(`已更新 ${targets.length} 个模型`, "success");
  } catch (error) {
    adminState.error = adminSaveError(error, "批量更新公用状态失败。");
    showToast(adminState.error, "error");
  } finally {
    adminState.saving = "";
  }
}

async function bulkSetAdminPromptOptimize(enabled: boolean) {
  const targets = adminSelectedModels.value.filter((model) => (model.promptOptimizeEnabled !== false) !== enabled);
  if (!targets.length) {
    showToast("没有需要变更的模型", "info");
    return;
  }
  adminState.saving = "bulk-prompt";
  adminState.error = "";
  try {
    for (const model of targets) {
      const updated = await updateAdminModel(model.id, { promptOptimizeEnabled: enabled });
      const nextModel = mapServerModel(updated);
      const index = adminState.models.findIndex((item) => item.id === model.id);
      if (index >= 0) adminState.models[index] = nextModel;
      delete adminState.modelDrafts[model.id];
      ensureAdminModelDraft(nextModel);
    }
    showToast(`已${enabled ? "启用" : "禁用"} ${targets.length} 个模型的 AI 文案优化`, "success");
  } catch (error) {
    adminState.error = adminSaveError(error, "批量更新提示优化失败。");
    showToast(adminState.error, "error");
  } finally {
    adminState.saving = "";
  }
}

function csvEscape(value: unknown): string {
  const text = String(value ?? "");
  return `"${text.replace(/"/g, '""')}"`;
}

function downloadCsv(filename: string, rows: unknown[][]) {
  const csv = rows.map((row) => row.map(csvEscape).join(",")).join("\n");
  const blob = new Blob([`\ufeff${csv}`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function exportAdminUsers() {
  downloadCsv("genstudio-users.csv", [
    ["ID", "邮箱", "昵称", "角色", "状态", "会话数", "最近活跃", "最近登录 IP"],
    ...adminFilteredUsers.value.map((user) => [
      user.id,
      user.email,
      user.nickname,
      user.isAdmin ? "管理员" : "用户",
      user.status,
      user.sessionCount || 0,
      user.lastSeenAt || "",
      user.recentLoginIp || "未记录",
    ]),
  ]);
}

function exportAdminAuditLogs() {
  downloadCsv("genstudio-audit-logs.csv", [
    ["时间", "动作", "目标类型", "目标 ID", "风险", "状态", "摘要"],
    ...adminState.auditLogs.map((log) => [
      log.createdAt,
      log.action,
      log.targetType,
      log.targetId,
      adminRiskLabel(log.riskLevel),
      log.status,
      compactJson(log.summary || {}),
    ]),
  ]);
}

async function copyAdminText(value: string, label = "内容") {
  try {
    await navigator.clipboard.writeText(value);
    showToast(`${label}已复制`, "success");
  } catch {
    showToast("复制失败，请手动复制。", "error");
  }
}

function currentAdminRecordFilters(): Record<string, string> {
  return {
    status: adminState.recordStatus,
    userSearch: adminState.recordUserSearch,
    modelGroupId: adminState.recordModelGroupId,
    keyword: adminState.recordKeyword,
    size: adminState.recordSize,
    ratio: adminState.recordRatio,
    refCount: adminState.recordRefCount,
    duration: adminState.recordDuration,
    resolution: adminState.recordResolution,
    mode: adminState.recordMode,
  };
}

function applyAdminRecordFilters(filters: Record<string, string>) {
  adminState.recordStatus = filters.status || "";
  adminState.recordUserSearch = filters.userSearch || "";
  adminState.recordModelGroupId = filters.modelGroupId || "";
  adminState.recordKeyword = filters.keyword || "";
  adminState.recordSize = filters.size || "";
  adminState.recordRatio = filters.ratio || "";
  adminState.recordRefCount = filters.refCount || "";
  adminState.recordDuration = filters.duration || "";
  adminState.recordResolution = filters.resolution || "";
  adminState.recordMode = filters.mode || "";
  void loadAdminRecords(capabilityForAdminRecordTab(adminState.activeTab));
}

function saveAdminRecordFilter() {
  const capability = capabilityForAdminRecordTab(adminState.activeTab);
  const filled = Object.entries(currentAdminRecordFilters()).filter(([, value]) => value);
  if (!filled.length) {
    showToast("请先设置筛选条件", "info");
    return;
  }
  const name = `${CAPABILITY_LABELS[capability]}筛选 ${adminState.recordKeyword || adminState.recordStatus || filled[0][1]}`;
  adminState.recordSavedFilters.unshift({
    id: createLocalId("admin-filter"),
    name,
    capability,
    filters: currentAdminRecordFilters(),
  });
  adminState.recordSavedFilters = adminState.recordSavedFilters.slice(0, 8);
  showToast("常用筛选已保存", "success");
}

function clearAdminRecordFilters() {
  adminState.recordStatus = "";
  adminState.recordUserSearch = "";
  adminState.recordModelGroupId = "";
  adminState.recordKeyword = "";
  adminState.recordSize = "";
  adminState.recordRatio = "";
  adminState.recordRefCount = "";
  adminState.recordDuration = "";
  adminState.recordResolution = "";
  adminState.recordMode = "";
  void loadAdminRecords(capabilityForAdminRecordTab(adminState.activeTab));
}

function openAdminRecordDetail(record: AdminCreationRecord) {
  adminState.selectedRecordId = record.id;
}

function closeAdminRecordDetail() {
  adminState.selectedRecordId = "";
}

function adminRecordMarkdownHtml(record: AdminCreationRecord): string {
  return markdownPreview(adminRecordResponse(record));
}

function adminRecordIsMarkdownCapable(record: AdminCreationRecord): boolean {
  return record.capability === "text" && adminState.recordMarkdownPreview && Boolean(adminRecordResponse(record).trim());
}

function formatConversationTime(value: string): string {
  const time = new Date(value);
  if (Number.isNaN(time.getTime())) return "";
  return time.toLocaleString("zh-CN", { hour12: false });
}

function uploadedAssetAsConversationAsset(asset: UploadedAsset, role = "reference", label = "参考图") {
  const capability = (activeCapability.value || "image") as Capability;
  return {
    id: asset.id || createLocalId("local-asset"),
    capability,
    assetType: "image",
    url: asset.localPreviewUrl || asset.publicUrl,
    thumbnailUrl: asset.localPreviewUrl || asset.publicUrl,
    metadata: {
      role,
      label,
      source: "input",
      fileName: asset.fileName,
      publicUrl: asset.publicUrl,
    },
    createdAt: new Date().toISOString(),
  } satisfies ConversationAsset;
}

function uploadedAssetsAsConversationAssets(assets: UploadedAsset[], role = "reference", label = "参考图"): ConversationAsset[] {
  return assets.map((asset) => uploadedAssetAsConversationAsset(asset, role, label));
}

function currentImageReferenceAssets(): ConversationAsset[] {
  return uploadedAssetsAsConversationAssets(imageState.references, "reference", "参考图");
}

function currentVideoReferenceAssets(): ConversationAsset[] {
  const assets: ConversationAsset[] = [];
  if (supportsUnifiedAdapter(activeModel.value?.adapter)) {
    assets.push(...uploadedAssetsAsConversationAssets(videoState.unifiedImages, "reference", "参考图"));
  }
  if (activeModel.value?.adapter === "video-seedance") {
    assets.push(...uploadedAssetsAsConversationAssets(videoState.seedanceReferences, "reference", "参考图"));
    if (videoState.seedanceFirst) assets.push(uploadedAssetAsConversationAsset(videoState.seedanceFirst, "first_frame", "首帧"));
    if (videoState.seedanceLast) assets.push(uploadedAssetAsConversationAsset(videoState.seedanceLast, "last_frame", "尾帧"));
  }
  return assets;
}

function assetDisplayLabel(asset: ConversationAsset, message?: ConversationMessage): string {
  const label = asset.metadata?.label;
  if (typeof label === "string" && label.trim()) return label;
  const role = typeof asset.metadata?.role === "string" ? asset.metadata.role : "";
  if (role === "first_frame") return "首帧";
  if (role === "last_frame") return "尾帧";
  if (role === "mask") return "蒙版";
  if (asset.metadata?.source === "input" || message?.role === "user") return "参考图";
  return asset.assetType === "video" ? "视频结果" : "图片结果";
}

function resetMediaPreviewTransform() {
  mediaPreviewState.scale = 1;
  mediaPreviewState.offsetX = 0;
  mediaPreviewState.offsetY = 0;
  mediaPreviewState.dragging = false;
}

function openMediaPreview(asset: ConversationAsset) {
  mediaPreviewState.asset = asset;
  resetMediaPreviewTransform();
  document.documentElement.classList.add("media-preview-open");
}

function openUploadedMediaPreview(asset: UploadedAsset, role = "reference", label = "参考图") {
  openMediaPreview(uploadedAssetAsConversationAsset(asset, role, label));
}

function closeMediaPreview() {
  mediaPreviewState.asset = null;
  resetMediaPreviewTransform();
  document.documentElement.classList.remove("media-preview-open");
}

function mediaPreviewTransform(): string {
  return `translate(${mediaPreviewState.offsetX}px, ${mediaPreviewState.offsetY}px) scale(${mediaPreviewState.scale})`;
}

function zoomMediaPreview(delta: number) {
  const next = nextMediaPreviewTransform(mediaPreviewState, delta);
  mediaPreviewState.scale = next.scale;
  mediaPreviewState.offsetX = next.offsetX;
  mediaPreviewState.offsetY = next.offsetY;
}

function handleMediaPreviewWheel(event: WheelEvent) {
  if (mediaPreviewState.asset?.assetType !== "image") return;
  const direction = event.deltaY > 0 ? -0.16 : 0.16;
  zoomMediaPreview(direction);
}

function startMediaPreviewPan(event: PointerEvent) {
  if (mediaPreviewState.asset?.assetType !== "image") return;
  mediaPreviewState.dragging = true;
  mediaPreviewState.dragStartX = event.clientX;
  mediaPreviewState.dragStartY = event.clientY;
  mediaPreviewState.dragOriginX = mediaPreviewState.offsetX;
  mediaPreviewState.dragOriginY = mediaPreviewState.offsetY;
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
}

function moveMediaPreviewPan(event: PointerEvent) {
  if (!mediaPreviewState.dragging) return;
  mediaPreviewState.offsetX = mediaPreviewState.dragOriginX + event.clientX - mediaPreviewState.dragStartX;
  mediaPreviewState.offsetY = mediaPreviewState.dragOriginY + event.clientY - mediaPreviewState.dragStartY;
}

function stopMediaPreviewPan(event?: PointerEvent) {
  if (event?.currentTarget instanceof HTMLElement && event.pointerId) {
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      // Pointer capture may already be released by the browser.
    }
  }
  mediaPreviewState.dragging = false;
}

function useGeneratedAsset(asset: ConversationAsset) {
  const reference: UploadedAsset = {
    id: asset.id,
    fileName: generatedAssetReferenceFileName(asset),
    publicUrl: asset.url,
    contentType: asset.assetType === "video" ? "video/mp4" : "image/png",
    localPreviewUrl: asset.thumbnailUrl || asset.url,
  };
  if (asset.assetType === "image") {
    imageState.references = [reference, ...imageState.references].slice(0, 14);
    imageState.prompt = imageState.prompt.trim()
      ? imageState.prompt
      : "请基于引用图片继续编辑，保持主体一致，输出一个新的创意版本。";
    navigate("images");
  }
}

function editSelectedAsset(asset: ConversationAsset) {
  useGeneratedAsset(asset);
  imageState.prompt = "请基于当前选中的图片局部或主体继续编辑，保留关键构图，输出一个新的创意版本。";
  closeMediaPreview();
}

async function retryMessage(message: ConversationMessage) {
  const prompt = findPromptBeforeMessage(currentMessages.value, message.id);
  if (!prompt) return;
  if (message.capability === "text") {
    textState.prompt = prompt;
    navigate("text");
    await handleTextSubmit();
  }
  if (message.capability === "image") {
    imageState.prompt = prompt;
    navigate("images");
    await handleImageSubmit();
  }
  if (message.capability === "video") {
    videoState.prompt = prompt;
    navigate("videos");
    await handleVideoCreate();
  }
}

function taskIdFromConversation(): string {
  const processing = [...currentMessages.value].reverse().find(
    (message) => message.capability === "video" && message.status === "processing" && message.content.trim(),
  );
  return processing?.content.trim() || videoState.createResult?.taskId || "";
}

function textTaskIdFromConversation(): string {
  const processing = [...currentMessages.value].reverse().find(
    (message) => message.capability === "text" && message.status === "processing" && message.content.trim(),
  );
  return processing?.content.trim() || textState.result?.taskId || "";
}

function imageTaskIdFromConversation(): string {
  const processing = [...currentMessages.value].reverse().find(
    (message) => message.capability === "image" && message.status === "processing" && message.content.trim(),
  );
  return processing?.content.trim() || imageState.result?.taskId || "";
}

function simulateStreamingPreview(message?: ConversationMessage) {
  if (!message?.content) return;
  conversationState.streamingMessageId = message.id;
  conversationState.streamingContent = "";
  const content = message.content;
  let index = 0;
  const step = Math.max(1, Math.ceil(content.length / 36));
  const timer = window.setInterval(() => {
    index = Math.min(content.length, index + step);
    conversationState.streamingContent = content.slice(0, index);
    if (index >= content.length) {
      window.clearInterval(timer);
      window.setTimeout(() => {
        if (conversationState.streamingMessageId === message.id) {
          conversationState.streamingMessageId = "";
          conversationState.streamingContent = "";
        }
      }, 160);
    }
  }, 24);
}

async function initializeSession() {
  await auth.loadCurrentUser();
  await refreshServerModels();
  if (auth.state.user) {
    await refreshConversations();
  }
}

async function refreshServerModels() {
  const models = await fetchServerModels();
  store.applyServerModels(models);
}

function mapServerModel(item: ServerModelDefinition): ModelDefinition {
  return {
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
  };
}

function ensureAdminModelDraft(model: ModelDefinition) {
  if (adminState.modelDrafts[model.id]) return;
  adminState.modelDrafts[model.id] = {
    publicDisplayName: model.publicDisplayName || modelDisplayName(model),
    publicDescription: model.publicDescription || model.description || "",
    inputHint: model.inputHint || modelCatalogInputHint(model, ""),
    iconUrl: model.iconUrl || modelIconUrl(model),
    publicTagsText: (model.publicTags || []).join(", "),
    promptOptimizeEnabled: model.promptOptimizeEnabled !== false,
    defaultParametersText: JSON.stringify(model.defaultParameters || {}, null, 2),
  };
}

function syncAdminModelDrafts() {
  adminState.models.forEach(ensureAdminModelDraft);
}

function adminRecordList(tab: AdminTab): AdminCreationRecord[] {
  if (tab === "text-records") return adminState.textRecords;
  if (tab === "image-records") return adminState.imageRecords;
  if (tab === "video-records") return adminState.videoRecords;
  return [];
}

function capabilityForAdminRecordTab(tab: AdminTab): Capability {
  return ADMIN_RECORD_CAPABILITY_BY_TAB[tab] || "text";
}

function adminRecordTabForCapability(capability: Capability): AdminTab {
  if (capability === "image") return "image-records";
  if (capability === "video") return "video-records";
  return "text-records";
}

function switchAdminRecordCapability(capability: Capability) {
  switchAdminTab(adminRecordTabForCapability(capability));
}

function adminRecordTitle(tab: AdminTab): string {
  if (tab === "image-records") return "生图记录";
  if (tab === "video-records") return "视频记录";
  return "文案记录";
}

function adminStatusLabel(status: string): string {
  if (status === "active") return "启用";
  if (status === "disabled") return "禁用";
  if (status === "deleted") return "已删除";
  if (status === "success") return "成功";
  if (status === "error") return "失败";
  if (status === "processing") return "处理中";
  return status || "-";
}

function adminStatusBadge(status: string): string {
  if (status === "active" || status === "success") return "badge-success";
  if (status === "error" || status === "deleted") return "badge-danger";
  return "badge-warn";
}

function adminUserLabel(user: AdminUserDefinition | null | undefined): string {
  if (!user) return "未知用户";
  return user.nickname || user.email || user.id;
}

function adminRecordPrompt(record: AdminCreationRecord): string {
  const requestPrompt =
    typeof record.requestParams?.prompt === "string"
      ? record.requestParams.prompt
      : typeof record.requestParams?.content === "string"
        ? record.requestParams.content
        : "";
  return record.prompt || requestPrompt || "-";
}

function adminRecordResponse(record: AdminCreationRecord): string {
  if (record.response) return record.response;
  if (record.errorMessage) return record.errorMessage;
  const assetCount = record.assets?.length || 0;
  if (assetCount) return `已返回 ${assetCount} 个${record.capability === "video" ? "视频" : "图片"}结果`;
  if (record.taskId) return `任务 ${record.taskId}`;
  return record.status === "processing" ? "结果生成中" : "-";
}

function adminRecordMediaAssets(record: AdminCreationRecord): Array<{ type: string; url: string; thumbnailUrl?: string }> {
  return (record.assets || []).filter((asset) => asset.url);
}

function markAdminRecordAssetBroken(event: Event) {
  const target = event.currentTarget as HTMLElement | null;
  target?.closest(".admin-record-asset")?.classList.add("admin-record-asset-broken");
}

function adminRecordJsonInitiallyOpen(record: AdminCreationRecord): boolean {
  void record;
  return false;
}

function editAdminModel(model: ModelDefinition) {
  ensureAdminModelDraft(model);
  adminState.editingModelId = adminState.editingModelId === model.id ? "" : model.id;
}

function cancelAdminModelEdit(model: ModelDefinition) {
  delete adminState.modelDrafts[model.id];
  ensureAdminModelDraft(model);
  adminState.editingModelId = "";
}

function editAdminUser(user: AdminUserDefinition) {
  adminState.editingUserId = adminState.editingUserId === user.id ? "" : user.id;
}

function adminSaveError(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

async function loadAdminOverview() {
  if (!auth.state.user?.isAdmin) return;
  adminState.loading = true;
  adminState.error = "";
  try {
    const [overview, users, models] = await Promise.all([
      fetchAdminOverview(),
      fetchAdminOverviewUsers(),
      fetchAdminOverviewModels(),
    ]);
    adminState.overview = overview;
    adminState.overviewUsers = users;
    adminState.overviewModels = models;
  } catch (error) {
    adminState.error = adminSaveError(error, "加载运营面板失败。");
  } finally {
    adminState.loading = false;
  }
}

async function loadAdminModels() {
  if (!auth.state.user?.isAdmin) return;
  adminState.loading = true;
  adminState.error = "";
  try {
    const models = await fetchAdminModels({
      capability: adminState.modelCapability,
      search: adminState.modelSearch,
      publicState: adminState.modelPublicState,
    });
    adminState.models = models.map(mapServerModel);
    adminState.selectedModelIds = adminState.selectedModelIds.filter((id) => adminState.models.some((model) => model.id === id));
    syncAdminModelDrafts();
  } catch (error) {
    adminState.error = adminSaveError(error, "加载公用模型配置失败。");
  } finally {
    adminState.loading = false;
  }
}

async function saveAdminModel(model: ModelDefinition) {
  const draft = adminState.modelDrafts[model.id];
  if (!draft) return;
  adminState.saving = model.id;
  adminState.error = "";
  try {
    const parameters = draft.defaultParametersText.trim() ? JSON.parse(draft.defaultParametersText) : {};
    const updated = await updateAdminModel(model.id, {
      publicDisplayName: draft.publicDisplayName,
      publicDescription: draft.publicDescription,
      inputHint: draft.inputHint,
      iconUrl: draft.iconUrl,
      publicTags: draft.publicTagsText
        .split(/[,，]/)
        .map((item) => item.trim())
        .filter(Boolean),
      promptOptimizeEnabled: draft.promptOptimizeEnabled,
      defaultParameters: parameters,
    });
    const nextModel = mapServerModel(updated);
    const index = adminState.models.findIndex((item) => item.id === model.id);
    if (index >= 0) adminState.models[index] = nextModel;
    delete adminState.modelDrafts[model.id];
    ensureAdminModelDraft(nextModel);
    adminState.editingModelId = "";
    await refreshServerModels();
    showToast("后台模型配置已保存", "success");
  } catch (error) {
    adminState.error = adminSaveError(error, "保存模型配置失败。");
    showToast(adminState.error, "error");
  } finally {
    adminState.saving = "";
  }
}

async function toggleAdminPublicModel(model: ModelDefinition) {
  if (model.isPublic && !window.confirm(`确认取消公用模型「${modelDisplayName(model)}」吗？`)) return;
  adminState.saving = `${model.id}:public`;
  adminState.error = "";
  try {
    const updated = model.isPublic ? await unpublishAdminModel(model.id) : await publishAdminModel(model.id);
    const nextModel = mapServerModel(updated);
    const index = adminState.models.findIndex((item) => item.id === model.id);
    if (index >= 0) adminState.models[index] = nextModel;
    delete adminState.modelDrafts[model.id];
    ensureAdminModelDraft(nextModel);
    adminState.editingModelId = "";
    await refreshServerModels();
    showToast(nextModel.isPublic ? "已设为公用模型" : "已取消公用模型", "success");
  } catch (error) {
    adminState.error = adminSaveError(error, "切换公用模型失败。");
    showToast(adminState.error, "error");
  } finally {
    adminState.saving = "";
  }
}

async function loadPromptTemplates() {
  if (!auth.state.user?.isAdmin) return;
  adminState.loading = true;
  adminState.error = "";
  try {
    adminState.templates = await fetchPromptTemplates("all");
    const selected = adminState.templates.find(
      (item) =>
        item.capability === adminState.templateDraft.capability &&
        item.modelGroupId === adminState.templateDraft.modelGroupId &&
        item.templateType === "prompt_optimize",
    );
    if (selected) {
      adminState.templateDraft.id = selected.id;
      adminState.templateDraft.name = selected.name;
      adminState.templateDraft.content = selected.content;
      adminState.templateDraft.enabled = selected.enabled;
    }
  } catch (error) {
    adminState.error = adminSaveError(error, "加载提示语模板失败。");
  } finally {
    adminState.loading = false;
  }
}

function selectPromptTemplateDraft() {
  const selected = adminState.templates.find(
    (item) =>
      item.capability === adminState.templateDraft.capability &&
      item.modelGroupId === adminState.templateDraft.modelGroupId &&
      item.templateType === "prompt_optimize",
  );
  adminState.templateDraft.id = selected?.id || "";
  adminState.templateDraft.name = selected?.name || "提示词优化模板";
  adminState.templateDraft.content =
    selected?.content || "请将下面的用户提示词优化为更清晰、可执行、细节完整的创作提示词：\n\n{{prompt}}";
  adminState.templateDraft.enabled = selected?.enabled ?? true;
  adminState.templateDraft.preview = "";
}

async function savePromptTemplate() {
  adminState.saving = "prompt-template";
  adminState.error = "";
  try {
    const previous = adminState.templates.find((item) => item.id === adminState.templateDraft.id);
    const template = await saveAdminPromptTemplateApi(adminState.templateDraft.id || "new", {
      capability: adminState.templateDraft.capability,
      modelGroupId: adminState.templateDraft.modelGroupId,
      templateType: "prompt_optimize",
      name: adminState.templateDraft.name,
      content: adminState.templateDraft.content,
      enabled: adminState.templateDraft.enabled,
    });
    if (previous) {
      adminState.templateHistory.unshift({
        id: createLocalId("admin-template-history"),
        templateId: previous.id,
        name: previous.name,
        capability: previous.capability,
        modelGroupId: previous.modelGroupId,
        content: previous.content,
        enabled: previous.enabled,
        savedAt: new Date().toISOString(),
      });
      adminState.templateHistory = adminState.templateHistory.slice(0, 20);
    }
    const index = adminState.templates.findIndex((item) => item.id === template.id);
    if (index >= 0) adminState.templates[index] = template;
    else adminState.templates.unshift(template);
    adminState.templateDraft.id = template.id;
    showToast("提示语模板已保存", "success");
  } catch (error) {
    adminState.error = adminSaveError(error, "保存提示语模板失败。");
    showToast(adminState.error, "error");
  } finally {
    adminState.saving = "";
  }
}

async function testAdminPromptTemplate() {
  adminState.saving = "prompt-preview";
  adminState.error = "";
  try {
    const samples = adminState.templateDraft.testSamplesText
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean)
      .slice(0, 5);
    const inputs = samples.length ? samples : [adminState.templateDraft.testPrompt];
    const previews = [];
    for (const prompt of inputs) {
      const result = await testAdminPromptTemplateApi({
        capability: adminState.templateDraft.capability,
        content: adminState.templateDraft.content,
        prompt,
      });
      previews.push({ input: prompt, output: result.prompt });
    }
    adminState.templateDraft.previews = previews;
    adminState.templateDraft.preview = previews[0]?.output || "";
  } catch (error) {
    adminState.error = adminSaveError(error, "测试提示语模板失败。");
  } finally {
    adminState.saving = "";
  }
}

async function loadAdminUsers() {
  if (!auth.state.user?.isAdmin) return;
  adminState.loading = true;
  adminState.error = "";
  try {
    adminState.users = await fetchAdminUsers(adminState.userSearch);
    if (adminState.selectedUserId && !adminState.users.some((user) => user.id === adminState.selectedUserId)) {
      adminState.selectedUserId = "";
    }
  } catch (error) {
    adminState.error = adminSaveError(error, "加载用户列表失败。");
  } finally {
    adminState.loading = false;
  }
}

async function saveAdminUser(user: AdminUserDefinition) {
  adminState.saving = user.id;
  adminState.error = "";
  try {
    const updated = await updateAdminUser(user.id, {
      email: user.email,
      phone: user.phone,
      nickname: user.nickname,
      avatarUrl: user.avatarUrl,
      status: user.status,
    });
    const index = adminState.users.findIndex((item) => item.id === user.id);
    if (index >= 0) adminState.users[index] = updated;
    adminState.editingUserId = "";
    showToast("用户信息已保存", "success");
  } catch (error) {
    adminState.error = adminSaveError(error, "保存用户失败。");
    showToast(adminState.error, "error");
  } finally {
    adminState.saving = "";
  }
}

async function setAdminUserStatus(user: AdminUserDefinition, action: "enable" | "disable" | "delete" | "restore") {
  const riskyAction = action === "disable" || action === "delete";
  if (riskyAction && !window.confirm(`确认${action === "delete" ? "删除" : "禁用"}用户「${adminUserLabel(user)}」吗？`)) return;
  adminState.saving = `${user.id}:${action}`;
  adminState.error = "";
  try {
    const updated =
      action === "enable"
        ? await enableAdminUser(user.id)
        : action === "disable"
          ? await disableAdminUser(user.id)
          : action === "delete"
            ? await deleteAdminUser(user.id)
            : await restoreAdminUser(user.id);
    const index = adminState.users.findIndex((item) => item.id === user.id);
    if (index >= 0) adminState.users[index] = updated;
    showToast("用户状态已更新", "success");
  } catch (error) {
    adminState.error = adminSaveError(error, "更新用户状态失败。");
    showToast(adminState.error, "error");
  } finally {
    adminState.saving = "";
  }
}

async function loadAdminRecords(capability: Capability) {
  if (!auth.state.user?.isAdmin) return;
  adminState.loading = true;
  adminState.error = "";
  try {
    const records = await fetchAdminRecords(capability, {
      userSearch: adminState.recordUserSearch,
      modelGroupId: adminState.recordModelGroupId,
      status: adminState.recordStatus,
      keyword: adminState.recordKeyword,
      size: adminState.recordSize,
      ratio: adminState.recordRatio,
      refCount: adminState.recordRefCount,
      duration: adminState.recordDuration,
      resolution: adminState.recordResolution,
      mode: adminState.recordMode,
    });
    if (capability === "text") adminState.textRecords = records;
    if (capability === "image") adminState.imageRecords = records;
    if (capability === "video") adminState.videoRecords = records;
  } catch (error) {
    adminState.error = adminSaveError(error, "加载创作记录失败。");
  } finally {
    adminState.loading = false;
  }
}

async function loadAdminAuditLogs() {
  if (!auth.state.user?.isAdmin) return;
  adminState.loading = true;
  adminState.error = "";
  try {
    adminState.auditLogs = await fetchAdminAuditLogs({
      action: adminState.auditAction,
      adminUserId: adminState.auditAdminUserId,
      targetType: adminState.auditTargetType,
      targetId: adminState.auditTargetId,
      risk: adminState.auditRisk,
    });
  } catch (error) {
    adminState.error = adminSaveError(error, "加载操作记录失败。");
  } finally {
    adminState.loading = false;
  }
}

async function loadAdminTab(tab: AdminTab = adminState.activeTab) {
  if (!auth.state.user?.isAdmin) return;
  if (tab === "overview") await loadAdminOverview();
  if (tab === "models") await loadAdminModels();
  if (tab === "prompts") await loadPromptTemplates();
  if (tab === "users") await loadAdminUsers();
  if (tab === "text-records") await loadAdminRecords("text");
  if (tab === "image-records") await loadAdminRecords("image");
  if (tab === "video-records") await loadAdminRecords("video");
  if (tab === "audit") await loadAdminAuditLogs();
}

function scrollAdminConsoleToTop() {
  window.requestAnimationFrame(() => {
    document.querySelector(".admin-console-main")?.scrollTo({ top: 0, behavior: "auto" });
  });
}

function switchAdminTab(tab: AdminTab) {
  adminState.activeTab = tab;
  scrollAdminConsoleToTop();
  void loadAdminTab(tab);
}

async function refreshUserWorkspace() {
  await refreshServerModels();
  if (auth.state.user) {
    await refreshConversations();
  }
  syncInitialModels();
}

async function clearUserWorkspace() {
  await refreshServerModels();
  conversationState.conversations = [];
  conversationState.current = null;
  conversationState.streamingMessageId = "";
  conversationState.streamingContent = "";
}

async function handleDevLogin() {
  authForm.error = "";
  try {
    await auth.loginForDevelopment();
    await refreshUserWorkspace();
    syncProfileForm();
    navigate(resolveAuthRedirect(window.location.hash) as ViewName);
  } catch (error) {
    authForm.error = error instanceof Error ? error.message : "开发登录失败。";
  }
}

function handleAuthCodeLogin() {
  const code = devAuthCode.value.trim();
  if (!code) return;
  const nextRoute = resolveAuthRedirect(window.location.hash);
  window.location.href = `/auth/callback?code=${encodeURIComponent(code)}&next=${encodeURIComponent(`/#/${nextRoute}`)}`;
}

function syncProfileForm() {
  profileForm.nickname = auth.state.user?.nickname || "";
  profileForm.phone = auth.state.user?.phone || "";
  profileForm.avatarUrl = auth.state.user?.avatarUrl || "";
  profileForm.error = "";
  profileForm.success = "";
}

async function handlePasswordLogin() {
  authForm.error = "";
  try {
    await auth.login({
      identifier: authForm.identifier,
      password: authForm.password,
    });
    await refreshUserWorkspace();
    syncProfileForm();
    navigate(resolveAuthRedirect(window.location.hash) as ViewName);
  } catch (error) {
    authForm.error = error instanceof Error ? error.message : "登录失败。";
  }
}

async function handleRegister() {
  authForm.error = "";
  try {
    await auth.registerWithPassword({
      email: authForm.email,
      phone: authForm.phone,
      password: authForm.registerPassword,
      nickname: authForm.nickname,
    });
    authForm.password = "";
    authForm.registerPassword = "";
    await refreshUserWorkspace();
    syncProfileForm();
    navigate(resolveAuthRedirect(window.location.hash) as ViewName);
  } catch (error) {
    authForm.error = error instanceof Error ? error.message : "注册失败。";
  }
}

async function handleLogout() {
  try {
    await auth.logoutCurrentUser();
    await clearUserWorkspace();
    navigate("images");
  } catch (error) {
    profileForm.error = error instanceof Error ? error.message : "退出登录失败。";
  }
}

async function handleProfileSave() {
  profileForm.error = "";
  profileForm.success = "";
  try {
    await auth.updateProfile({
      nickname: profileForm.nickname,
      phone: profileForm.phone,
      avatarUrl: profileForm.avatarUrl,
    });
    profileForm.success = "个人信息已保存。";
    showToast("Profile saved");
  } catch (error) {
    profileForm.error = error instanceof Error ? error.message : "保存个人信息失败。";
    showToast(profileForm.error, "error");
  }
}

function getSetting(modelId: string): ModelSetting {
  return (
    store.state.modelSettings[modelId] || {
      baseUrl: "",
      apiKey: "",
      modelNameOverride: "",
      availableModels: [],
    }
  );
}

function getModelHref(model: ModelDefinition): ViewName {
  if (model.capability === "image") return "images";
  if (model.capability === "video") return "videos";
  return "text";
}

function selectModel(model: ModelDefinition) {
  if (shouldResetConversationForModelSwitch(conversationState.current, {
    capability: model.capability,
    modelGroupId: model.id,
    subModelId: model.primarySubModelId || null,
  })) {
    startNewConversation(getModelHref(model));
  }
  if (model.capability === "text") textModelId.value = model.id;
  if (model.capability === "image") imageModelId.value = model.id;
  if (model.capability === "video") videoModelId.value = model.id;
  navigate(getModelHref(model));
}

function activeModelIdForSidebar(): string {
  if (view.value === "text") return textModelId.value;
  if (view.value === "images") return imageModelId.value;
  if (view.value === "videos") return videoModelId.value;
  return "";
}

function applyTemplate(state: { prompt: string }, template: PromptTemplate) {
  state.prompt = state.prompt.trim()
    ? `${state.prompt.trim()}\n\n${template.prompt}`
    : template.prompt;
}

function parseJsonInput(value: string): Record<string, unknown> {
  if (!value.trim()) return {};
  const parsed = JSON.parse(value) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("高级参数 JSON 必须是对象。");
  }
  return parsed as Record<string, unknown>;
}

function isModelConfigured(model: ModelDefinition, setting: ModelSetting): boolean {
  return model.serverManaged ? Boolean(model.primarySubModelId) : Boolean(setting.baseUrl.trim() && setting.apiKey.trim());
}

function buildModelProxyPayload(
  model: ModelDefinition,
  setting: ModelSetting,
  extras: Record<string, unknown> = {},
): Record<string, unknown> {
  const primarySubModel = getPrimarySubModel(model);
  if (model.serverManaged && primarySubModel) {
    return {
      subModelId: primarySubModel.id,
      ...extras,
    };
  }
  return {
    config: { baseUrl: setting.baseUrl, apiKey: setting.apiKey },
    capability: model.capability,
    adapter: model.adapter,
    model: resolveModelName(model, setting),
    ...extras,
  };
}

function buildUploadConfig(model: ModelDefinition, setting: ModelSetting): { baseUrl?: string; apiKey?: string; subModelId?: string } {
  const primarySubModel = getPrimarySubModel(model);
  if (model.serverManaged && primarySubModel) {
    return { subModelId: primarySubModel.id };
  }
  return { baseUrl: setting.baseUrl, apiKey: setting.apiKey };
}

function conversationIdFor(capability: Capability): string {
  return conversationState.current?.capability === capability ? conversationState.current.id : "";
}

function persistedConversationIdFor(capability: Capability): string {
  const conversationId = conversationIdFor(capability);
  return conversationId.startsWith("cnv_") ? conversationId : "";
}

function getModelReadyError(model: ModelDefinition, setting: ModelSetting): string {
  if (model.serverManaged) {
    return getPrimarySubModel(model) ? "" : "当前服务端模型还没有可用的主模型，请先获取模型列表并选择主模型。";
  }
  if (!setting.baseUrl.trim() || !setting.apiKey.trim()) {
    return "当前模型尚未配置 baseURL 或 API Key。";
  }
  return "";
}

function promptTextForCapability(capability: Capability): string {
  if (capability === "text") return textState.prompt;
  if (capability === "image") return imageState.prompt;
  return videoState.prompt;
}

function promptKeywordsForCapability(capability: Capability): string {
  if (capability === "text") return textState.keywords;
  if (capability === "image") return imageState.keywords;
  return videoState.keywords;
}

function setPromptForCapability(capability: Capability, value: string) {
  if (capability === "text") textState.prompt = value;
  if (capability === "image") imageState.prompt = value;
  if (capability === "video") videoState.prompt = value;
}

function setPromptOptimizeState(capability: Capability, loading: boolean, error = "") {
  if (capability === "text") {
    textState.optimizing = loading;
    textState.error = error;
  }
  if (capability === "image") {
    imageState.optimizing = loading;
    imageState.error = error;
  }
  if (capability === "video") {
    videoState.optimizing = loading;
    videoState.error = error;
  }
}

function promptOptimizeParameters(capability: Capability): Record<string, unknown> {
  if (capability === "image") {
    return {
      size: imageUsesSizeControls.value ? imageState.size : "",
      ratio: imageUsesRatioControls.value ? imageState.ratio : "",
      resolution: imageUsesResolutionControls.value ? imageState.resolution : "",
      quality: imageUsesQualityControls.value ? imageState.quality : "",
      quantity: imageUsesQuantityControls.value ? imageState.count : "",
    };
  }
  if (capability === "video") {
    return {
      mode: videoUsesModeControls.value ? videoModeParamValue(videoState.mode) : "",
      aspect_ratio: videoUsesRatioControls.value ? videoState.aspectRatio : "",
      resolution: videoUsesResolutionControls.value ? videoState.resolution : "",
      duration: videoUsesDurationControls.value ? videoState.duration : "",
      quantity: videoUsesQuantityControls.value ? videoState.count : "",
      audio: videoUsesAudioControls.value ? videoState.audio : "",
    };
  }
  return {
    temperature: textState.temperature,
    max_tokens: textState.maxTokens,
  };
}

function promptOptimizeReferenceCount(capability: Capability): number {
  if (capability === "image") return imageState.references.length;
  if (capability === "video") {
    if (supportsUnifiedAdapter(activeModel.value?.adapter)) return videoState.unifiedImages.length;
    if (videoState.mode === "reference") return videoState.seedanceReferences.length;
    if (videoState.mode === "first-frame") return videoState.seedanceFirst ? 1 : 0;
    if (videoState.mode === "start-end") return [videoState.seedanceFirst, videoState.seedanceLast].filter(Boolean).length;
  }
  return 0;
}

async function handlePromptOptimize(capability: Capability) {
  const model = activeModel.value;
  const prompt = promptTextForCapability(capability).trim();
  if (!prompt) {
    setPromptOptimizeState(capability, false, "请先输入需要优化的提示词。");
    return;
  }
  setPromptOptimizeState(capability, true, "");
  try {
    const result = await optimizePrompt({
      capability,
      prompt,
      keywords: promptKeywordsForCapability(capability),
      subModelId: model?.capability === "text" ? getPrimarySubModel(model)?.id || "" : "",
      parameters: promptOptimizeParameters(capability),
      referenceCount: promptOptimizeReferenceCount(capability),
    });
    if (result.prompt?.trim()) {
      setPromptForCapability(capability, result.prompt.trim());
      showToast("提示词已优化", "success");
    }
  } catch (error) {
    setPromptOptimizeState(capability, false, error instanceof Error ? error.message : "提示词优化失败。");
    return;
  }
  setPromptOptimizeState(capability, false, "");
}

async function handleTextSubmit() {
  const model = activeModel.value;
  const setting = activeSetting.value;
  if (!model || !setting) {
    textState.error = getMissingModelMessage("text");
    return;
  }

  const finalPrompt = combinePrompt(textState.keywords, textState.prompt);
  if (!finalPrompt.trim()) {
    textState.error = "请先输入文案需求。";
    return;
  }
  const readyError = getModelReadyError(model, setting);
  if (readyError) {
    textState.error = readyError;
    return;
  }

  textState.loading = true;
  textState.error = "";
  const pendingConversation = appendLocalConversationMessages(conversationState.current, {
    capability: "text",
    titleSeed: finalPrompt,
    modelGroupId: model.id,
    subModelId: model.primarySubModelId || null,
    messages: [
      { role: "user", content: finalPrompt, assets: currentVideoReferenceAssets() },
      { role: "assistant", content: "", status: "processing" },
    ],
  });
  const pendingAssistantId = pendingConversation.messages[pendingConversation.messages.length - 1]?.id || "";
  setCurrentConversation(pendingConversation);
  const controller = createRequestController();
  try {
    const extra = parseJsonInput(textState.extraJson);
    const response = await postProxyWithSignal<TextResult>("/api/proxy/text", buildModelProxyPayload(model, setting, {
      conversationId: persistedConversationIdFor("text"),
      requestBody: {
        messages: [
          textState.systemPrompt.trim()
            ? { role: "system", content: textState.systemPrompt.trim() }
            : null,
          { role: "user", content: finalPrompt },
        ].filter(Boolean),
        stream: false,
        temperature: Number(textState.temperature) || undefined,
        max_tokens: Number(textState.maxTokens) || undefined,
        ...extra,
      },
    }), controller.signal);
    textState.result = response;
    const isAsyncTextTask = Boolean(response.taskId && shouldContinuePollingTask(response.status || "processing"));
    if (response.conversation) {
      setCurrentConversation(response.conversation);
      if (!isAsyncTextTask) simulateStreamingPreview(response.assistantMessage);
    } else if (isAsyncTextTask && response.taskId) {
      setCurrentConversation(updateLocalConversationMessage(pendingConversation, pendingAssistantId, {
        content: response.taskId,
        status: "processing",
        errorMessage: "",
        canRetry: false,
      }));
    } else {
      const localConversation = updateLocalConversationMessage(pendingConversation, pendingAssistantId, {
        content: response.content || "已返回响应",
        status: "success",
        errorMessage: "",
        canRetry: false,
      });
      setCurrentConversation(localConversation);
      simulateStreamingPreview(localConversation.messages[localConversation.messages.length - 1]);
    }
    if (isAsyncTextTask && response.taskId) {
      startTextPolling(response.taskId);
      return;
    }
    store.addHistory({
      id: createLocalId("history"),
      capability: "text",
      modelId: model.id,
      modelName: modelDisplayName(model),
      title: "文案创作",
      status: "success",
      createdAt: Date.now(),
      summary: shortText(response.content || "已返回响应"),
    });
  } catch (error) {
    const serverConversation = error instanceof ApiRequestError ? conversationFromUnknown(error.detail) : null;
    const message = resolveRequestErrorMessage(error, "文案生成失败。");
    if (serverConversation) {
      setCurrentConversation(serverConversation);
    } else {
      markLocalAssistantMessageFailed(pendingConversation, pendingAssistantId, message);
    }
    textState.error = message;
  } finally {
    clearRequestController(controller);
    textState.loading = false;
  }
}

function stopTextPolling() {
  if (textPollTimer !== null) {
    window.clearTimeout(textPollTimer);
    textPollTimer = null;
  }
  textPollTaskId = "";
}

function scheduleTextPolling(taskId: string) {
  if (!taskId || textPollTaskId !== taskId) return;
  if (textPollTimer !== null) window.clearTimeout(textPollTimer);
  textPollTimer = window.setTimeout(() => {
    void handleTextQuery(taskId, { fromPoll: true });
  }, TASK_POLL_INTERVAL_MS);
}

function startTextPolling(taskId: string) {
  if (!taskId) return;
  stopTextPolling();
  textPollTaskId = taskId;
  scheduleTextPolling(taskId);
}

async function handleTextQuery(taskIdArg?: string, options: { fromPoll?: boolean } = {}) {
  const model = activeModel.value;
  const setting = activeSetting.value;
  const taskId = taskIdArg || textTaskIdFromConversation();
  if (!model || !setting || !taskId) {
    if (!options.fromPoll) textState.error = "暂无可查询的文案任务 ID。";
    if (options.fromPoll) stopTextPolling();
    return;
  }

  textState.error = "";
  const controller = options.fromPoll ? new AbortController() : createRequestController();
  try {
    const response = await postProxyWithSignal<TextResult>("/api/proxy/text/query", buildModelProxyPayload(model, setting, {
      conversationId: persistedConversationIdFor("text"),
      taskId,
    }), controller.signal);
    textState.result = response;
    const messageStatus = videoMessageStatusFromTaskStatus(response.status || "");
    if (response.conversation) {
      setCurrentConversation(response.conversation);
      if (messageStatus === "success") simulateStreamingPreview(response.assistantMessage);
    } else {
      const updatedConversation = updateLocalConversationTaskMessage(conversationState.current, taskId, {
        content: messageStatus === "success" ? response.content || "" : taskId,
        status: messageStatus,
        errorMessage: messageStatus === "error" ? "文案任务失败，请检查模型后台或重新发送。" : "",
        canRetry: messageStatus === "error",
      });
      if (updatedConversation) setCurrentConversation(updatedConversation);
    }
    if (shouldContinuePollingTask(response.status || "")) {
      const nextTaskId = response.taskId || taskId;
      if (nextTaskId !== taskId) {
        startTextPolling(nextTaskId);
      } else {
        scheduleTextPolling(taskId);
      }
    } else {
      stopTextPolling();
      if (messageStatus === "success") {
        store.addHistory({
          id: createLocalId("history"),
          capability: "text",
          modelId: model.id,
          modelName: modelDisplayName(model),
          title: "文案创作",
          status: "success",
          createdAt: Date.now(),
          summary: shortText(response.content || "已返回响应"),
        });
      }
      if (messageStatus === "error") {
        textState.error = response.assistantMessage?.errorMessage || "文案任务失败，请检查模型后台或重新发送。";
      }
    }
  } catch (error) {
    textState.error = handleRequestError(error, "文案任务查询失败。");
    stopTextPolling();
  } finally {
    if (!options.fromPoll) clearRequestController(controller);
  }
}

function hasDraggedFiles(event: DragEvent): boolean {
  return Array.from(event.dataTransfer?.types || []).includes("Files");
}

function dragLeftCurrentTarget(event: DragEvent): boolean {
  const currentTarget = event.currentTarget;
  const relatedTarget = event.relatedTarget;
  if (!(currentTarget instanceof Node) || !(relatedTarget instanceof Node)) return true;
  return !currentTarget.contains(relatedTarget);
}

function handleImageDragEnter(event: DragEvent) {
  if (!hasDraggedFiles(event)) return;
  referenceDropState.image = true;
}

function handleImageDragOver(event: DragEvent) {
  if (!hasDraggedFiles(event)) return;
  referenceDropState.image = true;
  if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
}

function handleImageDragLeave(event: DragEvent) {
  if (dragLeftCurrentTarget(event)) referenceDropState.image = false;
}

function handleVideoDragEnter(event: DragEvent) {
  if (!hasDraggedFiles(event) || !currentVideoDropTarget()) return;
  referenceDropState.video = true;
}

function handleVideoDragOver(event: DragEvent) {
  if (!hasDraggedFiles(event) || !currentVideoDropTarget()) return;
  referenceDropState.video = true;
  if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
}

function handleVideoDragLeave(event: DragEvent) {
  if (dragLeftCurrentTarget(event)) referenceDropState.video = false;
}

function filesFromUploadInput(event: Event): File[] {
  const input = event.target as HTMLInputElement;
  return input.files ? filterReferenceImageFiles(input.files) : [];
}

function filesFromDropEvent(event: DragEvent): File[] {
  return event.dataTransfer?.files ? filterReferenceImageFiles(event.dataTransfer.files) : [];
}

function notifyTrimmedReferenceUploads(total: number, accepted: number) {
  if (total > accepted) {
    showToast(`已按当前上限添加 ${accepted} 张参考图。`, "info");
  }
}

async function uploadImageReferenceFiles(files: File[]) {
  const model = activeModel.value;
  const setting = activeSetting.value;
  if (!model || !setting) return;
  if (!files.length) {
    imageState.error = "请拖入 PNG、JPG 或 WebP 图片。";
    return;
  }
  const remainingSlots = Math.max(0, imageReferenceLimit.value - imageState.references.length);
  if (!remainingSlots) {
    imageState.error = `参考图最多 ${imageReferenceLimit.value} 张。`;
    return;
  }
  const selectedFiles = files.slice(0, remainingSlots);
  imageState.uploading = true;
  imageState.error = "";
  try {
    const uploaded = await Promise.all(
      selectedFiles.map((file) => uploadAsset(file, buildUploadConfig(model, setting))),
    );
    imageState.references = [...imageState.references, ...uploaded].slice(0, imageReferenceLimit.value);
    notifyTrimmedReferenceUploads(files.length, selectedFiles.length);
  } catch (error) {
    imageState.error = error instanceof Error ? error.message : "上传参考图失败。";
  } finally {
    imageState.uploading = false;
  }
}

async function handleImageUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  try {
    await uploadImageReferenceFiles(filesFromUploadInput(event));
  } finally {
    input.value = "";
  }
}

async function handleImageDrop(event: DragEvent) {
  referenceDropState.image = false;
  await uploadImageReferenceFiles(filesFromDropEvent(event));
}

async function handleImageSubmit() {
  const model = activeModel.value;
  const setting = activeSetting.value;
  if (!model || !setting) {
    imageState.error = getMissingModelMessage("image");
    return;
  }

  const finalPrompt = combinePrompt(imageState.keywords, imageState.prompt);
  if (!finalPrompt.trim()) {
    imageState.error = "请先输入图片需求。";
    return;
  }
  const readyError = getModelReadyError(model, setting);
  if (readyError) {
    imageState.error = readyError;
    return;
  }

  imageState.loading = true;
  imageState.error = "";
  const pendingConversation = appendLocalConversationMessages(conversationState.current, {
    capability: "image",
    titleSeed: finalPrompt,
    modelGroupId: model.id,
    subModelId: model.primarySubModelId || null,
    messages: [
      { role: "user", content: finalPrompt, assets: currentImageReferenceAssets() },
      { role: "assistant", content: "", status: "processing" },
    ],
  });
  const pendingAssistantId = pendingConversation.messages[pendingConversation.messages.length - 1]?.id || "";
  setCurrentConversation(pendingConversation);
  const controller = createRequestController();
  try {
    const extra = parseJsonInput(imageState.extraJson);
    imageState.result = await postProxyWithSignal<ImageResult>("/api/proxy/image", buildModelProxyPayload(model, setting, {
      conversationId: persistedConversationIdFor("image"),
      requestBody: buildImageRequestBody(model, finalPrompt, extra),
    }), controller.signal);
    if (imageState.result.conversation) {
      setCurrentConversation(imageState.result.conversation);
    } else {
      setCurrentConversation(updateLocalConversationMessage(pendingConversation, pendingAssistantId, {
        content: `已生成 ${imageState.result.images.length} 张图片。`,
        status: "success",
        errorMessage: "",
        canRetry: false,
        assets: imageState.result.images.map((image) => ({
          id: createLocalId("local-asset"),
          capability: "image",
          assetType: "image",
          url: image.src,
          thumbnailUrl: "",
          metadata: {},
          createdAt: new Date().toISOString(),
        })),
      }));
    }
    if (imageState.result.taskId && shouldContinuePollingTask(imageState.result.status || "processing")) {
      if (!imageState.result.conversation) {
        setCurrentConversation(updateLocalConversationMessage(pendingConversation, pendingAssistantId, {
          content: imageState.result.taskId,
          status: "processing",
          errorMessage: "",
          canRetry: false,
          assets: [],
        }));
      }
      startImagePolling(imageState.result.taskId);
    }
  } catch (error) {
    const serverConversation = error instanceof ApiRequestError ? conversationFromUnknown(error.detail) : null;
    if (serverConversation) {
      setCurrentConversation(serverConversation);
    } else {
      markLocalAssistantMessageFailed(pendingConversation, pendingAssistantId, resolveRequestErrorMessage(error, "图片生成失败。"));
    }
  } finally {
    clearRequestController(controller);
    imageState.loading = false;
  }
}

function stopImagePolling() {
  if (imagePollTimer !== null) {
    window.clearTimeout(imagePollTimer);
    imagePollTimer = null;
  }
  imagePollTaskId = "";
}

function scheduleImagePolling(taskId: string) {
  if (!taskId || imagePollTaskId !== taskId) return;
  if (imagePollTimer !== null) window.clearTimeout(imagePollTimer);
  imagePollTimer = window.setTimeout(() => {
    void handleImageQuery(taskId, { fromPoll: true });
  }, TASK_POLL_INTERVAL_MS);
}

function startImagePolling(taskId: string) {
  if (!taskId) return;
  stopImagePolling();
  imagePollTaskId = taskId;
  scheduleImagePolling(taskId);
}

async function handleImageQuery(taskIdArg?: string, options: { fromPoll?: boolean } = {}) {
  const model = activeModel.value;
  const setting = activeSetting.value;
  const taskId = taskIdArg || imageTaskIdFromConversation();
  if (!model || !setting || !taskId) {
    if (!options.fromPoll) imageState.error = "暂无可查询的图片任务 ID。";
    if (options.fromPoll) stopImagePolling();
    return;
  }

  imageState.error = "";
  const controller = options.fromPoll ? new AbortController() : createRequestController();
  try {
    imageState.result = await postProxyWithSignal<ImageResult>("/api/proxy/image/query", buildModelProxyPayload(model, setting, {
      conversationId: persistedConversationIdFor("image"),
      taskId,
    }), controller.signal);
    if (imageState.result.conversation) {
      setCurrentConversation(imageState.result.conversation);
    } else {
      const messageStatus = videoMessageStatusFromTaskStatus(imageState.result.status || "");
      const assets = conversationAssetsFromImageQueryResult({
        taskId,
        status: imageState.result.status,
        progress: imageState.result.progress,
        images: imageState.result.images || [],
      }).map((asset) => ({
        id: createLocalId("local-asset"),
        capability: "image" as Capability,
        assetType: asset.assetType,
        url: asset.url,
        thumbnailUrl: asset.thumbnailUrl || "",
        metadata: asset.metadata || {},
        createdAt: new Date().toISOString(),
      }));
      const updatedConversation = updateLocalConversationTaskMessage(conversationState.current, taskId, {
        content: messageStatus === "success" ? String(imageState.result.status || taskId) : taskId,
        status: messageStatus,
        errorMessage: messageStatus === "error" ? "图片任务失败，请检查模型后台或重新发送。" : "",
        canRetry: messageStatus === "error",
        assets,
      });
      setCurrentConversation(updatedConversation || appendLocalConversationMessages(conversationState.current, {
        capability: "image",
        titleSeed: taskId,
        modelGroupId: model.id,
        subModelId: model.primarySubModelId || null,
        messages: [
          {
            role: "assistant",
            content: messageStatus === "success" ? String(imageState.result.status || taskId) : taskId,
            status: messageStatus,
            errorMessage: messageStatus === "error" ? "图片任务失败，请检查模型后台或重新发送。" : "",
            canRetry: messageStatus === "error",
            assets,
          },
        ],
      }));
    }
    if (shouldContinuePollingTask(imageState.result.status || "")) {
      const nextTaskId = imageState.result.taskId || taskId;
      if (nextTaskId !== taskId) {
        startImagePolling(nextTaskId);
        return;
      }
      if (options.fromPoll) {
        scheduleImagePolling(taskId);
      } else {
        imagePollTaskId = taskId;
        scheduleImagePolling(taskId);
      }
    } else {
      stopImagePolling();
    }
  } catch (error) {
    imageState.error = handleRequestError(error, "图片任务查询失败。");
    stopImagePolling();
  } finally {
    if (!options.fromPoll) clearRequestController(controller);
  }
}

function supportsUnifiedAdapter(adapter?: Adapter): boolean {
  return adapter ? UNIFIED_ADAPTERS.includes(adapter) : false;
}

function currentVideoDropTarget(): VideoUploadTarget | null {
  const model = activeModel.value;
  if (!model) return null;
  if (supportsUnifiedAdapter(model.adapter)) {
    return videoState.mode === "text" ? null : "unified";
  }
  if (model.adapter !== "video-seedance") return null;
  if (videoState.mode === "reference") return "seedanceRef";
  if (videoState.mode === "first-frame") return "first";
  if (videoState.mode === "start-end") return "startEnd";
  return null;
}

function seedanceReferenceLimit(): number {
  return videoModeUploadLimit(activeModel.value, "reference");
}

function assignStartEndFrames(uploaded: UploadedAsset[]) {
  const queue = [...uploaded];
  if (!videoState.seedanceFirst && queue.length) {
    videoState.seedanceFirst = queue.shift() || null;
  } else if (queue.length) {
    videoState.seedanceFirst = queue.shift() || null;
  }
  if (!videoState.seedanceLast && queue.length) {
    videoState.seedanceLast = queue.shift() || null;
  } else if (queue.length) {
    videoState.seedanceLast = queue.shift() || null;
  }
}

async function uploadVideoReferenceFiles(files: File[], target: VideoUploadTarget) {
  const model = activeModel.value;
  const setting = activeSetting.value;
  if (!model || !setting) return;
  if (!files.length) {
    videoState.error = "请拖入 PNG、JPG 或 WebP 图片。";
    return;
  }

  let selectedFiles = files;
  if (target === "unified") {
    const remainingSlots = Math.max(0, unifiedVideoImageLimit.value - videoState.unifiedImages.length);
    if (!remainingSlots) {
      videoState.error = `参考图最多 ${unifiedVideoImageLimit.value} 张。`;
      return;
    }
    selectedFiles = files.slice(0, remainingSlots);
  }
  if (target === "seedanceRef") {
    const limit = seedanceReferenceLimit();
    const remainingSlots = Math.max(0, limit - videoState.seedanceReferences.length);
    if (!remainingSlots) {
      videoState.error = `参考图最多 ${limit} 张。`;
      return;
    }
    selectedFiles = files.slice(0, remainingSlots);
  }
  if (target === "first" || target === "last") {
    selectedFiles = files.slice(0, 1);
  }
  if (target === "startEnd") {
    selectedFiles = files.slice(0, 2);
  }

  videoState.uploading = true;
  videoState.error = "";
  try {
    const uploaded = await Promise.all(
      selectedFiles.map((file) => uploadAsset(file, buildUploadConfig(model, setting))),
    );
    if (target === "unified") {
      videoState.unifiedImages = [...videoState.unifiedImages, ...uploaded].slice(0, unifiedVideoImageLimit.value);
    }
    if (target === "first") videoState.seedanceFirst = uploaded[0] || null;
    if (target === "last") videoState.seedanceLast = uploaded[0] || null;
    if (target === "seedanceRef") {
      videoState.seedanceReferences = [...videoState.seedanceReferences, ...uploaded].slice(0, seedanceReferenceLimit());
    }
    if (target === "startEnd") assignStartEndFrames(uploaded);
    notifyTrimmedReferenceUploads(files.length, selectedFiles.length);
  } catch (error) {
    videoState.error = error instanceof Error ? error.message : "素材上传失败。";
  } finally {
    videoState.uploading = false;
  }
}

async function uploadVideoFiles(event: Event, target: VideoUploadTarget) {
  const input = event.target as HTMLInputElement;
  try {
    await uploadVideoReferenceFiles(filesFromUploadInput(event), target);
  } finally {
    input.value = "";
  }
}

async function handleVideoDrop(event: DragEvent) {
  referenceDropState.video = false;
  const target = currentVideoDropTarget();
  if (!target) {
    videoState.error = "当前视频模式不需要参考图。";
    return;
  }
  await uploadVideoReferenceFiles(filesFromDropEvent(event), target);
}

function buildVideoRequestBody(model: ModelDefinition, modelName: string, finalPrompt: string, extra: Record<string, unknown>) {
  const mediaImages = videoState.mode === "text" ? [] : videoState.unifiedImages.map((item) => item.publicUrl);
  const mediaFields = buildVideoMediaFields(model, videoState.mode, mediaImages);
  const addVideoParameter = (
    payload: Record<string, unknown>,
    keys: string[],
    outputKey: string,
    value: unknown,
  ) => addPayloadField(payload, model, keys, outputKey, value);
  const addSharedVideoParameters = (payload: Record<string, unknown>, options: { includeAudio?: boolean } = {}) => {
    addVideoParameter(payload, ["video_mode"], "video_mode", videoModeParamValue(videoState.mode));
    addVideoParameter(payload, ["ratio", "aspect_ratio"], "aspect_ratio", videoState.aspectRatio);
    addVideoParameter(payload, ["duration"], "duration", Number(videoState.duration) || 5);
    addVideoParameter(payload, ["quantity"], "quantity", Number(videoState.count) || 1);
    addVideoParameter(payload, ["resolution", "size"], videoResolutionRequestKey(model, videoState.resolution), videoState.resolution);
    if (options.includeAudio) addVideoParameter(payload, ["generate_audio", "audio"], "audio", videoState.audio);
  };
  if (model.adapter === "video-unified-jimeng") {
    const body: Record<string, unknown> = {
      model: modelName,
      prompt: finalPrompt,
      ...mediaFields,
    };
    addVideoParameter(body, ["video_mode"], "video_mode", videoModeParamValue(videoState.mode));
    addVideoParameter(body, ["ratio", "aspect_ratio"], "aspect_ratio", videoState.aspectRatio);
    addVideoParameter(body, ["resolution", "size"], videoResolutionRequestKey(model, videoState.resolution), videoState.resolution);
    addVideoParameter(body, ["quantity"], "quantity", Number(videoState.count) || 1);
    return { ...body, ...extra };
  }
  if (model.adapter === "video-unified-vidu") {
    const body: Record<string, unknown> = {
      model: modelName,
      prompt: finalPrompt,
      ...mediaFields,
    };
    addSharedVideoParameters(body, { includeAudio: true });
    addSeedParameter(body, model);
    return { ...body, ...extra };
  }
  if (model.adapter === "video-unified-veo") {
    const body: Record<string, unknown> = {
      model: modelName,
      prompt: finalPrompt,
      orientation: videoState.aspectRatio === "9:16" ? "portrait" : "landscape",
      enable_upsample: videoState.upsample,
      ...mediaFields,
    };
    addVideoParameter(body, ["video_mode"], "video_mode", videoModeParamValue(videoState.mode));
    addVideoParameter(body, ["resolution", "size"], videoResolutionRequestKey(model, videoState.resolution), videoState.resolution);
    addVideoParameter(body, ["duration"], "duration", Number(videoState.duration) || 8);
    addVideoParameter(body, ["quantity"], "quantity", Number(videoState.count) || 1);
    addVideoParameter(body, ["ratio", "aspect_ratio"], "aspect_ratio", videoState.aspectRatio);
    return { ...body, ...extra };
  }
  if (model.adapter === "video-seedance") {
    const content: Array<Record<string, unknown>> = [{ type: "text", text: finalPrompt }];
    if (videoState.mode === "reference") {
      videoState.seedanceReferences.forEach((asset) => {
        content.push({ type: "image_url", image_url: { url: asset.publicUrl }, role: "reference_image" });
      });
    }
    if (videoState.mode === "first-frame" && videoState.seedanceFirst) {
      content.push({ type: "image_url", image_url: { url: videoState.seedanceFirst.publicUrl }, role: "first_frame" });
    }
    if (videoState.mode === "start-end") {
      if (videoState.seedanceFirst) {
        content.push({ type: "image_url", image_url: { url: videoState.seedanceFirst.publicUrl }, role: "first_frame" });
      }
      if (videoState.seedanceLast) {
        content.push({ type: "image_url", image_url: { url: videoState.seedanceLast.publicUrl }, role: "last_frame" });
      }
    }
    const metadata: Record<string, unknown> = {};
    addVideoParameter(metadata, ["duration"], "duration", Number(videoState.duration) || 5);
    addVideoParameter(metadata, ["resolution", "size"], "resolution", videoState.resolution);
    addVideoParameter(metadata, ["ratio", "aspect_ratio"], "ratio", videoState.aspectRatio);
    addVideoParameter(metadata, ["generate_audio", "audio"], "generate_audio", videoState.audio);
    addVideoParameter(metadata, ["quantity"], "quantity", Number(videoState.count) || 1);
    addVideoParameter(metadata, ["video_mode"], "video_mode", videoModeParamValue(videoState.mode));
    addSeedParameter(metadata, model);
    return {
      model: modelName,
      content,
      metadata,
      ...extra,
    };
  }
  const body: Record<string, unknown> = {
    model: modelName,
    prompt: finalPrompt,
    ...mediaFields,
  };
  addSharedVideoParameters(body, { includeAudio: true });
  addSeedParameter(body, model);
  return { ...body, ...extra };
}

async function handleVideoCreate() {
  const model = activeModel.value;
  const setting = activeSetting.value;
  if (!model || !setting) {
    videoState.error = getMissingModelMessage("video");
    return;
  }

  const finalPrompt = combinePrompt(videoState.keywords, videoState.prompt);
  if (!finalPrompt.trim()) {
    videoState.error = "请先输入视频需求。";
    return;
  }
  const readyError = getModelReadyError(model, setting);
  if (readyError) {
    videoState.error = readyError;
    return;
  }
  if (supportsUnifiedAdapter(model.adapter) && videoState.unifiedImages.length < unifiedVideoRequiredImageCount.value) {
    videoState.error = "当前模式需要的参考图数量还不够。";
    return;
  }
  if (model.adapter === "video-seedance" && videoState.mode === "reference" && !videoState.seedanceReferences.length) {
    videoState.error = "Seedance 参考模式至少需要上传一张参考图。";
    return;
  }
  if (model.adapter === "video-seedance" && videoState.mode === "first-frame" && !videoState.seedanceFirst) {
    videoState.error = "Seedance 首帧模式需要上传首帧。";
    return;
  }
  if (model.adapter === "video-seedance" && videoState.mode === "start-end" && (!videoState.seedanceFirst || !videoState.seedanceLast)) {
    videoState.error = "Seedance 首尾帧模式需要同时上传首帧和尾帧。";
    return;
  }

  videoState.loading = true;
  videoState.error = "";
  videoState.taskResult = null;
  const pendingConversation = appendLocalConversationMessages(conversationState.current, {
    capability: "video",
    titleSeed: finalPrompt,
    modelGroupId: model.id,
    subModelId: model.primarySubModelId || null,
    messages: [
      { role: "user", content: finalPrompt },
      { role: "assistant", content: "", status: "processing" },
    ],
  });
  const pendingAssistantId = pendingConversation.messages[pendingConversation.messages.length - 1]?.id || "";
  setCurrentConversation(pendingConversation);
  const controller = createRequestController();
  try {
    const extra = parseJsonInput(videoState.extraJson);
    const requestBody = buildVideoRequestBody(model, resolveModelName(model, setting), finalPrompt, extra);
    videoState.createResult = await postProxyWithSignal<VideoCreateResult>("/api/proxy/video/create", buildModelProxyPayload(model, setting, {
      adapter: model.adapter,
      conversationId: persistedConversationIdFor("video"),
      requestBody,
    }), controller.signal);
    if (videoState.createResult.conversation) {
      setCurrentConversation(videoState.createResult.conversation);
    } else {
      setCurrentConversation(updateLocalConversationMessage(pendingConversation, pendingAssistantId, {
        content: videoState.createResult.taskId,
        status: "processing",
        errorMessage: "",
        canRetry: false,
      }));
    }
    if (videoState.autoPoll) {
      startVideoPolling(videoState.createResult.taskId);
    }
  } catch (error) {
    const serverConversation = error instanceof ApiRequestError ? conversationFromUnknown(error.detail) : null;
    const message = resolveRequestErrorMessage(error, "视频任务提交失败。");
    if (serverConversation) {
      setCurrentConversation(serverConversation);
    } else {
      markLocalAssistantMessageFailed(pendingConversation, pendingAssistantId, message);
    }
    videoState.error = message;
  } finally {
    clearRequestController(controller);
    videoState.loading = false;
  }
}

function stopVideoPolling() {
  if (videoPollTimer !== null) {
    window.clearTimeout(videoPollTimer);
    videoPollTimer = null;
  }
  videoPollTaskId = "";
}

function scheduleVideoPolling(taskId: string) {
  if (!videoState.autoPoll || !taskId || videoPollTaskId !== taskId) return;
  if (videoPollTimer !== null) window.clearTimeout(videoPollTimer);
  videoPollTimer = window.setTimeout(() => {
    void handleVideoQuery(taskId, { fromPoll: true });
  }, TASK_POLL_INTERVAL_MS);
}

function startVideoPolling(taskId: string) {
  if (!taskId) return;
  stopVideoPolling();
  videoPollTaskId = taskId;
  scheduleVideoPolling(taskId);
}

async function handleVideoQuery(taskIdArg?: string, options: { fromPoll?: boolean } = {}) {
  const model = activeModel.value;
  const setting = activeSetting.value;
  const taskId = taskIdArg || taskIdFromConversation();
  if (!model || !setting || !taskId) {
    videoState.error = "暂无可查询的任务 ID。";
    if (options.fromPoll) stopVideoPolling();
    return;
  }

  videoState.querying = true;
  videoState.error = "";
  const controller = options.fromPoll ? new AbortController() : createRequestController();
  try {
    videoState.taskResult = await postProxyWithSignal<VideoQueryResult>("/api/proxy/video/query", buildModelProxyPayload(model, setting, {
      adapter: model.adapter,
      conversationId: persistedConversationIdFor("video"),
      taskId,
    }), controller.signal);
    if (videoState.taskResult.conversation) {
      setCurrentConversation(videoState.taskResult.conversation);
    } else {
      const messageStatus = videoMessageStatusFromTaskStatus(videoState.taskResult.status || "");
      const videoAsset = conversationAssetFromVideoQueryResult({
        taskId,
        status: videoState.taskResult.status,
        progress: videoState.taskResult.progress,
        videoUrl: videoState.taskResult.videoUrl,
        thumbnailUrl: videoState.taskResult.thumbnailUrl,
      });
      const assets = videoAsset
        ? [{
            id: createLocalId("local-asset"),
            capability: "video" as Capability,
            assetType: videoAsset.assetType,
            url: videoAsset.url,
            thumbnailUrl: videoAsset.thumbnailUrl || "",
            metadata: videoAsset.metadata || {},
            createdAt: new Date().toISOString(),
          }]
        : [];
      const updatedConversation = updateLocalConversationTaskMessage(conversationState.current, taskId, {
        content: messageStatus === "success" ? String(videoState.taskResult.status || taskId) : taskId,
        status: messageStatus,
        errorMessage: messageStatus === "error" ? "视频任务失败，请检查模型后台或重新发送。" : "",
        canRetry: messageStatus === "error",
        assets,
      });
      setCurrentConversation(updatedConversation || appendLocalConversationMessages(conversationState.current, {
        capability: "video",
        titleSeed: taskId,
        modelGroupId: model.id,
        subModelId: model.primarySubModelId || null,
        messages: [
          {
            role: "assistant",
            content: messageStatus === "success" ? String(videoState.taskResult.status || taskId) : taskId,
            status: messageStatus,
            errorMessage: messageStatus === "error" ? "视频任务失败，请检查模型后台或重新发送。" : "",
            canRetry: messageStatus === "error",
            assets,
          },
        ],
      }));
    }
    if (shouldContinuePollingTask(videoState.taskResult.status || "")) {
      if (options.fromPoll) {
        scheduleVideoPolling(taskId);
      } else if (videoState.autoPoll) {
        videoPollTaskId = taskId;
        scheduleVideoPolling(taskId);
      }
    } else {
      stopVideoPolling();
    }
  } catch (error) {
    videoState.error = handleRequestError(error, "任务查询失败。");
    if (options.fromPoll) stopVideoPolling();
  } finally {
    if (!options.fromPoll) clearRequestController(controller);
    videoState.querying = false;
  }
}

function createIdleState<T>(): ActionState<T> {
  return { loading: false, error: "", result: null };
}

function createEmptyDraft(): ConfigDraft {
  return {
    id: createLocalId("custom-model"),
    name: "",
    vendor: "",
    capability: "video",
    adapter: "video-unified-generic",
    model: "",
    description: "",
    baseUrl: "",
    apiKey: "",
    modelNameOverride: "",
    availableModels: [],
    catalogModelId: "",
  };
}

function createDraftFromModel(model: ModelDefinition): ConfigDraft {
  const setting = getSetting(model.id);
  return {
    id: model.id,
    name: model.name,
    vendor: model.vendor,
    capability: model.capability,
    adapter: model.adapter,
    model: model.model,
    description: model.description,
    baseUrl: setting.baseUrl,
    apiKey: setting.apiKey,
    modelNameOverride: setting.modelNameOverride,
    availableModels: setting.availableModels || [],
    catalogModelId: model.catalogModelId || getPrimarySubModel(model)?.catalogModelId || "",
  };
}

function getDraftSetting(): ModelSetting {
  return {
    baseUrl: settingsState.draft.baseUrl,
    apiKey: settingsState.draft.apiKey,
    modelNameOverride: settingsState.draft.modelNameOverride,
    availableModels: settingsState.draft.availableModels,
  };
}

function getDraftModel(): ModelDefinition {
  const draft = settingsState.draft;
  const modelName = getDraftModelName(draft);
  return {
    id: draft.id,
    name: draft.name.trim() || "未命名模型",
    vendor: draft.vendor.trim() || "自定义",
    capability: draft.capability,
    adapter: draft.adapter,
    model: modelName || draft.id,
    description: draft.description.trim() || "用户自定义模型",
    builtin: false,
  };
}

function getDraftModelName(draft: ConfigDraft): string {
  return resolveDraftPrimaryModel(draft);
}

function getDraftDefaultName(): string {
  return modelDisplayNameFromPrimary(settingsState.draft.capability, getDraftModelName(settingsState.draft));
}

function isAutoDraftName(value: string): boolean {
  return isGeneratedModelDisplayName(value);
}

function syncDraftAutoName() {
  if (isAutoDraftName(settingsState.draft.name)) {
    settingsState.draft.name = getDraftDefaultName();
  }
}

function handleDraftCapabilityChange() {
  settingsState.draft.adapter = getCapabilityDefaultAdapter(settingsState.draft.capability);
  settingsState.draft.model = "";
  settingsState.draft.modelNameOverride = "";
  settingsState.draft.availableModels = [];
  syncDraftAutoName();
  delete settingsState.modelListState[settingsState.draft.id];
  delete settingsState.testState[settingsState.draft.id];
}

function canSaveDraft(): boolean {
  return canSaveModelDraft(
    settingsState.draft,
    getDraftSetting(),
    Boolean(auth.state.user && settingsState.dialogMode === "create"),
  );
}

function getAvailableModels(model: ModelDefinition): string[] {
  const latestModels = settingsState.modelListState[model.id]?.result?.models || [];
  if (latestModels.length) return latestModels;
  if (model.subModels?.length) return model.subModels.map((item) => item.modelName);
  return getSetting(model.id).availableModels || [];
}

function getModelStatusLabel(model: ModelDefinition, setting: ModelSetting): string {
  if (settingsState.testState[model.id]?.loading) return "测试中";
  if (settingsState.testState[model.id]?.result) return `已连接 ${testResultSummary(settingsState.testState[model.id].result).duration}`;
  if (settingsState.testState[model.id]?.error) return "连接失败";
  if (!isModelConfigured(model, setting)) return "待配置";
  return "待测试";
}

function getModelStatusClass(model: ModelDefinition, setting: ModelSetting): string {
  if (settingsState.testState[model.id]?.result) return "badge-success";
  if (settingsState.testState[model.id]?.error) return "badge-danger";
  if (settingsState.testState[model.id]?.loading || !isModelConfigured(model, setting)) return "badge-warn";
  return "";
}

function compactJson(value: unknown): string {
  return testResultSummary({ raw: value }).rawPreview;
}

function modelDisplayName(model: ModelDefinition): string {
  return modelDisplayNameForModel(model, getSetting(model.id));
}

function modelIconUrl(model: ModelDefinition): string {
  return modelCatalogIconUrl(model);
}

function modelSafeDescription(model: ModelDefinition | null | undefined): string {
  return safeModelDescription(model, "选择模型并输入需求开始调试。");
}

function hideBrokenModelIcon(event: Event) {
  const target = event.target;
  if (target instanceof HTMLImageElement) {
    target.style.display = "none";
    target.parentElement?.classList.add("model-avatar-icon-failed");
  }
}

function modelSummaryText(model: ModelDefinition): string {
  const setting = getSetting(model.id);
  const primaryModel = resolveModelName(model, setting);
  return `${CAPABILITY_LABELS[model.capability]} · ${primaryModel || "尚未选择主模型"} · ${modelConnectionLabel(model, setting)}`;
}

function testSummaryFor(result: TestRequestResult | null | undefined) {
  return testResultSummary(result || {});
}

async function setPrimaryModel(modelId: string, model: ModelDefinition, setting: ModelSetting) {
  if (!canEditModel(model)) {
    settingsState.modelListState[model.id] = { ...createIdleState<AvailableModelsResult>(), error: "公共模型只有管理员可以修改。" };
    return;
  }
  if (model.serverManaged) {
    const target = model.subModels?.find((item) => item.modelName === modelId || item.id === modelId);
    if (!target) {
      settingsState.modelListState[model.id] = { ...createIdleState<AvailableModelsResult>(), error: "未找到对应的服务端子模型。" };
      return;
    }
    settingsState.modelListState[model.id] = { ...createIdleState<AvailableModelsResult>(), loading: true };
    try {
      await setServerPrimaryModel(model.id, target.id);
      await refreshServerModels();
      showToast("Primary model updated");
      settingsState.modelListState[model.id] = {
        loading: false,
        error: "",
        result: {
          models: getAvailableModels(model),
          durationMs: 0,
          raw: {},
        },
      };
    } catch (error) {
      settingsState.modelListState[model.id] = {
        loading: false,
        error: error instanceof Error ? error.message : "设置主模型失败。",
        result: null,
      };
    }
    return;
  }
  store.updateModelSetting(model.id, {
    ...setting,
    modelNameOverride: modelId,
  });
  showToast("Primary model updated");
}

function openCreateDialog() {
  closeModelSelect();
  settingsState.dialogMode = "create";
  settingsState.draft = createEmptyDraft();
  syncDraftAutoName();
  settingsState.dialogOpen = true;
}

function openEditDialog(model: ModelDefinition) {
  if (!canEditModel(model)) {
    showToast("公共模型只有管理员可以编辑。", "error");
    return;
  }
  closeModelSelect();
  settingsState.dialogMode = "edit";
  settingsState.draft = createDraftFromModel(model);
  settingsState.dialogOpen = true;
}

function closeSettingsDialog() {
  closeModelSelect();
  settingsState.dialogOpen = false;
}

async function saveDialog() {
  const draft = settingsState.draft;
  syncDraftAutoName();
  const modelName = getDraftModelName(draft);
  if (
    !draft.name.trim() ||
    !modelName ||
    getModelIdentifierError(draft.model) ||
    getModelIdentifierError(draft.modelNameOverride)
  ) {
    return;
  }
  if (auth.state.user) {
    const payload = {
      name: draft.name.trim() || getDraftDefaultName(),
      vendor: draft.vendor.trim() || "自定义",
      capability: draft.capability,
      adapter: draft.adapter,
      description: draft.description.trim() || "用户自定义模型",
      baseUrl: draft.baseUrl.trim(),
      apiKey: draft.apiKey.trim(),
      primaryModelName: modelName,
      availableModelNames: draft.availableModels.length ? draft.availableModels : [modelName],
      catalogModelId: draft.catalogModelId,
    };
    settingsState.testState[draft.id] = { ...createIdleState<TestRequestResult>(), loading: true };
    try {
      if (settingsState.dialogMode === "create") {
        await createServerModel(payload);
      } else {
        await updateServerModel(draft.id, payload);
      }
      await refreshServerModels();
      settingsState.testState[draft.id] = { ...createIdleState<TestRequestResult>() };
      closeModelSelect();
      settingsState.dialogOpen = false;
      showToast("Model saved");
    } catch (error) {
      settingsState.testState[draft.id] = {
        loading: false,
        error: error instanceof Error ? error.message : "保存模型失败。",
        result: null,
      };
      showToast(settingsState.testState[draft.id].error, "error");
    }
    return;
  }
  if (settingsState.dialogMode === "create") {
    store.addCustomModel({
      id: draft.id,
      name: draft.name.trim() || getDraftDefaultName(),
      vendor: draft.vendor.trim() || "自定义",
      capability: draft.capability,
      adapter: draft.adapter,
      model: modelName,
      description: draft.description.trim() || "用户自定义模型",
    });
  } else {
    const target = store.models.value.find((model) => model.id === draft.id);
    if (target && !target.builtin) {
      store.updateCustomModel(draft.id, {
        name: draft.name.trim() || getDraftDefaultName(),
        vendor: draft.vendor.trim() || "自定义",
        capability: draft.capability,
        adapter: draft.adapter,
        model: modelName,
        description: draft.description.trim() || "用户自定义模型",
      });
    }
  }
  store.updateModelSetting(draft.id, {
    baseUrl: draft.baseUrl.trim(),
    apiKey: draft.apiKey.trim(),
    modelNameOverride: draft.modelNameOverride.trim(),
    availableModels: draft.availableModels,
  });
  closeModelSelect();
  showToast("Model saved");
  settingsState.dialogOpen = false;
}

async function fetchModelList(model: ModelDefinition, setting: ModelSetting) {
  if (!canEditModel(model)) {
    settingsState.modelListState[model.id] = { ...createIdleState<AvailableModelsResult>(), error: "公共模型只有管理员可以同步模型列表。" };
    showToast(settingsState.modelListState[model.id].error, "error");
    return;
  }
  if (model.serverManaged) {
    settingsState.modelListState[model.id] = { ...createIdleState<AvailableModelsResult>(), loading: true };
    try {
      const result = await syncServerModel(model.id);
      await refreshServerModels();
      settingsState.modelListState[model.id] = {
        loading: false,
        error: "",
        result: {
          models: result.models,
          durationMs: result.durationMs,
          raw: {},
        },
      };
      showToast("Model list updated");
    } catch (error) {
      settingsState.modelListState[model.id] = {
        loading: false,
        error: error instanceof Error ? error.message : "获取可用模型失败。",
        result: null,
      };
      showToast(settingsState.modelListState[model.id].error, "error");
    }
    return;
  }
  if (!setting.baseUrl.trim() || !setting.apiKey.trim()) {
    settingsState.modelListState[model.id] = { ...createIdleState<AvailableModelsResult>(), error: "请先填写 baseURL 和 API Key。" };
    return;
  }
  settingsState.modelListState[model.id] = { ...createIdleState<AvailableModelsResult>(), loading: true };
  try {
      const result = await postProxy<AvailableModelsResult>("/api/proxy/models", {
      config: { baseUrl: setting.baseUrl, apiKey: setting.apiKey },
      capability: model.capability,
    });
    const isDraftModel = model.id === settingsState.draft.id;
    const updatedDraft = isDraftModel ? applyFetchedModelsToDraft(settingsState.draft, result.models) : null;
    const primaryModel = updatedDraft?.modelNameOverride || pickPrimaryModel(result.models, setting.modelNameOverride || model.model);
    settingsState.modelListState[model.id] = {
      loading: false,
      error: "",
      result,
    };
    if (updatedDraft) {
      settingsState.draft = updatedDraft;
      syncDraftAutoName();
      showToast("Model list fetched");
      return;
    }
    store.updateModelSetting(model.id, {
      ...setting,
      availableModels: result.models,
      modelNameOverride: primaryModel,
    });
    showToast("Model list fetched");
  } catch (error) {
    settingsState.modelListState[model.id] = {
      loading: false,
      error: error instanceof Error ? error.message : "获取可用模型失败。",
      result: null,
    };
      showToast(settingsState.modelListState[model.id].error, "error");
  }
}

async function testModel(model: ModelDefinition, setting: ModelSetting) {
  const readyError = getModelReadyError(model, setting);
  if (readyError) {
    settingsState.testState[model.id] = { ...createIdleState<TestRequestResult>(), error: readyError };
    return;
  }
  if (!model.serverManaged) {
    const modelIdentifierError = getModelIdentifierError(resolveModelName(model, setting));
    if (modelIdentifierError) {
      settingsState.testState[model.id] = { ...createIdleState<TestRequestResult>(), error: modelIdentifierError };
      return;
    }
  }
  settingsState.testState[model.id] = { ...createIdleState<TestRequestResult>(), loading: true };
  try {
    settingsState.testState[model.id] = {
      loading: false,
      error: "",
      result: await postProxy<TestRequestResult>("/api/proxy/test", buildModelProxyPayload(model, setting)),
    };
    showToast("Test succeeded");
  } catch (error) {
    settingsState.testState[model.id] = {
      loading: false,
      error: error instanceof Error ? error.message : "测试请求失败。",
      result: null,
    };
      showToast(settingsState.testState[model.id].error, "error");
  }
}

function toggleSelected(modelId: string, checked: boolean) {
  const model = store.models.value.find((item) => item.id === modelId);
  if (checked && model && !canEditModel(model)) {
    showToast("公共模型不能加入批量编辑。", "info");
    return;
  }
  settingsState.selectedIds = checked
    ? Array.from(new Set([...settingsState.selectedIds, modelId]))
    : settingsState.selectedIds.filter((id) => id !== modelId);
}

function toggleAllSettings(checked: boolean) {
  const visibleIds = filteredSettingsModels.value.filter((model) => canEditModel(model)).map((model) => model.id);
  settingsState.selectedIds = checked
    ? Array.from(new Set([...settingsState.selectedIds, ...visibleIds]))
    : settingsState.selectedIds.filter((id) => !visibleIds.includes(id));
}

async function batchTest() {
  await Promise.allSettled(
    selectedVisibleSettingsModels.value
      .filter((model) => {
        const setting = getSetting(model.id);
        return isModelConfigured(model, setting);
      })
      .map((model) => testModel(model, getSetting(model.id))),
  );
}

async function batchPublishPublic() {
  if (!auth.state.user?.isAdmin) {
    showToast("只有主管理员可以设置公用模型。", "error");
    return;
  }
  const targets = publicShareTargets.value;
  if (!targets.length) {
    showToast("请选择可发布的私有服务端模型。", "info");
    return;
  }
  for (const model of targets) {
    settingsState.testState[model.id] = { ...createIdleState<TestRequestResult>(), loading: true };
  }
  let successCount = 0;
  for (const model of targets) {
    try {
      await updateServerModel(model.id, { isPublic: true });
      successCount += 1;
      settingsState.testState[model.id] = { ...createIdleState<TestRequestResult>() };
    } catch (error) {
      settingsState.testState[model.id] = {
        loading: false,
        error: error instanceof Error ? error.message : "设置公用模型失败。",
        result: null,
      };
    }
  }
  await refreshServerModels();
  settingsState.selectedIds = settingsState.selectedIds.filter((id) => !targets.some((model) => model.id === id));
  showToast(successCount ? `已设置 ${successCount} 个公用模型` : "没有模型被设置为公用", successCount ? "success" : "error");
}

async function removeModelFromWorkbench(modelId: string, options: { skipConfirm?: boolean } = {}) {
  const model = store.models.value.find((item) => item.id === modelId);
  if (model && !canEditModel(model)) {
    settingsState.testState[modelId] = { ...createIdleState<TestRequestResult>(), error: "公共模型只有管理员可以删除。" };
    showToast(settingsState.testState[modelId].error, "error");
    return;
  }
  if (!options.skipConfirm && model) {
    const confirmed = window.confirm(deleteConfirmationSummary("删除", 1));
    if (!confirmed) return;
  }
  if (model?.serverManaged) {
    settingsState.testState[modelId] = { ...createIdleState<TestRequestResult>(), loading: true };
    try {
      await deleteServerModel(modelId);
      await refreshServerModels();
    } catch (error) {
      settingsState.testState[modelId] = {
        loading: false,
        error: error instanceof Error ? error.message : "删除模型失败。",
        result: null,
      };
      return;
    }
  } else {
    store.removeModel(modelId);
  }
  settingsState.selectedIds = settingsState.selectedIds.filter((selectedId) => selectedId !== modelId);
  delete settingsState.modelListState[modelId];
  delete settingsState.testState[modelId];
}

async function removeModelsWithConfirmation(models: ModelDefinition[], actionLabel: string, skippedCount = 0) {
  const ids = models.map((model) => model.id);
  if (!ids.length) {
    showToast("没有可删除的模型。", "info");
    return;
  }
  if (!window.confirm(deleteConfirmationSummary(actionLabel, ids.length, skippedCount))) return;
  await Promise.allSettled(ids.map((modelId) => removeModelFromWorkbench(modelId, { skipConfirm: true })));
  settingsState.selectedIds = settingsState.selectedIds.filter((selectedId) => !ids.includes(selectedId));
}

async function batchDelete() {
  const editableModels = selectedVisibleSettingsModels.value.filter((model) => canEditModel(model));
  const skippedCount = selectedVisibleSettingsModels.value.length - editableModels.length;
  if (skippedCount > 0) {
    showToast("公共模型已跳过，只有管理员可以删除。", "info");
  }
  await removeModelsWithConfirmation(editableModels, "批量删除", skippedCount);
}

async function removeUnavailableModels() {
  const targets = unavailableEditableSettingsModels.value;
  const unavailableCount = filteredSettingsModels.value.filter((model) => {
    const state = settingsState.testState[model.id];
    return Boolean(state?.error) && !state?.loading && !state?.result;
  }).length;
  const skippedCount = unavailableCount - targets.length;
  if (skippedCount > 0) {
    showToast("不可删除的公共模型已跳过。", "info");
  }
  await removeModelsWithConfirmation(targets, "移除不可用", skippedCount);
}
</script>

<template>
  <div :class="['shell', view === 'admin' ? 'shell-admin' : '']" :data-theme="themeMode">
    <aside v-if="view !== 'admin'" class="sidebar">
      <div class="sidebar-logo">
        <div class="logo-mark">
          <img src="/brand/cylon-studio-mark.png" alt="创意工坊" />
        </div>
        <div>
          <strong>创意工坊</strong>
          <span>多模型创作调试台</span>
        </div>
      </div>

      <div class="category-tabs">
        <div class="primary-selector">
          <button class="primary-item primary-item-active">大模型</button>
          <button class="primary-item" @click="navigate('profile')">个人信息</button>
        </div>
        <div class="secondary-selector">
          <button
            v-for="item in [
              { label: '全部', value: 'all' },
              { label: '聊天', value: 'text' },
              { label: '图片', value: 'image' },
              { label: '视频', value: 'video' },
            ]"
            :key="item.value"
            :class="['secondary-item', effectiveSidebarFilter === item.value ? 'secondary-item-active' : '']"
            @click="sidebarFilter = item.value as SidebarFilter"
          >
            {{ item.label }}
          </button>
        </div>
      </div>

      <div class="model-list">
        <div class="model-divider"><span>模型列表</span></div>
        <button
          v-for="model in filteredModels"
          :key="model.id"
          :data-model-id="model.id"
          :class="['sidebar-model-item', model.id === activeModelIdForSidebar() ? 'sidebar-model-active' : '', model.isPublic ? 'sidebar-model-public' : '']"
          @click="selectModel(model)"
        >
          <div :class="['model-avatar', `model-avatar-${model.capability}`, modelIconUrl(model) ? 'model-avatar-has-icon' : '']">
            <img v-if="modelIconUrl(model)" :src="modelIconUrl(model)" :alt="modelDisplayName(model)" loading="lazy" @error="hideBrokenModelIcon" />
            <span>{{ model.capability === "text" ? "T" : model.capability === "image" ? "I" : "V" }}</span>
          </div>
          <div class="model-info">
            <strong>{{ modelDisplayName(model) }}</strong>
            <span>{{ modelSummaryText(model) }}</span>
            <span :class="['parameter-source-chip', hasCatalogParameters(model) ? 'parameter-source-chip-exact' : 'parameter-source-chip-generic']">
              {{ modelParameterSourceLabel(model) }}
            </span>
            <span v-if="model.isPublic" class="sidebar-public-tag">公共</span>
          </div>
          <span :class="['model-tag', `tag-${model.capability}`]">
            {{ CAPABILITY_LABELS[model.capability] }}
          </span>
        </button>
      </div>

      <div class="sidebar-account">
        <div class="account-avatar">{{ auth.state.user?.nickname?.slice(0, 1) || "S" }}</div>
        <div class="account-copy">
          <strong>{{ auth.state.user?.nickname || "未登录" }}</strong>
          <span>{{ userAccountLabel }}</span>
        </div>
        <button v-if="auth.state.user" class="account-recharge" @click="navigate('profile')">我的</button>
        <button v-else class="account-recharge" :disabled="auth.state.loading" @click="navigate('auth')">登录</button>
      </div>
    </aside>

    <main class="main">
      <div v-if="view !== 'admin'" class="workspace-topbar">
        <div class="workspace-topbar-actions">
          <button @click="startNewConversation()">+ 新建对话</button>
          <button class="button-secondary" @click="toggleHistoryDrawer">历史记录</button>
          <button v-if="conversationState.activeRequest" class="button-danger" @click="stopActiveRequest">暂停</button>
        </div>
        <div class="workspace-topbar-actions">
          <span class="topbar-model-label">{{ currentModelLabel }}</span>
          <button :class="['theme-toggle-button', themeMode === 'light' ? 'theme-toggle-light' : 'theme-toggle-dark']" :title="themeToggleTitle" @click="toggleTheme">
            <span class="theme-toggle-track"><i></i></span>
            <span>{{ themeToggleLabel }}</span>
          </button>
          <button v-if="auth.state.user?.isAdmin" class="topbar-icon-button" @click="navigate('admin')">后台</button>
          <button class="topbar-icon-button" @click="navigate('settings')">设置</button>
          <button class="topbar-icon-button" @click="navigate('profile')">个人</button>
        </div>
      </div>

      <section
        v-if="view !== 'auth' && view !== 'auth-error' && view !== 'settings' && view !== 'profile' && view !== 'admin'"
        :class="['studio-panel', composerUiState.collapsed ? 'studio-panel-composer-collapsed' : 'studio-panel-composer-expanded']"
      >
        <div class="studio-canvas">
          <aside v-if="conversationState.listOpen" class="history-drawer">
            <div class="history-drawer-head">
              <strong>历史记录</strong>
              <button class="button-secondary icon-button" @click="conversationState.listOpen = false">关闭</button>
            </div>
            <div v-if="conversationState.error" class="inline-message inline-danger">{{ conversationState.error }}</div>
            <div v-if="!conversationState.loading && !visibleConversations.length" class="history-empty">No saved conversations yet.</div>
            <button
              v-for="conversation in visibleConversations"
              :key="conversation.id"
              :class="['history-item', conversationState.current?.id === conversation.id ? 'history-item-active' : '']"
              @click="openConversation(conversation.id)"
            >
              <span :class="['history-kind', `history-kind-${conversation.capability}`]">
                {{ CAPABILITY_LABELS[conversation.capability] }}
              </span>
              <strong>{{ conversation.title }}</strong>
              <span class="history-meta">
                <span>{{ formatConversationTime(conversation.updatedAt) }}</span>
                <span>{{ conversation.status || "active" }}</span>
              </span>
            </button>
            <p v-if="!visibleConversations.length" class="muted">当前类型还没有历史记录。</p>
          </aside>

          <div v-if="currentMessages.length" class="conversation-timeline">
            <header class="conversation-header">
              <div>
                <p class="eyebrow">{{ activeCapability ? CAPABILITY_LABELS[activeCapability] : "Conversation" }}</p>
                <h2>{{ conversationState.current?.title || "新对话" }}</h2>
              </div>
              <div class="conversation-header-actions">
                <span class="badge">{{ currentMessages.length }} 条消息</span>
                <span class="badge">{{ conversationState.current?.status || "active" }}</span>
              </div>
            </header>

            <article
              v-for="message in currentMessages"
              :key="message.id"
              :class="['message-card', `message-${message.role}`, `message-status-${message.status}`]"
            >
              <div class="message-meta">
                <span>{{ message.role === "user" ? "你" : "模型" }}</span>
                <span>{{ messageStatusLabel(message) }}</span>
                <span>{{ formatConversationTime(message.createdAt) }}</span>
              </div>
              <div v-if="message.status === 'error'" class="message-error">
                <span>{{ message.errorMessage || "请求失败" }}</span>
                <button v-if="message.canRetry" class="retry-button" title="重新发送" @click="retryMessage(message)">↻</button>
              </div>
              <div
                v-else-if="message.content && message.capability === 'text'"
                class="markdown-preview"
                v-html="markdownPreview(previewMessageContent(message))"
              />
              <p v-else-if="message.content" class="message-content">{{ message.content }}</p>
              <div v-if="message.status === 'processing'" class="long-loading">
                <span class="loader-dot" />
                <span>{{ message.capability === "video" ? "视频任务运行中，可以稍后重新进入历史记录继续查询。" : "模型正在生成，请保持当前会话打开。" }}</span>
                <button v-if="message.capability === 'video'" class="button-secondary" @click="() => handleVideoQuery(message.content)">查询进度</button>
              </div>
              <div v-if="message.assets.length" class="message-assets">
                <article v-for="asset in message.assets" :key="asset.id" class="message-asset-card">
                  <span class="asset-kind-badge">{{ assetDisplayLabel(asset, message) }}</span>
                  <button v-if="asset.assetType === 'image'" class="asset-preview-trigger" @click="openMediaPreview(asset)">
                    <img :src="asset.thumbnailUrl || asset.url" :alt="assetDisplayLabel(asset, message)" />
                  </button>
                  <video v-else-if="asset.assetType === 'video'" :src="asset.url" :poster="asset.thumbnailUrl || undefined" controls playsinline preload="metadata" />
                  <div class="asset-actions">
                    <button class="button-link" @click="openMediaPreview(asset)">查看</button>
                    <button v-if="asset.assetType === 'image'" class="button-secondary" @click="useGeneratedAsset(asset)">引用编辑</button>
                    <button v-if="asset.assetType === 'image'" class="button-secondary" @click="editSelectedAsset(asset)">选取编辑</button>
                    <a class="button-secondary" :href="asset.url" download target="_blank" rel="noreferrer">保存</a>
                  </div>
                </article>
              </div>
            </article>
          </div>

          <div v-else class="empty-canvas">
            <div class="empty-canvas-card">
              <div :class="['hero-model-mark', activeModel && modelIconUrl(activeModel) ? 'hero-model-mark-has-icon' : '']">
                <img v-if="activeModel && modelIconUrl(activeModel)" :src="modelIconUrl(activeModel)" :alt="modelDisplayName(activeModel)" loading="lazy" @error="hideBrokenModelIcon" />
                {{ activeCapability === "text" ? "T" : activeCapability === "image" ? "I" : "V" }}
              </div>
              <div class="empty-canvas-top">
                <span class="badge badge-accent">{{ activeCapability ? CAPABILITY_LABELS[activeCapability] : "创作" }}</span>
                <span :class="['parameter-source-chip', activeModelHasCatalogParameters ? 'parameter-source-chip-exact' : 'parameter-source-chip-generic']">
                  {{ activeModelParameterSourceLabel }}
                </span>
                <span>{{ activeModel ? modelDisplayName(activeModel) : "未选择模型" }}</span>
              </div>
              <h3>{{ activeModel ? modelDisplayName(activeModel) : "创作模型" }}</h3>
              <p class="muted">{{ modelSafeDescription(activeModel) }}</p>
              <div class="canvas-hints">
                <span v-if="view === 'images'">电商海报</span>
                <span v-if="view === 'images'">电影感剧照</span>
                <span v-if="view === 'text'">品牌短句</span>
                <span v-if="view === 'text'">视频脚本</span>
                <span v-if="view === 'videos'">文生视频</span>
                <span v-if="view === 'videos'">首尾帧</span>
              </div>
            </div>
          </div>
        </div>

        <div :class="['composer-card', composerUiState.collapsed ? 'composer-card-collapsed' : 'composer-card-expanded']">
          <div class="composer-handle-row">
            <button
              class="composer-collapse-toggle"
              type="button"
              :aria-expanded="!composerUiState.collapsed"
              @click="toggleComposerCollapsed"
            >
              <span class="composer-collapse-icon">{{ composerUiState.collapsed ? "⌃" : "⌄" }}</span>
              <span>{{ composerUiState.collapsed ? "展开输入" : "收起输入" }}</span>
            </button>
          </div>

          <button
            v-if="composerUiState.collapsed"
            class="composer-compact-bar"
            type="button"
            @click="toggleComposerCollapsed"
          >
            <span class="composer-compact-kind">{{ activeCapability ? CAPABILITY_LABELS[activeCapability] : "创作" }}</span>
            <strong>{{ composerSummary.prompt }}</strong>
            <span class="composer-compact-meta">{{ composerSummary.controls }}</span>
            <span v-if="composerSummary.refs" class="composer-compact-meta">{{ composerSummary.refs }} 张参考图</span>
          </button>

          <template v-else>
          <div class="composer-topline">
            <button class="gameplay-btn">玩法说明</button>
            <div class="composer-status-stack">
              <span :class="['parameter-source-chip', activeModelHasCatalogParameters ? 'parameter-source-chip-exact' : 'parameter-source-chip-generic']">
                {{ activeModelParameterSourceLabel }}
              </span>
              <span>{{ activeModel && activeSetting && isModelConfigured(activeModel, activeSetting) ? "模型已就绪" : "模型待配置" }}</span>
            </div>
          </div>

          <div class="composer-toolbar">
            <div class="template-row">
              <button
                v-for="template in view === 'text' ? TEXT_TEMPLATES : view === 'images' ? IMAGE_TEMPLATES : VIDEO_TEMPLATES"
                :key="template.id"
                class="chip-button"
                @click="applyTemplate(view === 'text' ? textState : view === 'images' ? imageState : videoState, template)"
              >
                {{ template.label }}
              </button>
            </div>
          </div>

          <div v-if="view === 'text'" class="composer-surface">
            <div class="prompt-input-wrap">
              <textarea v-model="textState.prompt" class="composer-input" :placeholder="textComposerPlaceholder" />
              <button class="prompt-ai-button" :disabled="textState.loading || textState.optimizing || !textState.prompt.trim()" title="优化提示词" @click="handlePromptOptimize('text')">
                {{ textState.optimizing ? "..." : "AI" }}
              </button>
            </div>
            <div class="composer-footer-bar">
              <div class="composer-quick-fields">
                <label class="composer-keyword-compact"><span>关键词</span><input v-model="textState.keywords" placeholder="夏日果茶" /></label>
                <label><span>温度</span><input v-model="textState.temperature" /></label>
                <label><span>最大 Token</span><input v-model="textState.maxTokens" /></label>
              </div>
              <button class="composer-submit-button" :disabled="textState.loading" @click="handleTextSubmit">发送</button>
            </div>
            <details class="composer-details">
              <summary>系统提示词与高级 JSON</summary>
              <label class="field field-full"><span>系统提示词</span><textarea v-model="textState.systemPrompt" /></label>
              <label class="field field-full"><span>高级参数 JSON</span><textarea v-model="textState.extraJson" placeholder='例如：{"response_format":{"type":"json_object"}}' /></label>
            </details>
            <div v-if="textState.error" class="inline-message inline-danger">{{ textState.error }}</div>
          </div>

          <div
            v-if="view === 'images'"
            :class="['composer-surface', referenceDropState.image ? 'composer-surface-drop-active' : '']"
            @dragenter.prevent="handleImageDragEnter"
            @dragover.prevent="handleImageDragOver"
            @dragleave="handleImageDragLeave"
            @drop.prevent="handleImageDrop"
          >
            <div v-if="referenceDropState.image" class="composer-drop-hint">
              <strong>松开添加参考图</strong>
              <span>PNG / JPG / WebP</span>
            </div>
            <div class="composer-attach-row media-composer-grid">
              <label class="button-secondary composer-attach-button media-composer-upload">
                {{ imageState.uploading ? "上传中" : "+ 参考图" }}
                <input hidden type="file" accept="image/png,image/jpeg,image/jpg,image/webp" multiple @change="handleImageUpload" />
              </label>
              <div class="prompt-input-wrap">
                <textarea v-model="imageState.prompt" class="composer-input" :placeholder="imageComposerPlaceholder" />
                <button class="prompt-ai-button" :disabled="imageState.loading || imageState.optimizing || !imageState.prompt.trim()" title="优化提示词" @click="handlePromptOptimize('image')">
                  {{ imageState.optimizing ? "..." : "AI" }}
                </button>
              </div>
            </div>
            <div v-if="imageState.references.length" class="reference-strip">
              <article v-for="asset in imageState.references" :key="asset.id" class="reference-thumb">
                <button type="button" class="reference-preview-button" title="查看参考图" @click="openUploadedMediaPreview(asset)">
                  <img :src="asset.localPreviewUrl" :alt="asset.fileName" />
                </button>
                <button type="button" class="reference-remove-button" title="移除参考图" @click.stop="removeImageReference(asset.id)">×</button>
              </article>
            </div>
            <div class="composer-footer-bar">
              <div class="composer-quick-fields composer-quick-fields-wide composer-control-cluster">
                <label class="composer-keyword-compact"><span>关键词</span><input v-model="imageState.keywords" placeholder="玻璃感、青柠色" /></label>
                <div class="composer-popover-anchor">
                  <button
                    :class="['composer-pill', composerUiState.popover === 'image-settings' ? 'composer-pill-active' : '']"
                    :aria-expanded="composerUiState.popover === 'image-settings'"
                    @click="toggleComposerPopover('image-settings')"
                  >
                    {{ imageControlSummary }}
                  </button>
                  <section v-if="composerUiState.popover === 'image-settings'" class="composer-popover image-options-popover">
                    <div class="popover-title-row"><strong>图片参数</strong><button class="button-link" @click="closeComposerPopover">关闭</button></div>
                    <div v-if="imageUsesRatioControls" class="popover-section">
                      <span>图片比例</span>
                      <div class="segmented-grid">
                        <button
                          v-for="ratio in imageRatioOptions"
                          :key="ratio.value"
                          :class="['segmented-option', imageState.ratio === ratio.value ? 'segmented-option-active' : '']"
                          @click="imageState.ratio = ratio.value"
                        >
                          {{ ratio.label }}
                        </button>
                      </div>
                    </div>
                    <div v-if="imageUsesResolutionControls" class="popover-section">
                      <span>分辨率</span>
                      <div class="segmented-grid segmented-grid-compact">
                        <button
                          v-for="resolution in imageResolutionOptions"
                          :key="resolution.value"
                          :class="['segmented-option', imageState.resolution === resolution.value ? 'segmented-option-active' : '']"
                          @click="imageState.resolution = resolution.value"
                        >
                          {{ resolution.label }}
                        </button>
                      </div>
                    </div>
                    <div v-if="imageUsesSizeControls" class="popover-section">
                      <span>尺寸</span>
                      <div class="segmented-grid">
                        <button
                          v-for="size in imageSizeOptions"
                          :key="size.value"
                          :class="['segmented-option', imageState.size === size.value ? 'segmented-option-active' : '']"
                          @click="imageState.size = size.value"
                        >
                          {{ size.label }}
                        </button>
                      </div>
                    </div>
                    <div v-if="imageUsesQualityControls" class="popover-section">
                      <span>质量</span>
                      <div class="segmented-grid segmented-grid-compact">
                        <button
                          v-for="quality in imageQualityOptions"
                          :key="quality.value"
                          :class="['segmented-option', imageState.quality === quality.value ? 'segmented-option-active' : '']"
                          @click="imageState.quality = quality.value"
                        >
                          {{ quality.label }}
                        </button>
                      </div>
                    </div>
                    <div v-if="imageUsesQuantityControls || (!imageHasCatalogParameters && !imageUsesSizeControls)" class="popover-section popover-two-col">
                      <label v-if="imageUsesQuantityControls">
                        <span>生成数量</span>
                        <select v-model="imageState.count">
                          <option v-for="count in imageQuantityOptions" :key="count.value" :value="count.value">{{ count.label }}</option>
                        </select>
                      </label>
                      <label v-if="!imageHasCatalogParameters && !imageUsesSizeControls"><span>尺寸</span><input v-model="imageState.size" placeholder="1024x1024" /></label>
                    </div>
                  </section>
                </div>
                <div class="composer-popover-anchor">
                  <button
                    :class="['composer-pill', composerUiState.popover === 'image-advanced' ? 'composer-pill-active' : '']"
                    :aria-expanded="composerUiState.popover === 'image-advanced'"
                    @click="toggleComposerPopover('image-advanced')"
                  >
                    参考与高级 JSON
                  </button>
                  <section v-if="composerUiState.popover === 'image-advanced'" class="composer-popover composer-popover-wide">
                    <div class="popover-title-row"><strong>参考与高级 JSON</strong><button class="button-link" @click="closeComposerPopover">关闭</button></div>
                    <div v-if="imageState.references.length" class="asset-grid asset-grid-compact">
                      <article v-for="asset in imageState.references" :key="asset.id" class="asset-card">
                        <button type="button" class="asset-card-preview" @click="openUploadedMediaPreview(asset)">
                          <img :src="asset.localPreviewUrl" :alt="asset.fileName" />
                        </button>
                        <div class="asset-card-body"><strong>{{ asset.fileName }}</strong><p class="muted">{{ asset.publicUrl }}</p></div>
                      </article>
                    </div>
                    <p v-else class="muted">还没有上传参考图。</p>
                    <label class="field field-full"><span>高级参数 JSON</span><textarea v-model="imageState.extraJson" /></label>
                  </section>
                </div>
              </div>
              <div class="composer-action-group">
                <button class="composer-submit-button" :disabled="imageState.loading" @click="handleImageSubmit">生成</button>
                <button class="button-secondary composer-query-button" :disabled="imageState.loading || !imageTaskIdFromConversation()" @click="() => handleImageQuery()">查询</button>
              </div>
            </div>
            <div v-if="imageState.error" class="inline-message inline-danger">{{ imageState.error }}</div>
          </div>

          <div
            v-if="view === 'videos'"
            :class="['composer-surface', referenceDropState.video ? 'composer-surface-drop-active' : '']"
            @dragenter.prevent="handleVideoDragEnter"
            @dragover.prevent="handleVideoDragOver"
            @dragleave="handleVideoDragLeave"
            @drop.prevent="handleVideoDrop"
          >
            <div v-if="referenceDropState.video" class="composer-drop-hint">
              <strong>{{ videoDropHint }}</strong>
              <span>PNG / JPG / WebP</span>
            </div>
            <div class="composer-attach-row composer-video-attach-row media-composer-grid">
              <button v-if="supportsUnifiedAdapter(activeModel?.adapter) && videoState.mode === 'text'" class="button-secondary composer-attach-button media-composer-upload" disabled>无需素材</button>
              <label v-else-if="supportsUnifiedAdapter(activeModel?.adapter)" class="button-secondary composer-attach-button media-composer-upload">
                {{ videoState.uploading ? "上传中" : "+ 参考图" }}
                <input hidden type="file" accept="image/png,image/jpeg,image/jpg,image/webp" :multiple="unifiedVideoAllowsMultiple" @change="(event) => uploadVideoFiles(event, 'unified')" />
              </label>
              <label v-if="activeModel?.adapter === 'video-seedance' && videoState.mode === 'reference'" class="button-secondary composer-attach-button media-composer-upload">
                + 参考图
                <input hidden type="file" multiple accept="image/png,image/jpeg,image/jpg,image/webp" @change="(event) => uploadVideoFiles(event, 'seedanceRef')" />
              </label>
              <label v-if="activeModel?.adapter === 'video-seedance' && videoState.mode === 'first-frame'" class="button-secondary composer-attach-button media-composer-upload">
                首帧<input hidden type="file" accept="image/png,image/jpeg,image/jpg,image/webp" @change="(event) => uploadVideoFiles(event, 'first')" />
              </label>
              <div v-if="activeModel?.adapter === 'video-seedance' && videoState.mode === 'start-end'" class="composer-frame-actions media-composer-upload">
                <label class="button-secondary composer-attach-button">首帧<input hidden type="file" accept="image/png,image/jpeg,image/jpg,image/webp" @change="(event) => uploadVideoFiles(event, 'first')" /></label>
                <label class="button-secondary composer-attach-button">尾帧<input hidden type="file" accept="image/png,image/jpeg,image/jpg,image/webp" @change="(event) => uploadVideoFiles(event, 'last')" /></label>
              </div>
              <div class="prompt-input-wrap">
                <textarea v-model="videoState.prompt" class="composer-input" :placeholder="videoComposerPlaceholder" />
                <button class="prompt-ai-button" :disabled="videoState.loading || videoState.optimizing || !videoState.prompt.trim()" title="优化提示词" @click="handlePromptOptimize('video')">
                  {{ videoState.optimizing ? "..." : "AI" }}
                </button>
              </div>
            </div>
            <div v-if="videoState.unifiedImages.length || videoState.seedanceFirst || videoState.seedanceLast || videoState.seedanceReferences.length" class="reference-strip">
              <article v-for="asset in videoState.unifiedImages" :key="asset.id" class="reference-thumb">
                <button type="button" class="reference-preview-button" title="查看参考图" @click="openUploadedMediaPreview(asset)">
                  <img :src="asset.localPreviewUrl" :alt="asset.fileName" />
                </button>
                <button type="button" class="reference-remove-button" title="移除参考图" @click.stop="removeUnifiedVideoReference(asset.id)">×</button>
              </article>
              <article v-if="videoState.seedanceFirst" class="reference-thumb">
                <button type="button" class="reference-preview-button" title="查看首帧" @click="openUploadedMediaPreview(videoState.seedanceFirst, 'first_frame', '首帧')">
                  <img :src="videoState.seedanceFirst.localPreviewUrl" :alt="videoState.seedanceFirst.fileName" />
                </button>
                <span>首帧</span>
                <button type="button" class="reference-remove-button" title="移除首帧" @click.stop="videoState.seedanceFirst = null">×</button>
              </article>
              <article v-if="videoState.seedanceLast" class="reference-thumb">
                <button type="button" class="reference-preview-button" title="查看尾帧" @click="openUploadedMediaPreview(videoState.seedanceLast, 'last_frame', '尾帧')">
                  <img :src="videoState.seedanceLast.localPreviewUrl" :alt="videoState.seedanceLast.fileName" />
                </button>
                <span>尾帧</span>
                <button type="button" class="reference-remove-button" title="移除尾帧" @click.stop="videoState.seedanceLast = null">×</button>
              </article>
              <article v-for="asset in videoState.seedanceReferences" :key="asset.id" class="reference-thumb">
                <button type="button" class="reference-preview-button" title="查看参考图" @click="openUploadedMediaPreview(asset)">
                  <img :src="asset.localPreviewUrl" :alt="asset.fileName" />
                </button>
                <button type="button" class="reference-remove-button" title="移除参考图" @click.stop="removeSeedanceReference(asset.id)">×</button>
              </article>
            </div>
            <div class="composer-footer-bar">
              <div class="composer-quick-fields composer-quick-fields-wide composer-control-cluster">
                <div v-if="videoUsesModeControls" class="composer-popover-anchor">
                  <button
                    :class="['composer-pill', composerUiState.popover === 'video-mode' ? 'composer-pill-active' : '']"
                    :aria-expanded="composerUiState.popover === 'video-mode'"
                    @click="toggleComposerPopover('video-mode')"
                  >
                    {{ videoModeLabel(videoState.mode) }}
                  </button>
                  <section v-if="composerUiState.popover === 'video-mode'" class="composer-popover composer-menu-popover">
                    <strong>生成模式</strong>
                    <button
                      v-for="mode in videoModeOptions"
                      :key="mode.value"
                      :class="['composer-menu-option', videoState.mode === mode.value ? 'composer-menu-option-active' : '']"
                      @click="selectVideoMode(mode.value)"
                    >
                      {{ mode.label }}
                    </button>
                  </section>
                </div>
                <label class="composer-keyword-compact"><span>关键词</span><input v-model="videoState.keywords" /></label>
                <div class="composer-popover-anchor">
                  <button
                    :class="['composer-pill', composerUiState.popover === 'video-settings' ? 'composer-pill-active' : '']"
                    :aria-expanded="composerUiState.popover === 'video-settings'"
                    @click="toggleComposerPopover('video-settings')"
                  >
                    {{ videoControlSummary }}
                  </button>
                  <section v-if="composerUiState.popover === 'video-settings'" class="composer-popover video-options-popover">
                    <div class="popover-title-row"><strong>视频参数</strong><button class="button-link" @click="closeComposerPopover">关闭</button></div>
                    <div v-if="videoUsesRatioControls" class="popover-section">
                      <span>视频比例</span>
                      <div class="segmented-grid">
                        <button
                          v-for="ratio in videoRatioOptions"
                          :key="ratio.value"
                          :class="['segmented-option', videoState.aspectRatio === ratio.value ? 'segmented-option-active' : '']"
                          @click="videoState.aspectRatio = ratio.value"
                        >
                          {{ ratio.label }}
                        </button>
                      </div>
                    </div>
                    <div v-if="videoUsesResolutionControls" class="popover-section">
                      <span>分辨率</span>
                      <div class="segmented-grid segmented-grid-compact">
                        <button
                          v-for="resolution in videoResolutionOptions"
                          :key="resolution.value"
                          :class="['segmented-option', videoState.resolution === resolution.value ? 'segmented-option-active' : '']"
                          @click="videoState.resolution = resolution.value"
                        >
                          {{ resolution.label }}
                        </button>
                      </div>
                    </div>
                    <div v-if="videoUsesDurationControls" class="popover-section">
                      <span>视频时长</span>
                      <div class="segmented-grid segmented-grid-duration">
                        <button
                          v-for="duration in videoDurationOptions"
                          :key="duration.value"
                          :class="['segmented-option', videoState.duration === duration.value ? 'segmented-option-active' : '']"
                          @click="videoState.duration = duration.value"
                        >
                          {{ duration.label }}
                        </button>
                      </div>
                    </div>
                    <div v-if="videoUsesQuantityControls || videoUsesSeedControls" class="popover-section popover-two-col">
                      <label v-if="videoUsesQuantityControls">
                        <span>生成数量</span>
                        <select v-model="videoState.count">
                          <option v-for="count in videoQuantityOptions" :key="count.value" :value="count.value">{{ count.label }}</option>
                        </select>
                      </label>
                      <label v-if="videoUsesSeedControls"><span>种子</span><input v-model="videoState.seed" /></label>
                    </div>
                    <label v-if="videoUsesAudioControls" class="checkbox-inline"><input v-model="videoState.audio" type="checkbox" />生成音频</label>
                  </section>
                </div>
                <div class="composer-popover-anchor">
                  <button
                    :class="['composer-pill', composerUiState.popover === 'video-advanced' ? 'composer-pill-active' : '']"
                    :aria-expanded="composerUiState.popover === 'video-advanced'"
                    @click="toggleComposerPopover('video-advanced')"
                  >
                    参考与高级 JSON
                  </button>
                  <section v-if="composerUiState.popover === 'video-advanced'" class="composer-popover composer-popover-wide">
                    <div class="popover-title-row"><strong>参考与高级 JSON</strong><button class="button-link" @click="closeComposerPopover">关闭</button></div>
                    <label class="field field-full"><span>高级参数 JSON</span><textarea v-model="videoState.extraJson" /></label>
                    <label class="checkbox-inline"><input v-model="videoState.autoPoll" type="checkbox" />自动轮询</label>
                    <label class="checkbox-inline"><input v-model="videoState.upsample" type="checkbox" />增强清晰度</label>
                  </section>
                </div>
              </div>
              <div class="composer-video-actions composer-action-group">
                <button class="composer-submit-button" :disabled="videoState.loading" @click="handleVideoCreate">创建</button>
                <button class="button-secondary composer-query-button" :disabled="videoState.querying || !videoState.createResult?.taskId" @click="() => handleVideoQuery()">查询</button>
              </div>
            </div>
            <div v-if="videoState.error" class="inline-message inline-danger">{{ videoState.error }}</div>
          </div>
          </template>
        </div>
      </section>

      <section v-else-if="view === 'auth'" class="auth-page">
        <section class="auth-panel">
          <div class="auth-copy auth-value-panel">
            <p class="eyebrow">Account</p>
            <h2>登录 创意工坊</h2>
            <p class="muted">账号、密钥、模型、子模型和创作记录都会按用户隔离保存。官网创意工坊跳转过来的 code 登录仍然保留。</p>
            <div class="auth-security-list">
              <span>HttpOnly 会话 cookie</span>
              <span>Argon2 密码哈希</span>
              <span>CSRF 写请求保护</span>
            </div>
          </div>

          <div class="auth-card">
            <div class="auth-tabs">
              <button :class="authMode === 'login' ? 'auth-tab-active' : ''" @click="authMode = 'login'">登录</button>
              <button :class="authMode === 'register' ? 'auth-tab-active' : ''" @click="authMode = 'register'">注册</button>
            </div>

            <form v-if="authMode === 'login'" class="auth-form" @submit.prevent="handlePasswordLogin">
              <label class="field">
                <span>邮箱或手机号</span>
                <input v-model="authForm.identifier" autocomplete="username" placeholder="name@example.com" />
              </label>
              <label class="field">
                <span>密码</span>
                <input v-model="authForm.password" autocomplete="current-password" type="password" placeholder="至少 8 位" />
              </label>
              <button :disabled="auth.state.loading || !authForm.identifier || !authForm.password" type="submit">
                {{ auth.state.loading ? "登录中..." : "登录" }}
              </button>
            </form>

            <form v-else class="auth-form" @submit.prevent="handleRegister">
              <label class="field">
                <span>邮箱</span>
                <input v-model="authForm.email" autocomplete="email" placeholder="name@example.com" />
              </label>
              <label class="field">
                <span>手机号</span>
                <input v-model="authForm.phone" autocomplete="tel" placeholder="可选" />
              </label>
              <label class="field">
                <span>昵称</span>
                <input v-model="authForm.nickname" autocomplete="name" placeholder="创作者名称" />
              </label>
              <label class="field">
                <span>密码</span>
                <input v-model="authForm.registerPassword" autocomplete="new-password" type="password" placeholder="至少 8 位，包含字母和数字" />
              </label>
              <button :disabled="auth.state.loading || (!authForm.email && !authForm.phone) || !authForm.registerPassword" type="submit">
                {{ auth.state.loading ? "注册中..." : "注册并登录" }}
              </button>
            </form>

            <div v-if="authForm.error || auth.state.error" class="inline-message inline-danger">{{ authForm.error || auth.state.error }}</div>

            <div v-if="showDevAuth" class="auth-code-block">
              <div>
                <strong>官网授权 code</strong>
                <span>用于官网登录后跳转到子站自动登录。</span>
              </div>
              <div class="auth-code-form">
                <input v-model="devAuthCode" placeholder="dev:alice" @keyup.enter="handleAuthCodeLogin" />
                <button class="button-secondary" type="button" @click="handleAuthCodeLogin">授权登录</button>
              </div>
              <div class="settings-row-actions">
                <button class="button-secondary" type="button" @click="devAuthCode = 'dev:alice'">Alice</button>
                <button class="button-secondary" type="button" @click="devAuthCode = 'dev:bob'">Bob</button>
                <button class="button-secondary" type="button" @click="devAuthCode = 'dev:carol'">Carol</button>
                <button class="button-secondary" type="button" :disabled="auth.state.loading" @click="handleDevLogin">开发登录</button>
              </div>
            </div>
            <div v-else class="auth-code-block auth-official-only">
              <div>
                <strong>Official SSO</strong>
                <span>从官网进入创意工坊，回调地址为 /auth/callback?code=xxx。</span>
              </div>
            </div>
          </div>
        </section>
      </section>

      <section v-else-if="view === 'auth-error'" class="auth-page">
        <section class="auth-panel auth-error-panel">
          <div class="auth-copy auth-value-panel">
            <div>
              <p class="eyebrow">SSO</p>
              <h2>Authorization failed</h2>
              <p class="muted">{{ authErrorMessage() }}</p>
            </div>
            <button @click="navigate('auth')">Back to login</button>
          </div>
        </section>
      </section>

      <section v-else-if="view === 'profile'" class="settings-page profile-page">
        <section class="settings-hero profile-hero">
          <div>
            <p class="eyebrow">Profile</p>
            <h2>个人信息</h2>
            <p class="muted">当前账号的密钥、模型、子模型和创作历史都会按用户隔离保存。</p>
          </div>
          <div class="profile-card">
            <div class="profile-avatar">{{ auth.state.user?.nickname?.slice(0, 1) || "G" }}</div>
            <strong>{{ auth.state.user?.nickname || "未登录用户" }}</strong>
            <span>{{ userAccountLabel }}</span>
          </div>
        </section>

        <section class="settings-list-panel profile-grid">
          <article class="profile-stat">
            <span>用户 ID</span>
            <strong>{{ auth.state.user?.externalUserId || "-" }}</strong>
          </article>
          <article class="profile-stat">
            <span>已保存模型</span>
            <strong>{{ store.models.value.length }}</strong>
          </article>
          <article class="profile-stat">
            <span>已配置模型</span>
            <strong>{{ configuredCount }}</strong>
          </article>
          <article class="profile-stat">
            <span>历史对话</span>
            <strong>{{ conversationState.conversations.length }}</strong>
          </article>
        </section>

        <section class="settings-list-panel profile-editor">
          <div class="settings-list-toolbar">
            <div class="settings-toolbar-copy">
              <strong>账号资料</strong>
              <span>本地注册账号和官网授权账号共用同一个用户资料，模型与创作记录继续按用户隔离。</span>
            </div>
            <div class="settings-row-actions">
              <button class="button-secondary" :disabled="!auth.state.user || auth.state.loading" @click="handleProfileSave">
                {{ auth.state.loading ? "保存中..." : "保存资料" }}
              </button>
              <button v-if="auth.state.user" class="button-danger" :disabled="auth.state.loading" @click="handleLogout">退出登录</button>
              <button v-else @click="navigate('auth')">去登录</button>
            </div>
          </div>
          <div class="profile-form-grid">
            <label class="field">
              <span>昵称</span>
              <input v-model="profileForm.nickname" :disabled="!auth.state.user" placeholder="创作者名称" />
            </label>
            <label class="field">
              <span>手机号</span>
              <input v-model="profileForm.phone" :disabled="!auth.state.user" placeholder="可选" />
            </label>
            <label class="field field-full">
              <span>头像 URL</span>
              <input v-model="profileForm.avatarUrl" :disabled="!auth.state.user" placeholder="https://..." />
            </label>
          </div>
          <div v-if="profileForm.error" class="inline-message inline-danger">{{ profileForm.error }}</div>
          <div v-if="profileForm.success" class="inline-message inline-success">{{ profileForm.success }}</div>
        </section>

        <section v-if="showDevAuth" class="settings-list-panel profile-actions">
          <div>
            <h3>官网授权回跳</h3>
            <p class="muted">正式环境使用官网生成的短期 code 访问 /auth/callback?code=xxx；本地测试可输入 dev:alice、dev:bob、dev:carol 模拟多个用户。</p>
          </div>
          <div class="auth-code-form">
            <label class="field">
              <span>授权 code</span>
              <input v-model="devAuthCode" placeholder="dev:alice" @keyup.enter="handleAuthCodeLogin" />
            </label>
            <button @click="handleAuthCodeLogin">授权登录</button>
          </div>
          <div class="settings-row-actions">
            <button class="button-secondary" @click="devAuthCode = 'dev:alice'">Alice</button>
            <button class="button-secondary" @click="devAuthCode = 'dev:bob'">Bob</button>
            <button class="button-secondary" @click="devAuthCode = 'dev:carol'">Carol</button>
            <button class="button-secondary" @click="refreshConversations">刷新历史</button>
          </div>
        </section>
        <section v-else class="settings-list-panel profile-actions">
          <div>
            <h3>Official SSO callback</h3>
            <p class="muted">Production login is created by the official site redirecting to /auth/callback?code=xxx. Manual code entry is disabled outside development.</p>
          </div>
          <div class="settings-row-actions">
            <button class="button-secondary" @click="refreshConversations">Refresh history</button>
          </div>
        </section>
      </section>

      <section v-else-if="view === 'admin'" class="admin-page">
        <section v-if="!auth.state.user?.isAdmin" class="admin-denied">
          <p class="eyebrow">Admin Console</p>
          <h2>需要管理员权限</h2>
          <p class="muted">当前账号没有后台管理权限。普通用户可以继续使用创作页面和模型设置页。</p>
          <button @click="navigate('images')">返回创作台</button>
        </section>

        <div v-else class="admin-console">
          <aside class="admin-sidebar">
            <div class="admin-sidebar-brand">
              <div class="admin-brand-mark">
                <img src="/brand/cylon-studio-mark.png" alt="创意工坊" />
              </div>
              <div>
                <strong>创意工坊</strong>
                <span>Admin Console</span>
              </div>
            </div>

            <div class="admin-sidebar-status">
              <span>当前管理员</span>
              <strong>{{ auth.state.user?.nickname || auth.state.user?.email || "管理员" }}</strong>
              <small>{{ auth.state.user?.email || "本地控制台" }}</small>
            </div>

            <nav class="admin-tabs" aria-label="后台功能">
              <section v-for="group in adminNavGroups" :key="group.title" class="admin-nav-group">
                <p>{{ group.title }}</p>
                <button
                  v-for="tabValue in group.tabs"
                  :key="tabValue"
                  :class="['admin-tab', adminState.activeTab === tabValue ? 'admin-tab-active' : '']"
                  @click="switchAdminTab(tabValue)"
                >
                  <span :class="['admin-nav-icon', `admin-nav-icon-${adminTabs.find((tab) => tab.value === tabValue)?.icon || 'dot'}`]"></span>
                  <span class="admin-nav-copy">
                    <strong>{{ adminTabs.find((tab) => tab.value === tabValue)?.label }}</strong>
                    <span>{{ adminTabs.find((tab) => tab.value === tabValue)?.hint }}</span>
                  </span>
                </button>
              </section>
            </nav>

            <div class="admin-sidebar-footer">
              <span>studio.cylonai.cn</span>
              <button class="button-secondary" @click="navigate('images')">返回创作台</button>
            </div>
          </aside>

          <section class="admin-console-main">
            <header class="admin-topbar">
              <div>
                <p class="eyebrow">Creative Workshop Console</p>
                <h2>{{ adminActiveTab.label }}</h2>
                <p class="muted">{{ adminActiveTab.hint }}</p>
              </div>
              <div class="admin-topbar-actions">
                <span class="admin-env-pill"><i></i> studio.cylonai.cn</span>
                <span class="admin-user-pill">{{ auth.state.user?.email || "admin" }}<small>管理员</small></span>
                <button :class="['theme-toggle-button', themeMode === 'light' ? 'theme-toggle-light' : 'theme-toggle-dark']" :title="themeToggleTitle" @click="toggleTheme">
                  <span class="theme-toggle-track"><i></i></span>
                  <span>{{ themeToggleLabel }}</span>
                </button>
                <button class="button-secondary" :disabled="adminState.loading" @click="loadAdminTab()">刷新当前页</button>
              </div>
            </header>

            <main class="admin-content">
              <div v-if="adminState.error" class="inline-message inline-danger">{{ adminState.error }}</div>
              <div v-if="adminState.loading" class="admin-loading">加载中...</div>
              <section class="admin-insight-strip" aria-label="当前页面巡检建议">
                <article>
                  <span>当前模块</span>
                  <strong>{{ adminActiveTab.label }}</strong>
                  <small>{{ adminActiveTab.hint }}</small>
                </article>
                <article v-for="suggestion in ADMIN_PAGE_SUGGESTIONS[adminState.activeTab]" :key="suggestion">
                  <span>优化建议</span>
                  <strong>{{ suggestion }}</strong>
                </article>
              </section>

              <template v-if="adminState.activeTab === 'overview'">
                <div class="admin-section-head">
                  <div>
                    <h3>运营面板</h3>
                    <p class="muted">按用户、模型、能力和调用状态查看公用模型与私有模型的使用情况。</p>
                  </div>
                  <button class="button-secondary" @click="loadAdminOverview">刷新统计</button>
                </div>

                <div class="admin-metrics admin-metrics-hero">
                  <article class="admin-metric admin-metric-primary">
                    <span><i>API</i> 总调用</span>
                    <strong>{{ formatAdminNumber(adminState.overview?.totalCalls) }}</strong>
                    <small>全部创作请求</small>
                  </article>
                  <article class="admin-metric">
                    <span><i>OK</i> 成功</span>
                    <strong>{{ formatAdminNumber(adminState.overview?.successCalls) }}</strong>
                    <small>{{ adminPercentLabel(adminSuccessRate) }} 成功率</small>
                  </article>
                  <article class="admin-metric admin-metric-alert">
                    <span><i>ERR</i> 失败</span>
                    <strong>{{ formatAdminNumber(adminState.overview?.failedCalls) }}</strong>
                    <small>{{ adminPercentLabel(adminFailurePercent) }} 失败率</small>
                  </article>
                  <article class="admin-metric">
                    <span><i>AVG</i> 平均响应</span>
                    <strong>{{ adminAverageDuration }}</strong>
                    <small>服务端记录耗时</small>
                  </article>
                  <article class="admin-metric">
                    <span><i>PUB</i> 公用模型调用</span>
                    <strong>{{ formatAdminNumber(adminState.overview?.publicModelCalls) }}</strong>
                    <small>管理员发布模型</small>
                  </article>
                  <article class="admin-metric">
                    <span><i>PRI</i> 私有模型调用</span>
                    <strong>{{ formatAdminNumber(adminState.overview?.privateModelCalls) }}</strong>
                    <small>用户自有模型</small>
                  </article>
                  <article class="admin-metric">
                    <span><i>QTA</i> 额度消耗</span>
                    <strong>{{ formatAdminQuota(adminState.overview?.quotaUnits) }}</strong>
                    <small>从调用日志推算</small>
                  </article>
                  <article class="admin-metric">
                    <span><i>QUE</i> 平均排队</span>
                    <strong>{{ formatAdminDuration(adminState.overview?.averageQueueMs) }}</strong>
                    <small>有队列字段时统计</small>
                  </article>
                  <article class="admin-metric admin-metric-alert">
                    <span><i>TO</i> 超时率</span>
                    <strong>{{ adminPercentLabel(adminTimeoutPercent) }}</strong>
                    <small>{{ formatAdminNumber(adminState.overview?.timeoutCalls) }} 次疑似超时</small>
                  </article>
                </div>

                <div class="admin-ops-grid admin-console-dashboard">
                  <section class="admin-subpanel admin-chart-card admin-wide-panel">
                    <div class="admin-subpanel-head">
                      <h4>调用趋势</h4>
                      <div class="admin-segmented">
                        <button :class="adminState.trendPeriod === 'day' ? 'active' : ''" @click="adminState.trendPeriod = 'day'">日</button>
                        <button :class="adminState.trendPeriod === 'week' ? 'active' : ''" @click="adminState.trendPeriod = 'week'">周</button>
                        <button :class="adminState.trendPeriod === 'month' ? 'active' : ''" @click="adminState.trendPeriod = 'month'">月</button>
                      </div>
                    </div>
                    <div class="admin-trend-chart">
                      <div v-for="point in adminTrendPoints" :key="`${adminState.trendPeriod}-${point.label}`" class="admin-trend-column">
                        <div class="admin-trend-stack">
                          <i class="admin-trend-success" :style="{ height: adminTrendHeight(point.successCalls) }"></i>
                          <i v-if="point.failedCalls" class="admin-trend-failed" :style="{ height: adminTrendHeight(point.failedCalls) }"></i>
                        </div>
                        <strong>{{ formatAdminNumber(point.totalCalls) }}</strong>
                        <span>{{ point.label }}</span>
                      </div>
                    </div>
                    <div class="admin-trend-foot">
                      <span>绿色为成功，红色为失败；额度与耗时来自后端日志聚合。</span>
                      <strong>本周期额度 {{ formatAdminQuota(adminTrendPoints.reduce((sum, point) => sum + (point.quotaUnits || 0), 0)) }}</strong>
                    </div>
                  </section>

                  <section class="admin-subpanel admin-chart-card">
                    <div class="admin-subpanel-head">
                      <h4>失败模型联动</h4>
                      <span>Failed models</span>
                    </div>
                    <div class="admin-failed-model-list">
                      <button
                        v-for="row in adminFailedModels"
                        :key="row.modelGroupId"
                        class="admin-failed-model"
                        @click="adminApplyFailedModelFilter(row)"
                      >
                        <strong>{{ row.modelName }}</strong>
                        <span>{{ adminCapabilityLabel(row.capability) }} / 失败 {{ formatAdminNumber(row.failedCalls) }} / {{ adminPercentLabel((row.failureRate || 0) * 100) }}</span>
                        <small>{{ row.lastError || "点击查看相关记录" }}</small>
                      </button>
                      <p v-if="!adminFailedModels.length" class="admin-empty">暂无失败模型样本</p>
                    </div>
                  </section>

                  <section class="admin-subpanel admin-chart-card">
                    <div class="admin-subpanel-head">
                      <h4>调用状态</h4>
                      <span>Success / Error</span>
                    </div>
                    <div class="admin-donut-layout">
                      <div class="admin-donut" :style="{ background: adminDonutGradient(adminStatusDonutSegments) }">
                        <span>{{ adminPercentLabel(adminSuccessRate) }}</span>
                        <small>成功率</small>
                      </div>
                      <div class="admin-chart-legend">
                        <div v-for="segment in adminStatusDonutSegments" :key="segment.label" class="admin-legend-row">
                          <i :style="{ backgroundColor: segment.color }"></i>
                          <span>{{ segment.label }}</span>
                          <strong>{{ formatAdminNumber(segment.value) }}</strong>
                          <small>{{ adminPercentLabel(adminRatio(segment.value, adminOverviewTotal)) }}</small>
                        </div>
                      </div>
                    </div>
                  </section>

                  <section class="admin-subpanel admin-chart-card">
                    <div class="admin-subpanel-head">
                      <h4>模型归属</h4>
                      <span>Public / Private</span>
                    </div>
                    <div class="admin-donut-layout">
                      <div class="admin-donut admin-donut-alt" :style="{ background: adminDonutGradient(adminOwnershipDonutSegments) }">
                        <span>{{ formatAdminNumber(adminState.overview?.publicModelCalls) }}</span>
                        <small>公用调用</small>
                      </div>
                      <div class="admin-chart-legend">
                        <div v-for="segment in adminOwnershipDonutSegments" :key="segment.label" class="admin-legend-row">
                          <i :style="{ backgroundColor: segment.color }"></i>
                          <span>{{ segment.label }}</span>
                          <strong>{{ formatAdminNumber(segment.value) }}</strong>
                          <small>{{ adminPercentLabel(adminRatio(segment.value, adminOverviewTotal)) }}</small>
                        </div>
                      </div>
                    </div>
                  </section>

                  <section class="admin-subpanel admin-chart-card">
                    <div class="admin-subpanel-head">
                      <h4>能力分布</h4>
                      <span>Text / Image / Video</span>
                    </div>
                    <div class="admin-progress-list">
                      <div v-for="row in adminCapabilityRows" :key="row.capability" class="admin-progress-row">
                        <div>
                          <span>{{ row.label }}</span>
                          <strong>{{ formatAdminNumber(row.total) }}</strong>
                        </div>
                        <div class="admin-progress-track">
                          <i :class="`admin-progress-${row.capability}`" :style="{ width: adminBarWidth(row.total, adminOverviewTotal) }"></i>
                        </div>
                        <small>{{ adminPercentLabel(row.percent) }}</small>
                      </div>
                    </div>
                  </section>

                  <section class="admin-subpanel admin-chart-card">
                    <div class="admin-subpanel-head">
                      <h4>慢响应模型</h4>
                      <span>Slowest models</span>
                    </div>
                    <div class="admin-slow-list">
                      <div v-for="row in adminSlowModels" :key="row.model.id" class="admin-slow-row">
                        <div>
                          <strong>{{ modelDisplayName(mapServerModel(row.model)) }}</strong>
                          <span>{{ formatAdminNumber(row.totalCalls) }} 次调用</span>
                        </div>
                        <b>{{ formatAdminDuration(row.averageDurationMs) }}</b>
                      </div>
                      <p v-if="!adminSlowModels.length" class="admin-empty">暂无慢响应数据</p>
                    </div>
                  </section>

                  <section class="admin-subpanel admin-chart-card admin-wide-panel">
                    <div class="admin-subpanel-head">
                      <h4>模型调用 Top 8</h4>
                      <span>Top models</span>
                    </div>
                    <div class="admin-bar-list">
                      <div v-for="row in adminTopModels" :key="row.model.id" class="admin-bar-row">
                        <div class="admin-bar-label">
                          <strong>{{ modelDisplayName(mapServerModel(row.model)) }}</strong>
                          <span>{{ CAPABILITY_LABELS[row.model.capability] }} / 成功 {{ formatAdminNumber(row.successCalls) }} / 失败 {{ formatAdminNumber(row.failedCalls) }}</span>
                        </div>
                        <div class="admin-bar-track"><i :style="{ width: adminBarWidth(row.totalCalls, adminMaxModelCalls) }"></i></div>
                        <b>{{ formatAdminNumber(row.totalCalls) }}</b>
                      </div>
                      <p v-if="!adminTopModels.length" class="admin-empty">暂无模型调用数据</p>
                    </div>
                  </section>

                  <section class="admin-subpanel admin-chart-card admin-wide-panel">
                    <div class="admin-subpanel-head">
                      <h4>用户调用 Top 8</h4>
                      <span>Top users</span>
                    </div>
                    <div class="admin-user-rank-list">
                      <div v-for="row in adminTopUsers" :key="row.user.id" class="admin-user-rank-row">
                        <div class="admin-user-cell">
                          <div class="admin-user-avatar">{{ (row.user.nickname || row.user.email || "U").slice(0, 1) }}</div>
                          <div>
                            <strong>{{ adminUserLabel(row.user) }}</strong>
                            <small>公用 {{ formatAdminNumber(row.publicModelCalls) }} / 私有 {{ formatAdminNumber(row.privateModelCalls) }} / 失败 {{ formatAdminNumber(row.failedCalls) }}</small>
                          </div>
                        </div>
                        <div class="admin-bar-track"><i :style="{ width: adminBarWidth(row.totalCalls, adminMaxUserCalls) }"></i></div>
                        <b>{{ formatAdminNumber(row.totalCalls) }}</b>
                      </div>
                      <p v-if="!adminTopUsers.length" class="admin-empty">暂无用户调用数据</p>
                    </div>
                  </section>
                </div>
              </template>

              <template v-else-if="adminState.activeTab === 'models'">
                <div class="admin-section-head">
                  <div>
                    <h3>公用模型配置</h3>
                    <p class="muted">发布公用模型、维护展示名称、图标、默认 hint、AI 文案优化开关和默认参数。</p>
                  </div>
                  <button class="button-secondary" @click="loadAdminModels">刷新模型</button>
                </div>

                <div class="admin-mini-metrics">
                  <article><span>模型总数</span><strong>{{ formatAdminNumber(adminState.models.length) }}</strong><small>当前筛选结果</small></article>
                  <article><span>公用模型</span><strong>{{ formatAdminNumber(adminPublicModelCount) }}</strong><small>所有用户可见</small></article>
                  <article><span>私有模型</span><strong>{{ formatAdminNumber(adminPrivateModelCount) }}</strong><small>管理员未发布</small></article>
                  <article><span>提示优化</span><strong>{{ formatAdminNumber(adminState.models.filter((model) => model.promptOptimizeEnabled !== false).length) }}</strong><small>AI 图标可用</small></article>
                </div>

                <div class="admin-toolbar admin-command-panel">
                  <div class="settings-filter-tabs" role="tablist" aria-label="后台模型分组">
                    <button
                      v-for="tab in adminCapabilityTabs"
                      :key="tab.value"
                      :class="['settings-filter-tab', adminState.modelCapability === tab.value ? 'settings-filter-tab-active' : '']"
                      @click="adminState.modelCapability = tab.value; loadAdminModels()"
                    >
                      {{ tab.label }}
                    </button>
                  </div>
                  <select v-model="adminState.modelPublicState" @change="loadAdminModels">
                    <option value="all">全部状态</option>
                    <option value="public">仅公用</option>
                    <option value="private">仅私有</option>
                  </select>
                  <label class="settings-search-box admin-search">
                    <span>搜索</span>
                    <input v-model="adminState.modelSearch" placeholder="模型名称、厂商、备注" @keyup.enter="loadAdminModels" />
                  </label>
                  <button class="button-secondary" @click="loadAdminModels">筛选</button>
                </div>

                <div class="admin-bulk-bar admin-command-panel admin-command-panel-secondary">
                  <label class="admin-check">
                    <input :checked="adminAllVisibleModelsSelected" type="checkbox" @change="toggleAdminSelectAllModels" />
                    选择当前列表
                  </label>
                  <span>已选择 {{ formatAdminNumber(adminSelectedModels.length) }} 个模型</span>
                  <button class="button-secondary" :disabled="!adminSelectedModels.length || adminState.saving === 'bulk-public'" @click="bulkSetAdminPublicState(true)">批量设为公用</button>
                  <button class="button-secondary" :disabled="!adminSelectedModels.length || adminState.saving === 'bulk-public'" @click="bulkSetAdminPublicState(false)">批量取消公用</button>
                  <button class="button-secondary" :disabled="!adminSelectedModels.length || adminState.saving === 'bulk-prompt'" @click="bulkSetAdminPromptOptimize(true)">批量启用 AI 文案</button>
                  <button class="button-secondary" :disabled="!adminSelectedModels.length || adminState.saving === 'bulk-prompt'" @click="bulkSetAdminPromptOptimize(false)">批量禁用 AI 文案</button>
                </div>

                <div class="admin-data-table admin-model-table admin-list-shell">
                  <div class="admin-data-row admin-data-head">
                    <span>选择</span><span>模型</span><span>能力</span><span>公开状态</span><span>主模型</span><span>提示优化</span><span>操作</span>
                  </div>
                  <article v-for="model in adminState.models" :key="model.id" class="admin-data-row admin-model-row">
                    <label class="admin-row-check">
                      <input :checked="adminState.selectedModelIds.includes(model.id)" type="checkbox" @change="toggleAdminModelSelection(model.id)" />
                    </label>
                    <div class="admin-model-cell">
                      <div :class="['model-avatar', `model-avatar-${model.capability}`, modelIconUrl(model) ? 'model-avatar-has-icon' : '']">
                        <img
                          v-if="modelIconUrl(model)"
                          :src="modelIconUrl(model)"
                          :alt="modelDisplayName(model)"
                          loading="lazy"
                          @error="markAdminIconFailed(model, $event)"
                          @load="clearAdminIconError(model)"
                        />
                        <span>{{ model.capability === 'text' ? 'T' : model.capability === 'image' ? 'I' : 'V' }}</span>
                      </div>
                      <div>
                        <strong>{{ modelDisplayName(model) }}</strong>
                        <small>{{ model.vendor || "-" }}</small>
                      </div>
                    </div>
                    <span class="badge">{{ CAPABILITY_LABELS[model.capability] }}</span>
                    <span :class="['badge', model.isPublic ? 'badge-success' : 'badge-warn']">{{ model.isPublic ? "公用" : "私有" }}</span>
                    <span class="admin-truncate">{{ resolveModelName(model, getSetting(model.id)) || "未选择主模型" }}</span>
                    <span :class="['badge', model.promptOptimizeEnabled === false ? 'badge-warn' : 'badge-success']">{{ model.promptOptimizeEnabled === false ? "禁用" : "启用" }}</span>
                    <div class="admin-action-cell">
                      <button class="button-secondary" @click="editAdminModel(model)">{{ adminState.editingModelId === model.id ? "收起" : "编辑配置" }}</button>
                      <button :class="model.isPublic ? 'button-danger' : ''" :disabled="adminState.saving === `${model.id}:public`" @click="toggleAdminPublicModel(model)">
                        {{ model.isPublic ? "取消公用" : "设为公用" }}
                      </button>
                    </div>
                    <div v-if="adminState.editingModelId === model.id && adminState.modelDrafts[model.id]" class="admin-row-editor admin-model-form">
                      <label><span>公用展示名</span><input v-model="adminState.modelDrafts[model.id].publicDisplayName" /></label>
                      <label><span>图标 URL</span><input v-model="adminState.modelDrafts[model.id].iconUrl" placeholder="https://...svg" @input="clearAdminIconError(model)" /></label>
                      <div class="admin-icon-preview">
                        <div :class="['model-avatar', `model-avatar-${model.capability}`, adminState.modelDrafts[model.id].iconUrl ? 'model-avatar-has-icon' : '']">
                          <img
                            v-if="adminState.modelDrafts[model.id].iconUrl"
                            :src="adminState.modelDrafts[model.id].iconUrl"
                            alt="模型图标预览"
                            @error="markAdminIconFailed(model, $event)"
                            @load="clearAdminIconError(model)"
                          />
                          <span>{{ model.capability === 'text' ? 'T' : model.capability === 'image' ? 'I' : 'V' }}</span>
                        </div>
                        <small :class="adminIconError(model) ? 'admin-inline-error' : ''">{{ adminIconError(model) || "图标会展示在模型列表和聊天输入区。" }}</small>
                      </div>
                      <label class="field-full"><span>公用描述</span><textarea v-model="adminState.modelDrafts[model.id].publicDescription" rows="3" /></label>
                      <label class="field-full"><span>输入框默认提示语 hint</span><textarea v-model="adminState.modelDrafts[model.id].inputHint" rows="3" /></label>
                      <label><span>标签</span><input v-model="adminState.modelDrafts[model.id].publicTagsText" placeholder="公用, 推荐" /></label>
                      <label class="admin-check"><input v-model="adminState.modelDrafts[model.id].promptOptimizeEnabled" type="checkbox" /> 启用 AI 文案优化</label>
                      <div class="admin-param-editor field-full">
                        <div class="admin-param-editor-head">
                          <span>默认参数结构化表单</span>
                          <button class="button-secondary" type="button" @click="addAdminDefaultParameter(model)">添加参数</button>
                        </div>
                        <div v-if="adminDefaultParameterRows(model).length" class="admin-param-grid">
                          <label v-for="row in adminDefaultParameterRows(model)" :key="row.key">
                            <span>{{ row.key }}</span>
                            <input :value="row.value" @input="setAdminDefaultParameterFromEvent(model, row.key, $event)" />
                          </label>
                        </div>
                        <p v-else class="muted">暂无默认参数。可以添加常用参数，或直接编辑下面的高级 JSON。</p>
                      </div>
                      <label class="field-full"><span>默认参数 JSON</span><textarea v-model="adminState.modelDrafts[model.id].defaultParametersText" rows="5" /></label>
                      <div class="admin-row-actions field-full">
                        <button :disabled="adminState.saving === model.id" @click="saveAdminModel(model)">保存配置</button>
                        <button class="button-secondary" @click="cancelAdminModelEdit(model)">取消</button>
                      </div>
                    </div>
                  </article>
                  <p v-if="!adminState.models.length" class="admin-empty">暂无匹配模型</p>
                </div>
              </template>

              <template v-else-if="adminState.activeTab === 'prompts'">
                <div class="admin-section-head">
                  <div>
                    <h3>提示语模板</h3>
                    <p class="muted">配置三种创作模式中 AI 图标使用的提示词优化模板，可绑定全局或单个模型。</p>
                  </div>
                  <button class="button-secondary" @click="loadPromptTemplates">刷新模板</button>
                </div>

                <div class="admin-mini-metrics">
                  <article><span>模板数量</span><strong>{{ formatAdminNumber(adminPromptTemplateCount) }}</strong><small>已保存模板</small></article>
                  <article><span>启用模板</span><strong>{{ formatAdminNumber(adminState.templates.filter((template) => template.enabled).length) }}</strong><small>可用于优化提示词</small></article>
                  <article><span>当前能力</span><strong>{{ CAPABILITY_LABELS[adminState.templateDraft.capability] }}</strong><small>编辑器目标</small></article>
                  <article><span>测试状态</span><strong>{{ adminState.templateDraft.preview ? "已生成" : "待测试" }}</strong><small>预览优化结果</small></article>
                  <article><span>模型启用总览</span><strong>{{ formatAdminNumber(adminPromptModelOverview.filter((row) => row.enabled).length) }}</strong><small>模型开关 + 模板开关</small></article>
                </div>

                <div class="admin-template-layout">
                  <section class="admin-subpanel">
                    <div class="admin-subpanel-head">
                      <h4>模板编辑</h4>
                      <span>Prompt optimizer</span>
                    </div>
                    <div class="form-grid">
                      <label class="field"><span>能力</span><select v-model="adminState.templateDraft.capability" @change="selectPromptTemplateDraft"><option value="text">文案创作</option><option value="image">图片创作</option><option value="video">视频创作</option></select></label>
                      <label class="field"><span>绑定模型</span><select v-model="adminState.templateDraft.modelGroupId" @change="selectPromptTemplateDraft"><option value="">该能力默认模板</option><option v-for="model in adminState.models" :key="model.id" :value="model.id">{{ modelDisplayName(model) }}</option></select></label>
                      <label class="field field-full"><span>模板名称</span><input v-model="adminState.templateDraft.name" /></label>
                      <label class="field field-full"><span>模板内容</span><textarea v-model="adminState.templateDraft.content" rows="12" /></label>
                      <label class="admin-check"><input v-model="adminState.templateDraft.enabled" type="checkbox" /> 启用模板</label>
                    </div>
                    <div class="admin-row-actions">
                      <button class="button-secondary" :disabled="adminState.saving === 'prompt-preview'" @click="testAdminPromptTemplate">测试预览</button>
                      <button :disabled="adminState.saving === 'prompt-template'" @click="savePromptTemplate">保存模板</button>
                    </div>
                  </section>

                  <section class="admin-subpanel">
                    <div class="admin-subpanel-head">
                      <h4>测试与模板列表</h4>
                      <span>{{ adminState.templates.length }} 个模板</span>
                    </div>
                    <label class="field field-full"><span>多样例测试</span><textarea v-model="adminState.templateDraft.testSamplesText" rows="5" placeholder="每行一个测试提示词，最多 5 条" /></label>
                    <div v-if="adminState.templateDraft.previews.length" class="admin-template-previews">
                      <article v-for="item in adminState.templateDraft.previews" :key="item.input">
                        <span>{{ item.input }}</span>
                        <pre>{{ item.output }}</pre>
                      </article>
                    </div>
                    <pre v-else class="admin-preview">{{ adminState.templateDraft.preview || "点击测试预览后显示渲染结果。" }}</pre>
                    <div class="admin-template-list">
                      <button
                        v-for="template in adminState.templates"
                        :key="template.id"
                        class="button-secondary admin-template-item"
                        @click="adminState.templateDraft.capability = template.capability; adminState.templateDraft.modelGroupId = template.modelGroupId; selectPromptTemplateDraft()"
                      >
                        <strong>{{ template.name }}</strong>
                        <span>{{ CAPABILITY_LABELS[template.capability] }} / {{ template.modelGroupId ? "模型专属" : "默认" }} / {{ template.enabled ? "启用" : "禁用" }}</span>
                      </button>
                    </div>
                  </section>

                  <section class="admin-subpanel admin-wide-panel">
                    <div class="admin-subpanel-head">
                      <h4>模型级启用状态</h4>
                      <span>Prompt optimizer matrix</span>
                    </div>
                    <div class="admin-prompt-model-grid">
                      <article v-for="row in adminPromptModelOverview" :key="row.model.id">
                        <strong>{{ modelDisplayName(row.model) }}</strong>
                        <span>{{ CAPABILITY_LABELS[row.model.capability] }} / {{ row.template?.name || "未配置模板" }}</span>
                        <b :class="['badge', row.enabled ? 'badge-success' : 'badge-warn']">{{ row.enabled ? "可用" : "未启用" }}</b>
                      </article>
                    </div>
                  </section>

                  <section class="admin-subpanel admin-wide-panel">
                    <div class="admin-subpanel-head">
                      <h4>版本历史</h4>
                      <span>最近 {{ adminState.templateHistory.length }} 次保存前快照</span>
                    </div>
                    <div class="admin-template-history">
                      <article v-for="item in adminState.templateHistory" :key="item.id">
                        <div>
                          <strong>{{ item.name }}</strong>
                          <span>{{ CAPABILITY_LABELS[item.capability] }} / {{ item.modelGroupId || "默认模板" }} / {{ formatConversationTime(item.savedAt) }}</span>
                        </div>
                        <button class="button-secondary" @click="adminState.templateDraft.capability = item.capability; adminState.templateDraft.modelGroupId = item.modelGroupId; adminState.templateDraft.name = item.name; adminState.templateDraft.content = item.content; adminState.templateDraft.enabled = item.enabled">恢复到编辑器</button>
                      </article>
                      <p v-if="!adminState.templateHistory.length" class="admin-empty">保存模板后会在这里保留上一个版本的快照。</p>
                    </div>
                  </section>
                </div>
              </template>

              <template v-else-if="adminState.activeTab === 'users'">
                <div class="admin-section-head">
                  <div>
                    <h3>用户管理</h3>
                    <p class="muted">查看用户资料，执行启用、禁用、删除、恢复，以及必要的信息修正。</p>
                  </div>
                  <button class="button-secondary" @click="loadAdminUsers">刷新用户</button>
                </div>

                <div class="admin-mini-metrics">
                  <article><span>用户总数</span><strong>{{ formatAdminNumber(adminState.users.length) }}</strong><small>当前搜索结果</small></article>
                  <article><span>启用用户</span><strong>{{ formatAdminNumber(adminActiveUserCount) }}</strong><small>可正常使用</small></article>
                  <article><span>管理员</span><strong>{{ formatAdminNumber(adminState.users.filter((user) => user.isAdmin).length) }}</strong><small>受保护账号</small></article>
                  <article><span>禁用/删除</span><strong>{{ formatAdminNumber(adminState.users.filter((user) => user.status !== "active").length) }}</strong><small>需复核账号</small></article>
                </div>

                <div class="admin-toolbar admin-command-panel">
                  <label class="settings-search-box admin-search"><span>搜索</span><input v-model="adminState.userSearch" placeholder="邮箱、昵称、手机号、ID" @keyup.enter="loadAdminUsers" /></label>
                  <select v-model="adminState.userRoleFilter">
                    <option value="all">全部角色</option>
                    <option value="admin">仅管理员</option>
                    <option value="user">仅普通用户</option>
                  </select>
                  <button class="button-secondary" @click="loadAdminUsers">筛选</button>
                  <button class="button-secondary" @click="exportAdminUsers">导出用户</button>
                </div>

                <div class="admin-users-layout">
                  <div class="admin-data-table admin-user-table admin-list-shell">
                    <div class="admin-data-row admin-data-head"><span>用户</span><span>联系方式</span><span>状态</span><span>最近活跃</span><span>操作</span></div>
                    <article v-for="user in adminFilteredUsers" :key="user.id" class="admin-data-row admin-user-row">
                    <div class="admin-user-cell">
                      <div class="admin-user-avatar">{{ (user.nickname || user.email || "U").slice(0, 1) }}</div>
                      <div>
                        <strong>{{ adminUserLabel(user) }}</strong>
                        <small>ID {{ user.id }}</small>
                      </div>
                    </div>
                    <div class="admin-stack">
                      <span>{{ user.email || "-" }}</span>
                      <small>{{ user.phone || "未填写手机" }}</small>
                    </div>
                    <span :class="['badge', adminStatusBadge(user.status)]">{{ user.isAdmin ? "管理员" : adminStatusLabel(user.status) }}</span>
                    <span>{{ user.lastSeenAt ? formatConversationTime(user.lastSeenAt) : formatConversationTime(user.updatedAt) }}</span>
                    <div class="admin-action-cell">
                      <button class="button-secondary" @click="adminState.selectedUserId = user.id">详情</button>
                      <button class="button-secondary" @click="editAdminUser(user)">{{ adminState.editingUserId === user.id ? "收起" : "编辑" }}</button>
                      <button class="button-secondary" :disabled="user.isAdmin" @click="setAdminUserStatus(user, 'enable')">启用</button>
                      <button class="button-secondary" :disabled="user.isAdmin" @click="setAdminUserStatus(user, 'disable')">禁用</button>
                      <button class="button-danger" :disabled="user.isAdmin" @click="setAdminUserStatus(user, 'delete')">删除</button>
                      <button class="button-secondary" :disabled="user.isAdmin" @click="setAdminUserStatus(user, 'restore')">恢复</button>
                    </div>
                    <div v-if="adminState.editingUserId === user.id" class="admin-row-editor admin-user-fields">
                      <label><span>昵称</span><input v-model="user.nickname" /></label>
                      <label><span>邮箱</span><input v-model="user.email" /></label>
                      <label><span>手机</span><input v-model="user.phone" /></label>
                      <label><span>状态</span><select v-model="user.status"><option value="active">active</option><option value="disabled">disabled</option><option value="deleted">deleted</option></select></label>
                      <div class="admin-row-actions field-full">
                        <button class="button-secondary" :disabled="adminState.saving === user.id" @click="saveAdminUser(user)">保存用户</button>
                      </div>
                    </div>
                  </article>
                    <p v-if="!adminFilteredUsers.length" class="admin-empty">暂无用户</p>
                  </div>

                  <aside class="admin-detail-drawer admin-user-drawer" :class="adminSelectedUser ? 'admin-detail-open' : ''">
                    <div class="admin-detail-head">
                      <div>
                        <span>用户详情</span>
                        <strong>{{ adminSelectedUser ? adminUserLabel(adminSelectedUser) : "请选择用户" }}</strong>
                      </div>
                      <button class="button-secondary" @click="adminState.selectedUserId = ''">关闭</button>
                    </div>
                    <template v-if="adminSelectedUser">
                      <div class="admin-user-profile-card">
                        <div class="admin-user-avatar">{{ (adminSelectedUser.nickname || adminSelectedUser.email || "U").slice(0, 1) }}</div>
                        <div>
                          <strong>{{ adminUserLabel(adminSelectedUser) }}</strong>
                          <span>{{ adminSelectedUser.email || "未填写邮箱" }}</span>
                        </div>
                      </div>
                      <dl class="admin-detail-list">
                        <dt>角色</dt><dd>{{ adminSelectedUser.isAdmin ? "管理员" : "普通用户" }}</dd>
                        <dt>状态</dt><dd>{{ adminStatusLabel(adminSelectedUser.status) }}</dd>
                        <dt>活跃会话</dt><dd>{{ formatAdminNumber(adminSelectedUser.sessionCount || 0) }}</dd>
                        <dt>最近登录 IP</dt><dd>{{ adminSelectedUser.recentLoginIp || "未记录" }}</dd>
                        <dt>最近活跃</dt><dd>{{ adminSelectedUser.lastSeenAt ? formatConversationTime(adminSelectedUser.lastSeenAt) : "-" }}</dd>
                        <dt>创建时间</dt><dd>{{ formatConversationTime(adminSelectedUser.createdAt) }}</dd>
                      </dl>
                    </template>
                    <p v-else class="admin-empty">点击用户行里的“详情”查看用户画像、会话和登录信息。</p>
                  </aside>
                </div>
              </template>

              <template v-else-if="adminState.activeTab === 'text-records' || adminState.activeTab === 'image-records' || adminState.activeTab === 'video-records'">
                <div class="admin-section-head">
                  <div>
                    <h3>{{ adminRecordTitle(adminState.activeTab) }}</h3>
                    <p class="muted">按类型、用户和状态查看创作请求，正文优先展示提问、回答和媒体结果。</p>
                  </div>
                  <button class="button-secondary" @click="loadAdminRecords(capabilityForAdminRecordTab(adminState.activeTab))">刷新记录</button>
                </div>

                <div class="admin-mini-metrics">
                  <article><span>记录数</span><strong>{{ formatAdminNumber(adminRecordCount) }}</strong><small>当前筛选结果</small></article>
                  <article><span>成功</span><strong>{{ formatAdminNumber(adminRecordList(adminState.activeTab).filter((record) => record.status === "success").length) }}</strong><small>已完成调用</small></article>
                  <article><span>失败</span><strong>{{ formatAdminNumber(adminRecordList(adminState.activeTab).filter((record) => record.status === "error").length) }}</strong><small>可排查样本</small></article>
                  <article><span>处理中</span><strong>{{ formatAdminNumber(adminRecordList(adminState.activeTab).filter((record) => record.status === "processing").length) }}</strong><small>长任务追踪</small></article>
                </div>

                <div class="admin-toolbar admin-record-toolbar admin-command-panel">
                  <div class="settings-filter-tabs" role="tablist" aria-label="调用记录类型">
                    <button
                      v-for="tab in adminRecordCapabilityTabs"
                      :key="tab.value"
                      :class="['settings-filter-tab', capabilityForAdminRecordTab(adminState.activeTab) === tab.value ? 'settings-filter-tab-active' : '']"
                      @click="switchAdminRecordCapability(tab.value)"
                    >
                      <strong>{{ tab.label }}</strong>
                      <span>{{ tab.hint }}</span>
                    </button>
                  </div>
                  <label class="settings-search-box admin-search admin-record-user-search">
                    <span>用户</span>
                    <input
                      v-model="adminState.recordUserSearch"
                      placeholder="邮箱、昵称、手机号或用户 ID"
                      @keyup.enter="loadAdminRecords(capabilityForAdminRecordTab(adminState.activeTab))"
                    />
                  </label>
                  <label class="settings-search-box admin-search admin-record-keyword-search">
                    <span>关键词</span>
                    <input v-model="adminState.recordKeyword" placeholder="提示词、回答、错误内容" @keyup.enter="loadAdminRecords(capabilityForAdminRecordTab(adminState.activeTab))" />
                  </label>
                  <select v-model="adminState.recordStatus" @change="loadAdminRecords(capabilityForAdminRecordTab(adminState.activeTab))">
                    <option value="">全部状态</option>
                    <option value="success">success</option>
                    <option value="error">error</option>
                    <option value="processing">processing</option>
                  </select>
                  <details class="admin-filter-more">
                    <summary>高级筛选</summary>
                    <label class="settings-search-box admin-search">
                      <span>模型 ID</span>
                      <input v-model="adminState.recordModelGroupId" placeholder="可选" @keyup.enter="loadAdminRecords(capabilityForAdminRecordTab(adminState.activeTab))" />
                    </label>
                    <label v-if="adminState.activeTab === 'image-records'" class="settings-search-box admin-search">
                      <span>尺寸</span>
                      <input v-model="adminState.recordSize" placeholder="1024x1024" @keyup.enter="loadAdminRecords('image')" />
                    </label>
                    <label v-if="adminState.activeTab !== 'text-records'" class="settings-search-box admin-search">
                      <span>比例</span>
                      <input v-model="adminState.recordRatio" placeholder="16:9" @keyup.enter="loadAdminRecords(capabilityForAdminRecordTab(adminState.activeTab))" />
                    </label>
                    <label v-if="adminState.activeTab !== 'text-records'" class="settings-search-box admin-search">
                      <span>参考图数量</span>
                      <input v-model="adminState.recordRefCount" placeholder="0 / 1 / 2" @keyup.enter="loadAdminRecords(capabilityForAdminRecordTab(adminState.activeTab))" />
                    </label>
                    <label v-if="adminState.activeTab === 'video-records'" class="settings-search-box admin-search">
                      <span>时长</span>
                      <input v-model="adminState.recordDuration" placeholder="8" @keyup.enter="loadAdminRecords('video')" />
                    </label>
                    <label v-if="adminState.activeTab === 'video-records'" class="settings-search-box admin-search">
                      <span>分辨率</span>
                      <input v-model="adminState.recordResolution" placeholder="720p" @keyup.enter="loadAdminRecords('video')" />
                    </label>
                    <label v-if="adminState.activeTab === 'video-records'" class="settings-search-box admin-search">
                      <span>模式</span>
                      <input v-model="adminState.recordMode" placeholder="reference / first_last_frame" @keyup.enter="loadAdminRecords('video')" />
                    </label>
                  </details>
                  <button class="button-secondary" @click="loadAdminRecords(capabilityForAdminRecordTab(adminState.activeTab))">筛选</button>
                  <button class="button-secondary" @click="saveAdminRecordFilter">保存筛选</button>
                  <button class="button-secondary" @click="clearAdminRecordFilters">清空</button>
                  <label v-if="adminState.activeTab === 'text-records'" class="admin-check admin-inline-toggle">
                    <input v-model="adminState.recordMarkdownPreview" type="checkbox" />
                    Markdown 预览
                  </label>
                  <label v-if="adminState.activeTab === 'image-records'" class="admin-check admin-inline-toggle">
                    <input v-model="adminState.recordWaterfall" type="checkbox" />
                    瀑布流
                  </label>
                </div>

                <div v-if="adminState.recordSavedFilters.length" class="admin-saved-filters">
                  <button
                    v-for="filter in adminState.recordSavedFilters"
                    :key="filter.id"
                    class="button-secondary"
                    @click="switchAdminRecordCapability(filter.capability); applyAdminRecordFilters(filter.filters)"
                  >
                    {{ filter.name }}
                  </button>
                </div>

                <div :class="['admin-record-list', 'admin-list-shell', adminState.activeTab === 'image-records' && adminState.recordWaterfall ? 'admin-record-waterfall' : '']">
                  <article
                    v-for="record in adminRecordList(adminState.activeTab)"
                    :key="record.id"
                    :class="[
                      'admin-record-card',
                      `admin-record-card-${record.capability}`,
                      record.status === 'error' ? 'admin-record-card-error' : '',
                    ]"
                  >
                    <div class="admin-record-head">
                      <div>
                        <strong>{{ record.modelName || "未知模型" }}</strong>
                        <span>{{ adminUserLabel(record.user) }} / {{ CAPABILITY_LABELS[record.capability] }} / {{ formatConversationTime(record.createdAt) }}</span>
                      </div>
                      <div class="admin-record-actions">
                        <span :class="['badge', adminStatusBadge(record.status)]">{{ adminStatusLabel(record.status) }}</span>
                        <button class="button-secondary" @click="openAdminRecordDetail(record)">详情</button>
                      </div>
                    </div>

                    <div v-if="record.capability === 'text'" class="admin-record-qa">
                      <section>
                        <span>提问</span>
                        <p class="admin-record-preview-clamp">{{ adminRecordPrompt(record) }}</p>
                      </section>
                      <section>
                        <span>回答</span>
                        <div v-if="adminRecordIsMarkdownCapable(record)" class="markdown-preview admin-markdown-preview" v-html="adminRecordMarkdownHtml(record)"></div>
                        <p v-else class="admin-record-preview-clamp">{{ adminRecordResponse(record) }}</p>
                      </section>
                    </div>

                    <div v-else class="admin-record-media-layout">
                      <section class="admin-record-request">
                        <span>请求</span>
                        <p class="admin-record-preview-clamp">{{ adminRecordPrompt(record) }}</p>
                        <small v-if="record.taskId">任务 ID: {{ record.taskId }}</small>
                        <small>参数：{{ adminRecordParam(record, ['size']) }} / {{ adminRecordParam(record, ['aspect_ratio', 'ratio']) }} / 参考图 {{ adminRecordReferenceCount(record) }}</small>
                      </section>
                      <section class="admin-record-result">
                        <span>响应结果</span>
                        <div v-if="adminRecordMediaAssets(record).length" class="admin-record-assets">
                          <a v-for="asset in adminRecordMediaAssets(record)" :key="asset.url" class="admin-record-asset" :href="asset.url" target="_blank" rel="noreferrer" @click.prevent="openAdminRecordDetail(record)">
                            <img v-if="asset.type === 'image'" :src="asset.thumbnailUrl || asset.url" alt="record asset" @error="markAdminRecordAssetBroken" />
                            <video v-else-if="asset.type === 'video'" :src="asset.url" :poster="asset.thumbnailUrl" controls playsinline @error="markAdminRecordAssetBroken" />
                            <span v-else>打开资源</span>
                            <span class="admin-record-asset-fallback">资源加载失败<br />打开详情查看原链接</span>
                          </a>
                        </div>
                        <p v-else class="admin-record-preview-clamp">{{ adminRecordResponse(record) }}</p>
                      </section>
                    </div>

                    <details class="admin-record-json" :open="adminRecordJsonInitiallyOpen(record)">
                      <summary>调试 JSON</summary>
                      <div class="admin-record-json-grid">
                        <div><span>请求参数</span><pre>{{ compactJson(record.requestParams || {}) }}</pre></div>
                        <div><span>响应摘要</span><pre>{{ compactJson(record.responseSummary || {}) }}</pre></div>
                      </div>
                    </details>
                  </article>
                  <p v-if="!adminRecordList(adminState.activeTab).length" class="admin-empty">暂无记录</p>
                </div>

                <aside class="admin-detail-drawer admin-record-drawer" :class="adminSelectedRecord ? 'admin-detail-open' : ''">
                  <div class="admin-detail-head">
                    <div>
                      <span>记录详情</span>
                      <strong>{{ adminSelectedRecord?.modelName || "请选择记录" }}</strong>
                    </div>
                    <button class="button-secondary" @click="closeAdminRecordDetail">关闭</button>
                  </div>
                  <template v-if="adminSelectedRecord">
                    <div class="admin-record-detail-media" v-if="adminRecordMediaAssets(adminSelectedRecord).length">
                      <a v-for="asset in adminRecordMediaAssets(adminSelectedRecord)" :key="asset.url" class="admin-record-asset" :href="asset.url" target="_blank" rel="noreferrer">
                        <img v-if="asset.type === 'image'" :src="asset.thumbnailUrl || asset.url" alt="record asset" @error="markAdminRecordAssetBroken" />
                        <video v-else-if="asset.type === 'video'" :src="asset.url" :poster="asset.thumbnailUrl" controls playsinline @error="markAdminRecordAssetBroken" />
                        <span class="admin-record-asset-fallback">资源加载失败<br />点击打开原链接</span>
                      </a>
                    </div>
                    <div v-if="adminSelectedRecord.capability === 'video'" class="admin-task-timeline">
                      <article v-for="item in adminRecordTimeline(adminSelectedRecord)" :key="item.label" :class="`admin-timeline-${item.tone}`">
                        <span>{{ item.label }}</span>
                        <strong>{{ item.value }}</strong>
                      </article>
                    </div>
                    <dl class="admin-detail-list">
                      <dt>用户</dt><dd>{{ adminUserLabel(adminSelectedRecord.user) }}</dd>
                      <dt>状态</dt><dd>{{ adminStatusLabel(adminSelectedRecord.status) }}</dd>
                      <dt>任务 ID</dt><dd><button v-if="adminSelectedRecord.taskId" class="button-secondary" @click="copyAdminText(adminSelectedRecord.taskId || '', '任务 ID')">复制 {{ adminSelectedRecord.taskId }}</button><span v-else>-</span></dd>
                      <dt>尺寸/比例</dt><dd>{{ adminRecordParam(adminSelectedRecord, ['size']) }} / {{ adminRecordParam(adminSelectedRecord, ['aspect_ratio', 'ratio']) }}</dd>
                      <dt>时长/分辨率/模式</dt><dd>{{ adminRecordParam(adminSelectedRecord, ['duration']) }} / {{ adminRecordParam(adminSelectedRecord, ['resolution']) }} / {{ adminRecordParam(adminSelectedRecord, ['video_mode', 'mode']) }}</dd>
                      <dt>参考图数量</dt><dd>{{ adminRecordReferenceCount(adminSelectedRecord) }}</dd>
                    </dl>
                    <section class="admin-record-detail-copy">
                      <span>提示词</span>
                      <p>{{ adminRecordPrompt(adminSelectedRecord) }}</p>
                    </section>
                    <section class="admin-record-detail-copy">
                      <span>响应</span>
                      <div v-if="adminRecordIsMarkdownCapable(adminSelectedRecord)" class="markdown-preview" v-html="adminRecordMarkdownHtml(adminSelectedRecord)"></div>
                      <p v-else>{{ adminRecordResponse(adminSelectedRecord) }}</p>
                    </section>
                    <details class="admin-record-json">
                      <summary>完整 JSON</summary>
                      <div class="admin-record-json-grid">
                        <div><span>请求参数</span><pre>{{ compactJson(adminSelectedRecord.requestParams || {}) }}</pre></div>
                        <div><span>响应摘要</span><pre>{{ compactJson(adminSelectedRecord.responseSummary || {}) }}</pre></div>
                      </div>
                    </details>
                  </template>
                </aside>
              </template>

              <template v-else-if="adminState.activeTab === 'audit'">
                <div class="admin-section-head">
                  <div>
                    <h3>操作记录</h3>
                    <p class="muted">记录公用模型、模板、用户管理等后台变更，便于上线后追溯。</p>
                  </div>
                  <button class="button-secondary" @click="loadAdminAuditLogs">刷新审计</button>
                </div>

                <div class="admin-mini-metrics">
                  <article><span>审计记录</span><strong>{{ formatAdminNumber(adminAuditCount) }}</strong><small>当前筛选结果</small></article>
                  <article><span>成功操作</span><strong>{{ formatAdminNumber(adminState.auditLogs.filter((log) => log.status === "success").length) }}</strong><small>已落库变更</small></article>
                  <article><span>异常操作</span><strong>{{ formatAdminNumber(adminState.auditLogs.filter((log) => log.status === "error").length) }}</strong><small>需复核记录</small></article>
                  <article><span>高风险操作</span><strong>{{ formatAdminNumber(adminState.auditLogs.filter((log) => log.riskLevel === "high").length) }}</strong><small>删除、禁用、取消公用等</small></article>
                </div>

                <div class="admin-toolbar admin-command-panel">
                  <label class="settings-search-box admin-search"><span>动作</span><input v-model="adminState.auditAction" placeholder="publish_model" @keyup.enter="loadAdminAuditLogs" /></label>
                  <label class="settings-search-box admin-search"><span>管理员 ID</span><input v-model="adminState.auditAdminUserId" placeholder="可选" @keyup.enter="loadAdminAuditLogs" /></label>
                  <select v-model="adminState.auditTargetType" @change="loadAdminAuditLogs">
                    <option value="">全部对象</option>
                    <option value="model">模型</option>
                    <option value="user">用户</option>
                    <option value="prompt_template">提示语模板</option>
                  </select>
                  <label class="settings-search-box admin-search"><span>目标 ID</span><input v-model="adminState.auditTargetId" placeholder="模型或用户 ID" @keyup.enter="loadAdminAuditLogs" /></label>
                  <select v-model="adminState.auditRisk" @change="loadAdminAuditLogs">
                    <option value="">全部风险</option>
                    <option value="high">高风险</option>
                    <option value="medium">需关注</option>
                    <option value="normal">普通</option>
                  </select>
                  <button class="button-secondary" @click="loadAdminAuditLogs">筛选</button>
                  <button class="button-secondary" @click="exportAdminAuditLogs">导出审计</button>
                </div>

                <div class="admin-data-table admin-audit-table admin-list-shell">
                  <div class="admin-data-row admin-data-head"><span>时间</span><span>动作</span><span>目标</span><span>风险</span><span>状态</span><span>摘要</span></div>
                  <div v-for="log in adminState.auditLogs" :key="log.id" class="admin-data-row">
                    <span>{{ formatConversationTime(log.createdAt) }}</span>
                    <strong>{{ log.action }}</strong>
                    <span>{{ log.targetType }} / {{ log.targetId }}</span>
                    <span :class="['badge', adminRiskBadge(log.riskLevel)]">{{ adminRiskLabel(log.riskLevel) }}</span>
                    <span :class="['badge', adminStatusBadge(log.status)]">{{ adminStatusLabel(log.status) }}</span>
                    <pre>{{ compactJson(log.summary || {}) }}</pre>
                  </div>
                  <p v-if="!adminState.auditLogs.length" class="admin-empty">暂无操作记录</p>
                </div>
              </template>
            </main>
          </section>
        </div>
      </section>

      <section v-else class="settings-page">
        <section class="settings-hero">
          <div>
            <p class="eyebrow">Model Settings</p>
            <h2>模型配置</h2>
            <p class="muted">{{ auth.state.user ? "配置会保存到创意工坊数据库，密钥只由后端调用。" : "未登录时配置会缓存在当前浏览器，登录后可保存到数据库。" }}</p>
          </div>
          <div class="settings-hero-stats">
            <span class="badge">{{ store.models.value.length }} 个模型</span>
            <span class="badge badge-success">{{ configuredCount }} 个已配置</span>
          </div>
        </section>

        <section class="settings-list-panel">
          <div class="settings-list-toolbar">
            <div class="settings-toolbar-copy">
              <strong>已保存模型</strong>
              <span>每个模型都绑定当前用户自己的密钥、主模型和测试状态。</span>
            </div>
            <div class="settings-bulk-actions">
              <span class="badge">已选 {{ selectedVisibleSettingsModels.length }} / {{ filteredSettingsModels.length }}</span>
              <button
                v-if="auth.state.user?.isAdmin"
                class="button-secondary"
                :disabled="!publicShareTargets.length"
                @click="batchPublishPublic"
              >
                设为公用模型 {{ publicShareTargets.length ? publicShareTargets.length : "" }}
              </button>
              <button class="button-secondary" :disabled="!selectedVisibleSettingsModels.length" @click="batchTest">批量测试</button>
              <button class="button-danger" :disabled="!unavailableEditableSettingsModels.length" @click="removeUnavailableModels">
                移除不可用 {{ unavailableEditableSettingsModels.length ? unavailableEditableSettingsModels.length : "" }}
              </button>
              <button class="button-danger" :disabled="!selectedEditableSettingsModels.length" @click="batchDelete">批量删除</button>
              <button @click="openCreateDialog">+ 添加模型</button>
            </div>
          </div>

          <div class="settings-filter-bar">
            <div class="settings-filter-tabs" role="tablist" aria-label="模型分组">
              <button
                v-for="tab in settingsCapabilityTabs"
                :key="tab.value"
                type="button"
                :class="['settings-filter-tab', settingsState.activeCapability === tab.value ? 'settings-filter-tab-active' : '']"
                @click="settingsState.activeCapability = tab.value"
              >
                <span>{{ tab.label }}</span>
                <small>{{ settingsCapabilityCounts[tab.value] }}</small>
              </button>
            </div>
            <label class="settings-search-box">
              <span>搜索</span>
              <input v-model="settingsState.searchQuery" placeholder="名称、主模型、子模型" />
              <button v-if="settingsState.searchQuery" type="button" class="settings-search-clear" @click="settingsState.searchQuery = ''">清除</button>
            </label>
          </div>

          <div class="settings-model-board">
            <div class="settings-board-head">
              <label class="settings-check-cell">
                <input type="checkbox" :checked="allSettingsSelected" :indeterminate.prop="partialSettingsSelected" @change="(event) => toggleAllSettings((event.target as HTMLInputElement).checked)" />
              </label>
              <span>模型</span>
              <span>主模型</span>
              <span>状态</span>
              <span>操作</span>
            </div>
            <article
              v-for="model in filteredSettingsModels"
              :key="model.id"
              :class="[
                'settings-model-row',
                `settings-model-row-${model.capability}`,
                model.isPublic ? 'settings-model-row-public' : '',
                isModelSelectOpen(modelSelectKey('row', model.id)) ? 'settings-model-row-select-open' : '',
              ]"
              :data-model-id="model.id"
            >
              <label class="settings-check-cell">
                <input type="checkbox" :disabled="!canEditModel(model)" :checked="settingsState.selectedIds.includes(model.id)" @change="(event) => toggleSelected(model.id, (event.target as HTMLInputElement).checked)" />
              </label>
              <div class="settings-model-main">
                <div :class="['model-avatar', `model-avatar-${model.capability}`, modelIconUrl(model) ? 'model-avatar-has-icon' : '']">
                  <img v-if="modelIconUrl(model)" :src="modelIconUrl(model)" :alt="modelDisplayName(model)" loading="lazy" @error="hideBrokenModelIcon" />
                  <span>{{ model.capability === "text" ? "T" : model.capability === "image" ? "I" : "V" }}</span>
                </div>
                <div>
                  <strong>{{ modelDisplayName(model) }}</strong>
                  <span>{{ modelSummaryText(model) }}</span>
                  <div class="settings-model-meta-row">
                    <span :class="['parameter-source-chip', hasCatalogParameters(model) ? 'parameter-source-chip-exact' : 'parameter-source-chip-generic']">
                      {{ modelParameterSourceLabel(model) }}
                    </span>
                    <span v-if="model.isPublic" class="parameter-source-chip parameter-source-chip-exact">公共模型</span>
                    <span v-if="model.serverManaged && !canEditModel(model)" class="parameter-source-chip parameter-source-chip-generic">只读</span>
                    <span class="settings-model-hint">{{ modelCatalogInputHint(model, "暂无模型提示语") }}</span>
                  </div>
                </div>
              </div>
              <div class="settings-primary-model">
                <div
                  v-if="getAvailableModels(model).length"
                  :class="[
                    'model-select',
                    'inline-model-select',
                    isModelSelectOpen(modelSelectKey('row', model.id)) ? 'model-select-open' : '',
                    isModelSelectOpen(modelSelectKey('row', model.id)) ? `model-select-${modelSelectState.placement}` : '',
                  ]"
                  @keydown.escape.stop="closeModelSelect"
                >
                  <span class="model-select-label">主模型</span>
                <button
                    type="button"
                    class="model-select-trigger"
                    :disabled="!canEditModel(model)"
                    :aria-expanded="isModelSelectOpen(modelSelectKey('row', model.id))"
                    @click.stop="(event) => toggleModelSelect(modelSelectKey('row', model.id), event)"
                  >
                    <span class="model-select-trigger-text">{{ resolveModelName(model, getSetting(model.id)) || "选择主模型" }}</span>
                    <span class="model-select-trigger-meta">{{ getAvailableModels(model).length }} 项</span>
                    <span class="model-select-chevron">⌄</span>
                  </button>
                  <button
                    v-if="isModelSelectOpen(modelSelectKey('row', model.id))"
                    type="button"
                    class="model-select-scrim"
                    tabindex="-1"
                    aria-label="关闭模型选择"
                    @click="closeModelSelect"
                  ></button>
                  <div v-if="isModelSelectOpen(modelSelectKey('row', model.id))" class="model-select-menu" @click.stop>
                    <label v-if="getAvailableModels(model).length > 8" class="model-select-search">
                      <span>搜索</span>
                      <input v-model="modelSelectState.query" placeholder="输入模型名称" @keydown.stop />
                    </label>
                    <div class="model-select-list">
                      <button
                        v-for="modelId in filteredModelSelectOptions(getAvailableModels(model), resolveModelName(model, getSetting(model.id)))"
                        :key="modelId"
                        type="button"
                        :class="['model-select-option', modelId === resolveModelName(model, getSetting(model.id)) ? 'model-select-option-active' : '']"
                        @click="chooseRowPrimaryModel(modelId, model)"
                      >
                        <span class="model-select-option-name">{{ modelId }}</span>
                        <span v-if="modelId === resolveModelName(model, getSetting(model.id))" class="model-select-check">✓</span>
                      </button>
                      <div v-if="!filteredModelSelectOptions(getAvailableModels(model), resolveModelName(model, getSetting(model.id))).length" class="model-select-empty">没有匹配的模型</div>
                    </div>
                  </div>
                </div>
                <template v-else>
                  <strong>{{ resolveModelName(model, getSetting(model.id)) || "尚未选择" }}</strong>
                </template>
                <span>{{ getAvailableModels(model).length || 1 }} 个可用模型</span>
              </div>
              <div class="settings-status-cell">
                <span :class="['badge', getModelStatusClass(model, getSetting(model.id))]">
                  {{ getModelStatusLabel(model, getSetting(model.id)) }}
                </span>
              </div>
              <div class="settings-row-actions">
                <button class="button-secondary settings-action-button" :disabled="!canEditModel(model)" @click="fetchModelList(model, getSetting(model.id))">获取模型</button>
                <button class="button-secondary settings-action-button" @click="testModel(model, getSetting(model.id))">测试</button>
                <button class="button-secondary settings-action-button" :disabled="!canEditModel(model)" @click="openEditDialog(model)">编辑</button>
                <button class="button-danger settings-action-button" :disabled="!canEditModel(model)" @click="removeModelFromWorkbench(model.id)">删除</button>
              </div>
              <div v-if="settingsState.modelListState[model.id]?.error" class="settings-row-detail inline-message inline-danger">{{ settingsState.modelListState[model.id].error }}</div>
              <div v-if="settingsState.testState[model.id]?.error" class="settings-row-detail inline-message inline-danger">{{ settingsState.testState[model.id].error }}</div>
              <div v-if="settingsState.testState[model.id]?.result" class="settings-row-detail test-response-panel">
                <div><span>状态</span><strong>{{ testSummaryFor(settingsState.testState[model.id].result).status }}</strong></div>
                <div><span>耗时</span><strong>{{ testSummaryFor(settingsState.testState[model.id].result).duration }}</strong></div>
                <div class="test-response-url"><span>请求</span><strong>{{ testSummaryFor(settingsState.testState[model.id].result).requestUrl }}</strong></div>
                <pre>{{ testSummaryFor(settingsState.testState[model.id].result).rawPreview }}</pre>
              </div>
              <div v-if="settingsState.modelListState[model.id]?.result" class="settings-row-detail settings-model-list-result">
                <div class="status-row">
                  <span class="badge badge-success">已获取 {{ getAvailableModels(model).length }} 个模型</span>
                  <span v-if="settingsState.modelListState[model.id]?.result" class="history-time">{{ settingsState.modelListState[model.id].result?.durationMs }}ms</span>
                </div>
              </div>
            </article>
            <div v-if="!store.models.value.length" class="settings-empty-state">
              <strong>还没有模型配置</strong>
              <span>添加一个密钥，先获取模型列表，再选择主模型保存。</span>
              <button @click="openCreateDialog">添加模型</button>
            </div>
            <div v-else-if="!filteredSettingsModels.length" class="settings-empty-state">
              <strong>没有匹配的模型</strong>
              <span>换一个分组或关键词再试试。</span>
              <button class="button-secondary" @click="settingsState.searchQuery = ''; settingsState.activeCapability = 'all'">查看全部</button>
            </div>
          </div>
        </section>

        <div v-if="settingsState.dialogOpen" class="settings-dialog-backdrop">
          <section class="settings-dialog">
            <div class="settings-dialog-head">
              <div>
                <p class="eyebrow">Model Config</p>
                <h3>{{ settingsState.dialogMode === "create" ? "添加模型" : "模型配置" }}</h3>
                <span>填写密钥后先获取可用模型，再选择一个主模型用于创作。</span>
              </div>
              <button class="button-secondary icon-button" @click="closeSettingsDialog">关闭</button>
            </div>
            <div class="settings-dialog-workspace">
              <div class="wizard-steps">
                <article
                  v-for="step in modelWizardProgress"
                  :key="step.step"
                  :class="['wizard-step', step.step === modelWizardStep ? 'wizard-step-active' : '', step.complete ? 'wizard-step-complete' : '']"
                >
                  <span>{{ step.index }}</span>
                  <div>
                    <strong>{{ step.label }}</strong>
                    <small>{{ step.description }}</small>
                  </div>
                </article>
              </div>

              <div class="settings-dialog-sections">
                <section class="settings-dialog-section">
                  <div class="section-copy">
                    <strong>连接密钥</strong>
                    <span>日常只填能力、baseURL 和 API Key。名称、厂商、适配器会自动使用默认值。</span>
                  </div>
                  <div class="settings-dialog-quick-grid">
                    <label class="field field-full">
                      <span>能力类型</span>
                      <select v-model="settingsState.draft.capability" @change="handleDraftCapabilityChange">
                        <option value="text">文案创作</option>
                        <option value="image">图片创作</option>
                        <option value="video">视频创作</option>
                      </select>
                    </label>
                    <label class="field field-full"><span>baseURL</span><input v-model="settingsState.draft.baseUrl" placeholder="例如：https://token.example.com" /></label>
                    <label class="field field-full"><span>API Key</span><input v-model="settingsState.draft.apiKey" type="password" placeholder="sk-..." /></label>
                    <button class="fetch-model-button" :disabled="!canFetchDraftModels || settingsState.modelListState[settingsState.draft.id]?.loading" :title="draftFetchDisabledTitle" @click="fetchModelList(getDraftModel(), getDraftSetting())">
                      {{ settingsState.modelListState[settingsState.draft.id]?.loading ? "获取中..." : "获取模型列表" }}
                    </button>
                    <details class="advanced-settings">
                      <summary>高级信息</summary>
                      <div class="form-grid settings-dialog-grid">
                        <label class="field"><span>名称</span><input v-model="settingsState.draft.name" :placeholder="getDraftDefaultName()" /></label>
                        <label class="field"><span>厂商</span><input v-model="settingsState.draft.vendor" placeholder="自定义" /></label>
                        <label class="field field-full"><span>备注</span><input v-model="settingsState.draft.description" placeholder="用于区分不同密钥或用途" /></label>
                        <label class="field field-full"><span>适配器</span><select v-model="settingsState.draft.adapter"><option v-for="adapter in getAdapterOptions(settingsState.draft.capability)" :key="adapter" :value="adapter">{{ ADAPTER_LABELS[adapter] }}</option></select></label>
                      </div>
                    </details>
                  </div>
                </section>

                <section class="settings-dialog-section">
                  <div class="section-copy">
                    <strong>选择主模型</strong>
                    <span>一个密钥可返回多个模型，保存后创作会使用当前选中的主模型。</span>
                  </div>
                  <div v-if="settingsState.draft.availableModels.length" class="model-pick-panel">
                    <div
                      :class="[
                        'model-select',
                        'model-select-dialog',
                        isModelSelectOpen(modelSelectKey('draft')) ? 'model-select-open' : '',
                        isModelSelectOpen(modelSelectKey('draft')) ? `model-select-${modelSelectState.placement}` : '',
                      ]"
                      @keydown.escape.stop="closeModelSelect"
                    >
                      <span class="model-select-label">主模型</span>
                      <button
                        type="button"
                        class="model-select-trigger"
                        :aria-expanded="isModelSelectOpen(modelSelectKey('draft'))"
                        @click.stop="(event) => toggleModelSelect(modelSelectKey('draft'), event)"
                      >
                        <span class="model-select-trigger-text">{{ getDraftModelName(settingsState.draft) || "选择主模型" }}</span>
                        <span class="model-select-trigger-meta">{{ settingsState.draft.availableModels.length }} 项</span>
                        <span class="model-select-chevron">⌄</span>
                      </button>
                      <button
                        v-if="isModelSelectOpen(modelSelectKey('draft'))"
                        type="button"
                        class="model-select-scrim"
                        tabindex="-1"
                        aria-label="关闭模型选择"
                        @click="closeModelSelect"
                      ></button>
                      <div v-if="isModelSelectOpen(modelSelectKey('draft'))" class="model-select-menu" @click.stop>
                        <label v-if="settingsState.draft.availableModels.length > 8" class="model-select-search">
                          <span>搜索</span>
                          <input v-model="modelSelectState.query" placeholder="输入模型名称" @keydown.stop />
                        </label>
                        <div class="model-select-list">
                          <button
                            v-for="modelId in filteredModelSelectOptions(settingsState.draft.availableModels, getDraftModelName(settingsState.draft))"
                            :key="modelId"
                            type="button"
                            :class="['model-select-option', modelId === getDraftModelName(settingsState.draft) ? 'model-select-option-active' : '']"
                            @click="chooseDraftPrimaryModel(modelId)"
                          >
                            <span class="model-select-option-name">{{ modelId }}</span>
                            <span v-if="modelId === getDraftModelName(settingsState.draft)" class="model-select-check">✓</span>
                          </button>
                          <div v-if="!filteredModelSelectOptions(settingsState.draft.availableModels, getDraftModelName(settingsState.draft)).length" class="model-select-empty">没有匹配的模型</div>
                        </div>
                      </div>
                    </div>
                    <div class="model-pick-list">
                      <span v-for="modelId in settingsState.draft.availableModels.slice(0, 8)" :key="modelId">{{ modelId }}</span>
                    </div>
                  </div>
                  <div v-else class="model-fetch-placeholder">
                    <strong>等待获取模型列表</strong>
                    <span>先点击“获取模型列表”，这里会出现主模型下拉选择。</span>
                  </div>
                </section>

                <section class="settings-dialog-section settings-dialog-review">
                <div class="section-copy">
                  <strong>测试与保存</strong>
                  <span>测试会真实请求当前主模型，并展示响应摘要。</span>
                </div>
                <div class="settings-dialog-review-body">
                  <div class="review-grid">
                    <div class="review-item">
                      <span>能力</span>
                      <strong>{{ CAPABILITY_LABELS[settingsState.draft.capability] }}</strong>
                    </div>
                    <div class="review-item">
                      <span>主模型</span>
                      <strong>{{ getDraftModelName(settingsState.draft) || "尚未选择" }}</strong>
                    </div>
                    <div class="review-item">
                      <span>模型数量</span>
                      <strong>{{ settingsState.draft.availableModels.length || 1 }}</strong>
                    </div>
                  </div>
                  <div v-if="settingsState.testState[settingsState.draft.id]?.result" class="dialog-test-result">
                    <div class="dialog-test-result-head">
                      <div>
                        <span>响应结果</span>
                        <strong>连接测试已完成</strong>
                      </div>
                      <span class="badge badge-success">HTTP {{ testSummaryFor(settingsState.testState[settingsState.draft.id].result).status }}</span>
                    </div>
                    <div class="test-response-metrics">
                      <div>
                        <span>状态码</span>
                        <strong>{{ testSummaryFor(settingsState.testState[settingsState.draft.id].result).status }}</strong>
                      </div>
                      <div>
                        <span>耗时</span>
                        <strong>{{ testSummaryFor(settingsState.testState[settingsState.draft.id].result).duration }}</strong>
                      </div>
                    </div>
                    <div class="test-response-url"><span>请求</span><strong>{{ testSummaryFor(settingsState.testState[settingsState.draft.id].result).requestUrl }}</strong></div>
                    <div class="response-preview-title">
                      <span>响应预览</span>
                      <strong>JSON</strong>
                    </div>
                    <pre>{{ testSummaryFor(settingsState.testState[settingsState.draft.id].result).rawPreview }}</pre>
                  </div>
                </div>
                </section>
              </div>
            </div>
            <div v-if="getModelIdentifierError(settingsState.draft.model)" class="inline-message inline-danger">{{ getModelIdentifierError(settingsState.draft.model) }}</div>
            <div v-if="getModelIdentifierError(settingsState.draft.modelNameOverride)" class="inline-message inline-danger">{{ getModelIdentifierError(settingsState.draft.modelNameOverride) }}</div>
            <div v-if="draftMissingFieldLabels.length" class="inline-message inline-warn">请先填写：{{ draftMissingFieldsText }}。</div>
            <div v-if="settingsState.modelListState[settingsState.draft.id]?.result" class="settings-dialog-models">
              <div class="status-row">
                <span class="badge badge-success">已获取 {{ settingsState.draft.availableModels.length }} 个模型</span>
                <span class="history-time">保存后会使用当前主模型创作</span>
              </div>
            </div>
            <div class="settings-dialog-actions">
              <button class="button-secondary" :disabled="!canTestDraftModel || settingsState.testState[settingsState.draft.id]?.loading" :title="draftTestDisabledTitle" @click="testModel(getDraftModel(), getDraftSetting())">
                {{ settingsState.testState[settingsState.draft.id]?.loading ? "测试中..." : "测试连接" }}
              </button>
              <button class="button-secondary" @click="closeSettingsDialog">取消</button>
              <button :disabled="!canSaveDraft()" :title="draftSaveDisabledTitle" @click="saveDialog">保存</button>
            </div>
            <div v-if="settingsState.modelListState[settingsState.draft.id]?.error" class="inline-message inline-danger">{{ settingsState.modelListState[settingsState.draft.id].error }}</div>
            <div v-if="settingsState.testState[settingsState.draft.id]?.error" class="inline-message inline-danger">{{ settingsState.testState[settingsState.draft.id].error }}</div>
            <div v-else-if="settingsState.testState[settingsState.draft.id]?.result" class="inline-message inline-success">
              测试成功，耗时 {{ testSummaryFor(settingsState.testState[settingsState.draft.id].result).duration }}。
            </div>
          </section>
        </div>
      </section>

      <div v-if="mediaPreviewState.asset" class="media-preview-backdrop" role="dialog" aria-modal="true" aria-label="媒体预览" @click.self="closeMediaPreview">
        <section class="media-preview-panel">
          <div class="media-preview-actions">
            <div class="media-preview-title">
              <strong>{{ generatedAssetReferenceFileName(mediaPreviewState.asset) }}</strong>
              <span>{{ assetDisplayLabel(mediaPreviewState.asset) }}</span>
            </div>
            <div class="media-preview-button-row">
              <span class="sr-only">{{ mediaPreviewActionLabels(mediaPreviewState.asset.assetType).join("、") }}</span>
              <div v-if="mediaPreviewState.asset.assetType === 'image'" class="media-zoom-controls" aria-label="图片缩放">
                <button class="button-secondary media-icon-button" type="button" title="缩小" aria-label="缩小" @click="zoomMediaPreview(-0.25)">
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M5 12h14" />
                  </svg>
                </button>
                <button class="button-secondary media-scale-button" type="button" title="重置缩放" @click="resetMediaPreviewTransform">
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M4.5 12a7.5 7.5 0 0 1 12.8-5.3L20 9.4" />
                    <path d="M20 4.5v4.9h-4.9" />
                    <path d="M19.5 12a7.5 7.5 0 0 1-12.8 5.3L4 14.6" />
                    <path d="M4 19.5v-4.9h4.9" />
                  </svg>
                  <span>{{ Math.round(mediaPreviewState.scale * 100) }}%</span>
                </button>
                <button class="button-secondary media-icon-button" type="button" title="放大" aria-label="放大" @click="zoomMediaPreview(0.25)">
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M12 5v14" />
                    <path d="M5 12h14" />
                  </svg>
                </button>
              </div>
              <a class="button-secondary media-action-button" :href="mediaPreviewState.asset.url" download target="_blank" rel="noreferrer">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 4v10" />
                  <path d="m8 10 4 4 4-4" />
                  <path d="M5 19h14" />
                </svg>
                <span>保存</span>
              </a>
              <button
                v-if="mediaPreviewState.asset.assetType === 'image'"
                class="button-secondary media-action-button"
                @click="useGeneratedAsset(mediaPreviewState.asset); closeMediaPreview()"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M8 12h8" />
                  <path d="M12 8v8" />
                  <path d="M4 7.5A3.5 3.5 0 0 1 7.5 4h9A3.5 3.5 0 0 1 20 7.5v9a3.5 3.5 0 0 1-3.5 3.5h-9A3.5 3.5 0 0 1 4 16.5z" />
                </svg>
                <span>引用编辑</span>
              </button>
              <button
                v-if="mediaPreviewState.asset.assetType === 'image'"
                class="button-secondary media-action-button"
                @click="editSelectedAsset(mediaPreviewState.asset)"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M5 19 16.5 7.5" />
                  <path d="m14.5 5.5 4 4" />
                  <path d="M4 20h5" />
                </svg>
                <span>选取编辑</span>
              </button>
              <button class="button-link media-icon-button media-close-button" type="button" title="关闭" aria-label="关闭" @click="closeMediaPreview">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M6 6l12 12" />
                  <path d="M18 6 6 18" />
                </svg>
              </button>
            </div>
          </div>
          <div
            :class="['media-preview-stage', mediaPreviewState.asset.assetType === 'image' ? 'media-preview-stage-image' : '', mediaPreviewState.dragging ? 'media-preview-stage-dragging' : '']"
            @wheel.prevent="handleMediaPreviewWheel"
            @pointerdown="startMediaPreviewPan"
            @pointermove="moveMediaPreviewPan"
            @pointerup="stopMediaPreviewPan"
            @pointercancel="stopMediaPreviewPan"
            @dblclick="resetMediaPreviewTransform"
          >
            <img
              v-if="mediaPreviewState.asset.assetType === 'image'"
              :src="mediaPreviewState.asset.url"
              alt="生成图片预览"
              :style="{ transform: mediaPreviewTransform() }"
              draggable="false"
            />
            <video
              v-else-if="mediaPreviewState.asset.assetType === 'video'"
              :src="mediaPreviewState.asset.url"
              :poster="mediaPreviewState.asset.thumbnailUrl || undefined"
              controls
              autoplay
              playsinline
            />
          </div>
        </section>
      </div>
    </main>
    <div v-if="toastState.visible" :class="['app-toast', `app-toast-${toastState.type}`]">{{ toastState.message }}</div>
  </div>
</template>
