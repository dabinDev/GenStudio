<template>
  <section class="admin-model-center">
    <header class="admin-model-center__header">
      <div>
        <h2>{{ MODEL_CENTER_TITLE }}</h2>
        <p>管理模型的公开展示信息、积分价格和公用状态。</p>
      </div>
      <div class="admin-model-center__batch">
        <el-dropdown
          trigger="click"
          :disabled="!hasSelectedModels || isSaving || isBatchTesting"
          @command="(command: string) => handleBatchCommand(command)"
        >
          <el-button type="primary" :disabled="!hasSelectedModels || isSaving || isBatchTesting">
            批量操作
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-if="auth.can(ADMIN_PERMISSIONS.modelTest)"
                command="health-check"
                :disabled="!hasSelectedModels || isBatchTesting"
              >
                批量测试
              </el-dropdown-item>
              <el-dropdown-item
                v-if="auth.can(ADMIN_PERMISSIONS.modelPublish)"
                command="publish"
                :disabled="!canBatchPublishAllowed || isSaving"
              >
                批量公用
              </el-dropdown-item>
              <el-dropdown-item
                v-if="auth.can(ADMIN_PERMISSIONS.modelUnpublish)"
                command="unpublish"
                :disabled="!canBatchUnpublishAllowed || isSaving"
              >
                批量取消公用
              </el-dropdown-item>
              <el-dropdown-item
                v-if="canRemoveUnavailable"
                command="remove-unavailable"
                :disabled="!hasSelectedModels || isSaving"
              >
                移除不可用
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <section class="admin-model-center__filters" aria-label="模型筛选">
      <el-select v-model="filters.capability" aria-label="类型" @change="loadModels">
        <el-option
          v-for="option in capabilityOptions"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <el-select v-model="filters.publicState" aria-label="公用状态" @change="loadModels">
        <el-option
          v-for="option in publicStateOptions"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <el-input
        v-model="filters.search"
        clearable
        placeholder="搜索名称、厂商或公开名称"
        @keyup.enter="loadModels"
        @clear="loadModels"
      />
      <el-button type="primary" :loading="isLoading" @click="loadModels">搜索</el-button>
    </section>

    <el-alert
      v-if="pageErrorMessage"
      class="admin-model-center__alert"
      :title="pageErrorMessage"
      type="error"
      show-icon
      :closable="false"
    />
    <el-alert
      v-if="pageNoticeMessage"
      class="admin-model-center__alert"
      :title="pageNoticeMessage"
      type="success"
      show-icon
      @close="clearNoticeMessage"
    />

    <section class="admin-model-center__table">
      <el-table
        v-loading="isLoading"
        :data="filteredModels"
        row-key="id"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="44" reserve-selection />
        <el-table-column label="模型" min-width="240">
          <template #default="{ row }">
            <div class="admin-model-center__identity admin-model-center__asset-card">
              <div class="admin-model-center__model-mark">
                {{ capabilityLabel(row.capability).slice(0, 1) }}
              </div>
              <div class="admin-model-center__model-name">
                <strong>{{ row.publicDisplayName || row.name }}</strong>
                <small>{{ row.name }} · {{ row.primaryModelName }}</small>
                <div class="admin-model-center__source-badges">
                  <span>{{ capabilityLabel(row.capability) }}</span>
                  <span>{{ row.adapter }}</span>
                  <span>{{ row.isPublic ? '公用模型' : '私有模型' }}</span>
                </div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="96">
          <template #default="{ row }">{{ capabilityLabel(row.capability) }}</template>
        </el-table-column>
        <el-table-column label="厂商" prop="vendor" min-width="120" />
        <el-table-column label="公用状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.isPublic ? 'success' : 'info'" effect="plain">
              {{ publicStateLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="积分价格" width="120">
          <template #default="{ row }">
            <div class="admin-model-center__price-pill">
              <span>{{ row.creditPrice }}</span>
              <small class="admin-model-center__muted">{{ priceSourceLabel(row.creditPriceSource) }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="172" fixed="right">
          <template #default="{ row }">
            <div class="admin-model-center__row-actions">
              <el-button link type="primary" @click="openDrawer(row)">详情</el-button>
              <el-dropdown
                v-if="hasModelRowActions(row)"
                trigger="click"
                @command="(command: string) => handleRowCommand(command, row)"
              >
                <el-button link type="primary">操作</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item
                      v-if="auth.can(ADMIN_PERMISSIONS.modelPublish)"
                      command="publish"
                      :disabled="!canPublishRow(row)"
                    >
                      公用
                    </el-dropdown-item>
                    <el-dropdown-item
                      v-if="auth.can(ADMIN_PERMISSIONS.modelUnpublish)"
                      command="unpublish"
                      :disabled="!canUnpublishRow(row)"
                    >
                      取消公用
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-drawer v-model="drawerVisible" size="min(520px, 100vw)" :title="drawerTitle" destroy-on-close>
      <div v-if="activeModel && editForm" class="admin-model-center__drawer">
        <section class="admin-model-center__summary">
          <div>
            <span>内部名称</span>
            <strong>{{ activeModel.name }}</strong>
          </div>
          <div>
            <span>接口地址</span>
            <strong>{{ activeModel.baseUrl || '未配置' }}</strong>
          </div>
          <div>
            <span>适配器</span>
            <strong>{{ activeModel.adapter }}</strong>
          </div>
          <div>
            <span>说明</span>
            <strong>{{ displayModelDescription(activeModel) }}</strong>
          </div>
        </section>

        <section class="admin-model-center__health">
          <div>
            <span>健康状态</span>
            <strong>{{ healthStatusLabel }}</strong>
            <small class="admin-model-center__muted">{{ healthMessage }}</small>
          </div>
          <div>
            <span>最近失败率</span>
            <strong>{{ healthFailureRate }}</strong>
          </div>
          <el-button
            :disabled="!canRunActiveHealthCheck || isCheckingHealth"
            :loading="isCheckingHealth"
            @click="runHealthCheck"
          >
            测试连接
          </el-button>
        </section>

        <el-form label-position="top">
          <el-form-item label="公开名称">
            <el-input v-model="editForm.publicDisplayName" :disabled="!canUpdateActiveModel" />
          </el-form-item>
          <el-form-item label="公开描述">
            <el-input
              v-model="editForm.publicDescription"
              type="textarea"
              :rows="3"
              :disabled="!canUpdateActiveModel"
            />
          </el-form-item>
          <el-form-item label="输入提示">
            <el-input
              v-model="editForm.inputHint"
              type="textarea"
              :rows="2"
              :disabled="!canUpdateActiveModel"
            />
          </el-form-item>
          <el-form-item label="图标地址">
            <el-input v-model="editForm.iconUrl" :disabled="!canUpdateActiveModel" />
          </el-form-item>
          <el-form-item label="公开标签">
            <el-input
              v-model="editForm.publicTagsText"
              placeholder="用逗号或换行分隔"
              :disabled="!canUpdateActiveModel"
            />
          </el-form-item>
          <el-form-item label="提示词优化">
            <el-switch
              v-model="editForm.promptOptimizeEnabled"
              active-text="启用"
              inactive-text="停用"
              :disabled="!canUpdateActiveModel"
            />
          </el-form-item>
          <el-form-item label="默认参数">
            <el-input
              v-model="editForm.defaultParametersText"
              type="textarea"
              :rows="6"
              :disabled="!canUpdateActiveModel"
            />
          </el-form-item>
          <el-form-item label="积分价格">
            <div class="admin-model-center__pricing">
              <el-input-number
                v-model="creditPrice"
                :min="0"
                :precision="0"
                :disabled="!canUpdateActivePricing"
              />
              <el-button :disabled="!canUpdateActivePricing || isSaving" @click="saveCreditPrice">
                保存价格
              </el-button>
              <el-button :disabled="!canUpdateActivePricing || isSaving" @click="useDefaultPrice">
                使用默认
              </el-button>
            </div>
          </el-form-item>
        </el-form>

        <div class="admin-model-center__drawer-actions">
          <el-button @click="drawerVisible = false">关闭</el-button>
          <el-button
            type="primary"
            :disabled="!canUpdateActiveModel"
            :loading="isSaving"
            @click="saveModel"
          >
            保存资料
          </el-button>
        </div>
      </div>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { ElMessageBox } from 'element-plus';
import { ArrowDown } from '@element-plus/icons-vue';

import {
  fetchAdminModelHealth,
  publishAdminModel,
  removeUnavailableAdminModels,
  runAdminBatchModelHealthCheck,
  runAdminModelHealthCheck,
  unpublishAdminModel,
  updateAdminModel,
  updateModelCreditPricing,
} from '@/api/admin';
import {
  ADMIN_PERMISSIONS,
  canEditModel,
  canEditModelPricing,
  canPublishModel,
  canRemoveUnavailableModels,
  canTestModel,
  canUnpublishModel,
} from '@/adminPermissions';
import { useAdminAuthStore } from '@/stores/auth';
import type { AdminModel } from '@/types';
import {
  batchHealthSummary,
  buildAdminModelUpdatePayload,
  capabilityLabel,
  capabilityOptions,
  createEditForm,
  createModelHealthState,
  createModelCenterState,
  displayModelDescription,
  MODEL_CENTER_TITLE,
  nextActiveModelAfterRemoval,
  publicStateLabel,
  publicStateOptions,
  selectedIdsAfterRemoval,
  type ModelEditForm,
} from './modelCenterState';

const {
  filters,
  models,
  filteredModels,
  selectedIds,
  selectedModels,
  selectedEditableModels,
  isLoading,
  errorMessage,
  noticeMessage,
  setSelected,
  replaceModel,
  loadModels,
} = createModelCenterState();
const {
  activeHealth,
  isCheckingHealth,
  errorMessage: healthErrorMessage,
  noticeMessage: healthNoticeMessage,
  loadHealth,
  runHealthCheck: runModelHealthCheck,
  resetHealthState,
} = createModelHealthState(fetchAdminModelHealth, runAdminModelHealthCheck);

const auth = useAdminAuthStore();
const drawerVisible = ref(false);
const activeModel = ref<AdminModel | null>(null);
const editForm = ref<ModelEditForm | null>(null);
const creditPrice = ref(0);
const isSaving = ref(false);
const isBatchTesting = ref(false);

const drawerTitle = computed(() => {
  if (!activeModel.value) {
    return '模型详情';
  }
  return activeModel.value.publicDisplayName || activeModel.value.name;
});
const canUpdateActiveModel = computed(() => (
  activeModel.value ? canEditModel(auth.can, activeModel.value.canEdit) : false
));
const canUpdateActivePricing = computed(() => (
  activeModel.value ? canEditModelPricing(auth.can, activeModel.value.canEdit) : false
));
const canRunActiveHealthCheck = computed(() => (
  activeModel.value ? canTestModel(auth.can) : false
));
const hasSelectedModels = computed(() => selectedModels.value.length > 0);
const canRemoveUnavailable = computed(() => canRemoveUnavailableModels(auth.can));
const canBatchPublishAllowed = computed(() => selectedEditableModels.value.some(canPublishRow));
const canBatchUnpublishAllowed = computed(() => selectedEditableModels.value.some(canUnpublishRow));
const healthLatest = computed(() => {
  const latest = activeHealth.value?.latest;
  return latest && typeof latest === 'object' ? latest as Record<string, unknown> : null;
});
const healthStatusLabel = computed(() => {
  const status = String(healthLatest.value?.status || activeHealth.value?.status || '');
  if (status === 'success') return '正常';
  if (status === 'failed' || status === 'error') return '异常';
  return '未检测';
});
const healthMessage = computed(() => String(
  healthLatest.value?.message
    || activeHealth.value?.lastError
    || '点击测试连接后展示最新结果',
));
const healthFailureRate = computed(() => {
  const value = Number(activeHealth.value?.failureRate || 0);
  return `${Math.round(value * 100)}%`;
});
const pageErrorMessage = computed(() => errorMessage.value || healthErrorMessage.value);
const pageNoticeMessage = computed(() => noticeMessage.value || healthNoticeMessage.value);

function clearNoticeMessage() {
  noticeMessage.value = '';
  healthNoticeMessage.value = '';
}

function priceSourceLabel(source: string) {
  if (source === 'custom') {
    return '自定义';
  }
  if (source === 'default') {
    return '默认';
  }
  if (source === 'private_model') {
    return '私有模型';
  }
  if (source === 'capability_default') {
    return '能力默认';
  }
  if (source === 'model_override') {
    return '模型定价';
  }
  return '默认';
}

function openDrawer(model: AdminModel) {
  activeModel.value = model;
  editForm.value = createEditForm(model);
  creditPrice.value = model.creditPrice || 0;
  resetHealthState();
  drawerVisible.value = true;
  void loadHealth(model.id);
}

function handleSelectionChange(rows: AdminModel[]) {
  setSelected(rows.map((row) => row.id));
}

function canPublishRow(model: AdminModel) {
  return canPublishModel(auth.can, model.isPublic, model.canEdit);
}

function canUnpublishRow(model: AdminModel) {
  return canUnpublishModel(auth.can, model.isPublic, model.canEdit);
}

function hasModelRowActions(model: AdminModel) {
  return canPublishRow(model) || canUnpublishRow(model);
}

async function runFriendlyAction(action: () => Promise<void>, successMessage: string, failureMessage: string) {
  isSaving.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    await action();
    noticeMessage.value = successMessage;
  } catch {
    errorMessage.value = failureMessage;
  } finally {
    isSaving.value = false;
  }
}

async function publishModel(model: AdminModel) {
  if (!canPublishRow(model)) {
    errorMessage.value = '当前账号没有公用模型的权限。';
    return;
  }
  await runFriendlyAction(async () => {
    replaceModel(await publishAdminModel(model.id));
  }, '模型已设为公用。', '模型公用失败，请稍后重试。');
}

async function unpublishModel(model: AdminModel) {
  if (!canUnpublishRow(model)) {
    errorMessage.value = '当前账号没有取消公用模型的权限。';
    return;
  }
  await runFriendlyAction(async () => {
    replaceModel(await unpublishAdminModel(model.id));
  }, '模型已取消公用。', '取消公用失败，请稍后重试。');
}

async function handleRowCommand(command: string, model: AdminModel) {
  if (command === 'publish') {
    await publishModel(model);
  }
  if (command === 'unpublish') {
    await unpublishModel(model);
  }
}

async function handleBatchHealthCheck() {
  if (!auth.can(ADMIN_PERMISSIONS.modelTest)) {
    errorMessage.value = '当前账号没有测试模型连接的权限。';
    return;
  }
  const targetIds = selectedModels.value.map((model) => model.id);
  if (!targetIds.length) {
    return;
  }
  isBatchTesting.value = true;
  errorMessage.value = '';
  healthErrorMessage.value = '';
  noticeMessage.value = '';
  healthNoticeMessage.value = '';
  try {
    const result = await runAdminBatchModelHealthCheck(targetIds);
    const summary = batchHealthSummary(result.results, activeModel.value?.id || '');
    const successCount = summary.successCount;
    const failedCount = summary.failedCount;
    if (summary.activeHealth) {
      activeHealth.value = summary.activeHealth;
    }
    noticeMessage.value = `批量测试完成：${successCount} 个正常，${failedCount} 个异常。`;
  } catch {
    errorMessage.value = '批量测试失败，请稍后重试。';
  } finally {
    isBatchTesting.value = false;
  }
}

async function handleBatchPublish() {
  const targets = selectedEditableModels.value.filter(canPublishRow);
  await runFriendlyAction(async () => {
    const updated = await Promise.all(targets.map((model) => publishAdminModel(model.id)));
    updated.forEach(replaceModel);
  }, `已公用 ${targets.length} 个模型。`, '批量公用失败，请稍后重试。');
}

async function handleBatchUnpublish() {
  const targets = selectedEditableModels.value.filter(canUnpublishRow);
  await runFriendlyAction(async () => {
    const updated = await Promise.all(targets.map((model) => unpublishAdminModel(model.id)));
    updated.forEach(replaceModel);
  }, `已取消公用 ${targets.length} 个模型。`, '批量取消公用失败，请稍后重试。');
}

async function handleRemoveUnavailable() {
  if (!canRemoveUnavailable.value) {
    errorMessage.value = '当前账号没有删除模型的权限。';
    return;
  }
  const targetIds = selectedModels.value.map((model) => model.id);
  if (!targetIds.length) {
    return;
  }
  try {
    await ElMessageBox.confirm(
      `确认移除所选 ${targetIds.length} 个模型中最新健康检查异常的模型？没有健康记录或最新正常的模型会被跳过。`,
      '移除不可用模型',
      {
        confirmButtonText: '确认移除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    );
  } catch {
    return;
  }

  isSaving.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    const result = await removeUnavailableAdminModels(targetIds);
    models.value = result.models;
    setSelected(selectedIdsAfterRemoval(selectedIds.value, result.models));
    if (activeModel.value) {
      const refreshedActive = nextActiveModelAfterRemoval(activeModel.value.id, result.models);
      activeModel.value = refreshedActive;
      if (!refreshedActive) {
        drawerVisible.value = false;
        editForm.value = null;
        resetHealthState();
      }
    }
    noticeMessage.value = `已移除 ${result.removedIds.length} 个不可用模型，跳过 ${result.skipped.length} 个。`;
  } catch {
    errorMessage.value = '移除不可用模型失败，请稍后重试。';
  } finally {
    isSaving.value = false;
  }
}

async function handleBatchCommand(command: string) {
  if (command === 'health-check') {
    await handleBatchHealthCheck();
  } else if (command === 'publish') {
    await handleBatchPublish();
  } else if (command === 'unpublish') {
    await handleBatchUnpublish();
  } else if (command === 'remove-unavailable') {
    await handleRemoveUnavailable();
  }
}

async function saveModel() {
  if (!activeModel.value || !editForm.value) {
    return;
  }
  if (!canUpdateActiveModel.value) {
    errorMessage.value = '当前账号没有保存模型资料的权限。';
    return;
  }
  let payload;
  try {
    payload = buildAdminModelUpdatePayload(editForm.value);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '模型资料填写有误，请检查后重试。';
    return;
  }
  await runFriendlyAction(async () => {
    const updated = await updateAdminModel(activeModel.value!.id, payload);
    replaceModel(updated);
    activeModel.value = updated;
    editForm.value = createEditForm(updated);
  }, '模型资料已保存。', '模型资料保存失败，请稍后重试。');
}

async function saveCreditPrice() {
  if (!activeModel.value) {
    return;
  }
  if (!canUpdateActivePricing.value) {
    errorMessage.value = '当前账号没有修改积分价格的权限。';
    return;
  }
  await runFriendlyAction(async () => {
    const updated = await updateModelCreditPricing(activeModel.value!.id, { price: creditPrice.value });
    replaceModel(updated);
    activeModel.value = updated;
    creditPrice.value = updated.creditPrice || 0;
  }, '积分价格已保存。', '积分价格保存失败，请稍后重试。');
}

async function useDefaultPrice() {
  if (!activeModel.value) {
    return;
  }
  if (!canUpdateActivePricing.value) {
    errorMessage.value = '当前账号没有修改积分价格的权限。';
    return;
  }
  await runFriendlyAction(async () => {
    const updated = await updateModelCreditPricing(activeModel.value!.id, { useDefault: true });
    replaceModel(updated);
    activeModel.value = updated;
    creditPrice.value = updated.creditPrice || 0;
  }, '已恢复默认积分价格。', '恢复默认价格失败，请稍后重试。');
}

async function runHealthCheck() {
  if (!activeModel.value) {
    return;
  }
  if (!canRunActiveHealthCheck.value) {
    healthErrorMessage.value = '当前账号没有测试模型连接的权限。';
    return;
  }
  await runModelHealthCheck(activeModel.value.id);
}

onMounted(() => {
  void loadModels();
});
</script>
