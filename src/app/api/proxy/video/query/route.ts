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

function resolveQueryPath(adapter: Adapter, taskId: string): string {
  if (adapter === "video-seedance") {
    return `/v1/video/generations/${taskId}`;
  }

  return `/v1/video/query?id=${encodeURIComponent(taskId)}`;
}

function normalizeVideoStatus(value: string): string {
  const lower = value.toLowerCase();

  if (
    lower.includes("success") ||
    lower.includes("complete") ||
    lower.includes("succeed")
  ) {
    return "completed";
  }

  if (lower.includes("fail") || lower.includes("error") || lower.includes("cancel")) {
    return "failed";
  }

  if (
    lower.includes("processing") ||
    lower.includes("progress") ||
    lower.includes("pending") ||
    lower.includes("queue")
  ) {
    return "processing";
  }

  return value;
}

export async function POST(request: NextRequest) {
  const payload = (await request.json()) as {
    config?: { baseUrl: string; apiKey: string };
    adapter?: Adapter;
    taskId?: string;
  };

  const configError = validateConfig(payload.config);

  if (configError) {
    return jsonError(configError);
  }

  if (!payload.adapter) {
    return jsonError("缺少视频适配器。");
  }

  if (!payload.taskId?.trim()) {
    return jsonError("缺少任务 ID。");
  }

  const targetUrl = resolveUrl(
    payload.config!.baseUrl,
    resolveQueryPath(payload.adapter, payload.taskId),
  );
  const upstream = await fetch(targetUrl, {
    method: "GET",
    headers: createAuthHeaders(payload.config!.apiKey),
  });

  const raw = await parseUpstream(upstream);

  if (!upstream.ok || typeof raw === "string") {
    return NextResponse.json(
      {
        error: {
          message: pickErrorMessage(raw, "任务查询失败。"),
        },
        raw,
      },
      { status: upstream.status || 500 },
    );
  }

  const seedanceData =
    raw.data && typeof raw.data === "object"
      ? (raw.data as Record<string, unknown>)
      : null;
  const nestedSeedanceData =
    seedanceData?.data && typeof seedanceData.data === "object"
      ? (seedanceData.data as Record<string, unknown>)
      : null;
  const seedanceContent =
    nestedSeedanceData?.content && typeof nestedSeedanceData.content === "object"
      ? (nestedSeedanceData.content as Record<string, unknown>)
      : null;

  const statusSource =
    typeof raw.status === "string"
      ? raw.status
      : typeof seedanceData?.status === "string"
        ? seedanceData.status
        : typeof nestedSeedanceData?.status === "string"
          ? nestedSeedanceData.status
          : "processing";

  const videoUrl =
    typeof raw.video_url === "string"
      ? raw.video_url
      : typeof seedanceContent?.video_url === "string"
        ? seedanceContent.video_url
        : null;

  const thumbnailUrl =
    typeof raw.thumbnail_url === "string" ? raw.thumbnail_url : null;

  const progress =
    typeof raw.progress === "number" || typeof raw.progress === "string"
      ? raw.progress
      : typeof seedanceData?.progress === "number" ||
          typeof seedanceData?.progress === "string"
        ? seedanceData.progress
        : null;

  return NextResponse.json({
    taskId:
      (typeof raw.id === "string" ? raw.id : undefined) ||
      (typeof seedanceData?.task_id === "string" ? seedanceData.task_id : undefined) ||
      payload.taskId,
    status: normalizeVideoStatus(statusSource),
    progress,
    videoUrl,
    thumbnailUrl,
    raw,
  });
}
