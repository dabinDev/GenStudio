import type { ProxyConfigInput, UploadedAsset } from "@/lib/types";

interface ProxyErrorShape {
  error?: {
    message?: string;
  };
  message?: string;
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as ProxyErrorShape;
    return (
      payload.error?.message ||
      payload.message ||
      `请求失败，状态码 ${response.status}`
    );
  } catch {
    return `请求失败，状态码 ${response.status}`;
  }
}

export async function postProxy<T>(
  endpoint: string,
  body: Record<string, unknown>,
): Promise<T> {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  return (await response.json()) as T;
}

export async function postProxyWithRawError<T>(
  endpoint: string,
  body: Record<string, unknown>,
): Promise<T> {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  const payload = (await response.json()) as T & ProxyErrorShape;

  if (!response.ok) {
    throw Object.assign(
      new Error(
        payload.error?.message ||
          payload.message ||
          `请求失败，状态码 ${response.status}`,
      ),
      {
      payload,
      },
    );
  }

  return payload;
}

export async function uploadAsset(
  file: File,
  config: ProxyConfigInput,
): Promise<UploadedAsset> {
  const presign = await postProxy<{
    uploadUrl: string;
    method: string;
    publicUrl: string;
    objectKey: string;
    contentType: string;
  }>("/api/proxy/upload/presign", {
    config,
    fileName: file.name,
    contentType: file.type || "application/octet-stream",
  });

  const uploadResponse = await fetch(presign.uploadUrl, {
    method: presign.method || "PUT",
    headers: {
      "Content-Type": file.type || presign.contentType,
    },
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
