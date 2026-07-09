import { computed, ref } from 'vue';

import { buildExportFilename, downloadBlob } from '@/adminExport';
import { exportAdminUsers } from '@/api/admin';
import { AdminApiError } from '@/api/http';
import type { AdminUserDuplicateIdentity, AdminUserListQuery, AdminUserWithCredits } from '@/types';

export function friendlyAdminError(error: unknown, fallback: string): string {
  if (error instanceof AdminApiError && error.message.trim()) {
    return error.message.trim();
  }
  return fallback;
}

export function creditAdjustmentConfirmMessage(amount: number): string {
  const absolute = Math.abs(amount);
  if (amount > 0) {
    return `确认给该用户充值 ${absolute} 积分？`;
  }
  return `确认从该用户扣减 ${absolute} 积分？`;
}

export function visibleUserExportQuery(lastLoadedQuery: AdminUserListQuery): AdminUserListQuery {
  return { ...lastLoadedQuery };
}

export function duplicateIdentityGroups(users: AdminUserWithCredits[]): AdminUserDuplicateIdentity[] {
  const groups = new Map<string, AdminUserDuplicateIdentity>();
  for (const user of users) {
    const duplicate = user.duplicateIdentity;
    if (!duplicate?.identity || duplicate.duplicateCount <= 1) {
      continue;
    }
    if (!groups.has(duplicate.identity)) {
      groups.set(duplicate.identity, {
        identity: duplicate.identity,
        duplicateCount: duplicate.duplicateCount,
        targetUserId: duplicate.targetUserId,
        userIds: [...duplicate.userIds],
      });
    }
  }
  return [...groups.values()];
}

export function createUserCreditsState(loader: (query: AdminUserListQuery) => Promise<AdminUserWithCredits[]>) {
  const users = ref<AdminUserWithCredits[]>([]);
  const search = ref('');
  const roleFilter = ref('all');
  const statusFilter = ref('all');
  const lastLoadedQuery = ref<AdminUserListQuery>({ search: '', role: 'all', status: 'all' });
  const isLoading = ref(false);
  const errorMessage = ref('');
  let latestRequestId = 0;

  const selectedIds = ref<string[]>([]);
  const selectedUsers = computed(() => users.value.filter((u) => selectedIds.value.includes(u.id)));

  function setSelected(rows: AdminUserWithCredits[]) {
    selectedIds.value = rows.map((u) => u.id);
  }

  const adminCount = computed(() => users.value.filter((user) => user.isAdmin).length);
  const totalBalance = computed(() =>
    users.value.reduce((sum, user) => sum + (user.credits?.balance ?? 0), 0),
  );
  const filteredUsers = computed(() => users.value);

  async function loadUsers() {
    const requestId = latestRequestId + 1;
    const query: AdminUserListQuery = {
      search: search.value,
      role: roleFilter.value,
      status: statusFilter.value,
    };
    latestRequestId = requestId;
    isLoading.value = true;
    errorMessage.value = '';
    try {
      const result = await loader(query);
      if (requestId === latestRequestId) {
        users.value = result;
        lastLoadedQuery.value = { ...query };
      }
    } catch (error) {
      if (requestId === latestRequestId) {
        errorMessage.value = friendlyAdminError(error, '用户列表加载失败，请稍后重试。');
      }
    } finally {
      if (requestId === latestRequestId) {
        isLoading.value = false;
      }
    }
  }

  function replaceUser(user: AdminUserWithCredits) {
    const index = users.value.findIndex((item) => item.id === user.id);
    const existing = index >= 0 ? users.value[index] : null;
    const hasDuplicateIdentityField = Object.prototype.hasOwnProperty.call(user, 'duplicateIdentity');
    const nextUser = {
      ...user,
      duplicateIdentity: hasDuplicateIdentityField
        ? user.duplicateIdentity ?? null
        : existing?.duplicateIdentity ?? null,
    };
    if (index >= 0) {
      users.value.splice(index, 1, nextUser);
    } else {
      users.value.unshift(nextUser);
    }
  }

  return {
    users,
    search,
    roleFilter,
    statusFilter,
    lastLoadedQuery,
    isLoading,
    errorMessage,
    adminCount,
    totalBalance,
    filteredUsers,
    selectedIds,
    selectedUsers,
    setSelected,
    loadUsers,
    replaceUser,
  };
}

export function createUserExportState(
  exporter: (query: AdminUserListQuery) => Promise<Blob> = exportAdminUsers,
  downloader: (filename: string, blob: Blob) => void = downloadBlob,
) {
  const isExporting = ref(false);

  async function exportUsers(query: AdminUserListQuery = {}): Promise<boolean> {
    if (isExporting.value) {
      return false;
    }
    isExporting.value = true;
    try {
      const blob = await exporter(query);
      downloader(buildExportFilename('users'), blob);
      return true;
    } finally {
      isExporting.value = false;
    }
  }

  return {
    isExporting,
    exportUsers,
  };
}
