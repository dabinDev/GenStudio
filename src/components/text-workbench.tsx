"use client";

import Link from "next/link";
import { Bell, CircleDollarSign, Settings, WandSparkles } from "lucide-react";
import { useMemo, useState } from "react";

import { IconText } from "@/components/icon";
import { JsonViewer } from "@/components/json-viewer";
import { ModelSpotlight } from "@/components/model-spotlight";
import { RecentHistory } from "@/components/recent-history";
import { TemplateChips } from "@/components/template-chips";
import { useWorkbenchStore } from "@/components/workbench-provider";
import { TEXT_TEMPLATES } from "@/lib/catalog";
import { postProxy } from "@/lib/client-proxy";
import { combinePrompt, createLocalId, parseJsonInput, resolveModelName, shortText } from "@/lib/utils";
import type { ModelDefinition } from "@/lib/types";

interface TextResult {
  content: string;
  usage?: Record<string, unknown>;
  raw: Record<string, unknown>;
}

function chooseInitialModel(models: ModelDefinition[]): string {
  return models[0]?.id || "";
}

export function TextWorkbench() {
  const { getModelsByCapability, modelSettings, addHistory } = useWorkbenchStore();
  const models = getModelsByCapability("text");
  const [selectedModelId, setSelectedModelId] = useState(() =>
    chooseInitialModel(models),
  );
  const [keywords, setKeywords] = useState("");
  const [systemPrompt, setSystemPrompt] = useState(
    "你是一个擅长创意表达、结构整理和提示词优化的专业创作助手。",
  );
  const [prompt, setPrompt] = useState("");
  const [temperature, setTemperature] = useState("0.8");
  const [maxTokens, setMaxTokens] = useState("1200");
  const [extraJson, setExtraJson] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<TextResult | null>(null);

  const activeModelId = models.some((item) => item.id === selectedModelId)
    ? selectedModelId
    : chooseInitialModel(models);

  const selectedModel = useMemo(
    () => models.find((item) => item.id === activeModelId) || null,
    [activeModelId, models],
  );

  const setting = selectedModel ? modelSettings[selectedModel.id] : undefined;
  const missingConfig = !setting?.baseUrl?.trim() || !setting?.apiKey?.trim();

  async function handleSubmit() {
    if (!selectedModel) {
      return;
    }

    const finalPrompt = combinePrompt(keywords, prompt);

    if (!finalPrompt.trim()) {
      setError("请先输入文案需求。");
      return;
    }

    const parsedExtra = parseJsonInput(extraJson);

    if (!parsedExtra.ok) {
      setError(parsedExtra.message);
      return;
    }

    if (missingConfig || !setting) {
      setError("当前模型尚未配置 baseURL 或 API Key。");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await postProxy<TextResult>("/api/proxy/text", {
        config: {
          baseUrl: setting.baseUrl,
          apiKey: setting.apiKey,
        },
        model: resolveModelName(selectedModel, setting),
        requestBody: {
          messages: [
            systemPrompt.trim()
              ? {
                  role: "system",
                  content: systemPrompt.trim(),
                }
              : null,
            {
              role: "user",
              content: finalPrompt,
            },
          ].filter(Boolean),
          stream: false,
          temperature: temperature ? Number(temperature) : undefined,
          max_tokens: maxTokens ? Number(maxTokens) : undefined,
          ...parsedExtra.data,
        },
      });

      setResult(response);
      addHistory({
        id: createLocalId("history"),
        capability: "text",
        modelId: selectedModel.id,
        modelName: selectedModel.name,
        title: "文案创作",
        status: "success",
        createdAt: Date.now(),
        summary: shortText(response.content || "已返回响应"),
      });
    } catch (submitError) {
      const message =
        submitError instanceof Error ? submitError.message : "文案生成失败。";
      setError(message);
      addHistory({
        id: createLocalId("history"),
        capability: "text",
        modelId: selectedModel.id,
        modelName: selectedModel.name,
        title: "文案创作",
        status: "error",
        createdAt: Date.now(),
        summary: shortText(message),
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <div className="workspace-topbar">
        <div className="workspace-topbar-actions">
          <button type="button">+ 新建对话</button>
          <button type="button" className="button-secondary">
            历史记录
          </button>
        </div>
        <div className="workspace-topbar-actions">
          <Link href="/settings" className="topbar-icon-button" title="账户">
            <CircleDollarSign aria-hidden="true" size={18} strokeWidth={2} />
          </Link>
          <button type="button" className="topbar-icon-button" title="通知">
            <Bell aria-hidden="true" size={18} strokeWidth={2} />
          </button>
          <Link href="/settings" className="topbar-icon-button" title="设置">
            <Settings aria-hidden="true" size={18} strokeWidth={2} />
          </Link>
        </div>
      </div>

      <div className="studio-grid">
        <section className="studio-panel">
          <ModelSpotlight
            models={models}
            selectedModelId={selectedModelId}
            selectedModel={selectedModel}
            setting={setting}
            onChange={setSelectedModelId}
          />

          <div className="studio-canvas">
            {result ? (
              <article className="result-text studio-result">{result.content}</article>
            ) : (
              <div className="empty-canvas">
                <div className="empty-canvas-card">
                  <div className="hero-model-mark">
                    <WandSparkles aria-hidden="true" size={28} strokeWidth={2} />
                  </div>
                  <div className="empty-canvas-top">
                    <span className="badge badge-accent">文案创作</span>
                    <span>{selectedModel?.name || "未选择模型"}</span>
                  </div>
                  <h3>{selectedModel?.name || "文案创作模型"}</h3>
                  <p className="muted">
                    从一句关键词开始，扩成可直接使用的创意文案、分镜脚本或提示词。
                  </p>
                  <div className="canvas-hints">
                    <span>品牌短句</span>
                    <span>视频脚本</span>
                    <span>图片提示词</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="composer-card">
            <div className="composer-topline">
              <button type="button" className="gameplay-btn">玩法说明</button>
              <span>{missingConfig ? "模型待配置" : "模型已就绪"}</span>
            </div>

            <div className="composer-toolbar">
              <TemplateChips
                templates={TEXT_TEMPLATES}
                onApply={(template) =>
                  setPrompt((current) =>
                    current.trim()
                      ? `${current.trim()}\n\n${template.prompt}`
                      : template.prompt,
                  )
                }
              />
            </div>

            <div className="composer-surface">
              <textarea
                className="composer-input"
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="输入你想生成的文案、脚本、提示词或结构化内容..."
              />

              <div className="composer-footer-bar">
                <div className="composer-quick-fields">
                  <label className="composer-keyword-compact">
                    <span>关键词</span>
                    <input
                      value={keywords}
                      onChange={(event) => setKeywords(event.target.value)}
                      placeholder="夏日果茶、第一人称广告、年轻化"
                    />
                  </label>
              <label>
                <span>温度</span>
                <input
                  value={temperature}
                  onChange={(event) => setTemperature(event.target.value)}
                  placeholder="0.8"
                />
              </label>
              <label>
                <span>最大 Token</span>
                <input
                  value={maxTokens}
                  onChange={(event) => setMaxTokens(event.target.value)}
                  placeholder="1200"
                />
              </label>
                </div>
                <button
                  type="button"
                  className="composer-submit-button"
                  onClick={handleSubmit}
                  disabled={loading}
                  title={loading ? "生成中..." : "发送创作"}
                >
                  <IconText icon={WandSparkles}>
                    {loading ? "生成中..." : "发送创作"}
                  </IconText>
                </button>
              </div>
            </div>

            <details className="composer-details">
              <summary>系统提示词与高级 JSON</summary>
              <label className="field field-full">
                <span>系统提示词</span>
                <textarea
                  value={systemPrompt}
                  onChange={(event) => setSystemPrompt(event.target.value)}
                  placeholder="指定创作身份与输出规则"
                />
              </label>
              <label className="field field-full">
                <span>高级参数 JSON</span>
                <textarea
                  value={extraJson}
                  onChange={(event) => setExtraJson(event.target.value)}
                  placeholder='例如：{"response_format":{"type":"json_object"}}'
                />
              </label>
            </details>

            {error ? <div className="inline-message inline-danger">{error}</div> : null}
          </div>
        </section>

        <aside className="aside-column studio-aside">
          <div className="panel">
            <h3>调试响应</h3>
            {result ? (
              <>
                {result.usage ? <JsonViewer title="Token 用量" value={result.usage} /> : null}
                <JsonViewer title="原始响应" value={result.raw} />
              </>
            ) : (
              <p className="muted">提交请求后，这里展示 Token 用量与原始返回。</p>
            )}
          </div>

          <RecentHistory capability="text" />
        </aside>
      </div>
    </>
  );
}
