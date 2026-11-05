import { packager } from '@electron/packager';
import { fileURLToPath } from 'node:url';
import { readFile } from 'node:fs/promises';
import editionTools from '../../desktop/edition.cjs';
const edition = editionTools.getEdition();
const staged = JSON.parse(await readFile(new URL(`../../desktop/${edition.appDirectory}/edition.json`, import.meta.url)));
if (staged.id !== edition.id) throw new Error('Rebuild the selected desktop edition before packaging.');
const { version: electronVersion } = JSON.parse(await readFile(new URL('../node_modules/electron/package.json', import.meta.url)));


const platform = process.argv[2] || process.platform;
if (!["darwin", "win32"].includes(platform)) throw new Error("Desktop preview packaging supports macOS and Windows.");
const paths = await packager({
  platform, arch: platform === "win32" ? "x64" : process.arch,
  dir: fileURLToPath(new URL(`../../desktop/${edition.appDirectory}/`, import.meta.url)),
  out: fileURLToPath(new URL(`../../desktop/${edition.previewDirectory}/`, import.meta.url)),
  electronVersion, prune: false,
  name: edition.previewName, appBundleId: edition.previewAppId,
  icon: fileURLToPath(new URL(`../../desktop/icons/${edition.iconName}.${platform === 'darwin' ? 'icns' : 'ico'}`, import.meta.url)),
  overwrite: true, asar: true,
});
console.log(paths.join('\n'));
