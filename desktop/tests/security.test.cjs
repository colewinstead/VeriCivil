const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { assetPath, savePayload, websiteUrl } = require('../security.cjs');

test('asset access stays inside the packaged renderer and trusted origin', () => {
  const root = path.resolve('renderer');
  assert.equal(assetPath('vericivil://app/', root), path.join(root, 'index.html'));
  assert.equal(assetPath('vericivil://app/python/Super.py', root), path.join(root, 'python', 'Super.py'));
  for (const url of ['https://vericivil.com/', 'vericivil://other/secret', 'vericivil://app/..%2f..%2fprivate', 'vericivil://app/a%5cb', 'vericivil://app/%00']) {
    assert.throws(() => assetPath(url, root), url);
  }
});

test('save requests accept only supported bounded exports without a renderer-supplied path', () => {
  const data = new TextEncoder().encode('project');
  assert.equal(savePayload({ name: 'project.json', data }).data.toString(), 'project');
  for (const name of ['../project.json', 'C:\\project.json', 'project.exe', '/project.json', 'bad\0.json']) {
    assert.throws(() => savePayload({ name, data }), name);
  }
  assert.throws(() => savePayload({ name: 'project.json', data: 'not bytes' }));
  assert.throws(() => savePayload({ name: 'project.json', data: new Uint8Array(64 * 1024 * 1024 + 1) }));
});

test('external links are limited to the actual product website', () => {
  assert.equal(websiteUrl('https://vericivil.com/account'), true);
  for (const url of ['https://vericivil.com.evil.test/', 'file:///etc/passwd', 'javascript:alert(1)', 'https://x@vericivil.com/', 'http://vericivil.com/']) assert.equal(websiteUrl(url), false, url);
});

test('native saving replaces a file completely and cleans up failed replacements', async () => {
  const { mkdtemp, readFile, readdir, mkdir, rm } = require('node:fs/promises');
  const { tmpdir } = require('node:os');
  const { saveAtomically } = require('../files.cjs');
  const folder = await mkdtemp(path.join(tmpdir(), 'vericivil-save-'));
  try {
    const filename = path.join(folder, 'project.json');
    await saveAtomically(filename, Buffer.from('first'));
    await saveAtomically(filename, Buffer.from('replacement'));
    assert.equal(await readFile(filename, 'utf8'), 'replacement');
    const directory = path.join(folder, 'directory'); await mkdir(directory);
    await assert.rejects(saveAtomically(directory, Buffer.from('must not replace directory')));
    assert.deepEqual((await readdir(folder)).sort(), ['directory', 'project.json']);
    assert.equal(await readFile(filename, 'utf8'), 'replacement');
  } finally { await rm(folder, { recursive: true, force: true }); }
});
