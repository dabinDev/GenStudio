import { AdminApiError, adminRequest, setAdminCsrfToken } from './http';
import type {
  AdminBatchModelHealthCheckResponse,
  AssetCleanupPayload,
  AssetCleanupSettings,
  AssetCleanupSettingsUpdatePayload,
  AdminDashboardMetrics,
  AdminModel,
  AdminModelCreditPricingUpdate,
  AdminModelHealth,
  AdminModelListQuery,
  AdminRemoveUnavailableModelsResponse,
  AdminModelUpdate,
  AdminPermissions,
  AdminUserSession,
  AdminUserCreditPayload,
  AdminUserListQuery,
  AdminUserRoleUpdatePayload,
  AdminUserUpdatePayload,
  AdminUserWithCredits,
  AdminCreditAdjustmentPayload,
  PromptTemplate,
  PromptTemplateModelStatus,
  PromptSceneTemplate,
  PromptSceneTemplateImportSummary,
  PromptSceneTemplateListPayload,
  PromptSceneTemplateQuery,
  PromptSceneTemplateUpdatePayload,
  PromptTemplateTestPayload,
  PromptTemplateTestResult,
  PromptTemplateUpdatePayload,
  PromptTemplateVersion,
  AdminCreationRecord,
  AdminCreationRecordDetail,
  AdminRecordQuery,
  AdminTaskTimeline,
  AdminAuditLog,
  AdminAuditLogQuery,
  CreditSettings,
  CreditSettingsUpdatePayload,
  Capability,
  UserMergeMaintenancePayload,
  UserMergeSummary,
} from '@/types';

export async function fetchCurrentUser(): Promise<AdminUserSession | null> {
  const payload = await adminRequest<{ user?: AdminUserSession | null } | AdminUserSession>('/api/auth/me');
  if (payload && typeof payload === 'object' && 'user' in payload) {
    return payload.user ?? null;
  }
  return payload as AdminUserSession;
}

export async function fetchCsrfToken(): Promise<string> {
  const payload = await adminRequest<{ csrfToken?: string; csrf_token?: string; token?: string }>('/api/auth/csrf');
  const token = payload.csrfToken ?? payload.csrf_token ?? payload.token ?? '';
  setAdminCsrfToken(token);
  return token;
}

export async function fetchAdminPermissions(): Promise<AdminPermissions> {
  return adminRequest<AdminPermissions>('/api/admin/permissions/me');
}

export async function fetchDashboardMetrics(range = '30d'): Promise<AdminDashboardMetrics> {
  return adminRequest<AdminDashboardMetrics>(`/api/admin/dashboard/metrics?range=${encodeURIComponent(range)}`);
}

export async function fetchAdminModels(query: AdminModelListQuery = {}): Promise<AdminModel[]> {
  const params = new URLSearchParams();
  if (query.capability) {
    params.set('capability', query.capability);
  }
  if (query.search) {
    params.set('search', query.search);
  }
  if (query.publicState) {
    params.set('publicState', query.publicState);
  }
  const suffix = params.toString() ? `?${params.toString()}` : '';
  const payload = await adminRequest<{ models: AdminModel[] }>(`/api/admin/models${suffix}`);
  return payload.models;
}

export function adminModelPath(modelId: string): string {
  if (!/^[A-Za-z0-9_-]+$/.test(modelId)) {
    throw new AdminApiError('模型 ID 格式无效。', 400);
  }
  return `/api/admin/models/${modelId}`;
}

export async function updateAdminModel(modelId: string, payload: AdminModelUpdate): Promise<AdminModel> {
  const response = await adminRequest<{ model: AdminModel }>(adminModelPath(modelId), {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
  return response.model;
}

export async function updateModelCreditPricing(
  modelId: string,
  payload: AdminModelCreditPricingUpdate,
): Promise<AdminModel> {
  const response = await adminRequest<{ model: AdminModel }>(
    `${adminModelPath(modelId)}/credit-pricing`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  );
  return response.model;
}

export async function publishAdminModel(modelId: string): Promise<AdminModel> {
  const response = await adminRequest<{ model: AdminModel }>(
    `${adminModelPath(modelId)}/publish`,
    { method: 'POST' },
  );
  return response.model;
}

export async function unpublishAdminModel(modelId: string): Promise<AdminModel> {
  const response = await adminRequest<{ model: AdminModel }>(
    `${adminModelPath(modelId)}/unpublish`,
    { method: 'POST' },
  );
  return response.model;
}

export async function fetchAdminModelHealth(modelId: string): Promise<AdminModelHealth> {
  const response = await adminRequest<{ health: AdminModelHealth }>(
    `${adminModelPath(modelId)}/health`,
  );
  return response.health;
}

export async function runAdminModelHealthCheck(modelId: string): Promise<AdminModelHealth> {
  const response = await adminRequest<{ health: AdminModelHealth }>(
    `${adminModelPath(modelId)}/health-check`,
    { method: 'POST' },
  );
  return response.health;
}

export async function runAdminBatchModelHealthCheck(
  modelIds: string[],
): Promise<AdminBatchModelHealthCheckResponse> {
  return adminRequest<AdminBatchModelHealthCheckResponse>('/api/admin/models/batch-health-check', {
    method: 'POST',
    body: JSON.stringify({ modelIds }),
  });
}

export async function removeUnavailableAdminModels(
  modelIds: string[],
): Promise<AdminRemoveUnavailableModelsResponse> {
  return adminRequest<AdminRemoveUnavailableModelsResponse>('/api/admin/models/remove-unavailable', {
    method: 'POST',
    body: JSON.stringify({ modelIds }),
  });
}

export async function fetchAdminUsers(query: string | AdminUserListQuery = ''): Promise<AdminUserWithCredits[]> {
  const normalized = typeof query === 'string' ? { search: query } : query;
  const params = new URLSearchParams();
  const search = (normalized.search || '').trim();
  const role = (normalized.role || '').trim();
  const status = (normalized.status || '').trim();
  if (search) {
    params.set('search', search);
  }
  if (role && role !== 'all') {
    params.set('role', role);
  }
  if (status && status !== 'all') {
    params.set('status', status);
  }
  const suffix = params.toString() ? `?${params.toString()}` : '';
  const payload = await adminRequest<{ users: AdminUserWithCredits[] }>(`/api/admin/users${suffix}`);
  return payload.users;
}

export async function exportAdminUsers(query: AdminUserListQuery = {}): Promise<Blob> {
  const normalized = {
    search: (query.search || '').trim(),
    role: (query.role || '').trim(),
    status: (query.status || '').trim(),
  };
  const response = await fetch(`/api/admin/users/export${paramsFromQuery(normalized)}`, {
    credentials: 'include',
    method: 'GET',
  });
  if (!response.ok) {
    const payload = response.headers.get('content-type')?.includes('application/json')
      ? await response.json().catch(() => null)
      : await response.text().catch(() => '');
    throw new AdminApiError(
      typeof payload === 'string' && payload.trim() ? payload.trim() : '用户列表导出失败，请稍后重试。',
      response.status,
      payload,
    );
  }
  return response.blob();
}

export function adminUserPath(userId: string): string {
  if (!/^[A-Za-z0-9_-]+$/.test(userId)) {
    throw new AdminApiError('用户 ID 格式无效。', 400);
  }
  return `/api/admin/users/${userId}`;
}

export async function updateAdminUser(
  userId: string,
  body: AdminUserUpdatePayload,
): Promise<AdminUserWithCredits> {
  const payload = await adminRequest<{ user: AdminUserWithCredits }>(adminUserPath(userId), {
    method: 'PUT',
    body: JSON.stringify(body),
  });
  return payload.user;
}

export async function updateAdminUserRole(
  userId: string,
  body: AdminUserRoleUpdatePayload,
): Promise<AdminUserWithCredits> {
  const payload = await adminRequest<{ user: AdminUserWithCredits }>(`${adminUserPath(userId)}/role`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });
  return payload.user;
}

export type AdminUserStatusAction = 'enable' | 'disable' | 'delete' | 'restore';

export async function setAdminUserStatus(
  userId: string,
  action: AdminUserStatusAction,
): Promise<AdminUserWithCredits> {
  const payload = await adminRequest<{ user: AdminUserWithCredits }>(`${adminUserPath(userId)}/${action}`, {
    method: 'POST',
    body: '{}',
  });
  return payload.user;
}

export async function fetchAdminUserCredits(userId: string): Promise<AdminUserCreditPayload> {
  return adminRequest<AdminUserCreditPayload>(`${adminUserPath(userId)}/credits`);
}

export async function adjustUserCredits(
  userId: string,
  amount: number,
  reason: string,
): Promise<AdminCreditAdjustmentPayload> {
  return adminRequest<AdminCreditAdjustmentPayload>(`${adminUserPath(userId)}/credits/adjust`, {
    method: 'POST',
    body: JSON.stringify({ amount, reason }),
  });
}

function paramsFromQuery(query: object = {}): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value));
    }
  }
  return params.toString() ? `?${params.toString()}` : '';
}

export async function fetchPromptTemplates(capability = 'all'): Promise<PromptTemplate[]> {
  const payload = await adminRequest<{ templates: PromptTemplate[] }>(
    `/api/admin/prompt-templates${paramsFromQuery({ capability })}`,
  );
  return payload.templates;
}

export async function savePromptTemplate(
  templateId: string,
  body: PromptTemplateUpdatePayload,
): Promise<PromptTemplate> {
  const payload = await adminRequest<{ template: PromptTemplate }>(`/api/admin/prompt-templates/${templateId}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });
  return payload.template;
}

export async function fetchPromptTemplateVersions(templateId: string): Promise<PromptTemplateVersion[]> {
  const payload = await adminRequest<{ versions: PromptTemplateVersion[] }>(
    `/api/admin/prompt-templates/${encodeURIComponent(templateId)}/versions`,
  );
  return payload.versions;
}

export async function fetchPromptTemplateModelStatus(capability = 'all'): Promise<PromptTemplateModelStatus[]> {
  const payload = await adminRequest<{ models: PromptTemplateModelStatus[] }>(
    `/api/admin/prompt-templates/model-status${paramsFromQuery({ capability })}`,
  );
  return payload.models;
}

export async function testPromptTemplate(body: PromptTemplateTestPayload): Promise<string | PromptTemplateTestResult[]> {
  const payload = await adminRequest<{ prompt?: string; results?: PromptTemplateTestResult[] }>('/api/admin/prompt-templates/test', {
    method: 'POST',
    body: JSON.stringify(body),
  });
  return payload.results || payload.prompt || '';
}

export async function fetchPromptSceneTemplates(
  query: PromptSceneTemplateQuery = {},
): Promise<PromptSceneTemplateListPayload> {
  return adminRequest<PromptSceneTemplateListPayload>(`/api/admin/prompt-library${paramsFromQuery(query)}`);
}

export async function importPromptSceneTemplates(
  index: Record<string, unknown>,
  replace = false,
): Promise<PromptSceneTemplateImportSummary> {
  const payload = await adminRequest<{ summary: PromptSceneTemplateImportSummary }>('/api/admin/prompt-library/import', {
    method: 'POST',
    body: JSON.stringify({ index, replace }),
  });
  return payload.summary;
}

export async function updatePromptSceneTemplate(
  templateId: string,
  body: PromptSceneTemplateUpdatePayload,
): Promise<PromptSceneTemplate> {
  const payload = await adminRequest<{ template: PromptSceneTemplate }>(
    `/api/admin/prompt-library/${encodeURIComponent(templateId)}`,
    {
      method: 'PUT',
      body: JSON.stringify(body),
    },
  );
  return payload.template;
}

export async function batchUpdatePromptSceneTemplates(
  templateIds: string[],
  body: Pick<PromptSceneTemplateUpdatePayload, 'enabled'>,
): Promise<number> {
  const payload = await adminRequest<{ updated: number }>('/api/admin/prompt-library/batch', {
    method: 'POST',
    body: JSON.stringify({ templateIds, ...body }),
  });
  return payload.updated;
}

function recordCollectionPath(capability: Capability): string {
  if (capability === 'image') {
    return 'images';
  }
  if (capability === 'video') {
    return 'videos';
  }
  return 'text';
}

export async function fetchAdminRecords(
  capability: Capability,
  query: AdminRecordQuery = {},
): Promise<AdminCreationRecord[]> {
  const payload = await adminRequest<{ records: AdminCreationRecord[] }>(
    `/api/admin/records/${recordCollectionPath(capability)}${paramsFromQuery(query)}`,
  );
  return payload.records;
}

export async function exportAdminRecords(
  capability: Capability,
  query: AdminRecordQuery = {},
): Promise<Blob> {
  const response = await fetch(
    `/api/admin/records/${recordCollectionPath(capability)}/export${paramsFromQuery(query)}`,
    {
      credentials: 'include',
      method: 'GET',
    },
  );
  if (!response.ok) {
    const payload = response.headers.get('content-type')?.includes('application/json')
      ? await response.json().catch(() => null)
      : await response.text().catch(() => '');
    throw new AdminApiError(
      typeof payload === 'string' && payload.trim() ? payload.trim() : '创作记录导出失败，请稍后重试。',
      response.status,
      payload,
    );
  }
  return response.blob();
}

export async function fetchAdminRecordDetail(messageId: string): Promise<AdminCreationRecordDetail> {
  const payload = await adminRequest<{ record?: AdminCreationRecordDetail; detail?: AdminCreationRecordDetail } | AdminCreationRecordDetail>(
    `/api/admin/records/detail/${encodeURIComponent(messageId)}`,
  );
  if (payload && typeof payload === 'object' && 'record' in payload && payload.record) {
    return payload.record;
  }
  if (payload && typeof payload === 'object' && 'detail' in payload && payload.detail) {
    return payload.detail;
  }
  return payload as AdminCreationRecordDetail;
}

export async function fetchTaskTimeline(taskId: string): Promise<AdminTaskTimeline> {
  return adminRequest<AdminTaskTimeline>(`/api/admin/tasks/${encodeURIComponent(taskId)}/timeline`);
}

export async function fetchAuditLogs(query: AdminAuditLogQuery = {}): Promise<AdminAuditLog[]> {
  const payload = await adminRequest<{ logs: AdminAuditLog[] }>(
    `/api/admin/audit-logs${paramsFromQuery(query)}`,
  );
  return payload.logs;
}

export async function exportAuditLogs(query: AdminAuditLogQuery = {}): Promise<Blob> {
  const response = await fetch(`/api/admin/audit-logs/export${paramsFromQuery(query)}`, {
    credentials: 'include',
    method: 'GET',
  });
  if (!response.ok) {
    const payload = response.headers.get('content-type')?.includes('application/json')
      ? await response.json().catch(() => null)
      : await response.text().catch(() => '');
    throw new AdminApiError(
      typeof payload === 'string' && payload.trim() ? payload.trim() : '审计日志导出失败，请稍后重试。',
      response.status,
      payload,
    );
  }
  return response.blob();
}

export async function fetchCreditSettings(): Promise<CreditSettings> {
  const payload = await adminRequest<{ settings: CreditSettings }>('/api/admin/credits/settings');
  return payload.settings;
}

export async function saveCreditSettings(body: CreditSettingsUpdatePayload): Promise<CreditSettings> {
  const payload = await adminRequest<{ settings: CreditSettings }>('/api/admin/credits/settings', {
    method: 'PUT',
    body: JSON.stringify(body),
  });
  return payload.settings;
}

export async function runUserMergeMaintenance(body: UserMergeMaintenancePayload): Promise<UserMergeSummary> {
  const payload = await adminRequest<{ summary: UserMergeSummary }>('/api/admin/maintenance/user-merge', {
    method: 'POST',
    body: JSON.stringify(body),
  });
  return payload.summary;
}

export async function fetchAssetCleanupSettings(): Promise<AssetCleanupSettings> {
  const payload = await adminRequest<{ settings: AssetCleanupSettings }>('/api/admin/asset-cleanup/settings');
  return payload.settings;
}

export async function saveAssetCleanupSettings(
  body: AssetCleanupSettingsUpdatePayload,
): Promise<AssetCleanupSettings> {
  const payload = await adminRequest<{ settings: AssetCleanupSettings }>('/api/admin/asset-cleanup/settings', {
    method: 'PUT',
    body: JSON.stringify(body),
  });
  return payload.settings;
}

export async function previewAssetCleanup(): Promise<AssetCleanupPayload> {
  return adminRequest<AssetCleanupPayload>('/api/admin/asset-cleanup/preview');
}

export async function runAssetCleanup(
  body: AssetCleanupSettingsUpdatePayload = {},
): Promise<AssetCleanupPayload> {
  return adminRequest<AssetCleanupPayload>('/api/admin/asset-cleanup/run', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function logoutAdmin(): Promise<void> {
  await adminRequest('/api/auth/logout', { method: 'POST' });
}
