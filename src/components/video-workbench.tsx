"use client";

/* eslint-disable @next/next/no-img-element */

import Link from "next/link";
import {
  Bell,
  Clapperboard,
  CircleDollarSign,
  Play,
  RefreshCw,
  Settings,
  Trash2,
  Upload,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { IconText } from "@/components/icon";
import { JsonViewer } from "@/components/json-viewer";
import { ModelSpotlight } from "@/components/model-spotlight";
import { RecentHistory } from "@/components/recent-history";
import { TemplateChips } from "@/components/template-chips";
import { useWorkbenchStore } from "@/components/workbench-provider";
import { VIDEO_TEMPLATES } from "@/lib/catalog";
import { postProxy, uploadAsset } from "@/lib/client-proxy";
import {
  combinePrompt,
  createLocalId,
  parseJsonInput,
  resolveModelName,
  shortText,
} from "@/lib/utils";
import type { Adapter, ModelDefinition, UploadedAsset } from "@/lib/types";

interface VideoCreateResult {
  taskId: string;
  status: string;
  raw: Record<string, unknown>;
}

interface VideoQueryResult {
  taskId: string;
  status: string;
  progress: number | string | null;
  videoUrl: string | null;
  thumbnailUrl: string | null;
  raw: Record<string, unknown>;
}

type VideoMode = "text" | "reference" | "start-end";

const UNIFIED_ADAPTERS: Adapter[] = [
  "video-unified-jimeng",
  "video-unified-vidu",
  "video-unified-veo",
  "video-unified-generic",
];

function chooseInitialModel(models: ModelDefinition[]): string {
  return models[0]?.id || "";
}

function getUnifiedImageLimit(mode: VideoMode): number {
  if (mode === "text") {
    return 0;
  }

  if (mode === "reference") {
    return 1;
  }

  return 2;
}

function supportsUnifiedAdapter(adapter: Adapter): boolean {
  return UNIFIED_ADAPTERS.includes(adapter);
}

function getVideoDefaults(model: ModelDefinition | null): {
  duration?: string;
  size?: string;
  resolution?: string;
} {
  if (!model) {
    return {};
  }

  if (model.adapter === "video-unified-jimeng") {
    return { size: "720P", resolution: "720p" };
  }

  if (model.adapter === "video-unified-veo") {
    return { duration: "8", size: "1280x720" };
  }

  if (
    model.adapter === "video-unified-vidu" ||
    model.adapter === "video-seedance"
  ) {
    return { duration: "5", resolution: "720p" };
  }

  return {};
}

export function VideoWorkbench() {
  const { getModelsByCapability, modelSettings, addHistory } = useWorkbenchStore();
  const models = getModelsByCapability("video");
  const unifiedInputRef = useRef<HTMLInputElement | null>(null);
  const seedanceFirstRef = useRef<HTMLInputElement | null>(null);
  const seedanceLastRef = useRef<HTMLInputElement | null>(null);
  const seedanceReferenceRef = useRef<HTMLInputElement | null>(null);
  const [selectedModelId, setSelectedModelId] = useState(() =>
    chooseInitialModel(models),
  );
  const [mode, setMode] = useState<VideoMode>("text");
  const [keywords, setKeywords] = useState("");
  const [prompt, setPrompt] = useState("");
  const [aspectRatio, setAspectRatio] = useState("16:9");
  const [duration, setDuration] = useState("5");
  const [size, setSize] = useState("720P");
  const [resolution, setResolution] = useState("720p");
  const [audio, setAudio] = useState(false);
  const [upsample, setUpsample] = useState(false);
  const [seed, setSeed] = useState("0");
  const [extraJson, setExtraJson] = useState("");
  const [autoPoll, setAutoPoll] = useState(true);
  const [unifiedImages, setUnifiedImages] = useState<UploadedAsset[]>([]);
  const [seedanceFirst, setSeedanceFirst] = useState<UploadedAsset | null>(null);
  const [seedanceLast, setSeedanceLast] = useState<UploadedAsset | null>(null);
  const [seedanceReferences, setSeedanceReferences] = useState<UploadedAsset[]>([]);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [querying, setQuerying] = useState(false);
  const [error, setError] = useState("");
  const [createResult, setCreateResult] = useState<VideoCreateResult | null>(null);
  const [taskResult, setTaskResult] = useState<VideoQueryResult | null>(null);

  const activeModelId = models.some((item) => item.id === selectedModelId)
    ? selectedModelId
    : chooseInitialModel(models);

  const selectedModel = useMemo(
    () => models.find((item) => item.id === activeModelId) || null,
    [activeModelId, models],
  );

  const setting = selectedModel ? modelSettings[selectedModel.id] : undefined;
  const missingConfig = !setting?.baseUrl?.trim() || !setting?.apiKey?.trim();

  useEffect(() => {
    if (!createResult?.taskId || !autoPoll) {
      return;
    }

    const terminal =
      taskResult?.status === "completed" || taskResult?.status === "failed";

    if (terminal) {
      return;
    }

    const timer = window.setInterval(() => {
      void handleQuery();
    }, 5000);

    return () => window.clearInterval(timer);
    // handleQuery reads the latest task id through state and also supports manual calls.
    // Including it here recreates the interval every render without improving freshness.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoPoll, createResult?.taskId, taskResult?.status]);

  async function uploadFiles(
    files: FileList | null,
    assign: (assets: UploadedAsset[]) => void,
  ) {
    if (!files?.length || !setting) {
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

      assign(uploaded);
    } catch (uploadError) {
      setError(
        uploadError instanceof Error ? uploadError.message : "素材上传失败。",
      );
    } finally {
      setUploading(false);
    }
  }

  async function handleUnifiedUpload(files: FileList | null) {
    const limit = getUnifiedImageLimit(mode);

    if (limit === 0) {
      return;
    }

    await uploadFiles(files, (assets) => {
      setUnifiedImages(assets.slice(0, limit));
      if (unifiedInputRef.current) {
        unifiedInputRef.current.value = "";
      }
    });
  }

  async function handleSeedanceFirstUpload(files: FileList | null) {
    await uploadFiles(files, (assets) => {
      setSeedanceFirst(assets[0] || null);
      if (seedanceFirstRef.current) {
        seedanceFirstRef.current.value = "";
      }
    });
  }

  async function handleSeedanceLastUpload(files: FileList | null) {
    await uploadFiles(files, (assets) => {
      setSeedanceLast(assets[0] || null);
      if (seedanceLastRef.current) {
        seedanceLastRef.current.value = "";
      }
    });
  }

  async function handleSeedanceReferenceUpload(files: FileList | null) {
    await uploadFiles(files, (assets) => {
      setSeedanceReferences((current) => [...current, ...assets]);
      if (seedanceReferenceRef.current) {
        seedanceReferenceRef.current.value = "";
      }
    });
  }

  function buildVideoRequestBody(
    adapter: Adapter,
    modelName: string,
    finalPrompt: string,
    extraBody: Record<string, unknown>,
  ): Record<string, unknown> {
    const extraMetadata =
      extraBody.metadata &&
      typeof extraBody.metadata === "object" &&
      !Array.isArray(extraBody.metadata)
        ? (extraBody.metadata as Record<string, unknown>)
        : {};

    if (adapter === "video-unified-jimeng") {
      return {
        model: modelName,
        prompt: finalPrompt,
        images:
          mode === "text" ? [] : unifiedImages.map((item) => item.publicUrl),
        aspect_ratio: aspectRatio,
        size,
        ...extraBody,
      };
    }

    if (adapter === "video-unified-vidu") {
      return {
        model: modelName,
        prompt: finalPrompt,
        images:
          mode === "text" ? [] : unifiedImages.map((item) => item.publicUrl),
        aspect_ratio: aspectRatio,
        duration: Number(duration) || 5,
        resolution,
        audio,
        seed: Number(seed) || 0,
        ...extraBody,
      };
    }

    if (adapter === "video-unified-veo") {
      const orientation = aspectRatio === "9:16" ? "portrait" : "landscape";
      return {
        model: modelName,
        prompt: finalPrompt,
        images:
          mode === "text" ? [] : unifiedImages.map((item) => item.publicUrl),
        orientation,
        size,
        duration: Number(duration) || 8,
        aspect_ratio: aspectRatio,
        enable_upsample: upsample,
        ...extraBody,
      };
    }

    if (adapter === "video-seedance") {
      const content: Array<Record<string, unknown>> = [
        {
          type: "text",
          text: finalPrompt,
        },
      ];

      if (mode === "reference") {
        seedanceReferences.forEach((asset) => {
          content.push({
            type: "image_url",
            image_url: { url: asset.publicUrl },
            role: "reference_image",
          });
        });
      }

      if (mode === "start-end") {
        if (seedanceFirst) {
          content.push({
            type: "image_url",
            image_url: { url: seedanceFirst.publicUrl },
            role: "first_frame",
          });
        }

        if (seedanceLast) {
          content.push({
            type: "image_url",
            image_url: { url: seedanceLast.publicUrl },
            role: "last_frame",
          });
        }
      }

      return {
        model: modelName,
        content,
        metadata: {
          duration: Number(duration) || 5,
          resolution,
          ratio: aspectRatio,
          generate_audio: audio,
          seed: Number(seed) || 0,
          ...extraMetadata,
        },
        ...extraBody,
      };
    }

    return {
      model: modelName,
      prompt: finalPrompt,
      images:
        mode === "text" ? [] : unifiedImages.map((item) => item.publicUrl),
      aspect_ratio: aspectRatio,
      duration: Number(duration) || 5,
      size,
      resolution,
      audio,
      seed: Number(seed) || 0,
      ...extraBody,
    };
  }

  async function handleCreate() {
    if (!selectedModel || !setting) {
      return;
    }

    const finalPrompt = combinePrompt(keywords, prompt);

    if (!finalPrompt.trim()) {
      setError("请先输入视频需求。");
      return;
    }

    if (supportsUnifiedAdapter(selectedModel.adapter)) {
      const limit = getUnifiedImageLimit(mode);
      if (unifiedImages.length < limit) {
        setError("当前模式需要的参考图数量还不够。");
        return;
      }
    }

    if (selectedModel.adapter === "video-seedance") {
      if (mode === "reference" && seedanceReferences.length === 0) {
        setError("Seedance 参考模式至少需要上传一张参考图。");
        return;
      }

      if (mode === "start-end" && (!seedanceFirst || !seedanceLast)) {
        setError("Seedance 首尾帧模式需要同时上传首帧和尾帧。");
        return;
      }
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
    setTaskResult(null);

    try {
      const modelName = resolveModelName(selectedModel, setting);
      const requestBody = buildVideoRequestBody(
        selectedModel.adapter,
        modelName,
        finalPrompt,
        parsedExtra.data,
      );

      const response = await postProxy<VideoCreateResult>(
        "/api/proxy/video/create",
        {
          config: {
            baseUrl: setting.baseUrl,
            apiKey: setting.apiKey,
          },
          adapter: selectedModel.adapter,
          requestBody,
        },
      );

      setCreateResult(response);
      addHistory({
        id: createLocalId("history"),
        capability: "video",
        modelId: selectedModel.id,
        modelName: selectedModel.name,
        title: "视频创作",
        status: "processing",
        createdAt: Date.now(),
        summary: `任务已提交：${response.taskId}`,
      });

      if (autoPoll) {
        await handleQuery(response.taskId, selectedModel.adapter);
      }
    } catch (submitError) {
      const message =
        submitError instanceof Error ? submitError.message : "视频任务提交失败。";
      setError(message);
      addHistory({
        id: createLocalId("history"),
        capability: "video",
        modelId: selectedModel.id,
        modelName: selectedModel.name,
        title: "视频创作",
        status: "error",
        createdAt: Date.now(),
        summary: shortText(message),
      });
    } finally {
      setLoading(false);
    }
  }

  async function handleQuery(
    taskIdArg?: string,
    adapterArg?: Adapter,
  ): Promise<void> {
    if (!selectedModel || !setting) {
      return;
    }

    const taskId = taskIdArg || createResult?.taskId;
    const adapter = adapterArg || selectedModel.adapter;

    if (!taskId) {
      setError("暂无可查询的任务 ID。");
      return;
    }

    setQuerying(true);
    setError("");

    try {
      const response = await postProxy<VideoQueryResult>(
        "/api/proxy/video/query",
        {
          config: {
            baseUrl: setting.baseUrl,
            apiKey: setting.apiKey,
          },
          adapter,
          taskId,
        },
      );

      setTaskResult(response);

      if (response.status === "completed") {
        addHistory({
          id: createLocalId("history"),
          capability: "video",
          modelId: selectedModel.id,
          modelName: selectedModel.name,
          title: "视频创作",
          status: "success",
          createdAt: Date.now(),
          summary: `任务完成：${taskId}`,
        });
      }

      if (response.status === "failed") {
        addHistory({
          id: createLocalId("history"),
          capability: "video",
          modelId: selectedModel.id,
          modelName: selectedModel.name,
          title: "视频创作",
          status: "error",
          createdAt: Date.now(),
          summary: `任务失败：${taskId}`,
        });
      }
    } catch (queryError) {
      setError(
        queryError instanceof Error ? queryError.message : "任务查询失败。",
      );
    } finally {
      setQuerying(false);
    }
  }

  const selectedAdapter = selectedModel?.adapter;
  const unifiedMode = selectedAdapter
    ? supportsUnifiedAdapter(selectedAdapter)
    : false;

  function handleModelChange(nextModelId: string) {
    const nextModel =
      models.find((item) => item.id === nextModelId) || null;
    const defaults = getVideoDefaults(nextModel);

    setSelectedModelId(nextModelId);
    if (defaults.duration) {
      setDuration(defaults.duration);
    }
    if (defaults.size) {
      setSize(defaults.size);
    }
    if (defaults.resolution) {
      setResolution(defaults.resolution);
    }
    setCreateResult(null);
    setTaskResult(null);
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
            onChange={handleModelChange}
          />

          <div className="studio-canvas video-canvas">
            {taskResult?.videoUrl ? (
              <div className="video-stage">
                <video
                  src={taskResult.videoUrl}
                  controls
                  playsInline
                  preload="metadata"
                />
                <a
                  className="button-link"
                  href={taskResult.videoUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  <IconText icon={Play}>打开视频地址</IconText>
                </a>
              </div>
            ) : createResult ? (
              <div className="task-canvas">
                <span className="badge badge-accent">任务已提交</span>
                <h3>{createResult.taskId}</h3>
                <div className="task-metrics">
                  <span>提交状态：{createResult.status}</span>
                  <span>
                    查询状态：{taskResult?.status || "等待查询"}
                  </span>
                  <span>
                    进度：
                    {taskResult?.progress === null || taskResult?.progress === undefined
                      ? "-"
                      : String(taskResult.progress)}
                  </span>
                </div>
                {taskResult?.thumbnailUrl ? (
                  <img
                    className="single-preview"
                    src={taskResult.thumbnailUrl}
                    alt="视频缩略图"
                  />
                ) : null}
              </div>
            ) : (
              <div className="empty-canvas">
                <div className="empty-canvas-card">
                  <div className="hero-model-mark">
                    <Clapperboard aria-hidden="true" size={28} strokeWidth={2} />
                  </div>
                  <div className="empty-canvas-top">
                    <span className="badge badge-accent">视频创作</span>
                    <span>{selectedModel?.name || "未选择模型"}</span>
                  </div>
                  <h3>{selectedModel?.name || "视频创作模型"}</h3>
                  <p className="muted">
                    把镜头语言、素材和参数放进同一个任务入口，支持文生、图生和首尾帧。
                  </p>
                  <div className="canvas-hints">
                    <span>文生视频</span>
                    <span>图生视频</span>
                    <span>首尾帧</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="composer-card">
            <div className="composer-topline">
              <button type="button" className="gameplay-btn">玩法说明</button>
              <span>{missingConfig ? "模型待配置" : autoPoll ? "自动轮询已开" : "手动查询任务"}</span>
            </div>

            <div className="composer-toolbar">
              <TemplateChips
                templates={VIDEO_TEMPLATES}
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
              <div className="composer-attach-row composer-video-attach-row">
                {unifiedMode ? (
                  <button
                    type="button"
                    className="button-secondary composer-attach-button"
                    disabled={
                      missingConfig || uploading || getUnifiedImageLimit(mode) === 0
                    }
                    onClick={() => unifiedInputRef.current?.click()}
                  >
                    <IconText icon={Upload}>
                      {mode === "text" ? "无需素材" : uploading ? "上传中..." : "+ 参考图"}
                    </IconText>
                  </button>
                ) : null}

                {!unifiedMode && mode === "reference" ? (
                  <button
                    type="button"
                    className="button-secondary composer-attach-button"
                    disabled={missingConfig || uploading}
                    onClick={() => seedanceReferenceRef.current?.click()}
                  >
                    <IconText icon={Upload}>{uploading ? "上传中..." : "+ 参考图"}</IconText>
                  </button>
                ) : null}

                {!unifiedMode && mode === "start-end" ? (
                  <div className="composer-frame-actions">
                    <button
                      type="button"
                      className="button-secondary composer-attach-button"
                      disabled={missingConfig || uploading}
                      onClick={() => seedanceFirstRef.current?.click()}
                    >
                      <IconText icon={Upload}>首帧</IconText>
                    </button>
                    <button
                      type="button"
                      className="button-secondary composer-attach-button"
                      disabled={missingConfig || uploading}
                      onClick={() => seedanceLastRef.current?.click()}
                    >
                      <IconText icon={Upload}>尾帧</IconText>
                    </button>
                  </div>
                ) : null}

                <textarea
                  className="composer-input"
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  placeholder="描述主体动作、镜头运动、时长、风格和节奏..."
                />
              </div>

              <div className="composer-footer-bar">
                <div className="composer-quick-fields composer-quick-fields-wide">
              <label>
                <span>创作模式</span>
                <select
                  value={mode}
                  onChange={(event) => {
                    setMode(event.target.value as VideoMode);
                    setUnifiedImages([]);
                    setSeedanceFirst(null);
                    setSeedanceLast(null);
                    setSeedanceReferences([]);
                  }}
                >
                  <option value="text">纯文生视频</option>
                  <option value="reference">上传参考图</option>
                  <option value="start-end">首尾帧过渡</option>
                </select>
              </label>
              <label className="composer-keyword-compact">
                <span>关键词</span>
                <input
                  value={keywords}
                  onChange={(event) => setKeywords(event.target.value)}
                  placeholder="果茶广告、镜头推进"
                />
              </label>
              <label>
                <span>画幅比例</span>
                <select
                  value={aspectRatio}
                  onChange={(event) => setAspectRatio(event.target.value)}
                >
                  {["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"].map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>

              {selectedAdapter !== "video-unified-jimeng" ? (
                <label>
                  <span>时长（秒）</span>
                  <input
                    value={duration}
                    onChange={(event) => setDuration(event.target.value)}
                    placeholder="5"
                  />
                </label>
              ) : null}

              {selectedAdapter === "video-unified-jimeng" ? (
                <label>
                  <span>尺寸档位</span>
                  <select
                    value={size}
                    onChange={(event) => setSize(event.target.value)}
                  >
                    {["720P", "1080P"].map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}

              {selectedAdapter === "video-unified-veo" ? (
                <label>
                  <span>输出尺寸</span>
                  <select
                    value={size}
                    onChange={(event) => setSize(event.target.value)}
                  >
                    {["1280x720", "720x1280"].map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}

              {(selectedAdapter === "video-unified-vidu" ||
                selectedAdapter === "video-unified-generic" ||
                selectedAdapter === "video-seedance") ? (
                <label>
                  <span>分辨率</span>
                  <select
                    value={resolution}
                    onChange={(event) => setResolution(event.target.value)}
                  >
                    {["540p", "720p", "1080p"].map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}

              <label>
                <span>随机种子</span>
                <input
                  value={seed}
                  onChange={(event) => setSeed(event.target.value)}
                  placeholder="0"
                />
              </label>

              <label className="composer-check-field">
                <input
                  type="checkbox"
                  checked={audio}
                  onChange={(event) => setAudio(event.target.checked)}
                />
                <span>生成音频 / 合成音频</span>
              </label>

              {selectedAdapter === "video-unified-veo" ? (
                <label className="composer-check-field">
                  <input
                    type="checkbox"
                    checked={upsample}
                    onChange={(event) => setUpsample(event.target.checked)}
                  />
                  <span>开启 Veo 高清增强</span>
                </label>
              ) : null}
                </div>

                <div className="composer-video-actions">
                  <button
                    type="button"
                    className="composer-submit-button"
                    onClick={handleCreate}
                    disabled={loading}
                    title={loading ? "提交中..." : "创建视频任务"}
                  >
                    <IconText icon={loading ? Clapperboard : Play}>
                      {loading ? "提交中..." : "创建视频任务"}
                    </IconText>
                  </button>
                  <button
                    type="button"
                    className="button-secondary"
                    onClick={() => void handleQuery()}
                    disabled={querying || !createResult?.taskId}
                  >
                    <IconText icon={RefreshCw}>
                      {querying ? "查询中..." : "查询任务"}
                    </IconText>
                  </button>
                </div>
              </div>
            </div>

            <details className="composer-details">
              <summary>素材上传与高级 JSON</summary>
              {unifiedMode ? (
                <div className="upload-block composer-upload-block">
              <div className="upload-head">
                <div>
                  <h3>素材上传</h3>
                  <p className="muted">
                    当前模式下需要 {getUnifiedImageLimit(mode)} 张图片。
                  </p>
                </div>
                <button
                  type="button"
                  className="button-secondary"
                  disabled={
                    missingConfig || uploading || getUnifiedImageLimit(mode) === 0
                  }
                  onClick={() => unifiedInputRef.current?.click()}
                >
                  <IconText icon={Upload}>
                    {uploading ? "上传中..." : "上传图片素材"}
                  </IconText>
                </button>
                <input
                  ref={unifiedInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/jpg,image/webp"
                  multiple={mode === "start-end"}
                  hidden
                  onChange={(event) => handleUnifiedUpload(event.target.files)}
                />
              </div>

              {mode === "text" ? (
                <p className="muted">纯文生视频无需上传素材。</p>
              ) : (
                <div className="asset-grid">
                  {unifiedImages.map((asset) => (
                    <article key={asset.id} className="asset-card">
                      <img src={asset.localPreviewUrl} alt={asset.fileName} />
                      <div className="asset-card-body">
                        <strong>{asset.fileName}</strong>
                        <p className="muted">{asset.publicUrl}</p>
                        <button
                          type="button"
                          className="button-link danger-link"
                          onClick={() =>
                            setUnifiedImages((current) =>
                              current.filter((item) => item.id !== asset.id),
                            )
                          }
                          title="移除素材"
                        >
                          <Trash2 aria-hidden="true" size={16} strokeWidth={2} />
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
                </div>
              ) : (
                <div className="upload-block composer-upload-block">
              <div className="upload-head">
                <div>
                  <h3>Seedance 素材上传</h3>
                  <p className="muted">
                    参考模式可上传多张参考图；首尾帧模式分别上传首帧和尾帧。
                  </p>
                </div>
              </div>

              {mode === "reference" ? (
                <>
                  <div className="button-row">
                    <button
                      type="button"
                      className="button-secondary"
                      disabled={missingConfig || uploading}
                      onClick={() => seedanceReferenceRef.current?.click()}
                    >
                      <IconText icon={Upload}>
                        {uploading ? "上传中..." : "上传参考图"}
                      </IconText>
                    </button>
                    <input
                      ref={seedanceReferenceRef}
                      type="file"
                      accept="image/png,image/jpeg,image/jpg,image/webp"
                      multiple
                      hidden
                      onChange={(event) =>
                        handleSeedanceReferenceUpload(event.target.files)
                      }
                    />
                  </div>

                  <div className="asset-grid">
                    {seedanceReferences.map((asset) => (
                      <article key={asset.id} className="asset-card">
                        <img src={asset.localPreviewUrl} alt={asset.fileName} />
                        <div className="asset-card-body">
                          <strong>{asset.fileName}</strong>
                          <button
                            type="button"
                            className="button-link danger-link"
                            onClick={() =>
                              setSeedanceReferences((current) =>
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
                </>
              ) : null}

              {mode === "start-end" ? (
                <div className="dual-upload-grid">
                  <div className="panel panel-subtle">
                    <h4>首帧</h4>
                    <button
                      type="button"
                      className="button-secondary"
                      disabled={missingConfig || uploading}
                      onClick={() => seedanceFirstRef.current?.click()}
                    >
                      <IconText icon={Upload}>上传首帧</IconText>
                    </button>
                    <input
                      ref={seedanceFirstRef}
                      type="file"
                      accept="image/png,image/jpeg,image/jpg,image/webp"
                      hidden
                      onChange={(event) =>
                        handleSeedanceFirstUpload(event.target.files)
                      }
                    />
                    {seedanceFirst ? (
                      <img
                        className="single-preview"
                        src={seedanceFirst.localPreviewUrl}
                        alt={seedanceFirst.fileName}
                      />
                    ) : null}
                  </div>

                  <div className="panel panel-subtle">
                    <h4>尾帧</h4>
                    <button
                      type="button"
                      className="button-secondary"
                      disabled={missingConfig || uploading}
                      onClick={() => seedanceLastRef.current?.click()}
                    >
                      <IconText icon={Upload}>上传尾帧</IconText>
                    </button>
                    <input
                      ref={seedanceLastRef}
                      type="file"
                      accept="image/png,image/jpeg,image/jpg,image/webp"
                      hidden
                      onChange={(event) =>
                        handleSeedanceLastUpload(event.target.files)
                      }
                    />
                    {seedanceLast ? (
                      <img
                        className="single-preview"
                        src={seedanceLast.localPreviewUrl}
                        alt={seedanceLast.fileName}
                      />
                    ) : null}
                  </div>
                </div>
              ) : null}

              {mode === "text" ? (
                <p className="muted">纯文生视频无需上传素材。</p>
              ) : null}
                </div>
              )}
              <label className="field field-full">
                <span>高级参数 JSON</span>
                <textarea
                  value={extraJson}
                  onChange={(event) => setExtraJson(event.target.value)}
                  placeholder='例如：{"watermark":false}'
                />
              </label>
            </details>

          {error ? <div className="inline-message inline-danger">{error}</div> : null}

            <div className="composer-status-row">
              <label className="checkbox-inline">
                <input
                  type="checkbox"
                  checked={autoPoll}
                  onChange={(event) => setAutoPoll(event.target.checked)}
                />
                <span>自动轮询</span>
              </label>
            </div>
          </div>
        </section>

        <aside className="aside-column studio-aside">
          <div className="panel">
            <h3>调试响应</h3>
            {createResult || taskResult ? (
              <>
                {createResult ? (
                  <JsonViewer title="提交响应" value={createResult.raw} />
                ) : null}
                {taskResult ? (
                  <JsonViewer title="查询响应" value={taskResult.raw} />
                ) : null}
              </>
            ) : (
              <p className="muted">提交视频任务后，这里展示提交与查询的原始返回。</p>
            )}
          </div>

          <RecentHistory capability="video" />
        </aside>
      </div>
    </>
  );
}
