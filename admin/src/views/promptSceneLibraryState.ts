import type { PromptSceneTemplate, PromptSceneTemplateUpdatePayload } from '@/types';

export interface PromptSceneTemplateForm {
  title: string;
  promptText: string;
  tagsText: string;
  categoryId: string;
  category: string;
  subcategory: string;
  weight: number;
  enabled: boolean;
}

export function parseYuquePromptLibrarySource(source: string): Record<string, unknown> {
  const clean = source.trim();
  if (!clean) {
    throw new Error('文件内容为空。');
  }
  if (clean.startsWith('{')) {
    return JSON.parse(clean) as Record<string, unknown>;
  }

  const assignmentIndex = clean.indexOf('=');
  if (assignmentIndex < 0) {
    throw new Error('未找到 Yuque 提示词索引对象。');
  }
  let objectSource = clean.slice(assignmentIndex + 1).trim();
  objectSource = objectSource
    .replace(/;\s*export\s+default\s+[\w$]+;\s*$/s, '')
    .replace(/;\s*$/s, '')
    .trim();
  return JSON.parse(objectSource) as Record<string, unknown>;
}

export function createPromptSceneTemplateForm(template?: PromptSceneTemplate | null): PromptSceneTemplateForm {
  return {
    title: template?.title || '',
    promptText: template?.promptText || '',
    tagsText: (template?.tags || []).join('，'),
    categoryId: template?.categoryId || '',
    category: template?.category || '',
    subcategory: template?.subcategory || '',
    weight: template?.weight || 0,
    enabled: template?.enabled ?? true,
  };
}

export function buildPromptSceneTemplateUpdatePayload(
  form: PromptSceneTemplateForm,
): PromptSceneTemplateUpdatePayload {
  return {
    title: form.title.trim(),
    promptText: form.promptText.trim(),
    tags: form.tagsText
      .split(/[,，、\s]+/)
      .map((item) => item.trim())
      .filter(Boolean),
    categoryId: form.categoryId.trim(),
    category: form.category.trim(),
    subcategory: form.subcategory.trim(),
    weight: Math.max(0, Number(form.weight) || 0),
    enabled: form.enabled,
  };
}
