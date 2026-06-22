import { chromium } from 'playwright';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

export const FRONT_SMOKE_ROUTES = [
  { route: '/', name: 'front-home' },
  { route: '/#/text', name: 'front-text' },
  { route: '/#/images', name: 'front-images' },
  { route: '/#/videos', name: 'front-videos' },
  { route: '/#/settings', name: 'front-settings' },
  { route: '/#/profile', name: 'front-profile' },
];

export const FRONT_SMOKE_VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 1000 },
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
  return raw ? `u-${digest}` : 'page';
}

export function hasMojibake(text) {
  return /(?:\u951f|\ufffd|\?\?\?)/.test(text || '');
}

export function summarizeSmokeFailures(summary) {
  const failedCheckCount = summary.failedChecks?.length || 0;
  const failedResponseCount = summary.failedResponses?.length || 0;
  const consoleErrorCount = summary.nonAuthConsoleErrors?.length || 0;
  return {
    ok: failedCheckCount === 0 && failedResponseCount === 0 && consoleErrorCount === 0,
    failedCheckCount,
    failedResponseCount,
    consoleErrorCount,
  };
}

if (process.env.FRONTED_SMOKE_UNIT_ONLY !== '1') {
const FRONT = process.env.FRONT_URL || 'http://127.0.0.1:5175';
const SMOKE_EMAIL = process.env.SMOKE_EMAIL || '';
const SMOKE_PASSWORD = process.env.SMOKE_PASSWORD || '';
const outDir = path.resolve(
  'output/playwright/fronted-online-smoke-' + new Date().toISOString().replace(/[:.]/g, '-'),
);

fs.mkdirSync(outDir, { recursive: true });

const results = [];
const checks = [];
const failedResponses = [];
const consoleErrors = [];

function rootOrigin(url) {
  return new URL(url).origin;
}

function pushCheck(name, ok, extra = {}) {
  checks.push({ name, ok: Boolean(ok), ...extra });
}

async function shot(page, name) {
  const file = path.join(outDir, `${safeName(name)}.png`);
  await page.screenshot({ path: file, fullPage: true }).catch(() => null);
  return file;
}

async function capture(page, route, name) {
  await page.goto(`${FRONT}${route}`, { waitUntil: SMOKE_WAIT_UNTIL, timeout: 60000 }).catch(async () => {
    await page.waitForLoadState('domcontentloaded', { timeout: 15000 }).catch(() => null);
  });
  await page.waitForTimeout(1200);
  const text = await page.locator('body').innerText({ timeout: 10000 }).catch(() => '');
  const screenshot = await shot(page, name);
  const result = {
    name,
    url: page.url(),
    title: await page.title().catch(() => ''),
    screenshot,
    hasVisibleMojibake: hasMojibake(text),
    textSample: text.slice(0, 500),
  };
  results.push(result);
  pushCheck(`${name}:visible-text`, text.trim().length > 0, { length: text.trim().length });
  pushCheck(`${name}:no-mojibake`, !result.hasVisibleMojibake);
  return result;
}

async function clickVisible(page, locator, name, optional = false) {
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
  try {
    await first.click({ timeout: 8000 });
    await page.waitForTimeout(700);
    pushCheck(name, true);
    return true;
  } catch (error) {
    pushCheck(name, optional, { reason: String(error?.message || error), skipped: optional });
    return false;
  }
}

async function assertVisible(page, locator, name, optional = false) {
  await locator.first().waitFor({ state: 'visible', timeout: 5000 }).catch(() => null);
  const count = await locator.count().catch(() => 0);
  if (!count) {
    pushCheck(name, optional, { reason: 'not-found', skipped: optional });
    return false;
  }
  const first = locator.first();
  const visible = await first.isVisible().catch(() => false);
  const enabled = visible ? await first.isEnabled().catch(() => false) : false;
  pushCheck(name, visible || optional, { count, enabled });
  return visible;
}

function promptAiButton(page) {
  return page.locator('.composer-card button, .composer-card .prompt-ai-button', { hasText: /^AI$/ }).last();
}

async function login(context) {
  if (SMOKE_EMAIL && SMOKE_PASSWORD) {
    const response = await context.request.post(`${rootOrigin(FRONT)}/api/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { identifier: SMOKE_EMAIL, password: SMOKE_PASSWORD },
    });
    const payload = await response.json().catch(() => null);
    pushCheck('auth:password-login', response.ok(), { status: response.status(), user: payload?.user?.email || '' });
    return response.ok();
  }

  const response = await context.request.post(`${rootOrigin(FRONT)}/api/auth/dev-login`, {
    headers: { 'Content-Type': 'application/json' },
    data: {
      externalUserId: 'local-fronted-smoke',
      email: 'cage_ben@sina.com',
      nickname: 'Fronted Smoke Admin',
    },
  });
  const payload = await response.json().catch(() => null);
  pushCheck('auth:dev-login', response.ok(), { status: response.status(), user: payload?.user?.email || '' });
  return response.ok();
}

async function exerciseFrontWorkspace(page, viewportName = 'desktop') {
  await capture(page, '/', `${viewportName}-front-home`);
  await clickVisible(page, page.getByRole('button', { name: /后台|管理/ }), 'front:admin-button', true);

  await capture(page, '/#/text', `${viewportName}-front-text`);
  await assertVisible(page, promptAiButton(page), 'front:text-prompt-polish-button-visible');
  await clickVisible(page, page.getByRole('button', { name: /历史|记录/ }), 'front:text-history-button', true);
  await shot(page, `${viewportName}-front-text-history-popover`);
  await page.keyboard.press('Escape').catch(() => null);
  await page.keyboard.press('Escape').catch(() => null);

  await capture(page, '/#/images', `${viewportName}-front-images`);
  await clickVisible(page, page.getByRole('button', { name: /上传|参考|图片/ }), 'front:image-upload-entry-visible', true);
  await page.keyboard.press('Escape').catch(() => null);

  await capture(page, '/#/videos', `${viewportName}-front-videos`);
  await clickVisible(page, page.getByRole('button', { name: /上传|参考|图片|首帧|尾帧/ }), 'front:video-upload-entry-visible', true);
  await page.keyboard.press('Escape').catch(() => null);

  await capture(page, '/#/settings', `${viewportName}-front-settings`);
  await clickVisible(page, page.getByRole('button', { name: /添加模型/ }), 'front:settings-add-model', true);
  await shot(page, `${viewportName}-front-settings-add-model-dialog`);
  await page.keyboard.press('Escape').catch(() => null);
  await assertVisible(page, page.getByRole('button', { name: /批量测试/ }), 'front:settings-batch-test-button-visible');
  await page.keyboard.press('Escape').catch(() => null);

  await capture(page, '/#/profile', `${viewportName}-front-profile`);
}

const browser = await chromium.launch({ headless: process.env.HEADLESS !== 'false' });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
const page = await context.newPage();

page.on('console', (message) => {
  if (message.type() === 'error') consoleErrors.push({ url: page.url(), text: message.text() });
});
page.on('response', (response) => {
  const status = response.status();
  if (status >= 500) failedResponses.push({ url: response.url(), status });
});

try {
  const health = await context.request.get(`${rootOrigin(FRONT)}/api/health`).catch(() => null);
  pushCheck('api:health', Boolean(health?.ok?.()), { status: health?.status?.() || 0 });
  const loggedIn = await login(context);
  if (!loggedIn) {
    throw new Error('Fronted smoke login failed.');
  }

  for (const viewport of FRONT_SMOKE_VIEWPORTS) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    pushCheck(`viewport:${viewport.name}`, true, { width: viewport.width, height: viewport.height });
    await exerciseFrontWorkspace(page, viewport.name);
  }
} finally {
  await browser.close();
}

const failedChecks = checks.filter((item) => !item.ok);
const nonAuthConsoleErrors = consoleErrors.filter((item) => !/401|favicon/i.test(item.text || ''));
const summary = {
  front: FRONT,
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

const failureSummary = summarizeSmokeFailures(summary);
if (!failureSummary.ok) {
  process.exitCode = 1;
}
}
