import type { ModelDefinition, ModelSetting } from "./types";

export function createLocalId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

export function safeJsonParse<T>(value: string | null, fallback: T): T {
  if (!value) return fallback;
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

export function combinePrompt(keywords: string, prompt: string): string {
  const chunks = [];
  if (keywords.trim()) chunks.push(`关键词：${keywords.trim()}`);
  if (prompt.trim()) chunks.push(prompt.trim());
  return chunks.join("\n\n");
}

export function resolveModelName(model: ModelDefinition, setting?: ModelSetting): string {
  return setting?.modelNameOverride?.trim() || model.model;
}

export function shortText(value: string, max = 72): string {
  const text = value.replace(/\s+/g, " ").trim();
  return text.length > max ? `${text.slice(0, max)}...` : text;
}
