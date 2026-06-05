import { NextRequest, NextResponse } from "next/server";

import {
  createAuthHeaders,
  jsonError,
  parseUpstream,
  pickErrorMessage,
  resolveUrl,
  validateConfig,
} from "@/lib/server/proxy";

function parseModelIds(raw: Record<string, unknown>): string[] {
  const data = Array.isArray(raw.data) ? raw.data : [];

  return data.flatMap((item) => {
    if (!item || typeof item !== "object") {
      return [];
    }

    const record = item as Record<string, unknown>;
    return typeof record.id === "string" ? [record.id] : [];
  });
}

export async function POST(request: NextRequest) {
  const payload = (await request.json()) as {
    config?: { baseUrl: string; apiKey: string };
  };

  const configError = validateConfig(payload.config);

  if (configError) {
    return jsonError(configError);
  }

  const targetUrl = resolveUrl(payload.config!.baseUrl, "/v1/models");
  const startedAt = Date.now();
  const upstream = await fetch(targetUrl, {
    method: "GET",
    headers: createAuthHeaders(payload.config!.apiKey),
  });
  const durationMs = Date.now() - startedAt;
  const raw = await parseUpstream(upstream);

  if (!upstream.ok || typeof raw === "string") {
    return NextResponse.json(
      {
        error: {
          message: pickErrorMessage(raw, "获取模型列表失败。"),
        },
        durationMs,
        raw,
      },
      { status: upstream.status || 500 },
    );
  }

  return NextResponse.json({
    models: parseModelIds(raw),
    durationMs,
    raw,
  });
}
