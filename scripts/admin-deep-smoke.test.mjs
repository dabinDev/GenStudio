import assert from 'node:assert/strict';
import { test } from 'node:test';

process.env.ADMIN_DEEP_SMOKE_UNIT_ONLY = '1';

const smoke = await import('./admin-deep-smoke.mjs');

test('safeName keeps ASCII names readable and gives Chinese names a stable fallback', () => {
  assert.equal(smoke.safeName('admin-models-detail-drawer'), 'admin-models-detail-drawer');
  assert.match(smoke.safeName('文案记录'), /^u-[a-f0-9]+$/);
  assert.notEqual(smoke.safeName('文案记录'), smoke.safeName('生图记录'));
  assert.notEqual(smoke.safeName('生图记录'), smoke.safeName('视频记录'));
  assert.notEqual(smoke.safeName('admin-records-tab-文案记录'), smoke.safeName('admin-records-tab-生图记录'));
  assert.notEqual(smoke.safeName('admin-records-tab-文案记录'), 'admin-records-tab');
});

test('record tab labels stay readable for role-based browser locators', () => {
  assert.deepEqual(smoke.RECORD_TAB_NAMES, ['文案记录', '生图记录', '视频记录']);
  for (const label of smoke.RECORD_TAB_NAMES) {
    assert.equal(smoke.hasMojibake(label), false);
  }
});

test('admin smoke routes and viewports cover release-critical desktop and mobile paths', () => {
  assert.deepEqual(smoke.ADMIN_SMOKE_ROUTES, ['dashboard', 'models', 'users', 'forbidden']);
  assert.deepEqual(
    smoke.ADMIN_SMOKE_VIEWPORTS.map((item) => item.name),
    ['desktop', 'mobile'],
  );
  assert.deepEqual(smoke.ADMIN_SMOKE_VIEWPORTS[1], { name: 'mobile', width: 390, height: 844 });
});

test('admin smoke uses load-oriented waits instead of networkidle for dashboard charts', () => {
  assert.equal(smoke.SMOKE_WAIT_UNTIL, 'load');
});

test('mojibake detector catches broken placeholder labels', () => {
  assert.equal(smoke.hasMojibake('????????'), true);
  assert.equal(smoke.hasMojibake('�'), true);
  assert.equal(smoke.hasMojibake('正常中文'), false);
});

test('admin route URLs are joined without double slash blank pages', () => {
  assert.equal(
    smoke.adminRouteUrl('https://studio.cylonai.cn/admin/', 'dashboard'),
    'https://studio.cylonai.cn/admin/dashboard',
  );
  assert.equal(
    smoke.adminRouteUrl('https://studio.cylonai.cn/admin', 'records?capability=image'),
    'https://studio.cylonai.cn/admin/records?capability=image',
  );
  assert.equal(
    smoke.adminRouteUrl('https://studio.cylonai.cn/admin/', '/settings'),
    'https://studio.cylonai.cn/admin/settings',
  );
});

test('route wait helper recognizes only the target admin route', () => {
  assert.equal(
    smoke.isAdminRouteActive('https://studio.cylonai.cn/admin/dashboard', 'dashboard'),
    true,
  );
  assert.equal(
    smoke.isAdminRouteActive('https://studio.cylonai.cn/admin/dashboard?foo=bar', 'dashboard'),
    true,
  );
  assert.equal(
    smoke.isAdminRouteActive('http://127.0.0.1:5174/admin/models', 'models'),
    true,
  );
  assert.equal(
    smoke.isAdminRouteActive('http://127.0.0.1:5174/admin/dashboard', 'models'),
    false,
  );
  assert.equal(
    smoke.isAdminRouteActive('not a url', 'models'),
    false,
  );
});

test('requiresImageViewerCoverage requires all image viewer checks to pass', () => {
  const passingChecks = [
    { name: 'records:image-tab-selected', ok: true },
    { name: 'records:image-table-mode', ok: true },
    { name: 'records:image-record-media-visible', ok: true },
    { name: 'records:image-viewer-visible', ok: true },
    { name: 'records:image-viewer-actions-visible', ok: true },
  ];

  assert.equal(smoke.requiresImageViewerCoverage({ checks: passingChecks }), true);
  assert.equal(smoke.requiresImageViewerCoverage(passingChecks), true);
  assert.equal(
    smoke.requiresImageViewerCoverage(passingChecks.filter((check) => check.name !== 'records:image-viewer-visible')),
    false,
  );
  assert.equal(
    smoke.requiresImageViewerCoverage(
      passingChecks.map((check) =>
        check.name === 'records:image-record-media-visible' ? { ...check, ok: false } : check,
      ),
    ),
    false,
  );
});

test('buildAdminDeepSmokeSummary adds the image viewer coverage gate before failed checks are finalized', () => {
  const summary = smoke.buildAdminDeepSmokeSummary({
    front: 'http://127.0.0.1:5175',
    admin: 'http://127.0.0.1:5174/admin',
    api: 'http://127.0.0.1:8000',
    outDir: 'output/test',
    results: [],
    checks: [
      { name: 'records:image-tab-selected', ok: true },
      { name: 'records:image-table-mode', ok: true },
      { name: 'records:image-record-media-visible', ok: true },
      { name: 'records:image-viewer-visible', ok: true },
    ],
    failedResponses: [],
    consoleErrors: [],
    nonAuthConsoleErrors: [],
  });

  assert.equal(summary.failedChecks.some((check) => check.name === 'records:image-viewer-coverage-required'), true);
  assert.equal(summary.checks.some((check) => check.name === 'records:image-viewer-coverage-required'), true);
});

test('buildAdminDeepSmokeSummary treats skipped audit detail checks as passing', () => {
  const summary = smoke.buildAdminDeepSmokeSummary({
    front: 'http://127.0.0.1:5175',
    admin: 'http://127.0.0.1:5174/admin',
    api: 'http://127.0.0.1:8000',
    outDir: 'output/test',
    results: [],
    checks: [
      { name: 'records:image-tab-selected', ok: true },
      { name: 'records:image-table-mode', ok: true },
      { name: 'records:image-record-media-visible', ok: true },
      { name: 'records:image-viewer-visible', ok: true },
      { name: 'records:image-viewer-actions-visible', ok: true },
      { name: 'audit:open-detail', ok: true, skipped: true, reason: 'no-audit-rows' },
    ],
    failedResponses: [],
    consoleErrors: [],
    nonAuthConsoleErrors: [],
  });

  assert.deepEqual(summary.failedChecks, []);
});

test('buildImageViewerActionChecks scopes every control lookup to the image viewer', async () => {
  const calls = [];
  const viewer = {
    getByRole(role, options) {
      calls.push({ role, name: String(options.name) });
      return {
        first() {
          return {
            async isVisible() {
              return true;
            },
          };
        },
      };
    },
  };

  const checks = smoke.buildImageViewerActionChecks(viewer);
  const actionSummary = await smoke.collectViewerActionVisibility(checks);

  assert.equal(actionSummary.ok, true);
  assert.deepEqual(actionSummary.results.map((item) => item.label), [
    '上一张',
    '下一张',
    '缩小',
    '放大',
    '重置',
    '保存',
    '原图',
    '关闭',
  ]);
  assert.deepEqual(calls.map((call) => call.role), [
    'button',
    'button',
    'button',
    'button',
    'button',
    'link',
    'link',
    'button',
  ]);
});
