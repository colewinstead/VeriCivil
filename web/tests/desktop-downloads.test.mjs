import assert from 'node:assert/strict';
import test from 'node:test';
import { desktopDownloads } from '../lib/desktop-downloads.ts';

const asset = name => ({ name, browser_download_url: `https://github.com/colewinstead/VeriCivil/releases/download/v1.7.0/${name}` });
test('downloads prefer signed installers and retain unsigned/legacy fallbacks', () => {
  const data = desktopDownloads({ tag_name: 'v1.7.0', assets: [
    asset('VeriCivil-Superelevation-1.7.0-win-x64-unsigned.exe'), asset('VeriCivil-Superelevation-1.7.0-win-x64.exe'),
    asset('VeriCivil-Superelevation-1.7.0-mac-arm64-unsigned.dmg'), asset('Superelevation-Desktop-Preview-1.7.0-macOS-Intel.dmg'),
  ] });
  assert.equal(data.downloads.length, 3);
  assert.equal(data.downloads[0].unsigned, false);
  assert.equal(data.downloads[1].unsigned, true);
  assert.equal(data.downloads[2].unsigned, true);
});
test('downloads reject draft/prerelease metadata, foreign URLs, and wrong versions', () => {
  assert.equal(desktopDownloads({ tag_name: 'v1.7.0', draft: true, assets: [] }), null);
  assert.equal(desktopDownloads({ tag_name: 'v1.7.0', prerelease: true, assets: [] }), null);
  assert.equal(desktopDownloads({ tag_name: '<script>', assets: [] }), null);
  assert.deepEqual(desktopDownloads({ tag_name: 'v1.7.0', assets: [{ ...asset('VeriCivil-Superelevation-1.7.0-win-x64.exe'), browser_download_url: 'https://evil.example/setup.exe' }, asset('VeriCivil-Superelevation-1.6.0-win-x64.exe')] }).downloads, []);
});
