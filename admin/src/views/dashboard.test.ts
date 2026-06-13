import { afterEach, describe, expect, it, vi } from 'vitest';
import { nextTick } from 'vue';

import { fetchDashboardMetrics } from '@/api/admin';
import type { AdminDashboardMetrics } from '@/types';
import {
  createDashboardState,
  CREDIT_SUMMARY_TITLE,
  DASHBOARD_TITLE,
  formatDuration,
  formatPercent,
} from './dashboardState';

const chartMock = vi.hoisted(() => {
  const setOption = vi.fn();
  const dispose = vi.fn();
  const resize = vi.fn();
  const init = vi.fn(() => ({ setOption, dispose, resize }));
  return { setOption, dispose, resize, init };
});

vi.mock('echarts', () => ({ init: chartMock.init }));
vi.mock('@/api/admin', () => ({
  fetchDashboardMetrics: vi.fn(),
}));

function makeMetrics(overrides: Partial<AdminDashboardMetrics> = {}): AdminDashboardMetrics {
  return {
    totals: {
      totalCalls: 1280,
      successCalls: 1216,
      failedCalls: 64,
      timeoutCalls: 16,
      failureRate: 0.05,
      timeoutRate: 0.0125,
      averageDurationMs: 2450,
      averageQueueMs: 380,
      quotaUnits: 97.5,
      publicModelCalls: 900,
      privateModelCalls: 380,
    },
    trends: {
      day: [
        {
          label: '06-10',
          totalCalls: 80,
          successCalls: 76,
          failedCalls: 4,
          timeoutCalls: 1,
          quotaUnits: 12,
          averageDurationMs: 2100,
        },
      ],
      week: [
        {
          label: '06-08~06-14',
          totalCalls: 180,
          successCalls: 170,
          failedCalls: 10,
          timeoutCalls: 2,
          quotaUnits: 32,
          averageDurationMs: 3200,
        },
      ],
      month: [
        {
          label: '2026-06',
          totalCalls: 520,
          successCalls: 500,
          failedCalls: 20,
          timeoutCalls: 4,
          quotaUnits: 88,
          averageDurationMs: 4100,
        },
      ],
    },
    capabilityBreakdown: [],
    ownershipBreakdown: [],
    creditSummary: {
      reserved: 11,
      spent: 230,
      refunded: 8,
      adminAdjusted: 5,
    },
    failedModels: [
      {
        modelGroupId: 'model-1',
        modelName: 'Image Pro',
        capability: 'image',
        failedCalls: 9,
        totalCalls: 120,
        failureRate: 0.075,
        lastError: 'upstream timeout',
      },
    ],
    slowModels: [],
    activeUsers: [
      {
        userId: 'user-1',
        label: 'alice@example.com',
        totalCalls: 66,
        publicModelCalls: 40,
        privateModelCalls: 26,
      },
    ],
    ...overrides,
  };
}

async function flushDashboard() {
  await Promise.resolve();
  await Promise.resolve();
  await nextTick();
}

describe('DashboardView', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('requests 30d metrics by default and renders key dashboard copy', async () => {
    vi.mocked(fetchDashboardMetrics).mockResolvedValue(makeMetrics());

    const dashboard = createDashboardState();
    await dashboard.loadDashboard();
    await flushDashboard();

    expect(fetchDashboardMetrics).toHaveBeenCalledWith('30d');
    expect(DASHBOARD_TITLE).toBe('运营仪表盘');
    expect(CREDIT_SUMMARY_TITLE).toBe('积分概览');
    expect(dashboard.metricCards.value).toEqual(expect.arrayContaining([
      expect.objectContaining({ label: '总调用', value: '1,280' }),
      expect.objectContaining({ label: '失败率', value: '5.0%' }),
      expect.objectContaining({ label: '超时率', value: '1.3%' }),
      expect.objectContaining({ label: '平均耗时', value: '2.45s' }),
      expect.objectContaining({ label: '平均排队', value: '380ms' }),
      expect.objectContaining({ label: '额度消耗', value: '97.5' }),
    ]));
    expect(dashboard.creditItems.value).toEqual(expect.arrayContaining([
      expect.objectContaining({ label: '已消耗', value: '230' }),
    ]));
    expect(dashboard.failedModels.value[0].modelName).toBe('Image Pro');
    expect(dashboard.activeUsers.value[0].label).toBe('alice@example.com');
  });

  it('switches dashboard trend buckets and builds failed-model record links', async () => {
    vi.mocked(fetchDashboardMetrics).mockResolvedValue(makeMetrics());

    const dashboard = createDashboardState();
    await dashboard.loadDashboard();
    await flushDashboard();

    expect(dashboard.trendGranularity.value).toBe('day');
    expect(dashboard.currentTrendBuckets.value[0].label).toBe('06-10');

    dashboard.handleTrendGranularityChange('week');

    expect(dashboard.trendGranularity.value).toBe('week');
    expect(dashboard.currentTrendBuckets.value[0].label).toBe('06-08~06-14');
    expect(dashboard.failedModelRecordLink(dashboard.failedModels.value[0])).toBe('/records?capability=image&modelGroupId=model-1&status=non_success');
    expect(dashboard.modelRecordLink({
      modelGroupId: 'model-2',
      modelName: 'Slow Video',
      capability: 'video',
      totalCalls: 8,
    })).toBe('/records?capability=video&modelGroupId=model-2');
    expect(dashboard.activeUserRecordLink(dashboard.activeUsers.value[0])).toBe('/records?userId=user-1');
  });

  it('reloads metrics when range changes', async () => {
    vi.mocked(fetchDashboardMetrics).mockResolvedValue(makeMetrics());
    const dashboard = createDashboardState();
    await dashboard.loadDashboard();
    await flushDashboard();

    await dashboard.handleRangeChange('7d');
    await flushDashboard();

    expect(fetchDashboardMetrics).toHaveBeenNthCalledWith(1, '30d');
    expect(fetchDashboardMetrics).toHaveBeenNthCalledWith(2, '7d');
  });

  it('formats rates and durations for metric cards', () => {
    expect(formatPercent(0.125)).toBe('12.5%');
    expect(formatDuration(980)).toBe('980ms');
    expect(formatDuration(2450)).toBe('2.45s');
  });

  it('shows a friendly error when metrics cannot load', async () => {
    vi.mocked(fetchDashboardMetrics).mockRejectedValue(new Error('upstream exploded'));

    const dashboard = createDashboardState();
    await dashboard.loadDashboard();
    await flushDashboard();

    expect(dashboard.errorMessage.value).toBe('仪表盘数据暂时无法加载，请稍后重试。');
  });

  it('keeps the latest range result when earlier requests resolve late', async () => {
    let resolve30d: (metrics: AdminDashboardMetrics) => void = () => {};
    const fast7d = makeMetrics({
      totals: {
        ...makeMetrics().totals,
        totalCalls: 7,
      },
    });
    const stale30d = makeMetrics({
      totals: {
        ...makeMetrics().totals,
        totalCalls: 30,
      },
    });
    vi.mocked(fetchDashboardMetrics)
      .mockImplementationOnce(() => new Promise((resolve) => { resolve30d = resolve; }))
      .mockResolvedValueOnce(fast7d);

    const dashboard = createDashboardState();
    const initialLoad = dashboard.loadDashboard();
    const rangeLoad = dashboard.handleRangeChange('7d');
    await rangeLoad;
    await flushDashboard();

    expect(dashboard.selectedRange.value).toBe('7d');
    expect(dashboard.metrics.value?.totals.totalCalls).toBe(7);

    resolve30d(stale30d);
    await initialLoad;
    await flushDashboard();

    expect(dashboard.selectedRange.value).toBe('7d');
    expect(dashboard.metrics.value?.totals.totalCalls).toBe(7);
    expect(dashboard.isLoading.value).toBe(false);
  });
});
