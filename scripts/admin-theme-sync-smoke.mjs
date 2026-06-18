import { chromium } from 'playwright';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

export const THEME_CASES = ['light', 'dark'];

export function normalizeThemeValue(value) {
  return value === 'dark' ? 'dark' : 'light';
}

export function safeName(value) {
  const raw = String(value);
  const ascii = raw.replace(/[^a-z0-9_-]+/gi, '-').replace(/^-+|-+$/g, '').toLowerCase();
  const digest = crypto.createHash('sha1').update(raw).digest('hex').slice(0, 10);
  return ascii || `theme-${digest}`;
}

export function summarizeThemeSmoke(summary) {
  const failedCheckCount = summary.checks?.filter((item) => !item.ok).length || 0;
  const failedResponseCount = summary.failedResponses?.length || 0;
  const consoleErrorCount = summary.nonAuthConsoleErrors?.length || 0;
  return {
    ok: failedCheckCount === 0 && failedResponseCount === 0 && consoleErrorCount === 0,
    failedCheckCount,
    failedResponseCount,
    consoleErrorCount,
  };
}

export function adminEntryUrl(value) {
  const url = new URL(value);
  if (url.pathname === '/admin') {
    url.pathname = '/admin/';
  }
  return url.toString().replace(/\/$/, url.pathname.endsWith('/admin/') ? '/' : '');
}

if (process.env.ADMIN_THEME_SYNC_UNIT_ONLY !== '1') {
const FRONT = process.env.FRONT_URL || 'http://127.0.0.1:5175';
const ADMIN = adminEntryUrl(process.env.ADMIN_URL || new URL('/admin/', FRONT).toString());
const SMOKE_EMAIL = process.env.SMOKE_EMAIL || '';
const SMOKE_PASSWORD = process.env.SMOKE_PASSWORD || '';
const outDir = path.resolve(
  'output/playwright/admin-theme-sync-smoke-' + new Date().toISOString().replace(/[:.]/g, '-'),
);

fs.mkdirSync(outDir, { recursive: true });

const results = [];
const checks = [];
const consoleErrors = [];
const failedResponses = [];

function rootOrigin(url) {
  return new URL(url).origin;
}

function pushCheck(name, ok, extra = {}) {
  checks.push({ name, ok: Boolean(ok), ...extra });
}

async function login(context) {
  const baseUrl = rootOrigin(FRONT);
  if (SMOKE_EMAIL && SMOKE_PASSWORD) {
    const response = await context.request.post(`${baseUrl}/api/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { identifier: SMOKE_EMAIL, password: SMOKE_PASSWORD },
    });
    const payload = await response.json().catch(() => null);
    pushCheck('auth:password-login', response.ok(), { status: response.status(), user: payload?.user?.email || '' });
    return response.ok();
  }

  const response = await context.request.post(`${baseUrl}/api/auth/dev-login`, {
    headers: { 'Content-Type': 'application/json' },
    data: {
      externalUserId: 'local-admin-theme-smoke',
      email: 'cage_ben@sina.com',
      nickname: 'Theme Smoke Admin',
    },
  });
  const payload = await response.json().catch(() => null);
  pushCheck('auth:dev-login', response.ok(), { status: response.status(), user: payload?.user?.email || '' });
  return response.ok();
}

async function shot(page, name) {
  const file = path.join(outDir, `${safeName(name)}.png`);
  await page.screenshot({ path: file, fullPage: true }).catch(() => null);
  return file;
}

async function setFrontSharedTheme(page, theme) {
  await page.goto(FRONT, { waitUntil: 'networkidle', timeout: 60000 }).catch(async () => {
    await page.waitForLoadState('domcontentloaded', { timeout: 15000 }).catch(() => null);
  });
  await page.evaluate((value) => {
    localStorage.setItem('genstudio-theme', value);
    document.documentElement.dataset.theme = value;
  }, theme);
  pushCheck(`front:set-shared-theme:${theme}`, true);
}

async function verifyAdminTheme(page, theme) {
  await page.goto(ADMIN, { waitUntil: 'networkidle', timeout: 60000 }).catch(async () => {
    await page.waitForLoadState('domcontentloaded', { timeout: 15000 }).catch(() => null);
  });
  await page.waitForTimeout(800);
  const state = await page.evaluate(() => ({
    datasetTheme: document.documentElement.dataset.theme || '',
    sharedTheme: localStorage.getItem('genstudio-theme') || '',
    legacyAdminTheme: localStorage.getItem('genstudio-admin-theme') || '',
    title: document.title,
    bodyText: document.body?.innerText?.slice(0, 280) || '',
  }));
  const screenshot = await shot(page, `admin-theme-${theme}`);
  results.push({ theme, url: page.url(), screenshot, ...state });
  pushCheck(`admin:dataset-theme:${theme}`, normalizeThemeValue(state.datasetTheme) === theme, state);
  pushCheck(`admin:shared-theme:${theme}`, normalizeThemeValue(state.sharedTheme) === theme, state);
  pushCheck(`admin:legacy-theme:${theme}`, normalizeThemeValue(state.legacyAdminTheme) === theme, state);
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
  if (!loggedIn) throw new Error('Admin theme smoke login failed.');

  const sameOrigin = rootOrigin(FRONT) === rootOrigin(ADMIN);
  pushCheck('theme:same-origin', sameOrigin, { frontOrigin: rootOrigin(FRONT), adminOrigin: rootOrigin(ADMIN) });

  for (const theme of THEME_CASES) {
    await setFrontSharedTheme(page, theme);
    await verifyAdminTheme(page, theme);
  }
} finally {
  await browser.close();
}

const nonAuthConsoleErrors = consoleErrors.filter((item) => !/401|favicon/i.test(item.text || ''));
const summary = {
  front: FRONT,
  admin: ADMIN,
  outDir,
  results,
  checks,
  failedChecks: checks.filter((item) => !item.ok),
  failedResponses,
  consoleErrors,
  nonAuthConsoleErrors,
};

fs.writeFileSync(path.join(outDir, 'summary.json'), JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 2));

if (!summarizeThemeSmoke(summary).ok) {
  process.exitCode = 1;
}
}
