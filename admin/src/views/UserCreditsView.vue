<template>
  <section class="admin-user-credits">
    <header class="admin-user-credits__header">
      <div>
        <h2>用户与积分</h2>
        <p>查看用户状态、登录活跃度和积分账户，并对用户执行充值、扣减或状态调整。</p>
      </div>
      <div class="admin-user-credits__header-side">
        <div class="admin-user-credits__summary" aria-label="用户积分概览">
          <div>
            <span>总用户</span>
            <strong>{{ users.length }}</strong>
          </div>
          <div>
            <span>管理员</span>
            <strong>{{ adminCount }}</strong>
          </div>
          <div>
            <span>总积分余额</span>
            <strong>{{ totalBalance }}</strong>
          </div>
        </div>
        <el-button
          v-if="canExportUsers"
          :disabled="!filteredUsers.length || isExporting"
          :loading="isExporting"
          @click="exportCurrentUsers"
        >
          导出用户列表
        </el-button>
      </div>
    </header>

    <section class="admin-user-credits__filters" aria-label="用户筛选">
      <el-input
        v-model="search"
        clearable
        placeholder="搜索邮箱、昵称、手机号"
        @clear="loadUsers"
        @keyup.enter="loadUsers"
      />
      <el-select v-model="roleFilter" aria-label="角色筛选">
        <el-option label="全部角色" value="all" />
        <el-option label="管理员" value="admin" />
        <el-option label="普通用户" value="user" />
      </el-select>
      <el-select v-model="statusFilter" aria-label="状态筛选">
        <el-option label="全部状态" value="all" />
        <el-option label="正常" value="active" />
        <el-option label="已禁用" value="disabled" />
        <el-option label="已删除" value="deleted" />
      </el-select>
      <el-button type="primary" :loading="isLoading" @click="loadUsers">搜索</el-button>
    </section>

    <el-alert
      v-if="errorMessage"
      class="admin-user-credits__alert"
      :title="errorMessage"
      type="error"
      show-icon
      :closable="false"
    />
    <el-alert
      v-if="noticeMessage"
      class="admin-user-credits__alert"
      :title="noticeMessage"
      type="success"
      show-icon
      @close="noticeMessage = ''"
    />
    <el-alert
      v-if="duplicateGroups.length"
      class="admin-user-credits__alert"
      type="warning"
      show-icon
      :closable="false"
    >
      <template #title>
        当前列表发现 {{ duplicateGroups.length }} 组重复账号，涉及 {{ duplicateUserCount }} 个用户。
        <el-button v-if="canRunUserMerge" link type="primary" @click="openUserMergeTool">前往合并工具</el-button>
        <span v-else>需要具备用户合并权限后才能处理。</span>
      </template>
    </el-alert>

    <section class="admin-user-credits__table">
      <el-table v-loading="isLoading" :data="filteredUsers" row-key="id">
        <el-table-column label="用户" min-width="250">
          <template #default="{ row }">
            <div class="admin-user-credits__identity">
              <span class="admin-user-credits__avatar">{{ initials(row) }}</span>
              <div>
                <strong>{{ row.nickname || row.email || row.externalUserId }}</strong>
                <el-tag
                  v-if="row.duplicateIdentity"
                  class="admin-user-credits__duplicate-tag"
                  type="warning"
                  effect="light"
                >
                  重复账号 {{ row.duplicateIdentity.duplicateCount }}
                </el-tag>
                <small>{{ row.email || '未绑定邮箱' }}</small>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="row.isAdmin ? 'warning' : 'info'" effect="plain">
              {{ row.isAdmin ? (row.adminRole || '管理员') : '用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" effect="plain">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="积分" width="130" align="right">
          <template #default="{ row }">
            <strong>{{ row.credits?.balance ?? 0 }}</strong>
            <small class="admin-user-credits__muted">冻结 {{ row.credits?.reservedBalance ?? 0 }}</small>
          </template>
        </el-table-column>
        <el-table-column label="登录" width="150">
          <template #default="{ row }">
            <span>{{ row.sessionCount ?? 0 }} 个会话</span>
            <small class="admin-user-credits__muted">{{ formatDate(row.lastSeenAt) }}</small>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDate(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <div class="admin-user-credits__row-actions">
              <el-button link type="primary" @click="openDrawer(row)">详情</el-button>
              <el-dropdown
                v-if="hasUserStatusActions(row)"
                trigger="click"
                @command="(command: string) => handleUserCommand(command, row)"
              >
                <el-button link type="primary">操作</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="enable" :disabled="!canRunStatusAction('enable', row.status)">
                      启用
                    </el-dropdown-item>
                    <el-dropdown-item command="disable" :disabled="!canRunStatusAction('disable', row.status)">
                      禁用
                    </el-dropdown-item>
                    <el-dropdown-item command="restore" :disabled="!canRunStatusAction('restore', row.status)">
                      恢复
                    </el-dropdown-item>
                    <el-dropdown-item command="delete" :disabled="!canRunStatusAction('delete', row.status)">
                      删除
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-drawer v-model="drawerVisible" size="min(560px, 100vw)" :title="drawerTitle" destroy-on-close>
      <div v-if="selectedUser" class="admin-user-credits__drawer">
        <section class="admin-user-credits__profile">
          <span class="admin-user-credits__profile-avatar">{{ initials(selectedUser) }}</span>
          <div>
            <strong>{{ selectedUser.nickname || selectedUser.email || selectedUser.externalUserId }}</strong>
            <small>{{ selectedUser.email || '未绑定邮箱' }}</small>
          </div>
        </section>

        <section class="admin-user-credits__stats">
          <div>
            <span>可用余额</span>
            <strong>{{ selectedUser.credits?.balance ?? 0 }}</strong>
          </div>
          <div>
            <span>冻结积分</span>
            <strong>{{ selectedUser.credits?.reservedBalance ?? 0 }}</strong>
          </div>
          <div>
            <span>累计充值</span>
            <strong>{{ selectedUser.credits?.totalRecharged ?? 0 }}</strong>
          </div>
          <div>
            <span>累计消耗</span>
            <strong>{{ selectedUser.credits?.totalSpent ?? 0 }}</strong>
          </div>
        </section>

        <el-descriptions :column="1" border>
          <el-descriptions-item label="用户 ID">{{ selectedUser.id }}</el-descriptions-item>
          <el-descriptions-item label="外部用户 ID">{{ selectedUser.externalUserId || '未记录' }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ selectedUser.phone || '未填写' }}</el-descriptions-item>
          <el-descriptions-item label="最近登录 IP">{{ selectedUser.recentLoginIp || '未记录' }}</el-descriptions-item>
          <el-descriptions-item label="最近活跃">{{ formatDate(selectedUser.lastSeenAt) }}</el-descriptions-item>
        </el-descriptions>

        <el-divider />

        <el-form label-position="top">
          <el-form-item label="昵称">
            <el-input v-model="profileForm.nickname" placeholder="用户昵称" :disabled="!canUpdateUserProfile" />
          </el-form-item>
          <el-form-item label="手机号">
            <el-input v-model="profileForm.phone" placeholder="手机号" :disabled="!canUpdateUserProfile" />
          </el-form-item>
          <div class="admin-user-credits__drawer-actions">
            <el-button :disabled="!canUpdateUserProfile" :loading="isSaving" @click="saveProfile">保存资料</el-button>
          </div>
        </el-form>

        <el-divider />

        <el-form label-position="top">
          <el-form-item label="后台角色">
            <el-select v-model="roleForm.role" placeholder="选择后台角色" :disabled="!canUpdateUserRole">
              <el-option label="管理员" value="admin" />
              <el-option label="运营" value="operator" />
              <el-option label="只读" value="viewer" />
            </el-select>
            <small class="admin-user-credits__muted">
              {{ selectedUser.adminRoleSource === 'database' ? '数据库角色' : '配置文件角色' }}
            </small>
          </el-form-item>
          <el-form-item label="变更备注">
            <el-input
              v-model="roleForm.note"
              maxlength="120"
              placeholder="例如：临时只读、运营值班"
              :disabled="!canUpdateUserRole"
            />
          </el-form-item>
          <div class="admin-user-credits__drawer-actions">
            <el-button :disabled="!canUpdateUserRole" :loading="isSaving" @click="saveAdminRole">保存角色</el-button>
          </div>
        </el-form>

        <el-divider />

        <el-form label-position="top">
          <el-form-item label="积分调整">
            <el-input-number v-model="adjustAmount" :precision="0" :step="1" :disabled="!canAdjustCredits" />
          </el-form-item>
          <el-form-item label="调整原因">
            <el-input
              v-model="adjustReason"
              type="textarea"
              :rows="3"
              maxlength="120"
              show-word-limit
              placeholder="例如：活动充值、人工扣减、异常补偿"
              :disabled="!canAdjustCredits"
            />
          </el-form-item>
          <div class="admin-user-credits__drawer-actions">
            <el-button @click="drawerVisible = false">关闭</el-button>
            <el-button type="primary" :disabled="!canAdjustCredits" :loading="isSaving" @click="submitCreditAdjustment">
              提交调整
            </el-button>
          </div>
        </el-form>
      </div>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessageBox } from 'element-plus';
import { useRouter } from 'vue-router';

import {
  adjustUserCredits,
  fetchAdminUsers,
  setAdminUserStatus,
  updateAdminUser,
  updateAdminUserRole,
  type AdminUserStatusAction,
} from '@/api/admin';
import {
  ADMIN_PERMISSIONS,
  canRunUserStatusAction,
} from '@/adminPermissions';
import { useAdminAuthStore } from '@/stores/auth';
import type { AdminUserWithCredits } from '@/types';
import {
  createUserExportState,
  createUserCreditsState,
  creditAdjustmentConfirmMessage,
  duplicateIdentityGroups,
  friendlyAdminError,
  visibleUserExportQuery,
} from './userCreditsState';

const {
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
  loadUsers,
  replaceUser: replaceUserInState,
} = createUserCreditsState(fetchAdminUsers);

const auth = useAdminAuthStore();
const router = useRouter();
const { isExporting, exportUsers: exportUsersFromServer } = createUserExportState();
const isSaving = ref(false);
const noticeMessage = ref('');
const drawerVisible = ref(false);
const selectedUser = ref<AdminUserWithCredits | null>(null);
const adjustAmount = ref(0);
const adjustReason = ref('');
const profileForm = reactive({
  nickname: '',
  phone: '',
});
const roleForm = reactive({
  role: 'viewer',
  note: '',
});

const drawerTitle = computed(() => {
  if (!selectedUser.value) {
    return '用户详情';
  }
  return selectedUser.value.nickname || selectedUser.value.email || selectedUser.value.externalUserId;
});
const canExportUsers = computed(() => auth.can(ADMIN_PERMISSIONS.userExport));
const canUpdateUserProfile = computed(() => auth.can(ADMIN_PERMISSIONS.userUpdate));
const canUpdateUserRole = computed(() => auth.can(ADMIN_PERMISSIONS.userRoleUpdate));
const canAdjustCredits = computed(() => auth.can(ADMIN_PERMISSIONS.creditAdjust));
const canRunUserMerge = computed(() => auth.can(ADMIN_PERMISSIONS.maintenanceUserMerge));
const duplicateGroups = computed(() => duplicateIdentityGroups(filteredUsers.value));
const duplicateUserCount = computed(() =>
  duplicateGroups.value.reduce((sum, group) => sum + group.duplicateCount, 0),
);

function formatDate(value?: string | null) {
  if (!value) {
    return '暂无记录';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '暂无记录';
  }
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function initials(user: AdminUserWithCredits) {
  const source = user.nickname || user.email || user.externalUserId || 'U';
  return source.trim().slice(0, 1).toUpperCase();
}

function statusLabel(status: string) {
  if (status === 'active') {
    return '正常';
  }
  if (status === 'disabled') {
    return '已禁用';
  }
  if (status === 'deleted') {
    return '已删除';
  }
  return status || '未知';
}

function statusTagType(status: string) {
  if (status === 'active') {
    return 'success';
  }
  if (status === 'disabled') {
    return 'warning';
  }
  if (status === 'deleted') {
    return 'danger';
  }
  return 'info';
}

function canRunStatusAction(action: AdminUserStatusAction, status: string) {
  return canRunUserStatusAction((permission) => auth.can(permission), action, status);
}

function hasUserStatusActions(user: AdminUserWithCredits) {
  return (['enable', 'disable', 'delete', 'restore'] as AdminUserStatusAction[])
    .some((action) => canRunStatusAction(action, user.status));
}

function openUserMergeTool() {
  const firstIdentity = duplicateGroups.value[0]?.identity || '';
  void router.push({
    path: '/admin/settings',
    query: firstIdentity ? { mergeIdentity: firstIdentity } : undefined,
  });
}

async function exportCurrentUsers() {
  if (!canExportUsers.value || !filteredUsers.value.length) return;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    const exported = await exportUsersFromServer(visibleUserExportQuery(lastLoadedQuery.value));
    if (exported) {
      noticeMessage.value = '导出任务已开始。';
    }
  } catch (error) {
    errorMessage.value = friendlyAdminError(error, '用户列表导出失败，请稍后重试。');
  }
}

function replaceUser(user: AdminUserWithCredits) {
  replaceUserInState(user);
  if (selectedUser.value?.id === user.id) {
    selectedUser.value = user;
    syncProfileForm(user);
  }
}

function syncProfileForm(user: AdminUserWithCredits) {
  profileForm.nickname = user.nickname || '';
  profileForm.phone = user.phone || '';
  roleForm.role = user.adminRole || (user.isAdmin ? 'admin' : 'viewer');
  roleForm.note = '';
}

function openDrawer(user: AdminUserWithCredits) {
  selectedUser.value = user;
  syncProfileForm(user);
  adjustAmount.value = 0;
  adjustReason.value = '';
  drawerVisible.value = true;
}

async function handleUserCommand(command: string, user: AdminUserWithCredits) {
  if (!['enable', 'disable', 'delete', 'restore'].includes(command)) {
    return;
  }
  const action = command as AdminUserStatusAction;
  if (!canRunStatusAction(action, user.status)) {
    errorMessage.value = '当前账号没有执行该用户操作的权限。';
    return;
  }
  const label = {
    enable: '启用',
    disable: '禁用',
    delete: '删除',
    restore: '恢复',
  }[action];
  try {
    await ElMessageBox.confirm(`确认${label}该用户？`, '确认操作', {
      type: action === 'delete' || action === 'disable' ? 'warning' : 'info',
      confirmButtonText: label,
      cancelButtonText: '取消',
    });
  } catch {
    return;
  }

  isSaving.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    replaceUser(await setAdminUserStatus(user.id, action));
    noticeMessage.value = `用户已${label}。`;
  } catch (error) {
    errorMessage.value = friendlyAdminError(error, `${label}用户失败，请稍后重试。`);
  } finally {
    isSaving.value = false;
  }
}

async function saveProfile() {
  if (!selectedUser.value) {
    return;
  }
  if (!canUpdateUserProfile.value) {
    errorMessage.value = '当前账号没有保存用户资料的权限。';
    return;
  }
  isSaving.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    replaceUser(await updateAdminUser(selectedUser.value.id, {
      nickname: profileForm.nickname,
      phone: profileForm.phone,
    }));
    noticeMessage.value = '用户资料已保存。';
  } catch (error) {
    errorMessage.value = friendlyAdminError(error, '用户资料保存失败，请稍后重试。');
  } finally {
    isSaving.value = false;
  }
}

async function saveAdminRole() {
  if (!selectedUser.value) {
    return;
  }
  if (!canUpdateUserRole.value) {
    errorMessage.value = '当前账号没有修改后台角色的权限。';
    return;
  }
  try {
    await ElMessageBox.confirm(`确认将该用户后台角色设置为 ${roleForm.role}？`, '确认角色变更', {
      type: 'warning',
      confirmButtonText: '确认变更',
      cancelButtonText: '取消',
    });
  } catch {
    return;
  }
  isSaving.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    replaceUser(await updateAdminUserRole(selectedUser.value.id, {
      role: roleForm.role,
      note: roleForm.note,
    }));
    noticeMessage.value = '后台角色已更新。';
  } catch (error) {
    errorMessage.value = friendlyAdminError(error, '后台角色保存失败，请稍后重试。');
  } finally {
    isSaving.value = false;
  }
}

async function submitCreditAdjustment() {
  if (!selectedUser.value) {
    return;
  }
  if (!canAdjustCredits.value) {
    errorMessage.value = '当前账号没有调整积分的权限。';
    return;
  }
  if (!adjustAmount.value) {
    errorMessage.value = '请输入非零积分调整数。';
    return;
  }
  if (!adjustReason.value.trim()) {
    errorMessage.value = '请填写积分调整原因。';
    return;
  }
  try {
    await ElMessageBox.confirm(creditAdjustmentConfirmMessage(adjustAmount.value), '确认积分调整', {
      type: 'warning',
      confirmButtonText: '确认调整',
      cancelButtonText: '取消',
    });
  } catch {
    return;
  }
  isSaving.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    const payload = await adjustUserCredits(selectedUser.value.id, adjustAmount.value, adjustReason.value.trim());
    replaceUser(payload.user);
    adjustAmount.value = 0;
    adjustReason.value = '';
    noticeMessage.value = '积分已调整。';
  } catch (error) {
    errorMessage.value = friendlyAdminError(error, '积分调整失败，请稍后重试。');
  } finally {
    isSaving.value = false;
  }
}

onMounted(() => {
  void loadUsers();
});
</script>
