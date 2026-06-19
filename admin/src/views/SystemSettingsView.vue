<template>
  <section class="admin-content-page">
    <header class="admin-content-page__header">
      <div>
        <h2>系统设置</h2>
        <p>配置公用模型积分扣除规则、注册赠送积分，以及后续运营策略入口。</p>
      </div>
      <div class="admin-content-page__actions">
        <el-button :loading="isLoading" @click="loadSettings">刷新</el-button>
        <el-button
          v-if="canUpdateSettings"
          type="primary"
          :loading="isSaving"
          @click="saveSettings"
        >
          保存设置
        </el-button>
      </div>
    </header>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
    <el-alert v-if="noticeMessage" :title="noticeMessage" type="success" show-icon @close="noticeMessage = ''" />

    <section class="admin-settings-grid">
      <el-card shadow="never">
        <template #header>
          <div class="admin-settings-grid__head">
            <strong>默认积分价格</strong>
            <span>仅对公用模型生效，个人私有模型不扣积分。</span>
          </div>
        </template>
        <el-form label-position="top">
          <el-form-item label="文案创作">
            <el-input-number v-model="form.defaults.text" :min="0" :precision="0" :disabled="!canUpdateSettings" />
          </el-form-item>
          <el-form-item label="图片创作">
            <el-input-number v-model="form.defaults.image" :min="0" :precision="0" :disabled="!canUpdateSettings" />
          </el-form-item>
          <el-form-item label="视频创作">
            <el-input-number v-model="form.defaults.video" :min="0" :precision="0" :disabled="!canUpdateSettings" />
          </el-form-item>
        </el-form>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="admin-settings-grid__head">
            <strong>拉新活动</strong>
            <span>控制新用户注册后的赠送积分。</span>
          </div>
        </template>
        <el-form label-position="top">
          <el-form-item label="启用注册送积分">
            <el-switch
              v-model="form.signupBonusEnabled"
              active-text="启用"
              inactive-text="停用"
              :disabled="!canUpdateSettings"
            />
          </el-form-item>
          <el-form-item label="赠送积分">
            <el-input-number
              v-model="form.signupBonusAmount"
              :min="0"
              :precision="0"
              :disabled="!canUpdateSettings"
            />
          </el-form-item>
        </el-form>
      </el-card>

      <el-card v-if="canRunUserMerge" shadow="never" class="admin-maintenance-card">
        <template #header>
          <div class="admin-settings-grid__head">
            <strong>重复用户合并</strong>
            <span>先预览同邮箱或手机号的重复账号，确认后再迁移关联数据并删除重复用户。</span>
          </div>
        </template>
        <el-form label-position="top">
          <el-form-item label="身份过滤">
            <el-input
              v-model="mergeIdentityFilter"
              placeholder="例如 email:dup@example.com，可留空扫描全部"
              clearable
            />
          </el-form-item>
          <div class="admin-maintenance-card__actions">
            <el-button :loading="isPreviewingMerge" @click="previewUserMerge">预览重复用户</el-button>
            <el-button
              type="danger"
              :disabled="!mergeSummary || !mergeSummary.groupCount"
              :loading="isApplyingMerge"
              @click="confirmUserMerge"
            >
              确认合并
            </el-button>
          </div>
        </el-form>
        <div v-if="mergeSummary" class="admin-maintenance-summary">
          <div>
            <strong>{{ mergeSummary.groupCount }}</strong>
            <span>重复组</span>
          </div>
          <div>
            <strong>{{ mergeSummary.mergedUsers }}</strong>
            <span>待合并用户</span>
          </div>
          <div>
            <strong>{{ mergeSummary.movedRecords }}</strong>
            <span>迁移记录</span>
          </div>
          <div>
            <strong>{{ mergeSummary.roleConflictCount || 0 }}</strong>
            <span>角色冲突</span>
          </div>
        </div>
        <el-table v-if="mergeSummary?.groups.length" :data="mergeSummary.groups" size="small">
          <el-table-column prop="identity" label="重复身份" min-width="180" />
          <el-table-column prop="targetUserId" label="保留用户" min-width="160" />
          <el-table-column label="合并来源" min-width="220">
            <template #default="{ row }">{{ row.sourceUserIds.join(', ') }}</template>
          </el-table-column>
          <el-table-column prop="movedRecords" label="迁移记录" width="100" />
          <el-table-column label="角色冲突" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.roleConflicts?.length" type="warning" effect="light">
                {{ row.roleConflicts.length }} 个
              </el-tag>
              <span v-else class="admin-maintenance-muted">无</span>
            </template>
          </el-table-column>
          <el-table-column type="expand">
            <template #default="{ row }">
              <div v-if="row.roleConflicts?.length" class="admin-role-conflicts">
                <div
                  v-for="conflict in row.roleConflicts"
                  :key="`${conflict.sourceUserId}-${conflict.discardedRole}`"
                  class="admin-role-conflict"
                >
                  <span>来源 {{ conflict.sourceUserId }}</span>
                  <strong>{{ conflict.discardedRole }}</strong>
                  <span>未覆盖保留用户的</span>
                  <strong>{{ conflict.targetRole }}</strong>
                </div>
              </div>
              <span v-else class="admin-maintenance-muted">该组没有角色冲突。</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessageBox } from 'element-plus';
import { useRoute } from 'vue-router';

import { ADMIN_PERMISSIONS } from '@/adminPermissions';
import { fetchCreditSettings, runUserMergeMaintenance, saveCreditSettings } from '@/api/admin';
import { AdminApiError } from '@/api/http';
import { useAdminAuthStore } from '@/stores/auth';
import type { UserMergeSummary } from '@/types';

const auth = useAdminAuthStore();
const route = useRoute();
const isLoading = ref(false);
const isSaving = ref(false);
const errorMessage = ref('');
const noticeMessage = ref('');
const mergeIdentityFilter = ref('');
const mergeSummary = ref<UserMergeSummary | null>(null);
const isPreviewingMerge = ref(false);
const isApplyingMerge = ref(false);
const form = reactive({
  defaults: {
    text: 0,
    image: 1,
    video: 0,
  },
  signupBonusEnabled: false,
  signupBonusAmount: 0,
});
const canUpdateSettings = computed(() => auth.can(ADMIN_PERMISSIONS.creditSettings));
const canRunUserMerge = computed(() => auth.can(ADMIN_PERMISSIONS.maintenanceUserMerge));

function friendlyError(error: unknown, fallback: string) {
  return error instanceof AdminApiError && error.message.trim() ? error.message.trim() : fallback;
}

async function loadSettings() {
  isLoading.value = true;
  errorMessage.value = '';
  try {
    const settings = await fetchCreditSettings();
    form.defaults.text = settings.defaults.text ?? 0;
    form.defaults.image = settings.defaults.image ?? 1;
    form.defaults.video = settings.defaults.video ?? 0;
    form.signupBonusEnabled = Boolean(settings.signupBonusEnabled);
    form.signupBonusAmount = settings.signupBonusAmount ?? 0;
  } catch (error) {
    errorMessage.value = friendlyError(error, '系统设置加载失败，请稍后重试。');
  } finally {
    isLoading.value = false;
  }
}

async function saveSettings() {
  if (!canUpdateSettings.value) {
    errorMessage.value = '当前账号没有保存系统设置的权限。';
    return;
  }
  isSaving.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    const settings = await saveCreditSettings({
      defaults: { ...form.defaults },
      signupBonusEnabled: form.signupBonusEnabled,
      signupBonusAmount: form.signupBonusAmount,
    });
    form.defaults.text = settings.defaults.text ?? 0;
    form.defaults.image = settings.defaults.image ?? 1;
    form.defaults.video = settings.defaults.video ?? 0;
    form.signupBonusEnabled = Boolean(settings.signupBonusEnabled);
    form.signupBonusAmount = settings.signupBonusAmount ?? 0;
    noticeMessage.value = '系统设置已保存。';
  } catch (error) {
    errorMessage.value = friendlyError(error, '系统设置保存失败，请稍后重试。');
  } finally {
    isSaving.value = false;
  }
}

async function previewUserMerge() {
  isPreviewingMerge.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    mergeSummary.value = await runUserMergeMaintenance({
      apply: false,
      identityFilter: mergeIdentityFilter.value.trim(),
    });
    noticeMessage.value = mergeSummary.value.groupCount
      ? `发现 ${mergeSummary.value.groupCount} 组重复用户，请确认后再执行合并。`
      : '没有发现需要合并的重复用户。';
  } catch (error) {
    errorMessage.value = friendlyError(error, '重复用户预览失败，请稍后重试。');
  } finally {
    isPreviewingMerge.value = false;
  }
}

async function confirmUserMerge() {
  if (!mergeSummary.value?.groupCount) return;
  try {
    await ElMessageBox.confirm(
      `确认合并 ${mergeSummary.value.mergedUsers} 个重复用户吗？该操作会迁移关联记录并删除重复账号。`,
      '确认用户合并',
      { type: 'warning', confirmButtonText: '确认合并', cancelButtonText: '取消' },
    );
  } catch {
    return;
  }
  isApplyingMerge.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    mergeSummary.value = await runUserMergeMaintenance({
      apply: true,
      identityFilter: mergeIdentityFilter.value.trim(),
    });
    const conflictText = mergeSummary.value.roleConflictCount
      ? `，发现 ${mergeSummary.value.roleConflictCount} 个角色冲突，已保留目标用户角色`
      : '';
    noticeMessage.value = `已合并 ${mergeSummary.value.mergedUsers} 个用户，迁移 ${mergeSummary.value.movedRecords} 条关联记录${conflictText}。`;
  } catch (error) {
    errorMessage.value = friendlyError(error, '重复用户合并失败，请稍后重试。');
  } finally {
    isApplyingMerge.value = false;
  }
}

onMounted(() => {
  const mergeIdentity = route.query.mergeIdentity;
  if (typeof mergeIdentity === 'string') {
    mergeIdentityFilter.value = mergeIdentity;
  }
  void loadSettings();
});
</script>
