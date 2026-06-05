import type { ModelDefinition, ModelSetting } from "@/lib/types";

export function safeJsonParse<T>(value: string, fallback: T): T {
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

export function resolveModelName(
  model: ModelDefinition,
  setting?: ModelSetting,
): string {
  return setting?.modelNameOverride?.trim() || model.model;
}

export function combinePrompt(keywords: string, prompt: string): string {
  const pieces = [
    keywords.trim() ? `关键词：${keywords.trim()}` : "",
    prompt.trim(),
  ].filter(Boolean);

  return pieces.join("\n");
}

export function formatTime(value: number): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(value);
}

export function shortText(value: string, max = 100): string {
  if (value.length <= max) {
    return value;
  }

  return `${value.slice(0, max)}...`;
}

export function createLocalId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

export function parseJsonInput(
  value: string,
): { ok: true; data: Record<string, unknown> } | { ok: false; message: string } {
  const trimmed = value.trim();

  if (!trimmed) {
    return { ok: true, data: {} };
  }

  try {
    const parsed = JSON.parse(trimmed) as unknown;

    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      return { ok: false, message: "高级参数必须是 JSON 对象。" };
    }

    return { ok: true, data: parsed as Record<string, unknown> };
  } catch {
    return { ok: false, message: "高级参数 JSON 格式不合法。" };
  }
}
