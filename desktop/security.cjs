const path = require('node:path');

const APP_URL = 'vericivil://app/';
const FILE_TYPES = { json: 'Superelevation project', vericivil: 'VeriCivil project', pdf: 'PDF report', csv: 'OpenRoads CSV', dxf: 'DXF drawing' };

function assetPath(url, root) {
  const parsed = new URL(url);
  if (parsed.protocol !== 'vericivil:' || parsed.host !== 'app') throw new Error('Unknown application origin.');
  const name = decodeURIComponent(parsed.pathname === '/' ? '/index.html' : parsed.pathname);
  if (name.includes('\0') || name.includes('\\')) throw new Error('Invalid asset path.');
  const resolved = path.resolve(root, '.' + name);
  if (!resolved.startsWith(path.resolve(root) + path.sep)) throw new Error('Asset path escapes the application.');
  return resolved;
}

function savePayload(payload) {
  if (!payload || typeof payload.name !== 'string' || path.basename(payload.name) !== payload.name || /[\\/:\x00-\x1f]/.test(payload.name)) {
    throw new Error('Invalid export filename.');
  }
  const extension = path.extname(payload.name).slice(1).toLowerCase();
  if (!FILE_TYPES[extension]) throw new Error('Unsupported export type.');
  if (!(payload.data instanceof Uint8Array) || payload.data.byteLength > 64 * 1024 * 1024) throw new Error('Invalid export data or export exceeds 64 MiB.');
  return { name: payload.name, extension, data: Buffer.from(payload.data) };
}

function websiteUrl(value) {
  try {
    const url = new URL(value);
    return url.origin === 'https://vericivil.com' && !url.username && !url.password;
  } catch { return false; }
}

module.exports = { APP_URL, FILE_TYPES, assetPath, savePayload, websiteUrl };
