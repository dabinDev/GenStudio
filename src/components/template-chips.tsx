"use client";

import type { PromptTemplate } from "@/lib/catalog";

interface TemplateChipsProps {
  templates: PromptTemplate[];
  onApply: (template: PromptTemplate) => void;
}

export function TemplateChips({ templates, onApply }: TemplateChipsProps) {
  return (
    <div className="template-row">
      {templates.map((template) => (
        <button
          key={template.id}
          type="button"
          className="chip-button"
          onClick={() => onApply(template)}
        >
          {template.label}
        </button>
      ))}
    </div>
  );
}
