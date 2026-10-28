const fs = require('node:fs');
const path = require('node:path');

function createDiagnostics(directory, versions) {
  fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
  const file = path.join(directory, 'desktop.log');
  const record = (event, code = '') => {
    try {
      if (fs.existsSync(file) && fs.statSync(file).size > 256 * 1024) fs.renameSync(file, file + '.previous');
      // Only fixed event names and error codes are recorded, never messages, paths, or project data.
      const safe = value => typeof value === 'string' && /^[a-z0-9_.-]{0,80}$/i.test(value) ? value : 'unknown';
      fs.appendFileSync(file, JSON.stringify({ time: new Date().toISOString(), event: safe(event), code: safe(code) }) + '\n', { mode: 0o600 });
    } catch { /* Logging must not prevent saving or startup. */ }
  };
  return {
    record,
    bundle: () => JSON.stringify({ versions, platform: process.platform, arch: process.arch, events: fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : '' }, null, 2),
  };
}
module.exports = { createDiagnostics };
