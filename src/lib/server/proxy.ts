import { NextResponse } from "next/server";

import type { ProxyConfigInput } from "@/lib/types";

export function validateConfig(config?: ProxyConfigInput): string | null {
  if (!config?.baseUrl?.trim()) {
    return "缺少 baseURL。";
  }

  if (!config?.apiKey?.trim()) {
    return "缺少 API Key。";
  }

  return null;
}

export function jsonError(message: string, status = 400): NextResponse {
  return NextResponse.json(
    {
      error: {
        message,
      },
    },
    { status },
  );
}

export function resolveUrl(baseUrl: string, path: string): string {
  const url = new URL(baseUrl);
  const basePath =
    url.pathname && url.pathname !== "/"
      ? url.pathname.replace(/\/+$/, "")
      : "";
  let targetPath = path.startsWith("/") ? path : `/${path}`;

  if (basePath && targetPath.startsWith(`${basePath}/`)) {
    targetPath = targetPath.slice(basePath.length);
  } else if (basePath && targetPath === basePath) {
    targetPath = "/";
  }

  url.pathname = `${basePath}${targetPath}`.replace(/\/{2,}/g, "/");
  url.search = "";
  url.hash = "";

  return url.toString();
}

export async function parseUpstream(
  response: Response,
): Promise<Record<string, unknown> | string> {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    return (await response.json()) as Record<string, unknown>;
  }

  return await response.text();
}

export function createAuthHeaders(apiKey: string): HeadersInit {
  return {
    Authorization: `Bearer ${apiKey}`,
    Accept: "application/json",
  };
}

export function pickErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") {
    return fallback;
  }

  const objectPayload = payload as Record<string, unknown>;
  const errorValue = objectPayload.error;

  if (typeof errorValue === "string") {
    return errorValue;
  }

  if (errorValue && typeof errorValue === "object") {
    const nested = errorValue as Record<string, unknown>;

    if (typeof nested.message === "string") {
      return nested.message;
    }
  }

  if (typeof objectPayload.message === "string") {
    return objectPayload.message;
  }

  return fallback;
}
