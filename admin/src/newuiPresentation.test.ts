import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const source = (path: string) => readFileSync(resolve(process.cwd(), path), 'utf8').replace(/\r\n/g, '\n');

const ROUTE_CONTRACTS = [
  { path: 'dashboard', title: '仪表盘', testId: 'admin-dashboard-view', view: 'DashboardView.vue', headingMarker: 'DASHBOARD_TITLE' },
  { path: 'models', title: '模型中心', testId: 'admin-models-view', view: 'ModelCenterView.vue', headingMarker: 'MODEL_CENTER_TITLE' },
  { path: 'prompts', title: '提示语中心', testId: 'admin-prompts-view', view: 'PromptCenterView.vue', headingMarker: '提示语中心' },
  { path: 'records', title: '创作中心', testId: 'admin-records-view', view: 'RecordsView.vue', headingMarker: '创作中心' },
  { path: 'users', title: '用户与积分', testId: 'admin-users-view', view: 'UserCreditsView.vue', headingMarker: '用户与积分' },
  { path: 'settings', title: '系统设置', testId: 'admin-settings-view', view: 'SystemSettingsView.vue', headingMarker: '系统设置' },
  { path: 'audit', title: '审计日志', testId: 'admin-audit-view', view: 'AuditLogsView.vue', headingMarker: '审计日志' },
  { path: 'forbidden', title: '无权访问', testId: 'admin-forbidden-view', view: 'ForbiddenView.vue', headingMarker: '<h2>{{ title }}</h2>' },
] as const;

describe('newui admin presentation contract', () => {
  it('defines stable titles and main-landmark ids for every route', () => {
    const router = source('src/router/index.ts');
    const layout = source('src/layouts/AdminLayout.vue');

    expect(layout).toContain('id="admin-route-heading"');
    expect(layout).toContain(':data-testid="route.meta.testId || \'admin-view\'"');
    expect(layout).toContain('aria-labelledby="admin-route-heading"');
    for (const route of ROUTE_CONTRACTS) {
      expect(router).toContain(`path: '${route.path}'`);
      expect(router).toContain(`title: '${route.title}'`);
      expect(router).toContain(`testId: '${route.testId}'`);
    }
  });

  it('keeps a concise visible page heading in every routed view', () => {
    for (const route of ROUTE_CONTRACTS) {
      const view = source(`src/views/${route.view}`);
      expect(view).toContain('<h2');
      expect(view).toContain(route.headingMarker);
    }
  });
});
