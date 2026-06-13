import { describe, expect, it } from 'vitest';

import {
  ADMIN_PERMISSIONS,
  canEditModel,
  canEditModelPricing,
  canPublishModel,
  canRemoveUnavailableModels,
  canTestModel,
  canRunUserStatusAction,
  canUnpublishModel,
  makePermissionChecker,
} from './adminPermissions';

describe('admin permission helpers', () => {
  it('keeps credit settings permission names aligned with backend contracts', () => {
    expect(ADMIN_PERMISSIONS.creditView).toBe('credit:view');
    expect(ADMIN_PERMISSIONS.creditSettings).toBe('credit:settings');
    expect(ADMIN_PERMISSIONS.userExport).toBe('user:export');
    expect(ADMIN_PERMISSIONS.recordExport).toBe('record:export');
    expect(ADMIN_PERMISSIONS.auditExport).toBe('audit:export');
    expect(ADMIN_PERMISSIONS.settingsView).toBe('settings:view');
    expect(ADMIN_PERMISSIONS.settingsUpdate).toBe('settings:update');
    expect(ADMIN_PERMISSIONS.maintenanceUserMerge).toBe('maintenance:user_merge');
  });

  it('checks model actions against permission points and editable state', () => {
    const can = makePermissionChecker([
      ADMIN_PERMISSIONS.modelPublish,
      ADMIN_PERMISSIONS.modelUpdate,
    ]);

    expect(canPublishModel(can, false, true)).toBe(true);
    expect(canPublishModel(can, true, true)).toBe(false);
    expect(canPublishModel(can, false, false)).toBe(false);
    expect(canUnpublishModel(can, true, true)).toBe(false);
    expect(canEditModel(can, true)).toBe(true);
    expect(canEditModelPricing(can, true)).toBe(false);
  });

  it('allows model health checks from the model:test permission without requiring edit access', () => {
    const can = makePermissionChecker([ADMIN_PERMISSIONS.modelTest]);

    expect(canTestModel(can)).toBe(true);
  });

  it('gates unavailable model removal behind model delete permission', () => {
    const canDelete = makePermissionChecker([ADMIN_PERMISSIONS.modelDelete]);
    const cannotDelete = makePermissionChecker([ADMIN_PERMISSIONS.modelTest]);

    expect(ADMIN_PERMISSIONS.modelDelete).toBe('model:delete');
    expect(canRemoveUnavailableModels(canDelete)).toBe(true);
    expect(canRemoveUnavailableModels(cannotDelete)).toBe(false);
  });

  it('checks user status actions against permissions and current status', () => {
    const can = makePermissionChecker([
      ADMIN_PERMISSIONS.userUpdate,
      ADMIN_PERMISSIONS.userDisable,
      ADMIN_PERMISSIONS.userRestore,
    ]);

    expect(canRunUserStatusAction(can, 'enable', 'disabled')).toBe(true);
    expect(canRunUserStatusAction(can, 'enable', 'active')).toBe(false);
    expect(canRunUserStatusAction(can, 'disable', 'active')).toBe(true);
    expect(canRunUserStatusAction(can, 'delete', 'active')).toBe(false);
    expect(canRunUserStatusAction(can, 'restore', 'deleted')).toBe(true);
    expect(canRunUserStatusAction(can, 'restore', 'active')).toBe(false);
  });
});
