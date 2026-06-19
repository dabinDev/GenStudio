import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

process.env.ADMIN_THEME_SYNC_UNIT_ONLY = '1';
const smoke = await import('./admin-theme-sync-smoke.mjs');

describe('admin theme sync smoke helpers', () => {
  it('normalizes only supported theme values', () => {
    assert.equal(smoke.normalizeThemeValue('dark'), 'dark');
    assert.equal(smoke.normalizeThemeValue('light'), 'light');
    assert.equal(smoke.normalizeThemeValue('midnight'), 'light');
    assert.equal(smoke.normalizeThemeValue(''), 'light');
  });

  it('requires light and dark cases', () => {
    assert.deepEqual(smoke.THEME_CASES, ['light', 'dark']);
  });

  it('normalizes admin entry URLs to the independent admin app', () => {
    assert.equal(
      smoke.adminEntryUrl('https://studio.cylonai.cn/admin'),
      'https://studio.cylonai.cn/admin/',
    );
    assert.equal(
      smoke.adminEntryUrl('https://studio.cylonai.cn/admin/'),
      'https://studio.cylonai.cn/admin/',
    );
    assert.equal(
      smoke.adminEntryUrl('https://studio.cylonai.cn/admin/dashboard'),
      'https://studio.cylonai.cn/admin/dashboard',
    );
  });

  it('adds a theme bridge query for local split-origin admin testing', () => {
    assert.equal(
      smoke.adminThemeUrl('http://127.0.0.1:5174/admin/', 'dark'),
      'http://127.0.0.1:5174/admin/?theme=dark',
    );
    assert.equal(
      smoke.adminThemeUrl('https://studio.cylonai.cn/admin/', 'light'),
      'https://studio.cylonai.cn/admin/?theme=light',
    );
    assert.equal(
      smoke.adminThemeUrl('https://studio.cylonai.cn/admin/?foo=bar', 'dark'),
      'https://studio.cylonai.cn/admin/?foo=bar&theme=dark',
    );
  });

  it('summarizes failed theme checks and browser errors', () => {
    const summary = smoke.summarizeThemeSmoke({
      checks: [{ ok: true }, { ok: false }],
      failedResponses: [{ status: 500 }],
      nonAuthConsoleErrors: [{ text: 'boom' }],
    });

    assert.deepEqual(summary, {
      ok: false,
      failedCheckCount: 1,
      failedResponseCount: 1,
      consoleErrorCount: 1,
    });
  });
});
