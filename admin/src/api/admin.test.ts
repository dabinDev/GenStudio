import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  exportAdminRecords,
  exportAuditLogs,
  fetchAdminRecordDetail,
  fetchAdminPermissions,
  fetchAssetSyncSettings,
  fetchCsrfToken,
  fetchCurrentUser,
  logoutAdmin,
  previewAssetSync,
  retryFailedAssetSync,
  runAssetSync,
  saveAssetSyncSettings,
} from './admin';
import {
  AdminApiError,
  adminRequest,
  extractApiMessage,
  setAdminCsrfToken,
} from './http';

describe('admin api client', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    setAdminCsrfToken('');
  });

  it('extracts messages from supported API error shapes', () => {
    expect(extractApiMessage({ detail: { message: '没有权限' } })).toBe('没有权限');
    expect(extractApiMessage({ message: '请先登录' })).toBe('请先登录');
    expect(extractApiMessage('<html>bad gateway</html>')).toBe('请求失败，请稍后重试。');
  });

  it('throws a normalized error for html failures', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('<html>server error</html>', {
        status: 500,
        headers: { 'content-type': 'text/html' },
      })),
    );

    await expect(adminRequest('/api/admin/broken')).rejects.toMatchObject({
      status: 500,
      message: '请求失败，请稍后重试。',
    });
    await expect(adminRequest('/api/admin/broken')).rejects.toBeInstanceOf(AdminApiError);
  });

  it('sends csrf token for mutating requests', async () => {
    const fetchMock = vi.fn(async () => new Response('{}', {
      status: 200,
      headers: { 'content-type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    setAdminCsrfToken('csrf-token');
    await adminRequest('/api/auth/logout', { method: 'POST' });

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.credentials).toBe('include');
    expect(init.method).toBe('POST');
    expect((init.headers as Headers).get('X-CSRF-Token')).toBe('csrf-token');
  });

  it('wraps current admin endpoints', async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url === '/api/auth/me') {
        return Response.json({ user: { id: 'u1', email: 'admin@example.com', isAdmin: true } });
      }
      if (url === '/api/auth/csrf') {
        return Response.json({ csrfToken: 'csrf-value' });
      }
      if (url === '/api/admin/permissions/me') {
        return Response.json({ role: 'super_admin', permissions: ['model:view'] });
      }
      if (url === '/api/auth/logout') {
        return Response.json({ ok: true });
      }
      return new Response('not found', { status: 404 });
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchCurrentUser()).resolves.toMatchObject({ id: 'u1', isAdmin: true });
    await expect(fetchCsrfToken()).resolves.toBe('csrf-value');
    await expect(fetchAdminPermissions()).resolves.toEqual({
      role: 'super_admin',
      permissions: ['model:view'],
    });
    await expect(logoutAdmin()).resolves.toBeUndefined();
  });

  it('fetches record detail by message id from the backend detail contract', async () => {
    const detail = {
      id: 'msg_123',
      conversationId: 'conv_1',
      conversationTitle: 'Launch poster',
      user: null,
      role: 'assistant',
      capability: 'image',
      status: 'success',
      content: 'final content',
      request: { prompt: 'detail prompt' },
      response: { text: 'detail response' },
      errorMessage: '',
      assets: [{ type: 'image', url: 'https://cdn.example.com/detail.png' }],
      timeline: [],
      createdAt: '2026-06-10T00:00:00Z',
    };
    const fetchMock = vi.fn(async () => Response.json({ record: detail }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchAdminRecordDetail('msg_123')).resolves.toEqual(detail);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/admin/records/detail/msg_123',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('exports audit logs through the backend export endpoint', async () => {
    const csv = '日志ID,管理员\r\nlog_1,usr_admin\r\n';
    const fetchMock = vi.fn(async () => new Response(csv, {
      status: 200,
      headers: { 'content-type': 'text/csv;charset=utf-8' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    const result = await exportAuditLogs({ targetType: 'credit_settings', risk: 'high', limit: 300 });

    expect(await result.text()).toBe(csv);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/admin/audit-logs/export?targetType=credit_settings&risk=high&limit=300',
      expect.objectContaining({ method: 'GET', credentials: 'include' }),
    );
  });

  it('exports creation records through the backend export endpoint', async () => {
    const csv = '消息ID,用户\r\nmsg_1,user@example.com\r\n';
    const fetchMock = vi.fn(async () => new Response(csv, {
      status: 200,
      headers: { 'content-type': 'text/csv;charset=utf-8' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    const result = await exportAdminRecords('image', { status: 'non_success', modelGroupId: 'mdl_1' });

    expect(await result.text()).toBe(csv);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/admin/records/images/export?status=non_success&modelGroupId=mdl_1',
      expect.objectContaining({ method: 'GET', credentials: 'include' }),
    );
  });

  it('wraps all asset synchronization controls and protects mutations with csrf', async () => {
    const payload = {
      settings: {
        enabled: true,
        intervalSeconds: 60,
        batchSize: 8,
        localTtlHours: 24,
        localTtlFixed: true,
        minIntervalSeconds: 15,
        maxIntervalSeconds: 3600,
        minBatchSize: 1,
        maxBatchSize: 100,
        lastRun: {},
        lastAutoRun: {},
      },
      summary: {
        totalAssets: 12,
        totalBytes: 4096,
        localBytes: 1024,
        eligibleAssets: 2,
        statusCounts: { r2_synced: 9, local_pending: 2, sync_failed: 1 },
        failureCount: 1,
        failures: [],
      },
      result: { reset: 1 },
    };
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => Response.json(payload));
    vi.stubGlobal('fetch', fetchMock);
    setAdminCsrfToken('csrf-token');

    await fetchAssetSyncSettings();
    await saveAssetSyncSettings({ enabled: false, intervalSeconds: 90, batchSize: 4 });
    await previewAssetSync();
    await runAssetSync();
    await retryFailedAssetSync();

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/admin/asset-sync/settings',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/admin/asset-sync/settings',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ enabled: false, intervalSeconds: 90, batchSize: 4 }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/admin/asset-sync/preview',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      '/api/admin/asset-sync/run',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({}) }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      '/api/admin/asset-sync/retry-failed',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({}) }),
    );
    for (const call of [fetchMock.mock.calls[1], fetchMock.mock.calls[3], fetchMock.mock.calls[4]]) {
      const headers = (call[1] as RequestInit).headers as Headers;
      expect(headers.get('X-CSRF-Token')).toBe('csrf-token');
    }
  });
});
