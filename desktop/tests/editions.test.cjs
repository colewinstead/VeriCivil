const test = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const { getEdition, updateChannel } = require('../edition.cjs');
const { Updates, editionDownload, isEditionUpdate } = require('../updates.cjs');

test('editions preserve branded defaults and isolate installed identities, outputs and updater caches', () => {
  const branded = getEdition('vericivil'), neutral = getEdition('neutral');
  assert.equal(branded.appId, 'com.vericivil.superelevation');
  assert.equal(branded.profileDirectory, 'VeriCivil Superelevation');
  assert.equal(branded.appDirectory, 'app');
  assert.equal(branded.projectExtension, 'vericivil');
  assert.equal(neutral.productName, 'Superelevation Calculator');
  assert.equal(neutral.projectExtension, 'json');
  for (const field of ['appId', 'previewAppId', 'profileDirectory', 'appDirectory', 'installerDirectory', 'previewDirectory', 'executableName', 'artifactPrefix', 'previewArtifactPrefix', 'packageName']) assert.notEqual(branded[field], neutral[field], field);
  // electron-builder derives updaterCacheDirName from packageName.
  assert.notEqual(`${branded.packageName}-updater`, `${neutral.packageName}-updater`);
  assert.equal(updateChannel(branded, 'win32', 'x64'), 'latest-unsigned-win32-x64');
  assert.equal(updateChannel(branded, 'darwin', 'arm64', true), 'latest-darwin-arm64');
  assert.equal(updateChannel(neutral, 'win32', 'x64'), 'latest-neutral-unsigned-win32-x64');
  for (const unknown of ['', 'other', '__proto__', 'constructor']) assert.throws(() => getEdition(unknown), /Unknown desktop edition/);
});

test('neutral download discovery requires the exact edition, version, architecture and trusted asset URL', () => {
  const neutral = getEdition('neutral');
  const name = 'Superelevation-Calculator-1.8.0-mac-arm64-unsigned.dmg';
  const url = `https://github.com/colewinstead/VeriCivil/releases/download/v1.8.0/${name}`;
  const release = { tag_name: 'v1.8.0', assets: [{ name, browser_download_url: url }] };
  assert.deepEqual(editionDownload(release, neutral, 'darwin', 'arm64'), { version: '1.8.0', url });
  assert.equal(editionDownload(release, neutral, 'darwin', 'x64'), null);
  assert.equal(editionDownload(release, getEdition('vericivil'), 'darwin', 'arm64'), null);
  assert.equal(editionDownload({ ...release, assets: [] }, neutral, 'darwin', 'arm64'), null);
  assert.equal(editionDownload({ ...release, assets: [{ name, browser_download_url: 'https://example.invalid/setup.dmg' }] }, neutral, 'darwin', 'arm64'), null);
  assert.throws(() => editionDownload({ ...release, prerelease: true }, neutral, 'darwin', 'arm64'));
});

test('neutral updater rejects branded/mixed feeds before download or installation', async () => {
  const edition = getEdition('neutral');
  const valid = { version: '1.8.0', files: [{ url: 'Superelevation-Calculator-1.8.0-win-x64-unsigned.exe' }] };
  assert.equal(isEditionUpdate(valid, edition, 'win32', 'x64'), true);
  assert.equal(isEditionUpdate(valid, edition, 'win32', 'arm64'), false);
  for (const files of [[], [{ url: 'VeriCivil-Superelevation-1.8.0-win-x64-unsigned.exe' }], [...valid.files, { url: 'other.exe' }], [{ url: '../' + valid.files[0].url }]]) {
    const info = { ...valid, files };
    const updater = new EventEmitter();
    const calls = [];
    updater.downloadUpdate = async () => calls.push('download');
    updater.quitAndInstall = () => calls.push('install');
    const updates = new Updates(updater, { enabled: true, version: '1.7.7', isDirty: () => false, closeWindows: async () => true, record: () => {}, validateUpdate: item => isEditionUpdate(item, edition, 'win32', 'x64') });
    updater.emit('update-available', info);
    assert.equal(updates.state.status, 'error');
    await updates.action('download');
    updater.emit('update-downloaded', info);
    await updates.action('install');
    assert.deepEqual(calls, []);
  }
});
