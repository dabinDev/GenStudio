export type AdminPermissionChecker = (permission: string) => boolean;

export const ADMIN_PERMISSIONS = {
  modelView: 'model:view',
  modelUpdate: 'model:update',
  modelDelete: 'model:delete',
  modelPublish: 'model:publish',
  modelUnpublish: 'model:unpublish',
  modelTest: 'model:test',
  modelPricing: 'model:pricing',
  userView: 'user:view',
  userUpdate: 'user:update',
  userDisable: 'user:disable',
  userDelete: 'user:delete',
  userRestore: 'user:restore',
  userRoleUpdate: 'user:role:update',
  creditView: 'credit:view',
  creditAdjust: 'credit:adjust',
  creditSettings: 'credit:settings',
  userExport: 'user:export',
  recordView: 'record:view',
  recordExport: 'record:export',
  auditView: 'audit:view',
  auditExport: 'audit:export',
  settingsView: 'settings:view',
  settingsUpdate: 'settings:update',
  maintenanceUserMerge: 'maintenance:user_merge',
  maintenanceAssetCleanup: 'maintenance:asset_cleanup',
} as const;

export function makePermissionChecker(permissions: readonly string[]): AdminPermissionChecker {
  const allowed = new Set(permissions);
  return (permission: string) => allowed.has(permission);
}

export function canPublishModel(can: AdminPermissionChecker, isPublic: boolean, canEdit: boolean) {
  return canEdit && !isPublic && can(ADMIN_PERMISSIONS.modelPublish);
}

export function canUnpublishModel(can: AdminPermissionChecker, isPublic: boolean, canEdit: boolean) {
  return canEdit && isPublic && can(ADMIN_PERMISSIONS.modelUnpublish);
}

export function canEditModel(can: AdminPermissionChecker, canEdit: boolean) {
  return canEdit && can(ADMIN_PERMISSIONS.modelUpdate);
}

export function canEditModelPricing(can: AdminPermissionChecker, canEdit: boolean) {
  return canEdit && can(ADMIN_PERMISSIONS.modelPricing);
}

export function canTestModel(can: AdminPermissionChecker) {
  return can(ADMIN_PERMISSIONS.modelTest);
}

export function canRemoveUnavailableModels(can: AdminPermissionChecker) {
  return can(ADMIN_PERMISSIONS.modelDelete);
}

export function userStatusPermission(action: 'enable' | 'disable' | 'delete' | 'restore') {
  if (action === 'enable') return ADMIN_PERMISSIONS.userUpdate;
  if (action === 'disable') return ADMIN_PERMISSIONS.userDisable;
  if (action === 'delete') return ADMIN_PERMISSIONS.userDelete;
  return ADMIN_PERMISSIONS.userRestore;
}

export function canRunUserStatusAction(
  can: AdminPermissionChecker,
  action: 'enable' | 'disable' | 'delete' | 'restore',
  status: string,
) {
  if (action === 'enable' && status === 'active') return false;
  if (action === 'disable' && status !== 'active') return false;
  if (action === 'delete' && status === 'deleted') return false;
  if (action === 'restore' && status !== 'deleted') return false;
  return can(userStatusPermission(action));
}
