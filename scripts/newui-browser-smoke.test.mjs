import assert from 'node:assert/strict';
import { test } from 'node:test';

process.env.NEWUI_SMOKE_UNIT_ONLY = '1';
const smoke = await import('./newui-browser-smoke.mjs');

test('newui route matrices cover every creator and admin surface', () => {
  assert.deepEqual(
    smoke.CREATOR_ROUTES.map((item) => [item.name, item.testId]),
    [
      ['text', 'text-view'],
      ['images', 'images-view'],
      ['videos', 'videos-view'],
      ['settings', 'settings-view'],
      ['profile', 'profile-view'],
    ],
  );
  assert.deepEqual(
    smoke.ADMIN_ROUTES.map((item) => [item.name, item.testId]),
    [
      ['dashboard', 'admin-dashboard-view'],
      ['models', 'admin-models-view'],
      ['prompts', 'admin-prompts-view'],
      ['records', 'admin-records-view'],
      ['users', 'admin-users-view'],
      ['settings', 'admin-settings-view'],
      ['audit', 'admin-audit-view'],
      ['forbidden', 'admin-forbidden-view'],
    ],
  );
});

test('newui smoke covers desktop, tablet, mobile, light, and dark modes', () => {
  assert.deepEqual(smoke.NEWUI_VIEWPORTS, [
    { name: 'desktop', width: 1440, height: 900 },
    { name: 'tablet', width: 1024, height: 768 },
    { name: 'mobile', width: 390, height: 844 },
  ]);
  assert.deepEqual(smoke.NEWUI_THEMES, ['light', 'dark']);
});

test('isolated smoke databases receive one deterministic model per creator capability', () => {
  assert.deepEqual(
    smoke.SMOKE_MODEL_FIXTURES.map((model) => [model.name, model.capability, model.adapter]),
    [
      ['NewUI Text Smoke', 'text', 'text-chat'],
      ['NewUI Image Smoke', 'image', 'image-openai'],
      ['Seedance 2.0', 'video', 'video-seedance'],
    ],
  );
});

test('browser launch falls back to installed stable channels when bundled chromium is absent', () => {
  assert.deepEqual(smoke.browserLaunchCandidates(true), [
    { headless: true },
    { headless: true, channel: 'chrome' },
    { headless: true, channel: 'msedge' },
  ]);
});

test('console and document overflow helpers fail only actionable states', () => {
  assert.equal(smoke.isUnexpectedConsoleMessage({ type: 'error', text: 'TypeError: boom' }), true);
  assert.equal(smoke.isUnexpectedConsoleMessage({ type: 'warning', text: 'slow request' }), false);
  assert.equal(smoke.isUnexpectedConsoleMessage({ type: 'error', text: 'favicon.ico 404 (Not Found)' }), false);
  assert.equal(smoke.isUnexpectedConsoleMessage({
    type: 'error',
    text: 'Failed to load resource: the server responded with a status of 404 (Not Found)',
    sourceUrl: 'http://127.0.0.1:5174/favicon.ico',
  }), false);
  const localPresignFailure = {
    type: 'error',
    text: 'Failed to load resource: the server responded with a status of 503 (Service Unavailable)',
    sourceUrl: 'http://127.0.0.1:5175/api/proxy/upload/presign',
  };
  assert.equal(smoke.isUnexpectedConsoleMessage(localPresignFailure, { allowLocalUploadFallback: true }), false);
  assert.equal(smoke.isUnexpectedConsoleMessage(localPresignFailure, { allowLocalUploadFallback: false }), true);
  const localViteSocketNoise = {
    type: 'error',
    text: 'Failed to load resource: net::ERR_NO_BUFFER_SPACE',
    sourceUrl: 'http://127.0.0.1:5174/admin/node_modules/.vite/deps/chunk-test.js',
  };
  assert.equal(smoke.isUnexpectedConsoleMessage(localViteSocketNoise, { allowLocalDevServerNoise: true }), false);
  assert.equal(smoke.isUnexpectedConsoleMessage(localViteSocketNoise, { allowLocalDevServerNoise: false }), true);
  assert.equal(smoke.isUnexpectedFailedResponse(
    { status: 503, url: localPresignFailure.sourceUrl },
    { allowLocalUploadFallback: true },
  ), false);
  assert.equal(smoke.isUnexpectedFailedResponse(
    { status: 503, url: 'https://studio.cylonai.cn/api/proxy/upload/presign' },
    { allowLocalUploadFallback: false },
  ), true);
  assert.equal(smoke.hasHorizontalOverflow({ scrollWidth: 391, clientWidth: 390 }), false);
  assert.equal(smoke.hasHorizontalOverflow({ scrollWidth: 398, clientWidth: 390 }), true);
});

test('route landmarks receive one bounded reload retry before becoming a failed check', () => {
  assert.equal(smoke.VIEW_WAIT_ATTEMPTS, 2);
});

test('reference fixtures exercise the tenth image and produce deterministic PNG uploads', () => {
  const fixtures = smoke.createReferenceFixturePayloads(10);

  assert.equal(fixtures.length, 10);
  assert.equal(fixtures[0].name, 'reference-01.png');
  assert.equal(fixtures[9].name, 'reference-10.png');
  assert.equal(fixtures[9].mimeType, 'image/png');
  assert.deepEqual([...fixtures[9].buffer.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
  assert.equal(fixtures[9].buffer.readUInt32BE(16), 32);
  assert.equal(fixtures[9].buffer.readUInt32BE(20), 32);
  assert.notDeepEqual(fixtures[0].buffer, fixtures[9].buffer);
  assert.equal(smoke.referencePromptForIndex(10), '使用 @10 作为主要构图参考');
  assert.throws(() => smoke.createReferenceFixturePayloads(11), /最多 10 张/);
});

test('thumbnail and screenshot helpers reject blank media and unsafe names', () => {
  assert.equal(smoke.THUMBNAIL_WAIT_TIMEOUT_MS, 15000);
  assert.equal(smoke.isRenderedThumbnail({ complete: true, naturalWidth: 640, naturalHeight: 360, src: 'blob:preview' }), true);
  assert.equal(smoke.isRenderedThumbnail({ complete: true, naturalWidth: 0, naturalHeight: 0, src: 'blob:preview' }), false);
  assert.equal(smoke.isRenderedThumbnail({ complete: false, naturalWidth: 640, naturalHeight: 360, src: '' }), false);
  assert.equal(
    smoke.smokeScreenshotName({ surface: 'creator', route: 'images', theme: 'dark', viewport: 'mobile' }),
    'creator-images-dark-mobile.png',
  );
  assert.equal(
    smoke.smokeScreenshotName({ surface: 'admin', route: '../models', theme: 'light', viewport: 'desktop' }),
    'admin-models-light-desktop.png',
  );
});
