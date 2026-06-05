import { NextRequest, NextResponse } from "next/server";

import {
  createAuthHeaders,
  jsonError,
  parseUpstream,
  pickErrorMessage,
  resolveUrl,
  validateConfig,
} from "@/lib/server/proxy";

export async function POST(request: NextRequest) {
  const payload = (await request.json()) as {
    config?: { baseUrl: string; apiKey: string };
    fileName?: string;
    contentType?: string;
  };

  const configError = validateConfig(payload.config);

  if (configError) {
    return jsonError(configError);
  }

  const targetUrl = resolveUrl(payload.config!.baseUrl, "/api/upload/presign");
  const upstream = await fetch(targetUrl, {
    method: "POST",
    headers: {
      ...createAuthHeaders(payload.config!.apiKey),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      file_name: payload.fileName || "upload.bin",
      content_type: payload.contentType || "application/octet-stream",
      expires_in: 900,
    }),
  });

  const raw = await parseUpstream(upstream);

  if (!upstream.ok || typeof raw === "string") {
    return NextResponse.json(
      {
        error: {
          message: pickErrorMessage(raw, "获取上传地址失败。"),
        },
        raw,
      },
      { status: upstream.status || 500 },
    );
  }

  if (!raw.success || !raw.data || typeof raw.data !== "object") {
    return NextResponse.json(
      {
        error: {
          message: pickErrorMessage(raw, "上传服务未正确返回预签名地址。"),
        },
        raw,
      },
      { status: 500 },
    );
  }

  const data = raw.data as Record<string, unknown>;

  return NextResponse.json({
    uploadUrl: typeof data.upload_url === "string" ? data.upload_url : "",
    method: typeof data.method === "string" ? data.method : "PUT",
    publicUrl: typeof data.public_url === "string" ? data.public_url : "",
    objectKey: typeof data.object_key === "string" ? data.object_key : "",
    contentType:
      typeof data.content_type === "string"
        ? data.content_type
        : payload.contentType || "application/octet-stream",
  });
}
