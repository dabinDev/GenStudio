import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

export const DEFAULT_MODEL_HEALTH_TIMEOUT_MS = 240000;

export function rootOrigin(url) {
  return new URL(url).origin;
}

export function modelHealthTimeoutMs(env = process.env) {
  const value = Number.parseInt(env.MODEL_HEALTH_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value > 0 ? value : DEFAULT_MODEL_HEALTH_TIMEOUT_MS;
}

export function normalizeModelsPayload(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.models)) return payload.models;
  return [];
}

export function normalizeBatchResultsPayload(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.results)) return payload.results;
  return [];
}

function modelId(model) {
  return String(model?.id || model?.modelId || '');
}

function modelName(model) {
  return String(model?.displayName || model?.display_name || model?.name || modelId(model));
}

function modelCapability(model) {
  return String(model?.capability || 'unknown');
}

function resultStatus(result) {
  const latest = result?.health?.latest;
  return String(result?.status || latest?.status || result?.health?.status || 'unknown');
}

function resultReason(result, fallback = '') {
  const candidates = [
    result?.error?.message,
    result?.health?.latest?.message,
    result?.health?.message,
    result?.message,
    fallback,
  ];
  return String(candidates.find((item) => typeof item === 'string' && item.trim()) || 'health check failed');
}

function increment(target, key) {
  target[key] = (target[key] || 0) + 1;
}

export function buildHealthCoverageSummary(models, batchResults) {
  const sortedModels = [...models].sort((a, b) => modelId(a).localeCompare(modelId(b)));
  const resultsById = new Map(batchResults.map((item) => [String(item?.modelId || item?.id || ''), item]));
  const idCounts = new Map();
  const byCapability = {};
  const byStatus = {};
  const failures = [];
  const integrityErrors = [];
  const summaryModels = [];
  let testedModels = 0;

  for (const model of sortedModels) {
    const id = modelId(model);
    if (id) idCounts.set(id, (idCounts.get(id) || 0) + 1);
  }

  if (sortedModels.length === 0) {
    const error = { reason: 'no models returned by admin model list' };
    integrityErrors.push(error);
    failures.push({ modelId: '', name: '', capability: 'unknown', status: 'invalid', reason: error.reason });
  }

  for (const model of sortedModels) {
    const id = modelId(model);
    if (!id) {
      const error = { modelId: id, name: modelName(model), capability: modelCapability(model), reason: 'model id is empty' };
      integrityErrors.push(error);
      failures.push({ ...error, status: 'invalid' });
    }
  }

  for (const [id, count] of [...idCounts.entries()].sort(([a], [b]) => a.localeCompare(b))) {
    if (count > 1) {
      const examples = sortedModels.filter((model) => modelId(model) === id).map(modelName);
      const error = { modelId: id, reason: 'duplicate model id', count, examples };
      integrityErrors.push(error);
      failures.push({ modelId: id, name: examples.join(', '), capability: 'unknown', status: 'invalid', reason: error.reason });
    }
  }

  for (const model of sortedModels) {
    const id = modelId(model);
    const capability = modelCapability(model);
    const result = resultsById.get(id);
    const duplicateId = Boolean(id && idCounts.get(id) > 1);
    const invalidId = !id || duplicateId;
    const status = invalidId ? 'invalid' : result ? resultStatus(result) : 'untested';
    const reason = !id
      ? 'model id is empty'
      : duplicateId
        ? 'duplicate model id'
        : result
          ? resultReason(result)
          : 'not returned by batch health check';

    increment(byCapability, capability);
    increment(byStatus, status);
    if (result && !invalidId) testedModels += 1;
    if (status !== 'success' && !invalidId) {
      failures.push({ modelId: id, name: modelName(model), capability, status, reason });
    }

    summaryModels.push({
      id,
      name: modelName(model),
      capability,
      status,
      durationMs: result?.health?.latest?.durationMs ?? result?.health?.latest?.duration_ms ?? null,
      reason: status === 'success' ? '' : reason,
    });
  }

  return {
    totalModels: sortedModels.length,
    testedModels,
    byCapability,
    byStatus,
    failures,
    integrityErrors,
    models: summaryModels,
  };
}

export function shouldFailCoverage(summary) {
  return (
    summary.totalModels === 0 ||
    summary.totalModels !== summary.testedModels ||
    (summary.failures?.length || 0) > 0 ||
    (summary.integrityErrors?.length || 0) > 0
  );
}

export function createOutputDir(now = new Date()) {
  return path.resolve(
    'output/playwright/model-health-coverage-' + now.toISOString().replace(/[:.]/g, '-'),
  );
}

export function writeSummaryArtifact(summary, outDir = createOutputDir()) {
  fs.mkdirSync(outDir, { recursive: true });
  const file = path.join(outDir, 'summary.json');
  fs.writeFileSync(file, JSON.stringify(summary, null, 2));
  return { outDir, file };
}

async function readJsonResponse(response, label) {
  const payload = await response.json().catch(async () => {
    const text = await response.text().catch(() => '');
    return { message: text };
  });
  if (!response.ok()) {
    const message = payload?.detail?.message || payload?.message || `${label} failed with HTTP ${response.status()}`;
    throw new Error(`${label} failed: ${message}`);
  }
  return payload;
}

async function login(context, baseUrl) {
  if (process.env.SMOKE_EMAIL && process.env.SMOKE_PASSWORD) {
    const response = await context.request.post(`${baseUrl}/api/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { identifier: process.env.SMOKE_EMAIL, password: process.env.SMOKE_PASSWORD },
    });
    await readJsonResponse(response, 'password login');
    return;
  }

  const response = await context.request.post(`${baseUrl}/api/auth/dev-login`, {
    headers: { 'Content-Type': 'application/json' },
    data: {
      externalUserId: 'local-model-health-coverage',
      email: 'cage_ben@sina.com',
      nickname: 'Model Health Coverage',
    },
  });
  await readJsonResponse(response, 'dev login');
}

async function fetchCsrfToken(context, baseUrl) {
  const response = await context.request.get(`${baseUrl}/api/auth/csrf`);
  const payload = await readJsonResponse(response, 'csrf fetch');
  return payload.csrfToken || payload.csrf_token || payload.token || '';
}

export async function runModelHealthCoverage(options = {}) {
  const siteUrl = options.baseUrl || process.env.BASE_URL || process.env.FRONT_URL || 'http://127.0.0.1:5175';
  const baseUrl = rootOrigin(siteUrl);
  const browser = await chromium.launch({ headless: process.env.HEADLESS !== 'false' });
  const context = await browser.newContext();

  try {
    await login(context, baseUrl);
    const csrfToken = await fetchCsrfToken(context, baseUrl);
    const modelsPayload = await readJsonResponse(
      await context.request.get(`${baseUrl}/api/admin/models`),
      'fetch admin models',
    );
    const models = normalizeModelsPayload(modelsPayload);
    const modelIds = models.map(modelId).filter(Boolean);
    const batchPayload = await readJsonResponse(
      await context.request.post(`${baseUrl}/api/admin/models/batch-health-check`, {
        timeout: modelHealthTimeoutMs(),
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
        },
        data: { modelIds },
      }),
      'batch model health check',
    );
    const batchResults = normalizeBatchResultsPayload(batchPayload);
    return buildHealthCoverageSummary(models, batchResults);
  } finally {
    await browser.close();
  }
}

if (process.env.MODEL_HEALTH_COVERAGE_UNIT_ONLY !== '1') {
  const summary = await runModelHealthCoverage();
  summary.outDir = createOutputDir();
  writeSummaryArtifact(summary, summary.outDir);
  console.log(JSON.stringify(summary, null, 2));
  if (shouldFailCoverage(summary)) {
    process.exitCode = 1;
  }
}
