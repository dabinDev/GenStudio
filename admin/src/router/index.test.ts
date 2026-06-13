import { describe, expect, it } from 'vitest';

import { ADMIN_MENU_ITEMS } from '@/adminNavigation';

import router from './index';

describe('admin router', () => {
  it('redirects the admin root to the dashboard', () => {
    expect(router.resolve('/').matched[0]?.redirect).toBeUndefined();
    expect(router.resolve('/dashboard').name).toBe('admin-dashboard');
  });

  it('registers the forbidden route outside the admin layout', () => {
    expect(router.resolve('/forbidden').name).toBe('admin-forbidden');
  });

  it('uses readable Chinese labels for admin routes and navigation', () => {
    expect(ADMIN_MENU_ITEMS.map((item) => item.label)).toEqual([
      '仪表盘',
      '模型中心',
      '提示语中心',
      '用户与积分',
      '创作记录',
      '审计日志',
      '系统设置',
    ]);
    expect(router.resolve('/dashboard').meta.title).toBe('仪表盘');
    expect(router.resolve('/prompts').meta.title).toBe('提示语中心');
    expect(router.resolve('/forbidden').meta.title).toBe('无权访问');
  });
});
