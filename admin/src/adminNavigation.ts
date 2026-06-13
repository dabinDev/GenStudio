import { ADMIN_PERMISSIONS, type AdminPermissionChecker } from '@/adminPermissions';

export interface AdminMenuItem {
  path: string;
  label: string;
  mark: string;
  permission: string;
  alternatePermissions?: string[];
}

export const ADMIN_MENU_ITEMS: AdminMenuItem[] = [
  { path: '/dashboard', label: '仪表盘', mark: '总', permission: ADMIN_PERMISSIONS.recordView },
  { path: '/models', label: '模型中心', mark: '模', permission: ADMIN_PERMISSIONS.modelView },
  { path: '/prompts', label: '提示语中心', mark: '提', permission: ADMIN_PERMISSIONS.settingsView },
  { path: '/users', label: '用户与积分', mark: '用', permission: ADMIN_PERMISSIONS.userView },
  { path: '/records', label: '创作记录', mark: '录', permission: ADMIN_PERMISSIONS.recordView },
  { path: '/audit', label: '审计日志', mark: '审', permission: ADMIN_PERMISSIONS.auditView },
  {
    path: '/settings',
    label: '系统设置',
    mark: '设',
    permission: ADMIN_PERMISSIONS.creditView,
    alternatePermissions: [ADMIN_PERMISSIONS.maintenanceUserMerge],
  },
];

export function visibleAdminMenuItems(can: AdminPermissionChecker): AdminMenuItem[] {
  return ADMIN_MENU_ITEMS.filter((item) => can(item.permission) || (item.alternatePermissions || []).some(can));
}
