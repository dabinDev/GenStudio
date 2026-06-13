import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  adjustUserCredits,
  adminUserPath,
  exportAdminUsers,
  fetchAdminUsers,
  setAdminUserStatus,
  updateAdminUser,
} from '@/api/admin';
import { AdminApiError, setAdminCsrfToken } from '@/api/http';
import type { AdminUserWithCredits } from '@/types';
import {
  createUserExportState,
  createUserCreditsState,
  creditAdjustmentConfirmMessage,
  friendlyAdminError,
  duplicateIdentityGroups,
  visibleUserExportQuery,
} from './userCreditsState';

function okJson(payload: unknown) {
  return Response.json(payload);
}

describe('user credits api client', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    setAdminCsrfToken('');
  });

  it('encodes user search and unwraps users', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => okJson({
      users: [
        {
          id: 'usr_1',
          email: 'member@example.com',
          nickname: 'Member',
          status: 'active',
          isAdmin: false,
          credits: { balance: 12, reservedBalance: 1 },
        },
      ],
    }));
    vi.stubGlobal('fetch', fetchMock);

    const users = await fetchAdminUsers('member 邮箱');

    expect(users).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/admin/users?search=member+%E9%82%AE%E7%AE%B1',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('encodes role and status filters when fetching users', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => okJson({ users: [] }));
    vi.stubGlobal('fetch', fetchMock);

    await fetchAdminUsers({ search: 'operator', role: 'operator', status: 'disabled' });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/admin/users?search=operator&role=operator&status=disabled',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('exports users through the backend export endpoint', async () => {
    const csv = '用户ID,邮箱\r\nusr_1,user@example.com\r\n';
    const fetchMock = vi.fn(async () => new Response(csv, {
      status: 200,
      headers: { 'content-type': 'text/csv;charset=utf-8' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    const result = await exportAdminUsers({ search: 'operator', role: 'operator', status: 'active' });

    expect(await result.text()).toBe(csv);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/admin/users/export?search=operator&role=operator&status=active',
      expect.objectContaining({ method: 'GET', credentials: 'include' }),
    );
  });

  it('uses expected user write endpoints and csrf token', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      okJson({ user: { id: 'usr_1' }, account: {}, transaction: {} }));
    vi.stubGlobal('fetch', fetchMock);
    setAdminCsrfToken('csrf-token');

    await updateAdminUser('usr_1', { nickname: 'New Name' });
    await setAdminUserStatus('usr_1', 'disable');
    await adjustUserCredits('usr_1', 20, '活动充值');

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/admin/users/usr_1',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ nickname: 'New Name' }),
        headers: expect.any(Headers),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/admin/users/usr_1/disable',
      expect.objectContaining({
        method: 'POST',
        body: '{}',
        headers: expect.any(Headers),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/admin/users/usr_1/credits/adjust',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ amount: 20, reason: '活动充值' }),
        headers: expect.any(Headers),
      }),
    );

    const firstCall = fetchMock.mock.calls.at(0);
    expect(firstCall).toBeDefined();
    const firstHeaders = (firstCall?.[1] as RequestInit).headers as Headers;
    expect(firstHeaders.get('X-CSRF-Token')).toBe('csrf-token');
    for (const call of fetchMock.mock.calls) {
      const headers = (call[1] as RequestInit).headers as Headers;
      expect(headers.get('X-CSRF-Token')).toBe('csrf-token');
    }
  });

  it('documents the URL-safe user id contract', () => {
    expect(adminUserPath('usr_abc123')).toBe('/api/admin/users/usr_abc123');
    expect(() => adminUserPath('usr/abc123')).toThrow('用户 ID 格式无效。');
  });
});

describe('user export state', () => {
  it('keeps user export single-flight and resets exporting state after download', async () => {
    let resolveExport!: (blob: Blob) => void;
    const exporter = vi.fn(() => new Promise<Blob>((resolve) => {
      resolveExport = resolve;
    }));
    const downloader = vi.fn();
    const state = createUserExportState(exporter, downloader);

    const firstExport = state.exportUsers({ search: 'operator', role: 'operator' });
    const secondExport = state.exportUsers({ search: 'operator', role: 'operator' });

    expect(state.isExporting.value).toBe(true);
    expect(exporter).toHaveBeenCalledTimes(1);
    await expect(secondExport).resolves.toBe(false);

    const blob = new Blob(['csv'], { type: 'text/csv' });
    resolveExport(blob);
    await expect(firstExport).resolves.toBe(true);

    expect(downloader).toHaveBeenCalledWith(expect.stringMatching(/^users-/), blob);
    expect(state.isExporting.value).toBe(false);
  });
});

function makeUser(id: string, overrides: Partial<AdminUserWithCredits> = {}): AdminUserWithCredits {
  return {
    id,
    externalUserId: id,
    email: `${id}@example.com`,
    phone: '',
    nickname: id,
    status: 'active',
    isAdmin: false,
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    credits: {
      id: `credit_${id}`,
      userId: id,
      balance: 0,
      reservedBalance: 0,
      totalRecharged: 0,
      totalSpent: 0,
      totalRefunded: 0,
      createdAt: '2026-01-01T00:00:00Z',
      updatedAt: '2026-01-01T00:00:00Z',
    },
    ...overrides,
  };
}

describe('user credits state', () => {
  it('keeps the latest search result when an earlier request resolves later', async () => {
    let resolveFirst!: (users: AdminUserWithCredits[]) => void;
    let resolveSecond!: (users: AdminUserWithCredits[]) => void;
    const loader = vi
      .fn()
      .mockImplementationOnce(() => new Promise<AdminUserWithCredits[]>((resolve) => {
        resolveFirst = resolve;
      }))
      .mockImplementationOnce(() => new Promise<AdminUserWithCredits[]>((resolve) => {
        resolveSecond = resolve;
      }));
    const state = createUserCreditsState(loader);

    state.search.value = 'first';
    const firstLoad = state.loadUsers();
    state.search.value = 'second';
    const secondLoad = state.loadUsers();

    resolveSecond([makeUser('second')]);
    await secondLoad;
    expect(state.lastLoadedQuery.value).toEqual({
      search: 'second',
      role: 'all',
      status: 'all',
    });

    resolveFirst([makeUser('first')]);
    await firstLoad;

    expect(state.users.value.map((user) => user.id)).toEqual(['second']);
    expect(state.lastLoadedQuery.value).toEqual({
      search: 'second',
      role: 'all',
      status: 'all',
    });
    expect(state.isLoading.value).toBe(false);
  });

  it('passes current search, role, and status filters to the loader', async () => {
    const loader = vi.fn(async () => [
      makeUser('operator', { isAdmin: true, adminRole: 'operator', status: 'disabled' }),
    ]);
    const state = createUserCreditsState(loader);

    state.search.value = 'operator';
    state.roleFilter.value = 'operator';
    state.statusFilter.value = 'disabled';
    await state.loadUsers();

    expect(loader).toHaveBeenCalledWith({
      search: 'operator',
      role: 'operator',
      status: 'disabled',
    });
    expect(state.filteredUsers.value.map((user) => user.id)).toEqual(['operator']);
  });

  it('keeps the last loaded user query for exporting the visible list', async () => {
    const loader = vi.fn(async () => [makeUser('operator', { isAdmin: true, adminRole: 'operator' })]);
    const state = createUserCreditsState(loader);

    state.search.value = 'operator';
    state.roleFilter.value = 'operator';
    state.statusFilter.value = 'active';
    await state.loadUsers();
    state.search.value = 'unsaved edit';
    state.roleFilter.value = 'admin';
    state.statusFilter.value = 'disabled';

    expect(state.lastLoadedQuery.value).toEqual({
      search: 'operator',
      role: 'operator',
      status: 'active',
    });
  });

  it('keeps the visible user list tied to the last successful load instead of unsaved filters', async () => {
    const loader = vi.fn(async () => [makeUser('operator', { isAdmin: true, adminRole: 'operator', status: 'active' })]);
    const state = createUserCreditsState(loader);

    state.search.value = 'operator';
    state.roleFilter.value = 'operator';
    state.statusFilter.value = 'active';
    await state.loadUsers();
    state.search.value = 'draft';
    state.roleFilter.value = 'user';
    state.statusFilter.value = 'disabled';

    expect(state.filteredUsers.value.map((user) => user.id)).toEqual(['operator']);
    expect(visibleUserExportQuery(state.lastLoadedQuery.value)).toEqual({
      search: 'operator',
      role: 'operator',
      status: 'active',
    });
  });

  it('summarizes duplicate identity groups from the visible user list', async () => {
    const loader = vi.fn(async () => [
      makeUser('duplicate-a', {
        email: 'dup@example.com',
        duplicateIdentity: {
          identity: 'email:dup@example.com',
          duplicateCount: 2,
          targetUserId: 'duplicate-a',
          userIds: ['duplicate-a', 'duplicate-b'],
        },
      }),
      makeUser('duplicate-b', {
        email: 'dup@example.com',
        duplicateIdentity: {
          identity: 'email:dup@example.com',
          duplicateCount: 2,
          targetUserId: 'duplicate-a',
          userIds: ['duplicate-a', 'duplicate-b'],
        },
      }),
      makeUser('unique'),
    ]);
    const state = createUserCreditsState(loader);

    await state.loadUsers();

    expect(duplicateIdentityGroups(state.filteredUsers.value)).toEqual([
      {
        identity: 'email:dup@example.com',
        duplicateCount: 2,
        targetUserId: 'duplicate-a',
        userIds: ['duplicate-a', 'duplicate-b'],
      },
    ]);
  });

  it('preserves duplicate identity metadata when replacing a user with a partial response', async () => {
    const duplicateIdentity = {
      identity: 'email:dup@example.com',
      duplicateCount: 2,
      targetUserId: 'duplicate-a',
      userIds: ['duplicate-a', 'duplicate-b'],
    };
    const loader = vi.fn(async () => [
      makeUser('duplicate-a', { email: 'dup@example.com', duplicateIdentity }),
      makeUser('duplicate-b', { email: 'dup@example.com', duplicateIdentity }),
    ]);
    const state = createUserCreditsState(loader);

    await state.loadUsers();
    state.replaceUser(makeUser('duplicate-a', { nickname: 'Updated duplicate' }));

    expect(state.users.value.find((user) => user.id === 'duplicate-a')?.duplicateIdentity).toEqual(duplicateIdentity);
    expect(duplicateIdentityGroups(state.filteredUsers.value)).toHaveLength(1);
  });

  it('clears duplicate identity metadata when the backend explicitly returns null', async () => {
    const duplicateIdentity = {
      identity: 'email:dup@example.com',
      duplicateCount: 2,
      targetUserId: 'duplicate-a',
      userIds: ['duplicate-a', 'duplicate-b'],
    };
    const loader = vi.fn(async () => [
      makeUser('duplicate-a', { email: 'dup@example.com', duplicateIdentity }),
      makeUser('duplicate-b', { email: 'dup@example.com', duplicateIdentity }),
    ]);
    const state = createUserCreditsState(loader);

    await state.loadUsers();
    state.replaceUser(makeUser('duplicate-a', {
      email: 'unique@example.com',
      duplicateIdentity: null,
    }));

    expect(state.users.value.find((user) => user.id === 'duplicate-a')?.duplicateIdentity).toBeNull();
    expect(duplicateIdentityGroups(state.filteredUsers.value)).toHaveLength(1);
  });

  it('surfaces friendly backend messages before falling back to generic copy', () => {
    expect(friendlyAdminError(new AdminApiError('余额不足，无法扣减。', 400), '操作失败')).toBe('余额不足，无法扣减。');
    expect(friendlyAdminError(new Error('network'), '操作失败')).toBe('操作失败');
  });

  it('describes credit adjustment confirmation by direction', () => {
    expect(creditAdjustmentConfirmMessage(8)).toBe('确认给该用户充值 8 积分？');
    expect(creditAdjustmentConfirmMessage(-3)).toBe('确认从该用户扣减 3 积分？');
  });
});
