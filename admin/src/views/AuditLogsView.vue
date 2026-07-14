<template>
  <section class="admin-content-page">
    <header class="admin-content-page__header">
      <div>
        <h2>审计日志</h2>
        <p>追踪后台模型、公用配置、用户状态和积分调整等操作，重点标记高风险行为。</p>
      </div>
      <div class="admin-content-page__actions">
        <el-button :loading="isLoading" @click="loadLogs">刷新</el-button>
        <el-button v-if="canExportAudit" :loading="isExporting" :disabled="!logs.length" @click="exportLogs">
          导出审计日志
        </el-button>
      </div>
    </header>

    <section class="admin-content-page__filters admin-content-page__filters--audit">
      <el-input v-model="filters.action" clearable placeholder="操作名称" @keyup.enter="loadLogs" />
      <el-input v-model="filters.adminUserId" clearable placeholder="管理员 ID" @keyup.enter="loadLogs" />
      <el-select v-model="filters.targetType" aria-label="目标对象" placeholder="选择对象类型">
        <el-option
          v-for="option in targetTypeOptions"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <el-input v-model="filters.targetId" clearable placeholder="目标 ID" @keyup.enter="loadLogs" />
      <el-select v-model="filters.status" aria-label="执行状态" placeholder="选择执行状态">
        <el-option label="全部状态" value="" />
        <el-option label="成功" value="success" />
        <el-option label="失败" value="error" />
      </el-select>
      <el-select v-model="filters.risk" aria-label="风险等级" placeholder="选择风险等级">
        <el-option label="全部风险" value="" />
        <el-option label="高风险" value="high" />
        <el-option label="中风险" value="medium" />
        <el-option label="普通" value="normal" />
      </el-select>
      <el-date-picker
        v-model="filters.dateRange"
        class="admin-content-page__audit-date-range"
        type="datetimerange"
        range-separator="至"
        start-placeholder="开始时间"
        end-placeholder="结束时间"
        value-format="YYYY-MM-DDTHH:mm:ss"
        :shortcuts="dateShortcuts"
      />
      <el-button @click="resetFilters">重置</el-button>
      <el-button class="admin-content-page__audit-submit" type="primary" :loading="isLoading" @click="applyFilters">查询</el-button>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />

    <section class="audit-summary-grid">
      <article>
        <span>日志总数</span>
        <strong>{{ totalLogs }}</strong>
      </article>
      <article class="audit-summary-grid__danger">
        <span>高风险<small>（本页）</small></span>
        <strong>{{ auditSummary.highRisk }}</strong>
      </article>
      <article>
        <span>中风险<small>（本页）</small></span>
        <strong>{{ auditSummary.mediumRisk }}</strong>
      </article>
      <article>
        <span>失败操作<small>（本页）</small></span>
        <strong>{{ auditSummary.errors }}</strong>
      </article>
      <article>
        <span>对象类型</span>
        <strong>{{ auditSummary.targetTypes }}</strong>
      </article>
    </section>

    <section class="admin-content-page__table">
      <el-table v-loading="isLoading" :data="logs" row-key="id" :row-class-name="rowClassName">
        <el-table-column label="操作" min-width="180">
          <template #default="{ row }">
            <div class="admin-content-page__title-cell">
              <strong>{{ row.action }}</strong>
              <small>{{ row.adminUserId || '系统' }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="目标" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.targetType || 'unknown' }} / {{ row.targetId || '无' }}</template>
        </el-table-column>
        <el-table-column label="风险" width="100" prop="riskLevel" sortable>
          <template #default="{ row }">
            <el-tag :type="riskTagType(row.riskLevel)" effect="plain">{{ riskLabel(row.riskLevel) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'error' ? 'danger' : 'success'" effect="plain">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170" prop="createdAt" sortable>
          <template #default="{ row }">{{ formatDate(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDrawer(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="admin-content-page__pagination">
        <el-pagination
          layout="total, sizes, prev, pager, next"
          :total="totalLogs"
          :current-page="filters.page"
          :page-size="filters.pageSize"
          :page-sizes="[20, 50, 100, 300]"
          :disabled="isLoading"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </section>

    <el-drawer v-model="drawerVisible" size="min(620px, 100vw)" title="审计详情" destroy-on-close>
      <div v-if="activeLog" class="admin-content-page__drawer">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="操作">{{ activeLog.action }}</el-descriptions-item>
          <el-descriptions-item label="管理员">{{ activeLog.adminUserId || '系统' }}</el-descriptions-item>
          <el-descriptions-item label="目标">
            <span>{{ activeLog.targetType || 'unknown' }} / {{ activeLog.targetId || '无' }}</span>
            <el-button v-if="targetLink(activeLog)" link type="primary" @click="goToTarget(activeLog)">查看对象</el-button>
          </el-descriptions-item>
          <el-descriptions-item label="风险">{{ riskLabel(activeLog.riskLevel) }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusLabel(activeLog.status) }}</el-descriptions-item>
        </el-descriptions>
        <section class="admin-content-page__detail-block">
          <strong>摘要 JSON</strong>
          <pre>{{ stringify(activeLog.summary) }}</pre>
        </section>
      </div>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { ADMIN_PERMISSIONS } from '@/adminPermissions';
import { buildExportFilename } from '@/adminExport';
import { exportAuditLogs, fetchAuditLogs } from '@/api/admin';
import { AdminApiError } from '@/api/http';
import { useAdminAuthStore } from '@/stores/auth';
import type { AdminAuditLog } from '@/types';
import {
  auditRowClassName,
  buildAuditLogQuery,
  buildAuditLogSummary,
  buildAuditTargetScope,
  createAuditLogFilters,
  TARGET_TYPE_OPTIONS,
} from './auditLogsState';

const auth = useAdminAuthStore();
const router = useRouter();
const logs = ref<AdminAuditLog[]>([]);
const totalLogs = ref(0);
const isLoading = ref(false);
const isExporting = ref(false);
const errorMessage = ref('');
const drawerVisible = ref(false);
const activeLog = ref<AdminAuditLog | null>(null);
const filters = reactive(createAuditLogFilters());
const canExportAudit = computed(() => auth.can(ADMIN_PERMISSIONS.auditExport));
const auditSummary = computed(() => buildAuditLogSummary(logs.value));
const targetTypeOptions = TARGET_TYPE_OPTIONS;

function friendlyError(error: unknown, fallback: string) {
  return error instanceof AdminApiError && error.message.trim() ? error.message.trim() : fallback;
}

function formatDate(value?: string) {
  if (!value) return '暂无记录';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '暂无记录' : date.toLocaleString('zh-CN');
}

function riskLabel(risk?: string) {
  if (risk === 'high') return '高风险';
  if (risk === 'medium') return '中风险';
  return '普通';
}

function riskTagType(risk?: string) {
  if (risk === 'high') return 'danger';
  if (risk === 'medium') return 'warning';
  return 'info';
}

function statusLabel(status?: string) {
  if (status === 'success') return '成功';
  if (status === 'error') return '失败';
  return status || '未知';
}

function stringify(value: unknown) {
  return JSON.stringify(value || {}, null, 2);
}

function openDrawer(log: AdminAuditLog) {
  activeLog.value = log;
  drawerVisible.value = true;
}

async function exportLogs() {
  if (!canExportAudit.value || !logs.value.length) return;
  isExporting.value = true;
  errorMessage.value = '';
  try {
    const blob = await exportAuditLogs(buildAuditLogQuery(filters));
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = buildExportFilename('audit', buildAuditTargetScope(filters));
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  } catch (error) {
    errorMessage.value = friendlyError(error, '审计日志导出失败，请稍后重试。');
  } finally {
    isExporting.value = false;
  }
}

function rowClassName({ row }: { row: AdminAuditLog }) {
  return auditRowClassName(row);
}

async function loadLogs() {
  isLoading.value = true;
  errorMessage.value = '';
  try {
    logs.value = await fetchAuditLogs(buildAuditLogQuery(filters), (meta) => {
      if (typeof meta.total === 'number') totalLogs.value = meta.total;
    });
  } catch (error) {
    errorMessage.value = friendlyError(error, '审计日志加载失败，请稍后重试。');
  } finally {
    isLoading.value = false;
  }
}

function applyFilters() {
  filters.page = 1;
  void loadLogs();
}

function handlePageChange(nextPage: number) {
  filters.page = nextPage;
  void loadLogs();
}

function handleSizeChange(size: number) {
  filters.pageSize = size;
  filters.page = 1;
  void loadLogs();
}

function resetFilters() {
  Object.assign(filters, createAuditLogFilters());
  void loadLogs();
}

const dateShortcuts = [
  {
    text: '今天',
    value: () => {
      const start = new Date();
      start.setHours(0, 0, 0, 0);
      return [start, new Date()];
    },
  },
  {
    text: '近 7 天',
    value: () => {
      const start = new Date();
      start.setDate(start.getDate() - 7);
      return [start, new Date()];
    },
  },
  {
    text: '近 30 天',
    value: () => {
      const start = new Date();
      start.setDate(start.getDate() - 30);
      return [start, new Date()];
    },
  },
];

function targetLink(log: AdminAuditLog): boolean {
  return Boolean(log.targetId) && ['user', 'model', 'prompt_template', 'record'].includes(log.targetType || '');
}

function goToTarget(log: AdminAuditLog) {
  if (!targetLink(log)) return;
  if (log.targetType === 'user') {
    void router.push({ path: '/users', query: { search: log.targetId } });
  } else if (log.targetType === 'model') {
    void router.push({ path: '/models', query: { search: log.targetId } });
  } else if (log.targetType === 'prompt_template') {
    void router.push({ path: '/prompts' });
  } else if (log.targetType === 'record') {
    void router.push({ path: '/records' });
  }
}

onMounted(() => {
  void loadLogs();
});
</script>

<style scoped>
.audit-summary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.audit-summary-grid article {
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 14px;
  background: var(--el-bg-color-overlay);
}

.audit-summary-grid span {
  display: block;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.audit-summary-grid strong {
  display: block;
  margin-top: 6px;
  color: var(--el-text-color-primary);
  font-size: 22px;
}

.audit-summary-grid__danger {
  border-color: var(--el-color-danger-light-5);
  background: var(--el-color-danger-light-9);
}

:deep(.audit-row--high-risk) {
  --el-table-tr-bg-color: var(--el-color-danger-light-9);
}

:deep(.audit-row--error) {
  --el-table-tr-bg-color: var(--el-color-warning-light-9);
}

@media (max-width: 960px) {
  .audit-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
