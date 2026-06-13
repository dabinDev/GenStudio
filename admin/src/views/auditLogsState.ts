import type { AdminAuditLog, AdminAuditLogQuery } from '@/types';

export const TARGET_TYPE_OPTIONS = [
  { label: '全部对象', value: '' },
  { label: '用户', value: 'user' },
  { label: '模型', value: 'model' },
  { label: '提示语模板', value: 'prompt_template' },
  { label: '积分设置', value: 'credit_settings' },
  { label: '维护任务', value: 'maintenance' },
  { label: '仪表盘', value: 'dashboard' },
] as const;

export interface AuditLogFilters {
  action: string;
  adminUserId: string;
  targetType: string;
  targetId: string;
  status: string;
  risk: string;
  dateRange: string[];
  limit: number;
}

export function createAuditLogFilters(): AuditLogFilters {
  return {
    action: '',
    adminUserId: '',
    targetType: '',
    targetId: '',
    status: '',
    risk: '',
    dateRange: [],
    limit: 100,
  };
}

export function buildAuditLogQuery(filters: AuditLogFilters): AdminAuditLogQuery {
  const [startAt, endAt] = filters.dateRange;
  return {
    action: filters.action,
    adminUserId: filters.adminUserId,
    targetType: filters.targetType,
    targetId: filters.targetId,
    status: filters.status,
    risk: filters.risk,
    startAt,
    endAt,
    limit: filters.limit,
  };
}

export function buildAuditTargetScope(filters: Pick<AuditLogFilters, 'targetType' | 'risk'>): string {
  return [filters.targetType || 'all', filters.risk || 'all'].join('-');
}

export function buildAuditLogSummary(logs: AdminAuditLog[]) {
  return {
    total: logs.length,
    highRisk: logs.filter((item) => item.riskLevel === 'high').length,
    mediumRisk: logs.filter((item) => item.riskLevel === 'medium').length,
    errors: logs.filter((item) => item.status === 'error').length,
    targetTypes: new Set(logs.map((item) => item.targetType || 'unknown')).size,
  };
}

export function auditRowClassName(row: Pick<AdminAuditLog, 'riskLevel' | 'status'>): string {
  if (row.riskLevel === 'high') {
    return 'audit-row--high-risk';
  }
  if (row.status === 'error') {
    return 'audit-row--error';
  }
  return '';
}
