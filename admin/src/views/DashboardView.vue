<template>
  <section class="admin-dashboard">
    <header class="admin-dashboard__header">
      <div>
        <h2>{{ DASHBOARD_TITLE }}</h2>
        <p>查看调用质量、积分消耗、重点模型健康状态和用户活跃情况。</p>
        <small v-if="lastUpdatedLabel" class="admin-dashboard__updated">最后更新 {{ lastUpdatedLabel }}</small>
      </div>
      <div class="admin-dashboard__ranges" aria-label="时间范围">
        <button
          v-for="option in rangeOptions"
          :key="option.value"
          type="button"
          :class="{ 'is-active': selectedRange === option.value }"
          @click="handleRangeChange(option.value)"
        >
          {{ option.label }}
        </button>
      </div>
    </header>

    <div v-if="errorMessage" class="admin-dashboard__error" role="alert">
      {{ errorMessage }}
      <button type="button" @click="loadDashboard()">重试</button>
    </div>

    <div v-loading="isLoading && !metrics" class="admin-dashboard__metrics" :aria-busy="isLoading">
      <AdminMetricCard
        v-for="card in metricCards"
        :key="card.label"
        :label="card.label"
        :value="card.value"
        :hint="card.hint"
        :tone="card.tone"
      />
    </div>

    <div class="admin-dashboard__grid">
      <section class="admin-dashboard__panel admin-dashboard__panel--wide">
        <div class="admin-dashboard__panel-head">
          <h3>调用趋势</h3>
          <div class="admin-dashboard__panel-actions">
            <span>{{ rangeLabel }}</span>
            <div class="admin-dashboard__segmented" aria-label="趋势粒度">
              <button
                v-for="option in trendGranularityOptions"
                :key="option.value"
                type="button"
                :class="{ 'is-active': trendGranularity === option.value }"
                @click="handleTrendGranularityChange(option.value)"
              >
                {{ option.label }}
              </button>
            </div>
          </div>
        </div>
        <div ref="trendChartRef" class="admin-dashboard__chart" aria-label="调用趋势图"></div>
      </section>

      <section class="admin-dashboard__panel">
        <div class="admin-dashboard__panel-head">
          <h3>{{ CREDIT_SUMMARY_TITLE }}</h3>
        </div>
        <dl class="admin-dashboard__credits">
          <div v-for="item in creditItems" :key="item.label">
            <dt>{{ item.label }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>
      </section>
    </div>

    <div class="admin-dashboard__tables">
      <section class="admin-dashboard__panel">
        <div class="admin-dashboard__panel-head">
          <h3>失败模型 <small class="admin-dashboard__panel-hint">前 10</small></h3>
        </div>
        <table>
          <thead>
            <tr>
              <th>模型</th>
              <th>失败</th>
              <th>失败率</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="model in failedModels" :key="model.modelGroupId">
              <td>
                <router-link class="admin-dashboard__table-link admin-dashboard__action-card" :to="failedModelRecordLink(model)">
                  <span>
                    <strong>{{ model.modelName }}</strong>
                    <small>{{ friendlyModelError(model.lastError, model.capability) }}</small>
                  </span>
                  <em class="admin-dashboard__action-pill">查看失败记录</em>
                </router-link>
              </td>
              <td>{{ formatNumber(model.failedCalls || 0) }}</td>
              <td>{{ formatPercent(model.failureRate || 0) }}</td>
            </tr>
            <tr v-if="!failedModels.length">
              <td colspan="3">暂无失败模型</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="admin-dashboard__panel">
        <div class="admin-dashboard__panel-head">
          <h3>慢模型 <small class="admin-dashboard__panel-hint">前 10</small></h3>
        </div>
        <table>
          <thead>
            <tr>
              <th>模型</th>
              <th>调用</th>
              <th>平均耗时</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="model in slowModels" :key="model.modelGroupId">
              <td>
                <router-link class="admin-dashboard__table-link admin-dashboard__action-card" :to="modelRecordLink(model)">
                  <span>
                    <strong>{{ model.modelName }}</strong>
                    <small>{{ model.capability }}</small>
                  </span>
                  <em class="admin-dashboard__action-pill">查看慢调用</em>
                </router-link>
              </td>
              <td>{{ formatNumber(model.totalCalls) }}</td>
              <td>{{ formatDuration(model.averageDurationMs || 0) }}</td>
            </tr>
            <tr v-if="!slowModels.length">
              <td colspan="3">暂无慢模型</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="admin-dashboard__panel">
        <div class="admin-dashboard__panel-head">
          <h3>活跃用户 <small class="admin-dashboard__panel-hint">前 10</small></h3>
        </div>
        <table>
          <thead>
            <tr>
              <th>用户</th>
              <th>调用</th>
              <th>公有/私有</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in activeUsers" :key="user.userId">
              <td>
                <router-link class="admin-dashboard__table-link" :to="activeUserRecordLink(user)">
                  <strong>{{ user.label }}</strong>
                </router-link>
              </td>
              <td>{{ formatNumber(user.totalCalls) }}</td>
              <td>{{ formatNumber(user.publicModelCalls) }} / {{ formatNumber(user.privateModelCalls) }}</td>
            </tr>
            <tr v-if="!activeUsers.length">
              <td colspan="3">暂无活跃用户</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

import AdminMetricCard from '@/components/AdminMetricCard.vue';
import { useAdminThemeStore } from '@/stores/theme';
import type { AdminDashboardMetrics } from '@/types';
import {
  createDashboardState,
  CREDIT_SUMMARY_TITLE,
  DASHBOARD_TITLE,
  formatDuration,
  formatNumber,
  formatPercent,
  friendlyModelError,
  rangeOptions,
} from './dashboardState';

const trendChartRef = ref<HTMLElement | null>(null);
const themeStore = useAdminThemeStore();
const lastUpdatedLabel = ref('');
type TrendChart = { setOption: (option: unknown) => void; dispose: () => void; resize?: () => void };
type EChartsCore = { init: (element: HTMLElement) => TrendChart };

let trendChart: TrendChart | null = null;
let echartsCorePromise: Promise<EChartsCore> | null = null;

const {
  selectedRange,
  metrics,
  isLoading,
  errorMessage,
  rangeLabel,
  metricCards,
  creditItems,
  failedModels,
  slowModels,
  activeUsers,
  trendGranularity,
  trendGranularityOptions,
  currentTrendBuckets,
  handleTrendGranularityChange,
  failedModelRecordLink,
  modelRecordLink,
  activeUserRecordLink,
  loadDashboard,
  handleRangeChange,
} = createDashboardState(undefined, undefined, undefined, undefined, () => {
  void renderTrendChart();
});

async function loadEChartsCore(): Promise<EChartsCore> {
  if (!echartsCorePromise) {
    echartsCorePromise = Promise.all([
      import('echarts/core'),
      import('echarts/lib/chart/bar'),
      import('echarts/lib/chart/line'),
      import('echarts/lib/component/grid'),
      import('echarts/lib/component/tooltip'),
      import('echarts/lib/component/legend'),
      import('echarts/lib/component/dataZoom'),
      import('echarts/lib/renderer/installCanvasRenderer.js'),
    ]).then(([core, _bar, _line, _grid, _tooltip, _legend, _dataZoom, canvasRenderer]) => {
      core.use([canvasRenderer.install]);
      return core;
    });
  }
  return echartsCorePromise;
}

async function renderTrendChart() {
  if (!trendChartRef.value || !metrics.value) {
    return;
  }
  const echarts = await loadEChartsCore();
  if (!trendChartRef.value || !metrics.value) {
    return;
  }
  const buckets = currentTrendBuckets.value;
  if (!trendChart) {
    trendChart = echarts.init(trendChartRef.value);
  }
  const axisColor = themeStore.isDark ? 'rgba(226,232,240,0.72)' : 'rgba(71,85,105,0.85)';
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { top: 2, textStyle: { color: axisColor } },
    grid: { left: 44, right: 18, top: 40, bottom: 52 },
    xAxis: {
      type: 'category',
      data: buckets.map((item) => item.label),
      axisTick: { show: false },
      axisLabel: { color: axisColor },
    },
    yAxis: { type: 'value', axisLabel: { color: axisColor } },
    dataZoom: [
      { type: 'inside' },
      { type: 'slider', height: 16, bottom: 10 },
    ],
    series: [
      {
        name: '总调用',
        type: 'line',
        smooth: true,
        data: buckets.map((item) => item.totalCalls),
      },
      {
        name: '失败',
        type: 'bar',
        data: buckets.map((item) => item.failedCalls),
      },
      {
        name: '超时',
        type: 'bar',
        data: buckets.map((item) => item.timeoutCalls),
      },
    ],
  });
}

function handleResize() {
  trendChart?.resize?.();
}

watch(
  () => themeStore.theme,
  () => {
    void renderTrendChart();
  },
);

watch(metrics, () => {
  if (metrics.value) {
    lastUpdatedLabel.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  }
});

onMounted(() => {
  void loadDashboard();
  window.addEventListener('resize', handleResize);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  trendChart?.dispose();
  trendChart = null;
});

defineExpose({
  selectedRange,
  metrics,
  metricCards,
  errorMessage,
  loadDashboard,
  handleRangeChange,
});
</script>
