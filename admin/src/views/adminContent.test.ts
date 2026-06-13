import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  fetchAdminRecords,
  fetchAuditLogs,
  fetchCreditSettings,
  fetchPromptTemplates,
  fetchPromptTemplateModelStatus,
  fetchPromptTemplateVersions,
  runUserMergeMaintenance,
  saveCreditSettings,
  savePromptTemplate,
  testPromptTemplate,
} from '@/api/admin';
import { setAdminCsrfToken } from '@/api/http';
import type { AdminCreationRecord, Capability, PromptTemplate } from '@/types';
import {
  auditRowClassName,
  buildAuditLogQuery,
  buildAuditLogSummary,
  buildAuditTargetScope,
  createAuditLogFilters,
  TARGET_TYPE_OPTIONS,
} from './auditLogsState';
import {
  buildPromptTemplateSavePayload,
  buildPromptTemplateTestSamples,
  createPromptTemplateForm,
} from './promptCenterState';
import {
  canExportVisibleRecords,
  createRecordsExportState,
  createRecordsState,
  recordStatusLabel,
  renderSafeMarkdown,
  visibleRecordExportQuery,
  type RecordFilterPreset,
} from './recordsState';

function okJson(payload: unknown) {
  return Response.json(payload);
}

describe('admin content api client', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    setAdminCsrfToken('');
  });

  it('loads and saves prompt templates', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => okJson({
      templates: [{ id: 'tpl_1', capability: 'image', name: '图片优化' }],
      template: { id: 'tpl_1', capability: 'image', name: '图片优化' },
      prompt: '优化后的提示词',
    }));
    vi.stubGlobal('fetch', fetchMock);
    setAdminCsrfToken('csrf-token');

    await fetchPromptTemplates('image');
    await savePromptTemplate('tpl_1', { name: '图片优化', enabled: true });
    await testPromptTemplate({ capability: 'image', content: '{{prompt}}', prompt: '生成车' });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/admin/prompt-templates?capability=image',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/admin/prompt-templates/tpl_1',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ name: '图片优化', enabled: true }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/admin/prompt-templates/test',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ capability: 'image', content: '{{prompt}}', prompt: '生成车' }),
      }),
    );
    for (const call of fetchMock.mock.calls.slice(1)) {
      const headers = (call[1] as RequestInit).headers as Headers;
      expect(headers.get('X-CSRF-Token')).toBe('csrf-token');
    }
  });

  it('loads prompt template versions, model status, and posts multi-sample tests', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/versions')) {
        return okJson({ versions: [{ id: 'ptv_1', version: 2, content: 'v2 {{prompt}}' }] });
      }
      if (url.includes('/model-status')) {
        return okJson({ models: [{ modelGroupId: 'mdl_1', modelName: 'Image', hasModelTemplate: true }] });
      }
      return okJson({ results: [{ prompt: '生成车', rendered: '优化 生成车' }] });
    });
    vi.stubGlobal('fetch', fetchMock);
    setAdminCsrfToken('csrf-token');

    await fetchPromptTemplateVersions('tpl_1');
    await fetchPromptTemplateModelStatus('image');
    await testPromptTemplate({ capability: 'image', content: '优化 {{prompt}}', prompts: ['生成车'] });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/admin/prompt-templates/tpl_1/versions',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/admin/prompt-templates/model-status?capability=image',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/admin/prompt-templates/test',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ capability: 'image', content: '优化 {{prompt}}', prompts: ['生成车'] }),
      }),
    );
  });

  it('maps record capability to backend collection paths and query filters', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => okJson({ records: [] }));
    vi.stubGlobal('fetch', fetchMock);

    await fetchAdminRecords('text', { keyword: 'hello world' });
    await fetchAdminRecords('image', { userSearch: 'cage', size: '1024x1024', ratio: '16:9', refCount: '2' });
    await fetchAdminRecords('video', { duration: '8', resolution: '720p', mode: 'reference' });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/admin/records/text?keyword=hello+world',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/admin/records/images?userSearch=cage&size=1024x1024&ratio=16%3A9&refCount=2',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/admin/records/videos?duration=8&resolution=720p&mode=reference',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('loads audit logs and updates credit settings', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => okJson({
      logs: [],
      settings: {
        defaults: { text: 0, image: 1, video: 0 },
        signupBonusEnabled: true,
        signupBonusAmount: 5,
      },
    }));
    vi.stubGlobal('fetch', fetchMock);
    setAdminCsrfToken('csrf-token');

    await fetchAuditLogs({
      adminUserId: 'usr_admin',
      risk: 'high',
      targetType: 'user',
      targetId: 'usr_target',
      status: 'success',
      startAt: '2026-06-11T00:00:00.000Z',
      endAt: '2026-06-12T00:00:00.000Z',
      limit: 150,
    });
    await fetchCreditSettings();
    await saveCreditSettings({ defaults: { text: 0, image: 2, video: 8 }, signupBonusAmount: 10 });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/admin/audit-logs?adminUserId=usr_admin&risk=high&targetType=user&targetId=usr_target&status=success&startAt=2026-06-11T00%3A00%3A00.000Z&endAt=2026-06-12T00%3A00%3A00.000Z&limit=150',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/admin/credits/settings',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/admin/credits/settings',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ defaults: { text: 0, image: 2, video: 8 }, signupBonusAmount: 10 }),
      }),
    );
    const headers = (fetchMock.mock.calls[2][1] as RequestInit).headers as Headers;
    expect(headers.get('X-CSRF-Token')).toBe('csrf-token');
  });

  it('runs user merge maintenance through the admin API', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => okJson({
      summary: {
        apply: false,
        groupCount: 1,
        mergedUsers: 1,
        movedRecords: 0,
        groups: [
          {
            identity: 'email:dup@example.com',
            targetUserId: 'usr_target',
            sourceUserIds: ['usr_source'],
            movedRecords: 0,
            roleConflicts: [
              {
                sourceUserId: 'usr_source',
                targetUserId: 'usr_target',
                targetRole: 'operator',
                discardedRole: 'admin',
                resolution: 'kept_target_role',
              },
            ],
          },
        ],
        roleConflictCount: 1,
      },
    }));
    vi.stubGlobal('fetch', fetchMock);
    setAdminCsrfToken('csrf-token');

    const summary = await runUserMergeMaintenance({
      apply: false,
      identityFilter: 'email:dup@example.com',
    });

    expect(summary.groupCount).toBe(1);
    expect(summary.roleConflictCount).toBe(1);
    expect(summary.groups[0].roleConflicts?.[0].discardedRole).toBe('admin');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/admin/maintenance/user-merge',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ apply: false, identityFilter: 'email:dup@example.com' }),
      }),
    );
    const headers = (fetchMock.mock.calls[0][1] as RequestInit).headers as Headers;
    expect(headers.get('X-CSRF-Token')).toBe('csrf-token');
  });
});

describe('records export state', () => {
  it('keeps record export single-flight and resets exporting state after download', async () => {
    let resolveExport!: (blob: Blob) => void;
    const exporter = vi.fn(() => new Promise<Blob>((resolve) => {
      resolveExport = resolve;
    }));
    const downloader = vi.fn();
    const state = createRecordsExportState(exporter, downloader);

    const firstExport = state.exportRecords('image', { status: 'non_success' });
    const secondExport = state.exportRecords('image', { status: 'non_success' });

    expect(state.isExporting.value).toBe(true);
    expect(exporter).toHaveBeenCalledTimes(1);
    await expect(secondExport).resolves.toBe(false);

    const blob = new Blob(['csv'], { type: 'text/csv' });
    resolveExport(blob);
    await expect(firstExport).resolves.toBe(true);

    expect(downloader).toHaveBeenCalledWith(expect.stringMatching(/^records-image-/), blob);
    expect(state.isExporting.value).toBe(false);
  });
});

describe('audit logs state', () => {
  it('builds the audit log query from every visible filter', () => {
    const filters = createAuditLogFilters();
    filters.action = 'update';
    filters.adminUserId = 'usr_admin';
    filters.targetType = 'user';
    filters.targetId = 'usr_target';
    filters.status = 'success';
    filters.risk = 'high';
    filters.dateRange = ['2026-06-11T00:00:00', '2026-06-12T00:00:00'];
    filters.limit = 300;

    expect(buildAuditLogQuery(filters)).toEqual({
      action: 'update',
      adminUserId: 'usr_admin',
      targetType: 'user',
      targetId: 'usr_target',
      status: 'success',
      risk: 'high',
      startAt: '2026-06-11T00:00:00',
      endAt: '2026-06-12T00:00:00',
      limit: 300,
    });
  });

  it('summarizes audit risk and target filters for the operations page', () => {
    const filters = createAuditLogFilters();
    filters.targetType = 'user';
    filters.risk = 'high';

    expect(TARGET_TYPE_OPTIONS.map((item) => item.value)).toEqual([
      '',
      'user',
      'model',
      'prompt_template',
      'credit_settings',
      'maintenance',
      'dashboard',
    ]);
    expect(buildAuditTargetScope(filters)).toBe('user-high');
    expect(buildAuditLogSummary([
      {
        id: 'log_1',
        adminUserId: 'usr_admin',
        action: 'delete_user',
        targetType: 'user',
        targetId: 'usr_1',
        status: 'success',
        riskLevel: 'high',
        summary: {},
        createdAt: '2026-06-11T00:00:00Z',
      },
      {
        id: 'log_2',
        adminUserId: 'usr_admin',
        action: 'save_prompt_template',
        targetType: 'prompt_template',
        targetId: 'tpl_1',
        status: 'success',
        riskLevel: 'medium',
        summary: {},
        createdAt: '2026-06-11T00:01:00Z',
      },
      {
        id: 'log_3',
        adminUserId: 'usr_admin',
        action: 'view_dashboard',
        targetType: 'dashboard',
        targetId: '',
        status: 'error',
        riskLevel: 'high',
        summary: {},
        createdAt: '2026-06-11T00:02:00Z',
      },
    ])).toEqual({
      total: 3,
      highRisk: 2,
      mediumRisk: 1,
      errors: 1,
      targetTypes: 3,
    });
    expect(auditRowClassName({ riskLevel: 'high', status: 'success' })).toBe('audit-row--high-risk');
    expect(auditRowClassName({ riskLevel: 'normal', status: 'error' })).toBe('audit-row--error');
  });
});

describe('prompt center state', () => {
  it('keeps template identity fields locked when building save payload', () => {
    const template: PromptTemplate = {
      id: 'tpl_image',
      capability: 'image',
      modelGroupId: 'model_1',
      templateType: 'prompt_optimize',
      name: '图片模板',
      content: 'old {{prompt}}',
      enabled: true,
    };
    const form = createPromptTemplateForm(template);

    form.capability = 'video';
    form.modelGroupId = 'model_2';
    form.templateType = 'other_template';
    form.name = '新名称';
    form.content = 'new {{prompt}}';
    form.enabled = false;

    expect(buildPromptTemplateSavePayload(template, form)).toEqual({
      capability: 'image',
      modelGroupId: 'model_1',
      templateType: 'prompt_optimize',
      name: '新名称',
      content: 'new {{prompt}}',
      enabled: false,
    });
  });

  it('normalizes multi-sample prompt input', () => {
    expect(buildPromptTemplateTestSamples(' 生成车\\n\\n生成猫\\n生成车 ')).toEqual(['生成车', '生成猫']);
    expect(buildPromptTemplateTestSamples('')).toEqual([]);
  });
});

function makeRecord(id: string, capability: Capability): AdminCreationRecord {
  return {
    id,
    user: null,
    modelName: 'model',
    capability,
    status: 'success',
    prompt: id,
    response: '',
    createdAt: '2026-01-01T00:00:00Z',
    durationMs: 0,
    taskId: '',
    assets: [],
    requestParams: {},
    responseSummary: {},
    errorMessage: '',
  };
}

describe('records state', () => {
  beforeEach(() => {
    const store = new Map<string, string>();
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key: string) => store.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => {
        store.set(key, value);
      }),
      removeItem: vi.fn((key: string) => {
        store.delete(key);
      }),
      clear: vi.fn(() => {
        store.clear();
      }),
    });
  });

  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('keeps the latest capability result when an older request resolves later', async () => {
    let resolveFirst!: (records: AdminCreationRecord[]) => void;
    let resolveSecond!: (records: AdminCreationRecord[]) => void;
    const loader = vi
      .fn()
      .mockImplementationOnce(() => new Promise<AdminCreationRecord[]>((resolve) => {
        resolveFirst = resolve;
      }))
      .mockImplementationOnce(() => new Promise<AdminCreationRecord[]>((resolve) => {
        resolveSecond = resolve;
      }));
    const state = createRecordsState(loader);

    state.capability.value = 'image';
    state.filters.keyword = 'image';
    const firstLoad = state.loadRecords();
    state.capability.value = 'video';
    state.filters.keyword = 'video';
    const secondLoad = state.loadRecords();

    resolveSecond([makeRecord('video-record', 'video')]);
    await secondLoad;
    resolveFirst([makeRecord('image-record', 'image')]);
    await firstLoad;

    expect(state.records.value.map((record) => record.id)).toEqual(['video-record']);
    expect(state.lastLoadedCapability.value).toBe('video');
    expect(state.lastLoadedQuery.value).toEqual(expect.objectContaining({ keyword: 'video' }));
    expect(state.isLoading.value).toBe(false);
  });

  it('passes image size filters and supports saved filter presets per capability', async () => {
    const loader = vi.fn(async () => [makeRecord('image-record', 'image')]);
    const state = createRecordsState(loader);

    state.capability.value = 'image';
    state.filters.keyword = 'poster';
    state.filters.size = '1024x1024';
    state.filters.ratio = '16:9';
    state.filters.refCount = '2';

    await state.loadRecords();
    const preset = state.saveCurrentFilterPreset('SU7 references');
    state.filters.keyword = '';
    state.filters.size = '';
    state.filters.ratio = '';
    state.filters.refCount = '';
    state.applyFilterPreset(preset.id);

    expect(loader).toHaveBeenCalledWith('image', expect.objectContaining({
      keyword: 'poster',
      size: '1024x1024',
      ratio: '16:9',
      refCount: '2',
    }));
    expect(state.filters).toMatchObject({
      keyword: 'poster',
      size: '1024x1024',
      ratio: '16:9',
      refCount: '2',
    });
    expect(state.savedFilterPresets.value).toEqual<RecordFilterPreset[]>([
      expect.objectContaining({
        name: 'SU7 references',
        capability: 'image',
        filters: expect.objectContaining({ size: '1024x1024' }),
      }),
    ]);
  });

  it('applies dashboard record query filters before loading records', async () => {
    const loader = vi.fn(async () => [makeRecord('image-error', 'image')]);
    const state = createRecordsState(loader);

    state.applyRouteQueryFilters({
      capability: 'image',
      userId: 'user-1',
      modelGroupId: 'model-1',
      status: 'error',
    });
    await state.loadRecords();

    expect(state.capability.value).toBe('image');
    expect(state.filters.userId).toBe('user-1');
    expect(state.filters.modelGroupId).toBe('model-1');
    expect(state.filters.status).toBe('error');
    expect(loader).toHaveBeenCalledWith('image', expect.objectContaining({
      userId: 'user-1',
      modelGroupId: 'model-1',
      status: 'error',
    }));
  });

  it('exports records with the last successful load query instead of unsaved filter drafts', async () => {
    const loader = vi.fn(async () => [makeRecord('image-record', 'image')]);
    const state = createRecordsState(loader);

    state.capability.value = 'image';
    state.filters.keyword = 'poster';
    state.filters.size = '1024x1024';
    state.filters.ratio = '16:9';
    await state.loadRecords();
    state.filters.keyword = 'draft';
    state.filters.size = '512x512';
    state.filters.ratio = '1:1';
    state.capability.value = 'video';

    expect(state.records.value.map((record) => record.id)).toEqual(['image-record']);
    expect(visibleRecordExportQuery(state.lastLoadedCapability.value, state.lastLoadedQuery.value)).toEqual({
      capability: 'image',
      query: expect.objectContaining({
        keyword: 'poster',
        size: '1024x1024',
        ratio: '16:9',
      }),
    });
  });

  it('disables visible record export while data is loading', () => {
    expect(canExportVisibleRecords({
      canExportRecords: true,
      recordCount: 3,
      isExporting: false,
      isLoading: true,
    })).toBe(false);
    expect(canExportVisibleRecords({
      canExportRecords: true,
      recordCount: 3,
      isExporting: false,
      isLoading: false,
    })).toBe(true);
  });

  it('labels dashboard non-success record filters clearly', () => {
    expect(recordStatusLabel('non_success')).toBe('未成功');
    expect(recordStatusLabel('processing')).toBe('处理中');
    expect(recordStatusLabel('error')).toBe('失败');
  });

  it('renders safe markdown without preserving raw html tags', () => {
    expect(renderSafeMarkdown('## 标题\n**重点** <script>alert(1)</script>\n- 项目')).toContain('<h3>标题</h3>');
    expect(renderSafeMarkdown('## 标题\n**重点** <script>alert(1)</script>\n- 项目')).toContain('<strong>重点</strong>');
    expect(renderSafeMarkdown('## 标题\n**重点** <script>alert(1)</script>\n- 项目')).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(renderSafeMarkdown('## 标题\n**重点** <script>alert(1)</script>\n- 项目')).not.toContain('<script>');
  });
});
