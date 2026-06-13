import type { AdminAuditLog, AdminCreationRecord, AdminUserWithCredits } from '@/types';

export function csvEscape(value: unknown): string {
  const text = value == null ? '' : String(value);
  if (!/[",\r\n]/.test(text)) {
    return text;
  }
  return `"${text.replace(/"/g, '""')}"`;
}

function jsonCell(value: unknown): string {
  if (value == null) return '';
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function rowsToCsv(rows: unknown[][]): string {
  return rows.map((row) => row.map(csvEscape).join(',')).join('\r\n');
}

export function buildCreationRecordCsv(records: AdminCreationRecord[]): string {
  return rowsToCsv([
    ['消息ID', '用户', '类型', '模型', '状态', '提示词', '响应', '错误信息', '资源数', '任务ID', '耗时ms', '创建时间'],
    ...records.map((record) => [
      record.id,
      record.user?.email || record.user?.nickname || record.user?.id || '',
      record.capability,
      record.modelName,
      record.status,
      record.prompt,
      record.response,
      record.errorMessage,
      record.assets?.length || 0,
      record.taskId,
      record.durationMs || 0,
      record.createdAt,
    ]),
  ]);
}

export function buildAuditLogCsv(logs: AdminAuditLog[]): string {
  return rowsToCsv([
    ['日志ID', '管理员', '操作', '目标类型', '目标ID', '风险等级', '状态', '摘要', '创建时间'],
    ...logs.map((log) => [
      log.id,
      log.adminUserId || '',
      log.action,
      log.targetType,
      log.targetId,
      log.riskLevel || 'normal',
      log.status,
      jsonCell(log.summary),
      log.createdAt,
    ]),
  ]);
}

export function buildUserCsv(users: AdminUserWithCredits[]): string {
  return rowsToCsv([
    [
      '用户ID',
      '外部用户ID',
      '邮箱',
      '昵称',
      '手机号',
      '后台角色',
      '角色来源',
      '状态',
      '可用积分',
      '冻结积分',
      '累计充值',
      '累计消耗',
      '累计退回',
      '会话数',
      '最近登录IP',
      '最近活跃',
      '创建时间',
    ],
    ...users.map((user) => [
      user.id,
      user.externalUserId,
      user.email || '',
      user.nickname || '',
      user.phone || '',
      user.adminRole || (user.isAdmin ? 'admin' : 'user'),
      user.adminRoleSource || '',
      user.status,
      user.credits?.balance ?? 0,
      user.credits?.reservedBalance ?? 0,
      user.credits?.totalRecharged ?? 0,
      user.credits?.totalSpent ?? 0,
      user.credits?.totalRefunded ?? 0,
      user.sessionCount ?? 0,
      user.recentLoginIp || '',
      user.lastSeenAt || '',
      user.createdAt,
    ]),
  ]);
}

export function buildExportFilename(prefix: string, scope = '', now = new Date()): string {
  const date = now.toISOString().slice(0, 10);
  return [prefix, scope, date].filter(Boolean).join('-') + '.csv';
}

export function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' });
  downloadBlob(filename, blob);
}

export function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
