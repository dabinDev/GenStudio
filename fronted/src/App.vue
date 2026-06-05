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
import { postProxy, uploadAsset } from "./api";
import { useWorkbenchStore } from "./stores/workbench";
import type {
  Adapter,
  Capability,
  ModelDefinition,
  ModelSetting,
  PromptTemplate,
  UploadedAsset,
} from "./types";
import { combinePrompt, createLocalId, resolveModelName, shortText } from "./utils";

type ViewName = "text" | "images" | "videos" | "settings";
type SidebarFilter = Capability | "all";
type VideoMode = "text" | "reference" | "start-end";
type DialogMode = "create" | "edit";

interface ImageResult {
  images: Array<{ src: string; revisedPrompt?: string }>;
  raw: Record<string, unknown>;
}

interface TextResult {
  content: string;
  usage?: Record<string, unknown>;
  raw: Record<string, unknown>;
}

interface VideoCreateResult {
  taskId: string;
  status: string;
  raw: Record<string, unknown>;
}

interface VideoQueryResult {
  taskId: string;
  status: string;
  progress: number | string | null;
  videoUrl: string | null;
  thumbnailUrl: string | null;
  raw: Record<string, unknown>;
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
}

const UNIFIED_ADAPTERS: Adapter[] = [
  "video-unified-jimeng",
  "video-unified-vidu",
  "video-unified-veo",
  "video-unified-generic",
];

const store = useWorkbenchStore();
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
    return setting.baseUrl.trim() && setting.apiKey.trim();
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

onMounted(() => {
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
  if (hash === "images" || hash === "videos" || hash === "settings" || hash === "text") {
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

function getSetting(modelId: string): ModelSetting {
  return (
    store.state.modelSettings[modelId] || {
      baseUrl: "",
      apiKey: "",
      modelNameOverride: "",
    }
  );
}

function getModelHref(model: ModelDefinition): ViewName {
  if (model.capability === "image") return "images";
  if (model.capability === "video") return "videos";
  return "text";
}

function selectModel(model: ModelDefinition) {
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

async function handleTextSubmit() {
  const model = activeModel.value;
  const setting = activeSetting.value;
  if (!model || !setting) return;

  const finalPrompt = combinePrompt(textState.keywords, textState.prompt);
  if (!finalPrompt.trim()) {
    textState.error = "请先输入文案需求。";
    return;
  }
  if (!setting.baseUrl.trim() || !setting.apiKey.trim()) {
    textState.error = "当前模型尚未配置 baseURL 或 API Key。";
    return;
  }

  textState.loading = true;
  textState.error = "";
  try {
    const extra = parseJsonInput(textState.extraJson);
    const response = await postProxy<TextResult>("/api/proxy/text", {
      config: { baseUrl: setting.baseUrl, apiKey: setting.apiKey },
      model: resolveModelName(model, setting),
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
    });
    textState.result = response;
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
    textState.error = error instanceof Error ? error.message : "文案生成失败。";
  } finally {
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
  if (!setting.baseUrl.trim() || !setting.apiKey.trim()) {
    imageState.error = "当前模型尚未配置 baseURL 或 API Key。";
    return;
  }

  imageState.loading = true;
  imageState.error = "";
  try {
    const extra = parseJsonInput(imageState.extraJson);
    imageState.result = await postProxy<ImageResult>("/api/proxy/image", {
      config: { baseUrl: setting.baseUrl, apiKey: setting.apiKey },
      model: resolveModelName(model, setting),
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
    });
  } catch (error) {
    imageState.error = error instanceof Error ? error.message : "图片生成失败。";
  } finally {
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
  if (!setting.baseUrl.trim() || !setting.apiKey.trim()) {
    videoState.error = "当前模型尚未配置 baseURL 或 API Key。";
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
  try {
    const extra = parseJsonInput(videoState.extraJson);
    const requestBody = buildVideoRequestBody(model, resolveModelName(model, setting), finalPrompt, extra);
    videoState.createResult = await postProxy<VideoCreateResult>("/api/proxy/video/create", {
      config: { baseUrl: setting.baseUrl, apiKey: setting.apiKey },
      adapter: model.adapter,
      requestBody,
    });
    if (videoState.autoPoll) {
      await handleVideoQuery(videoState.createResult.taskId);
    }
  } catch (error) {
    videoState.error = error instanceof Error ? error.message : "视频任务提交失败。";
  } finally {
    videoState.loading = false;
  }
}

async function handleVideoQuery(taskIdArg?: string) {
  const model = activeModel.value;
  const setting = activeSetting.value;
  const taskId = taskIdArg || videoState.createResult?.taskId;
  if (!model || !setting || !taskId) {
    videoState.error = "暂无可查询的任务 ID。";
    return;
  }

  videoState.querying = true;
  videoState.error = "";
  try {
    videoState.taskResult = await postProxy<VideoQueryResult>("/api/proxy/video/query", {
      config: { baseUrl: setting.baseUrl, apiKey: setting.apiKey },
      adapter: model.adapter,
      taskId,
    });
  } catch (error) {
    videoState.error = error instanceof Error ? error.message : "任务查询失败。";
  } finally {
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
  };
}

function getDraftSetting(): ModelSetting {
  return {
    baseUrl: settingsState.draft.baseUrl,
    apiKey: settingsState.draft.apiKey,
    modelNameOverride: settingsState.draft.modelNameOverride,
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
  return draft.model.trim() || draft.modelNameOverride.trim();
}

function canSaveDraft(): boolean {
  return Boolean(settingsState.draft.name.trim() && getDraftModelName(settingsState.draft));
}

function selectDraftModelId(modelId: string) {
  settingsState.draft.model = modelId;
  settingsState.draft.modelNameOverride = modelId;
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

function saveDialog() {
  const draft = settingsState.draft;
  const modelName = getDraftModelName(draft);
  if (!draft.name.trim() || !modelName) return;
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
  });
  settingsState.dialogOpen = false;
}

async function fetchModelList(model: ModelDefinition, setting: ModelSetting) {
  if (!setting.baseUrl.trim() || !setting.apiKey.trim()) {
    settingsState.modelListState[model.id] = { ...createIdleState<AvailableModelsResult>(), error: "请先填写 baseURL 和 API Key。" };
    return;
  }
  settingsState.modelListState[model.id] = { ...createIdleState<AvailableModelsResult>(), loading: true };
  try {
    settingsState.modelListState[model.id] = {
      loading: false,
      error: "",
      result: await postProxy<AvailableModelsResult>("/api/proxy/models", {
        config: { baseUrl: setting.baseUrl, apiKey: setting.apiKey },
      }),
    };
  } catch (error) {
    settingsState.modelListState[model.id] = {
      loading: false,
      error: error instanceof Error ? error.message : "获取可用模型失败。",
      result: null,
    };
  }
}

async function testModel(model: ModelDefinition, setting: ModelSetting) {
  if (!setting.baseUrl.trim() || !setting.apiKey.trim()) {
    settingsState.testState[model.id] = { ...createIdleState<TestRequestResult>(), error: "请先填写 baseURL 和 API Key。" };
    return;
  }
  settingsState.testState[model.id] = { ...createIdleState<TestRequestResult>(), loading: true };
  try {
    settingsState.testState[model.id] = {
      loading: false,
      error: "",
      result: await postProxy<TestRequestResult>("/api/proxy/test", {
        config: { baseUrl: setting.baseUrl, apiKey: setting.apiKey },
        capability: model.capability,
        adapter: model.adapter,
        model: resolveModelName(model, setting),
      }),
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
        return setting.baseUrl.trim() && setting.apiKey.trim();
      })
      .map((model) => testModel(model, getSetting(model.id))),
  );
}

function removeModelFromWorkbench(modelId: string) {
  store.removeModel(modelId);
  settingsState.selectedIds = settingsState.selectedIds.filter((selectedId) => selectedId !== modelId);
  delete settingsState.modelListState[modelId];
  delete settingsState.testState[modelId];
}

function batchDelete() {
  selectedSettingsModels.value.forEach((model) => removeModelFromWorkbench(model.id));
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
          <button class="primary-item" disabled>智能体</button>
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
        <div class="account-avatar">S</div>
        <div class="account-copy">
          <strong>本地调试台</strong>
          <span>在线</span>
        </div>
        <button class="account-recharge" @click="navigate('settings')">设置</button>
      </div>
    </aside>

    <main class="main">
      <div class="workspace-topbar">
        <div class="workspace-topbar-actions">
          <button @click="view === 'settings' ? navigate('images') : undefined">+ 新建对话</button>
          <button class="button-secondary">历史记录</button>
        </div>
        <div class="workspace-topbar-actions">
          <button class="topbar-icon-button" @click="navigate('settings')">设置</button>
        </div>
      </div>

      <section v-if="view !== 'settings'" class="studio-panel">
        <div class="studio-canvas">
          <div v-if="view === 'images' && imageState.result" class="media-grid studio-media-grid">
            <article v-for="(image, index) in imageState.result.images" :key="`${image.src}-${index}`" class="result-card">
              <img :src="image.src" :alt="`生成结果 ${index + 1}`" />
              <p v-if="image.revisedPrompt" class="muted">{{ image.revisedPrompt }}</p>
            </article>
          </div>
          <article v-else-if="view === 'text' && textState.result" class="result-text studio-result">
            {{ textState.result.content }}
          </article>
          <div v-else-if="view === 'videos' && videoState.taskResult?.videoUrl" class="video-stage">
            <video :src="videoState.taskResult.videoUrl" controls playsinline preload="metadata" />
            <a class="button-link" :href="videoState.taskResult.videoUrl" target="_blank" rel="noreferrer">打开视频地址</a>
          </div>
          <div v-else-if="view === 'videos' && videoState.createResult" class="task-canvas">
            <span class="badge badge-accent">任务已提交</span>
            <h3>{{ videoState.createResult.taskId }}</h3>
            <div class="task-metrics">
              <span>提交状态：{{ videoState.createResult.status }}</span>
              <span>查询状态：{{ videoState.taskResult?.status || "等待查询" }}</span>
              <span>进度：{{ videoState.taskResult?.progress ?? "-" }}</span>
            </div>
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
            <span>{{ !activeSetting?.baseUrl || !activeSetting?.apiKey ? "模型待配置" : "模型已就绪" }}</span>
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

      <section v-else class="settings-page">
        <section class="settings-hero">
          <div>
            <p class="eyebrow">Model Settings</p>
            <h2>模型配置</h2>
            <p class="muted">使用列表管理每个模型的 baseURL、API Key 和连通状态。配置会缓存在当前浏览器。</p>
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
              </div>
              <div class="settings-url">{{ getSetting(model.id).baseUrl || "-" }}</div>
              <div>
                <span v-if="settingsState.testState[model.id]?.loading" class="badge badge-warn">测试中</span>
                <span v-else-if="settingsState.testState[model.id]?.result" class="badge badge-success">已连接 {{ settingsState.testState[model.id].result?.durationMs }}ms</span>
                <span v-else-if="settingsState.testState[model.id]?.error" class="badge badge-danger">连接失败</span>
                <span v-else-if="!getSetting(model.id).baseUrl || !getSetting(model.id).apiKey" class="badge badge-warn">待配置</span>
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
              <div v-if="settingsState.modelListState[model.id]?.result" class="settings-row-detail settings-model-list-result">
                <div class="status-row">
                  <span class="badge badge-success">已获取 {{ settingsState.modelListState[model.id].result?.models.length }} 个模型</span>
                  <span class="history-time">{{ settingsState.modelListState[model.id].result?.durationMs }}ms</span>
                </div>
                <div class="available-model-list">
                  <button
                    v-for="modelId in settingsState.modelListState[model.id].result?.models.slice(0, 24)"
                    :key="modelId"
                    class="chip-button model-id-chip"
                    @click="store.updateModelSetting(model.id, { modelNameOverride: modelId })"
                  >
                    {{ modelId }}
                  </button>
                </div>
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
            <div class="form-grid settings-dialog-grid">
              <label class="field"><span>名称</span><input v-model="settingsState.draft.name" /></label>
              <label class="field"><span>备注</span><input v-model="settingsState.draft.description" /></label>
              <label class="field"><span>厂商</span><input v-model="settingsState.draft.vendor" /></label>
              <label class="field"><span>能力类型</span><select v-model="settingsState.draft.capability" @change="settingsState.draft.adapter = getCapabilityDefaultAdapter(settingsState.draft.capability)"><option value="text">文案创作</option><option value="image">图片创作</option><option value="video">视频创作</option></select></label>
              <label class="field field-full"><span>适配器</span><select v-model="settingsState.draft.adapter"><option v-for="adapter in getAdapterOptions(settingsState.draft.capability)" :key="adapter" :value="adapter">{{ ADAPTER_LABELS[adapter] }}</option></select></label>
              <label class="field field-full"><span>模型标识</span><input v-model="settingsState.draft.model" /></label>
              <label class="field field-full"><span>baseURL</span><input v-model="settingsState.draft.baseUrl" placeholder="例如：https://ai.ai666.net" /></label>
              <label class="field field-full"><span>API Key</span><input v-model="settingsState.draft.apiKey" type="password" /></label>
              <label class="field field-full"><span>模型标识覆盖</span><input v-model="settingsState.draft.modelNameOverride" /></label>
            </div>
            <div v-if="settingsState.modelListState[settingsState.draft.id]?.result" class="settings-dialog-models">
              <div class="available-model-list">
                <button
                  v-for="modelId in settingsState.modelListState[settingsState.draft.id].result?.models.slice(0, 18)"
                  :key="modelId"
                  class="chip-button model-id-chip"
                  @click="selectDraftModelId(modelId)"
                >
                  {{ modelId }}
                </button>
              </div>
            </div>
            <div class="settings-dialog-actions">
              <button class="button-secondary" @click="fetchModelList(getDraftModel(), getDraftSetting())">获取模型列表</button>
              <button class="button-secondary" @click="testModel(getDraftModel(), getDraftSetting())">测速</button>
              <button class="button-secondary" @click="settingsState.dialogOpen = false">取消</button>
              <button :disabled="!canSaveDraft()" @click="saveDialog">保存</button>
            </div>
            <div v-if="settingsState.modelListState[settingsState.draft.id]?.error" class="inline-message inline-danger">{{ settingsState.modelListState[settingsState.draft.id].error }}</div>
            <div v-if="settingsState.testState[settingsState.draft.id]?.error" class="inline-message inline-danger">{{ settingsState.testState[settingsState.draft.id].error }}</div>
          </section>
        </div>
      </section>
    </main>
  </div>
</template>
