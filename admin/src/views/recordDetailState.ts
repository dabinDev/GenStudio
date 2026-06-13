import type { AdminCreationRecord, AdminCreationRecordDetail } from '@/types';

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

export function taskIdFromDetail(detail: AdminCreationRecordDetail): string {
  if (detail.taskId) return detail.taskId;
  if (detail.request && typeof detail.request === 'object') {
    const requestTaskId = stringValue(detail.request.taskId)
      || stringValue(detail.request.task_id)
      || stringValue(detail.request.localTaskId)
      || stringValue(detail.request.providerTaskId);
    if (requestTaskId) return requestTaskId;
  }
  if (detail.response && typeof detail.response === 'object') {
    return stringValue(detail.response.taskId)
      || stringValue(detail.response.task_id)
      || stringValue(detail.response.localTaskId)
      || stringValue(detail.response.providerTaskId);
  }
  return '';
}

export function detailResponseText(response: AdminCreationRecordDetail['response']): string {
  if (!response) return '';
  if (typeof response === 'string') return response;
  if (typeof response.text === 'string') return response.text;
  if (typeof response.content === 'string') return response.content;
  if (typeof response.message === 'string') return response.message;
  return JSON.stringify(response);
}

export function recordFromDetail(
  fallback: AdminCreationRecord,
  detail: AdminCreationRecordDetail,
): AdminCreationRecord {
  const detailPrompt = detail.role === 'user' ? detail.content : '';
  return {
    ...fallback,
    id: detail.id || fallback.id,
    user: detail.user ?? fallback.user,
    capability: detail.capability || fallback.capability,
    status: detail.status || fallback.status,
    prompt: detailPrompt || fallback.prompt,
    response: detailResponseText(detail.response) || fallback.response,
    createdAt: detail.createdAt || fallback.createdAt,
    assets: detail.assets || fallback.assets,
    requestParams: detail.request || fallback.requestParams,
    responseSummary: typeof detail.response === 'string'
      ? { content: detail.response }
      : detail.response || fallback.responseSummary,
    taskId: taskIdFromDetail(detail) || fallback.taskId,
    errorMessage: detail.errorMessage || fallback.errorMessage,
  };
}
