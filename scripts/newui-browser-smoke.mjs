import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { deflateSync } from 'node:zlib';

import { chromium } from 'playwright';

export const CREATOR_ROUTES = [
  { name: 'text', hash: '#/text', testId: 'text-view' },
  { name: 'images', hash: '#/images', testId: 'images-view' },
  { name: 'videos', hash: '#/videos', testId: 'videos-view' },
  { name: 'settings', hash: '#/settings', testId: 'settings-view' },
  { name: 'profile', hash: '#/profile', testId: 'profile-view' },
];

export const ADMIN_ROUTES = [
  { name: 'dashboard', path: 'dashboard', testId: 'admin-dashboard-view' },
  { name: 'models', path: 'models', testId: 'admin-models-view' },
  { name: 'prompts', path: 'prompts', testId: 'admin-prompts-view' },
  { name: 'records', path: 'records', testId: 'admin-records-view' },
  { name: 'users', path: 'users', testId: 'admin-users-view' },
  { name: 'settings', path: 'settings', testId: 'admin-settings-view' },
  { name: 'audit', path: 'audit', testId: 'admin-audit-view' },
  { name: 'forbidden', path: 'forbidden', testId: 'admin-forbidden-view' },
];

export const NEWUI_VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'tablet', width: 1024, height: 768 },
  { name: 'mobile', width: 390, height: 844 },
];

export const NEWUI_THEMES = ['light', 'dark'];
export const REFERENCE_UPLOAD_COUNT = 10;
export const SMOKE_WAIT_UNTIL = 'load';
export const THUMBNAIL_WAIT_TIMEOUT_MS = 15000;
export const VIEW_WAIT_ATTEMPTS = 2;
export const SMOKE_MODEL_FIXTURES = [
  {
    name: 'NewUI Text Smoke',
    vendor: 'Smoke',
    capability: 'text',
    adapter: 'text-chat',
    baseUrl: 'https://smoke.invalid',
    apiKey: 'smoke-not-used',
    primaryModelName: 'gpt-smoke',
  },
  {
    name: 'NewUI Image Smoke',
    vendor: 'Smoke',
    capability: 'image',
    adapter: 'image-openai',
    baseUrl: 'https://smoke.invalid',
    apiKey: 'smoke-not-used',
    primaryModelName: 'gpt-image-smoke',
  },
  {
    name: 'Seedance 2.0',
    vendor: 'Smoke',
    capability: 'video',
    adapter: 'video-seedance',
    baseUrl: 'https://smoke.invalid',
    apiKey: 'smoke-not-used',
    primaryModelName: 'doubao-seedance-2-0-260128',
  },
];

const PNG_SIGNATURE = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function pngChunk(type, data = Buffer.alloc(0)) {
  const typeBuffer = Buffer.from(type, 'ascii');
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const checksum = Buffer.alloc(4);
  checksum.writeUInt32BE(crc32(Buffer.concat([typeBuffer, data])));
  return Buffer.concat([length, typeBuffer, data, checksum]);
}

function createFixturePng(index) {
  const width = 32;
  const height = 32;
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header.set([8, 6, 0, 0, 0], 8);

  const pixels = Buffer.alloc((width * 4 + 1) * height);
  for (let y = 0; y < height; y += 1) {
    const row = y * (width * 4 + 1);
    pixels[row] = 0;
    for (let x = 0; x < width; x += 1) {
      const offset = row + 1 + x * 4;
      pixels[offset] = (index * 37 + x * 4) % 256;
      pixels[offset + 1] = (80 + index * 19 + y * 3) % 256;
      pixels[offset + 2] = (210 - index * 11 + x + y) % 256;
      pixels[offset + 3] = 255;
    }
  }

  return Buffer.concat([
    PNG_SIGNATURE,
    pngChunk('IHDR', header),
    pngChunk('IDAT', deflateSync(pixels)),
    pngChunk('IEND'),
  ]);
}

function safeSegment(value) {
  const raw = String(value || '');
  const ascii = raw.replace(/[^a-z0-9_-]+/gi, '-').replace(/^-+|-+$/g, '').toLowerCase();
  if (ascii) return ascii;
  const digest = crypto.createHash('sha1').update(raw).digest('hex').slice(0, 10);
  return raw ? `u-${digest}` : 'page';
}

export function smokeScreenshotName({ surface, route, theme, viewport }) {
  return [surface, route, theme, viewport].map(safeSegment).join('-') + '.png';
}

function isUploadPresignUrl(url) {
  return /\/api\/proxy\/upload\/presign(?:[?#]|$)/i.test(url || '');
}

export function isUnexpectedConsoleMessage(message, options = {}) {
  if (message?.type !== 'error') return false;
  const text = message?.text || '';
  const sourceUrl = message?.sourceUrl || '';
  const isFaviconFailure = /favicon\.ico(?:[?#].*)?$/i.test(sourceUrl)
    || /favicon\.ico[^\n]*404|failed to load resource[^\n]*favicon/i.test(text);
  const isExpectedLocalUploadFallback = options.allowLocalUploadFallback
    && isUploadPresignUrl(sourceUrl)
    && /\b5\d\d\b/.test(text);
  const isExpectedLocalDevServerNoise = options.allowLocalDevServerNoise
    && /net::ERR_NO_BUFFER_SPACE/i.test(text)
    && /\/node_modules\/\.vite\/deps\//i.test(sourceUrl);
  return !isFaviconFailure && !isExpectedLocalUploadFallback && !isExpectedLocalDevServerNoise;
}

export function isUnexpectedFailedResponse(response, options = {}) {
  if (Number(response?.status || 0) < 500) return false;
  return !(options.allowLocalUploadFallback && isUploadPresignUrl(response?.url || ''));
}

export function hasHorizontalOverflow(metrics, tolerance = 1) {
  return Number(metrics?.scrollWidth || 0) - Number(metrics?.clientWidth || 0) > tolerance;
}

export function createReferenceFixturePayloads(count = REFERENCE_UPLOAD_COUNT) {
  if (!Number.isInteger(count) || count < 1 || count > REFERENCE_UPLOAD_COUNT) {
    throw new Error('参考图最多 10 张');
  }
  return Array.from({ length: count }, (_, index) => ({
    name: `reference-${String(index + 1).padStart(2, '0')}.png`,
    mimeType: 'image/png',
    buffer: createFixturePng(index + 1),
  }));
}

export function referencePromptForIndex(index) {
  return `使用 @${index} 作为主要构图参考`;
}

export function isRenderedThumbnail(image) {
  return Boolean(
    image?.complete
    && image?.src
    && Number(image?.naturalWidth || 0) > 0
    && Number(image?.naturalHeight || 0) > 0,
  );
}

export function browserLaunchCandidates(headless) {
  return [
    { headless },
    { headless, channel: 'chrome' },
    { headless, channel: 'msedge' },
  ];
}

async function launchBrowser(headless) {
  let lastError;
  for (const options of browserLaunchCandidates(headless)) {
    try {
      return await chromium.launch(options);
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

function timestamp() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

function originOf(url) {
  return new URL(url).origin;
}

function adminRouteUrl(base, route, theme) {
  const root = String(base).replace(/\/+$/, '');
  return `${root}/${route}?theme=${theme}`;
}

function createCollector() {
  const checks = [];
  return {
    checks,
    add(name, ok, details = {}) {
      checks.push({ name, ok: Boolean(ok), ...details });
    },
  };
}

async function waitForView(page, testId, options = {}) {
  const view = page.locator(`[data-testid="${testId}"]`);
  let lastError;

  for (let attempt = 1; attempt <= VIEW_WAIT_ATTEMPTS; attempt += 1) {
    try {
      await view.waitFor({ state: 'visible', timeout: 20000 });
      await page.waitForTimeout(250);
      return view;
    } catch (error) {
      lastError = error;
      if (attempt < VIEW_WAIT_ATTEMPTS) {
        await page.reload({ waitUntil: SMOKE_WAIT_UNTIL, timeout: 30000 });
      }
    }
  }

  const url = page.url();
  const body = (await page.locator('body').innerText().catch(() => '')).slice(0, 2000);
  let screenshot = '';
  if (options.diagnosticScreenshot) {
    screenshot = options.diagnosticScreenshot;
    await page.screenshot({ path: screenshot, fullPage: true }).catch(() => {
      screenshot = '';
    });
  }
  throw new Error(
    `View ${testId} was not visible after ${VIEW_WAIT_ATTEMPTS} attempts. URL: ${url}. Screenshot: ${screenshot || 'unavailable'}. Body: ${body || '<empty>'}`,
    { cause: lastError },
  );
}

async function documentMetrics(page) {
  return page.evaluate(() => ({
    scrollWidth: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
    clientWidth: document.documentElement.clientWidth,
  }));
}

async function criticalRegionsOverlap(page, surface) {
  return page.evaluate((kind) => {
    const selectors = kind === 'creator'
      ? ['.workspace-topbar', '.studio-panel, .settings-page, .profile-page, .auth-page']
      : ['.admin-topbar', '.admin-content'];
    const nodes = selectors.map((selector) => {
      const element = Array.from(document.querySelectorAll(selector)).find((candidate) => {
        const style = getComputedStyle(candidate);
        const rect = candidate.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
      });
      return element?.getBoundingClientRect() || null;
    });
    if (!nodes[0] || !nodes[1]) return false;
    const [first, second] = nodes;
    const horizontal = first.left < second.right - 1 && first.right > second.left + 1;
    const vertical = first.top < second.bottom - 1 && first.bottom > second.top + 1;
    return horizontal && vertical;
  }, surface);
}

async function thumbnailResults(page) {
  return page.locator('.reference-thumb img').evaluateAll((images) => images.map((image) => {
    let hasOpaquePixel = false;
    try {
      const canvas = document.createElement('canvas');
      canvas.width = 8;
      canvas.height = 8;
      const context = canvas.getContext('2d', { willReadFrequently: true });
      context?.drawImage(image, 0, 0, 8, 8);
      const pixels = context?.getImageData(0, 0, 8, 8).data || [];
      for (let offset = 3; offset < pixels.length; offset += 4) {
        if (pixels[offset] > 0) {
          hasOpaquePixel = true;
          break;
        }
      }
    } catch {
      hasOpaquePixel = true;
    }
    return {
      complete: image.complete,
      naturalWidth: image.naturalWidth,
      naturalHeight: image.naturalHeight,
      src: image.currentSrc || image.src,
      hasOpaquePixel,
    };
  }));
}

async function login(context, apiUrl, collector) {
  const response = await context.request.post(`${originOf(apiUrl)}/api/auth/dev-login`, {
    headers: { 'Content-Type': 'application/json' },
    data: {
      externalUserId: 'newui-browser-smoke-admin',
      email: 'cage_ben@sina.com',
      nickname: 'NewUI Smoke Admin',
    },
  });
  collector.add('auth:dev-login', response.ok(), { status: response.status() });
  return response.ok();
}

async function ensureSmokeModels(context, apiUrl, collector) {
  const root = originOf(apiUrl);
  const csrfResponse = await context.request.get(`${root}/api/auth/csrf`);
  const csrfPayload = await csrfResponse.json().catch(() => null);
  const csrfToken = csrfPayload?.csrfToken || '';
  collector.add('setup:csrf', csrfResponse.ok() && Boolean(csrfToken), { status: csrfResponse.status() });
  if (!csrfResponse.ok() || !csrfToken) throw new Error('Unable to obtain smoke CSRF token');

  const listResponse = await context.request.get(`${root}/api/models`);
  const listPayload = await listResponse.json().catch(() => null);
  const existing = Array.isArray(listPayload?.models) ? listPayload.models : [];
  collector.add('setup:list-models', listResponse.ok(), { status: listResponse.status(), count: existing.length });
  if (!listResponse.ok()) throw new Error('Unable to list smoke models');

  for (const model of SMOKE_MODEL_FIXTURES) {
    if (existing.some((item) => item.name === model.name && item.capability === model.capability)) {
      collector.add(`setup:model:${model.capability}`, true, { reused: true });
      continue;
    }
    const response = await context.request.post(`${root}/api/models`, {
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
      data: model,
    });
    collector.add(`setup:model:${model.capability}`, response.ok(), { status: response.status(), reused: false });
    if (!response.ok()) {
      const message = await response.text().catch(() => '');
      throw new Error(`Unable to create ${model.capability} smoke model (${response.status()}): ${message.slice(0, 200)}`);
    }
  }
}

async function prepareSmokeModels(browser, apiUrl, collector) {
  const context = await browser.newContext();
  try {
    if (!await login(context, apiUrl, collector)) throw new Error('Smoke setup login failed');
    await ensureSmokeModels(context, apiUrl, collector);
  } finally {
    await context.close();
  }
}

function observePage(page, browserEvents) {
  page.on('console', (message) => {
    const entry = {
      type: message.type(),
      text: message.text(),
      sourceUrl: message.location()?.url || '',
      url: page.url(),
    };
    if (isUnexpectedConsoleMessage(entry, browserEvents)) browserEvents.consoleErrors.push(entry);
  });
  page.on('pageerror', (error) => {
    browserEvents.pageErrors.push({ text: error.message, url: page.url() });
  });
  page.on('response', (response) => {
    const entry = { status: response.status(), url: response.url() };
    if (isUnexpectedFailedResponse(entry, browserEvents)) browserEvents.failedResponses.push(entry);
  });
}

async function captureRoute({ page, surface, route, theme, viewport, outDir, collector }) {
  const screenshot = path.join(outDir, smokeScreenshotName({
    surface,
    route: route.name,
    theme,
    viewport: viewport.name,
  }));
  const view = await waitForView(page, route.testId, { diagnosticScreenshot: screenshot });
  const text = await view.innerText().catch(() => '');
  const metrics = await documentMetrics(page);
  const overlap = await criticalRegionsOverlap(page, surface);
  const appliedTheme = await page.evaluate((kind) => (
    kind === 'creator'
      ? document.querySelector('.shell')?.getAttribute('data-theme')
      : document.documentElement.dataset.theme
  ), surface);
  const headingId = await view.getAttribute('aria-labelledby');
  const headingVisible = headingId
    ? await page.locator(`#${headingId}`).first().count().catch(() => 0)
    : 0;

  collector.add(`${surface}:${route.name}:${theme}:${viewport.name}:text`, text.trim().length > 0);
  collector.add(`${surface}:${route.name}:${theme}:${viewport.name}:theme`, appliedTheme === theme, { appliedTheme });
  collector.add(`${surface}:${route.name}:${theme}:${viewport.name}:heading`, headingVisible === 1, { headingId });
  collector.add(`${surface}:${route.name}:${theme}:${viewport.name}:overflow`, !hasHorizontalOverflow(metrics), metrics);
  collector.add(`${surface}:${route.name}:${theme}:${viewport.name}:overlap`, !overlap);

  await page.screenshot({ path: screenshot, fullPage: true });
  return { surface, route: route.name, theme, viewport: viewport.name, screenshot, metrics };
}

async function runRouteMatrix({ browser, frontUrl, adminUrl, apiUrl, outDir, collector, browserEvents }) {
  const captures = [];
  for (const viewport of NEWUI_VIEWPORTS) {
    for (const theme of NEWUI_THEMES) {
      const context = await browser.newContext({
        viewport: { width: viewport.width, height: viewport.height },
        deviceScaleFactor: 1,
      });
      await context.addInitScript((nextTheme) => {
        localStorage.setItem('genstudio-theme', nextTheme);
        localStorage.setItem('genstudio-admin-theme', nextTheme);
      }, theme);
      const page = await context.newPage();
      observePage(page, browserEvents);
      try {
        if (!await login(context, apiUrl, collector)) throw new Error('NewUI smoke login failed');
        for (const route of CREATOR_ROUTES) {
          await page.goto(`${frontUrl.replace(/\/+$/, '')}/${route.hash}`, {
            waitUntil: SMOKE_WAIT_UNTIL,
            timeout: 30000,
          });
          captures.push(await captureRoute({ page, surface: 'creator', route, theme, viewport, outDir, collector }));
        }
        for (const route of ADMIN_ROUTES) {
          await page.goto(adminRouteUrl(adminUrl, route.path, theme), {
            waitUntil: SMOKE_WAIT_UNTIL,
            timeout: 30000,
          });
          captures.push(await captureRoute({ page, surface: 'admin', route, theme, viewport, outDir, collector }));
        }
      } finally {
        await context.close();
      }
    }
  }
  return captures;
}

async function uploadReferences(page, selector, collector, prefix) {
  const fixtures = createReferenceFixturePayloads();
  const input = page.locator(selector).first();
  await input.waitFor({ state: 'attached', timeout: 10000 });
  await input.setInputFiles(fixtures);
  await page.waitForFunction(
    (count) => document.querySelectorAll('.reference-thumb').length === count,
    REFERENCE_UPLOAD_COUNT,
    { timeout: 90000 },
  );
  await page.waitForFunction(
    (count) => {
      const images = Array.from(document.querySelectorAll('.reference-thumb img'));
      return images.length === count && images.every((image) => (
        image.complete && image.naturalWidth > 0 && image.naturalHeight > 0
      ));
    },
    REFERENCE_UPLOAD_COUNT,
    { timeout: THUMBNAIL_WAIT_TIMEOUT_MS },
  );

  const badges = await page.locator('.reference-index-badge').allTextContents();
  const thumbnails = await thumbnailResults(page);
  collector.add(`${prefix}:ten-references`, badges.length === 10 && badges[0]?.trim() === '1' && badges[9]?.trim() === '10', { badges });
  collector.add(
    `${prefix}:thumbnails-rendered`,
    thumbnails.length === 10 && thumbnails.every((image) => isRenderedThumbnail(image) && image.hasOpaquePixel),
    { thumbnails },
  );
}

async function exerciseMentionRewrite({ page, capability, collector, outDir }) {
  const prompt = page.locator(`textarea.composer-input`).first();
  await prompt.fill('@10');
  const option = page.getByRole('option', { name: '引用图片 10' });
  await option.waitFor({ state: 'visible', timeout: 10000 });
  await option.click();
  collector.add(`${capability}:mention-10-inserted`, (await prompt.inputValue()).includes('@10'));

  await prompt.fill('使用 @2 和 @10 作为构图参考');
  await page.locator('.reference-thumb').nth(1).locator('.reference-remove-button').click();
  await page.waitForFunction(() => document.querySelectorAll('.reference-thumb').length === 9);
  const rewritten = await prompt.inputValue();
  collector.add(
    `${capability}:mention-rewrite-after-remove`,
    rewritten.includes('@9') && !rewritten.includes('@10') && !rewritten.includes('@2'),
    { rewritten },
  );

  let generationRequests = 0;
  const endpoint = capability === 'image' ? '/api/proxy/image' : '/api/proxy/video/create';
  const countRequest = (request) => {
    if (request.url().includes(endpoint) && request.method() === 'POST') generationRequests += 1;
  };
  page.on('request', countRequest);
  await prompt.fill('引用已删除的 @10');
  const primaryAction = page.locator(`[data-testid="${capability === 'image' ? 'images' : 'videos'}-primary-action"]`);
  const disabled = await primaryAction.isDisabled();
  await primaryAction.dispatchEvent('click').catch(() => null);
  await page.waitForTimeout(200);
  page.off('request', countRequest);
  collector.add(`${capability}:invalid-reference-blocked`, disabled && generationRequests === 0, {
    disabled,
    generationRequests,
  });

  const screenshot = path.join(outDir, `creator-${capability}-references-light-desktop.png`);
  await page.screenshot({ path: screenshot, fullPage: true });
}

async function exerciseReferenceWorkflows({ browser, frontUrl, apiUrl, outDir, collector, browserEvents }) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  await context.addInitScript(() => localStorage.setItem('genstudio-theme', 'light'));
  const page = await context.newPage();
  observePage(page, browserEvents);
  try {
    if (!await login(context, apiUrl, collector)) throw new Error('Reference smoke login failed');

    await page.goto(`${frontUrl.replace(/\/+$/, '')}/#/images`, { waitUntil: SMOKE_WAIT_UNTIL, timeout: 30000 });
    await waitForView(page, 'images-view', {
      diagnosticScreenshot: path.join(outDir, 'creator-images-workflow-wait-failed.png'),
    });
    await uploadReferences(page, 'input[type="file"][multiple]', collector, 'image');
    await exerciseMentionRewrite({ page, capability: 'image', collector, outDir });

    await page.goto(`${frontUrl.replace(/\/+$/, '')}/#/videos`, { waitUntil: SMOKE_WAIT_UNTIL, timeout: 30000 });
    await waitForView(page, 'videos-view', {
      diagnosticScreenshot: path.join(outDir, 'creator-videos-workflow-wait-failed.png'),
    });
    const seedanceModel = page.locator('.sidebar-model-item', { hasText: 'Seedance 2.0' }).first();
    await seedanceModel.click({ timeout: 10000 });
    const modeButton = page.locator('.composer-pill', { hasText: /文生视频|全能参考|首帧|首尾帧/ }).first();
    await modeButton.click({ timeout: 10000 });
    await page.locator('.composer-menu-option', { hasText: '全能参考' }).click({ timeout: 10000 });
    await uploadReferences(page, 'input[type="file"][multiple]', collector, 'video');
    await exerciseMentionRewrite({ page, capability: 'video', collector, outDir });
  } finally {
    await context.close();
  }
}

export async function runNewuiBrowserSmoke(options = {}) {
  const frontUrl = options.frontUrl || process.env.FRONT_URL || 'http://127.0.0.1:5175';
  const adminUrl = options.adminUrl || process.env.ADMIN_URL || 'http://127.0.0.1:5174/admin';
  const apiUrl = options.apiUrl || process.env.API_URL || 'http://127.0.0.1:8000';
  const outDir = path.resolve(options.outDir || process.env.NEWUI_SMOKE_OUT_DIR || `output/newui-smoke/${timestamp()}`);
  fs.mkdirSync(outDir, { recursive: true });

  const collector = createCollector();
  const frontHostname = new URL(frontUrl).hostname;
  const allowLocalUploadFallback = options.allowLocalUploadFallback
    ?? ['127.0.0.1', 'localhost', '::1'].includes(frontHostname);
  const browserEvents = {
    consoleErrors: [],
    pageErrors: [],
    failedResponses: [],
    allowLocalUploadFallback,
    allowLocalDevServerNoise: allowLocalUploadFallback,
  };
  const browser = await launchBrowser(process.env.HEADLESS !== 'false');
  let captures = [];
  try {
    await prepareSmokeModels(browser, apiUrl, collector);
    captures = await runRouteMatrix({ browser, frontUrl, adminUrl, apiUrl, outDir, collector, browserEvents });
    await exerciseReferenceWorkflows({ browser, frontUrl, apiUrl, outDir, collector, browserEvents });
  } finally {
    await browser.close();
  }

  collector.add('browser:no-console-errors', browserEvents.consoleErrors.length === 0, {
    errors: browserEvents.consoleErrors,
  });
  collector.add('browser:no-page-errors', browserEvents.pageErrors.length === 0, {
    errors: browserEvents.pageErrors,
  });
  collector.add('browser:no-5xx-responses', browserEvents.failedResponses.length === 0, {
    responses: browserEvents.failedResponses,
  });

  const failedChecks = collector.checks.filter((check) => !check.ok);
  const summary = {
    ok: failedChecks.length === 0,
    frontUrl,
    adminUrl,
    apiUrl,
    outDir,
    captures,
    checks: collector.checks,
    failedChecks,
    ...browserEvents,
  };
  fs.writeFileSync(path.join(outDir, 'summary.json'), JSON.stringify(summary, null, 2));
  return summary;
}

if (process.env.NEWUI_SMOKE_UNIT_ONLY !== '1') {
  const summary = await runNewuiBrowserSmoke();
  console.log(JSON.stringify(summary, null, 2));
  if (!summary.ok) process.exitCode = 1;
}
