"use client";

/* eslint-disable @next/next/no-img-element */

import Link from "next/link";
import {
  Bell,
  CircleDollarSign,
  ImagePlus,
  Settings,
  Trash2,
  Upload,
  WandSparkles,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { IconText } from "@/components/icon";
import { JsonViewer } from "@/components/json-viewer";
import { ModelSpotlight } from "@/components/model-spotlight";
import { RecentHistory } from "@/components/recent-history";
import { TemplateChips } from "@/components/template-chips";
import { useWorkbenchStore } from "@/components/workbench-provider";
import { IMAGE_TEMPLATES } from "@/lib/catalog";
import { postProxy, uploadAsset } from "@/lib/client-proxy";
import { combinePrompt, createLocalId, parseJsonInput, resolveModelName, shortText } from "@/lib/utils";
import type { ModelDefinition, UploadedAsset } from "@/lib/types";

interface ImageResult {
  images: Array<{
    src: string;
    revisedPrompt?: string;
  }>;
  raw: Record<string, unknown>;
}

function chooseInitialModel(models: ModelDefinition[]): string {
  return models[0]?.id || "";
}

export function ImageWorkbench() {
  const { getModelsByCapability, modelSettings, addHistory } = useWorkbenchStore();
  const models = getModelsByCapability("image");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedModelId, setSelectedModelId] = useState(() =>
    chooseInitialModel(models),
  );
  const [keywords, setKeywords] = useState("");
  const [prompt, setPrompt] = useState("");
  const [size, setSize] = useState("1024x1024");
  const [ratio, setRatio] = useState("16:9");
  const [resolution, setResolution] = useState("2k");
  const [quality, setQuality] = useState("auto");
  const [count, setCount] = useState("1");
  const [extraJson, setExtraJson] = useState("");
  const [references, setReferences] = useState<UploadedAsset[]>([]);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ImageResult | null>(null);

  const activeModelId = models.some((item) => item.id === selectedModelId)
    ? selectedModelId
    : chooseInitialModel(models);

  const selectedModel = useMemo(
    () => models.find((item) => item.id === activeModelId) || null,
    [activeModelId, models],
  );

  const setting = selectedModel ? modelSettings[selectedModel.id] : undefined;
  const missingConfig = !setting?.baseUrl?.trim() || !setting?.apiKey?.trim();

  async function handleUpload(files: FileList | null) {
    if (!files?.length || !setting || !selectedModel) {
      return;
    }

    setUploading(true);
    setError("");

    try {
      const uploaded = await Promise.all(
        Array.from(files).map((file) =>
          uploadAsset(file, {
            baseUrl: setting.baseUrl,
            apiKey: setting.apiKey,
          }),
        ),
      );

      setReferences((current) => [...current, ...uploaded]);
    } catch (uploadError) {
      setError(
        uploadError instanceof Error ? uploadError.message : "上传参考图失败。",
      );
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  async function handleSubmit() {
    if (!selectedModel || !setting) {
      return;
    }

    const finalPrompt = combinePrompt(keywords, prompt);

    if (!finalPrompt.trim()) {
      setError("请先输入图片需求。");
      return;
    }

    const parsedExtra = parseJsonInput(extraJson);

    if (!parsedExtra.ok) {
      setError(parsedExtra.message);
      return;
    }

    if (missingConfig) {
      setError("当前模型尚未配置 baseURL 或 API Key。");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await postProxy<ImageResult>("/api/proxy/image", {
        config: {
          baseUrl: setting.baseUrl,
          apiKey: setting.apiKey,
        },
        model: resolveModelName(selectedModel, setting),
        requestBody: {
          prompt: finalPrompt,
          n: Number(count) || 1,
          size,
          ratio,
          resolution,
          quality,
          response_format: "url",
          image: references.map((item) => item.publicUrl),
          ...parsedExtra.data,
        },
      });

      setResult(response);
      addHistory({
        id: createLocalId("history"),
        capability: "image",
        modelId: selectedModel.id,
        modelName: selectedModel.name,
        title: "图片创作",
        status: "success",
        createdAt: Date.now(),
        summary: shortText(finalPrompt),
      });
    } catch (submitError) {
      const message =
        submitError instanceof Error ? submitError.message : "图片生成失败。";
      setError(message);
      addHistory({
        id: createLocalId("history"),
        capability: "image",
        modelId: selectedModel.id,
        modelName: selectedModel.name,
        title: "图片创作",
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

          <div className="studio-canvas image-canvas">
            {result ? (
              <div className="media-grid studio-media-grid">
                {result.images.map((image, index) => (
                  <article key={`${image.src}-${index}`} className="result-card">
                    <img src={image.src} alt={`生成结果 ${index + 1}`} />
                    {image.revisedPrompt ? (
                      <p className="muted">{image.revisedPrompt}</p>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-canvas">
                <div className="empty-canvas-card">
                  <div className="hero-model-mark">
                    <ImagePlus aria-hidden="true" size={28} strokeWidth={2} />
                  </div>
                  <div className="empty-canvas-top">
                    <span className="badge badge-accent">图片创作</span>
                    <span>{selectedModel?.name || "未选择模型"}</span>
                  </div>
                  <h3>{selectedModel?.name || "图片创作模型"}</h3>
                  <p className="muted">
                    描述画面主体、构图和风格，支持参考图和模板快速生成。
                  </p>
                  <div className="canvas-hints">
                    <span>电商海报</span>
                    <span>电影感剧照</span>
                    <span>参考图增强</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="composer-card">
            <div className="composer-topline">
              <button type="button" className="gameplay-btn">玩法说明</button>
              <span>
                {missingConfig
                  ? "模型待配置"
                  : references.length
                    ? `${references.length} 张参考图`
                    : "¥0.8 / 次"}
              </span>
            </div>

            <div className="composer-toolbar">
              <TemplateChips
                templates={IMAGE_TEMPLATES}
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
              <div className="composer-attach-row">
                <button
                  type="button"
                  className="button-secondary composer-attach-button"
                  disabled={missingConfig || uploading}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <IconText icon={Upload}>
                    {uploading ? "上传中..." : "+ 参考图"}
                  </IconText>
                </button>

                <textarea
                  className="composer-input"
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  placeholder="描述你想要生成的图片内容，支持上传参考图片进行图生图，最多14张"
                />
              </div>

              <div className="composer-footer-bar">
                <div className="composer-quick-fields composer-quick-fields-wide">
                  <label className="composer-keyword-compact">
                    <span>关键词</span>
                    <input
                      value={keywords}
                      onChange={(event) => setKeywords(event.target.value)}
                      placeholder="玻璃感、青柠色、电商静物"
                    />
                  </label>
              <label>
                <span>数量</span>
                <input
                  value={count}
                  onChange={(event) => setCount(event.target.value)}
                  placeholder="1"
                />
              </label>
              <label>
                <span>尺寸</span>
                <input
                  value={size}
                  onChange={(event) => setSize(event.target.value)}
                  placeholder="1024x1024"
                />
              </label>
              <label>
                <span>比例</span>
                <select
                  value={ratio}
                  onChange={(event) => setRatio(event.target.value)}
                >
                  {["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"].map(
                    (value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ),
                  )}
                </select>
              </label>
              <label>
                <span>分辨率</span>
                <select
                  value={resolution}
                  onChange={(event) => setResolution(event.target.value)}
                >
                  {["1k", "2k", "4k"].map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>质量</span>
                <select
                  value={quality}
                  onChange={(event) => setQuality(event.target.value)}
                >
                  <option value="auto">价格优先</option>
                  <option value="standard">标准</option>
                  <option value="hd">高清优先</option>
                </select>
              </label>
                </div>
                <button
                  type="button"
                  className="composer-submit-button"
                  onClick={handleSubmit}
                  disabled={loading}
                  title={loading ? "生成中..." : "生成图片"}
                >
                  <IconText icon={loading ? ImagePlus : WandSparkles}>
                    {loading ? "生成中..." : "生成图片"}
                  </IconText>
                </button>
              </div>
            </div>

            <details className="composer-details">
              <summary>参考图与高级 JSON</summary>
              <div className="upload-block composer-upload-block">
                <div className="upload-head">
                  <div>
                    <h3>参考图</h3>
                    <p className="muted">可上传多张图片，工作台会自动转成公网 URL。</p>
                  </div>
                  <div className="button-row">
                    <button
                      type="button"
                      className="button-secondary"
                      disabled={missingConfig || uploading}
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <IconText icon={Upload}>
                        {uploading ? "上传中..." : "上传参考图"}
                      </IconText>
                    </button>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/png,image/jpeg,image/jpg,image/webp"
                      multiple
                      hidden
                      onChange={(event) => handleUpload(event.target.files)}
                    />
                  </div>
                </div>

                {references.length > 0 ? (
                  <div className="asset-grid">
                    {references.map((asset) => (
                      <article key={asset.id} className="asset-card">
                        <img src={asset.localPreviewUrl} alt={asset.fileName} />
                        <div className="asset-card-body">
                          <strong>{asset.fileName}</strong>
                          <p className="muted">{asset.publicUrl}</p>
                          <button
                            type="button"
                            className="button-link danger-link"
                            onClick={() =>
                              setReferences((current) =>
                                current.filter((item) => item.id !== asset.id),
                              )
                            }
                            title="移除参考图"
                          >
                            <Trash2 aria-hidden="true" size={16} strokeWidth={2} />
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="muted">未上传参考图时，将按纯文生图处理。</p>
                )}
              </div>
              <label className="field field-full">
                <span>高级参数 JSON</span>
                <textarea
                  value={extraJson}
                  onChange={(event) => setExtraJson(event.target.value)}
                  placeholder='例如：{"watermark":false,"background":"solid"}'
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
              <JsonViewer title="原始响应" value={result.raw} />
            ) : (
              <p className="muted">生成成功后，这里会展示原始返回与模型调试信息。</p>
            )}
          </div>

          <RecentHistory capability="image" />
        </aside>
      </div>
    </>
  );
}
