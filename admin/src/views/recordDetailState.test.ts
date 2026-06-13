import { describe, expect, it } from 'vitest';

import type { AdminCreationRecord, AdminCreationRecordDetail } from '@/types';
import { detailResponseText, recordFromDetail } from './recordDetailState';

function makeRecord(overrides: Partial<AdminCreationRecord> = {}): AdminCreationRecord {
  return {
    id: 'msg_123',
    user: null,
    modelName: 'List Model',
    capability: 'image',
    status: 'success',
    prompt: 'list prompt',
    response: 'list response',
    createdAt: '2026-06-10T00:00:00Z',
    durationMs: 100,
    taskId: 'task_123',
    assets: [],
    requestParams: { source: 'list-request' },
    responseSummary: { source: 'list-response' },
    errorMessage: '',
    ...overrides,
  };
}

function makeDetail(overrides: Partial<AdminCreationRecordDetail> = {}): AdminCreationRecordDetail {
  return {
    id: 'msg_123',
    conversationId: 'conv_1',
    conversationTitle: 'Conversation detail',
    user: null,
    role: 'assistant',
    capability: 'image',
    status: 'success',
    content: 'detail content body',
    request: { prompt: 'detail prompt', seed: 42 },
    response: { text: 'detail response text' },
    errorMessage: '',
    assets: [{ type: 'image', url: 'https://cdn.example.com/detail.png' }],
    timeline: [],
    createdAt: '2026-06-10T00:00:00Z',
    ...overrides,
  };
}

describe('record detail state', () => {
  it('maps detail contract data into the drawer record without losing list fallback fields', () => {
    const merged = recordFromDetail(makeRecord(), makeDetail());

    expect(merged).toMatchObject({
      id: 'msg_123',
      modelName: 'List Model',
      prompt: 'list prompt',
      response: 'detail response text',
      requestParams: { prompt: 'detail prompt', seed: 42 },
      responseSummary: { text: 'detail response text' },
      assets: [{ type: 'image', url: 'https://cdn.example.com/detail.png' }],
    });
  });

  it('uses user detail content as prompt only when the detail row is a user message', () => {
    expect(recordFromDetail(makeRecord(), makeDetail({
      role: 'user',
      content: 'user detail prompt',
      response: {},
    })).prompt).toBe('user detail prompt');
    expect(recordFromDetail(makeRecord(), makeDetail({
      role: 'assistant',
      content: 'assistant response body',
    })).prompt).toBe('list prompt');
  });

  it('normalizes supported response shapes for display', () => {
    expect(detailResponseText('plain response')).toBe('plain response');
    expect(detailResponseText({ content: 'content response' })).toBe('content response');
    expect(detailResponseText({ message: 'message response' })).toBe('message response');
    expect(detailResponseText({ nested: true })).toBe(JSON.stringify({ nested: true }));
  });

  it('derives task id from detail fields before falling back to the list row', () => {
    expect(recordFromDetail(makeRecord({ taskId: '' }), makeDetail({ taskId: 'task_from_detail' })).taskId).toBe('task_from_detail');
    expect(recordFromDetail(makeRecord({ taskId: '' }), makeDetail({
      response: { providerTaskId: 'task_from_response' },
    })).taskId).toBe('task_from_response');
    expect(recordFromDetail(makeRecord({ taskId: 'task_from_list' }), makeDetail({
      taskId: '',
      response: {},
    })).taskId).toBe('task_from_list');
  });
});
