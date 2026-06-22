import assert from 'node:assert/strict';
import { test } from 'node:test';

process.env.FRONTED_SMOKE_UNIT_ONLY = '1';

const smoke = await import('./fronted-online-smoke.mjs');

test('safeName keeps screenshot names unique when Chinese route labels are used', () => {
  assert.equal(smoke.safeName('front-settings'), 'front-settings');
  assert.notEqual(smoke.safeName('front-history-文案'), smoke.safeName('front-history-图片'));
  assert.notEqual(smoke.safeName('front-history-视频'), 'front-history');
});

test('mojibake detector catches placeholder titles without flagging readable Chinese', () => {
  assert.equal(smoke.hasMojibake('????????????????????'), true);
  assert.equal(smoke.hasMojibake('�'), true);
  assert.equal(smoke.hasMojibake('图片创作历史'), false);
});

test('front smoke routes cover the creative workspace and account surfaces', () => {
  assert.deepEqual(
    smoke.FRONT_SMOKE_ROUTES.map((item) => item.name),
    ['front-home', 'front-text', 'front-images', 'front-videos', 'front-settings', 'front-profile'],
  );
});

test('front smoke viewports cover desktop and mobile before release', () => {
  assert.deepEqual(
    smoke.FRONT_SMOKE_VIEWPORTS.map((item) => item.name),
    ['desktop', 'mobile'],
  );
  assert.deepEqual(smoke.FRONT_SMOKE_VIEWPORTS[1], { name: 'mobile', width: 390, height: 844 });
});

test('front smoke uses load-oriented waits instead of networkidle for long polling pages', () => {
  assert.equal(smoke.SMOKE_WAIT_UNTIL, 'load');
});

test('summarizeSmokeFailures combines failed checks, failed responses and console errors', () => {
  const summary = smoke.summarizeSmokeFailures({
    failedChecks: [{ name: 'front-images:no-mojibake' }],
    failedResponses: [{ url: '/api/broken', status: 500 }],
    nonAuthConsoleErrors: [{ text: 'boom' }],
  });

  assert.equal(summary.failedCheckCount, 1);
  assert.equal(summary.failedResponseCount, 1);
  assert.equal(summary.consoleErrorCount, 1);
  assert.equal(summary.ok, false);
});
