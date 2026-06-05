import { NextRequest, NextResponse } from "next/server";

import {
  createAuthHeaders,
  jsonError,
  parseUpstream,
  pickErrorMessage,
  resolveUrl,
  validateConfig,
} from "@/lib/server/proxy";
import type { Adapter } from "@/lib/types";

function resolveCreatePath(adapter: Adapter): string {
  if (adapter === "video-seedance") {
    return "/v1/video/generations";
  }

  return "/v1/video/create";
}

function pickTaskId(raw: Record<string, unknown>): string {
  if (typeof raw.task_id === "string") {
    return raw.task_id;
  }

  if (typeof raw.id === "string") {
    return raw.id;
  }

  return "";
}

export async function POST(request: NextRequest) {
  const payload = (await request.json()) as {
    config?: { baseUrl: string; apiKey: string };
    adapter?: Adapter;
    requestBody?: Record<string, unknown>;
  };

  const configError = validateConfig(payload.config);

  if (configError) {
    return jsonError(configError);
  }

  if (!payload.adapter) {
    return jsonError("缺少视频适配器。");
  }

  const targetUrl = resolveUrl(
    payload.config!.baseUrl,
    resolveCreatePath(payload.adapter),
  );
  const upstream = await fetch(targetUrl, {
    method: "POST",
    headers: {
      ...createAuthHeaders(payload.config!.apiKey),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload.requestBody || {}),
  });

  const raw = await parseUpstream(upstream);

  if (!upstream.ok || typeof raw === "string") {
    return NextResponse.json(
      {
        error: {
          message: pickErrorMessage(raw, "视频任务提交失败。"),
        },
        raw,
      },
      { status: upstream.status || 500 },
    );
  }

  return NextResponse.json({
    taskId: pickTaskId(raw),
    status:
      typeof raw.status === "string"
        ? raw.status
        : typeof raw.code === "string"
          ? raw.code
          : "submitted",
    raw,
  });
}
