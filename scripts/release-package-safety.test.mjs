import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const dockerignore = fs.readFileSync(path.join(repoRoot, '.dockerignore'), 'utf8');
const operations = fs.readFileSync(path.join(repoRoot, 'docs', 'OPERATIONS.md'), 'utf8');
const remoteDeploy = fs.readFileSync(path.join(repoRoot, 'deploy', 'remote-brand-deploy.sh'), 'utf8');

test('docker build context excludes environment files at every depth', () => {
  const patterns = dockerignore
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  assert.ok(
    patterns.includes('**/.env*'),
    'expected .dockerignore to exclude nested .env files such as server/.env',
  );
});

test('release runbook stages tracked backend source with git archive', () => {
  assert.match(operations, /git archive --format=tar HEAD/);
});

test('release runbook does not copy the raw server working directory', () => {
  assert.doesNotMatch(operations, /Copy-Item -LiteralPath 'server'/);
});

test('remote deploy helper can load a verified image without building on the server', () => {
  assert.match(remoteDeploy, /GENSTUDIO_IMAGE_ARCHIVE/);
  assert.match(remoteDeploy, /GENSTUDIO_IMAGE_TAG/);
  assert.match(remoteDeploy, /docker load --input "\$image_archive"/);
  assert.match(remoteDeploy, /docker compose up -d --no-build genstudio-api/);
});

test('remote deploy helper uses Unix line endings', () => {
  assert.equal(remoteDeploy.includes('\r'), false);
});
