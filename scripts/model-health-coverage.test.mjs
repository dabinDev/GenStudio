import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';

process.env.MODEL_HEALTH_COVERAGE_UNIT_ONLY = '1';

const coverage = await import('./model-health-coverage.mjs');

test('buildHealthCoverageSummary counts all models and tested batch results by capability and status', () => {
  const models = [
    { id: 'text-ok', name: 'Text OK', capability: 'text' },
    { id: 'image-bad', displayName: 'Image Bad', capability: 'image' },
    { id: 'video-missing', name: 'Video Missing', capability: 'video' },
  ];
  const batchResults = [
    { modelId: 'text-ok', status: 'success', health: { latest: { durationMs: 120, message: 'ok' } } },
    { modelId: 'image-bad', status: 'failed', health: { latest: { message: 'upstream down' } } },
  ];

  const summary = coverage.buildHealthCoverageSummary(models, batchResults);

  assert.equal(summary.totalModels, 3);
  assert.equal(summary.testedModels, 2);
  assert.deepEqual(summary.byCapability, { image: 1, text: 1, video: 1 });
  assert.deepEqual(summary.byStatus, { failed: 1, success: 1, untested: 1 });
  assert.deepEqual(
    summary.failures.map((item) => ({ modelId: item.modelId, status: item.status, reason: item.reason })),
    [
      { modelId: 'image-bad', status: 'failed', reason: 'upstream down' },
      { modelId: 'video-missing', status: 'untested', reason: 'not returned by batch health check' },
    ],
  );
  assert.deepEqual(
    summary.models.map((item) => ({ id: item.id, capability: item.capability, status: item.status })),
    [
      { id: 'image-bad', capability: 'image', status: 'failed' },
      { id: 'text-ok', capability: 'text', status: 'success' },
      { id: 'video-missing', capability: 'video', status: 'untested' },
    ],
  );
});

test('shouldFailCoverage requires every model to be tested and successful', () => {
  assert.equal(
    coverage.shouldFailCoverage({ totalModels: 2, testedModels: 2, failures: [] }),
    false,
  );
  assert.equal(
    coverage.shouldFailCoverage({ totalModels: 2, testedModels: 1, failures: [] }),
    true,
  );
  assert.equal(
    coverage.shouldFailCoverage({ totalModels: 2, testedModels: 2, failures: [{ modelId: 'broken' }] }),
    true,
  );
});

test('empty model list fails coverage to avoid a false 0/0 success', () => {
  const summary = coverage.buildHealthCoverageSummary([], []);

  assert.equal(summary.totalModels, 0);
  assert.equal(summary.testedModels, 0);
  assert.deepEqual(
    summary.integrityErrors.map((item) => item.reason),
    ['no models returned by admin model list'],
  );
  assert.equal(coverage.shouldFailCoverage(summary), true);
});

test('models with empty ids are reported as integrity failures', () => {
  const summary = coverage.buildHealthCoverageSummary(
    [
      { id: '', name: 'Missing ID', capability: 'text' },
      { id: 'text-ok', name: 'Text OK', capability: 'text' },
    ],
    [{ modelId: 'text-ok', status: 'success' }],
  );

  assert.deepEqual(
    summary.integrityErrors.map((item) => ({ reason: item.reason, name: item.name })),
    [{ reason: 'model id is empty', name: 'Missing ID' }],
  );
  assert.deepEqual(
    summary.failures.map((item) => ({ modelId: item.modelId, status: item.status, reason: item.reason })),
    [{ modelId: '', status: 'invalid', reason: 'model id is empty' }],
  );
  assert.equal(coverage.shouldFailCoverage(summary), true);
});

test('duplicate model ids are reported as integrity failures', () => {
  const summary = coverage.buildHealthCoverageSummary(
    [
      { id: 'dup', name: 'Duplicate A', capability: 'image' },
      { id: 'dup', name: 'Duplicate B', capability: 'video' },
    ],
    [{ modelId: 'dup', status: 'success' }],
  );

  assert.deepEqual(
    summary.integrityErrors.map((item) => ({ modelId: item.modelId, reason: item.reason, count: item.count })),
    [{ modelId: 'dup', reason: 'duplicate model id', count: 2 }],
  );
  assert.deepEqual(
    summary.failures.map((item) => ({ modelId: item.modelId, status: item.status, reason: item.reason })),
    [{ modelId: 'dup', status: 'invalid', reason: 'duplicate model id' }],
  );
  assert.equal(coverage.shouldFailCoverage(summary), true);
});

test('model health timeout defaults to four minutes and supports environment override', () => {
  const original = process.env.MODEL_HEALTH_TIMEOUT_MS;
  try {
    delete process.env.MODEL_HEALTH_TIMEOUT_MS;
    assert.equal(coverage.modelHealthTimeoutMs(), 240000);

    process.env.MODEL_HEALTH_TIMEOUT_MS = '300000';
    assert.equal(coverage.modelHealthTimeoutMs(), 300000);

    process.env.MODEL_HEALTH_TIMEOUT_MS = 'invalid';
    assert.equal(coverage.modelHealthTimeoutMs(), 240000);
  } finally {
    if (original === undefined) {
      delete process.env.MODEL_HEALTH_TIMEOUT_MS;
    } else {
      process.env.MODEL_HEALTH_TIMEOUT_MS = original;
    }
  }
});

test('writeSummaryArtifact stores summary.json under the provided output directory', () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'model-health-coverage-'));
  const summary = {
    totalModels: 1,
    testedModels: 1,
    byCapability: { text: 1 },
    byStatus: { success: 1 },
    failures: [],
    integrityErrors: [],
    models: [{ id: 'text-ok', status: 'success' }],
    outDir,
  };

  const artifact = coverage.writeSummaryArtifact(summary, outDir);
  const saved = JSON.parse(fs.readFileSync(artifact.file, 'utf8'));

  assert.equal(artifact.outDir, outDir);
  assert.equal(path.basename(artifact.file), 'summary.json');
  assert.deepEqual(saved, summary);
});
