import type {
  AdminAuditLog,
  AdminCreationRecord,
  AdminOverview,
  AdminOverviewModelRow,
  AdminOverviewUserRow,
  AdminUserDefinition,
  CatalogModelDefinition,
  Capability,
  ConversationDefinition,
  PromptTemplateDefinition,
  ServerModelDefinition,
  UploadedAsset,
  UserProfile,
} from "./types";
import { isProductionRuntime } from "./env";

const CSRF_SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const AUTH_CSRF_EXEMPT_ENDPOINTS = new Set(["/api/auth/login", "/api/auth/register", "/api/auth/dev-login"]);

let csrfToken = "";

interface ProxyErrorShape {
  detail?: {
    message?: string;
    [key: string]: unknown;
  };
  error?: {
    message?: string;
  };
  message?: string;
}

export class ApiRequestError extends Error {
  detail: ProxyErrorShape["detail"] | null;
  status: number;

  constructor(message: string, status: number, detail: ProxyErrorShape["detail"] | null = null) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.detail = detail;
  }
}

async function parseErrorPayload(response: Response): Promise<{ message: string; detail: ProxyErrorShape["detail"] | null }> {
  try {
    const payload = (await response.json()) as ProxyErrorShape;
    const message = (
      payload.detail?.message ||
      payload.error?.message ||
      payload.message ||
      `请求失败，状态码 ${response.status}`
    );
    return { message, detail: payload.detail || null };
  } catch {
    return { message: `请求失败，状态码 ${response.status}`, detail: null };
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

export async function updateMyProfile(body: { nickname?: string; phone?: string; avatarUrl?: string }): Promise<UserProfile> {
  const payload = await putApi<{ user: UserProfile }>("/api/users/me", body);
  return payload.user;
}

export async function fetchServerModels(): Promise<ServerModelDefinition[]> {
  const payload = await getApi<{ models: ServerModelDefinition[] }>("/api/models");
  return payload.models;
}

export async function fetchAdminOverview(): Promise<AdminOverview> {
  return getApi<AdminOverview>("/api/admin/overview");
}

export async function fetchAdminOverviewUsers(): Promise<AdminOverviewUserRow[]> {
  const payload = await getApi<{ users: AdminOverviewUserRow[] }>("/api/admin/overview/users");
  return payload.users;
}

export async function fetchAdminOverviewModels(): Promise<AdminOverviewModelRow[]> {
  const payload = await getApi<{ models: AdminOverviewModelRow[] }>("/api/admin/overview/models");
  return payload.models;
}

export async function fetchAdminModels(query: { capability?: string; search?: string; publicState?: string } = {}): Promise<ServerModelDefinition[]> {
  const params = new URLSearchParams();
  if (query.capability) params.set("capability", query.capability);
  if (query.search) params.set("search", query.search);
  if (query.publicState) params.set("publicState", query.publicState);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const payload = await getApi<{ models: ServerModelDefinition[] }>(`/api/admin/models${suffix}`);
  return payload.models;
}

export async function updateAdminModel(modelId: string, body: Record<string, unknown>): Promise<ServerModelDefinition> {
  const payload = await putApi<{ model: ServerModelDefinition }>(`/api/admin/models/${modelId}`, body);
  return payload.model;
}

export async function publishAdminModel(modelId: string): Promise<ServerModelDefinition> {
  const payload = await postApi<{ model: ServerModelDefinition }>(`/api/admin/models/${modelId}/publish`, {});
  return payload.model;
}

export async function unpublishAdminModel(modelId: string): Promise<ServerModelDefinition> {
  const payload = await postApi<{ model: ServerModelDefinition }>(`/api/admin/models/${modelId}/unpublish`, {});
  return payload.model;
}

export async function fetchPromptTemplates(capability?: Capability | "all"): Promise<PromptTemplateDefinition[]> {
  const suffix = capability ? `?capability=${encodeURIComponent(capability)}` : "";
  const payload = await getApi<{ templates: PromptTemplateDefinition[] }>(`/api/admin/prompt-templates${suffix}`);
  return payload.templates;
}

export async function savePromptTemplate(templateId: string, body: Record<string, unknown>): Promise<PromptTemplateDefinition> {
  const payload = await putApi<{ template: PromptTemplateDefinition }>(`/api/admin/prompt-templates/${templateId}`, body);
  return payload.template;
}

export async function testPromptTemplate(body: Record<string, unknown>): Promise<{ prompt: string }> {
  return postApi<{ prompt: string }>("/api/admin/prompt-templates/test", body);
}

export async function fetchAdminUsers(search = ""): Promise<AdminUserDefinition[]> {
  const suffix = search.trim() ? `?search=${encodeURIComponent(search.trim())}` : "";
  const payload = await getApi<{ users: AdminUserDefinition[] }>(`/api/admin/users${suffix}`);
  return payload.users;
}

export async function updateAdminUser(userId: string, body: Record<string, unknown>): Promise<AdminUserDefinition> {
  const payload = await putApi<{ user: AdminUserDefinition }>(`/api/admin/users/${userId}`, body);
  return payload.user;
}

export async function enableAdminUser(userId: string): Promise<AdminUserDefinition> {
  const payload = await postApi<{ user: AdminUserDefinition }>(`/api/admin/users/${userId}/enable`, {});
  return payload.user;
}

export async function disableAdminUser(userId: string): Promise<AdminUserDefinition> {
  const payload = await postApi<{ user: AdminUserDefinition }>(`/api/admin/users/${userId}/disable`, {});
  return payload.user;
}

export async function deleteAdminUser(userId: string): Promise<AdminUserDefinition> {
  const payload = await postApi<{ user: AdminUserDefinition }>(`/api/admin/users/${userId}/delete`, {});
  return payload.user;
}

export async function restoreAdminUser(userId: string): Promise<AdminUserDefinition> {
  const payload = await postApi<{ user: AdminUserDefinition }>(`/api/admin/users/${userId}/restore`, {});
  return payload.user;
}

export async function fetchAdminRecords(
  capability: Capability,
  query: {
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
  } = {},
): Promise<AdminCreationRecord[]> {
  const endpoint = capability === "text" ? "text" : capability === "image" ? "images" : "videos";
  const params = new URLSearchParams();
  if (query.userId) params.set("userId", query.userId);
  if (query.userSearch) params.set("userSearch", query.userSearch);
  if (query.modelGroupId) params.set("modelGroupId", query.modelGroupId);
  if (query.status) params.set("status", query.status);
  if (query.keyword) params.set("keyword", query.keyword);
  if (query.size) params.set("size", query.size);
  if (query.ratio) params.set("ratio", query.ratio);
  if (query.refCount) params.set("refCount", query.refCount);
  if (query.duration) params.set("duration", query.duration);
  if (query.resolution) params.set("resolution", query.resolution);
  if (query.mode) params.set("mode", query.mode);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const payload = await getApi<{ records: AdminCreationRecord[] }>(`/api/admin/records/${endpoint}${suffix}`);
  return payload.records;
}

export async function fetchAdminAuditLogs(query: { action?: string; adminUserId?: string; targetType?: string; targetId?: string; risk?: string } = {}): Promise<AdminAuditLog[]> {
  const params = new URLSearchParams();
  if (query.action) params.set("action", query.action);
  if (query.adminUserId) params.set("adminUserId", query.adminUserId);
  if (query.targetType) params.set("targetType", query.targetType);
  if (query.targetId) params.set("targetId", query.targetId);
  if (query.risk) params.set("risk", query.risk);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const payload = await getApi<{ logs: AdminAuditLog[] }>(`/api/admin/audit-logs${suffix}`);
  return payload.logs;
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
  config: { baseUrl?: string; apiKey?: string; subModelId?: string },
): Promise<UploadedAsset> {
  try {
    const presign = await postProxy<{
      uploadUrl: string;
      method: string;
      publicUrl: string;
      objectKey: string;
      contentType: string;
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
