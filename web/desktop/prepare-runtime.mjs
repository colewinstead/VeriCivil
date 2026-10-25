import { createHash } from 'node:crypto';
import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const root = new URL('../../', import.meta.url);
const runtime = new URL('../../desktop/runtime/', import.meta.url);
const python = process.platform === 'win32' ? 'python' : 'python3';
execFileSync(python, [fileURLToPath(new URL('scripts/prepare_web_runtime.py', root))], { stdio: 'inherit' });
await mkdir(new URL('pyodide/', runtime), { recursive: true });
await mkdir(new URL('wheels/', runtime), { recursive: true });
const pyodidePackage = new URL('../node_modules/pyodide/', import.meta.url);
const { version } = JSON.parse(await readFile(new URL('package.json', pyodidePackage)));
const lock = JSON.parse(await readFile(new URL('pyodide-lock.json', pyodidePackage)));
for (const file of ['pyodide.js', 'pyodide.asm.js', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json']) {
  await cp(new URL(file, pyodidePackage), new URL('pyodide/' + file, runtime));
}
const manifest = JSON.parse(await readFile(new URL('web/public/python/manifest.json', root)));
const bundle = manifest.calculators.superelevation;
const packages = new Set();
function include(name) {
  name = name.toLowerCase().replaceAll('_', '-');
  if (packages.has(name)) return;
  const info = lock.packages[name];
  if (!info) throw new Error(`Missing Pyodide package: ${name}`);
  packages.add(name);
  info.depends.forEach(include);
}
[...bundle.pyodide_packages, 'pyparsing', 'typing-extensions', 'charset-normalizer'].forEach(include);
const checksums = [];
async function download(url, destination, expected) {
  let bytes;
  try { bytes = await readFile(destination); } catch { /* Download uncached dependency. */ }
  if (!bytes || createHash('sha256').update(bytes).digest('hex') !== expected) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Dependency download failed: ${url} (${response.status})`);
    bytes = Buffer.from(await response.arrayBuffer());
  }
  if (createHash('sha256').update(bytes).digest('hex') !== expected) throw new Error(`Dependency checksum mismatch: ${url}`);
  await writeFile(destination, bytes);
  checksums.push({ url, sha256: expected, file: fileURLToPath(destination).slice(fileURLToPath(runtime).length) });
}
await Promise.all([...packages].map((name) => {
  const info = lock.packages[name];
  return download(`https://cdn.jsdelivr.net/pyodide/v${version}/full/${info.file_name}`, new URL('pyodide/' + info.file_name, runtime), info.sha256);
}));
const wheels = [];
for (const requirement of bundle.micropip_packages) {
  const [name, version] = requirement.split('==');
  const response = await fetch(`https://pypi.org/pypi/${name}/${version}/json`);
  if (!response.ok) throw new Error(`Could not resolve pinned wheel: ${requirement}`);
  const release = await response.json();
  const wheel = release.urls.find((item) => item.filename.endsWith('-py3-none-any.whl'));
  if (!wheel || !wheel.digests.sha256) throw new Error(`No pure Python wheel for ${requirement}`);
  await download(wheel.url, new URL('wheels/' + wheel.filename, runtime), wheel.digests.sha256);
  wheels.push('/wheels/' + wheel.filename);
}
bundle.pyodide_packages = [...packages];
bundle.micropip_packages = wheels;
bundle.offline = true;
await writeFile(new URL('manifest.json', runtime), JSON.stringify({ calculators: { superelevation: bundle } }, null, 2));
await writeFile(new URL('checksums.json', runtime), JSON.stringify(checksums.sort((a, b) => a.file.localeCompare(b.file)), null, 2));
console.log(`Offline runtime ready: ${packages.size} Pyodide packages and ${wheels.length} pinned export wheels.`);
