<template>
  <section class="admin-content-page">
    <header class="admin-content-page__header">
      <div>
        <h2>系统设置</h2>
        <p>配置公用模型积分扣除规则、注册赠送积分，以及后续运营策略入口。</p>
      </div>
      <div class="admin-content-page__actions">
        <el-button :loading="isLoading" @click="loadSettings">刷新</el-button>
        <el-button v-if="canUpdateCreditSettings && isCreditSettingsDirty" @click="revertCreditSettings">取消更改</el-button>
        <el-button
          v-if="canUpdateCreditSettings"
          type="primary"
          :loading="isSaving"
          :disabled="!isCreditSettingsDirty"
          @click="saveSettings"
        >
          保存设置
        </el-button>
      </div>
    </header>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
    <el-alert v-if="noticeMessage" :title="noticeMessage" type="success" show-icon @close="noticeMessage = ''" />

    <div class="admin-settings-section-head">
      <strong>计费与活动</strong>
      <span>面向全站公用模型和新用户的计费规则。</span>
    </div>
    <section class="admin-settings-grid">
      <el-card v-if="canViewCreditSettings" shadow="never">
        <template #header>
          <div class="admin-settings-grid__head">
            <strong>默认积分价格</strong>
            <span>仅对公用模型生效，个人私有模型不扣积分。</span>
          </div>
        </template>
        <el-form label-position="top">
          <el-form-item label="文案创作">
            <el-input-number v-model="form.defaults.text" :min="0" :precision="0" :disabled="!canUpdateCreditSettings" />
          </el-form-item>
          <el-form-item label="图片创作">
            <el-input-number v-model="form.defaults.image" :min="0" :precision="0" :disabled="!canUpdateCreditSettings" />
          </el-form-item>
          <el-form-item label="视频创作">
            <el-input-number v-model="form.defaults.video" :min="0" :precision="0" :disabled="!canUpdateCreditSettings" />
          </el-form-item>
        </el-form>
      </el-card>

      <el-card v-if="canViewCreditSettings" shadow="never">
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
              :disabled="!canUpdateCreditSettings"
            />
          </el-form-item>
          <el-form-item label="赠送积分">
            <el-input-number
              v-model="form.signupBonusAmount"
              :min="0"
              :precision="0"
              :disabled="!canUpdateCreditSettings"
            />
          </el-form-item>
        </el-form>
      </el-card>

      </section>

      <div class="admin-settings-section-head admin-settings-section-head--danger">
        <strong>运维与维护</strong>
        <span>以下为谨慎 / 不可逆操作，请确认后再执行。</span>
      </div>
      <section class="admin-settings-grid">
      <el-card v-if="canViewAssetCleanup" shadow="never" class="admin-maintenance-card admin-asset-storage-card">
        <template #header>
          <div class="admin-settings-grid__head admin-asset-cleanup-card__head admin-asset-storage-card__head">
            <div>
              <strong>图片存储与同步</strong>
              <span>本地缓存负责即时访问，R2 承担长期存储与缩略图分发。</span>
            </div>
            <el-tag :type="assetSyncForm.enabled ? 'success' : 'info'" effect="light">
              {{ assetSyncForm.enabled ? '自动同步已启用' : '自动同步已停用' }}
            </el-tag>
          </div>
        </template>

        <section class="admin-asset-sync-section">
          <el-alert
            type="info"
            show-icon
            :closable="false"
            title="原图与缩略图在本地固定缓存 24 小时；到期后，已同步内容只返回 R2 地址，未同步内容继续保留本地副本。"
          />
          <el-form label-position="top" class="admin-asset-sync-form">
            <el-form-item label="自动同步">
              <el-switch
                v-model="assetSyncForm.enabled"
                active-text="启用"
                inactive-text="停用"
                :disabled="!canManageAssetCleanup"
              />
            </el-form-item>
            <el-form-item label="执行间隔（秒）">
              <el-input-number
                v-model="assetSyncForm.intervalSeconds"
                :min="assetSyncForm.minIntervalSeconds"
                :max="assetSyncForm.maxIntervalSeconds"
                :step="15"
                :precision="0"
                :disabled="!canManageAssetCleanup"
              />
            </el-form-item>
            <el-form-item label="单批处理数量">
              <el-input-number
                v-model="assetSyncForm.batchSize"
                :min="assetSyncForm.minBatchSize"
                :max="assetSyncForm.maxBatchSize"
                :precision="0"
                :disabled="!canManageAssetCleanup"
              />
            </el-form-item>
          </el-form>

          <div class="admin-asset-sync-actions">
            <el-button :icon="View" :loading="isPreviewingAssetSync" @click="refreshAssetSyncPreview">
              刷新状态
            </el-button>
            <el-button
              v-if="canManageAssetCleanup"
              :icon="Check"
              :loading="isSavingAssetSync"
              @click="saveAssetStorageSettings"
            >
              保存同步策略
            </el-button>
            <el-button
              v-if="canManageAssetCleanup"
              type="primary"
              :icon="UploadFilled"
              :loading="isRunningAssetSync"
              @click="runAssetStorageSync"
            >
              立即同步
            </el-button>
            <el-button
              v-if="canManageAssetCleanup"
              :icon="RefreshLeft"
              :disabled="!assetSyncSummary.failureCount"
              :loading="isRetryingAssetSync"
              @click="retryFailedAssets"
            >
              重试失败
            </el-button>
          </div>

          <div class="admin-asset-sync-metrics" aria-label="图片同步指标">
            <div>
              <strong>{{ assetSyncSummary.totalAssets }}</strong>
              <span>全部图片</span>
            </div>
            <div>
              <strong>{{ assetSyncStatusCount('r2_synced') }}</strong>
              <span>R2 已同步</span>
            </div>
            <div>
              <strong>{{ pendingAssetSyncCount }}</strong>
              <span>等待处理</span>
            </div>
            <div>
              <strong>{{ assetSyncSummary.failureCount }}</strong>
              <span>同步失败</span>
            </div>
            <div>
              <strong>{{ formatBytes(assetSyncSummary.localBytes) }}</strong>
              <span>本地占用</span>
            </div>
          </div>

          <div class="admin-asset-sync-runline">
            <span>上次自动执行：{{ formatDateTime(assetSyncForm.lastAutoRun?.ranAt) }}</span>
            <span>上次执行结果：{{ assetSyncLastResult }}</span>
          </div>

          <div v-if="assetSyncSummary.failures.length" class="admin-asset-sync-failures">
            <div class="admin-asset-sync-failures__head">
              <strong>同步失败明细</strong>
              <span>最多展示最近 20 条，不暴露本地路径或对象存储密钥。</span>
            </div>
            <el-table :data="assetSyncSummary.failures" size="small">
              <el-table-column prop="assetId" label="图片 ID" min-width="180" />
              <el-table-column prop="message" label="失败原因" min-width="240" show-overflow-tooltip />
              <el-table-column prop="attempts" label="尝试" width="76" />
              <el-table-column label="大小" width="110">
                <template #default="{ row }">{{ formatBytes(row.sizeBytes) }}</template>
              </el-table-column>
              <el-table-column label="更新时间" min-width="170">
                <template #default="{ row }">{{ formatDateTime(row.updatedAt) }}</template>
              </el-table-column>
            </el-table>
          </div>
        </section>

        <section class="admin-asset-orphan-cleanup">
          <div class="admin-asset-orphan-cleanup__head">
            <div>
              <strong>孤儿缓存清理</strong>
              <span>只处理未被数据库跟踪的过期文件；未完成 R2 同步的唯一副本始终受保护。</span>
            </div>
            <el-tag :type="assetCleanupForm.enabled ? 'success' : 'info'" effect="plain">
              {{ assetCleanupForm.enabled ? '每日扫描' : '定时扫描已停用' }}
            </el-tag>
          </div>
        <el-alert
          class="admin-asset-cleanup-card__notice"
          type="info"
          show-icon
          :closable="false"
          :title="`默认保留 ${assetCleanupForm.defaultRetentionDays || 7} 天；当前策略：图片缓存保留 ${assetCleanupForm.retentionDays || assetCleanupForm.defaultRetentionDays || 7} 天，超过后由后台定时任务清理；也可在此手动执行。只清理生成图片缓存和上传参考图缓存，不删除数据库创作记录。`"
        />
        <el-form label-position="top">
          <div class="admin-asset-cleanup-card__form">
            <el-form-item label="启用定时清理">
              <el-switch
                v-model="assetCleanupForm.enabled"
                active-text="启用"
                inactive-text="停用"
                :disabled="!canManageAssetCleanup"
                @change="clearAssetCleanupPreview"
              />
            </el-form-item>
            <el-form-item label="缓存保留天数">
              <el-input-number
                v-model="assetCleanupForm.retentionDays"
                :min="assetCleanupForm.minRetentionDays || 1"
                :max="assetCleanupForm.maxRetentionDays || 365"
                :precision="0"
                :disabled="!canManageAssetCleanup"
                @change="clearAssetCleanupPreview"
              />
            </el-form-item>
          </div>
          <div class="admin-maintenance-card__actions admin-asset-cleanup-card__actions">
            <div class="admin-asset-cleanup-card__safe-actions">
              <el-button :loading="isPreviewingAssetCleanup" @click="previewAssetCacheCleanup">
                预览可清理缓存
              </el-button>
              <el-button
                v-if="canManageAssetCleanup"
                :loading="isSavingAssetCleanup"
                @click="saveAssetCacheCleanupSettings"
              >
                保存清理策略
              </el-button>
            </div>
            <div v-if="canManageAssetCleanup" class="admin-asset-cleanup-card__danger-actions">
              <el-button
                type="danger"
                :disabled="!assetCleanupSummary || assetCleanupSummary.expiredFiles <= 0"
                :loading="isRunningAssetCleanup"
                @click="confirmAssetCacheCleanup"
              >
                手动清理
              </el-button>
            </div>
          </div>
        </el-form>
        <div v-if="assetCleanupSummary" class="admin-maintenance-summary">
          <div>
            <strong>{{ assetCleanupSummary.totalFiles }}</strong>
            <span>缓存文件</span>
          </div>
          <div>
            <strong>{{ assetCleanupSummary.expiredFiles }}</strong>
            <span>超过 {{ assetCleanupSummary.retentionDays }} 天</span>
          </div>
          <div>
            <strong>{{ formatBytes(assetCleanupSummary.expiredBytes) }}</strong>
            <span>预计释放</span>
          </div>
          <div>
            <strong>{{ assetCleanupSummary.deletedFiles ?? 0 }}</strong>
            <span>本次已删除</span>
          </div>
          <div>
            <strong>{{ assetCleanupSummary.protectedFiles ?? 0 }}</strong>
            <span>受保护文件</span>
          </div>
        </div>
        <el-table v-if="assetCleanupSummary?.targets.length" :data="assetCleanupSummary.targets" size="small">
          <el-table-column prop="label" label="缓存目录" min-width="150" />
          <el-table-column label="路径" min-width="260" class-name="admin-asset-cleanup-card__path-col" label-class-name="admin-asset-cleanup-card__path-col">
            <template #default="{ row }">
              <span class="admin-maintenance-muted">{{ row.path }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="totalFiles" label="文件数" width="100" />
          <el-table-column prop="expiredFiles" label="可清理" width="100" />
          <el-table-column label="预计释放" width="120">
            <template #default="{ row }">{{ formatBytes(row.expiredBytes) }}</template>
          </el-table-column>
        </el-table>
        <div v-if="assetCleanupForm.lastRun?.ranAt" class="admin-asset-cleanup-card__last-run">
          上次清理：{{ formatDateTime(assetCleanupForm.lastRun.ranAt) }}，
          删除 {{ assetCleanupForm.lastRun.deletedFiles ?? 0 }} 个文件，
          释放 {{ formatBytes(Number(assetCleanupForm.lastRun.deletedBytes || 0)) }}。
        </div>
        </section>
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
import { Check, RefreshLeft, UploadFilled, View } from '@element-plus/icons-vue';
import { useRoute } from 'vue-router';

import { ADMIN_PERMISSIONS } from '@/adminPermissions';
import {
  fetchAssetCleanupSettings,
  fetchAssetSyncSettings,
  fetchCreditSettings,
  previewAssetCleanup,
  previewAssetSync,
  retryFailedAssetSync,
  runAssetCleanup,
  runAssetSync,
  runUserMergeMaintenance,
  saveAssetCleanupSettings,
  saveAssetSyncSettings,
  saveCreditSettings,
} from '@/api/admin';
import { AdminApiError } from '@/api/http';
import { useAdminAuthStore } from '@/stores/auth';
import type {
  AssetCleanupSettings,
  AssetCleanupSummary,
  AssetSyncPayload,
  AssetSyncSettings,
  AssetSyncSummary,
  UserMergeSummary,
} from '@/types';

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
const assetCleanupSummary = ref<AssetCleanupSummary | null>(null);
const assetCleanupPreviewRetentionDays = ref(7);
const isSavingAssetCleanup = ref(false);
const isPreviewingAssetCleanup = ref(false);
const isRunningAssetCleanup = ref(false);
const isSavingAssetSync = ref(false);
const isPreviewingAssetSync = ref(false);
const isRunningAssetSync = ref(false);
const isRetryingAssetSync = ref(false);
const form = reactive({
  defaults: {
    text: 0,
    image: 1,
    video: 0,
  },
  signupBonusEnabled: false,
  signupBonusAmount: 0,
});
const assetCleanupForm = reactive<AssetCleanupSettings>({
  enabled: true,
  retentionDays: 7,
  defaultRetentionDays: 7,
  minRetentionDays: 1,
  maxRetentionDays: 365,
  lastRun: {},
});
const assetSyncForm = reactive<AssetSyncSettings>({
  enabled: true,
  intervalSeconds: 60,
  batchSize: 8,
  localTtlHours: 24,
  localTtlFixed: true,
  minIntervalSeconds: 15,
  maxIntervalSeconds: 3600,
  minBatchSize: 1,
  maxBatchSize: 100,
  lastRun: {},
  lastAutoRun: {},
});
const assetSyncSummary = ref<AssetSyncSummary>({
  totalAssets: 0,
  totalBytes: 0,
  localBytes: 0,
  eligibleAssets: 0,
  statusCounts: {},
  failureCount: 0,
  failures: [],
});
const canViewCreditSettings = computed(() => auth.can(ADMIN_PERMISSIONS.creditView));

const savedSnapshot = ref('');
function snapshotForm(): string {
  return JSON.stringify({
    defaults: { ...form.defaults },
    signupBonusEnabled: form.signupBonusEnabled,
    signupBonusAmount: form.signupBonusAmount,
  });
}
const isCreditSettingsDirty = computed(() => savedSnapshot.value !== '' && savedSnapshot.value !== snapshotForm());
function revertCreditSettings() {
  if (!savedSnapshot.value) return;
  const parsed = JSON.parse(savedSnapshot.value);
  form.defaults.text = parsed.defaults?.text ?? 0;
  form.defaults.image = parsed.defaults?.image ?? 1;
  form.defaults.video = parsed.defaults?.video ?? 0;
  form.signupBonusEnabled = Boolean(parsed.signupBonusEnabled);
  form.signupBonusAmount = parsed.signupBonusAmount ?? 0;
}
const canUpdateCreditSettings = computed(() => auth.can(ADMIN_PERMISSIONS.creditSettings));
const canRunUserMerge = computed(() => auth.can(ADMIN_PERMISSIONS.maintenanceUserMerge));
const canManageAssetCleanup = computed(() => auth.can(ADMIN_PERMISSIONS.maintenanceAssetCleanup));
const canViewAssetCleanup = computed(() => auth.can(ADMIN_PERMISSIONS.settingsView) || canManageAssetCleanup.value);
const pendingAssetSyncCount = computed(() => (
  assetSyncStatusCount('local_pending')
  + assetSyncStatusCount('remote_pending')
  + assetSyncStatusCount('syncing')
));
const assetSyncLastResult = computed(() => {
  const result = assetSyncForm.lastRun;
  if (!result?.ranAt) return '尚未执行';
  if (result.status === 'failed') return result.message || '执行失败';
  if (result.skipped === 'object_storage_disabled') return 'R2 未启用';
  return `${result.synced ?? 0} 成功 · ${result.failed ?? 0} 失败 · ${result.removed ?? 0} 个本地副本已释放`;
});

function friendlyError(error: unknown, fallback: string) {
  return error instanceof AdminApiError && error.message.trim() ? error.message.trim() : fallback;
}

function applyAssetCleanupSettings(settings: AssetCleanupSettings) {
  assetCleanupForm.enabled = Boolean(settings.enabled);
  assetCleanupForm.retentionDays = settings.retentionDays ?? 7;
  assetCleanupForm.defaultRetentionDays = settings.defaultRetentionDays ?? 7;
  assetCleanupForm.minRetentionDays = settings.minRetentionDays ?? 1;
  assetCleanupForm.maxRetentionDays = settings.maxRetentionDays ?? 365;
  assetCleanupForm.lastRun = settings.lastRun ?? {};
}

function applyAssetSyncPayload(payload: AssetSyncPayload) {
  Object.assign(assetSyncForm, payload.settings);
  assetSyncSummary.value = payload.summary;
}

function assetSyncStatusCount(status: string) {
  return Number(assetSyncSummary.value.statusCounts[status] || 0);
}

function clearAssetCleanupPreview() {
  assetCleanupSummary.value = null;
  assetCleanupPreviewRetentionDays.value = assetCleanupForm.retentionDays || assetCleanupForm.defaultRetentionDays || 7;
}

function formatBytes(value: number | undefined) {
  const bytes = Number(value || 0);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatDateTime(value: unknown) {
  if (typeof value !== 'string' || !value) return '未知时间';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
}

async function loadSettings() {
  isLoading.value = true;
  errorMessage.value = '';
  try {
    const [settings, syncPayload, cleanupSettings] = await Promise.all([
      canViewCreditSettings.value ? fetchCreditSettings() : Promise.resolve(null),
      canViewAssetCleanup.value ? fetchAssetSyncSettings() : Promise.resolve(null),
      canViewAssetCleanup.value ? fetchAssetCleanupSettings() : Promise.resolve(null),
    ]);
    if (settings) {
      form.defaults.text = settings.defaults.text ?? 0;
      form.defaults.image = settings.defaults.image ?? 1;
      form.defaults.video = settings.defaults.video ?? 0;
      form.signupBonusEnabled = Boolean(settings.signupBonusEnabled);
      form.signupBonusAmount = settings.signupBonusAmount ?? 0;
    }
    if (cleanupSettings) {
      applyAssetCleanupSettings(cleanupSettings);
    }
    if (syncPayload) {
      applyAssetSyncPayload(syncPayload);
    }
    savedSnapshot.value = snapshotForm();
  } catch (error) {
    errorMessage.value = friendlyError(error, '系统设置加载失败，请稍后重试。');
  } finally {
    isLoading.value = false;
  }
}

async function saveSettings() {
  if (!canUpdateCreditSettings.value) {
    errorMessage.value = '当前账号没有保存系统设置的权限。';
    return;
  }
  try {
    await ElMessageBox.confirm(
      '保存后新的默认积分价格将立即对所有使用「默认」价格的公用模型生效，注册赠送规则也会同步更新。确认保存？',
      '确认保存系统设置',
      { type: 'warning', confirmButtonText: '确认保存', cancelButtonText: '取消' },
    );
  } catch {
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
    savedSnapshot.value = snapshotForm();
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

async function saveAssetStorageSettings() {
  if (!canManageAssetCleanup.value) {
    errorMessage.value = '当前账号没有保存图片同步策略的权限。';
    return;
  }
  isSavingAssetSync.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    const payload = await saveAssetSyncSettings({
      enabled: assetSyncForm.enabled,
      intervalSeconds: assetSyncForm.intervalSeconds,
      batchSize: assetSyncForm.batchSize,
    });
    applyAssetSyncPayload(payload);
    noticeMessage.value = `图片同步策略已保存，每 ${payload.settings.intervalSeconds} 秒处理最多 ${payload.settings.batchSize} 张。`;
  } catch (error) {
    errorMessage.value = friendlyError(error, '图片同步策略保存失败，请稍后重试。');
  } finally {
    isSavingAssetSync.value = false;
  }
}

async function refreshAssetSyncPreview() {
  isPreviewingAssetSync.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    const payload = await previewAssetSync();
    applyAssetSyncPayload(payload);
    noticeMessage.value = `同步状态已刷新，当前有 ${payload.summary.eligibleAssets} 张图片可处理。`;
  } catch (error) {
    errorMessage.value = friendlyError(error, '图片同步状态刷新失败，请稍后重试。');
  } finally {
    isPreviewingAssetSync.value = false;
  }
}

async function runAssetStorageSync() {
  isRunningAssetSync.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    const payload = await runAssetSync();
    applyAssetSyncPayload(payload);
    noticeMessage.value = `同步完成：${payload.result?.synced ?? 0} 张成功，${payload.result?.failed ?? 0} 张失败。`;
  } catch (error) {
    errorMessage.value = friendlyError(error, '立即同步执行失败，请稍后重试。');
  } finally {
    isRunningAssetSync.value = false;
  }
}

async function retryFailedAssets() {
  if (!assetSyncSummary.value.failureCount) return;
  isRetryingAssetSync.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    const payload = await retryFailedAssetSync();
    applyAssetSyncPayload(payload);
    noticeMessage.value = `已将 ${payload.result?.reset ?? 0} 张失败图片重新加入同步队列。`;
  } catch (error) {
    errorMessage.value = friendlyError(error, '失败任务重置失败，请稍后重试。');
  } finally {
    isRetryingAssetSync.value = false;
  }
}

async function saveAssetCacheCleanupSettings() {
  if (!canManageAssetCleanup.value) {
    errorMessage.value = '当前账号没有保存图片缓存清理策略的权限。';
    return;
  }
  isSavingAssetCleanup.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    const settings = await saveAssetCleanupSettings({
      enabled: assetCleanupForm.enabled,
      retentionDays: assetCleanupForm.retentionDays,
    });
    applyAssetCleanupSettings(settings);
    noticeMessage.value = `图片缓存清理策略已保存，当前保留 ${settings.retentionDays} 天。`;
  } catch (error) {
    errorMessage.value = friendlyError(error, '图片缓存清理策略保存失败，请稍后重试。');
  } finally {
    isSavingAssetCleanup.value = false;
  }
}

async function previewAssetCacheCleanup() {
  isPreviewingAssetCleanup.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    const payload = await previewAssetCleanup();
    applyAssetCleanupSettings(payload.settings);
    assetCleanupSummary.value = payload.summary;
    assetCleanupPreviewRetentionDays.value = payload.summary.retentionDays;
    noticeMessage.value = payload.summary.expiredFiles
      ? `发现 ${payload.summary.expiredFiles} 个超过 ${payload.summary.retentionDays} 天的图片缓存，预计释放 ${formatBytes(payload.summary.expiredBytes)}。`
      : `没有超过 ${payload.summary.retentionDays} 天的图片缓存。`;
  } catch (error) {
    errorMessage.value = friendlyError(error, '图片缓存预览失败，请稍后重试。');
  } finally {
    isPreviewingAssetCleanup.value = false;
  }
}

async function confirmAssetCacheCleanup() {
  const expiredFiles = assetCleanupSummary.value?.expiredFiles ?? 0;
  if (expiredFiles <= 0) return;
  try {
    await ElMessageBox.confirm(
      `确认删除 ${expiredFiles} 个超过 ${assetCleanupPreviewRetentionDays.value} 天的图片缓存文件吗？数据库里的创作记录不会删除。`,
      '确认清理图片缓存',
      { type: 'warning', confirmButtonText: '确认清理', cancelButtonText: '取消' },
    );
  } catch {
    return;
  }
  isRunningAssetCleanup.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    const payload = await runAssetCleanup({ retentionDays: assetCleanupPreviewRetentionDays.value });
    applyAssetCleanupSettings(payload.settings);
    assetCleanupSummary.value = payload.summary;
    noticeMessage.value = `已清理 ${payload.summary.deletedFiles ?? 0} 个图片缓存文件，释放 ${formatBytes(payload.summary.deletedBytes)}。`;
  } catch (error) {
    errorMessage.value = friendlyError(error, '图片缓存清理失败，请稍后重试。');
  } finally {
    isRunningAssetCleanup.value = false;
  }
}

async function confirmUserMerge() {
  if (!mergeSummary.value?.groupCount) return;
  try {
    const affectedIds = mergeSummary.value.groups.flatMap((group) => group.sourceUserIds);
    await ElMessageBox.confirm(
      `确认合并 ${mergeSummary.value.mergedUsers} 个重复用户吗？将删除并迁移这些账号：${affectedIds.slice(0, 8).join('、')}${affectedIds.length > 8 ? ` 等 ${affectedIds.length} 个` : ''}。`,
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
