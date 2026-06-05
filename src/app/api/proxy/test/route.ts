import { NextRequest, NextResponse } from "next/server";

import {
  createAuthHeaders,
  jsonError,
  parseUpstream,
  pickErrorMessage,
  resolveUrl,
  validateConfig,
} from "@/lib/server/proxy";
import type { Adapter, Capability } from "@/lib/types";

function resolveTestPath(capability: Capability, adapter?: Adapter): string {
  if (capability === "text") {
    return "/v1/chat/completions";
  }

  if (capability === "image") {
    return "/v1/images/generations";
  }

  if (adapter === "video-seedance") {
    return "/v1/video/generations";
  }

  return "/v1/video/create";
}

function buildTestBody(
  capability: Capability,
  model: string,
  adapter?: Adapter,
): Record<string, unknown> {
  if (capability === "text") {
    return {
      model,
      messages: [
        {
          role: "user",
          content: "ping",
        },
      ],
      max_tokens: 8,
      stream: false,
    };
  }

  if (capability === "image") {
    return {
      model,
      prompt: "simple ping test image, plain geometric dot",
      n: 1,
      size: "512x512",
      response_format: "url",
    };
  }

  if (adapter === "video-seedance") {
    return {
      model,
      content: [
        {
          type: "text",
          text: "ping test, one second static shot",
        },
      ],
      metadata: {
        duration: 1,
        resolution: "540p",
        ratio: "16:9",
        generate_audio: false,
      },
    };
  }

  return {
    model,
    prompt: "ping test, one second static shot",
    aspect_ratio: "16:9",
    duration: 1,
    resolution: "540p",
    audio: false,
  };
}

export async function POST(request: NextRequest) {
  const payload = (await request.json()) as {
    config?: { baseUrl: string; apiKey: string };
    capability?: Capability;
    adapter?: Adapter;
    model?: string;
  };

  const configError = validateConfig(payload.config);

  if (configError) {
    return jsonError(configError);
  }

  if (!payload.capability) {
    return jsonError("缺少模型能力类型。");
  }

  if (!payload.model?.trim()) {
    return jsonError("缺少模型标识。");
  }

  const targetUrl = resolveUrl(
    payload.config!.baseUrl,
    resolveTestPath(payload.capability, payload.adapter),
  );
  const body = buildTestBody(
    payload.capability,
    payload.model.trim(),
    payload.adapter,
  );
  const startedAt = Date.now();
  const upstream = await fetch(targetUrl, {
    method: "POST",
    headers: {
      ...createAuthHeaders(payload.config!.apiKey),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  const durationMs = Date.now() - startedAt;
  const raw = await parseUpstream(upstream);

  if (!upstream.ok || typeof raw === "string") {
    return NextResponse.json(
      {
        ok: false,
        error: {
          message: pickErrorMessage(raw, "测试请求失败。"),
        },
        request: {
          url: targetUrl,
          body,
        },
        durationMs,
        raw,
      },
      { status: upstream.status || 500 },
    );
  }

  return NextResponse.json({
    ok: true,
    status: upstream.status,
    request: {
      url: targetUrl,
      body,
    },
    durationMs,
    raw,
  });
}
