import { build, Platform, Arch } from 'electron-builder';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const platform = process.argv[2] || process.platform;
if (!['win32', 'darwin'].includes(platform)) throw new Error('Installers support Windows and macOS.');
const arch = platform === 'win32' ? 'x64' : process.arch;
const signed = process.env.VERICIVIL_SIGNED_RELEASE === 'true';
const upgradeTest = process.argv.includes('--upgrade-test');
if (upgradeTest && (signed || process.env.GITHUB_ACTIONS !== 'true')) throw new Error('Synthetic upgrade installers are restricted to unsigned CI tests.');
if (signed) {
  if (process.env.GITHUB_EVENT_NAME === 'pull_request') throw new Error('PR builds cannot use production signing.');
  const required = platform === 'win32' ? ['CSC_LINK', 'VERICIVIL_WINDOWS_PUBLISHER'] : ['CSC_LINK', 'APPLE_ID', 'APPLE_APP_SPECIFIC_PASSWORD', 'APPLE_TEAM_ID'];
  if (required.some(name => !process.env[name])) throw new Error('Production signing credentials are incomplete. See desktop/README.md.');
} else process.env.CSC_IDENTITY_AUTO_DISCOVERY = 'false';
const config = JSON.parse(await readFile(new URL('../../desktop/electron-builder.json', import.meta.url)));
const { version: electronVersion } = JSON.parse(await readFile(new URL('../node_modules/electron/package.json', import.meta.url)));
const channel = `latest-${platform}-${arch}`;
config.electronVersion = electronVersion;
config.forceCodeSigning = signed;
config.artifactName = `VeriCivil-Superelevation-\${version}-\${os}-\${arch}${signed ? '' : '-unsigned'}.\${ext}`;
config.directories.output = `installers/${platform}-${arch}`;
if (upgradeTest) {
  const { version } = JSON.parse(await readFile(new URL('../../desktop/app/package.json', import.meta.url)));
  const parts = version.split('.').map(Number);
  parts[2] += 1;
  config.extraMetadata = { version: parts.join('.') };
  config.directories.output = 'installer-tests';
}
if (signed) {
  config.publish = { provider: 'github', owner: 'colewinstead', repo: 'VeriCivil', channel };
  if (platform === 'win32') config.win.publisherName = process.env.VERICIVIL_WINDOWS_PUBLISHER;
  else config.mac.notarize = true;
} else config.mac.notarize = false;
await writeFile(new URL('../../desktop/app/desktop-config.json', import.meta.url), JSON.stringify({ signedUpdates: signed, updateChannel: channel }));
try {
  const targets = (platform === 'win32' ? Platform.WINDOWS : Platform.MAC).createTarget(undefined, arch === 'arm64' ? Arch.arm64 : Arch.x64);
  const artifacts = await build({ projectDir: fileURLToPath(new URL('../../desktop/', import.meta.url)), targets, config, publish: 'never' });
  console.log(artifacts.join('\n'));
} finally {
  // A later local/preview package must never inherit production update settings.
  await writeFile(new URL('../../desktop/app/desktop-config.json', import.meta.url), JSON.stringify({ signedUpdates: false }));
}
