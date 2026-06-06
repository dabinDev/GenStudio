<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";

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
  fetchConversation,
  fetchConversations,
  fetchServerModels,
  postProxy,
  postProxyWithSignal,
  setServerPrimaryModel,
  syncServerModel,
  updateServerModel,
  uploadAsset,
} from "./api";
import { useAuthStore } from "./stores/auth";
import { useWorkbenchStore } from "./stores/workbench";
import type {
  Adapter,
  Capability,
  ConversationAsset,
  ConversationDefinition,
  ConversationMessage,
  ModelDefinition,
  ModelSetting,
  PromptTemplate,
  SubModelDefinition,
  UploadedAsset,
} from "./types";
import {
  appendLocalConversationMessages,
  combinePrompt,
  createLocalId,
  findPromptBeforeMessage,
  generatedAssetReferenceFileName,
  getModelIdentifierError,
  pickPrimaryModel,
  renderMarkdownPreview,
  resolveModelName,
  shouldResetConversationForModelSwitch,
  shortText,
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

type ViewName = "text" | "images" | "videos" | "settings" | "profile";
type SidebarFilter = Capability | "all";
type VideoMode = "text" | "reference" | "start-end";
type DialogMode = "create" | "edit";

interface ImageResult {
  images: Array<{ src: string; revisedPrompt?: string }>;
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
}

const UNIFIED_ADAPTERS: Adapter[] = [
  "video-unified-jimeng",
  "video-unified-vidu",
  "video-unified-veo",
  "video-unified-generic",
];

const store = useWorkbenchStore();
const auth = useAuthStore();
const view = ref<ViewName>(getViewFromHash());
const sidebarFilter = ref<SidebarFilter>("all");

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
  size: "720P",
  resolution: "720p",
  audio: false,
  upsample: false,
  seed: "0",
  extraJson: "",
  autoPoll: true,
  uploading: false,
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

const settingsState = reactive({
  selectedIds: [] as string[],
  dialogOpen: false,
  dialogMode: "create" as DialogMode,
  draft: createEmptyDraft(),
  modelListState: {} as Record<string, ActionState<AvailableModelsResult>>,
  testState: {} as Record<string, ActionState<TestRequestResult>>,
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

const activeCapability = computed<Capability | null>(() => {
  if (view.value === "images") return "image";
  if (view.value === "videos") return "video";
  if (view.value === "text") return "text";
  return null;
});

const filteredModels = computed(() =>
  store.models.value.filter((model) =>
    sidebarFilter.value === "all" ? true : model.capability === sidebarFilter.value,
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

const selectedSettingsModels = computed(() =>
  store.models.value.filter((model) => settingsState.selectedIds.includes(model.id)),
);

const configuredCount = computed(() =>
  store.models.value.filter((model) => {
    const setting = getSetting(model.id);
    return isModelConfigured(model, setting);
  }).length,
);

const allSettingsSelected = computed(
  () => store.models.value.length > 0 && settingsState.selectedIds.length === store.models.value.length,
);

const partialSettingsSelected = computed(
  () =>
    settingsState.selectedIds.length > 0 &&
    settingsState.selectedIds.length < store.models.value.length,
);

const visibleConversations = computed(() => {
  if (!activeCapability.value) return conversationState.conversations;
  return conversationState.conversations.filter((item) => item.capability === activeCapability.value);
});

const currentMessages = computed(() => conversationState.current?.messages || []);

const currentModelLabel = computed(() => {
  const model = activeModel.value;
  const setting = activeSetting.value;
  if (!model || !setting) return "未选择模型";
  return `${model.name} / ${resolveModelName(model, setting)}`;
});

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
  canTestDraftModel.value ? "测试当前主模型" : "请先填写 baseURL、API Key 和模型标识",
);
const draftSaveDisabledTitle = computed(() =>
  canSaveDraft() ? "保存模型配置" : `请先填写：${draftMissingFieldsText.value || "必填信息"}`,
);

onMounted(async () => {
  await initializeSession();
  syncInitialModels();
  window.addEventListener("hashchange", () => {
    view.value = getViewFromHash();
  });
});

watch(
  () => store.models.value.map((model) => model.id).join(","),
  syncInitialModels,
  { immediate: true },
);

function getViewFromHash(): ViewName {
  const hash = window.location.hash.replace(/^#\/?/, "");
  if (hash === "images" || hash === "videos" || hash === "settings" || hash === "profile" || hash === "text") {
    return hash;
  }
  return "images";
}

function navigate(nextView: ViewName) {
  window.location.hash = `/${nextView}`;
  view.value = nextView;
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
  conversationState.current = null;
  conversationState.streamingMessageId = "";
  conversationState.streamingContent = "";
  textState.result = null;
  imageState.result = null;
  videoState.createResult = null;
  videoState.taskResult = null;
  if (nextView === "settings" || nextView === "profile") {
    navigate("images");
  }
}

async function toggleHistoryDrawer() {
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
  if (auth.state.user) {
    await refreshServerModels();
    await refreshConversations();
  }
}

async function refreshServerModels() {
  const models = await fetchServerModels();
  store.applyServerModels(models);
}

async function handleDevLogin() {
  await auth.loginForDevelopment();
  if (auth.state.user) {
    await refreshServerModels();
    await refreshConversations();
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
  if (shouldResetConversationForModelSwitch(conversationState.current, model.capability)) {
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

function getPrimarySubModel(model: ModelDefinition): SubModelDefinition | null {
  if (!model.serverManaged) return null;
  return (
    model.subModels?.find((item) => item.id === model.primarySubModelId) ||
    model.subModels?.find((item) => item.isPrimary) ||
    model.subModels?.[0] ||
    null
  );
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

function conversationIdFor(capability: Capability): string {
  return conversationState.current?.capability === capability ? conversationState.current.id : "";
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

async function handleTextSubmit() {
  const model = activeModel.value;
  const setting = activeSetting.value;
  if (!model || !setting) return;

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
  const controller = createRequestController();
  try {
    const extra = parseJsonInput(textState.extraJson);
    const response = await postProxyWithSignal<TextResult>("/api/proxy/text", buildModelProxyPayload(model, setting, {
      conversationId: conversationIdFor("text"),
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
      const localConversation = appendLocalConversationMessages(conversationState.current, {
        capability: "text",
        titleSeed: finalPrompt,
        modelGroupId: model.id,
        messages: [
          { role: "user", content: finalPrompt },
          { role: "assistant", content: response.content || "已返回响应", status: "success" },
        ],
      });
      setCurrentConversation(localConversation);
      simulateStreamingPreview(localConversation.messages[localConversation.messages.length - 1]);
    }
    store.addHistory({
      id: createLocalId("history"),
      capability: "text",
      modelId: model.id,
      modelName: model.name,
      title: "文案创作",
      status: "success",
      createdAt: Date.now(),
      summary: shortText(response.content || "已返回响应"),
    });
  } catch (error) {
    textState.error = handleRequestError(error, "文案生成失败。");
  } finally {
    clearRequestController(controller);
    textState.loading = false;
  }
}

async function handleImageUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const setting = activeSetting.value;
  if (!setting || !input.files?.length) return;
  imageState.uploading = true;
  imageState.error = "";
  try {
    const uploaded = await Promise.all(
      Array.from(input.files).map((file) => uploadAsset(file, setting)),
    );
    imageState.references.push(...uploaded);
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
  if (!model || !setting) return;

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
  const controller = createRequestController();
  try {
    const extra = parseJsonInput(imageState.extraJson);
    imageState.result = await postProxyWithSignal<ImageResult>("/api/proxy/image", buildModelProxyPayload(model, setting, {
      conversationId: conversationIdFor("image"),
      requestBody: {
        prompt: finalPrompt,
        n: Number(imageState.count) || 1,
        size: imageState.size,
        ratio: imageState.ratio,
        resolution: imageState.resolution,
        quality: imageState.quality,
        response_format: "url",
        image: imageState.references.map((item) => item.publicUrl),
        ...extra,
      },
    }), controller.signal);
    if (imageState.result.conversation) {
      setCurrentConversation(imageState.result.conversation);
    } else {
      setCurrentConversation(appendLocalConversationMessages(conversationState.current, {
        capability: "image",
        titleSeed: finalPrompt,
        modelGroupId: model.id,
        messages: [
          { role: "user", content: finalPrompt },
          {
            role: "assistant",
            content: `已生成 ${imageState.result.images.length} 张图片。`,
            status: "success",
            assets: imageState.result.images.map((image) => ({ assetType: "image", url: image.src })),
          },
        ],
      }));
    }
  } catch (error) {
    imageState.error = handleRequestError(error, "图片生成失败。");
  } finally {
    clearRequestController(controller);
    imageState.loading = false;
  }
}

function supportsUnifiedAdapter(adapter?: Adapter): boolean {
  return adapter ? UNIFIED_ADAPTERS.includes(adapter) : false;
}

function getUnifiedImageLimit(mode: VideoMode): number {
  if (mode === "text") return 0;
  if (mode === "reference") return 1;
  return 2;
}

async function uploadVideoFiles(event: Event, target: "unified" | "first" | "last" | "seedanceRef") {
  const input = event.target as HTMLInputElement;
  const setting = activeSetting.value;
  if (!setting || !input.files?.length) return;

  videoState.uploading = true;
  videoState.error = "";
  try {
    const uploaded = await Promise.all(
      Array.from(input.files).map((file) => uploadAsset(file, setting)),
    );
    if (target === "unified") {
      videoState.unifiedImages = uploaded.slice(0, getUnifiedImageLimit(videoState.mode));
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
  if (model.adapter === "video-unified-jimeng") {
    return {
      model: modelName,
      prompt: finalPrompt,
      images: videoState.mode === "text" ? [] : videoState.unifiedImages.map((item) => item.publicUrl),
      aspect_ratio: videoState.aspectRatio,
      size: videoState.size,
      ...extra,
    };
  }
  if (model.adapter === "video-unified-vidu") {
    return {
      model: modelName,
      prompt: finalPrompt,
      images: videoState.mode === "text" ? [] : videoState.unifiedImages.map((item) => item.publicUrl),
      aspect_ratio: videoState.aspectRatio,
      duration: Number(videoState.duration) || 5,
      resolution: videoState.resolution,
      audio: videoState.audio,
      seed: Number(videoState.seed) || 0,
      ...extra,
    };
  }
  if (model.adapter === "video-unified-veo") {
    return {
      model: modelName,
      prompt: finalPrompt,
      images: videoState.mode === "text" ? [] : videoState.unifiedImages.map((item) => item.publicUrl),
      orientation: videoState.aspectRatio === "9:16" ? "portrait" : "landscape",
      size: videoState.size,
      duration: Number(videoState.duration) || 8,
      aspect_ratio: videoState.aspectRatio,
      enable_upsample: videoState.upsample,
      ...extra,
    };
  }
  if (model.adapter === "video-seedance") {
    const content: Array<Record<string, unknown>> = [{ type: "text", text: finalPrompt }];
    if (videoState.mode === "reference") {
      videoState.seedanceReferences.forEach((asset) => {
        content.push({ type: "image_url", image_url: { url: asset.publicUrl }, role: "reference_image" });
      });
    }
    if (videoState.mode === "start-end") {
      if (videoState.seedanceFirst) {
        content.push({ type: "image_url", image_url: { url: videoState.seedanceFirst.publicUrl }, role: "first_frame" });
      }
      if (videoState.seedanceLast) {
        content.push({ type: "image_url", image_url: { url: videoState.seedanceLast.publicUrl }, role: "last_frame" });
      }
    }
    return {
      model: modelName,
      content,
      metadata: {
        duration: Number(videoState.duration) || 5,
        resolution: videoState.resolution,
        ratio: videoState.aspectRatio,
        generate_audio: videoState.audio,
        seed: Number(videoState.seed) || 0,
      },
      ...extra,
    };
  }
  return {
    model: modelName,
    prompt: finalPrompt,
    images: videoState.mode === "text" ? [] : videoState.unifiedImages.map((item) => item.publicUrl),
    aspect_ratio: videoState.aspectRatio,
    duration: Number(videoState.duration) || 5,
    size: videoState.size,
    resolution: videoState.resolution,
    audio: videoState.audio,
    seed: Number(videoState.seed) || 0,
    ...extra,
  };
}

async function handleVideoCreate() {
  const model = activeModel.value;
  const setting = activeSetting.value;
  if (!model || !setting) return;

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
  if (supportsUnifiedAdapter(model.adapter) && videoState.unifiedImages.length < getUnifiedImageLimit(videoState.mode)) {
    videoState.error = "当前模式需要的参考图数量还不够。";
    return;
  }
  if (model.adapter === "video-seedance" && videoState.mode === "reference" && !videoState.seedanceReferences.length) {
    videoState.error = "Seedance 参考模式至少需要上传一张参考图。";
    return;
  }
  if (model.adapter === "video-seedance" && videoState.mode === "start-end" && (!videoState.seedanceFirst || !videoState.seedanceLast)) {
    videoState.error = "Seedance 首尾帧模式需要同时上传首帧和尾帧。";
    return;
  }

  videoState.loading = true;
  videoState.error = "";
  videoState.taskResult = null;
  const controller = createRequestController();
  try {
    const extra = parseJsonInput(videoState.extraJson);
    const requestBody = buildVideoRequestBody(model, resolveModelName(model, setting), finalPrompt, extra);
    videoState.createResult = await postProxyWithSignal<VideoCreateResult>("/api/proxy/video/create", buildModelProxyPayload(model, setting, {
      adapter: model.adapter,
      conversationId: conversationIdFor("video"),
      requestBody,
    }), controller.signal);
    if (videoState.createResult.conversation) {
      setCurrentConversation(videoState.createResult.conversation);
    } else {
      setCurrentConversation(appendLocalConversationMessages(conversationState.current, {
        capability: "video",
        titleSeed: finalPrompt,
        modelGroupId: model.id,
        messages: [
          { role: "user", content: finalPrompt },
          {
            role: "assistant",
            content: videoState.createResult.taskId,
            status: "processing",
          },
        ],
      }));
    }
    if (videoState.autoPoll) {
      await handleVideoQuery(videoState.createResult.taskId);
    }
  } catch (error) {
    videoState.error = handleRequestError(error, "视频任务提交失败。");
  } finally {
    clearRequestController(controller);
    videoState.loading = false;
  }
}

async function handleVideoQuery(taskIdArg?: string) {
  const model = activeModel.value;
  const setting = activeSetting.value;
  const taskId = taskIdArg || taskIdFromConversation();
  if (!model || !setting || !taskId) {
    videoState.error = "暂无可查询的任务 ID。";
    return;
  }

  videoState.querying = true;
  videoState.error = "";
  const controller = createRequestController();
  try {
    videoState.taskResult = await postProxyWithSignal<VideoQueryResult>("/api/proxy/video/query", buildModelProxyPayload(model, setting, {
      adapter: model.adapter,
      conversationId: conversationIdFor("video"),
      taskId,
    }), controller.signal);
    if (videoState.taskResult.conversation) {
      setCurrentConversation(videoState.taskResult.conversation);
    } else if (videoState.taskResult.videoUrl) {
      setCurrentConversation(appendLocalConversationMessages(conversationState.current, {
        capability: "video",
        titleSeed: taskId,
        modelGroupId: model.id,
        messages: [
          {
            role: "assistant",
            content: String(videoState.taskResult.status || "completed"),
            status: videoState.taskResult.status === "completed" ? "success" : "processing",
            assets: [{
              assetType: "video",
              url: videoState.taskResult.videoUrl,
              thumbnailUrl: videoState.taskResult.thumbnailUrl || "",
              metadata: { taskId, status: videoState.taskResult.status, progress: videoState.taskResult.progress },
            }],
          },
        ],
      }));
    }
  } catch (error) {
    videoState.error = handleRequestError(error, "任务查询失败。");
  } finally {
    clearRequestController(controller);
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

async function setPrimaryModel(modelId: string, model: ModelDefinition, setting: ModelSetting) {
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
}

function openCreateDialog() {
  settingsState.dialogMode = "create";
  settingsState.draft = createEmptyDraft();
  settingsState.dialogOpen = true;
}

function openEditDialog(model: ModelDefinition) {
  settingsState.dialogMode = "edit";
  settingsState.draft = createDraftFromModel(model);
  settingsState.dialogOpen = true;
}

async function saveDialog() {
  const draft = settingsState.draft;
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
      name: draft.name.trim(),
      vendor: draft.vendor.trim() || "自定义",
      capability: draft.capability,
      adapter: draft.adapter,
      description: draft.description.trim() || "用户自定义模型",
      baseUrl: draft.baseUrl.trim(),
      apiKey: draft.apiKey.trim(),
      primaryModelName: modelName,
      availableModelNames: draft.availableModels.length ? draft.availableModels : [modelName],
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
      settingsState.dialogOpen = false;
    } catch (error) {
      settingsState.testState[draft.id] = {
        loading: false,
        error: error instanceof Error ? error.message : "保存模型失败。",
        result: null,
      };
    }
    return;
  }
  if (settingsState.dialogMode === "create") {
    store.addCustomModel({
      id: draft.id,
      name: draft.name.trim(),
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
        name: draft.name.trim(),
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
  settingsState.dialogOpen = false;
}

async function fetchModelList(model: ModelDefinition, setting: ModelSetting) {
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
    } catch (error) {
      settingsState.modelListState[model.id] = {
        loading: false,
        error: error instanceof Error ? error.message : "获取可用模型失败。",
        result: null,
      };
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
      return;
    }
    store.updateModelSetting(model.id, {
      ...setting,
      availableModels: result.models,
      modelNameOverride: primaryModel,
    });
  } catch (error) {
    settingsState.modelListState[model.id] = {
      loading: false,
      error: error instanceof Error ? error.message : "获取可用模型失败。",
      result: null,
    };
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
  } catch (error) {
    settingsState.testState[model.id] = {
      loading: false,
      error: error instanceof Error ? error.message : "测试请求失败。",
      result: null,
    };
  }
}

function toggleSelected(modelId: string, checked: boolean) {
  settingsState.selectedIds = checked
    ? Array.from(new Set([...settingsState.selectedIds, modelId]))
    : settingsState.selectedIds.filter((id) => id !== modelId);
}

function toggleAllSettings(checked: boolean) {
  settingsState.selectedIds = checked ? store.models.value.map((model) => model.id) : [];
}

async function batchTest() {
  await Promise.allSettled(
    selectedSettingsModels.value
      .filter((model) => {
        const setting = getSetting(model.id);
        return isModelConfigured(model, setting);
      })
      .map((model) => testModel(model, getSetting(model.id))),
  );
}

async function removeModelFromWorkbench(modelId: string) {
  const model = store.models.value.find((item) => item.id === modelId);
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
  await Promise.allSettled(selectedSettingsModels.value.map((model) => removeModelFromWorkbench(model.id)));
  settingsState.selectedIds = [];
}
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="sidebar-logo">
        <div class="logo-mark">G</div>
        <div>
          <strong>GenStudio</strong>
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
            :class="['secondary-item', sidebarFilter === item.value ? 'secondary-item-active' : '']"
            @click="sidebarFilter = item.value as SidebarFilter"
          >
            {{ item.label }}
          </button>
        </div>
      </div>

      <div class="model-list">
        <div class="model-list-special">
          <div class="model-avatar">M</div>
          <div class="model-info">
            <strong>多模型协作</strong>
            <span>多个模型同时调试，对比响应结果</span>
          </div>
          <span class="model-tag tag-duo">多模型</span>
        </div>
        <div class="model-divider"><span>模型列表</span></div>
        <button
          v-for="model in filteredModels"
          :key="model.id"
          :data-model-id="model.id"
          :class="['sidebar-model-item', model.id === activeModelIdForSidebar() ? 'sidebar-model-active' : '']"
          @click="selectModel(model)"
        >
          <div :class="['model-avatar', `model-avatar-${model.capability}`]">
            {{ model.capability === "text" ? "T" : model.capability === "image" ? "I" : "V" }}
          </div>
          <div class="model-info">
            <strong>{{ model.name }}</strong>
            <span>{{ model.description }}</span>
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
          <span>{{ auth.state.user ? auth.state.user.email || "已通过官网授权" : auth.state.loading ? "登录状态读取中" : "可使用官网授权登录" }}</span>
        </div>
        <button v-if="auth.state.user" class="account-recharge" @click="navigate('profile')">我的</button>
        <button v-else class="account-recharge" :disabled="auth.state.loading" @click="handleDevLogin">开发登录</button>
      </div>
    </aside>

    <main class="main">
      <div class="workspace-topbar">
        <div class="workspace-topbar-actions">
          <button @click="startNewConversation()">+ 新建对话</button>
          <button class="button-secondary" @click="toggleHistoryDrawer">历史记录</button>
          <button v-if="conversationState.activeRequest" class="button-danger" @click="stopActiveRequest">暂停</button>
        </div>
        <div class="workspace-topbar-actions">
          <span class="topbar-model-label">{{ currentModelLabel }}</span>
          <button class="topbar-icon-button" @click="navigate('settings')">设置</button>
          <button class="topbar-icon-button" @click="navigate('profile')">个人</button>
        </div>
      </div>

      <section v-if="view !== 'settings' && view !== 'profile'" class="studio-panel">
        <div class="studio-canvas">
          <aside v-if="conversationState.listOpen" class="history-drawer">
            <div class="history-drawer-head">
              <strong>历史记录</strong>
              <button class="button-secondary icon-button" @click="conversationState.listOpen = false">关闭</button>
            </div>
            <div v-if="conversationState.error" class="inline-message inline-danger">{{ conversationState.error }}</div>
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
                <span>视频任务运行中，可以稍后重新进入历史记录继续查询。</span>
                <button class="button-secondary" @click="() => handleVideoQuery(message.content)">查询进度</button>
              </div>
              <div v-if="message.assets.length" class="message-assets">
                <article v-for="asset in message.assets" :key="asset.id" class="message-asset-card">
                  <img v-if="asset.assetType === 'image'" :src="asset.url" alt="生成图片" />
                  <video v-else-if="asset.assetType === 'video'" :src="asset.url" :poster="asset.thumbnailUrl || undefined" controls playsinline preload="metadata" />
                  <div class="asset-actions">
                    <a class="button-link" :href="asset.url" target="_blank" rel="noreferrer">查看</a>
                    <button v-if="asset.assetType === 'image'" class="button-secondary" @click="useGeneratedAsset(asset)">引用编辑</button>
                    <a class="button-secondary" :href="asset.url" download target="_blank" rel="noreferrer">保存</a>
                  </div>
                </article>
              </div>
            </article>
          </div>

          <div v-else class="empty-canvas">
            <div class="empty-canvas-card">
              <div class="hero-model-mark">
                {{ activeCapability === "text" ? "T" : activeCapability === "image" ? "I" : "V" }}
              </div>
              <div class="empty-canvas-top">
                <span class="badge badge-accent">{{ activeCapability ? CAPABILITY_LABELS[activeCapability] : "创作" }}</span>
                <span>{{ activeModel?.name || "未选择模型" }}</span>
              </div>
              <h3>{{ activeModel?.name || "创作模型" }}</h3>
              <p class="muted">{{ activeModel?.description || "选择模型并输入需求开始调试。" }}</p>
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
            <span>{{ activeModel && activeSetting && isModelConfigured(activeModel, activeSetting) ? "模型已就绪" : "模型待配置" }}</span>
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
            <textarea v-model="textState.prompt" class="composer-input" placeholder="输入你想生成的文案、脚本、提示词或结构化内容..." />
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
              <textarea v-model="imageState.prompt" class="composer-input" placeholder="描述你想要生成的图片内容，支持上传参考图片进行图生图，最多14张" />
            </div>
            <div class="composer-footer-bar">
              <div class="composer-quick-fields composer-quick-fields-wide">
                <label class="composer-keyword-compact"><span>关键词</span><input v-model="imageState.keywords" placeholder="玻璃感、青柠色" /></label>
                <label><span>数量</span><input v-model="imageState.count" /></label>
                <label><span>尺寸</span><input v-model="imageState.size" /></label>
                <label><span>比例</span><select v-model="imageState.ratio"><option>1:1</option><option>16:9</option><option>9:16</option><option>4:3</option><option>3:4</option></select></label>
                <label><span>分辨率</span><select v-model="imageState.resolution"><option>1k</option><option>2k</option><option>4k</option></select></label>
                <label><span>质量</span><select v-model="imageState.quality"><option value="auto">价格优先</option><option value="standard">标准</option><option value="hd">高清优先</option></select></label>
              </div>
              <button class="composer-submit-button" :disabled="imageState.loading" @click="handleImageSubmit">生成</button>
            </div>
            <details class="composer-details">
              <summary>参考图与高级 JSON</summary>
              <div class="asset-grid" v-if="imageState.references.length">
                <article v-for="asset in imageState.references" :key="asset.id" class="asset-card">
                  <img :src="asset.localPreviewUrl" :alt="asset.fileName" />
                  <div class="asset-card-body"><strong>{{ asset.fileName }}</strong><p class="muted">{{ asset.publicUrl }}</p></div>
                </article>
              </div>
              <label class="field field-full"><span>高级参数 JSON</span><textarea v-model="imageState.extraJson" /></label>
            </details>
            <div v-if="imageState.error" class="inline-message inline-danger">{{ imageState.error }}</div>
          </div>

          <div v-if="view === 'videos'" class="composer-surface">
            <div class="composer-attach-row composer-video-attach-row">
              <label v-if="supportsUnifiedAdapter(activeModel?.adapter)" class="button-secondary composer-attach-button">
                {{ videoState.mode === "text" ? "无需素材" : videoState.uploading ? "上传中" : "+ 参考图" }}
                <input hidden type="file" accept="image/png,image/jpeg,image/jpg,image/webp" :multiple="videoState.mode === 'start-end'" @change="(event) => uploadVideoFiles(event, 'unified')" />
              </label>
              <label v-if="activeModel?.adapter === 'video-seedance' && videoState.mode === 'reference'" class="button-secondary composer-attach-button">
                + 参考图
                <input hidden type="file" multiple accept="image/png,image/jpeg,image/jpg,image/webp" @change="(event) => uploadVideoFiles(event, 'seedanceRef')" />
              </label>
              <div v-if="activeModel?.adapter === 'video-seedance' && videoState.mode === 'start-end'" class="composer-frame-actions">
                <label class="button-secondary composer-attach-button">首帧<input hidden type="file" accept="image/png,image/jpeg,image/jpg,image/webp" @change="(event) => uploadVideoFiles(event, 'first')" /></label>
                <label class="button-secondary composer-attach-button">尾帧<input hidden type="file" accept="image/png,image/jpeg,image/jpg,image/webp" @change="(event) => uploadVideoFiles(event, 'last')" /></label>
              </div>
              <textarea v-model="videoState.prompt" class="composer-input" placeholder="描述主体动作、镜头运动、时长、风格和节奏..." />
            </div>
            <div class="composer-footer-bar">
              <div class="composer-quick-fields composer-quick-fields-wide">
                <label><span>模式</span><select v-model="videoState.mode"><option value="text">纯文生</option><option value="reference">参考图</option><option value="start-end">首尾帧</option></select></label>
                <label class="composer-keyword-compact"><span>关键词</span><input v-model="videoState.keywords" /></label>
                <label><span>比例</span><select v-model="videoState.aspectRatio"><option>16:9</option><option>9:16</option><option>1:1</option><option>4:3</option><option>21:9</option></select></label>
                <label><span>时长</span><input v-model="videoState.duration" /></label>
                <label><span>分辨率</span><select v-model="videoState.resolution"><option>540p</option><option>720p</option><option>1080p</option></select></label>
                <label><span>种子</span><input v-model="videoState.seed" /></label>
                <label class="composer-check-field"><input v-model="videoState.audio" type="checkbox" /><span>音频</span></label>
              </div>
              <div class="composer-video-actions">
                <button class="composer-submit-button" :disabled="videoState.loading" @click="handleVideoCreate">创建</button>
                <button class="button-secondary" :disabled="videoState.querying || !videoState.createResult?.taskId" @click="() => handleVideoQuery()">查询</button>
              </div>
            </div>
            <details class="composer-details">
              <summary>素材与高级 JSON</summary>
              <label class="field field-full"><span>高级参数 JSON</span><textarea v-model="videoState.extraJson" /></label>
              <label class="checkbox-inline"><input v-model="videoState.autoPoll" type="checkbox" />自动轮询</label>
            </details>
            <div v-if="videoState.error" class="inline-message inline-danger">{{ videoState.error }}</div>
          </div>
        </div>
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
            <span>{{ auth.state.user?.email || "请通过官网授权或本地模拟登录" }}</span>
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

        <section class="settings-list-panel profile-actions">
          <div>
            <h3>官网授权回跳</h3>
            <p class="muted">正式环境使用官网生成的短期 code 访问 /auth/callback?code=xxx；本地测试可用 dev:alice、dev:bob、dev:carol 模拟三个用户。</p>
          </div>
          <div class="settings-row-actions">
            <a class="button-link" href="/auth/callback?code=dev:alice">模拟 Alice</a>
            <a class="button-link" href="/auth/callback?code=dev:bob">模拟 Bob</a>
            <a class="button-link" href="/auth/callback?code=dev:carol">模拟 Carol</a>
            <button class="button-secondary" @click="refreshConversations">刷新历史</button>
          </div>
        </section>
      </section>

      <section v-else class="settings-page">
        <section class="settings-hero">
          <div>
            <p class="eyebrow">Model Settings</p>
            <h2>模型配置</h2>
            <p class="muted">{{ auth.state.user ? "配置会保存到 GenStudio 数据库，密钥只由后端调用。" : "未登录时配置会缓存在当前浏览器，登录后可保存到数据库。" }}</p>
          </div>
          <div class="settings-hero-stats">
            <span class="badge">{{ store.models.value.length }} 个模型</span>
            <span class="badge badge-success">{{ configuredCount }} 个已配置</span>
          </div>
        </section>

        <section class="settings-list-panel">
          <div class="settings-list-toolbar">
            <div class="settings-bulk-actions">
              <span class="badge">已选 {{ settingsState.selectedIds.length }} / {{ store.models.value.length }}</span>
              <button class="button-secondary" :disabled="!settingsState.selectedIds.length" @click="batchTest">批量测试</button>
              <button class="button-danger" :disabled="!settingsState.selectedIds.length" @click="batchDelete">批量删除</button>
            </div>
            <button @click="openCreateDialog">+ 添加模型</button>
          </div>

          <div class="settings-table">
            <div class="settings-table-head">
              <label class="settings-check-cell">
                <input type="checkbox" :checked="allSettingsSelected" :indeterminate.prop="partialSettingsSelected" @change="(event) => toggleAllSettings((event.target as HTMLInputElement).checked)" />
              </label>
              <span>名称</span><span>请求地址</span><span>链接状态</span><span>操作</span>
            </div>
            <article v-for="model in store.models.value" :key="model.id" class="settings-table-row" :data-model-id="model.id">
              <label class="settings-check-cell">
                <input type="checkbox" :checked="settingsState.selectedIds.includes(model.id)" @change="(event) => toggleSelected(model.id, (event.target as HTMLInputElement).checked)" />
              </label>
              <div class="settings-model-name">
                <strong>{{ model.name }}</strong>
                <span>{{ CAPABILITY_LABELS[model.capability] }} · {{ model.vendor }}</span>
                <span>主模型：{{ resolveModelName(model, getSetting(model.id)) }}</span>
              </div>
              <div class="settings-url">{{ getSetting(model.id).baseUrl || "-" }}</div>
              <div>
                <span v-if="settingsState.testState[model.id]?.loading" class="badge badge-warn">测试中</span>
                <span v-else-if="settingsState.testState[model.id]?.result" class="badge badge-success">已连接 {{ settingsState.testState[model.id].result?.durationMs }}ms</span>
                <span v-else-if="settingsState.testState[model.id]?.error" class="badge badge-danger">连接失败</span>
                <span v-else-if="!isModelConfigured(model, getSetting(model.id))" class="badge badge-warn">待配置</span>
                <span v-else class="badge">待测试</span>
              </div>
              <div class="settings-row-actions">
                <button class="button-secondary" @click="fetchModelList(model, getSetting(model.id))">模型列表</button>
                <button class="button-secondary" @click="testModel(model, getSetting(model.id))">测速</button>
                <button class="button-secondary icon-button" @click="openEditDialog(model)">编辑</button>
                <button class="button-danger icon-button" @click="removeModelFromWorkbench(model.id)">删除</button>
              </div>
              <div v-if="settingsState.modelListState[model.id]?.error" class="settings-row-detail inline-message inline-danger">{{ settingsState.modelListState[model.id].error }}</div>
              <div v-if="settingsState.testState[model.id]?.error" class="settings-row-detail inline-message inline-danger">{{ settingsState.testState[model.id].error }}</div>
              <div v-if="settingsState.modelListState[model.id]?.result || getAvailableModels(model).length" class="settings-row-detail settings-model-list-result">
                <div class="status-row">
                  <span class="badge badge-success">已获取 {{ getAvailableModels(model).length }} 个模型</span>
                  <span v-if="settingsState.modelListState[model.id]?.result" class="history-time">{{ settingsState.modelListState[model.id].result?.durationMs }}ms</span>
                </div>
                <label class="model-select-field">
                  <span>主模型</span>
                  <select
                    :value="resolveModelName(model, getSetting(model.id))"
                    @change="(event) => setPrimaryModel((event.target as HTMLSelectElement).value, model, getSetting(model.id))"
                  >
                    <option
                      v-for="modelId in getAvailableModels(model)"
                      :key="modelId"
                      :value="modelId"
                    >
                      {{ modelId }}
                    </option>
                  </select>
                </label>
              </div>
            </article>
          </div>
        </section>

        <div v-if="settingsState.dialogOpen" class="settings-dialog-backdrop">
          <section class="settings-dialog">
            <div class="settings-dialog-head">
              <div><p class="eyebrow">Model Config</p><h3>{{ settingsState.dialogMode === "create" ? "添加模型" : "模型配置" }}</h3></div>
              <button class="button-secondary icon-button" @click="settingsState.dialogOpen = false">关闭</button>
            </div>
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
                  <strong>1. 连接密钥</strong>
                  <span>先确认这个配置属于哪类创作能力，以及后端应该用哪个请求地址和密钥。</span>
                </div>
                <div class="form-grid settings-dialog-grid">
                  <label class="field"><span>名称</span><input v-model="settingsState.draft.name" /></label>
                  <label class="field"><span>备注</span><input v-model="settingsState.draft.description" /></label>
                  <label class="field"><span>厂商</span><input v-model="settingsState.draft.vendor" /></label>
                  <label class="field"><span>能力类型</span><select v-model="settingsState.draft.capability" @change="settingsState.draft.adapter = getCapabilityDefaultAdapter(settingsState.draft.capability)"><option value="text">文案创作</option><option value="image">图片创作</option><option value="video">视频创作</option></select></label>
                  <label class="field field-full"><span>适配器</span><select v-model="settingsState.draft.adapter"><option v-for="adapter in getAdapterOptions(settingsState.draft.capability)" :key="adapter" :value="adapter">{{ ADAPTER_LABELS[adapter] }}</option></select></label>
                  <label class="field field-full"><span>baseURL</span><input v-model="settingsState.draft.baseUrl" placeholder="例如：https://ai.ai666.net" /></label>
                  <label class="field field-full"><span>API Key</span><input v-model="settingsState.draft.apiKey" type="password" /></label>
                </div>
              </section>

              <section class="settings-dialog-section">
                <div class="section-copy">
                  <strong>2. 获取模型并选择主模型</strong>
                  <span>一个密钥可能返回多个模型，保存后创作会优先使用这里选中的主模型。</span>
                </div>
                <div class="form-grid settings-dialog-grid">
                  <label class="field field-full"><span>模型标识</span><input v-model="settingsState.draft.model" placeholder="例如：gpt-4o" /></label>
                  <label v-if="settingsState.draft.availableModels.length" class="field field-full">
                    <span>主模型</span>
                    <select v-model="settingsState.draft.modelNameOverride" @change="settingsState.draft.model = settingsState.draft.modelNameOverride">
                      <option
                        v-for="modelId in settingsState.draft.availableModels"
                        :key="modelId"
                        :value="modelId"
                      >
                        {{ modelId }}
                      </option>
                    </select>
                  </label>
                  <label v-else class="field field-full"><span>主模型覆盖</span><input v-model="settingsState.draft.modelNameOverride" placeholder="获取模型列表后可从下拉选择" /></label>
                </div>
              </section>

              <section class="settings-dialog-section settings-dialog-review">
                <div class="section-copy">
                  <strong>3. 保存确认</strong>
                  <span>当前主模型：{{ getDraftModelName(settingsState.draft) || "尚未选择" }}</span>
                </div>
                <div class="review-grid">
                  <span>能力</span><strong>{{ CAPABILITY_LABELS[settingsState.draft.capability] }}</strong>
                  <span>适配器</span><strong>{{ ADAPTER_LABELS[settingsState.draft.adapter] }}</strong>
                  <span>模型数量</span><strong>{{ settingsState.draft.availableModels.length || 1 }}</strong>
                </div>
              </section>
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
              <button class="button-secondary" :disabled="!canFetchDraftModels" :title="draftFetchDisabledTitle" @click="fetchModelList(getDraftModel(), getDraftSetting())">获取模型列表</button>
              <button class="button-secondary" :disabled="!canTestDraftModel" :title="draftTestDisabledTitle" @click="testModel(getDraftModel(), getDraftSetting())">测速</button>
              <button class="button-secondary" @click="settingsState.dialogOpen = false">取消</button>
              <button :disabled="!canSaveDraft()" :title="draftSaveDisabledTitle" @click="saveDialog">保存</button>
            </div>
            <div v-if="settingsState.modelListState[settingsState.draft.id]?.error" class="inline-message inline-danger">{{ settingsState.modelListState[settingsState.draft.id].error }}</div>
            <div v-if="settingsState.testState[settingsState.draft.id]?.error" class="inline-message inline-danger">{{ settingsState.testState[settingsState.draft.id].error }}</div>
          </section>
        </div>
      </section>
    </main>
  </div>
</template>
