import { readFileSync } from 'node:fs';

import { afterEach, describe, expect, it, vi } from 'vitest';
import { nextTick } from 'vue';

import {
  adminModelPath,
  fetchAdminModels,
  fetchAdminModelHealth,
  publishAdminModel,
  removeUnavailableAdminModels,
  runAdminBatchModelHealthCheck,
  runAdminModelHealthCheck,
  unpublishAdminModel,
  updateAdminModel,
  updateModelCreditPricing,
} from '@/api/admin';
import { setAdminCsrfToken } from '@/api/http';
import type { AdminModel } from '@/types';
import {
  buildAdminModelUpdatePayload,
  batchHealthSummary,
  createEditForm,
  createModelCenterState,
  createModelHealthState,
  displayModelDescription,
  nextActiveModelAfterRemoval,
  parseDefaultParameters,
  selectedIdsAfterRemoval,
  serializePublicTags,
} from './modelCenterState';

function okJson(payload: unknown) {
  return Response.json(payload);
}

function makeModel(overrides: Partial<AdminModel> = {}): AdminModel {
  return {
    id: 'model-1',
    name: 'gpt-image',
    vendor: 'openai',
    capability: 'image',
    adapter: 'openai',
    description: 'Image model',
    baseUrl: 'https://api.example.com',
    primaryModelName: 'gpt-image-1',
    isPublic: false,
    canEdit: true,
    publicDisplayName: '图像生成',
    publicDescription: '生成高质量图片',
    inputHint: '描述你想要的画面',
    iconUrl: 'https://cdn.example.com/icon.png',
    publicTags: ['图像', '创作'],
    promptOptimizeEnabled: true,
    defaultParameters: { size: '1024x1024' },
    creditPrice: 12,
    creditPriceSource: 'custom',
    ...overrides,
  };
}

describe('model center api client', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    setAdminCsrfToken('');
  });

  it('encodes model list query parameters and unwraps models', async () => {
    const fetchMock = vi.fn(async () => okJson({ models: [makeModel()] }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchAdminModels({
      capability: 'text',
      publicState: 'public',
      search: '图像 模型',
    })).resolves.toHaveLength(1);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/admin/models?capability=text&search=%E5%9B%BE%E5%83%8F+%E6%A8%A1%E5%9E%8B&publicState=public',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('uses the expected model write endpoints and payloads', async () => {
    const fetchMock = vi.fn(async () => okJson({ ok: true }));
    vi.stubGlobal('fetch', fetchMock);
    setAdminCsrfToken('csrf-token');

    await publishAdminModel('model-1');
    await unpublishAdminModel('model-2');
    await updateAdminModel('model-3', { publicDisplayName: '中文名称' });
    await updateModelCreditPricing('model-4', { price: 8 });
    await updateModelCreditPricing('model-5', { useDefault: true });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/admin/models/model-1/publish',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/admin/models/model-2/unpublish',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/admin/models/model-3',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ publicDisplayName: '中文名称' }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      '/api/admin/models/model-4/credit-pricing',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ price: 8 }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      '/api/admin/models/model-5/credit-pricing',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ useDefault: true }),
      }),
    );
  });

  it('fetches and runs model health checks through admin endpoints', async () => {
    const health = {
      modelGroupId: 'model-1',
      latest: { status: 'success', message: '连接正常。' },
      recent: [],
      failureRate: 0,
    };
    const fetchMock = vi.fn(async () => okJson({ health }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchAdminModelHealth('model-1')).resolves.toEqual(health);
    await expect(runAdminModelHealthCheck('model-1')).resolves.toEqual(health);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/admin/models/model-1/health',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/admin/models/model-1/health-check',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('documents the URL-safe model id contract', () => {
    expect(adminModelPath('mdl_abc123')).toBe('/api/admin/models/mdl_abc123');
    expect(() => adminModelPath('mdl/abc123')).toThrow('模型 ID 格式无效。');
  });

  it('uses backend batch maintenance endpoints with selected model ids', async () => {
    const batchHealth = {
      results: [
        { modelId: 'model-1', status: 'success', health: { latest: { status: 'success' } } },
        { modelId: 'model-2', status: 'failed', health: { latest: { status: 'failed' } } },
      ],
    };
    const removeResult = {
      removedIds: ['model-2'],
      skipped: [{ modelId: 'model-1', reason: 'latest_health_success' }],
      models: [makeModel({ id: 'model-1' })],
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(okJson(batchHealth))
      .mockResolvedValueOnce(okJson(removeResult));
    vi.stubGlobal('fetch', fetchMock);

    await expect(runAdminBatchModelHealthCheck(['model-1', 'model-2'])).resolves.toEqual(batchHealth);
    await expect(removeUnavailableAdminModels(['model-1', 'model-2'])).resolves.toEqual(removeResult);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/admin/models/batch-health-check',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ modelIds: ['model-1', 'model-2'] }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/admin/models/remove-unavailable',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ modelIds: ['model-1', 'model-2'] }),
      }),
    );
  });

  it('summarizes batch health results and exposes the active model health', () => {
    const results = [
      { modelId: 'model-1', status: 'success', health: { modelGroupId: 'model-1', latest: { status: 'success' } } },
      { modelId: 'model-2', status: 'failed', health: { modelGroupId: 'model-2', latest: { status: 'failed' } } },
      { modelId: 'model-3', status: 'error', error: { statusCode: 429, message: 'too frequent' } },
    ];

    const summary = batchHealthSummary(results, 'model-2');

    expect(summary.successCount).toBe(1);
    expect(summary.failedCount).toBe(2);
    expect(summary.activeHealth).toEqual({ modelGroupId: 'model-2', latest: { status: 'failed' } });
  });

  it('keeps model selection and active drawer consistent after removing unavailable models', () => {
    const remaining = [
      makeModel({ id: 'model-1' }),
      makeModel({ id: 'model-3' }),
    ];

    expect(selectedIdsAfterRemoval(['model-1', 'model-2', 'model-3'], remaining)).toEqual(['model-1', 'model-3']);
    expect(nextActiveModelAfterRemoval('model-2', remaining)).toBeNull();
    expect(nextActiveModelAfterRemoval('model-3', remaining)?.id).toBe('model-3');
  });

  it('keeps Element Plus table selection reserved by row key after data refreshes', () => {
    const source = readFileSync(new URL('./ModelCenterView.vue', import.meta.url), 'utf8');

    expect(source).toContain('row-key="id"');
    expect(source).toContain('reserve-selection');
  });

  it('uses backend error messages when loading health fails', async () => {
    const healthState = createModelHealthState(async () => {
      throw new Error('模型不存在。');
    });

    await healthState.loadHealth('missing-model');

    expect(healthState.errorMessage.value).toBe('模型不存在。');
    expect(healthState.activeHealth.value).toBeNull();
  });

  it('clears health check loading when active model changes during a check', async () => {
    let resolveCheck: (value: { modelGroupId: string; latest: { status: string } }) => void = () => {};
    const healthState = createModelHealthState(
      async (modelId) => ({
        modelGroupId: modelId,
        latest: { status: 'success' },
        recent: [],
        failureRate: 0,
      }),
      async () => new Promise((resolve) => {
        resolveCheck = resolve;
      }),
    );

    const checkRequest = healthState.runHealthCheck('model-a');
    expect(healthState.isCheckingHealth.value).toBe(true);

    await healthState.loadHealth('model-b');
    resolveCheck({ modelGroupId: 'model-a', latest: { status: 'failed' } });
    await checkRequest;

    expect(healthState.isCheckingHealth.value).toBe(false);
    expect(healthState.activeHealth.value?.modelGroupId).toBe('model-b');
  });

  it('clears health messages before opening another model', async () => {
    const healthState = createModelHealthState(
      async () => {
        throw new Error('模型不存在。');
      },
    );

    await healthState.loadHealth('missing-model');
    expect(healthState.errorMessage.value).toBe('模型不存在。');

    healthState.resetHealthState();

    expect(healthState.activeHealth.value).toBeNull();
    expect(healthState.errorMessage.value).toBe('');
    expect(healthState.noticeMessage.value).toBe('');
  });

  it('immediately releases health check loading when resetting for another model', async () => {
    let resolveCheck: (value: { modelGroupId: string; latest: { status: string } }) => void = () => {};
    const healthState = createModelHealthState(
      async (modelId) => ({
        modelGroupId: modelId,
        latest: { status: 'success' },
        recent: [],
        failureRate: 0,
      }),
      async () => new Promise((resolve) => {
        resolveCheck = resolve;
      }),
    );

    const checkRequest = healthState.runHealthCheck('model-a');
    expect(healthState.isCheckingHealth.value).toBe(true);

    healthState.resetHealthState();

    expect(healthState.isCheckingHealth.value).toBe(false);
    resolveCheck({ modelGroupId: 'model-a', latest: { status: 'success' } });
    await checkRequest;
    expect(healthState.activeHealth.value).toBeNull();
    expect(healthState.noticeMessage.value).toBe('');
  });
});

describe('model center state', () => {
  it('filters models by capability, public state, and search text', async () => {
    const state = createModelCenterState(async () => [
      makeModel({ id: 'public-image', name: 'Image Pro', isPublic: true, capability: 'image' }),
      makeModel({ id: 'private-text', name: 'Text Pro', isPublic: false, capability: 'text' }),
    ]);

    await state.loadModels();
    state.filters.capability = 'image';
    state.filters.publicState = 'public';
    state.filters.search = 'pro';
    await nextTick();

    expect(state.filteredModels.value.map((model) => model.id)).toEqual(['public-image']);
  });

  it('builds save payloads from editable model fields', () => {
    const payload = buildAdminModelUpdatePayload({
      publicDisplayName: '精选模型',
      publicDescription: ' 面向公开使用 ',
      publicAccentColor: ' #C857F1 ',
      inputHint: '输入创作需求',
      iconUrl: 'https://cdn.example.com/model.png',
      publicTagsText: '绘画,  图片\n推荐',
      promptOptimizeEnabled: false,
      defaultParametersText: '{ "temperature": 0.7 }',
    });

    expect(payload).toEqual({
      publicDisplayName: '精选模型',
      publicDescription: '面向公开使用',
      publicAccentColor: '#C857F1',
      inputHint: '输入创作需求',
      iconUrl: 'https://cdn.example.com/model.png',
      publicTags: ['绘画', '图片', '推荐'],
      promptOptimizeEnabled: false,
      defaultParameters: { temperature: 0.7 },
    });
  });

  it('preserves the public accent color in the edit form and save payload', () => {
    const form = createEditForm(makeModel({ publicAccentColor: '#FF6B8A' }));
    const payload = buildAdminModelUpdatePayload(form);

    expect(form.publicAccentColor).toBe('#FF6B8A');
    expect(payload.publicAccentColor).toBe('#FF6B8A');
  });

  it('validates default parameter JSON before saving', () => {
    expect(() => parseDefaultParameters('{bad json}')).toThrow('默认参数必须是合法的 JSON 对象');
    expect(serializePublicTags([' 图像 ', '', '创作'])).toBe('图像, 创作');
  });

  it('hides broken placeholder descriptions in model detail panels', () => {
    expect(displayModelDescription(makeModel({ description: '??????' }))).toBe('暂无说明');
    expect(displayModelDescription(makeModel({ description: '????????????????Agent????????????????' }))).toBe('暂无说明');
    expect(displayModelDescription(makeModel({ description: '高质量图片生成模型' }))).toBe('高质量图片生成模型');
    expect(displayModelDescription(makeModel({ description: '' }))).toBe('暂无说明');
  });

  it('ignores stale health responses when active model changes', async () => {
    let resolveModelA: (value: { modelGroupId: string; latest: { status: string } }) => void = () => {};
    const healthState = createModelHealthState(async (modelId) => {
      if (modelId === 'model-a') {
        return new Promise((resolve) => {
          resolveModelA = resolve;
        });
      }
      return { modelGroupId: 'model-b', latest: { status: 'success' }, recent: [], failureRate: 0 };
    });

    const modelARequest = healthState.loadHealth('model-a');
    const modelBRequest = healthState.loadHealth('model-b');
    resolveModelA({ modelGroupId: 'model-a', latest: { status: 'failed' } });
    await Promise.all([modelARequest, modelBRequest]);

    expect(healthState.activeHealth.value?.modelGroupId).toBe('model-b');
  });

  it('uses backend error messages when running health checks fails', async () => {
    const healthState = createModelHealthState(async () => {
      throw new Error('模型不存在。');
    });

    await healthState.runHealthCheck('missing-model');

    expect(healthState.errorMessage.value).toBe('模型不存在。');
    expect(healthState.activeHealth.value).toBeNull();
  });
});
