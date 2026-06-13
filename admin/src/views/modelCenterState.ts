import { computed, reactive, ref, type Ref } from 'vue';

import { fetchAdminModels } from '@/api/admin';
import type {
  AdminBatchModelHealthCheckResult,
  AdminModel,
  AdminModelHealth,
  AdminModelListQuery,
  AdminModelUpdate,
} from '@/types';

export const MODEL_CENTER_TITLE = '模型中心';

export const capabilityOptions = [
  { label: '全部类型', value: 'all' },
  { label: '文本', value: 'text' },
  { label: '图像', value: 'image' },
  { label: '视频', value: 'video' },
] as const;

export const publicStateOptions = [
  { label: '全部状态', value: 'all' },
  { label: '已公用', value: 'public' },
  { label: '未公用', value: 'private' },
] as const;

export interface ModelCenterFilters {
  capability: string;
  publicState: string;
  search: string;
}

export interface ModelEditForm {
  publicDisplayName: string;
  publicDescription: string;
  inputHint: string;
  iconUrl: string;
  publicTagsText: string;
  promptOptimizeEnabled: boolean;
  defaultParametersText: string;
}

export function capabilityLabel(value: string): string {
  return capabilityOptions.find((item) => item.value === value)?.label ?? (value || '未知');
}

export function publicStateLabel(model: Pick<AdminModel, 'isPublic'>): string {
  return model.isPublic ? '已公用' : '未公用';
}

export function serializePublicTags(tags: string[] = []): string {
  return tags.map((tag) => tag.trim()).filter(Boolean).join(', ');
}

export function parsePublicTags(value: string): string[] {
  return value
    .split(/[\n,，]/)
    .map((tag) => tag.trim())
    .filter(Boolean);
}

export function parseDefaultParameters(value: string): Record<string, unknown> {
  const cleanValue = value.trim();
  if (!cleanValue) {
    return {};
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(cleanValue);
  } catch {
    throw new Error('默认参数必须是合法的 JSON 对象');
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('默认参数必须是合法的 JSON 对象');
  }
  return parsed as Record<string, unknown>;
}

export function createEditForm(model: AdminModel): ModelEditForm {
  return {
    publicDisplayName: model.publicDisplayName || '',
    publicDescription: model.publicDescription || '',
    inputHint: model.inputHint || '',
    iconUrl: model.iconUrl || '',
    publicTagsText: serializePublicTags(model.publicTags),
    promptOptimizeEnabled: model.promptOptimizeEnabled,
    defaultParametersText: JSON.stringify(model.defaultParameters || {}, null, 2),
  };
}

export function buildAdminModelUpdatePayload(form: ModelEditForm): AdminModelUpdate {
  return {
    publicDisplayName: form.publicDisplayName.trim(),
    publicDescription: form.publicDescription.trim(),
    inputHint: form.inputHint.trim(),
    iconUrl: form.iconUrl.trim(),
    publicTags: parsePublicTags(form.publicTagsText),
    promptOptimizeEnabled: form.promptOptimizeEnabled,
    defaultParameters: parseDefaultParameters(form.defaultParametersText),
  };
}

export function friendlyModelCenterError(error: unknown, fallback: string): string {
  return error instanceof Error && error.message.trim() ? error.message.trim() : fallback;
}

export function batchHealthSummary(
  results: AdminBatchModelHealthCheckResult[],
  activeModelId = '',
): { successCount: number; failedCount: number; activeHealth: AdminModelHealth | null } {
  const successCount = results.filter((item) => item.status === 'success').length;
  const failedCount = results.length - successCount;
  const activeResult = activeModelId
    ? results.find((item) => item.modelId === activeModelId)
    : undefined;
  return {
    successCount,
    failedCount,
    activeHealth: activeResult?.health || null,
  };
}

export function selectedIdsAfterRemoval(selectedIds: string[], remainingModels: Pick<AdminModel, 'id'>[]): string[] {
  const remainingIds = new Set(remainingModels.map((model) => model.id));
  return selectedIds.filter((id) => remainingIds.has(id));
}

export function nextActiveModelAfterRemoval(
  activeModelId: string,
  remainingModels: AdminModel[],
): AdminModel | null {
  if (!activeModelId) {
    return null;
  }
  return remainingModels.find((model) => model.id === activeModelId) || null;
}

export function createModelHealthState(
  fetcher: (modelId: string) => Promise<AdminModelHealth>,
  runner: (modelId: string) => Promise<AdminModelHealth> = fetcher,
) {
  const activeHealth = ref<AdminModelHealth | null>(null);
  const isCheckingHealth = ref(false);
  const errorMessage = ref('');
  const noticeMessage = ref('');
  let latestHealthResultRequestId = 0;
  let latestCheckRequestId = 0;

  async function loadHealth(modelId: string) {
    const requestId = latestHealthResultRequestId + 1;
    latestHealthResultRequestId = requestId;
    try {
      const health = await fetcher(modelId);
      if (requestId === latestHealthResultRequestId) {
        activeHealth.value = health;
        errorMessage.value = '';
      }
    } catch (error) {
      if (requestId === latestHealthResultRequestId) {
        activeHealth.value = null;
        errorMessage.value = friendlyModelCenterError(error, '模型健康状态暂时无法加载，请稍后重试。');
      }
    }
  }

  async function runHealthCheck(modelId: string) {
    const resultRequestId = latestHealthResultRequestId + 1;
    latestHealthResultRequestId = resultRequestId;
    const checkRequestId = latestCheckRequestId + 1;
    latestCheckRequestId = checkRequestId;
    isCheckingHealth.value = true;
    errorMessage.value = '';
    noticeMessage.value = '';
    try {
      const health = await runner(modelId);
      if (resultRequestId !== latestHealthResultRequestId) {
        return;
      }
      activeHealth.value = health;
      const latest = health.latest;
      const latestStatus = String(
        latest && typeof latest === 'object' ? (latest as Record<string, unknown>).status || '' : '',
      );
      noticeMessage.value = latestStatus === 'success' ? '模型连接测试成功。' : '模型连接测试完成，请查看健康状态。';
    } catch (error) {
      if (resultRequestId === latestHealthResultRequestId) {
        activeHealth.value = null;
        errorMessage.value = friendlyModelCenterError(error, '模型连接测试失败，请稍后重试。');
      }
    } finally {
      if (checkRequestId === latestCheckRequestId) {
        isCheckingHealth.value = false;
      }
    }
  }

  function resetHealthState() {
    latestHealthResultRequestId += 1;
    latestCheckRequestId += 1;
    activeHealth.value = null;
    isCheckingHealth.value = false;
    errorMessage.value = '';
    noticeMessage.value = '';
  }

  return {
    activeHealth,
    isCheckingHealth,
    errorMessage,
    noticeMessage,
    loadHealth,
    runHealthCheck,
    resetHealthState,
  };
}

function createQuery(filters: ModelCenterFilters): AdminModelListQuery {
  return {
    capability: filters.capability === 'all' ? '' : filters.capability,
    publicState: filters.publicState === 'all' ? '' : filters.publicState,
    search: filters.search.trim(),
  };
}

function matchesSearch(model: AdminModel, search: string): boolean {
  const keyword = search.trim().toLowerCase();
  if (!keyword) {
    return true;
  }
  return [
    model.name,
    model.vendor,
    model.description,
    model.publicDisplayName,
    model.primaryModelName,
    ...model.publicTags,
  ].some((value) => String(value || '').toLowerCase().includes(keyword));
}

export function createModelCenterState(
  fetcher: (query: AdminModelListQuery) => Promise<AdminModel[]> = fetchAdminModels,
  models = ref<AdminModel[]>([]),
  isLoading = ref(false),
  errorMessage = ref(''),
) {
  const filters = reactive<ModelCenterFilters>({
    capability: 'all',
    publicState: 'all',
    search: '',
  });

  const selectedIds = ref<string[]>([]);
  const noticeMessage = ref('');
  let latestRequestId = 0;

  const filteredModels = computed(() => models.value.filter((model) => {
    if (filters.capability !== 'all' && model.capability !== filters.capability) {
      return false;
    }
    if (filters.publicState === 'public' && !model.isPublic) {
      return false;
    }
    if (filters.publicState === 'private' && model.isPublic) {
      return false;
    }
    return matchesSearch(model, filters.search);
  }));

  const selectedModels = computed(() => models.value.filter((model) => selectedIds.value.includes(model.id)));
  const selectedEditableModels = computed(() => selectedModels.value.filter((model) => model.canEdit));
  const canBatchPublish = computed(() => selectedEditableModels.value.some((model) => !model.isPublic));
  const canBatchUnpublish = computed(() => selectedEditableModels.value.some((model) => model.isPublic));

  function replaceModel(updated: AdminModel) {
    models.value = models.value.map((model) => (model.id === updated.id ? updated : model));
  }

  function setSelected(ids: string[]) {
    selectedIds.value = [...new Set(ids)];
  }

  async function loadModels() {
    const requestId = latestRequestId + 1;
    latestRequestId = requestId;
    isLoading.value = true;
    errorMessage.value = '';
    try {
      const nextModels = await fetcher(createQuery(filters));
      if (requestId === latestRequestId) {
        models.value = nextModels;
        selectedIds.value = selectedIds.value.filter((id) => nextModels.some((model) => model.id === id));
      }
    } catch {
      if (requestId === latestRequestId) {
        errorMessage.value = '模型列表暂时无法加载，请稍后重试。';
      }
    } finally {
      if (requestId === latestRequestId) {
        isLoading.value = false;
      }
    }
  }

  return {
    filters,
    models: models as Ref<AdminModel[]>,
    filteredModels,
    selectedIds,
    selectedModels,
    selectedEditableModels,
    canBatchPublish,
    canBatchUnpublish,
    isLoading,
    errorMessage,
    noticeMessage,
    setSelected,
    replaceModel,
    loadModels,
  };
}
