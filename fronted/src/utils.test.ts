import { describe, expect, it } from "vitest";

import type { ModelDefinition, ModelSetting } from "./types";
import {
  findPromptBeforeMessage,
  getModelIdentifierError,
  pickPrimaryModel,
  renderMarkdownPreview,
  resolveModelName,
} from "./utils";
import type { ConversationMessage } from "./types";

const textModel: ModelDefinition = {
  id: "custom-text",
  name: "Custom Text",
  vendor: "Test",
  capability: "text",
  adapter: "text-chat",
  model: "gpt-4o",
  description: "Test model",
  builtin: false,
};

function setting(patch: Partial<ModelSetting>): ModelSetting {
  return {
    baseUrl: "https://token.example.com",
    apiKey: "test-key",
    modelNameOverride: "",
    availableModels: [],
    ...patch,
  };
}

describe("model selection helpers", () => {
  it("uses the saved primary model when generating requests", () => {
    expect(
      resolveModelName(
        textModel,
        setting({
          modelNameOverride: "gpt-4.1",
          availableModels: ["gpt-4o", "gpt-4.1"],
        }),
      ),
    ).toBe("gpt-4.1");
  });

  it("keeps a valid primary model and otherwise picks the first fetched model", () => {
    expect(pickPrimaryModel(["gpt-4o", "gpt-4.1"], "gpt-4.1")).toBe("gpt-4.1");
    expect(pickPrimaryModel(["gpt-4o", "gpt-4.1"], "missing-model")).toBe("gpt-4o");
    expect(pickPrimaryModel([], "manual-model")).toBe("manual-model");
  });

  it("rejects URL-shaped model identifiers before saving or testing", () => {
    expect(getModelIdentifierError("https://token.cylonai.cn")).toContain("baseURL");
    expect(getModelIdentifierError("gpt-4o")).toBe("");
  });
});

describe("conversation helpers", () => {
  it("renders markdown previews while escaping raw html", () => {
    const html = renderMarkdownPreview([
      "# 标题",
      "",
      "这是 **重点**",
      "",
      "- 第一项",
      "- 第二项",
      "",
      "```js",
      "console.log('<x>')",
      "```",
      "",
      "<script>alert(1)</script>",
    ].join("\n"));

    expect(html).toContain("<h1>标题</h1>");
    expect(html).toContain("<strong>重点</strong>");
    expect(html).toContain("<ul><li>第一项</li><li>第二项</li></ul>");
    expect(html).toContain("<pre><code>console.log(&#39;&lt;x&gt;&#39;)</code></pre>");
    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(html).not.toContain("<script>");
  });

  it("finds the nearest user prompt before a failed assistant message", () => {
    const messages = [
      message({ id: "m1", role: "user", content: "第一次" }),
      message({ id: "m2", role: "assistant", content: "成功" }),
      message({ id: "m3", role: "user", content: "第二次" }),
      message({ id: "m4", role: "assistant", status: "error", canRetry: true }),
    ];

    expect(findPromptBeforeMessage(messages, "m4")).toBe("第二次");
  });
});

function message(patch: Partial<ConversationMessage>): ConversationMessage {
  return {
    id: "",
    role: "assistant",
    capability: "text",
    content: "",
    status: "success",
    errorMessage: "",
    canRetry: false,
    modelGroupId: null,
    subModelId: null,
    assets: [],
    createdAt: "2026-01-01T00:00:00",
    ...patch,
  };
}
