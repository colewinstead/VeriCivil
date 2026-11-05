import { build, Platform, Arch } from 'electron-builder';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

import editionTools from '../../desktop/edition.cjs';
const edition = editionTools.getEdition();
const app = new URL(`../../desktop/${edition.appDirectory}/`, import.meta.url);
const staged = JSON.parse(await readFile(new URL('edition.json', app)));
if (staged.id !== edition.id) throw new Error('Rebuild the selected desktop edition before packaging.');

const platform = process.argv[2] || process.platform;
if (!['win32', 'darwin'].includes(platform)) throw new Error('Installers support Windows and macOS.');
const arch = platform === 'win32' ? 'x64' : process.arch;
const signed = process.env.VERICIVIL_SIGNED_RELEASE === 'true';
const upgradeTest = process.argv.includes('--upgrade-test');
if (upgradeTest && (signed || process.env.GITHUB_ACTIONS !== 'true')) throw new Error('Synthetic upgrade installers are restricted to unsigned CI tests.');
if (signed && edition.id !== 'vericivil') throw new Error('Signed neutral releases are not configured.');
if (signed) {
  if (process.env.GITHUB_EVENT_NAME === 'pull_request') throw new Error('PR builds cannot use production signing.');
  const required = platform === 'win32' ? ['CSC_LINK', 'VERICIVIL_WINDOWS_PUBLISHER'] : ['CSC_LINK', 'APPLE_ID', 'APPLE_APP_SPECIFIC_PASSWORD', 'APPLE_TEAM_ID'];
  if (required.some(name => !process.env[name])) throw new Error('Production signing credentials are incomplete. See desktop/README.md.');
} else process.env.CSC_IDENTITY_AUTO_DISCOVERY = 'false';
const config = JSON.parse(await readFile(new URL('../../desktop/electron-builder.json', import.meta.url)));
const { version: electronVersion } = JSON.parse(await readFile(new URL('../node_modules/electron/package.json', import.meta.url)));
const updatesEnabled = signed || platform === 'win32';
const channel = editionTools.updateChannel(edition, platform, arch, signed);
Object.assign(config, { appId: edition.appId, productName: edition.productName, executableName: edition.executableName });
config.directories.app = edition.appDirectory;
config.win.icon = `icons/${edition.iconName}.ico`;
config.mac.icon = `icons/${edition.iconName}.icns`;
config.fileAssociations = edition.id === 'vericivil' ? [{ ext: 'vericivil', name: edition.projectLabel, role: 'Editor' }] : [];
config.afterPack = context => {
  if (edition.id === 'neutral' && context.packager.fileAssociations.length) throw new Error('Neutral packages must not register file associations.');
  if (context.packager.appInfo.updaterCacheDirName !== `${edition.packageName}-updater`) throw new Error('Desktop updater cache does not match the selected edition.');
};
config.electronVersion = electronVersion;
config.forceCodeSigning = signed;
config.artifactName = `${edition.artifactPrefix}-\${version}-\${os}-\${arch}${signed ? '' : '-unsigned'}.\${ext}`;
config.directories.output = `${edition.installerDirectory}/${platform}-${arch}`;
if (upgradeTest) {
  const { version } = JSON.parse(await readFile(new URL('package.json', app)));
  const parts = version.split('.').map(Number);
  parts[2] += 1;
  config.extraMetadata = { version: parts.join('.') };
  config.directories.output = edition.id === 'vericivil' ? 'installer-tests' : 'installer-tests/neutral';
}
if (updatesEnabled) {
  config.publish = { provider: 'github', owner: 'colewinstead', repo: 'VeriCivil', channel };
}
if (platform === 'win32') {
  config.win.verifyUpdateCodeSignature = signed;
  if (signed) config.win.publisherName = process.env.VERICIVIL_WINDOWS_PUBLISHER;
}
config.mac.notarize = signed;
await writeFile(new URL('desktop-config.json', app), JSON.stringify({ signedUpdates: signed, updatesEnabled, updateChannel: channel }));
try {
  const targets = (platform === 'win32' ? Platform.WINDOWS : Platform.MAC).createTarget(undefined, arch === 'arm64' ? Arch.arm64 : Arch.x64);
  const artifacts = await build({ projectDir: fileURLToPath(new URL('../../desktop/', import.meta.url)), targets, config, publish: 'never' });
  console.log(artifacts.join('\n'));
} finally {
  // A later local/preview package must never inherit production update settings.
  await writeFile(new URL('desktop-config.json', app), JSON.stringify({ signedUpdates: false }));
}
