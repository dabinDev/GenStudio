import type {
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

export function prioritizeModelOptions(options: string[], selectedModel: string): string[] {
  const selected = selectedModel.trim();
  if (!selected || !options.includes(selected)) return options;
  return [selected, ...options.filter((option) => option !== selected)];
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

export function shouldResetConversationForModelSwitch(
  conversation: { capability?: Capability | string } | null | undefined,
  nextCapability: Capability,
): boolean {
  return Boolean(conversation?.capability && conversation.capability !== nextCapability);
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
  return [input.ratio, input.resolution, `${input.count || "1"}张`].join("  ");
}

export function videoGenerationSummary(input: {
  mode: string;
  aspectRatio: string;
  resolution: string;
  duration: string;
  count?: string;
}): string {
  const modeLabel = input.mode === "reference" ? "全能参考" : input.mode === "start-end" ? "首尾帧" : "文生视频";
  return [modeLabel, input.aspectRatio, input.resolution, `${input.duration || "5"}秒`, `${input.count || "1"}条`].join("  ");
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
  if (model.name && !isGeneratedModelDisplayName(model.name)) return model.name;
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
