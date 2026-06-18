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

test('mojibake detector catches broken placeholder labels', () => {
  assert.equal(smoke.hasMojibake('????????'), true);
  assert.equal(smoke.hasMojibake('�'), true);
  assert.equal(smoke.hasMojibake('正常中文'), false);
});
