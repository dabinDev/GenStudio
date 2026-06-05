"use client";

import { useMemo, useState } from "react";
import {
  CheckCircle2,
  Clock3,
  Edit3,
  ListChecks,
  Plus,
  Send,
  Trash2,
  X,
  XCircle,
} from "lucide-react";

import { IconText } from "@/components/icon";
import { JsonViewer } from "@/components/json-viewer";
import {
  ADAPTER_LABELS,
  CAPABILITY_LABELS,
  getAdapterOptions,
  getCapabilityDefaultAdapter,
} from "@/lib/catalog";
import { postProxyWithRawError } from "@/lib/client-proxy";
import { createLocalId, resolveModelName } from "@/lib/utils";
import { useWorkbenchStore } from "@/components/workbench-provider";
import type {
  Adapter,
  Capability,
  ModelDefinition,
  ModelSetting,
} from "@/lib/types";

interface ConfigDraft {
  id: string;
  name: string;
  vendor: string;
  capability: Capability;
  adapter: Adapter;
  model: string;
  description: string;
  baseUrl: string;
  apiKey: string;
  modelNameOverride: string;
}

interface AvailableModelsResult {
  models: string[];
  durationMs: number;
  raw: Record<string, unknown>;
}

interface TestRequestResult {
  ok: boolean;
  status: number;
  request: {
    url: string;
    body: Record<string, unknown>;
  };
  durationMs: number;
  raw: Record<string, unknown>;
}

interface ModelActionState<T> {
  loading: boolean;
  error: string;
  result: T | null;
  rawError?: unknown;
}

type DialogMode = "create" | "edit";

function createIdleState<T>(): ModelActionState<T> {
  return {
    loading: false,
    error: "",
    result: null,
  };
}

function createEmptyDraft(): ConfigDraft {
  return {
    id: createLocalId("custom-model"),
    name: "",
    vendor: "",
    capability: "video",
    adapter: "video-unified-generic",
    model: "",
    description: "",
    baseUrl: "",
    apiKey: "",
    modelNameOverride: "",
  };
}

function createDraftFromModel(
  model: ModelDefinition,
  setting: ModelSetting,
): ConfigDraft {
  return {
    id: model.id,
    name: model.name,
    vendor: model.vendor,
    capability: model.capability,
    adapter: model.adapter,
    model: model.model,
    description: model.description,
    baseUrl: setting.baseUrl,
    apiKey: setting.apiKey,
    modelNameOverride: setting.modelNameOverride,
  };
}

function getPayloadFromError(error: unknown): unknown {
  if (!error || typeof error !== "object") {
    return undefined;
  }

  return (error as { payload?: unknown }).payload;
}

function maskUrl(url: string): string {
  return url.trim() || "-";
}

function getModelSetting(
  settings: Record<string, ModelSetting>,
  modelId: string,
): ModelSetting {
  return (
    settings[modelId] || {
      baseUrl: "",
      apiKey: "",
      modelNameOverride: "",
    }
  );
}

function getStatusLabel(
  model: ModelDefinition,
  setting: ModelSetting,
  testState?: ModelActionState<TestRequestResult>,
): {
  className: string;
  icon: typeof CheckCircle2;
  text: string;
} {
  if (testState?.loading) {
    return {
      className: "badge-warn",
      icon: Clock3,
      text: "测试中",
    };
  }

  if (testState?.result?.ok) {
    return {
      className: "badge-success",
      icon: CheckCircle2,
      text: `已连接 ${testState.result.durationMs}ms`,
    };
  }

  if (testState?.error) {
    return {
      className: "badge-danger",
      icon: XCircle,
      text: "连接失败",
    };
  }

  if (!setting.baseUrl.trim() || !setting.apiKey.trim()) {
    return {
      className: "badge-warn",
      icon: Clock3,
      text: "待配置",
    };
  }

  return {
    className: model.builtin ? "badge" : "badge-accent",
    icon: CheckCircle2,
    text: "待测试",
  };
}

export function SettingsPage() {
  const {
    models,
    modelSettings,
    updateModelSetting,
    clearModelSetting,
    addCustomModel,
    removeCustomModel,
    updateCustomModel,
  } = useWorkbenchStore();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<DialogMode>("create");
  const [draft, setDraft] = useState<ConfigDraft>(() => createEmptyDraft());
  const [modelListState, setModelListState] = useState<
    Record<string, ModelActionState<AvailableModelsResult>>
  >({});
  const [testState, setTestState] = useState<
    Record<string, ModelActionState<TestRequestResult>>
  >({});
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>([]);

  const configuredCount = useMemo(
    () =>
      models.filter((model) => {
        const setting = getModelSetting(modelSettings, model.id);
        return setting.baseUrl.trim() && setting.apiKey.trim();
      }).length,
    [modelSettings, models],
  );
  const selectedModels = useMemo(
    () => models.filter((model) => selectedModelIds.includes(model.id)),
    [models, selectedModelIds],
  );
  const allSelected = models.length > 0 && selectedModelIds.length === models.length;
  const partiallySelected =
    selectedModelIds.length > 0 && selectedModelIds.length < models.length;

  function openCreateDialog() {
    setDialogMode("create");
    setDraft(createEmptyDraft());
    setDialogOpen(true);
  }

  function openEditDialog(model: ModelDefinition) {
    setDialogMode("edit");
    setDraft(createDraftFromModel(model, getModelSetting(modelSettings, model.id)));
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
  }

  function updateDraft(patch: Partial<ConfigDraft>) {
    setDraft((current) => ({
      ...current,
      ...patch,
    }));
  }

  function handleDraftCapabilityChange(capability: Capability) {
    updateDraft({
      capability,
      adapter: getCapabilityDefaultAdapter(capability),
    });
  }

  function handleSaveDialog() {
    const name = draft.name.trim();
    const modelName = draft.model.trim();

    if (!name || !modelName) {
      return;
    }

    if (dialogMode === "create") {
      addCustomModel({
        id: draft.id,
        name,
        vendor: draft.vendor.trim() || "自定义",
        capability: draft.capability,
        adapter: draft.adapter,
        model: modelName,
        description: draft.description.trim() || "用户自定义模型",
      });
    } else {
      const target = models.find((model) => model.id === draft.id);

      if (target && !target.builtin) {
        updateCustomModel(draft.id, {
          name,
          vendor: draft.vendor.trim() || "自定义",
          capability: draft.capability,
          adapter: draft.adapter,
          model: modelName,
          description: draft.description.trim() || "用户自定义模型",
        });
      }
    }

    updateModelSetting(draft.id, {
      baseUrl: draft.baseUrl.trim(),
      apiKey: draft.apiKey.trim(),
      modelNameOverride: draft.modelNameOverride.trim(),
    });
    setDialogOpen(false);
  }

  async function handleFetchModels(model: ModelDefinition, setting: ModelSetting) {
    if (!setting.baseUrl.trim() || !setting.apiKey.trim()) {
      setModelListState((current) => ({
        ...current,
        [model.id]: {
          ...createIdleState<AvailableModelsResult>(),
          error: "请先填写 baseURL 和 API Key。",
        },
      }));
      return;
    }

    setModelListState((current) => ({
      ...current,
      [model.id]: {
        ...createIdleState<AvailableModelsResult>(),
        loading: true,
      },
    }));

    try {
      const result = await postProxyWithRawError<AvailableModelsResult>(
        "/api/proxy/models",
        {
          config: {
            baseUrl: setting.baseUrl,
            apiKey: setting.apiKey,
          },
        },
      );

      setModelListState((current) => ({
        ...current,
        [model.id]: {
          loading: false,
          error: "",
          result,
        },
      }));
    } catch (error) {
      setModelListState((current) => ({
        ...current,
        [model.id]: {
          loading: false,
          error:
            error instanceof Error ? error.message : "获取可用模型失败。",
          result: null,
          rawError: getPayloadFromError(error),
        },
      }));
    }
  }

  async function handleTestModel(model: ModelDefinition, setting: ModelSetting) {
    if (!setting.baseUrl.trim() || !setting.apiKey.trim()) {
      setTestState((current) => ({
        ...current,
        [model.id]: {
          ...createIdleState<TestRequestResult>(),
          error: "请先填写 baseURL 和 API Key。",
        },
      }));
      return;
    }

    setTestState((current) => ({
      ...current,
      [model.id]: {
        ...createIdleState<TestRequestResult>(),
        loading: true,
      },
    }));

    try {
      const result = await postProxyWithRawError<TestRequestResult>(
        "/api/proxy/test",
        {
          config: {
            baseUrl: setting.baseUrl,
            apiKey: setting.apiKey,
          },
          capability: model.capability,
          adapter: model.adapter,
          model: resolveModelName(model, setting),
        },
      );

      setTestState((current) => ({
        ...current,
        [model.id]: {
          loading: false,
          error: "",
          result,
        },
      }));
    } catch (error) {
      setTestState((current) => ({
        ...current,
        [model.id]: {
          loading: false,
          error: error instanceof Error ? error.message : "测试请求失败。",
          result: null,
          rawError: getPayloadFromError(error),
        },
      }));
    }
  }

  async function handleBatchTest() {
    const configuredModels = selectedModels.filter((model) => {
      const setting = getModelSetting(modelSettings, model.id);
      return setting.baseUrl.trim() && setting.apiKey.trim();
    });

    await Promise.allSettled(
      configuredModels.map((model) =>
        handleTestModel(model, getModelSetting(modelSettings, model.id)),
      ),
    );
  }

  function handleToggleAll(checked: boolean) {
    setSelectedModelIds(checked ? models.map((model) => model.id) : []);
  }

  function handleToggleModel(modelId: string, checked: boolean) {
    setSelectedModelIds((current) =>
      checked
        ? Array.from(new Set([...current, modelId]))
        : current.filter((id) => id !== modelId),
    );
  }

  function handleBatchDelete() {
    selectedModels.forEach((model) => {
      if (model.builtin) {
        clearModelSetting(model.id);
      } else {
        removeCustomModel(model.id);
      }
    });
    setSelectedModelIds([]);
  }

  const canSave = draft.name.trim() && draft.model.trim();
  const draftModelListState = modelListState[draft.id];
  const draftTestState = testState[draft.id];

  return (
    <>
      <section className="settings-hero">
        <div>
          <p className="eyebrow">Model Settings</p>
          <h2>模型配置</h2>
          <p className="muted">
            使用列表管理每个模型的 baseURL、API Key 和连通状态。配置会缓存在当前浏览器。
          </p>
        </div>
        <div className="settings-hero-stats">
          <span className="badge">{models.length} 个模型</span>
          <span className="badge badge-success">{configuredCount} 个已配置</span>
        </div>
      </section>

      <section className="settings-list-panel">
        <div className="settings-list-toolbar">
          <div className="settings-bulk-actions">
            <span className="badge">
              已选 {selectedModelIds.length} / {models.length}
            </span>
            <button
              type="button"
              className="button-secondary"
              disabled={selectedModelIds.length === 0}
              onClick={handleBatchTest}
            >
              <IconText icon={ListChecks}>批量测试</IconText>
            </button>
            <button
              type="button"
              className="button-danger"
              disabled={selectedModelIds.length === 0}
              onClick={handleBatchDelete}
            >
              <IconText icon={Trash2}>批量删除</IconText>
            </button>
          </div>
          <button type="button" onClick={openCreateDialog}>
            <IconText icon={Plus}>添加模型</IconText>
          </button>
        </div>

        <div className="settings-table">
          <div className="settings-table-head">
            <label className="settings-check-cell" title="全选">
              <input
                type="checkbox"
                checked={allSelected}
                ref={(element) => {
                  if (element) {
                    element.indeterminate = partiallySelected;
                  }
                }}
                onChange={(event) => handleToggleAll(event.target.checked)}
              />
            </label>
            <span>名称</span>
            <span>请求地址</span>
            <span>链接状态</span>
            <span>操作</span>
          </div>

          {models.map((model) => {
            const setting = getModelSetting(modelSettings, model.id);
            const fetchedModels = modelListState[model.id];
            const testResult = testState[model.id];
            const status = getStatusLabel(model, setting, testState[model.id]);
            const StatusIcon = status.icon;

            return (
              <article key={model.id} className="settings-table-row">
                <label className="settings-check-cell" title="选择模型">
                  <input
                    type="checkbox"
                    checked={selectedModelIds.includes(model.id)}
                    onChange={(event) =>
                      handleToggleModel(model.id, event.target.checked)
                    }
                  />
                </label>
                <div className="settings-model-name">
                  <strong>{model.name}</strong>
                  <span>
                    {CAPABILITY_LABELS[model.capability]} · {model.vendor}
                  </span>
                </div>
                <div className="settings-url" title={setting.baseUrl}>
                  {maskUrl(setting.baseUrl)}
                </div>
                <div>
                  <span className={`badge ${status.className}`}>
                    <IconText icon={StatusIcon}>{status.text}</IconText>
                  </span>
                </div>
                <div className="settings-row-actions">
                  <button
                    type="button"
                    className="button-secondary"
                    disabled={fetchedModels?.loading}
                    onClick={() => handleFetchModels(model, setting)}
                  >
                    <IconText icon={ListChecks}>
                      {fetchedModels?.loading ? "获取中" : "模型列表"}
                    </IconText>
                  </button>
                  <button
                    type="button"
                    className="button-secondary"
                    disabled={testResult?.loading}
                    onClick={() => handleTestModel(model, setting)}
                  >
                    <IconText icon={Send}>
                      {testResult?.loading ? "测试中" : "测速"}
                    </IconText>
                  </button>
                  <button
                    type="button"
                    className="button-secondary icon-button"
                    onClick={() => openEditDialog(model)}
                    title="编辑配置"
                  >
                    <Edit3 aria-hidden="true" size={15} strokeWidth={2} />
                  </button>
                  {!model.builtin ? (
                    <button
                      type="button"
                      className="button-danger icon-button"
                      onClick={() => removeCustomModel(model.id)}
                      title="删除模型"
                    >
                      <Trash2 aria-hidden="true" size={15} strokeWidth={2} />
                    </button>
                  ) : null}
                </div>

                {fetchedModels?.error ? (
                  <div className="settings-row-detail inline-message inline-danger">
                    {fetchedModels.error}
                  </div>
                ) : null}

                {testResult?.error ? (
                  <div className="settings-row-detail inline-message inline-danger">
                    {testResult.error}
                  </div>
                ) : null}

                {fetchedModels?.result ? (
                  <div className="settings-row-detail settings-model-list-result">
                    <div className="status-row">
                      <span className="badge badge-success">
                        <IconText icon={CheckCircle2}>
                          {`已获取 ${fetchedModels.result.models.length} 个模型`}
                        </IconText>
                      </span>
                      <span className="history-time">
                        {fetchedModels.result.durationMs}ms
                      </span>
                    </div>
                    <div className="available-model-list">
                      {fetchedModels.result.models
                        .slice(0, 24)
                        .map((modelId) => (
                          <button
                            key={modelId}
                            type="button"
                            className="chip-button model-id-chip"
                            onClick={() =>
                              updateModelSetting(model.id, {
                                modelNameOverride: modelId,
                              })
                            }
                          >
                            {modelId}
                          </button>
                        ))}
                    </div>
                  </div>
                ) : null}

                {testResult?.result ? (
                  <div className="settings-row-detail settings-test-result">
                    <span className="history-time">
                      HTTP {testResult.result.status} ·{" "}
                      {testResult.result.durationMs}ms ·{" "}
                      {testResult.result.request.url}
                    </span>
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      </section>

      {dialogOpen ? (
        <div className="settings-dialog-backdrop" role="presentation">
          <section
            className="settings-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="模型配置"
          >
            <div className="settings-dialog-head">
              <div>
                <p className="eyebrow">Model Config</p>
                <h3>{dialogMode === "create" ? "添加模型" : "模型配置"}</h3>
              </div>
              <button
                type="button"
                className="button-secondary icon-button"
                onClick={closeDialog}
                title="关闭"
              >
                <X aria-hidden="true" size={18} strokeWidth={2} />
              </button>
            </div>

            <div className="form-grid settings-dialog-grid">
              <label className="field">
                <span>名称</span>
                <input
                  value={draft.name}
                  onChange={(event) => updateDraft({ name: event.target.value })}
                  placeholder="例如：Seedance 2.0"
                />
              </label>

              <label className="field">
                <span>备注</span>
                <input
                  value={draft.description}
                  onChange={(event) =>
                    updateDraft({ description: event.target.value })
                  }
                  placeholder="例如：首尾帧视频模型"
                />
              </label>

              <label className="field">
                <span>厂商</span>
                <input
                  value={draft.vendor}
                  onChange={(event) => updateDraft({ vendor: event.target.value })}
                  placeholder="例如：字节 / Google / 自定义"
                />
              </label>

              <label className="field">
                <span>能力类型</span>
                <select
                  value={draft.capability}
                  disabled={dialogMode === "edit" && models.some((model) => model.id === draft.id && model.builtin)}
                  onChange={(event) =>
                    handleDraftCapabilityChange(event.target.value as Capability)
                  }
                >
                  {Object.entries(CAPABILITY_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field field-full">
                <span>适配器</span>
                <select
                  value={draft.adapter}
                  disabled={dialogMode === "edit" && models.some((model) => model.id === draft.id && model.builtin)}
                  onChange={(event) =>
                    updateDraft({ adapter: event.target.value as Adapter })
                  }
                >
                  {getAdapterOptions(draft.capability).map((adapter) => (
                    <option key={adapter} value={adapter}>
                      {ADAPTER_LABELS[adapter]}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field field-full">
                <span>模型标识</span>
                <input
                  value={draft.model}
                  disabled={dialogMode === "edit" && models.some((model) => model.id === draft.id && model.builtin)}
                  onChange={(event) => updateDraft({ model: event.target.value })}
                  placeholder="例如：doubao-seedance-2-0-260128"
                />
              </label>

              <label className="field field-full">
                <span>baseURL</span>
                <input
                  value={draft.baseUrl}
                  onChange={(event) => updateDraft({ baseUrl: event.target.value })}
                  placeholder="例如：https://ai.ai666.net"
                />
              </label>

              <label className="field field-full">
                <span>API Key</span>
                <input
                  type="password"
                  value={draft.apiKey}
                  onChange={(event) => updateDraft({ apiKey: event.target.value })}
                  placeholder="输入当前模型可用密钥"
                />
              </label>

              <label className="field field-full">
                <span>模型标识覆盖</span>
                <input
                  value={draft.modelNameOverride}
                  onChange={(event) =>
                    updateDraft({ modelNameOverride: event.target.value })
                  }
                  placeholder={draft.model || "可选：从获取模型列表结果中填入"}
                />
              </label>
            </div>

            {draftModelListState?.result ? (
              <div className="settings-dialog-models">
                <div className="available-model-list">
                  {draftModelListState.result.models
                    .slice(0, 18)
                    .map((modelId) => (
                      <button
                        key={modelId}
                        type="button"
                        className="chip-button model-id-chip"
                        onClick={() =>
                          updateDraft({ modelNameOverride: modelId })
                        }
                      >
                        {modelId}
                      </button>
                    ))}
                </div>
              </div>
            ) : null}

            <div className="settings-dialog-actions">
              <button
                type="button"
                className="button-secondary"
                onClick={() =>
                  handleFetchModels(
                    {
                      id: draft.id,
                      name: draft.name || "临时模型",
                      vendor: draft.vendor || "自定义",
                      capability: draft.capability,
                      adapter: draft.adapter,
                      model: draft.model || draft.modelNameOverride || "model",
                      description: draft.description || "临时配置",
                      builtin: false,
                    },
                    {
                      baseUrl: draft.baseUrl,
                      apiKey: draft.apiKey,
                      modelNameOverride: draft.modelNameOverride,
                    },
                  )
                }
              >
                <IconText icon={ListChecks}>获取模型列表</IconText>
              </button>
              <button
                type="button"
                className="button-secondary"
                onClick={() =>
                  handleTestModel(
                    {
                      id: draft.id,
                      name: draft.name || "临时模型",
                      vendor: draft.vendor || "自定义",
                      capability: draft.capability,
                      adapter: draft.adapter,
                      model: draft.model || draft.modelNameOverride || "model",
                      description: draft.description || "临时配置",
                      builtin: false,
                    },
                    {
                      baseUrl: draft.baseUrl,
                      apiKey: draft.apiKey,
                      modelNameOverride: draft.modelNameOverride,
                    },
                  )
                }
              >
                <IconText icon={Send}>测速</IconText>
              </button>
              <button type="button" className="button-secondary" onClick={closeDialog}>
                取消
              </button>
              <button type="button" disabled={!canSave} onClick={handleSaveDialog}>
                保存
              </button>
            </div>

            {draftModelListState?.error ? (
              <div className="inline-message inline-danger">
                {draftModelListState.error}
              </div>
            ) : null}

            {draftTestState?.error ? (
              <div className="inline-message inline-danger">
                {draftTestState.error}
              </div>
            ) : null}

            {draftTestState?.result ? (
              <div className="settings-dialog-debug">
                <JsonViewer
                  title="测速结果"
                  value={draftTestState.result.raw}
                />
              </div>
            ) : null}
          </section>
        </div>
      ) : null}
    </>
  );
}
