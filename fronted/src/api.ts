import type { ConversationDefinition, ServerModelDefinition, UploadedAsset, UserProfile } from "./types";

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

async function requestJson<T>(endpoint: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(endpoint, {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });

  if (!response.ok) {
    const parsed = await parseErrorPayload(response);
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

export async function devLogin(): Promise<UserProfile> {
  const payload = await postApi<{ user: UserProfile }>("/api/auth/dev-login", {});
  return payload.user;
}

export async function fetchServerModels(): Promise<ServerModelDefinition[]> {
  const payload = await getApi<{ models: ServerModelDefinition[] }>("/api/models");
  return payload.models;
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

export async function setServerPrimaryModel(modelId: string, subModelId: string): Promise<ServerModelDefinition> {
  const payload = await postApi<{ model: ServerModelDefinition }>(`/api/models/${modelId}/primary`, { subModelId });
  return payload.model;
}

export async function uploadAsset(
  file: File,
  config: { baseUrl?: string; apiKey?: string; subModelId?: string },
): Promise<UploadedAsset> {
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
}
