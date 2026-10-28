const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { EventEmitter } = require('node:events');
const { Projects, projectContent } = require('../projects.cjs');
const { createDiagnostics } = require('../diagnostics.cjs');
const { Updates, availableVersion, closeForUpdate } = require('../updates.cjs');
const project = JSON.stringify({ version: 5, vars: { project_name: 'Private project' }, last_results: { retained: 42 } });

test('recovery survives restart, ordered clears win, and project reads are bounded', async t => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'vericivil-project-test-'));
  t.after(() => fs.rm(directory, { recursive: true, force: true }));
  const store = new Projects(directory);
  await store.initialize();
  assert.equal(await store.recovery(), null);
  await store.saveRecovery(project);
  const restarted = new Projects(directory);
  await restarted.initialize();
  assert.equal((await restarted.recovery()).content, project);
  const file = path.join(directory, 'test.vericivil');
  await fs.writeFile(file, project);
  assert.equal((await store.read(file)).content, project);
  await store.remember(file);
  await store.remember(file);
  const recent = new Projects(directory);
  await recent.initialize();
  assert.deepEqual(recent.recent, [file]);
  const pending = store.saveRecovery(project);
  const clear = store.saveRecovery(null);
  await Promise.all([pending, clear]);
  assert.equal(await store.recovery(), null);
  await fs.writeFile(path.join(directory, 'recovery.json'), '{broken');
  await assert.rejects(store.recovery());
  assert.equal(await fs.readFile(path.join(directory, 'recovery.json'), 'utf8'), '{broken');
  await store.saveRecovery(null);
  assert.throws(() => projectContent('{broken'));
  assert.throws(() => projectContent('{"version":5}'));
  await assert.rejects(store.read('relative.vericivil'));
  await assert.rejects(store.read(path.join(directory, 'test.exe')));
  const large = path.join(directory, 'large.json');
  const handle = await fs.open(large, 'w');
  await handle.truncate(64 * 1024 * 1024 + 1);
  await handle.close();
  await assert.rejects(store.read(large), /64 MiB/);
});

test('diagnostics contain fixed events and versions without private file/error content', async t => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'vericivil-log-test-'));
  t.after(() => fs.rm(directory, { recursive: true, force: true }));
  const log = createDiagnostics(directory, { app: '1.7.0' });
  log.record('worker_failed', 'ERR_WORKER');
  log.record('C:/private/project.xml', 'token secret');
  const bundle = log.bundle();
  assert.match(bundle, /ERR_WORKER/);
  assert.match(bundle, /1.7.0/);
  assert.doesNotMatch(bundle, /project.xml|token secret|Private project/);
  await fs.writeFile(path.join(directory, 'desktop.log'), 'x'.repeat(257 * 1024));
  log.record('startup');
  assert.ok((await fs.stat(path.join(directory, 'desktop.log'))).size < 1024);
  assert.ok((await fs.stat(path.join(directory, 'desktop.log.previous'))).size > 256 * 1024);
});

function updaterFixture(enabled = true) {
  const updater = new EventEmitter();
  const calls = [];
  updater.checkForUpdates = async () => { calls.push('check'); updater.emit('update-available', { version: '1.8.0', releaseNotes: 'Changes' }); };
  updater.downloadUpdate = async () => { calls.push('download'); updater.emit('download-progress', { percent: 50 }); updater.emit('update-downloaded', { version: '1.8.0' }); };
  updater.quitAndInstall = () => calls.push('install');
  let dirty = false, closed = true;
  const updates = new Updates(updater, { enabled, version: '1.7.0', isDirty: () => dirty, closeWindows: async () => closed, record: () => {} });
  return { updates, updater, calls, setDirty: value => { dirty = value; }, setClosed: value => { closed = value; } };
}

test('updates require signed build, user download consent, and a saved workspace before restart', async () => {
  const unsigned = updaterFixture(false);
  for (const action of ['check', 'download', 'install']) await unsigned.updates.action(action);
  assert.deepEqual(unsigned.calls, []);
  const f = updaterFixture();
  assert.equal(f.updater.autoDownload, false);
  assert.equal(f.updater.autoInstallOnAppQuit, false);
  assert.equal(f.updater.allowDowngrade, false);
  await f.updates.action('install');
  assert.deepEqual(f.calls, []);
  await f.updates.action('check');
  assert.equal(f.updates.state.status, 'available');
  assert.deepEqual(f.calls, ['check']);
  await f.updates.action('download');
  assert.equal(f.updates.state.status, 'downloaded');
  f.setDirty(true);
  await f.updates.action('install');
  assert.match(f.updates.state.message, /Save your project/);
  assert.deepEqual(f.calls, ['check', 'download']);
  f.setDirty(false); f.setClosed(false);
  await f.updates.action('install');
  assert.deepEqual(f.calls, ['check', 'download']);
  f.setClosed(true);
  await f.updates.action('install');
  assert.deepEqual(f.calls, ['check', 'download', 'install']);
  await assert.rejects(f.updates.action('unknown'));
});

test('offline/invalid-signature update failures stay recoverable and do not install', async () => {
  const f = updaterFixture();
  f.updater.checkForUpdates = async () => { throw Object.assign(new Error('private path'), { code: 'ENETUNREACH' }); };
  await f.updates.action('check');
  assert.equal(f.updates.state.status, 'error');
  assert.doesNotMatch(f.updates.state.message, /private path/);
  f.updater.emit('error', Object.assign(new Error('signature'), { code: 'ERR_UPDATER_INVALID_SIGNATURE' }));
  await f.updates.action('install');
  assert.deepEqual(f.calls, []);
});

test('unsigned apps can discover new releases but cannot download or install them', async () => {
  assert.equal(availableVersion({ tag_name: 'v1.10.0' }, '1.9.9'), '1.10.0');
  assert.equal(availableVersion({ tag_name: 'v1.7.0' }, '1.7.0'), null);
  assert.equal(availableVersion({ tag_name: 'v1.6.0' }, '1.7.0'), null);
  assert.throws(() => availableVersion({ tag_name: 'v1.8.0', prerelease: true }, '1.7.0'));
  assert.throws(() => availableVersion({ tag_name: 'garbage' }, '1.7.0'));
  const f = updaterFixture(false);
  f.updates.discover = async () => '1.8.0';
  await f.updates.action('check');
  assert.equal(f.updates.state.status, 'manual');
  await f.updates.action('download');
  await f.updates.action('install');
  assert.deepEqual(f.calls, []);
  f.updates.discover = async () => { throw new Error('offline'); };
  await f.updates.action('check');
  assert.equal(f.updates.state.status, 'disabled');
});

test('update closing waits for the native close result and respects the unsaved-work choice', async () => {
  for (const discard of [false, true]) {
    const window = new EventEmitter();
    window.webContents = new EventEmitter();
    window.isDestroyed = () => false;
    window.close = () => {
      window.webContents.emit('will-prevent-unload', { defaultPrevented: discard });
      if (discard) setImmediate(() => window.emit('closed'));
    };
    assert.equal(await closeForUpdate(window), discard);
    assert.equal(window.listenerCount('closed'), 0);
    assert.equal(window.webContents.listenerCount('will-prevent-unload'), 0);
  }
  assert.equal(await closeForUpdate(null), true);
});
