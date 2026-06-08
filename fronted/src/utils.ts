import type {
  Adapter,
  CatalogParameterDefinition,
  Capability,
  ConversationAsset,
  ConversationDefinition,
  ConversationMessage,
  ModelDefinition,
  ModelSetting,
} from "./types";

export function createLocalId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

export function safeJsonParse<T>(value: string | null, fallback: T): T {
  if (!value) return fallback;
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

export function combinePrompt(keywords: string, prompt: string): string {
  const chunks = [];
  if (keywords.trim()) chunks.push(`关键词：${keywords.trim()}`);
  if (prompt.trim()) chunks.push(prompt.trim());
  return chunks.join("\n\n");
}

export function resolveModelName(model: ModelDefinition, setting?: ModelSetting): string {
  return setting?.modelNameOverride?.trim() || model.model;
}

export function pickPrimaryModel(availableModels: string[], currentModel: string): string {
  const current = currentModel.trim();
  if (!availableModels.length) return current;
  return availableModels.includes(current) ? current : availableModels[0];
}

export function filterModelOptions(options: string[], query: string): string[] {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return options;
  return options.filter((option) => option.toLowerCase().includes(normalizedQuery));
}

export function capabilityFilterForView(viewName: string): Capability | "all" {
  if (viewName === "text") return "text";
  if (viewName === "images") return "image";
  if (viewName === "videos") return "video";
  return "all";
}

export function isPrivateView(viewName: string): boolean {
  return viewName === "settings" || viewName === "profile";
}

export function loginRedirectForView(viewName: string): string {
  const safeView = viewName && viewName !== "auth" && viewName !== "auth-error" ? viewName : "images";
  return `/auth?redirect=${encodeURIComponent(`/${safeView}`)}`;
}

export function resolveAuthRedirect(hash: string, fallback = "images"): string {
  const query = hash.split("?", 2)[1] || "";
  const redirect = new URLSearchParams(query).get("redirect") || "";
  if (!redirect.startsWith("/") || redirect.startsWith("//")) return fallback;
  const route = redirect.replace(/^\/+/, "").split("?", 1)[0];
  return ["text", "images", "videos", "settings", "profile"].includes(route) ? route : fallback;
}

export function canEditModel(model: Pick<ModelDefinition, "serverManaged" | "isPublic" | "canEdit">): boolean {
  if (!model.serverManaged) return true;
  return model.canEdit === true;
}

export function publicShareTargetModels(models: ModelDefinition[], selectedIds: string[]): ModelDefinition[] {
  const selected = new Set(selectedIds);
  return models.filter((model) => selected.has(model.id) && model.serverManaged && model.canEdit === true && !model.isPublic);
}

export function modelConnectionLabel(
  model: Pick<ModelDefinition, "serverManaged" | "isPublic" | "canEdit">,
  setting: Pick<ModelSetting, "baseUrl">,
): string {
  if (model.isPublic) return "公共模型";
  if (model.serverManaged) return "平台托管";
  return setting.baseUrl.trim() ? "自定义密钥" : "未配置";
}

export function stripUpstreamUrls(value: string): string {
  return value
    .replace(/https?:\/\/[^\s)）]+/gi, "")
    .replace(/\s{2,}/g, " ")
    .replace(/\s+([。；，,.])/g, "$1")
    .trim();
}

export function safeModelDescription(model: Pick<ModelDefinition, "description" | "isPublic" | "canEdit"> | null | undefined, fallback: string): string {
  if (!model?.description?.trim()) return fallback;
  if (model.isPublic && model.canEdit !== true) return "平台公共模型，可直接用于创作。";
  const text = stripUpstreamUrls(model.description);
  return text || fallback;
}

export function resolveSidebarFilter(models: ModelDefinition[], filter: Capability | "all"): Capability | "all" {
  if (filter === "all") return "all";
  return filter;
}

export function filterSettingsModels(
  models: ModelDefinition[],
  capability: Capability | "all",
  query: string,
): ModelDefinition[] {
  const normalizedQuery = query.trim().toLowerCase();
  return models.filter((model) => {
    if (capability !== "all" && model.capability !== capability) return false;
    if (!normalizedQuery) return true;
    const searchable = [
      model.name,
      model.vendor,
      model.model,
      model.description,
      ...(model.subModels || []).flatMap((subModel) => [subModel.modelName, subModel.displayName]),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return searchable.includes(normalizedQuery);
  });
}

export function prioritizeModelOptions(options: string[], selectedModel: string): string[] {
  const selected = selectedModel.trim();
  if (!selected || !options.includes(selected)) return options;
  return [selected, ...options.filter((option) => option !== selected)];
}

export interface CatalogOptionItem {
  label: string;
  value: string;
  maxCount?: number | null;
}

export function getPrimarySubModel(model: ModelDefinition | null | undefined) {
  if (!model) return null;
  return (
    model.subModels?.find((item) => item.id === model.primarySubModelId) ||
    model.subModels?.find((item) => item.isPrimary) ||
    model.subModels?.[0] ||
    null
  );
}

export function modelCatalogParameters(model?: ModelDefinition | null): CatalogParameterDefinition[] {
  if (!model) return [];
  const subCatalog = getPrimarySubModel(model)?.catalog;
  const catalog = subCatalog || model.catalog;
  return catalog?.parameters || [];
}

export function hasCatalogParameters(model?: ModelDefinition | null): boolean {
  return modelCatalogParameters(model).length > 0;
}

export function modelCatalogInputHint(model: ModelDefinition | null | undefined, fallback: string): string {
  if (!model) return fallback;
  const subCatalogHint = getPrimarySubModel(model)?.catalog?.inputHint?.trim();
  if (subCatalogHint && !isBrokenDisplayText(subCatalogHint)) return subCatalogHint;
  const modelCatalogHint = model.catalog?.inputHint?.trim();
  return modelCatalogHint && !isBrokenDisplayText(modelCatalogHint) ? modelCatalogHint : fallback;
}

function isBrokenDisplayText(value: string): boolean {
  const text = value.trim();
  if (!text) return false;
  const compact = text.replace(/\s+/g, "");
  const questionMarks = compact.match(/\?/g)?.length || 0;
  if (compact.length >= 12 && questionMarks / compact.length > 0.45) return true;
  const mojibakeChars = text.match(/[锟�鐢瑙鍥閸缂]/g)?.length || 0;
  return text.length >= 12 && mojibakeChars / text.length > 0.28;
}

export function modelCatalogIconUrl(model: ModelDefinition | null | undefined): string {
  if (!model) return "";
  const inferred = inferModelIconUrl(model);
  const primary = getPrimarySubModel(model);
  const subCatalogIcon = primary?.catalog?.icon?.trim();
  if (subCatalogIcon && !shouldPreferInferredIcon(subCatalogIcon)) return subCatalogIcon;
  const modelCatalogIcon = model.catalog?.icon?.trim();
  if (modelCatalogIcon && !shouldPreferInferredIcon(modelCatalogIcon)) return modelCatalogIcon;
  return inferred || subCatalogIcon || modelCatalogIcon || "";
}

const LOBE_ICON_BASE_URL = "https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons";

function lobeIcon(name: string): string {
  return `${LOBE_ICON_BASE_URL}/${name}`;
}

function shouldPreferInferredIcon(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  return (
    normalized.includes("ai-apply-resource.kkidc.com") ||
    normalized.includes("x-oss-") ||
    normalized.endsWith("/grok-color.svg") ||
    normalized.endsWith("/glm-color.svg") ||
    normalized.endsWith("/veo-color.svg")
  );
}

export function inferModelIconUrl(model: ModelDefinition | null | undefined): string {
  if (!model) return "";
  const primary = getPrimarySubModel(model);
  const source = [
    primary?.modelName,
    primary?.displayName,
    primary?.catalog?.modelName,
    primary?.catalog?.displayName,
    primary?.catalog?.icon,
    model.catalog?.modelName,
    model.catalog?.displayName,
    model.catalog?.icon,
    model.model,
    model.name,
    model.vendor,
  ].filter(Boolean).join(" ").toLowerCase();
  if (!source) return "";
  if (source.includes("gemini") || source.includes("banana") || source.includes("veo")) return lobeIcon("Gemini-color.svg");
  if (source.includes("openai") || source.includes("gpt") || source.includes("codex")) return lobeIcon("OpenAI.svg");
  if (source.includes("doubao") || source.includes("seedance") || source.includes("seedream") || source.includes("seed2") || source.includes("kuaikuai")) return lobeIcon("Doubao-color.svg");
  if (source.includes("qwen") || source.includes("wanxiang") || source.includes("qvq")) return lobeIcon("Qwen-color.svg");
  if (source.includes("claude") || source.includes("anthropic")) return lobeIcon("Claude-color.svg");
  if (source.includes("deepseek")) return lobeIcon("DeepSeek-color.svg");
  if (source.includes("kimi")) return lobeIcon("Kimi-color.svg");
  if (source.includes("minimax")) return lobeIcon("Minimax-color.svg");
  if (source.includes("grok") || source.includes("xai")) return lobeIcon("XAI.svg");
  if (source.includes("glm") || source.includes("zhipu")) return lobeIcon("Zhipu-color.svg");
  return "";
}

export function modelParameterSourceLabel(model?: ModelDefinition | null): string {
  return hasCatalogParameters(model) ? "精确参数" : "通用参数";
}

export function catalogParameterSignature(model?: ModelDefinition | null): string {
  return modelCatalogParameters(model)
    .map((parameter) => {
      const options = [...parameter.options]
        .sort((left, right) => left.sortOrder - right.sortOrder)
        .map((option) => `${option.optionValue}:${option.isDefault ? "1" : "0"}`)
        .join(",");
      return `${parameter.paramKey}:${parameter.defaultValue}:${parameter.maxCount || ""}:${options}`;
    })
    .join("|");
}

type CatalogParameterKeyInput = string | string[];

function catalogParameterKeys(key: CatalogParameterKeyInput): string[] {
  return Array.isArray(key) ? key : [key];
}

export function catalogParameter(model: ModelDefinition | null | undefined, key: CatalogParameterKeyInput): CatalogParameterDefinition | null {
  const keys = catalogParameterKeys(key);
  return modelCatalogParameters(model).find((item) => keys.includes(item.paramKey)) || null;
}

export function hasCatalogParameter(model: ModelDefinition | null | undefined, key: CatalogParameterKeyInput): boolean {
  return Boolean(catalogParameter(model, key));
}

export function supportsCatalogParameter(model: ModelDefinition | null | undefined, ...keys: string[]): boolean {
  if (!hasCatalogParameters(model)) return true;
  return Boolean(catalogParameter(model, keys));
}

export function catalogOptionItems(model: ModelDefinition | null | undefined, key: CatalogParameterKeyInput, fallback: string[]): CatalogOptionItem[] {
  const parameter = catalogParameter(model, key);
  if (!parameter?.options.length) {
    return fallback.map((value) => ({ label: value, value }));
  }
  return [...parameter.options]
    .sort((left, right) => left.sortOrder - right.sortOrder)
    .map((option) => ({
      label: option.optionName || option.optionValue,
      value: option.optionValue,
      maxCount: option.maxCount,
    }))
    .filter((item) => item.value);
}

export function catalogDefaultValue(model: ModelDefinition | null | undefined, key: CatalogParameterKeyInput, fallback: string): string {
  const parameter = catalogParameter(model, key);
  if (!parameter) return fallback;
  const defaultOption = [...parameter.options].sort((left, right) => left.sortOrder - right.sortOrder).find((option) => option.isDefault);
  return defaultOption?.optionValue || parameter.defaultValue || fallback;
}

export function catalogMaxCount(model: ModelDefinition | null | undefined, key: CatalogParameterKeyInput, fallback: number): number {
  return catalogParameter(model, key)?.maxCount || fallback;
}

export function catalogRequestKey(model: ModelDefinition | null | undefined, key: CatalogParameterKeyInput, fallback: string): string {
  return catalogParameter(model, key)?.paramKey || fallback;
}

export type VideoModeValue = "text" | "reference" | "first-frame" | "start-end";

export interface ImageGenerationRequestInput {
  references: string[];
  count: string;
  size: string;
  ratio: string;
  resolution: string;
  quality: string;
}

export function catalogOptionMaxCount(
  model: ModelDefinition | null | undefined,
  key: CatalogParameterKeyInput,
  optionValue: string,
  fallback: number,
): number {
  const parameter = catalogParameter(model, key);
  const option = parameter?.options.find((item) => item.optionValue === optionValue);
  return option?.maxCount || fallback;
}

export function catalogVideoModeValue(value: string): VideoModeValue {
  if (value === "reference") return "reference";
  if (value === "first_frame" || value === "first-frame") return "first-frame";
  if (value === "first_last_frame" || value === "start-end") return "start-end";
  return "text";
}

export function videoModeParamValue(mode: VideoModeValue): string {
  if (mode === "reference") return "reference";
  if (mode === "first-frame") return "first_frame";
  if (mode === "start-end") return "first_last_frame";
  return "text";
}

export function videoModeRequiredUploadCount(mode: VideoModeValue): number {
  if (mode === "text") return 0;
  if (mode === "start-end") return 2;
  return 1;
}

export function videoModeUploadLimit(model: ModelDefinition | null | undefined, mode: VideoModeValue): number {
  const fallback = videoModeRequiredUploadCount(mode);
  if (mode === "text") return 0;
  return catalogOptionMaxCount(model, "video_mode", videoModeParamValue(mode), fallback) || fallback;
}

export function isVeoVideoModel(model: ModelDefinition | null | undefined): boolean {
  const names = [
    model?.adapter || "",
    model?.model || "",
    getPrimarySubModel(model)?.modelName || "",
  ];
  return names.some((value) => value.toLowerCase().includes("veo"));
}

export function videoDurationFallbackOptions(adapter?: Adapter): string[] {
  return adapter === "video-unified-veo" ? ["4", "5", "8"] : ["4", "5", "8", "10", "12", "15"];
}

export function videoDurationOptionItems(model: ModelDefinition | null | undefined): CatalogOptionItem[] {
  const options = catalogOptionItems(model, "duration", videoDurationFallbackOptions(model?.adapter));
  if (!isVeoVideoModel(model)) return options;
  return options.filter((item) => {
    const duration = Number(item.value);
    return Number.isFinite(duration) ? duration <= 8 : true;
  });
}

export function videoResolutionRequestKey(
  model: ModelDefinition | null | undefined,
  value: string,
): string {
  const normalized = value.trim().toLowerCase();
  if (/^\d+p$/.test(normalized)) return "resolution";
  return catalogRequestKey(model, ["resolution", "size"], "resolution");
}

function addCatalogField(
  payload: Record<string, unknown>,
  model: ModelDefinition,
  keys: CatalogParameterKeyInput,
  outputKey: string,
  value: unknown,
) {
  const keyList = Array.isArray(keys) ? keys : [keys];
  if (supportsCatalogParameter(model, ...keyList)) {
    payload[catalogRequestKey(model, keys, outputKey)] = value;
  }
}

export function buildImageGenerationRequestBody(
  model: ModelDefinition,
  input: ImageGenerationRequestInput,
  finalPrompt: string,
  extra: Record<string, unknown>,
): Record<string, unknown> {
  const body: Record<string, unknown> = {
    prompt: finalPrompt,
    response_format: "url",
  };
  if (supportsCatalogParameter(model, "image", "images") && input.references.length) {
    body[catalogRequestKey(model, ["image", "images"], "image")] = input.references;
  }
  const quantity = Number(input.count) || 1;
  addCatalogField(body, model, "quantity", "n", quantity);
  if (catalogRequestKey(model, "quantity", "n") !== "n") {
    addCatalogField(body, model, "quantity", "quantity", quantity);
  }
  addCatalogField(body, model, "size", "size", input.size);
  addCatalogField(body, model, ["ratio", "aspect_ratio"], "ratio", input.ratio);
  addCatalogField(body, model, "resolution", "resolution", input.resolution);
  addCatalogField(body, model, "quality", "quality", input.quality);
  return { ...body, ...extra };
}

export function buildVideoMediaFields(
  model: ModelDefinition,
  mode: VideoModeValue,
  images: string[],
): Record<string, unknown> {
  if (mode === "text" || !images.length) return {};
  const hasCatalog = hasCatalogParameters(model);
  const first = images[0];
  const last = images[1];
  if (mode === "first-frame") {
    if (hasCatalog && supportsCatalogParameter(model, "first_frame")) return { [catalogRequestKey(model, "first_frame", "first_frame")]: first };
    return { images: [first] };
  }
  if (mode === "start-end") {
    if (!hasCatalog) {
      return { images: images.slice(0, 2) };
    }
    const fields: Record<string, unknown> = {};
    if (first) {
      fields[catalogRequestKey(model, "first_frame", "first_frame")] = first;
    }
    if (last) {
      fields[catalogRequestKey(model, "last_frame", "last_frame")] = last;
    }
    if (!supportsCatalogParameter(model, "first_frame") && !supportsCatalogParameter(model, "last_frame")) {
      return { images: images.slice(0, 2) };
    }
    return fields;
  }
  if (hasCatalog && supportsCatalogParameter(model, "img_url")) {
    return { [catalogRequestKey(model, "img_url", "img_url")]: images };
  }
  if (hasCatalog && supportsCatalogParameter(model, "image", "images")) {
    return { [catalogRequestKey(model, ["image", "images"], "images")]: images };
  }
  return { images };
}

export function getModelIdentifierError(value: string): string {
  const model = value.trim();
  if (!model) return "";
  if (/^https?:\/\//i.test(model)) {
    return "模型标识应填写模型名称，例如 gpt-4o；请求地址请填写到 baseURL。";
  }
  return "";
}

export function getMissingModelMessage(capability: Capability): string {
  if (capability === "text") {
    return "当前用户还没有可用的文案创作模型，请先在设置里添加并保存一个聊天模型。";
  }
  if (capability === "image") {
    return "当前用户还没有可用的图片创作模型，请先在设置里添加并保存一个生图模型。";
  }
  return "当前用户还没有可用的视频创作模型，请先在设置里添加并保存一个视频模型。";
}

export function shortText(value: string, max = 72): string {
  const text = value.replace(/\s+/g, " ").trim();
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function renderMarkdownPreview(value: string): string {
  const lines = value.replace(/\r\n/g, "\n").split("\n");
  const chunks: string[] = [];
  let paragraph: string[] = [];
  let list: string[] = [];
  let code: string[] | null = null;

  const flushParagraph = () => {
    if (!paragraph.length) return;
    chunks.push(`<p>${formatInlineMarkdown(paragraph.join(" "))}</p>`);
    paragraph = [];
  };
  const flushList = () => {
    if (!list.length) return;
    chunks.push(`<ul>${list.map((item) => `<li>${formatInlineMarkdown(item)}</li>`).join("")}</ul>`);
    list = [];
  };

  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      if (code) {
        chunks.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);
        code = null;
      } else {
        flushParagraph();
        flushList();
        code = [];
      }
      continue;
    }

    if (code) {
      code.push(line);
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }

    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      const level = heading[1].length;
      chunks.push(`<h${level}>${formatInlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }

    const listItem = line.match(/^\s*[-*]\s+(.+)$/);
    if (listItem) {
      flushParagraph();
      list.push(listItem[1]);
      continue;
    }

    flushList();
    paragraph.push(line.trim());
  }

  if (code) chunks.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);
  flushParagraph();
  flushList();
  return chunks.join("");
}

function formatInlineMarkdown(value: string): string {
  const escaped = escapeHtml(value);
  return escaped
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>");
}

export function findPromptBeforeMessage(messages: ConversationMessage[], messageId: string): string {
  const index = messages.findIndex((message) => message.id === messageId);
  const searchUntil = index >= 0 ? index : messages.length;
  for (let cursor = searchUntil - 1; cursor >= 0; cursor -= 1) {
    const message = messages[cursor];
    if (message.role === "user" && message.content.trim()) {
      return message.content;
    }
  }
  return "";
}

interface LocalMessageInput {
  role: "user" | "assistant";
  content: string;
  status?: ConversationMessage["status"];
  errorMessage?: string;
  canRetry?: boolean;
  assets?: Array<Partial<ConversationAsset> & { assetType: string; url: string }>;
}

interface LocalConversationAppendInput {
  capability: Capability;
  titleSeed: string;
  modelGroupId: string | null;
  subModelId?: string | null;
  now?: string;
  messages: LocalMessageInput[];
}

export function appendLocalConversationMessages(
  current: ConversationDefinition | null,
  input: LocalConversationAppendInput,
): ConversationDefinition {
  const now = input.now || new Date().toISOString();
  const sameConversation = current?.capability === input.capability ? current : null;
  const base: ConversationDefinition = sameConversation || {
    id: createLocalId("local-conversation"),
    title: shortText(input.titleSeed || "本地对话", 34),
    capability: input.capability,
    modelGroupId: input.modelGroupId,
    subModelId: input.subModelId || null,
    status: "active",
    createdAt: now,
    updatedAt: now,
    messages: [],
  };
  const nextMessages = input.messages.map((item): ConversationMessage => ({
    id: createLocalId("local-message"),
    role: item.role,
    capability: input.capability,
    content: item.content,
    status: item.status || "success",
    errorMessage: item.errorMessage || "",
    canRetry: item.canRetry || false,
    modelGroupId: input.modelGroupId,
    subModelId: input.subModelId || null,
    assets: (item.assets || []).map((asset): ConversationAsset => ({
      id: asset.id || createLocalId("local-asset"),
      capability: input.capability,
      assetType: asset.assetType,
      url: asset.url,
      thumbnailUrl: asset.thumbnailUrl || "",
      metadata: asset.metadata || {},
      createdAt: now,
    })),
    createdAt: now,
  }));
  return {
    ...base,
    modelGroupId: base.modelGroupId || input.modelGroupId,
    subModelId: base.subModelId || input.subModelId || null,
    updatedAt: now,
    messages: [...base.messages, ...nextMessages],
  };
}

export function updateLocalConversationMessage(
  conversation: ConversationDefinition,
  messageId: string,
  patch: Partial<Pick<ConversationMessage, "content" | "status" | "errorMessage" | "canRetry" | "assets">>,
): ConversationDefinition {
  const now = new Date().toISOString();
  return {
    ...conversation,
    updatedAt: now,
    messages: conversation.messages.map((message) =>
      message.id === messageId
        ? {
            ...message,
            ...patch,
            assets: patch.assets || message.assets,
          }
        : message,
    ),
  };
}

export function updateLocalConversationTaskMessage(
  conversation: ConversationDefinition | null,
  taskId: string,
  patch: Partial<Pick<ConversationMessage, "content" | "status" | "errorMessage" | "canRetry" | "assets">>,
): ConversationDefinition | null {
  if (!conversation || !taskId) return conversation;
  const target = [...conversation.messages]
    .reverse()
    .find((message) => message.role === "assistant" && message.content.trim() === taskId);
  if (!target) return conversation;
  return updateLocalConversationMessage(conversation, target.id, patch);
}

export function markConversationMessageFailed(
  conversation: ConversationDefinition | null,
  messageId: string,
  message: string,
): ConversationDefinition | null {
  if (!conversation || !messageId) return conversation;
  return updateLocalConversationMessage(conversation, messageId, {
    status: "error",
    errorMessage: message,
    canRetry: true,
    content: "",
  });
}

export function videoMessageStatusFromTaskStatus(status: string): ConversationMessage["status"] {
  const normalized = status.trim().toLowerCase();
  if (normalized.includes("complete") || normalized.includes("success") || normalized.includes("succeed")) return "success";
  if (normalized.includes("fail") || normalized.includes("error") || normalized.includes("cancel")) return "error";
  return "processing";
}

export function shouldContinuePollingTask(status: string): boolean {
  return videoMessageStatusFromTaskStatus(status) === "processing";
}

export function conversationAssetFromVideoQueryResult(input: {
  taskId: string;
  status?: string | null;
  progress?: number | string | null;
  videoUrl?: string | null;
  thumbnailUrl?: string | null;
}): (Partial<ConversationAsset> & { assetType: string; url: string }) | null {
  if (!input.videoUrl) return null;
  return {
    assetType: "video",
    url: input.videoUrl,
    thumbnailUrl: input.thumbnailUrl || "",
    metadata: {
      taskId: input.taskId,
      status: input.status || "",
      progress: input.progress ?? null,
    },
  };
}

export function conversationAssetsFromImageQueryResult(input: {
  taskId: string;
  status?: string | null;
  progress?: number | string | null;
  images: Array<{ src: string; revisedPrompt?: string | null }>;
}): Array<Partial<ConversationAsset> & { assetType: string; url: string }> {
  return input.images
    .filter((image) => Boolean(image.src))
    .map((image) => ({
      assetType: "image",
      url: image.src,
      thumbnailUrl: "",
      metadata: {
        taskId: input.taskId,
        status: input.status || "",
        progress: input.progress ?? null,
        revisedPrompt: image.revisedPrompt || "",
      },
    }));
}

export function shouldResetConversationForModelSwitch(
  conversation: { capability?: Capability | string; modelGroupId?: string | null; subModelId?: string | null } | null | undefined,
  nextModel: { capability: Capability; modelGroupId?: string | null; subModelId?: string | null },
): boolean {
  if (!conversation?.capability) return false;
  if (conversation.capability !== nextModel.capability) return true;
  if (conversation.subModelId && nextModel.subModelId && conversation.subModelId !== nextModel.subModelId) return true;
  if (conversation.modelGroupId && nextModel.modelGroupId && conversation.modelGroupId !== nextModel.modelGroupId) return true;
  return false;
}

export function visibleConversationMessages(
  conversation: ConversationDefinition | null | undefined,
  activeCapability: Capability | null | undefined,
): ConversationMessage[] {
  if (!conversation || !activeCapability || conversation.capability !== activeCapability) return [];
  return conversation.messages;
}

export function generatedAssetReferenceFileName(asset: { assetType: string; url: string }): string {
  if (asset.url.startsWith("data:")) {
    return asset.assetType === "video" ? "generated-video.mp4" : "generated-image.png";
  }
  const path = asset.url.split(/[?#]/, 1)[0];
  const fileName = decodeURIComponent(path.split("/").pop() || "");
  if (fileName) return fileName;
  return asset.assetType === "video" ? "generated-video.mp4" : "generated-image.png";
}

export function mediaPreviewActionLabels(assetType: string): string[] {
  if (assetType === "image") {
    return ["保存", "引用编辑", "选取编辑", "关闭"];
  }
  return ["保存", "关闭"];
}

export function imageGenerationSummary(input: {
  ratio: string;
  resolution: string;
  count: string;
}): string {
  return [
    input.ratio,
    input.resolution,
    input.count ? `${input.count}张` : "",
  ].filter(Boolean).join("  ") || "参数";
}

export function videoGenerationSummary(input: {
  mode: string;
  aspectRatio: string;
  resolution: string;
  duration: string;
  count?: string;
}): string {
  const modeLabel = input.mode
    ? input.mode === "reference" ? "全能参考" : input.mode === "first-frame" ? "首帧" : input.mode === "start-end" ? "首尾帧" : "文生视频"
    : "";
  return [
    modeLabel,
    input.aspectRatio,
    input.resolution,
    input.duration ? `${input.duration}秒` : "",
    input.count ? `${input.count}条` : "",
  ].filter(Boolean).join("  ") || "参数";
}

export function modelDisplayNameFromPrimary(capability: Capability, primaryModel: string): string {
  const modelName = primaryModel.trim();
  const suffix = capability === "text" ? "文案" : capability === "image" ? "图片" : "视频";
  return modelName ? `${modelName} ${suffix}` : `${suffix}模型`;
}

export function isGeneratedModelDisplayName(value: string): boolean {
  const name = value.trim();
  return (
    !name ||
    name === "文案模型配置" ||
    name === "图片模型配置" ||
    name === "视频模型配置" ||
    name === "文案模型" ||
    name === "图片模型" ||
    name === "视频模型" ||
    /^.+\s(文案|图片|视频)$/.test(name)
  );
}

export function modelDisplayNameForModel(model: ModelDefinition, setting?: ModelSetting): string {
  if (model.name && !isGeneratedModelDisplayName(model.name) && !isBrokenDisplayText(model.name)) return model.name;
  return modelDisplayNameFromPrimary(model.capability, resolveModelName(model, setting));
}

export function testResultSummary(value: unknown): {
  status: string;
  duration: string;
  requestUrl: string;
  rawPreview: string;
} {
  const result = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const request = result.request && typeof result.request === "object" ? result.request as Record<string, unknown> : {};
  const status = result.status;
  const durationMs = result.durationMs;
  const raw = Object.prototype.hasOwnProperty.call(result, "raw") ? result.raw : {};
  const statusText = typeof status === "number" || typeof status === "string" ? String(status).trim() : "";
  const durationText = typeof durationMs === "number" || typeof durationMs === "string" ? String(durationMs).trim() : "";
  let rawPreview = "";
  try {
    rawPreview = JSON.stringify(raw, null, 2);
  } catch {
    rawPreview = String(raw);
  }
  return {
    status: statusText || "未知",
    duration: durationText ? `${durationText}ms` : "未知",
    requestUrl: typeof request.url === "string" && request.url.trim() ? request.url : "未知",
    rawPreview: rawPreview.slice(0, 1400),
  };
}
