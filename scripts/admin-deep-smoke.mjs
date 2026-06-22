import { chromium } from 'playwright';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

export const RECORD_TAB_NAMES = ['文案记录', '生图记录', '视频记录'];

export const ADMIN_SMOKE_ROUTES = ['dashboard', 'models', 'users', 'forbidden'];
export const ADMIN_SMOKE_VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 1100 },
  { name: 'mobile', width: 390, height: 844 },
];
export const SMOKE_WAIT_UNTIL = 'load';

export function safeName(value) {
  const raw = String(value);
  const ascii = raw.replace(/[^a-z0-9_-]+/gi, '-').replace(/^-+|-+$/g, '').toLowerCase();
  const digest = crypto.createHash('sha1').update(raw).digest('hex').slice(0, 10);
  if (ascii && /[^\x00-\x7F]/.test(raw)) {
    return `${ascii}-${digest}`;
  }
  if (ascii) return ascii;
  return raw ? `u-${digest}` : 'snapshot';
}

export function hasMojibake(text) {
  return /(?:\u951f|\ufffd|\?\?\?)/.test(text || '');
}

export function adminRouteUrl(adminBase, route) {
  const base = String(adminBase || '').replace(/\/+$/, '');
  const nextRoute = String(route || '').replace(/^\/+/, '');
  return `${base}/${nextRoute}`;
}

export function isAdminRouteActive(currentUrl, route) {
  try {
    const url = new URL(currentUrl);
    const targetRoute = String(route || '').replace(/^\/+/, '').split(/[?#]/, 1)[0].replace(/\/+$/, '');
    if (!targetRoute) return false;
    const path = url.pathname.replace(/\/+$/, '');
    return path.endsWith(`/admin/${targetRoute}`);
  } catch {
    return false;
  }
}

const REQUIRED_IMAGE_VIEWER_CHECKS = [
  'records:image-tab-selected',
  'records:image-table-mode',
  'records:image-record-media-visible',
  'records:image-viewer-visible',
  'records:image-viewer-actions-visible',
];

export function hasRequiredImageViewerChecks(checks) {
  if (!Array.isArray(checks)) return false;
  return REQUIRED_IMAGE_VIEWER_CHECKS.every((name) => checks.some((check) => check?.name === name && check.ok === true));
}

export function requiresImageViewerCoverage(summaryOrChecks) {
  const checks = Array.isArray(summaryOrChecks) ? summaryOrChecks : summaryOrChecks?.checks;
  return hasRequiredImageViewerChecks(checks);
}

export function buildAdminDeepSmokeSummary({
  front,
  admin,
  api,
  outDir,
  results,
  checks,
  failedResponses,
  consoleErrors,
  nonAuthConsoleErrors,
}) {
  const nextChecks = Array.isArray(checks) ? [...checks] : [];
  const summary = {
    front,
    admin,
    api,
    outDir,
    results,
    checks: nextChecks,
    failedChecks: [],
    failedResponses,
    consoleErrors,
    nonAuthConsoleErrors,
  };

  if (!requiresImageViewerCoverage(summary)) {
    summary.checks.push({
      name: 'records:image-viewer-coverage-required',
      ok: false,
      required: REQUIRED_IMAGE_VIEWER_CHECKS,
    });
  }

  summary.failedChecks = summary.checks.filter((item) => !item.ok);
  return summary;
}

export function buildImageViewerActionChecks(viewer) {
  return [
    { label: '上一张', locator: viewer.getByRole('button', { name: /上一张/ }) },
    { label: '下一张', locator: viewer.getByRole('button', { name: /下一张/ }) },
    { label: '缩小', locator: viewer.getByRole('button', { name: /缩小/ }) },
    { label: '放大', locator: viewer.getByRole('button', { name: /放大/ }) },
    { label: '重置', locator: viewer.getByRole('button', { name: /重置/ }) },
    { label: '保存', locator: viewer.getByRole('link', { name: /保存/ }) },
    { label: '原图', locator: viewer.getByRole('link', { name: /原图/ }) },
    { label: '关闭', locator: viewer.getByRole('button', { name: /关闭/ }) },
  ];
}

export async function collectViewerActionVisibility(viewerActionChecks) {
  const results = [];
  for (const action of viewerActionChecks) {
    results.push({
      label: action.label,
      visible: await action.locator.first().isVisible().catch(() => false),
    });
  }
  return {
    ok: results.every((item) => item.visible),
    results,
  };
}

if (process.env.ADMIN_DEEP_SMOKE_UNIT_ONLY !== '1') {
const FRONT = process.env.FRONT_URL || 'http://127.0.0.1:5175';
const ADMIN = process.env.ADMIN_URL || 'http://127.0.0.1:5174/admin';
const API = process.env.API_URL || 'http://127.0.0.1:8000';
const SMOKE_EMAIL = process.env.SMOKE_EMAIL || '';
const SMOKE_PASSWORD = process.env.SMOKE_PASSWORD || '';
const outDir = path.resolve(
  'output/playwright/admin-deep-smoke-' + new Date().toISOString().replace(/[:.]/g, '-'),
);

fs.mkdirSync(outDir, { recursive: true });

const results = [];
const checks = [];
const consoleErrors = [];
const failedResponses = [];

function rootOrigin(url) {
  return new URL(url).origin;
}

async function shot(page, name) {
  const file = path.join(outDir, `${safeName(name)}.png`);
  await page.screenshot({ path: file, fullPage: true }).catch(() => null);
  return file;
}

function pushCheck(name, ok, extra = {}) {
  checks.push({ name, ok: Boolean(ok), ...extra });
}

async function addPageResult(page, name, extra = {}) {
  const text = await page.locator('body').innerText({ timeout: 8000 }).catch(() => '');
  const screenshot = await shot(page, name);
  const result = {
    name,
    url: page.url(),
    title: await page.title().catch(() => ''),
    screenshot,
    hasVisibleMojibake: hasMojibake(text),
    textSample: text.slice(0, 520),
    ...extra,
  };
  results.push(result);
  pushCheck(`${name}:visible-text`, text.trim().length > 0, { length: text.trim().length });
  pushCheck(`${name}:no-mojibake`, !result.hasVisibleMojibake);
  return result;
}

async function gotoAndCapture(page, route, name) {
  const url = route.startsWith('http') ? route : adminRouteUrl(ADMIN, route);
  await page.goto(url, { waitUntil: SMOKE_WAIT_UNTIL, timeout: 60000 }).catch(async () => {
    await page.waitForLoadState('domcontentloaded', { timeout: 15000 }).catch(() => null);
  });
  if (!route.startsWith('http')) {
    await page.waitForURL((currentUrl) => isAdminRouteActive(String(currentUrl), route), {
      waitUntil: SMOKE_WAIT_UNTIL,
      timeout: 15000,
    }).catch(() => null);
  }
  await page.waitForTimeout(700);
  return addPageResult(page, name);
}

async function clickFirst(page, locator, name, options = {}) {
  const { optional = false, waitForIdle = true, ...clickOptions } = options;
  if (waitForIdle) {
    await waitForPageIdle(page, `${name}:idle-before-click`);
  }
  const count = await locator.count().catch(() => 0);
  if (!count) {
    pushCheck(name, optional, { reason: 'not-found', skipped: optional });
    return false;
  }
  const first = locator.first();
  if (!(await first.isVisible().catch(() => false))) {
    pushCheck(name, optional, { reason: 'not-visible', skipped: optional });
    return false;
  }
  let clickFailed = false;
  await first.click({ timeout: 8000, ...clickOptions }).catch((error) => {
    clickFailed = true;
    pushCheck(name, false, { reason: error.message });
  });
  await page.waitForTimeout(500);
  const wasRecorded = checks.some((item) => item.name === name);
  if (!wasRecorded) pushCheck(name, true);
  return !clickFailed;
}

async function waitForPageIdle(page, name = 'page:idle') {
  await page.waitForLoadState(SMOKE_WAIT_UNTIL, { timeout: 15000 }).catch(() => null);
  await page
    .locator('.el-loading-mask')
    .first()
    .waitFor({ state: 'hidden', timeout: 15000 })
    .catch(() => null);
  await page.waitForTimeout(200);
  const visibleLoadingMasks = await page.locator('.el-loading-mask:visible').count().catch(() => 0);
  if (visibleLoadingMasks === 0) {
    pushCheck(name, true, { visibleLoadingMasks });
  }
  return visibleLoadingMasks === 0;
}

async function fillFirst(page, locator, value, name, options = {}) {
  const { optional = false } = options;
  const count = await locator.count().catch(() => 0);
  if (!count) {
    pushCheck(name, optional, { reason: 'not-found', skipped: optional });
    return false;
  }
  const first = locator.first();
  if (!(await first.isVisible().catch(() => false))) {
    pushCheck(name, optional, { reason: 'not-visible', skipped: optional });
    return false;
  }
  await first.fill(value, { timeout: 8000 }).catch((error) => {
    pushCheck(name, false, { reason: error.message });
  });
  await page.keyboard.press('Enter').catch(() => null);
  await page.waitForTimeout(800);
  const wasRecorded = checks.some((item) => item.name === name);
  if (!wasRecorded) pushCheck(name, true);
  return true;
}

async function ensureImageTableMode(page) {
  const waterfall = page.locator('.admin-content-page__waterfall');
  const isWaterfallVisible = await waterfall.isVisible().catch(() => false);
  if (!isWaterfallVisible) {
    const tableVisible = await page.locator('.admin-content-page__table').isVisible().catch(() => false);
    pushCheck('records:image-table-mode', tableVisible, { alreadyTable: true, tableVisible });
    return tableVisible;
  }

  const switches = [
    page.locator('.admin-content-page__toolbar-group .el-switch').filter({ hasText: /瀑布流|表格/ }).last(),
    page.locator('.admin-content-page__toolbar-group .el-switch').last(),
  ];

  for (const switchLocator of switches) {
    const count = await switchLocator.count().catch(() => 0);
    if (!count || !(await switchLocator.first().isVisible().catch(() => false))) continue;
    await switchLocator.first().click({ timeout: 8000 }).catch(() => null);
    await page.waitForTimeout(800);
    if (!(await waterfall.isVisible().catch(() => false))) break;
  }

  const tableVisible = await page.locator('.admin-content-page__table').isVisible().catch(() => false);
  const stillWaterfall = await waterfall.isVisible().catch(() => false);
  pushCheck('records:image-table-mode', tableVisible && !stillWaterfall, { tableVisible, stillWaterfall });
  return tableVisible && !stillWaterfall;
}

async function verifyImageViewerActions(page) {
  const viewer = page.locator('.admin-image-viewer');
  return collectViewerActionVisibility(buildImageViewerActionChecks(viewer));
}

function summarizeViewerActionChecks(actionSummary) {
  return actionSummary.results.map((item) => `${item.label}:${item.visible ? 'visible' : 'missing'}`).join(', ');
}

async function login(context) {
  const frontOrigin = rootOrigin(FRONT);
  const apiOrigin = rootOrigin(API);
  if (SMOKE_EMAIL && SMOKE_PASSWORD) {
    const response = await context.request.post(`${rootOrigin(ADMIN)}/api/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { identifier: SMOKE_EMAIL, password: SMOKE_PASSWORD },
    });
    const payload = await response.json().catch(() => null);
    pushCheck('login:password', response.ok(), { status: response.status(), user: payload?.user?.email || '' });
    return response.ok();
  }

  const response = await context.request.post(`${frontOrigin}/api/auth/dev-login`, {
    headers: { 'Content-Type': 'application/json' },
    data: {
      externalUserId: 'local-admin-deep-smoke',
      email: 'cage_ben@sina.com',
      nickname: 'Deep Smoke Admin',
    },
  });
  const payload = await response.json().catch(() => null);
  pushCheck('login:dev', response.ok(), {
    status: response.status(),
    user: payload?.user?.email || '',
    apiOrigin,
  });
  return response.ok();
}

async function exerciseDashboard(page) {
  await gotoAndCapture(page, 'dashboard', 'admin-dashboard-initial');
  const rangeButtons = page.locator('.admin-dashboard__ranges button');
  const rangeCount = await rangeButtons.count().catch(() => 0);
  for (let index = 0; index < Math.min(rangeCount, 3); index += 1) {
    await rangeButtons.nth(index).click({ timeout: 8000 }).catch(() => null);
    await page.waitForTimeout(700);
  }
  pushCheck('dashboard:range-buttons', rangeCount >= 3, { count: rangeCount });

  const trendButtons = page.locator('.admin-dashboard__segmented button');
  const trendCount = await trendButtons.count().catch(() => 0);
  for (let index = 0; index < Math.min(trendCount, 3); index += 1) {
    await trendButtons.nth(index).click({ timeout: 8000 }).catch(() => null);
    await page.waitForTimeout(400);
  }
  pushCheck('dashboard:trend-buttons', trendCount >= 3, { count: trendCount });
  pushCheck('dashboard:chart-visible', await page.locator('.admin-dashboard__chart').isVisible().catch(() => false));
  await addPageResult(page, 'admin-dashboard-after-interactions');

  const linkClicked = await clickFirst(page, page.locator('.admin-dashboard__table-link'), 'dashboard:record-link');
  if (linkClicked) {
    await addPageResult(page, 'admin-dashboard-record-link-target');
    await clickFirst(page, page.getByRole('button', { name: /清空链接筛选/ }), 'records:clear-linked-filter-from-dashboard');
  }
}

async function exerciseModels(page) {
  await gotoAndCapture(page, 'models', 'admin-models-initial');
  await fillFirst(page, page.locator('.admin-model-center__filters input').last(), 'gpt', 'models:search');
  await addPageResult(page, 'admin-models-after-search');
  await clickFirst(page, page.getByRole('button', { name: /详情/ }), 'models:open-detail');
  await addPageResult(page, 'admin-models-detail-drawer');
  await page.keyboard.press('Escape').catch(() => null);
  await page.waitForTimeout(300);

  const checkboxClicked = await clickFirst(page, page.locator('.el-table__body-wrapper .el-checkbox'), 'models:select-row');
  if (checkboxClicked) {
    await clickFirst(page, page.getByRole('button', { name: /批量操作/ }), 'models:open-batch-menu');
    const menuText = await page.locator('body').innerText().catch(() => '');
    pushCheck('models:batch-menu-visible', /批量测试|批量公用|移除不可用/.test(menuText));
    await addPageResult(page, 'admin-models-batch-menu');
  }
}

async function exercisePrompts(page) {
  await gotoAndCapture(page, 'prompts', 'admin-prompts-initial');
  await fillFirst(page, page.getByPlaceholder(/搜索模板名称或内容/), '模板', 'prompts:search');
  await addPageResult(page, 'admin-prompts-after-search');
  const starterOpened = await clickFirst(page, page.locator('.admin-prompt-center__starter-grid button'), 'prompts:open-starter');
  if (starterOpened) {
    await addPageResult(page, 'admin-prompts-starter-drawer');
    await clickFirst(page, page.getByRole('button', { name: /测试渲染/ }), 'prompts:test-render');
    await addPageResult(page, 'admin-prompts-after-test-render');
    await page.keyboard.press('Escape').catch(() => null);
    await page.waitForTimeout(300);
  }
}

async function exerciseUsers(page) {
  await gotoAndCapture(page, 'users', 'admin-users-initial');
  await fillFirst(page, page.locator('.admin-user-credits__filters input').first(), 'cage', 'users:search');
  await addPageResult(page, 'admin-users-after-search');
  await clickFirst(page, page.getByRole('button', { name: /详情/ }), 'users:open-detail');
  await addPageResult(page, 'admin-users-detail-drawer');
  await page.keyboard.press('Escape').catch(() => null);
  await page.waitForTimeout(300);
}

async function exerciseRecords(page) {
  await gotoAndCapture(page, 'records?capability=image&status=non_success', 'admin-records-linked-filter');
  await clickFirst(page, page.getByRole('button', { name: /清空链接筛选/ }), 'records:clear-linked-filter');
  for (const tabName of RECORD_TAB_NAMES) {
    await clickFirst(page, page.getByRole('tab', { name: tabName }), `records:tab:${tabName}`);
    await page.waitForTimeout(800);
    await addPageResult(page, `admin-records-tab-${tabName}`);
  }
  await clickFirst(page, page.getByRole('tab', { name: '生图记录' }), 'records:return-image-tab');
  await page.waitForTimeout(800);
  pushCheck(
    'records:image-tab-selected',
    await page.getByRole('tab', { name: RECORD_TAB_NAMES[1], selected: true }).isVisible().catch(() => false),
  );
  await ensureImageTableMode(page);
  await waitForPageIdle(page, 'records:idle-after-image-table-mode');
  await addPageResult(page, 'admin-records-image-table-mode');
  await clickFirst(page, page.getByRole('button', { name: /高级筛选/ }), 'records:toggle-advanced-filters');
  pushCheck(
    'records:advanced-filters-visible',
    await page.locator('.admin-content-page__advanced-filters').isVisible().catch(() => false),
  );
  await addPageResult(page, 'admin-records-advanced-filters');

  const tableMediaButtons = page.locator('.admin-content-page__record-media-strip button');
  let mediaVisible = await tableMediaButtons.first().isVisible().catch(() => false);
  let openedViewer = false;

  if (mediaVisible) {
    pushCheck('records:image-record-media-visible', true, { source: 'table' });
    await tableMediaButtons.first().click({ timeout: 8000 }).catch((error) => {
      pushCheck('records:open-image-viewer', false, { source: 'table', reason: error.message });
    });
    openedViewer = await page
      .locator('.admin-image-viewer')
      .waitFor({ state: 'visible', timeout: 8000 })
      .then(() => true)
      .catch(() => false);
    if (!checks.some((item) => item.name === 'records:open-image-viewer')) {
      pushCheck('records:open-image-viewer', openedViewer, { source: 'table' });
    }
  } else {
    await clickFirst(page, page.getByRole('button', { name: /详情/ }), 'records:open-detail');
    await addPageResult(page, 'admin-records-detail-drawer');
    const drawerPreviewButtons = page.locator('.el-drawer .admin-content-page__asset-preview-button');
    mediaVisible = await drawerPreviewButtons.first().isVisible().catch(() => false);
    pushCheck('records:image-record-media-visible', mediaVisible, { source: 'detail-drawer' });
    if (mediaVisible) {
      await drawerPreviewButtons.first().click({ timeout: 8000 }).catch((error) => {
        pushCheck('records:open-image-viewer', false, { source: 'detail-drawer', reason: error.message });
      });
      openedViewer = await page
        .locator('.admin-image-viewer')
        .waitFor({ state: 'visible', timeout: 8000 })
        .then(() => true)
        .catch(() => false);
      if (!checks.some((item) => item.name === 'records:open-image-viewer')) {
        pushCheck('records:open-image-viewer', openedViewer, { source: 'detail-drawer' });
      }
    }
  }

  const viewerVisible = await page.locator('.admin-image-viewer').isVisible().catch(() => false);
  pushCheck('records:image-viewer-visible', openedViewer && viewerVisible);
  const viewerActionSummary = await verifyImageViewerActions(page);
  pushCheck('records:image-viewer-actions-visible', viewerVisible && viewerActionSummary.ok, {
    actions: summarizeViewerActionChecks(viewerActionSummary),
  });
  await page.keyboard.press('ArrowRight').catch(() => null);
  await page.keyboard.press('ArrowLeft').catch(() => null);
  await addPageResult(
    page,
    viewerVisible ? 'admin-records-image-viewer' : 'admin-records-image-viewer-missing',
    { viewerVisible },
  );
  await page.keyboard.press('Escape').catch(() => null);
}

async function exerciseAudit(page) {
  await gotoAndCapture(page, 'audit', 'admin-audit-initial');
  const detailCount = await page.getByRole('button', { name: /详情/ }).count().catch(() => 0);
  if (detailCount) {
    await clickFirst(page, page.getByRole('button', { name: /详情/ }), 'audit:open-detail');
    await addPageResult(page, 'admin-audit-detail-drawer');
    await page.keyboard.press('Escape').catch(() => null);
    await page.waitForTimeout(300);
  } else {
    pushCheck('audit:open-detail', true, { reason: 'no-audit-rows', skipped: true });
  }
  await fillFirst(page, page.locator('.admin-content-page__filters--audit input').first(), 'model', 'audit:search-action');
  await addPageResult(page, 'admin-audit-after-search');
}

async function exerciseSettings(page) {
  await gotoAndCapture(page, 'settings', 'admin-settings-initial');
  await clickFirst(page, page.getByRole('button', { name: /刷新/ }), 'settings:refresh');
  await clickFirst(page, page.getByRole('button', { name: /预览重复用户/ }), 'settings:preview-merge');
  await addPageResult(page, 'admin-settings-after-preview');
}

async function exerciseForbidden(page) {
  await gotoAndCapture(page, 'forbidden', 'admin-forbidden');
  await gotoAndCapture(page, 'forbidden?reason=system', 'admin-forbidden-system');
  await clickFirst(page, page.getByRole('button', { name: /返回仪表盘|返回/ }), 'forbidden:return-dashboard');
  await addPageResult(page, 'admin-forbidden-after-return');
}

async function exerciseReleaseCriticalRoutes(page) {
  for (const viewport of ADMIN_SMOKE_VIEWPORTS) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    pushCheck(`viewport:${viewport.name}`, true, { width: viewport.width, height: viewport.height });
    for (const route of ADMIN_SMOKE_ROUTES) {
      await gotoAndCapture(page, route, `${viewport.name}-admin-${route}`);
    }
  }
}

const browser = await chromium.launch({ headless: process.env.HEADLESS !== 'false' });
const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 1 });
const page = await context.newPage();

page.on('console', (message) => {
  if (message.type() === 'error') consoleErrors.push({ url: page.url(), text: message.text() });
});
page.on('response', (response) => {
  const status = response.status();
  if (status >= 500) failedResponses.push({ url: response.url(), status });
});

try {
  const health = await context.request.get(`${rootOrigin(API)}/api/health`).catch(() => null);
  pushCheck('api:health', Boolean(health?.ok?.()), { status: health?.status?.() || 0 });
  const loggedIn = await login(context);
  if (!loggedIn) {
    throw new Error('Admin smoke login failed.');
  }

  await exerciseReleaseCriticalRoutes(page);
  await page.setViewportSize({ width: ADMIN_SMOKE_VIEWPORTS[0].width, height: ADMIN_SMOKE_VIEWPORTS[0].height });
  await exerciseDashboard(page);
  await exerciseModels(page);
  await exercisePrompts(page);
  await exerciseUsers(page);
  await exerciseRecords(page);
  await exerciseAudit(page);
  await exerciseSettings(page);
  await exerciseForbidden(page);
} finally {
  await browser.close();
}

const nonAuthConsoleErrors = consoleErrors.filter((item) => !/401|favicon/i.test(item.text || ''));
const summary = buildAdminDeepSmokeSummary({
  front: FRONT,
  admin: ADMIN,
  api: API,
  outDir,
  results,
  checks,
  failedResponses,
  consoleErrors,
  nonAuthConsoleErrors,
});

fs.writeFileSync(path.join(outDir, 'summary.json'), JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 2));

if (summary.failedResponses.length || summary.nonAuthConsoleErrors.length || summary.failedChecks.length) {
  process.exitCode = 1;
}
}
