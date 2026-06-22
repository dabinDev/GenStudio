import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { RouteRecordRaw } from 'vue-router';

import { ADMIN_PERMISSIONS } from '@/adminPermissions';
import { visibleAdminMenuItems } from '@/adminNavigation';
import { AdminApiError } from '@/api/http';
import { useAdminAuthStore } from '@/stores/auth';
import router, {
  adminLoginRedirectHref,
  adminRoutes,
  isSharedLoginRedirect,
  resolveAdminRedirectPath,
} from './index';

vi.mock('@/api/admin', () => ({
  fetchCurrentUser: vi.fn(),
  fetchCsrfToken: vi.fn(),
  fetchAdminPermissions: vi.fn(),
  logoutAdmin: vi.fn(),
}));

describe('admin router guards', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('registers admin child routes under the layout', () => {
    const root = adminRoutes.find((route: RouteRecordRaw) => route.path === '/');

    expect(root?.children?.map((route) => route.path)).toEqual([
      '',
      'dashboard',
      'models',
      'prompts',
      'users',
      'records',
      'audit',
      'settings',
      'forbidden',
    ]);
    expect(router.resolve('/models').matched.some((record) => (
      record.meta.permission === ADMIN_PERMISSIONS.modelView
    ))).toBe(true);
  });

  it('uses readable Chinese titles for visible admin pages', () => {
    const root = adminRoutes.find((route: RouteRecordRaw) => route.path === '/');

    expect(root?.children?.map((route) => route.meta?.title).filter(Boolean)).toEqual([
      '仪表盘',
      '模型中心',
      '提示语中心',
      '用户与积分',
      '创作记录',
      '审计日志',
      '系统设置',
      '无权访问',
    ]);
  });

  it('uses settings permission for prompt center routes', () => {
    expect(router.resolve('/prompts').matched.some((record) => (
      record.meta.permission === ADMIN_PERMISSIONS.settingsView
    ))).toBe(true);
  });

  it('maps admin page routes to backend permission points', () => {
    const expectedPermissions = new Map([
      ['/dashboard', ADMIN_PERMISSIONS.recordView],
      ['/models', ADMIN_PERMISSIONS.modelView],
      ['/prompts', ADMIN_PERMISSIONS.settingsView],
      ['/users', ADMIN_PERMISSIONS.userView],
      ['/records', ADMIN_PERMISSIONS.recordView],
      ['/audit', ADMIN_PERMISSIONS.auditView],
      ['/settings', ADMIN_PERMISSIONS.creditView],
    ]);

    for (const [path, permission] of expectedPermissions) {
      expect(router.resolve(path).matched.some((record) => (
        record.meta.permission === permission
      )), path).toBe(true);
    }
  });

  it('keeps admin navigation permissions aligned with route permissions', () => {
    const allowed = new Set<string>(Object.values(ADMIN_PERMISSIONS));
    const visible = visibleAdminMenuItems((permission) => allowed.has(permission));

    for (const item of visible) {
      expect(router.resolve(item.path).matched.some((record) => (
        record.meta.permission === item.permission
      )), item.path).toBe(true);
    }
  });

  it('filters admin navigation entries by current permissions', () => {
    const allowed = new Set<string>([
      ADMIN_PERMISSIONS.recordView,
      ADMIN_PERMISSIONS.creditView,
    ]);
    const visible = visibleAdminMenuItems((permission) => allowed.has(permission));

    expect(visible.map((item) => item.label)).toEqual(['仪表盘', '创作记录', '系统设置']);
  });

  it('shows settings navigation for maintenance-only admins', () => {
    const visible = visibleAdminMenuItems((permission) => permission === ADMIN_PERMISSIONS.maintenanceUserMerge);

    expect(visible.map((item) => item.path)).toEqual(['/settings']);
  });

  it('redirects unauthenticated admins to the shared auth route', async () => {
    const auth = useAdminAuthStore();
    auth.bootstrap = vi.fn(async () => undefined);
    auth.user = null;

    const redirect = await resolveAdminRedirectPath({ fullPath: '/' });

    expect(redirect).toBe('/#/auth?redirect=%2Fadmin%2F');
    expect(isSharedLoginRedirect(redirect ?? '')).toBe(true);
  });

  it('sends local independent admin dev login redirects to the creative workspace dev server', () => {
    expect(adminLoginRedirectHref('http://127.0.0.1:5174')).toBe(
      'http://127.0.0.1:5175/#/auth?redirect=%2Fadmin%2F',
    );
    expect(adminLoginRedirectHref('http://localhost:5174', '5173')).toBe(
      'http://localhost:5173/#/auth?redirect=%2Fadmin%2F',
    );
    expect(adminLoginRedirectHref('https://studio.cylonai.cn')).toBe('/#/auth?redirect=%2Fadmin%2F');
  });

  it('redirects auth 401 errors to the shared auth route', async () => {
    const auth = useAdminAuthStore();
    auth.bootstrap = vi.fn(async () => {
      throw new AdminApiError('请先登录', 401);
    });

    await expect(resolveAdminRedirectPath({ fullPath: '/models' })).resolves.toBe('/#/auth?redirect=%2Fadmin%2F');
  });

  it('sends backend bootstrap failures to a system error state', async () => {
    const auth = useAdminAuthStore();
    auth.bootstrap = vi.fn(async () => {
      throw new AdminApiError('服务异常', 500);
    });

    await expect(resolveAdminRedirectPath({ fullPath: '/models' })).resolves.toBe('/forbidden?reason=system');
  });

  it('sends non-admin users and missing permissions to forbidden', async () => {
    const auth = useAdminAuthStore();
    auth.bootstrap = vi.fn(async () => undefined);
    auth.user = { id: 'u1', email: 'user@example.com', isAdmin: false };

    await expect(resolveAdminRedirectPath({ fullPath: '/models', meta: { permission: ADMIN_PERMISSIONS.modelView } })).resolves.toBe('/forbidden');

    auth.user = { id: 'u2', email: 'admin@example.com', isAdmin: true };
    auth.permissions = [ADMIN_PERMISSIONS.recordView];

    await expect(resolveAdminRedirectPath({ fullPath: '/models', meta: { permission: ADMIN_PERMISSIONS.modelView } })).resolves.toBe('/forbidden');
  });

  it('allows admins with matching permission', async () => {
    const auth = useAdminAuthStore();
    auth.bootstrap = vi.fn(async () => undefined);
    auth.user = { id: 'u2', email: 'admin@example.com', isAdmin: true };
    auth.permissions = [ADMIN_PERMISSIONS.modelView];

    await expect(resolveAdminRedirectPath({ fullPath: '/models', meta: { permission: ADMIN_PERMISSIONS.modelView } })).resolves.toBeNull();
  });

  it('allows admins through alternate route permissions', async () => {
    const auth = useAdminAuthStore();
    auth.bootstrap = vi.fn(async () => undefined);
    auth.user = { id: 'u3', email: 'maintenance@example.com', isAdmin: true };
    auth.permissions = [ADMIN_PERMISSIONS.maintenanceUserMerge];

    await expect(resolveAdminRedirectPath({
      fullPath: '/settings',
      meta: {
        permission: ADMIN_PERMISSIONS.creditView,
        alternatePermissions: [ADMIN_PERMISSIONS.maintenanceUserMerge],
      },
    })).resolves.toBeNull();
  });
});
