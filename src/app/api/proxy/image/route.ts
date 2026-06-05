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
    model?: string;
    requestBody?: Record<string, unknown>;
  };

  const configError = validateConfig(payload.config);

  if (configError) {
    return jsonError(configError);
  }

  if (!payload.model?.trim()) {
    return jsonError("缺少模型标识。");
  }

  const targetUrl = resolveUrl(payload.config!.baseUrl, "/v1/images/generations");
  const upstream = await fetch(targetUrl, {
    method: "POST",
    headers: {
      ...createAuthHeaders(payload.config!.apiKey),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: payload.model,
      ...payload.requestBody,
    }),
  });

  const raw = await parseUpstream(upstream);

  if (!upstream.ok || typeof raw === "string") {
    return NextResponse.json(
      {
        error: {
          message: pickErrorMessage(raw, "图片请求失败。"),
        },
        raw,
      },
      { status: upstream.status || 500 },
    );
  }

  const images = Array.isArray(raw.data)
    ? raw.data.flatMap((item) => {
        if (!item || typeof item !== "object") {
          return [];
        }

        const record = item as Record<string, unknown>;
        const src =
          typeof record.url === "string"
            ? record.url
            : typeof record.b64_json === "string"
              ? `data:image/png;base64,${record.b64_json}`
              : "";

        if (!src) {
          return [];
        }

        return [
          {
            src,
            revisedPrompt:
              typeof record.revised_prompt === "string"
                ? record.revised_prompt
                : undefined,
          },
        ];
      })
    : [];

  return NextResponse.json({
    images,
    raw,
  });
}
