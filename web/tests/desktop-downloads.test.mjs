import assert from 'node:assert/strict';
import test from 'node:test';
import { desktopDownloads } from '../lib/desktop-downloads.ts';

const asset = name => ({ name, browser_download_url: `https://github.com/colewinstead/VeriCivil/releases/download/v1.7.0/${name}` });
test('downloads offer Windows only, preserving installer preference and legacy fallbacks', () => {
  const data = desktopDownloads({ tag_name: 'v1.7.0', assets: [
    asset('VeriCivil-Superelevation-1.7.0-win-x64-unsigned.exe'), asset('VeriCivil-Superelevation-1.7.0-win-x64.exe'),
    asset('VeriCivil-Superelevation-1.7.0-mac-arm64-unsigned.dmg'), asset('Superelevation-Desktop-Preview-1.7.0-macOS-Intel.dmg'),
  ] });
  assert.equal(data.downloads.length, 1);
  assert.equal(data.downloads[0].label, 'Windows x64');
  assert.equal(data.downloads[0].unsigned, false);
  for (const name of ['VeriCivil-Superelevation-1.7.0-win-x64-unsigned.exe', 'Superelevation-Desktop-Preview-1.7.0-Windows-x64.zip']) {
    const fallback = desktopDownloads({ tag_name: 'v1.7.0', assets: [asset(name)] }).downloads;
    assert.equal(fallback.length, 1);
    assert.equal(fallback[0].unsigned, true);
    assert.equal(fallback[0].portable, name.endsWith('.zip'));
  }
  assert.deepEqual(desktopDownloads({ tag_name: 'v1.7.0', assets: [
    asset('VeriCivil-Superelevation-1.7.0-mac-arm64.dmg'),
    asset('VeriCivil-Superelevation-1.7.0-mac-x64-unsigned.dmg'),
    asset('Superelevation-Desktop-Preview-1.7.0-macOS-Intel.dmg'),
  ] }).downloads, []);
});
test('downloads reject draft/prerelease metadata, foreign URLs, and wrong versions', () => {
  assert.equal(desktopDownloads({ tag_name: 'v1.7.0', draft: true, assets: [] }), null);
  assert.equal(desktopDownloads({ tag_name: 'v1.7.0', prerelease: true, assets: [] }), null);
  assert.equal(desktopDownloads({ tag_name: '<script>', assets: [] }), null);
  assert.deepEqual(desktopDownloads({ tag_name: 'v1.7.0', assets: [{ ...asset('VeriCivil-Superelevation-1.7.0-win-x64.exe'), browser_download_url: 'https://evil.example/setup.exe' }, asset('VeriCivil-Superelevation-1.6.0-win-x64.exe')] }).downloads, []);
});

test('public download buttons ignore unadvertised neutral installers and previews', () => {
  const assets = [
    asset('Superelevation-Calculator-1.7.0-win-x64-unsigned.exe'),
    asset('Superelevation-Calculator-1.7.0-mac-arm64-unsigned.dmg'),
    asset('Superelevation-Calculator-Desktop-Preview-1.7.0-macOS-Intel.dmg'),
  ];
  assert.deepEqual(desktopDownloads({ tag_name: 'v1.7.0', assets }).downloads, []);
  assets.push(asset('VeriCivil-Superelevation-1.7.0-win-x64-unsigned.exe'));
  assert.equal(desktopDownloads({ tag_name: 'v1.7.0', assets }).downloads.length, 1);
});
