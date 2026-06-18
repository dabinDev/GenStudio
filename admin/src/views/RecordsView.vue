<template>
  <section class="admin-content-page">
    <header class="admin-content-page__header">
      <div>
        <h2>创作记录</h2>
        <p>按用户、模型、时间和类型查看文案、图片、视频调用的提示词、响应结果和任务状态。</p>
      </div>
      <div class="admin-content-page__actions">
        <el-button :loading="isLoading" @click="loadRecords">刷新</el-button>
        <el-button
          v-if="canExportRecords"
          :disabled="!canExportCurrentRecords"
          :loading="isExporting"
          @click="exportCurrentRecords"
        >
          导出当前列表
        </el-button>
      </div>
    </header>

    <el-tabs v-model="capability" class="admin-content-page__tabs">
      <el-tab-pane label="文案记录" name="text" />
      <el-tab-pane label="生图记录" name="image" />
      <el-tab-pane label="视频记录" name="video" />
    </el-tabs>

    <section class="admin-content-page__toolbar">
      <div v-if="hasRouteFilters" class="admin-content-page__toolbar-group">
        <span>当前来自仪表盘/链接的筛选</span>
        <el-tag
          v-for="chip in routeFilterChips"
          :key="chip.key"
          effect="plain"
        >
          {{ chip.label }}: {{ chip.value }}
        </el-tag>
        <el-button link type="primary" @click="clearLinkedFilters">清空链接筛选</el-button>
      </div>
      <div class="admin-content-page__toolbar-group">
        <el-select
          v-model="activePresetId"
          clearable
          filterable
          placeholder="常用筛选"
          @change="handlePresetChange"
        >
          <el-option
            v-for="preset in visibleFilterPresets()"
            :key="preset.id"
            :label="preset.name"
            :value="preset.id"
          />
        </el-select>
        <el-button @click="saveFilterPreset">保存筛选</el-button>
        <el-button :disabled="!activePresetId" @click="deleteFilterPreset">移除筛选</el-button>
      </div>
      <div class="admin-content-page__toolbar-group">
        <el-switch
          v-model="markdownEnabled"
          active-text="Markdown"
          inactive-text="纯文本"
          inline-prompt
        />
        <el-switch
          v-if="capability === 'image'"
          v-model="waterfallMode"
          active-text="瀑布流"
          inactive-text="表格"
          inline-prompt
        />
      </div>
    </section>

    <section class="admin-content-page__filters admin-content-page__filters--records">
      <el-input v-model="filters.userId" clearable placeholder="用户 ID" @keyup.enter="loadRecords" />
      <el-input v-model="filters.userSearch" clearable placeholder="用户邮箱或昵称" @keyup.enter="loadRecords" />
      <el-input v-model="filters.modelGroupId" clearable placeholder="模型 ID" @keyup.enter="loadRecords" />
      <el-input v-model="filters.keyword" clearable placeholder="提示词 / 响应关键词" @keyup.enter="loadRecords" />
      <el-select v-model="filters.status" aria-label="状态筛选">
        <el-option label="全部状态" value="" />
        <el-option label="未成功" value="non_success" />
        <el-option label="成功" value="success" />
        <el-option label="失败" value="error" />
        <el-option label="处理中" value="processing" />
      </el-select>
      <el-input v-if="capability === 'image'" v-model="filters.size" clearable placeholder="尺寸，如 1024x1024" />
      <el-input v-if="capability === 'image'" v-model="filters.ratio" clearable placeholder="比例，如 16:9" />
      <el-input v-if="capability === 'image'" v-model="filters.refCount" clearable placeholder="参考图数量" />
      <el-input v-if="capability === 'video'" v-model="filters.duration" clearable placeholder="时长，如 8" />
      <el-input v-if="capability === 'video'" v-model="filters.resolution" clearable placeholder="分辨率，如 720p" />
      <el-input v-if="capability === 'video'" v-model="filters.mode" clearable placeholder="模式，如 reference" />
      <el-button type="primary" :loading="isLoading" @click="loadRecords">查询</el-button>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />

    <section v-if="capability === 'image' && waterfallMode" class="admin-content-page__waterfall">
      <article v-for="record in records" :key="record.id" class="admin-content-page__image-card">
        <button class="admin-content-page__image-preview" type="button" @click="openDrawer(record)">
          <span v-if="!imageAssets(record).length">暂无图片</span>
          <span v-else-if="imageAssets(record).length === 1" class="admin-content-page__image-single">
            <img :src="imageAssets(record)[0].thumbnailUrl || imageAssets(record)[0].url" alt="创作图片" />
          </span>
          <span v-else class="admin-content-page__image-strip" aria-label="多张创作图片">
            <span
              v-for="(asset, index) in imageAssets(record)"
              :key="asset.url"
              class="admin-content-page__image-strip-item"
            >
              <img :src="asset.thumbnailUrl || asset.url" alt="创作图片" />
              <small class="admin-content-page__image-count">{{ index + 1 }}/{{ imageAssets(record).length }}</small>
            </span>
          </span>
        </button>
        <div class="admin-content-page__image-card-body">
          <strong>{{ record.prompt || '无提示词' }}</strong>
          <small>{{ record.user?.email || record.user?.nickname || '未知用户' }}</small>
          <div>
            <el-tag :type="statusTagType(record.status)" effect="plain">{{ statusLabel(record.status) }}</el-tag>
            <span>{{ record.modelName || '未知模型' }}</span>
          </div>
        </div>
      </article>
      <el-empty v-if="!isLoading && !records.length" description="暂无生图记录" />
    </section>

    <section v-else class="admin-content-page__table">
      <el-table v-loading="isLoading" :data="records" row-key="id">
        <el-table-column label="请求" min-width="320">
          <template #default="{ row }">
            <div class="admin-content-page__record-cell">
              <span class="admin-content-page__record-kicker">提问</span>
              <strong>{{ row.prompt || '无提示词' }}</strong>
              <small>{{ row.user?.email || row.user?.nickname || '未知用户' }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="响应结果" min-width="360">
          <template #default="{ row }">
            <div class="admin-content-page__record-cell admin-content-page__record-result">
              <template v-if="capability === 'image' && imageAssets(row).length">
                <div class="admin-content-page__record-media-strip">
                  <button
                    v-for="(asset, index) in imageAssets(row).slice(0, 4)"
                    :key="asset.url"
                    type="button"
                    @click="openImageViewer(imageAssets(row), index, row.modelName || '创作图片')"
                  >
                    <img :src="asset.thumbnailUrl || asset.url" alt="创作图片" />
                  </button>
                  <span v-if="imageAssets(row).length > 4">+{{ imageAssets(row).length - 4 }}</span>
                </div>
              </template>
              <template v-else-if="capability === 'video' && videoAssets(row).length">
                <div class="admin-content-page__record-media-strip admin-content-page__record-media-strip--video">
                  <video
                    v-for="asset in videoAssets(row).slice(0, 1)"
                    :key="asset.url"
                    :src="asset.url"
                    :poster="asset.thumbnailUrl || undefined"
                    controls
                    playsinline
                  />
                </div>
                <span v-if="row.taskId" class="admin-content-page__record-task">{{ row.taskId }}</span>
              </template>
              <template v-else>
                <span class="admin-content-page__record-kicker">回答</span>
                <p>{{ recordPreviewResponse(row) }}</p>
              </template>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="模型" width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.modelName || '未知模型' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" effect="plain">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="资源" width="90" align="right">
          <template #default="{ row }">{{ row.assets?.length || 0 }}</template>
        </el-table-column>
        <el-table-column v-if="capability === 'video'" label="任务 ID" width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.taskId || '无' }}</template>
        </el-table-column>
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ formatDate(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDrawer(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-drawer v-model="drawerVisible" size="min(720px, 100vw)" title="记录详情" destroy-on-close>
      <div v-if="activeRecord" class="admin-content-page__drawer">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="用户">{{ activeRecord.user?.email || activeRecord.user?.nickname || '未知用户' }}</el-descriptions-item>
          <el-descriptions-item label="模型">{{ activeRecord.modelName || '未知模型' }}</el-descriptions-item>
          <el-descriptions-item label="任务 ID">
            <span>{{ activeRecord.taskId || '无' }}</span>
            <el-button v-if="activeRecord.taskId" link type="primary" @click="copyTaskId(activeRecord.taskId)">复制</el-button>
          </el-descriptions-item>
          <el-descriptions-item label="耗时">{{ activeRecord.durationMs || 0 }} ms</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusLabel(activeRecord.status) }}</el-descriptions-item>
        </el-descriptions>
        <el-alert v-if="detailErrorMessage" :title="detailErrorMessage" type="warning" show-icon :closable="false" />

        <section class="admin-content-page__detail-block">
          <strong>提示词</strong>
          <div
            v-if="markdownEnabled"
            class="admin-content-page__markdown"
            v-html="renderSafeMarkdown(activeRecord.prompt || '无提示词')"
          />
          <p v-else>{{ activeRecord.prompt || '无提示词' }}</p>
        </section>
        <section class="admin-content-page__detail-block">
          <strong>响应</strong>
          <div
            v-if="markdownEnabled"
            class="admin-content-page__markdown"
            v-html="renderSafeMarkdown(activeRecord.response || activeRecord.errorMessage || '暂无响应')"
          />
          <p v-else>{{ activeRecord.response || activeRecord.errorMessage || '暂无响应' }}</p>
        </section>
        <section v-if="activeRecord.assets?.length" class="admin-content-page__asset-grid admin-content-page__asset-strip">
          <template v-for="asset in activeRecord.assets" :key="asset.url">
            <button
              v-if="asset.type === 'image'"
              class="admin-content-page__asset-preview-button"
              type="button"
              @click="openImageViewer(recordImageAssets(activeRecord), imageAssetIndex(activeRecord, asset), activeRecord.modelName || '创作图片')"
            >
              <img :src="asset.thumbnailUrl || asset.url" alt="创作图片" />
            </button>
            <a v-else :href="asset.url" target="_blank" rel="noreferrer">
              <video v-if="asset.type === 'video'" :src="asset.url" controls playsinline />
              <span v-else>{{ asset.type }} 资源</span>
            </a>
          </template>
        </section>
        <el-collapse>
          <el-collapse-item v-if="activeRecord.taskId || taskTimeline.length" title="任务状态时间线" name="timeline">
            <el-timeline v-loading="timelineLoading">
              <el-timeline-item
                v-for="event in taskTimeline"
                :key="event.id"
                :timestamp="formatDate(event.createdAt)"
                :type="statusTagType(event.status)"
              >
                <strong>{{ event.eventType || event.source }}</strong>
                <span>{{ event.status || '未知' }} · {{ event.endpoint || '本地事件' }}</span>
                <small v-if="event.durationMs">{{ event.durationMs }} ms</small>
                <p v-if="event.message || event.errorMessage">{{ event.message || event.errorMessage }}</p>
              </el-timeline-item>
              <el-empty v-if="!timelineLoading && !taskTimeline.length" description="暂无任务事件" />
            </el-timeline>
          </el-collapse-item>
          <el-collapse-item title="请求参数 JSON" name="request">
            <pre>{{ stringify(activeRecord.requestParams) }}</pre>
          </el-collapse-item>
          <el-collapse-item title="响应摘要 JSON" name="response">
            <pre>{{ stringify(activeRecord.responseSummary) }}</pre>
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-drawer>

    <AdminImageViewer
      v-model:visible="imageViewerState.visible"
      :images="imageViewerState.images"
      :initial-index="imageViewerState.initialIndex"
      :title="imageViewerState.title"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { useRoute, useRouter } from 'vue-router';

import { ADMIN_PERMISSIONS } from '@/adminPermissions';
import { fetchAdminRecordDetail, fetchTaskTimeline } from '@/api/admin';
import AdminImageViewer from '@/components/AdminImageViewer.vue';
import { useAdminAuthStore } from '@/stores/auth';
import type {
  AdminCreationAsset,
  AdminCreationRecord,
  AdminCreationRecordDetail,
  AdminTaskTimelineEvent,
} from '@/types';
import { recordFromDetail } from './recordDetailState';
import {
  canExportVisibleRecords,
  createRecordsExportState,
  createRecordsState,
  recordStatusLabel,
  renderSafeMarkdown,
  visibleRecordExportQuery,
} from './recordsState';

const {
  capability,
  records,
  isLoading,
  errorMessage,
  filters,
  lastLoadedCapability,
  lastLoadedQuery,
  activePresetId,
  routeFilterChips,
  hasRouteFilters,
  visibleFilterPresets,
  saveCurrentFilterPreset,
  applyFilterPreset,
  removeFilterPreset,
  applyRouteQueryFilters,
  clearRouteFilters,
  loadRecords,
} = createRecordsState();
const auth = useAdminAuthStore();
const route = useRoute();
const router = useRouter();
const drawerVisible = ref(false);
const activeRecord = ref<AdminCreationRecord | null>(null);
const taskTimeline = ref<AdminTaskTimelineEvent[]>([]);
const timelineLoading = ref(false);
const detailErrorMessage = ref('');
const markdownEnabled = ref(true);
const waterfallMode = ref(true);
const imageViewerState = reactive({
  visible: false,
  images: [] as AdminCreationAsset[],
  initialIndex: 0,
  title: '',
});
const canExportRecords = computed(() => auth.can(ADMIN_PERMISSIONS.recordExport));
const { isExporting, exportRecords: exportRecordsFromServer } = createRecordsExportState();
const canExportCurrentRecords = computed(() => canExportVisibleRecords({
  canExportRecords: canExportRecords.value,
  recordCount: records.value.length,
  isExporting: isExporting.value,
  isLoading: isLoading.value,
}));

function formatDate(value?: string) {
  if (!value) return '暂无记录';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '暂无记录' : date.toLocaleString('zh-CN');
}

function statusLabel(status: string) {
  return recordStatusLabel(status);
}

function statusTagType(status: string) {
  if (status === 'success') return 'success';
  if (status === 'error') return 'danger';
  if (status === 'running' || status === 'processing') return 'warning';
  return 'info';
}

function stringify(value: unknown) {
  return JSON.stringify(value || {}, null, 2);
}

function imageAssets(record: AdminCreationRecord) {
  return record.assets?.filter((asset) => asset.type === 'image') || [];
}

function videoAssets(record: AdminCreationRecord) {
  return record.assets?.filter((asset) => asset.type === 'video') || [];
}

function recordPreviewResponse(record: AdminCreationRecord) {
  const value = record.response || record.errorMessage || '暂无响应';
  return value.length > 180 ? `${value.slice(0, 180)}...` : value;
}

function recordImageAssets(record: AdminCreationRecord | null) {
  return record?.assets?.filter((asset) => asset.type === 'image') || [];
}

function imageAssetIndex(record: AdminCreationRecord | null, asset: AdminCreationAsset) {
  const images = recordImageAssets(record);
  const index = images.findIndex((item) => item.url === asset.url);
  return index >= 0 ? index : 0;
}

function openImageViewer(images: AdminCreationAsset[], initialIndex = 0, title = '创作图片') {
  if (!images.length) return;
  imageViewerState.images = images;
  imageViewerState.initialIndex = initialIndex;
  imageViewerState.title = title;
  imageViewerState.visible = true;
}

async function exportCurrentRecords() {
  if (!canExportCurrentRecords.value) return;
  try {
    const exportTarget = visibleRecordExportQuery(lastLoadedCapability.value, lastLoadedQuery.value);
    const exported = await exportRecordsFromServer(exportTarget.capability, exportTarget.query);
    if (exported) {
      ElMessage.success('导出任务已开始。');
    }
  } catch (error) {
    ElMessage.error(error instanceof Error && error.message ? error.message : '创作记录导出失败，请稍后重试。');
  }
}

function handlePresetChange(value: string) {
  if (!value) return;
  if (applyFilterPreset(value)) {
    void loadRecords();
  }
}

async function saveFilterPreset() {
  try {
    const { value } = await ElMessageBox.prompt('输入筛选名称，方便之后快速复用。', '保存常用筛选', {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputValue: `${capability.value} 筛选`,
      inputPattern: /\S+/,
      inputErrorMessage: '筛选名称不能为空',
    });
    saveCurrentFilterPreset(value);
    ElMessage.success('已保存常用筛选');
  } catch {
    // User cancelled.
  }
}

async function deleteFilterPreset() {
  if (!activePresetId.value) return;
  try {
    await ElMessageBox.confirm('确认移除当前常用筛选？', '移除筛选', {
      confirmButtonText: '移除',
      cancelButtonText: '取消',
      type: 'warning',
    });
    removeFilterPreset(activePresetId.value);
    ElMessage.success('已移除常用筛选');
  } catch {
    // User cancelled.
  }
}

async function clearLinkedFilters() {
  clearRouteFilters();
  await router.replace({ path: route.path, query: {} }).catch(() => undefined);
  await loadRecords();
}

async function copyTaskId(taskId: string) {
  try {
    await navigator.clipboard?.writeText(taskId);
    ElMessage.success('任务 ID 已复制');
  } catch {
    ElMessage.warning('复制失败，请手动复制任务 ID');
  }
}

async function openDrawer(record: AdminCreationRecord) {
  activeRecord.value = record;
  taskTimeline.value = [];
  detailErrorMessage.value = '';
  drawerVisible.value = true;

  let detail: AdminCreationRecordDetail | null = null;
  try {
    detail = await fetchAdminRecordDetail(record.id);
    activeRecord.value = recordFromDetail(record, detail);
    taskTimeline.value = detail.timeline || [];
  } catch {
    detailErrorMessage.value = '记录详情暂时无法加载，已保留列表信息。';
  }

  const timelineTaskId = activeRecord.value?.taskId || record.taskId;
  if (!timelineTaskId) return;
  timelineLoading.value = true;
  try {
    const timeline = await fetchTaskTimeline(timelineTaskId);
    if (timeline.events?.length) {
      taskTimeline.value = timeline.events;
    } else if (!taskTimeline.value.length && detail?.timeline?.length) {
      taskTimeline.value = detail.timeline;
    }
  } catch {
    if (!taskTimeline.value.length) {
      taskTimeline.value = [];
    }
  } finally {
    timelineLoading.value = false;
  }
}

defineExpose({
  openDrawer,
  activeRecord,
  taskTimeline,
  detailErrorMessage,
  imageViewerState,
  openImageViewer,
});

watch(capability, () => {
  void loadRecords();
});

onMounted(() => {
  applyRouteQueryFilters(route.query);
  void loadRecords();
});
</script>
