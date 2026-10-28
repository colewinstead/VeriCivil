import { packager } from '@electron/packager';
import { fileURLToPath } from 'node:url';
import { readFile } from 'node:fs/promises';
const { version: electronVersion } = JSON.parse(await readFile(new URL('../node_modules/electron/package.json', import.meta.url)));


const platform = process.argv[2] || process.platform;
if (!["darwin", "win32"].includes(platform)) throw new Error("Desktop preview packaging supports macOS and Windows.");
const paths = await packager({
  platform, arch: platform === "win32" ? "x64" : process.arch,
  dir: fileURLToPath(new URL('../../desktop/app/', import.meta.url)),
  out: fileURLToPath(new URL('../../desktop/releases/', import.meta.url)),
  electronVersion, prune: false,
  name: 'VeriCivil Desktop Preview', appBundleId: 'com.vericivil.desktop.preview',
  icon: fileURLToPath(new URL(`../../desktop/icons/vericivil.${platform === 'darwin' ? 'icns' : 'ico'}`, import.meta.url)),
  overwrite: true, asar: true,
});
console.log(paths.join('\n'));
