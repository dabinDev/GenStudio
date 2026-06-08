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
  updateLocalConversationMessage,
  updateLocalConversationTaskMessage,
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

type ViewName = "auth" | "auth-error" | "text" | "images" | "videos" | "settings" | "profile" | "admin";
type SidebarFilter = Capability | "all";
type VideoMode = VideoModeValue;
type DialogMode = "create" | "edit";
type ComposerPopover = "image-settings" | "image-advanced" | "video-mode" | "video-settings" | "video-advanced" | null;
type AdminTab = "overview" | "models" | "prompts" | "users" | "text-records" | "image-records" | "video-records" | "audit";

interface ImageResult {
  images: Array<{ src: string; revisedPrompt?: string }>;
  taskId?: string;
  status?: string;
  progress?: number | string | null;
  raw: Record<string, unknown>;
  conversation?: ConversationDefinition;
  assistantMessage?: ConversationMessage;
}

interface TextResult {
  content: string;
  usage?: Record<string, unknown>;
  raw: Record<string, unknown>;
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

const store = useWorkbenchStore();
const auth = useAuthStore();
const view = ref<ViewName>(getViewFromHash());
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

const adminTabs: Array<{ value: AdminTab; label: string; hint: string }> = [
  { value: "overview", label: "运营面板", hint: "调用、失败率、公私模型分布" },
  { value: "models", label: "公用模型配置", hint: "发布、取消公用、图标、提示语" },
  { value: "prompts", label: "提示语模板", hint: "AI 文案优化模板" },
  { value: "users", label: "用户管理", hint: "启用、禁用、删除、恢复" },
  { value: "text-records", label: "文案记录", hint: "提示词与响应追踪" },
  { value: "image-records", label: "生图记录", hint: "图片结果与参数" },
  { value: "video-records", label: "视频记录", hint: "任务、视频、失败原因" },
  { value: "audit", label: "操作记录", hint: "管理员变更审计" },
];

const adminCapabilityTabs: Array<{ value: Capability | "all"; label: string }> = [
  { value: "all", label: "全部" },
  { value: "text", label: "文案创作" },
  { value: "image", label: "图片创作" },
  { value: "video", label: "视频创作" },
];

const adminState = reactive({
  activeTab: "overview" as AdminTab,
  loading: false,
  saving: "",
  error: "",
  success: "",
  modelCapability: "all" as Capability | "all",
  modelPublicState: "all" as "all" | "public" | "private",
  modelSearch: "",
  userSearch: "",
  recordStatus: "",
  recordUserId: "",
  recordModelGroupId: "",
  auditAction: "",
  auditAdminUserId: "",
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
    preview: "",
  },
});

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
});

const composerUiState = reactive({
  popover: null as ComposerPopover,
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

const userAccountLabel = computed(() => {
  if (!auth.state.user) return auth.state.loading ? "登录状态读取中" : "可使用官网授权或本地账号登录";
  return auth.state.user.email || auth.state.user.phone || "已登录";
});

onMounted(async () => {
  await initializeSession();
  syncProfileForm();
  syncInitialModels();
  handleHashChange();
  window.addEventListener("hashchange", handleHashChange);
});

onUnmounted(() => {
  stopImagePolling();
  stopVideoPolling();
  window.removeEventListener("hashchange", handleHashChange);
});

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
  closeComposerPopover();
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

function formatConversationTime(value: string): string {
  const time = new Date(value);
  if (Number.isNaN(time.getTime())) return "";
  return time.toLocaleString("zh-CN", { hour12: false });
}

function openMediaPreview(asset: ConversationAsset) {
  mediaPreviewState.asset = asset;
}

function closeMediaPreview() {
  mediaPreviewState.asset = null;
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
  if (tab === "image-records") return "image";
  if (tab === "video-records") return "video";
  return "text";
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
  adminState.saving = `${model.id}:public`;
  adminState.error = "";
  try {
    const updated = model.isPublic ? await unpublishAdminModel(model.id) : await publishAdminModel(model.id);
    const nextModel = mapServerModel(updated);
    const index = adminState.models.findIndex((item) => item.id === model.id);
    if (index >= 0) adminState.models[index] = nextModel;
    delete adminState.modelDrafts[model.id];
    ensureAdminModelDraft(nextModel);
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
    const template = await saveAdminPromptTemplateApi(adminState.templateDraft.id || "new", {
      capability: adminState.templateDraft.capability,
      modelGroupId: adminState.templateDraft.modelGroupId,
      templateType: "prompt_optimize",
      name: adminState.templateDraft.name,
      content: adminState.templateDraft.content,
      enabled: adminState.templateDraft.enabled,
    });
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
    const result = await testAdminPromptTemplateApi({
      capability: adminState.templateDraft.capability,
      content: adminState.templateDraft.content,
      prompt: adminState.templateDraft.testPrompt,
    });
    adminState.templateDraft.preview = result.prompt;
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
    showToast("用户信息已保存", "success");
  } catch (error) {
    adminState.error = adminSaveError(error, "保存用户失败。");
    showToast(adminState.error, "error");
  } finally {
    adminState.saving = "";
  }
}

async function setAdminUserStatus(user: AdminUserDefinition, action: "enable" | "disable" | "delete" | "restore") {
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
      userId: adminState.recordUserId,
      modelGroupId: adminState.recordModelGroupId,
      status: adminState.recordStatus,
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

function switchAdminTab(tab: AdminTab) {
  adminState.activeTab = tab;
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
      { role: "user", content: finalPrompt },
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
    if (response.conversation) {
      setCurrentConversation(response.conversation);
      simulateStreamingPreview(response.assistantMessage);
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

async function handleImageUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const model = activeModel.value;
  const setting = activeSetting.value;
  if (!model || !setting || !input.files?.length) return;
  imageState.uploading = true;
  imageState.error = "";
  try {
    const uploaded = await Promise.all(
      Array.from(input.files).map((file) => uploadAsset(file, buildUploadConfig(model, setting))),
    );
    imageState.references = [...imageState.references, ...uploaded].slice(0, imageReferenceLimit.value);
  } catch (error) {
    imageState.error = error instanceof Error ? error.message : "上传参考图失败。";
  } finally {
    input.value = "";
    imageState.uploading = false;
  }
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
      { role: "user", content: finalPrompt },
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

async function uploadVideoFiles(event: Event, target: "unified" | "first" | "last" | "seedanceRef") {
  const input = event.target as HTMLInputElement;
  const model = activeModel.value;
  const setting = activeSetting.value;
  if (!model || !setting || !input.files?.length) return;

  videoState.uploading = true;
  videoState.error = "";
  try {
    const uploaded = await Promise.all(
      Array.from(input.files).map((file) => uploadAsset(file, buildUploadConfig(model, setting))),
    );
    if (target === "unified") {
      videoState.unifiedImages = [...videoState.unifiedImages, ...uploaded].slice(0, unifiedVideoImageLimit.value);
    }
    if (target === "first") videoState.seedanceFirst = uploaded[0] || null;
    if (target === "last") videoState.seedanceLast = uploaded[0] || null;
    if (target === "seedanceRef") videoState.seedanceReferences.push(...uploaded);
  } catch (error) {
    videoState.error = error instanceof Error ? error.message : "素材上传失败。";
  } finally {
    input.value = "";
    videoState.uploading = false;
  }
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

async function removeModelFromWorkbench(modelId: string) {
  const model = store.models.value.find((item) => item.id === modelId);
  if (model && !canEditModel(model)) {
    settingsState.testState[modelId] = { ...createIdleState<TestRequestResult>(), error: "公共模型只有管理员可以删除。" };
    showToast(settingsState.testState[modelId].error, "error");
    return;
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

async function batchDelete() {
  const editableModels = selectedVisibleSettingsModels.value.filter((model) => canEditModel(model));
  const ids = editableModels.map((model) => model.id);
  if (ids.length !== selectedVisibleSettingsModels.value.length) {
    showToast("公共模型已跳过，只有管理员可以删除。", "info");
  }
  await Promise.allSettled(ids.map((modelId) => removeModelFromWorkbench(modelId)));
  settingsState.selectedIds = settingsState.selectedIds.filter((selectedId) => !ids.includes(selectedId));
}
</script>

<template>
  <div :class="['shell', view === 'admin' ? 'shell-admin' : '']">
    <aside v-if="view !== 'admin'" class="sidebar">
      <div class="sidebar-logo">
        <div class="logo-mark">
          <img src="/brand/cylon-studio-logo.png" alt="塞隆studio" />
        </div>
        <div>
          <strong>塞隆studio</strong>
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
          <button v-if="auth.state.user?.isAdmin" class="topbar-icon-button" @click="navigate('admin')">后台</button>
          <button class="topbar-icon-button" @click="navigate('settings')">设置</button>
          <button class="topbar-icon-button" @click="navigate('profile')">个人</button>
        </div>
      </div>

      <section v-if="view !== 'auth' && view !== 'auth-error' && view !== 'settings' && view !== 'profile' && view !== 'admin'" class="studio-panel">
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
              <strong>{{ conversation.title }}</strong>
              <span>{{ CAPABILITY_LABELS[conversation.capability] }} · {{ formatConversationTime(conversation.updatedAt) }}</span>
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
                  <button v-if="asset.assetType === 'image'" class="asset-preview-trigger" @click="openMediaPreview(asset)">
                    <img :src="asset.url" alt="生成图片" />
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

        <div class="composer-card">
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

          <div v-if="view === 'images'" class="composer-surface">
            <div class="composer-attach-row">
              <label class="button-secondary composer-attach-button">
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
                <img :src="asset.localPreviewUrl" :alt="asset.fileName" />
                <button title="移除参考图" @click="removeImageReference(asset.id)">×</button>
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
                        <img :src="asset.localPreviewUrl" :alt="asset.fileName" />
                        <div class="asset-card-body"><strong>{{ asset.fileName }}</strong><p class="muted">{{ asset.publicUrl }}</p></div>
                      </article>
                    </div>
                    <p v-else class="muted">还没有上传参考图。</p>
                    <label class="field field-full"><span>高级参数 JSON</span><textarea v-model="imageState.extraJson" /></label>
                  </section>
                </div>
              </div>
              <button class="composer-submit-button" :disabled="imageState.loading" @click="handleImageSubmit">生成</button>
              <button class="button-secondary" :disabled="imageState.loading || !imageTaskIdFromConversation()" @click="() => handleImageQuery()">查询</button>
            </div>
            <div v-if="imageState.error" class="inline-message inline-danger">{{ imageState.error }}</div>
          </div>

          <div v-if="view === 'videos'" class="composer-surface">
            <div class="composer-attach-row composer-video-attach-row">
              <button v-if="supportsUnifiedAdapter(activeModel?.adapter) && videoState.mode === 'text'" class="button-secondary composer-attach-button" disabled>无需素材</button>
              <label v-else-if="supportsUnifiedAdapter(activeModel?.adapter)" class="button-secondary composer-attach-button">
                {{ videoState.uploading ? "上传中" : "+ 参考图" }}
                <input hidden type="file" accept="image/png,image/jpeg,image/jpg,image/webp" :multiple="unifiedVideoAllowsMultiple" @change="(event) => uploadVideoFiles(event, 'unified')" />
              </label>
              <label v-if="activeModel?.adapter === 'video-seedance' && videoState.mode === 'reference'" class="button-secondary composer-attach-button">
                + 参考图
                <input hidden type="file" multiple accept="image/png,image/jpeg,image/jpg,image/webp" @change="(event) => uploadVideoFiles(event, 'seedanceRef')" />
              </label>
              <label v-if="activeModel?.adapter === 'video-seedance' && videoState.mode === 'first-frame'" class="button-secondary composer-attach-button">
                首帧<input hidden type="file" accept="image/png,image/jpeg,image/jpg,image/webp" @change="(event) => uploadVideoFiles(event, 'first')" />
              </label>
              <div v-if="activeModel?.adapter === 'video-seedance' && videoState.mode === 'start-end'" class="composer-frame-actions">
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
                <img :src="asset.localPreviewUrl" :alt="asset.fileName" />
                <button title="移除参考图" @click="removeUnifiedVideoReference(asset.id)">×</button>
              </article>
              <article v-if="videoState.seedanceFirst" class="reference-thumb">
                <img :src="videoState.seedanceFirst.localPreviewUrl" :alt="videoState.seedanceFirst.fileName" />
                <span>首帧</span>
                <button title="移除首帧" @click="videoState.seedanceFirst = null">×</button>
              </article>
              <article v-if="videoState.seedanceLast" class="reference-thumb">
                <img :src="videoState.seedanceLast.localPreviewUrl" :alt="videoState.seedanceLast.fileName" />
                <span>尾帧</span>
                <button title="移除尾帧" @click="videoState.seedanceLast = null">×</button>
              </article>
              <article v-for="asset in videoState.seedanceReferences" :key="asset.id" class="reference-thumb">
                <img :src="asset.localPreviewUrl" :alt="asset.fileName" />
                <button title="移除参考图" @click="removeSeedanceReference(asset.id)">×</button>
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
              <div class="composer-video-actions">
                <button class="composer-submit-button" :disabled="videoState.loading" @click="handleVideoCreate">创建</button>
                <button class="button-secondary" :disabled="videoState.querying || !videoState.createResult?.taskId" @click="() => handleVideoQuery()">查询</button>
              </div>
            </div>
            <div v-if="videoState.error" class="inline-message inline-danger">{{ videoState.error }}</div>
          </div>
        </div>
      </section>

      <section v-else-if="view === 'auth'" class="auth-page">
        <section class="auth-panel">
          <div class="auth-copy">
            <p class="eyebrow">Account</p>
            <h2>登录 塞隆studio</h2>
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
                <span>从官网进入塞隆studio，回调地址为 /auth/callback?code=xxx。</span>
              </div>
            </div>
          </div>
        </section>
      </section>

      <section v-else-if="view === 'auth-error'" class="auth-page">
        <section class="auth-panel auth-error-panel">
          <div class="auth-copy">
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
          <button @click="navigate('images')">返回创作</button>
        </section>

        <template v-else>
          <section class="admin-hero">
            <div class="admin-brand-block">
              <div class="admin-brand-mark">
                <img src="/brand/cylon-studio-logo.png" alt="Cylon Studio" />
              </div>
              <div>
                <span>塞隆studio</span>
                <strong>Admin Ops</strong>
              </div>
            </div>
            <div>
              <p class="eyebrow">Admin Console</p>
              <h2>塞隆studio 管理后台</h2>
              <p class="muted">管理公用模型、提示语模板、用户状态、调用记录和后台操作审计。</p>
            </div>
            <div class="admin-hero-actions">
              <button class="button-secondary" @click="navigate('images')">返回创作台</button>
              <span class="badge badge-success">主管理员</span>
              <button class="button-secondary" :disabled="adminState.loading" @click="loadAdminTab()">刷新当前页</button>
            </div>
          </section>

          <div class="admin-shell">
            <nav class="admin-tabs" aria-label="后台功能">
              <button
                v-for="tab in adminTabs"
                :key="tab.value"
                :class="['admin-tab', adminState.activeTab === tab.value ? 'admin-tab-active' : '']"
                @click="switchAdminTab(tab.value)"
              >
                <strong>{{ tab.label }}</strong>
                <span>{{ tab.hint }}</span>
              </button>
            </nav>

            <section class="admin-panel">
              <div v-if="adminState.error" class="inline-message inline-danger">{{ adminState.error }}</div>
              <div v-if="adminState.loading" class="admin-loading">加载中...</div>

              <template v-if="adminState.activeTab === 'overview'">
                <div class="admin-panel-head">
                  <div>
                    <h3>运营面板</h3>
                    <p class="muted">按用户和模型查看公用模型、私有模型调用情况。</p>
                  </div>
                  <button class="button-secondary" @click="loadAdminOverview">刷新统计</button>
                </div>
                <div class="admin-metrics">
                  <article class="admin-metric"><span>总调用</span><strong>{{ adminState.overview?.totalCalls || 0 }}</strong></article>
                  <article class="admin-metric"><span>成功</span><strong>{{ adminState.overview?.successCalls || 0 }}</strong></article>
                  <article class="admin-metric"><span>失败</span><strong>{{ adminState.overview?.failedCalls || 0 }}</strong></article>
                  <article class="admin-metric"><span>失败率</span><strong>{{ ((adminState.overview?.failureRate || 0) * 100).toFixed(1) }}%</strong></article>
                  <article class="admin-metric"><span>公用模型调用</span><strong>{{ adminState.overview?.publicModelCalls || 0 }}</strong></article>
                  <article class="admin-metric"><span>私有模型调用</span><strong>{{ adminState.overview?.privateModelCalls || 0 }}</strong></article>
                </div>
                <div class="admin-dual-grid">
                  <section class="admin-subpanel">
                    <h4>用户调用排行</h4>
                    <div class="admin-table">
                      <div class="admin-table-head"><span>用户</span><span>总调用</span><span>公用</span><span>私有</span><span>失败</span></div>
                      <div v-for="row in adminState.overviewUsers" :key="row.user.id" class="admin-table-row">
                        <span>{{ row.user.nickname || row.user.email || row.user.id }}</span>
                        <strong>{{ row.totalCalls }}</strong>
                        <span>{{ row.publicModelCalls }}</span>
                        <span>{{ row.privateModelCalls }}</span>
                        <span>{{ row.failedCalls }}</span>
                      </div>
                      <p v-if="!adminState.overviewUsers.length" class="admin-empty">暂无用户调用数据</p>
                    </div>
                  </section>
                  <section class="admin-subpanel">
                    <h4>模型调用排行</h4>
                    <div class="admin-table">
                      <div class="admin-table-head"><span>模型</span><span>总调用</span><span>成功</span><span>失败</span><span>均耗时</span></div>
                      <div v-for="row in adminState.overviewModels" :key="row.model.id" class="admin-table-row">
                        <span>{{ modelDisplayName(mapServerModel(row.model)) }}</span>
                        <strong>{{ row.totalCalls }}</strong>
                        <span>{{ row.successCalls }}</span>
                        <span>{{ row.failedCalls }}</span>
                        <span>{{ row.averageDurationMs }}ms</span>
                      </div>
                      <p v-if="!adminState.overviewModels.length" class="admin-empty">暂无模型调用数据</p>
                    </div>
                  </section>
                </div>
              </template>

              <template v-else-if="adminState.activeTab === 'models'">
                <div class="admin-panel-head">
                  <div>
                    <h3>公用模型配置</h3>
                    <p class="muted">设置公用模型、展示名称、提示语 hint、图标资源和 AI 文案优化开关。</p>
                  </div>
                  <button class="button-secondary" @click="loadAdminModels">刷新模型</button>
                </div>
                <div class="admin-toolbar">
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
                <div class="admin-model-list">
                  <article v-for="model in adminState.models" :key="model.id" class="admin-model-card">
                    <div class="admin-model-card-main">
                      <div :class="['model-avatar', `model-avatar-${model.capability}`, modelIconUrl(model) ? 'model-avatar-has-icon' : '']">
                        <img v-if="modelIconUrl(model)" :src="modelIconUrl(model)" :alt="modelDisplayName(model)" loading="lazy" @error="hideBrokenModelIcon" />
                        <span>{{ model.capability === 'text' ? 'T' : model.capability === 'image' ? 'I' : 'V' }}</span>
                      </div>
                      <div>
                        <div class="admin-model-title">
                          <strong>{{ modelDisplayName(model) }}</strong>
                          <span :class="['badge', model.isPublic ? 'badge-success' : 'badge-warn']">{{ model.isPublic ? "公用" : "私有" }}</span>
                          <span class="badge">{{ CAPABILITY_LABELS[model.capability] }}</span>
                        </div>
                        <p class="muted">{{ modelSummaryText(model) }}</p>
                      </div>
                    </div>
                    <div v-if="adminState.modelDrafts[model.id]" class="admin-model-form">
                      <label><span>公用展示名</span><input v-model="adminState.modelDrafts[model.id].publicDisplayName" /></label>
                      <label><span>图标 URL</span><input v-model="adminState.modelDrafts[model.id].iconUrl" placeholder="https://...svg" /></label>
                      <label class="field-full"><span>公用描述</span><textarea v-model="adminState.modelDrafts[model.id].publicDescription" /></label>
                      <label class="field-full"><span>输入框默认提示语 hint</span><textarea v-model="adminState.modelDrafts[model.id].inputHint" /></label>
                      <label><span>标签</span><input v-model="adminState.modelDrafts[model.id].publicTagsText" placeholder="公用, 推荐" /></label>
                      <label class="admin-check"><input v-model="adminState.modelDrafts[model.id].promptOptimizeEnabled" type="checkbox" /> 启用 AI 文案优化</label>
                      <label class="field-full"><span>默认参数 JSON</span><textarea v-model="adminState.modelDrafts[model.id].defaultParametersText" /></label>
                    </div>
                    <div class="admin-row-actions">
                      <button class="button-secondary" :disabled="adminState.saving === model.id" @click="saveAdminModel(model)">保存配置</button>
                      <button :class="model.isPublic ? 'button-danger' : ''" :disabled="adminState.saving === `${model.id}:public`" @click="toggleAdminPublicModel(model)">
                        {{ model.isPublic ? "取消公用" : "设为公用" }}
                      </button>
                    </div>
                  </article>
                  <p v-if="!adminState.models.length" class="admin-empty">暂无匹配模型</p>
                </div>
              </template>

              <template v-else-if="adminState.activeTab === 'prompts'">
                <div class="admin-panel-head">
                  <div>
                    <h3>提示语模板</h3>
                    <p class="muted">用于三种创作模式里 AI 图标的提示词优化能力，可配置全局或指定模型。</p>
                  </div>
                  <button class="button-secondary" @click="loadPromptTemplates">刷新模板</button>
                </div>
                <div class="admin-template-layout">
                  <section class="admin-subpanel">
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
                    <h4>测试结果</h4>
                    <label class="field field-full"><span>测试提示词</span><textarea v-model="adminState.templateDraft.testPrompt" /></label>
                    <pre class="admin-preview">{{ adminState.templateDraft.preview || "点击测试预览后显示渲染结果。" }}</pre>
                    <h4>已有模板</h4>
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
                </div>
              </template>

              <template v-else-if="adminState.activeTab === 'users'">
                <div class="admin-panel-head">
                  <div>
                    <h3>用户管理</h3>
                    <p class="muted">支持编辑资料、启用、禁用、软删除和恢复用户。</p>
                  </div>
                  <button class="button-secondary" @click="loadAdminUsers">刷新用户</button>
                </div>
                <div class="admin-toolbar">
                  <label class="settings-search-box admin-search"><span>搜索</span><input v-model="adminState.userSearch" placeholder="邮箱、昵称、手机号、ID" @keyup.enter="loadAdminUsers" /></label>
                  <button class="button-secondary" @click="loadAdminUsers">筛选</button>
                </div>
                <div class="admin-user-list">
                  <article v-for="user in adminState.users" :key="user.id" class="admin-user-row">
                    <div class="admin-user-avatar">{{ (user.nickname || user.email || "U").slice(0, 1) }}</div>
                    <div class="admin-user-fields">
                      <label><span>昵称</span><input v-model="user.nickname" /></label>
                      <label><span>邮箱</span><input v-model="user.email" /></label>
                      <label><span>手机</span><input v-model="user.phone" /></label>
                      <label><span>状态</span><select v-model="user.status"><option value="active">active</option><option value="disabled">disabled</option><option value="deleted">deleted</option></select></label>
                    </div>
                    <div class="admin-row-actions">
                      <span :class="['badge', user.status === 'active' ? 'badge-success' : 'badge-warn']">{{ user.isAdmin ? "管理员" : user.status }}</span>
                      <button class="button-secondary" :disabled="adminState.saving === user.id" @click="saveAdminUser(user)">保存</button>
                      <button class="button-secondary" :disabled="user.isAdmin" @click="setAdminUserStatus(user, 'enable')">启用</button>
                      <button class="button-secondary" :disabled="user.isAdmin" @click="setAdminUserStatus(user, 'disable')">禁用</button>
                      <button class="button-danger" :disabled="user.isAdmin" @click="setAdminUserStatus(user, 'delete')">删除</button>
                      <button class="button-secondary" :disabled="user.isAdmin" @click="setAdminUserStatus(user, 'restore')">恢复</button>
                    </div>
                  </article>
                  <p v-if="!adminState.users.length" class="admin-empty">暂无用户</p>
                </div>
              </template>

              <template v-else-if="adminState.activeTab === 'text-records' || adminState.activeTab === 'image-records' || adminState.activeTab === 'video-records'">
                <div class="admin-panel-head">
                  <div>
                    <h3>{{ adminState.activeTab === 'text-records' ? '文案记录' : adminState.activeTab === 'image-records' ? '生图记录' : '视频记录' }}</h3>
                    <p class="muted">按用户、模型、调用时间查看提示词、响应、参数、资产和失败原因。</p>
                  </div>
                  <button class="button-secondary" @click="loadAdminRecords(capabilityForAdminRecordTab(adminState.activeTab))">刷新记录</button>
                </div>
                <div class="admin-toolbar">
                  <select v-model="adminState.recordStatus" @change="loadAdminRecords(capabilityForAdminRecordTab(adminState.activeTab))">
                    <option value="">全部状态</option>
                    <option value="success">success</option>
                    <option value="error">error</option>
                    <option value="processing">processing</option>
                  </select>
                  <label class="settings-search-box admin-search"><span>用户 ID</span><input v-model="adminState.recordUserId" placeholder="可选" @keyup.enter="loadAdminRecords(capabilityForAdminRecordTab(adminState.activeTab))" /></label>
                  <label class="settings-search-box admin-search"><span>模型 ID</span><input v-model="adminState.recordModelGroupId" placeholder="可选" @keyup.enter="loadAdminRecords(capabilityForAdminRecordTab(adminState.activeTab))" /></label>
                  <button class="button-secondary" @click="loadAdminRecords(capabilityForAdminRecordTab(adminState.activeTab))">筛选</button>
                </div>
                <div class="admin-record-list">
                  <article v-for="record in adminRecordList(adminState.activeTab)" :key="record.id" class="admin-record-card">
                    <div class="admin-record-head">
                      <div>
                        <strong>{{ record.modelName || "未知模型" }}</strong>
                        <span>{{ record.user?.nickname || record.user?.email || "未知用户" }} / {{ formatConversationTime(record.createdAt) }}</span>
                      </div>
                      <span :class="['badge', record.status === 'success' ? 'badge-success' : record.status === 'error' ? 'badge-danger' : 'badge-warn']">{{ record.status }}</span>
                    </div>
                    <div class="admin-record-detail">
                      <div><span>提示词</span><p>{{ record.prompt || "-" }}</p></div>
                      <div><span>响应</span><p>{{ record.response || record.errorMessage || "-" }}</p></div>
                      <div v-if="record.taskId"><span>任务 ID</span><p>{{ record.taskId }}</p></div>
                      <div><span>请求参数</span><pre>{{ compactJson(record.requestParams || {}) }}</pre></div>
                      <div><span>响应摘要</span><pre>{{ compactJson(record.responseSummary || {}) }}</pre></div>
                    </div>
                    <div v-if="record.assets?.length" class="admin-record-assets">
                      <a v-for="asset in record.assets" :key="asset.url" :href="asset.url" target="_blank" rel="noreferrer">
                        <img v-if="asset.type === 'image'" :src="asset.thumbnailUrl || asset.url" alt="record asset" />
                        <span v-else>打开视频</span>
                      </a>
                    </div>
                  </article>
                  <p v-if="!adminRecordList(adminState.activeTab).length" class="admin-empty">暂无记录</p>
                </div>
              </template>

              <template v-else-if="adminState.activeTab === 'audit'">
                <div class="admin-panel-head">
                  <div>
                    <h3>操作记录</h3>
                    <p class="muted">记录公用模型、模板、用户管理等后台变更。</p>
                  </div>
                  <button class="button-secondary" @click="loadAdminAuditLogs">刷新审计</button>
                </div>
                <div class="admin-toolbar">
                  <label class="settings-search-box admin-search"><span>动作</span><input v-model="adminState.auditAction" placeholder="publish_model" @keyup.enter="loadAdminAuditLogs" /></label>
                  <label class="settings-search-box admin-search"><span>管理员 ID</span><input v-model="adminState.auditAdminUserId" placeholder="可选" @keyup.enter="loadAdminAuditLogs" /></label>
                  <button class="button-secondary" @click="loadAdminAuditLogs">筛选</button>
                </div>
                <div class="admin-table admin-audit-table">
                  <div class="admin-table-head"><span>时间</span><span>动作</span><span>目标</span><span>状态</span><span>摘要</span></div>
                  <div v-for="log in adminState.auditLogs" :key="log.id" class="admin-table-row">
                    <span>{{ formatConversationTime(log.createdAt) }}</span>
                    <strong>{{ log.action }}</strong>
                    <span>{{ log.targetType }} / {{ log.targetId }}</span>
                    <span>{{ log.status }}</span>
                    <pre>{{ compactJson(log.summary || {}) }}</pre>
                  </div>
                  <p v-if="!adminState.auditLogs.length" class="admin-empty">暂无操作记录</p>
                </div>
              </template>
            </section>
          </div>
        </template>
      </section>

      <section v-else class="settings-page">
        <section class="settings-hero">
          <div>
            <p class="eyebrow">Model Settings</p>
            <h2>模型配置</h2>
            <p class="muted">{{ auth.state.user ? "配置会保存到塞隆studio数据库，密钥只由后端调用。" : "未登录时配置会缓存在当前浏览器，登录后可保存到数据库。" }}</p>
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

      <div v-if="mediaPreviewState.asset" class="media-preview-backdrop" @click.self="closeMediaPreview">
        <section class="media-preview-panel" aria-label="媒体预览">
          <div class="media-preview-stage">
            <img
              v-if="mediaPreviewState.asset.assetType === 'image'"
              :src="mediaPreviewState.asset.url"
              alt="生成图片预览"
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
          <div class="media-preview-actions">
            <div>
              <strong>{{ generatedAssetReferenceFileName(mediaPreviewState.asset) }}</strong>
              <span>{{ mediaPreviewState.asset.assetType === "image" ? "图片创作结果" : "视频创作结果" }}</span>
            </div>
            <div class="media-preview-button-row">
              <span class="sr-only">{{ mediaPreviewActionLabels(mediaPreviewState.asset.assetType).join("、") }}</span>
              <a class="button-secondary" :href="mediaPreviewState.asset.url" download target="_blank" rel="noreferrer">保存</a>
              <button
                v-if="mediaPreviewState.asset.assetType === 'image'"
                class="button-secondary"
                @click="useGeneratedAsset(mediaPreviewState.asset); closeMediaPreview()"
              >
                引用编辑
              </button>
              <button
                v-if="mediaPreviewState.asset.assetType === 'image'"
                class="button-secondary"
                @click="editSelectedAsset(mediaPreviewState.asset)"
              >
                选取编辑
              </button>
              <button class="button-link" @click="closeMediaPreview">关闭</button>
            </div>
          </div>
        </section>
      </div>
    </main>
    <div v-if="toastState.visible" :class="['app-toast', `app-toast-${toastState.type}`]">{{ toastState.message }}</div>
  </div>
</template>
