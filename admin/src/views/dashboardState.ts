import { computed, nextTick, ref, type Ref } from 'vue';

import { fetchDashboardMetrics } from '@/api/admin';
import type {
  AdminDashboardActiveUser,
  AdminDashboardMetrics,
  AdminDashboardModelMetric,
} from '@/types';

export const DASHBOARD_TITLE = '运营仪表盘';
export const CREDIT_SUMMARY_TITLE = '积分概览';

export const rangeOptions = [
  { label: '7天', value: '7d' },
  { label: '30天', value: '30d' },
  { label: '90天', value: '90d' },
] as const;

export type DashboardRangeValue = (typeof rangeOptions)[number]['value'];

const emptyTotals = {
  totalCalls: 0,
  successCalls: 0,
  failedCalls: 0,
  timeoutCalls: 0,
  failureRate: 0,
  timeoutRate: 0,
  averageDurationMs: 0,
  averageQueueMs: 0,
  quotaUnits: 0,
  publicModelCalls: 0,
  privateModelCalls: 0,
};

export const trendGranularityOptions = [
  { label: '日', value: 'day' },
  { label: '周', value: 'week' },
  { label: '月', value: 'month' },
] as const;

export type TrendGranularityValue = (typeof trendGranularityOptions)[number]['value'];

export function formatNumber(value: number) {
  return new Intl.NumberFormat('zh-CN').format(value || 0);
}

export function formatPercent(value: number) {
  return `${((value || 0) * 100).toFixed(1)}%`;
}

export function formatDuration(value: number) {
  if (!value) {
    return '0ms';
  }
  if (value < 1000) {
    return `${Math.round(value)}ms`;
  }
  return `${(value / 1000).toFixed(2)}s`;
}

function isRangeValue(value: string): value is DashboardRangeValue {
  return rangeOptions.some((item) => item.value === value);
}

export function createDashboardState(
  selectedRange = ref<DashboardRangeValue>('30d'),
  metrics = ref<AdminDashboardMetrics | null>(null),
  isLoading = ref(false),
  errorMessage = ref(''),
  afterLoad: () => void = () => {},
) {
  let latestRequestId = 0;
  const trendGranularity = ref<TrendGranularityValue>('day');
  const rangeLabel = computed(() => rangeOptions.find((item) => item.value === selectedRange.value)?.label || '30天');
  const totals = computed(() => metrics.value?.totals || emptyTotals);
  const metricCards = computed(() => [
    {
      label: '总调用',
      value: formatNumber(totals.value.totalCalls),
      hint: `成功 ${formatNumber(totals.value.successCalls)}`,
      tone: 'good' as const,
    },
    {
      label: '失败率',
      value: formatPercent(totals.value.failureRate),
      hint: `失败 ${formatNumber(totals.value.failedCalls)} 次`,
      tone: totals.value.failureRate >= 0.1 ? 'danger' as const : 'good' as const,
    },
    {
      label: '超时率',
      value: formatPercent(totals.value.timeoutRate),
      hint: `超时 ${formatNumber(totals.value.timeoutCalls)} 次`,
      tone: totals.value.timeoutRate >= 0.05 ? 'warn' as const : 'good' as const,
    },
    {
      label: '平均耗时',
      value: formatDuration(totals.value.averageDurationMs),
      hint: `公有 ${formatNumber(totals.value.publicModelCalls)} / 私有 ${formatNumber(totals.value.privateModelCalls)}`,
      tone: totals.value.averageDurationMs >= 60000 ? 'warn' as const : 'good' as const,
    },
    {
      label: '平均排队',
      value: formatDuration(totals.value.averageQueueMs || 0),
      hint: '任务进入上游前等待',
      tone: (totals.value.averageQueueMs || 0) >= 30000 ? 'warn' as const : 'good' as const,
    },
    {
      label: '额度消耗',
      value: formatNumber(totals.value.quotaUnits || 0),
      hint: 'Token / 积分 / 费用单位',
      tone: 'good' as const,
    },
  ]);

  const creditItems = computed(() => {
    const summary = metrics.value?.creditSummary || {
      reserved: 0,
      spent: 0,
      refunded: 0,
      adminAdjusted: 0,
    };
    return [
      { label: '已预留', value: formatNumber(summary.reserved) },
      { label: '已消耗', value: formatNumber(summary.spent) },
      { label: '已退回', value: formatNumber(summary.refunded) },
      { label: '后台调整', value: formatNumber(summary.adminAdjusted) },
    ];
  });

  const failedModels = computed<AdminDashboardModelMetric[]>(() => metrics.value?.failedModels || []);
  const slowModels = computed<AdminDashboardModelMetric[]>(() => metrics.value?.slowModels || []);
  const activeUsers = computed<AdminDashboardActiveUser[]>(() => metrics.value?.activeUsers || []);
  const currentTrendBuckets = computed(() => metrics.value?.trends?.[trendGranularity.value] || []);

  function isTrendGranularityValue(value: string): value is TrendGranularityValue {
    return trendGranularityOptions.some((item) => item.value === value);
  }

  function handleTrendGranularityChange(value: string) {
    if (!isTrendGranularityValue(value) || value === trendGranularity.value) {
      return;
    }
    trendGranularity.value = value;
    afterLoad();
  }

  function failedModelRecordLink(model: AdminDashboardModelMetric) {
    const params = new URLSearchParams();
    if (model.capability) params.set('capability', model.capability);
    if (model.modelGroupId) params.set('modelGroupId', model.modelGroupId);
    params.set('status', 'non_success');
    return `/records?${params.toString()}`;
  }

  function modelRecordLink(model: AdminDashboardModelMetric) {
    const params = new URLSearchParams();
    if (model.capability) params.set('capability', model.capability);
    if (model.modelGroupId) params.set('modelGroupId', model.modelGroupId);
    return `/records?${params.toString()}`;
  }

  function activeUserRecordLink(user: AdminDashboardActiveUser) {
    const params = new URLSearchParams();
    if (user.userId) params.set('userId', user.userId);
    return `/records?${params.toString()}`;
  }

  async function loadDashboard(range = selectedRange.value) {
    const requestId = latestRequestId + 1;
    latestRequestId = requestId;
    isLoading.value = true;
    errorMessage.value = '';
    try {
      const nextMetrics = await fetchDashboardMetrics(range);
      if (requestId !== latestRequestId) {
        return;
      }
      metrics.value = nextMetrics;
      await nextTick();
      afterLoad();
    } catch {
      if (requestId === latestRequestId) {
        errorMessage.value = '仪表盘数据暂时无法加载，请稍后重试。';
      }
    } finally {
      if (requestId === latestRequestId) {
        isLoading.value = false;
      }
    }
  }

  async function handleRangeChange(range: string) {
    if (range === selectedRange.value || !isRangeValue(range)) {
      return;
    }
    selectedRange.value = range;
    await loadDashboard(range);
  }

  return {
    selectedRange,
    metrics: metrics as Ref<AdminDashboardMetrics | null>,
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
  };
}
