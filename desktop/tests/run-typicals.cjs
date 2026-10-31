const { mkdtempSync, rmSync } = require('node:fs');
const { tmpdir } = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const electron = require('../../web/node_modules/electron');
const profile = mkdtempSync(path.join(tmpdir(), 'vericivil-typicals-'));
try {
  const result = spawnSync(electron, [path.join(__dirname, 'typicals-smoke.cjs')], {
    stdio: 'inherit', timeout: 180000, env: { ...process.env, VERICIVIL_TEST_PROFILE: profile },
  });
  if (result.error) throw result.error;
  process.exitCode = result.status ?? 1;
} finally { rmSync(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 }); }
