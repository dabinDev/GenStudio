// 管理后台通用 JSON 工具：格式化展示 + 安全解析为对象。
// 提炼自 AuditLogsView / RecordsView 重复的 JSON.stringify，以及 modelCenterState 的 parseDefaultParameters。

export function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value ?? '');
  }
}

export interface JsonObjectParseResult {
  ok: boolean;
  value: Record<string, unknown>;
  error: string;
}

// 解析文本为 JSON 对象。区分“语法错误”和“合法 JSON 但不是对象”两种情况，返回可读的中文错误。
export function parseJsonObject(text: string): JsonObjectParseResult {
  const clean = text.trim();
  if (!clean) {
    return { ok: true, value: {}, error: '' };
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(clean);
  } catch {
    return { ok: false, value: {}, error: 'JSON 语法有误，请检查括号、逗号和引号是否配对。' };
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return { ok: false, value: {}, error: '内容必须是 JSON 对象（以 { 开头、} 结尾）。' };
  }
  return { ok: true, value: parsed as Record<string, unknown>, error: '' };
}
