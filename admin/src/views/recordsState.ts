import { reactive, ref } from 'vue';

import { buildExportFilename, downloadBlob } from '@/adminExport';
import { exportAdminRecords, fetchAdminRecords } from '@/api/admin';
import { AdminApiError } from '@/api/http';
import type { AdminCreationRecord, AdminRecordQuery, Capability } from '@/types';

const RECORD_FILTER_PRESETS_KEY = 'genstudio-admin-record-filter-presets-v1';

type RecordFilters = Required<Pick<
  AdminRecordQuery,
  'userId' | 'userSearch' | 'modelGroupId' | 'keyword' | 'status' | 'size' | 'ratio' | 'refCount' | 'duration' | 'resolution' | 'mode'
>>;

export interface RecordFilterPreset {
  id: string;
  name: string;
  capability: Capability;
  filters: RecordFilters;
  createdAt: string;
}

function emptyRecordFilters(): RecordFilters {
  return {
    userId: '',
    userSearch: '',
    modelGroupId: '',
    keyword: '',
    status: '',
    size: '',
    ratio: '',
    refCount: '',
    duration: '',
    resolution: '',
    mode: '',
  };
}

function cloneRecordFilters(filters: RecordFilters): RecordFilters {
  return { ...emptyRecordFilters(), ...filters };
}

function loadFilterPresets(): RecordFilterPreset[] {
  if (typeof localStorage === 'undefined') return [];
  try {
    const value = localStorage.getItem(RECORD_FILTER_PRESETS_KEY);
    const parsed = value ? JSON.parse(value) : [];
    return Array.isArray(parsed) ? parsed.filter((item) => item && typeof item.id === 'string') : [];
  } catch {
    return [];
  }
}

function persistFilterPresets(presets: RecordFilterPreset[]) {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(RECORD_FILTER_PRESETS_KEY, JSON.stringify(presets));
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderInlineMarkdown(value: string): string {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
}

export function renderSafeMarkdown(value: string): string {
  const lines = String(value || '').split(/\r?\n/);
  const html: string[] = [];
  let inList = false;
  const closeList = () => {
    if (inList) {
      html.push('</ul>');
      inList = false;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    if (!line.trim()) {
      closeList();
      continue;
    }
    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    if (heading) {
      closeList();
      const level = Math.min(heading[1].length + 1, 4);
      html.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }
    const listItem = /^\s*[-*]\s+(.+)$/.exec(line);
    if (listItem) {
      if (!inList) {
        html.push('<ul>');
        inList = true;
      }
      html.push(`<li>${renderInlineMarkdown(listItem[1])}</li>`);
      continue;
    }
    closeList();
    html.push(`<p>${renderInlineMarkdown(line)}</p>`);
  }

  closeList();
  return html.join('');
}

function queryValue(value: unknown): string {
  if (Array.isArray(value)) return String(value[0] || '').trim();
  return String(value || '').trim();
}

function isCapability(value: string): value is Capability {
  return value === 'text' || value === 'image' || value === 'video';
}

export function friendlyAdminContentError(error: unknown, fallback: string): string {
  if (error instanceof AdminApiError && error.message.trim()) {
    return error.message.trim();
  }
  return fallback;
}

export function recordStatusLabel(status: string) {
  if (status === 'success') return '成功';
  if (status === 'error') return '失败';
  if (status === 'running' || status === 'processing') return '处理中';
  if (status === 'non_success') return '未成功';
  return status || '未知';
}

export function visibleRecordExportQuery(
  lastLoadedCapability: Capability,
  lastLoadedQuery: AdminRecordQuery,
): { capability: Capability; query: AdminRecordQuery } {
  return { capability: lastLoadedCapability, query: { ...lastLoadedQuery } };
}

export function canExportVisibleRecords(options: {
  canExportRecords: boolean;
  recordCount: number;
  isExporting: boolean;
  isLoading: boolean;
}): boolean {
  return options.canExportRecords && options.recordCount > 0 && !options.isExporting && !options.isLoading;
}

export function createRecordsState(
  loader: (capability: Capability, query: AdminRecordQuery) => Promise<AdminCreationRecord[]> = fetchAdminRecords,
) {
  const capability = ref<Capability>('text');
  const records = ref<AdminCreationRecord[]>([]);
  const isLoading = ref(false);
  const errorMessage = ref('');
  const filters = reactive<RecordFilters>(emptyRecordFilters());
  const lastLoadedCapability = ref<Capability>('text');
  const lastLoadedQuery = ref<AdminRecordQuery>({ ...emptyRecordFilters() });
  const savedFilterPresets = ref<RecordFilterPreset[]>(loadFilterPresets());
  const activePresetId = ref('');
  let latestRequestId = 0;

  async function loadRecords() {
    const requestId = latestRequestId + 1;
    latestRequestId = requestId;
    isLoading.value = true;
    errorMessage.value = '';
    const capabilityForRequest = capability.value;
    const queryForRequest = { ...filters };
    try {
      const result = await loader(capabilityForRequest, queryForRequest);
      if (requestId === latestRequestId) {
        records.value = result;
        lastLoadedCapability.value = capabilityForRequest;
        lastLoadedQuery.value = { ...queryForRequest };
      }
    } catch (error) {
      if (requestId === latestRequestId) {
        errorMessage.value = friendlyAdminContentError(error, '创作记录加载失败，请稍后重试。');
      }
    } finally {
      if (requestId === latestRequestId) {
        isLoading.value = false;
      }
    }
  }

  function visibleFilterPresets() {
    return savedFilterPresets.value.filter((preset) => preset.capability === capability.value);
  }

  function saveCurrentFilterPreset(name: string): RecordFilterPreset {
    const cleanName = name.trim() || `${capability.value} 筛选`;
    const preset: RecordFilterPreset = {
      id: `record_filter_${Date.now()}_${Math.random().toString(16).slice(2)}`,
      name: cleanName,
      capability: capability.value,
      filters: cloneRecordFilters(filters),
      createdAt: new Date().toISOString(),
    };
    savedFilterPresets.value = [
      preset,
      ...savedFilterPresets.value.filter(
        (item) => !(item.capability === preset.capability && item.name === preset.name),
      ),
    ].slice(0, 24);
    activePresetId.value = preset.id;
    persistFilterPresets(savedFilterPresets.value);
    return preset;
  }

  function applyFilterPreset(presetId: string): boolean {
    const preset = savedFilterPresets.value.find((item) => item.id === presetId);
    if (!preset) return false;
    Object.assign(filters, cloneRecordFilters(preset.filters));
    capability.value = preset.capability;
    activePresetId.value = preset.id;
    return true;
  }

  function removeFilterPreset(presetId: string): boolean {
    const next = savedFilterPresets.value.filter((item) => item.id !== presetId);
    if (next.length === savedFilterPresets.value.length) return false;
    savedFilterPresets.value = next;
    if (activePresetId.value === presetId) {
      activePresetId.value = '';
    }
    persistFilterPresets(savedFilterPresets.value);
    return true;
  }

  function applyRouteQueryFilters(query: Record<string, unknown>) {
    const queryCapability = queryValue(query.capability);
    if (isCapability(queryCapability)) {
      capability.value = queryCapability;
    }
    const routeFilters: Partial<RecordFilters> = {
      userId: queryValue(query.userId),
      userSearch: queryValue(query.userSearch),
      modelGroupId: queryValue(query.modelGroupId),
      keyword: queryValue(query.keyword),
      status: queryValue(query.status),
      size: queryValue(query.size),
      ratio: queryValue(query.ratio),
      refCount: queryValue(query.refCount),
      duration: queryValue(query.duration),
      resolution: queryValue(query.resolution),
      mode: queryValue(query.mode),
    };
    for (const [key, value] of Object.entries(routeFilters)) {
      if (value) {
        filters[key as keyof RecordFilters] = value;
      }
    }
  }

  return {
    capability,
    records,
    isLoading,
    errorMessage,
    filters,
    lastLoadedCapability,
    lastLoadedQuery,
    savedFilterPresets,
    activePresetId,
    visibleFilterPresets,
    saveCurrentFilterPreset,
    applyFilterPreset,
    removeFilterPreset,
    applyRouteQueryFilters,
    loadRecords,
  };
}

export function createRecordsExportState(
  exporter: (capability: Capability, query: AdminRecordQuery) => Promise<Blob> = exportAdminRecords,
  downloader: (filename: string, blob: Blob) => void = downloadBlob,
) {
  const isExporting = ref(false);

  async function exportRecords(capability: Capability, query: AdminRecordQuery = {}): Promise<boolean> {
    if (isExporting.value) {
      return false;
    }
    isExporting.value = true;
    try {
      const blob = await exporter(capability, query);
      downloader(buildExportFilename('records', capability), blob);
      return true;
    } finally {
      isExporting.value = false;
    }
  }

  return {
    isExporting,
    exportRecords,
  };
}
