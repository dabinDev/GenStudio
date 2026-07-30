import type {
  CatalogModelDefinition,
  Capability,
  ConversationDefinition,
  CreditBundle,
  CreditTransaction,
  ServerModelDefinition,
  PromptLibraryEventType,
  PromptSceneRecommendation,
  PromptSceneRecommendationPayload,
  UploadedAsset,
  UserProfile,
} from "./types";
import { isProductionRuntime } from "./env";

const CSRF_SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const AUTH_CSRF_EXEMPT_ENDPOINTS = new Set(["/api/auth/login", "/api/auth/register", "/api/auth/dev-login"]);

let csrfToken = "";

interface ProxyErrorShape {
  detail?:
    | {
    message?: string;
    [key: string]: unknown;
  }
    | Array<Record<string, unknown>>
    | string;
  error?: {
    message?: string;
  };
  message?: string;
}

export class ApiRequestError extends Error {
  detail: Extract<ProxyErrorShape["detail"], Record<string, unknown>> | null;
  status: number;

  constructor(message: string, status: number, detail: Extract<ProxyErrorShape["detail"], Record<string, unknown>> | null = null) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.detail = detail;
  }
}

function defaultErrorMessage(status: number): string {
  if (status === 502) return "服务暂时不可用，请稍后重试。";
  if (status === 503) return "服务正在维护或暂时不可用，请稍后重试。";
  if (status === 504) return "请求超时，请稍后重试。";
  return `请求失败，状态码 ${status}`;
}

function cleanValidationMessage(message: string): string {
  return message.replace(/^value error,\s*/i, "").trim();
}

function extractErrorMessage(value: unknown): string {
  if (!value) return "";
  if (typeof value === "string") return cleanValidationMessage(value);
  if (Array.isArray(value)) {
    for (const item of value) {
      const message = extractErrorMessage(item);
      if (message) return message;
    }
    return "";
  }
  if (typeof value !== "object") return "";
  const objectValue = value as Record<string, unknown>;
  for (const key of ["message", "msg", "detail"]) {
    const message = extractErrorMessage(objectValue[key]);
    if (message) return message;
  }
  return "";
}

function normalizeErrorDetail(detail: ProxyErrorShape["detail"], message: string): Extract<ProxyErrorShape["detail"], Record<string, unknown>> | null {
  if (!detail) return null;
  if (Array.isArray(detail)) {
    return { message, errors: detail };
  }
  if (typeof detail === "string") {
    return { message: detail };
  }
  return detail;
}

async function parseErrorPayload(response: Response): Promise<{ message: string; detail: Extract<ProxyErrorShape["detail"], Record<string, unknown>> | null }> {
  try {
    const payload = (await response.json()) as ProxyErrorShape;
    const message = (
      extractErrorMessage(payload.detail) ||
      payload.error?.message ||
      payload.message ||
      defaultErrorMessage(response.status)
    );
    return { message, detail: normalizeErrorDetail(payload.detail, message) };
  } catch {
    return { message: defaultErrorMessage(response.status), detail: null };
  }
}

export function setCsrfToken(token: string): void {
  csrfToken = token;
}

function shouldAttachCsrf(endpoint: string, method: string): boolean {
  return Boolean(csrfToken && !CSRF_SAFE_METHODS.has(method.toUpperCase()) && !AUTH_CSRF_EXEMPT_ENDPOINTS.has(endpoint));
}

function shouldRefreshCsrf(endpoint: string, method: string, status: number, message: string): boolean {
  return (
    status === 403 &&
    !CSRF_SAFE_METHODS.has(method.toUpperCase()) &&
    !AUTH_CSRF_EXEMPT_ENDPOINTS.has(endpoint) &&
    message.toLowerCase().includes("csrf")
  );
}

async function requestJson<T>(endpoint: string, init: RequestInit = {}, retryingCsrf = false): Promise<T> {
  const method = init.method || "GET";
  const response = await fetch(endpoint, {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(shouldAttachCsrf(endpoint, method) ? { "X-CSRF-Token": csrfToken } : {}),
      ...(init.headers || {}),
    },
  });

  if (!response.ok) {
    const parsed = await parseErrorPayload(response);
    if (!retryingCsrf && shouldRefreshCsrf(endpoint, method, response.status, parsed.message)) {
      await fetchCsrfToken();
      return requestJson<T>(endpoint, init, true);
    }
    throw new ApiRequestError(parsed.message, response.status, parsed.detail);
  }

  return (await response.json()) as T;
}

export async function postProxy<T>(endpoint: string, body: Record<string, unknown>): Promise<T> {
  return requestJson<T>(endpoint, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function postProxyWithSignal<T>(
  endpoint: string,
  body: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<T> {
  return requestJson<T>(endpoint, {
    method: "POST",
    body: JSON.stringify(body),
    signal,
  });
}

export async function getApi<T>(endpoint: string): Promise<T> {
  return requestJson<T>(endpoint);
}

export async function postApi<T>(endpoint: string, body: Record<string, unknown> = {}): Promise<T> {
  return requestJson<T>(endpoint, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function putApi<T>(endpoint: string, body: Record<string, unknown> = {}): Promise<T> {
  return requestJson<T>(endpoint, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function deleteApi<T>(endpoint: string): Promise<T> {
  return requestJson<T>(endpoint, {
    method: "DELETE",
  });
}

export async function fetchCurrentUser(): Promise<UserProfile | null> {
  const response = await fetch("/api/auth/me", { credentials: "include" });
  if (response.status === 401) return null;
  if (!response.ok) {
    const parsed = await parseErrorPayload(response);
    throw new ApiRequestError(parsed.message, response.status, parsed.detail);
  }
  const payload = (await response.json()) as { user: UserProfile };
  return payload.user;
}

export async function fetchCsrfToken(): Promise<string> {
  const payload = await getApi<{ csrfToken: string }>("/api/auth/csrf");
  setCsrfToken(payload.csrfToken);
  return payload.csrfToken;
}

export async function registerAccount(body: { email?: string; phone?: string; password: string; nickname?: string }): Promise<UserProfile> {
  const payload = await postApi<{ user: UserProfile }>("/api/auth/register", body);
  await fetchCsrfToken();
  return payload.user;
}

export async function loginWithPassword(body: { identifier: string; password: string }): Promise<UserProfile> {
  const payload = await postApi<{ user: UserProfile }>("/api/auth/login", body);
  await fetchCsrfToken();
  return payload.user;
}

export async function devLogin(body: Partial<UserProfile> = {}): Promise<UserProfile> {
  const payload = await postApi<{ user: UserProfile }>("/api/auth/dev-login", body);
  await fetchCsrfToken();
  return payload.user;
}

export async function logout(): Promise<void> {
  await postApi<{ ok: boolean }>("/api/auth/logout", {});
  setCsrfToken("");
}

export async function changeMyPassword(body: { currentPassword: string; newPassword: string }): Promise<void> {
  await postApi<{ ok: boolean }>("/api/users/me/password", body);
}

export async function updateMyProfile(body: { nickname?: string; phone?: string; avatarUrl?: string }): Promise<UserProfile> {
  const payload = await putApi<{ user: UserProfile }>("/api/users/me", body);
  return payload.user;
}

export async function fetchServerModels(): Promise<ServerModelDefinition[]> {
  const payload = await getApi<{ models: ServerModelDefinition[] }>("/api/models");
  return payload.models;
}

export async function fetchMyCredits(): Promise<CreditBundle> {
  return getApi<CreditBundle>("/api/credits/me");
}

export async function dismissCreditGrantNotice(transactionId: string): Promise<CreditTransaction> {
  const payload = await postApi<{ transaction: CreditTransaction }>(`/api/credits/notifications/${encodeURIComponent(transactionId)}/dismiss`);
  return payload.transaction;
}

export async function fetchCatalogModels(capability?: Capability): Promise<CatalogModelDefinition[]> {
  const query = capability ? `?capability=${encodeURIComponent(capability)}` : "";
  const payload = await getApi<{ models: CatalogModelDefinition[] }>(`/api/catalog/models${query}`);
  return payload.models;
}

export async function syncKkyiCatalog(body: { bearerToken?: string; modelType?: number }): Promise<{
  synced: number;
  models: CatalogModelDefinition[];
}> {
  return postApi("/api/catalog/kkyi/sync", body);
}

export async function fetchConversations(): Promise<ConversationDefinition[]> {
  const payload = await getApi<{ conversations: ConversationDefinition[] }>("/api/conversations");
  return payload.conversations;
}

export async function fetchConversation(conversationId: string): Promise<ConversationDefinition> {
  const payload = await getApi<{ conversation: ConversationDefinition }>(`/api/conversations/${conversationId}`);
  return payload.conversation;
}

export async function updateConversationTitle(conversationId: string, title: string): Promise<ConversationDefinition> {
  const payload = await postApi<{ conversation: ConversationDefinition }>(`/api/conversations/${conversationId}/rename`, { title });
  return payload.conversation;
}

export async function createServerModel(body: Record<string, unknown>): Promise<ServerModelDefinition> {
  const payload = await postApi<{ model: ServerModelDefinition }>("/api/models", body);
  return payload.model;
}

export async function updateServerModel(modelId: string, body: Record<string, unknown>): Promise<ServerModelDefinition> {
  const payload = await putApi<{ model: ServerModelDefinition }>(`/api/models/${modelId}`, body);
  return payload.model;
}

export async function deleteServerModel(modelId: string): Promise<void> {
  await deleteApi<{ ok: boolean }>(`/api/models/${modelId}`);
}

export async function syncServerModel(modelId: string): Promise<{ model: ServerModelDefinition; models: string[]; durationMs: number }> {
  return postApi(`/api/models/${modelId}/sync`, {});
}

export async function optimizePrompt(body: Record<string, unknown>): Promise<{ prompt: string; raw?: Record<string, unknown> }> {
  return postApi("/api/proxy/prompt/optimize", body);
}

export async function fetchImagePromptRecommendations(
  imageUrl: string,
  limit = 8,
): Promise<PromptSceneRecommendationPayload> {
  return postApi("/api/prompt-library/image-recommendations", { imageUrl, limit });
}

export async function recordPromptLibraryEvent(
  templateId: string,
  eventType: PromptLibraryEventType,
  imageUrl = "",
): Promise<PromptSceneRecommendation> {
  const payload = await postApi<{ template: PromptSceneRecommendation }>("/api/prompt-library/events", {
    templateId,
    eventType,
    imageUrl,
  });
  return payload.template;
}

export async function setServerPrimaryModel(modelId: string, subModelId: string): Promise<ServerModelDefinition> {
  const payload = await postApi<{ model: ServerModelDefinition }>(`/api/models/${modelId}/primary`, { subModelId });
  return payload.model;
}

export async function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
        return;
      }
      reject(new Error("读取本地文件失败。"));
    });
    reader.addEventListener("error", () => reject(new Error("读取本地文件失败。")));
    reader.readAsDataURL(file);
  });
}

function isUploadPresignErrorLike(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const maybeError = error as {
    message?: unknown;
    name?: unknown;
    status?: unknown;
    detail?: { message?: unknown; raw?: unknown } | null;
  };
  if (!(error instanceof ApiRequestError) && maybeError.name !== "ApiRequestError") return false;

  const status = typeof maybeError.status === "number" ? maybeError.status : 0;
  if (status === 404 || status === 405 || status >= 500) return true;

  const message = [maybeError.message, maybeError.detail?.message, maybeError.detail?.raw]
    .filter((value): value is string => typeof value === "string")
    .join("\n")
    .toLowerCase();
  return message.includes("invalid url") || message.includes("presign") || message.includes("404 page not found");
}

function uploadFallbackMessage(error: unknown): string {
  if (!error || typeof error !== "object") return "";
  const maybeError = error as {
    message?: unknown;
    detail?: { message?: unknown; raw?: unknown } | null;
  };
  return [maybeError.message, maybeError.detail?.message, maybeError.detail?.raw]
    .filter((value): value is string => typeof value === "string")
    .join("\n")
    .toLowerCase();
}

export function shouldFallbackToLocalReference(
  error: unknown,
  runtime: { mode?: string; env?: string } = {},
): boolean {
  const fallbackMessage = uploadFallbackMessage(error);
  if (
    isProductionRuntime(runtime.mode, runtime.env) &&
    !fallbackMessage.includes("object storage") &&
    !fallbackMessage.includes("对象存储")
  ) {
    return false;
  }
  if (isUploadPresignErrorLike(error)) return true;
  if (!(error instanceof ApiRequestError)) return false;
  if (error.status === 404 || error.status === 405 || error.status >= 500) return true;
  const message = error.message.toLowerCase();
  return message.includes("invalid url") || message.includes("presign") || message.includes("上传地址");
}

export async function uploadAsset(
  file: File,
  config: UploadConfig,
): Promise<UploadedAsset> {
  try {
    const presign = await postProxy<{
      uploadUrl: string;
      method: string;
      publicUrl: string;
      objectKey: string;
      contentType: string;
      thumbnailUrl?: string;
      thumbnailObjectKey?: string;
    }>("/api/proxy/upload/presign", {
      ...(config.subModelId ? { subModelId: config.subModelId } : { config }),
      fileName: file.name,
      contentType: file.type || "application/octet-stream",
    });

    const uploadResponse = await fetch(presign.uploadUrl, {
      method: presign.method || "PUT",
      headers: { "Content-Type": file.type || presign.contentType },
      body: file,
    });

    if (!uploadResponse.ok) {
      throw new Error("文件上传到预签名地址失败。");
    }

    return {
      id: crypto.randomUUID(),
      fileName: file.name,
      publicUrl: presign.publicUrl,
      contentType: file.type || presign.contentType,
      localPreviewUrl: URL.createObjectURL(file),
      objectKey: presign.objectKey,
      thumbnailUrl: presign.thumbnailUrl,
      thumbnailObjectKey: presign.thumbnailObjectKey,
    };
  } catch (error) {
    if (!shouldFallbackToLocalReference(error)) {
      throw error;
    }
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch("/api/upload/local", {
        method: "POST",
        credentials: "include",
        body: formData,
      });
      if (response.ok) {
        const payload = (await response.json()) as UploadedAsset;
        return {
          id: payload.id || crypto.randomUUID(),
          fileName: payload.fileName || file.name,
          publicUrl: payload.publicUrl,
          contentType: payload.contentType || file.type || "application/octet-stream",
          localPreviewUrl: payload.localPreviewUrl || payload.publicUrl,
          objectKey: payload.objectKey,
          thumbnailUrl: payload.thumbnailUrl,
          thumbnailObjectKey: payload.thumbnailObjectKey,
        };
      }
    } catch {
      // Last resort for development-only provider upload gaps.
    }
    const dataUrl = await fileToDataUrl(file);
    return {
      id: crypto.randomUUID(),
      fileName: file.name,
      publicUrl: dataUrl,
      contentType: file.type || "application/octet-stream",
      localPreviewUrl: dataUrl,
    };
  }
}

export interface UploadConfig {
  baseUrl?: string;
  apiKey?: string;
  subModelId?: string;
}

export interface UploadBatchResult {
  uploaded: UploadedAsset[];
  failed: Array<{ fileName: string; message: string }>;
}

type AssetUploader = (file: File, config: UploadConfig) => Promise<UploadedAsset>;

export async function uploadReferenceBatch(
  files: File[],
  config: UploadConfig,
  uploader: AssetUploader = uploadAsset,
): Promise<UploadBatchResult> {
  const settled = await Promise.allSettled(files.map((file) => uploader(file, config)));
  return settled.reduce<UploadBatchResult>(
    (result, item, index) => {
      if (item.status === "fulfilled") {
        result.uploaded.push(item.value);
      } else {
        result.failed.push({
          fileName: files[index].name,
          message: item.reason instanceof Error ? item.reason.message : "上传失败",
        });
      }
      return result;
    },
    { uploaded: [], failed: [] },
  );
}
