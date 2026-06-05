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

  const targetUrl = resolveUrl(payload.config!.baseUrl, "/v1/chat/completions");
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
          message: pickErrorMessage(raw, "文案请求失败。"),
        },
        raw,
      },
      { status: upstream.status || 500 },
    );
  }

  return NextResponse.json({
    content:
      (raw.choices as Array<Record<string, unknown>> | undefined)?.[0]?.message &&
      typeof (
        (raw.choices as Array<Record<string, unknown>>)[0].message as Record<
          string,
          unknown
        >
      ).content === "string"
        ? (
            (raw.choices as Array<Record<string, unknown>>)[0].message as Record<
              string,
              unknown
            >
          ).content
        : "",
    usage: raw.usage,
    raw,
  });
}
