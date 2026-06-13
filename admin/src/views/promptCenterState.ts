import { reactive } from 'vue';

import type { Capability, PromptTemplate, PromptTemplateUpdatePayload } from '@/types';

export interface PromptTemplateForm {
  name: string;
  capability: Capability;
  modelGroupId: string;
  templateType: string;
  content: string;
  enabled: boolean;
}

export function createPromptTemplateForm(template: PromptTemplate): PromptTemplateForm {
  return reactive({
    name: template.name || '',
    capability: template.capability || 'text',
    modelGroupId: template.modelGroupId || '',
    templateType: template.templateType || 'prompt_optimize',
    content: template.content || '',
    enabled: Boolean(template.enabled),
  });
}

export function syncPromptTemplateForm(form: PromptTemplateForm, template: PromptTemplate): void {
  form.name = template.name || '';
  form.capability = template.capability || 'text';
  form.modelGroupId = template.modelGroupId || '';
  form.templateType = template.templateType || 'prompt_optimize';
  form.content = template.content || '';
  form.enabled = Boolean(template.enabled);
}

export function buildPromptTemplateSavePayload(
  template: PromptTemplate,
  form: PromptTemplateForm,
): PromptTemplateUpdatePayload {
  return {
    capability: template.capability,
    modelGroupId: template.modelGroupId || '',
    templateType: template.templateType || 'prompt_optimize',
    name: form.name,
    content: form.content,
    enabled: form.enabled,
  };
}

export function buildPromptTemplateTestSamples(value: string): string[] {
  const seen = new Set<string>();
  const samples: string[] = [];
  for (const line of value.replace(/\\n/g, '\n').split(/\r?\n/)) {
    const sample = line.trim();
    if (!sample || seen.has(sample)) {
      continue;
    }
    seen.add(sample);
    samples.push(sample);
  }
  return samples;
}
