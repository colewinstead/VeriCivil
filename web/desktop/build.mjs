import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { build } from 'vite';
import './prepare-runtime.mjs';

const app = new URL('../../desktop/app/', import.meta.url);
await build({ configFile: fileURLToPath(new URL('vite.config.ts', import.meta.url)) });
for (const file of ['launch.cjs', 'main.cjs', 'preload.cjs', 'security.cjs', 'files.cjs']) await cp(new URL('../../desktop/' + file, import.meta.url), new URL(file, app));
await cp(new URL('../public/python/', import.meta.url), new URL('renderer/python/', app), { recursive: true });
await cp(new URL('../../desktop/runtime/pyodide/', import.meta.url), new URL('renderer/pyodide/', app), { recursive: true });
await cp(new URL('../../desktop/runtime/wheels/', import.meta.url), new URL('renderer/wheels/', app), { recursive: true });
await cp(new URL('../../desktop/runtime/manifest.json', import.meta.url), new URL('renderer/python/manifest.json', app));
await cp(new URL('../public/pyodide-worker.js', import.meta.url), new URL('renderer/pyodide-worker.js', app));
await mkdir(new URL('renderer/showcase/', app), { recursive: true });
await cp(new URL('../public/showcase/superelevation-report-sample.pdf', import.meta.url), new URL('renderer/showcase/superelevation-report-sample.pdf', app));
const { application_version: version } = JSON.parse(await readFile(new URL('../app/generated/release-info.json', import.meta.url)));
await writeFile(new URL('package.json', app), JSON.stringify({ name: 'vericivil-desktop-preview', productName: 'VeriCivil Desktop Preview', version, private: true, main: 'launch.cjs' }, null, 2));
await cp(new URL('../../LICENSE', import.meta.url), new URL('LICENSE', app));
console.log(`Electron preview ${version} built at ${fileURLToPath(app)}`);
