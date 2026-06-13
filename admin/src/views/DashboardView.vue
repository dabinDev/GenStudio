<template>
  <section class="admin-dashboard">
    <header class="admin-dashboard__header">
      <div>
        <h2>{{ DASHBOARD_TITLE }}</h2>
        <p>查看调用质量、积分消耗、重点模型健康状态和用户活跃情况。</p>
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

    <div class="admin-dashboard__metrics" :aria-busy="isLoading">
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
          <h3>失败模型</h3>
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
                <router-link class="admin-dashboard__table-link" :to="failedModelRecordLink(model)">
                  <strong>{{ model.modelName }}</strong>
                </router-link>
                <small>{{ model.lastError || model.capability }}</small>
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
          <h3>慢模型</h3>
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
                <router-link class="admin-dashboard__table-link" :to="modelRecordLink(model)">
                  <strong>{{ model.modelName }}</strong>
                </router-link>
                <small>{{ model.capability }}</small>
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
          <h3>活跃用户</h3>
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
import * as echarts from 'echarts';
import { onBeforeUnmount, onMounted, ref } from 'vue';

import AdminMetricCard from '@/components/AdminMetricCard.vue';
import type { AdminDashboardMetrics } from '@/types';
import {
  createDashboardState,
  CREDIT_SUMMARY_TITLE,
  DASHBOARD_TITLE,
  formatDuration,
  formatNumber,
  formatPercent,
  rangeOptions,
} from './dashboardState';

const trendChartRef = ref<HTMLElement | null>(null);
let trendChart: { setOption: (option: unknown) => void; dispose: () => void; resize?: () => void } | null = null;

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
} = createDashboardState(undefined, undefined, undefined, undefined, renderTrendChart);

function renderTrendChart() {
  if (!trendChartRef.value || !metrics.value) {
    return;
  }
  const buckets = currentTrendBuckets.value;
  if (!trendChart) {
    trendChart = echarts.init(trendChartRef.value);
  }
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 36, right: 18, top: 28, bottom: 32 },
    xAxis: {
      type: 'category',
      data: buckets.map((item) => item.label),
      axisTick: { show: false },
    },
    yAxis: { type: 'value' },
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
