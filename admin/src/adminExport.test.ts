import { describe, expect, it } from 'vitest';

import type { AdminAuditLog, AdminCreationRecord, AdminUserWithCredits } from '@/types';
import {
  buildAuditLogCsv,
  buildCreationRecordCsv,
  buildExportFilename,
  buildUserCsv,
  csvEscape,
} from './adminExport';

describe('admin export helpers', () => {
  it('escapes CSV cells that contain commas, quotes, or line breaks', () => {
    expect(csvEscape('plain')).toBe('plain');
    expect(csvEscape('a,b')).toBe('"a,b"');
    expect(csvEscape('a"b')).toBe('"a""b"');
    expect(csvEscape('a\nb')).toBe('"a\nb"');
  });

  it('builds creation record CSV from the current table rows', () => {
    const rows: AdminCreationRecord[] = [
      {
        id: 'msg_1',
        user: {
          id: 'usr_1',
          externalUserId: 'external_1',
          email: 'user@example.com',
          phone: '',
          status: 'active',
          isAdmin: false,
          createdAt: '2026-06-11T00:00:00Z',
          updatedAt: '2026-06-11T00:00:00Z',
          credits: null,
        },
        modelName: 'gpt-image',
        capability: 'image',
        status: 'success',
        prompt: '生成图片',
        response: 'https://example.com/image.png',
        createdAt: '2026-06-11T01:02:03Z',
        durationMs: 1234,
        taskId: 'task_1',
        assets: [{ type: 'image', url: 'https://example.com/image.png' }],
        requestParams: { size: '1024x1024' },
        responseSummary: { ok: true },
        errorMessage: '',
      },
    ];

    expect(buildCreationRecordCsv(rows)).toContain('消息ID,用户,类型,模型,状态,提示词,响应,错误信息,资源数,任务ID,耗时ms,创建时间');
    expect(buildCreationRecordCsv(rows)).toContain('msg_1,user@example.com,image,gpt-image,success,生成图片,https://example.com/image.png,,1,task_1,1234,2026-06-11T01:02:03Z');
  });

  it('builds audit log CSV from the current table rows', () => {
    const rows: AdminAuditLog[] = [
      {
        id: 'log_1',
        adminUserId: 'usr_admin',
        action: 'update_admin_role',
        targetType: 'user',
        targetId: 'usr_2',
        status: 'success',
        riskLevel: 'high',
        summary: { role: 'viewer' },
        createdAt: '2026-06-11T04:05:06Z',
      },
    ];

    expect(buildAuditLogCsv(rows)).toContain('日志ID,管理员,操作,目标类型,目标ID,风险等级,状态,摘要,创建时间');
    expect(buildAuditLogCsv(rows)).toContain('log_1,usr_admin,update_admin_role,user,usr_2,high,success,"{""role"":""viewer""}",2026-06-11T04:05:06Z');
  });

  it('builds user CSV with role, credit, and login fields', () => {
    const rows: AdminUserWithCredits[] = [
      {
        id: 'usr_1',
        externalUserId: 'wx_1',
        email: 'user@example.com',
        phone: '13800000000',
        nickname: 'User One',
        status: 'active',
        isAdmin: true,
        adminRole: 'viewer',
        adminRoleSource: 'database',
        createdAt: '2026-06-10T01:00:00Z',
        updatedAt: '2026-06-11T01:00:00Z',
        sessionCount: 3,
        lastSeenAt: '2026-06-11T02:00:00Z',
        recentLoginIp: '127.0.0.1',
        credits: {
          id: 'cred_1',
          userId: 'usr_1',
          balance: 12,
          reservedBalance: 2,
          totalRecharged: 20,
          totalSpent: 6,
          totalRefunded: 1,
          createdAt: '2026-06-10T01:00:00Z',
          updatedAt: '2026-06-11T01:00:00Z',
        },
      },
    ];

    expect(buildUserCsv(rows)).toContain('用户ID,外部用户ID,邮箱,昵称,手机号,后台角色,角色来源,状态,可用积分,冻结积分,累计充值,累计消耗,累计退回,会话数,最近登录IP,最近活跃,创建时间');
    expect(buildUserCsv(rows)).toContain('usr_1,wx_1,user@example.com,User One,13800000000,viewer,database,active,12,2,20,6,1,3,127.0.0.1,2026-06-11T02:00:00Z,2026-06-10T01:00:00Z');
  });

  it('builds stable export filenames with capability and date', () => {
    expect(buildExportFilename('records', 'image', new Date('2026-06-11T08:09:10Z'))).toBe('records-image-2026-06-11.csv');
    expect(buildExportFilename('audit', '', new Date('2026-06-11T08:09:10Z'))).toBe('audit-2026-06-11.csv');
  });
});
