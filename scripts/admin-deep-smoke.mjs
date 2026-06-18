import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

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

function safeName(value) {
  return String(value).replace(/[^a-z0-9_-]+/gi, '-').replace(/^-|-$/g, '').toLowerCase();
}

function rootOrigin(url) {
  return new URL(url).origin;
}

function hasMojibake(text) {
  return /(?:\u951f|\ufffd|\?\?\?)/.test(text || '');
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
  const url = route.startsWith('http') ? route : `${ADMIN}/${route.replace(/^\/+/, '')}`;
  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 }).catch(async () => {
    await page.waitForLoadState('domcontentloaded', { timeout: 15000 }).catch(() => null);
  });
  await page.waitForTimeout(700);
  return addPageResult(page, name);
}

async function clickFirst(page, locator, name, options = {}) {
  const { optional = false, ...clickOptions } = options;
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
  await first.click({ timeout: 8000, ...clickOptions }).catch((error) => {
    pushCheck(name, false, { reason: error.message });
  });
  await page.waitForTimeout(500);
  const wasRecorded = checks.some((item) => item.name === name);
  if (!wasRecorded) pushCheck(name, true);
  return true;
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
  const tabNames = ['文案记录', '生图记录', '视频记录'];
  for (const tabName of tabNames) {
    await clickFirst(page, page.getByRole('tab', { name: tabName }), `records:tab:${tabName}`);
    await page.waitForTimeout(800);
    await addPageResult(page, `admin-records-${safeName(tabName)}`);
  }
  await clickFirst(page, page.getByRole('switch').first(), 'records:first-switch', { optional: true });
  await clickFirst(page, page.getByRole('button', { name: /详情/ }), 'records:open-detail');
  await addPageResult(page, 'admin-records-detail-drawer');
  const openedViewer = await clickFirst(
    page,
    page.locator('.admin-content-page__record-media-strip button, .admin-content-page__asset-preview-button'),
    'records:open-image-viewer',
    { optional: true },
  );
  if (openedViewer) {
    await addPageResult(page, 'admin-records-image-viewer');
    await page.keyboard.press('ArrowRight').catch(() => null);
    await page.keyboard.press('ArrowLeft').catch(() => null);
    await page.keyboard.press('Escape').catch(() => null);
  }
}

async function exerciseAudit(page) {
  await gotoAndCapture(page, 'audit', 'admin-audit-initial');
  await fillFirst(page, page.locator('.admin-content-page__filters--audit input').first(), 'model', 'audit:search-action');
  await addPageResult(page, 'admin-audit-after-search');
  await clickFirst(page, page.getByRole('button', { name: /详情/ }), 'audit:open-detail');
  await addPageResult(page, 'admin-audit-detail-drawer');
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
const failedChecks = checks.filter((item) => !item.ok);
const summary = {
  front: FRONT,
  admin: ADMIN,
  api: API,
  outDir,
  results,
  checks,
  failedChecks,
  failedResponses,
  consoleErrors,
  nonAuthConsoleErrors,
};

fs.writeFileSync(path.join(outDir, 'summary.json'), JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 2));

if (failedResponses.length || nonAuthConsoleErrors.length || failedChecks.length) {
  process.exitCode = 1;
}
