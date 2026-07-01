import { createMemoryHistory, createRouter, createWebHistory, type RouteLocationNormalized } from 'vue-router';

import { ADMIN_PERMISSIONS } from '@/adminPermissions';
import { AdminApiError } from '@/api/http';
import { useAdminAuthStore } from '@/stores/auth';

const AdminLayout = () => import('@/layouts/AdminLayout.vue');
const DashboardView = () => import('@/views/DashboardView.vue');
const ModelCenterView = () => import('@/views/ModelCenterView.vue');
const PromptCenterView = () => import('@/views/PromptCenterView.vue');
const UserCreditsView = () => import('@/views/UserCreditsView.vue');
const RecordsView = () => import('@/views/RecordsView.vue');
const AuditLogsView = () => import('@/views/AuditLogsView.vue');
const SystemSettingsView = () => import('@/views/SystemSettingsView.vue');
const ForbiddenView = () => import('@/views/ForbiddenView.vue');

export const SHARED_LOGIN_REDIRECT = '/#/auth?redirect=%2Fadmin%2F';

export function adminLoginRedirectHref(
  origin = typeof window === 'undefined' ? '' : window.location.origin,
  frontendDevPort = import.meta.env.VITE_ADMIN_FRONTEND_PORT || '5175',
): string {
  if (/^https?:\/\/(127\.0\.0\.1|localhost):5174$/i.test(origin)) {
    return origin.replace(/:5174$/i, `:${frontendDevPort}`) + SHARED_LOGIN_REDIRECT;
  }
  return SHARED_LOGIN_REDIRECT;
}

export function isSharedLoginRedirect(path: string): boolean {
  return path.startsWith('/#/') || /^https?:\/\/[^/]+\/#\//i.test(path);
}

export const adminRoutes = [
  {
    path: '/',
    component: AdminLayout,
    children: [
      {
        path: '',
        redirect: '/dashboard',
      },
      {
        path: 'dashboard',
        name: 'admin-dashboard',
        component: DashboardView,
        meta: { title: '仪表盘', permission: ADMIN_PERMISSIONS.recordView },
      },
      {
        path: 'models',
        name: 'admin-models',
        component: ModelCenterView,
        meta: { title: '模型中心', permission: ADMIN_PERMISSIONS.modelView },
      },
      {
        path: 'prompts',
        name: 'admin-prompts',
        component: PromptCenterView,
        meta: { title: '提示语中心', permission: ADMIN_PERMISSIONS.settingsView },
      },
      {
        path: 'users',
        name: 'admin-users',
        component: UserCreditsView,
        meta: { title: '用户与积分', permission: ADMIN_PERMISSIONS.userView },
      },
      {
        path: 'records',
        name: 'admin-records',
        component: RecordsView,
        meta: { title: '创作记录', permission: ADMIN_PERMISSIONS.recordView },
      },
      {
        path: 'audit',
        name: 'admin-audit',
        component: AuditLogsView,
        meta: { title: '审计日志', permission: ADMIN_PERMISSIONS.auditView },
      },
      {
        path: 'settings',
        name: 'admin-settings',
        component: SystemSettingsView,
        meta: {
          title: '系统设置',
          permission: ADMIN_PERMISSIONS.creditView,
          alternatePermissions: [
            ADMIN_PERMISSIONS.maintenanceUserMerge,
            ADMIN_PERMISSIONS.maintenanceAssetCleanup,
          ],
        },
      },
      {
        path: 'forbidden',
        name: 'admin-forbidden',
        component: ForbiddenView,
        meta: { public: true, title: '无权访问' },
      },
    ],
  },
];

type GuardTarget = Pick<RouteLocationNormalized, 'fullPath'> & Partial<Pick<RouteLocationNormalized, 'meta'>>;

export async function resolveAdminRedirectPath(to: GuardTarget): Promise<string | null> {
  const meta = to.meta ?? {};
  if (meta.public) {
    return null;
  }

  const auth = useAdminAuthStore();
  try {
    await auth.bootstrap();
  } catch (error) {
    if (error instanceof AdminApiError && error.status === 401) {
      return SHARED_LOGIN_REDIRECT;
    }
    if (error instanceof AdminApiError && error.status === 403) {
      return '/forbidden';
    }
    return '/forbidden?reason=system';
  }

  if (!auth.user) {
    return SHARED_LOGIN_REDIRECT;
  }

  const requiredPermission = typeof meta.permission === 'string' ? meta.permission : '';
  const alternatePermissions = Array.isArray(meta.alternatePermissions)
    ? meta.alternatePermissions.filter((permission): permission is string => typeof permission === 'string')
    : [];
  const hasRequiredPermission = !requiredPermission
    || auth.can(requiredPermission)
    || alternatePermissions.some((permission) => auth.can(permission));
  if (!auth.isAdmin || !hasRequiredPermission) {
    return '/forbidden';
  }

  return null;
}

const router = createRouter({
  history: typeof window === 'undefined' ? createMemoryHistory('/admin/') : createWebHistory('/admin/'),
  routes: adminRoutes,
});

router.beforeEach(async (to) => {
  const redirect = await resolveAdminRedirectPath(to);
  if (redirect && isSharedLoginRedirect(redirect)) {
    if (typeof window !== 'undefined') {
      window.location.href = adminLoginRedirectHref();
    }
    return false;
  }
  return redirect ?? true;
});

export default router;
