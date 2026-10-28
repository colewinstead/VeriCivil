const { app, BrowserWindow, dialog, ipcMain, Menu, net, protocol, session, shell } = require('electron');
const { saveAtomically } = require('./files.cjs');
const { Projects, projectContent } = require('./projects.cjs');
const { createDiagnostics } = require('./diagnostics.cjs');
const { Updates, availableVersion } = require('./updates.cjs');
const { randomUUID } = require('node:crypto');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { APP_URL, FILE_TYPES, assetPath, savePayload, websiteUrl } = require('./security.cjs');

protocol.registerSchemesAsPrivileged([{ scheme: 'vericivil', privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true } }]);
app.setName('VeriCivil Superelevation');
const launchFile = args => args.find(value => path.isAbsolute(value) && /\.(vericivil|json)$/i.test(value));
let startupFile = launchFile(process.argv.slice(1));
let openFile;
app.on('open-file', (event, file) => { event.preventDefault(); if (openFile) void openFile(file); else startupFile = file; });

async function start() {
  if (!app.requestSingleInstanceLock()) { app.quit(); return null; }
  app.setAppUserModelId('com.vericivil.superelevation');
  const diagnostics = createDiagnostics(path.join(app.getPath('userData'), 'logs'), { app: app.getVersion(), electron: process.versions.electron, ...require('./release-info.json') });
  diagnostics.record('startup');
  process.on('uncaughtException', error => { diagnostics.record('native_uncaught', error.code); dialog.showErrorBox('VeriCivil needs to restart', 'An unexpected application error occurred. A local recovery snapshot may be available after restarting. Export diagnostics from Help if this repeats.'); app.exit(1); });
  process.on('unhandledRejection', error => diagnostics.record('native_rejection', error?.code));
  await app.whenReady();
  const projects = new Projects(app.getPath('userData'));
  await projects.initialize();
  let recovery;
  try { recovery = await projects.recovery(); }
  catch (error) { recovery = { name: 'unreadable recovery snapshot', content: '' }; diagnostics.record('recovery_read_failed', error.code); dialog.showErrorBox('Recovery could not be read', 'The recovery file could not be read. It will be preserved until you explicitly discard it. Your saved projects are unchanged.'); }
  let recoveryPending = !!recovery;
  let window, currentFile, opening, rendererReady = false, dirty = false, busy = false, closingForUpdate = false;
  const send = action => window?.webContents.send('desktop:menu', action);
  const showError = (message, error) => { diagnostics.record('file_operation_failed', error?.code); if (window && !window.isDestroyed()) void dialog.showMessageBox(window, { type: 'error', message, detail: error?.message || 'Please try again.' }); };
  protocol.handle('vericivil', request => {
    try { return net.fetch(pathToFileURL(assetPath(request.url, path.join(__dirname, 'renderer'))).href); }
    catch { return new Response('Not found', { status: 404 }); }
  });
  // Network services live in the main process; engineering data stays in the offline renderer.
  session.defaultSession.webRequest.onBeforeRequest({ urls: ['http://*/*', 'https://*/*', 'ws://*/*', 'wss://*/*'] }, (_request, callback) => callback({ cancel: true }));
  session.defaultSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  const createWindow = async () => {
    rendererReady = false;
    opening = null;
    if (currentFile) { startupFile = currentFile; currentFile = null; }
    window = new BrowserWindow({ width: 1440, height: 960, minWidth: 1040, minHeight: 700,
      title: 'Superelevation · VeriCivil', show: false, backgroundColor: '#10201b', icon: path.join(__dirname, 'icon.png'),
      webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true },
    });
    window.webContents.setWindowOpenHandler(({ url }) => { if (websiteUrl(url)) void shell.openExternal(url); return { action: 'deny' }; });
    window.webContents.on('will-navigate', (event, url) => { if (!url.startsWith(APP_URL)) event.preventDefault(); });
    window.webContents.on('will-prevent-unload', event => {
      if (dialog.showMessageBoxSync(window, { type: 'question', buttons: ['Keep working', 'Discard changes'], defaultId: 0, cancelId: 0,
        message: 'Close this unsaved project?', detail: 'Save your project before closing to keep your changes.' }) === 1) event.preventDefault();
    });
    window.webContents.on('render-process-gone', (_event, details) => { diagnostics.record('renderer_gone', details.reason); dirty = true; showError('The workspace stopped. Restart VeriCivil to recover your work.'); });
    await window.loadURL(APP_URL);
    window.show();
    return window;
  };
  app.on('second-instance', (_event, args) => {
    if (window?.isMinimized()) window.restore();
    window?.focus();
    const file = launchFile(args.slice(1));
    if (file) void openFile(file);
  });
  openFile = async file => {
    if (!rendererReady) { startupFile = file; return; }
    let request;
    try {
      if (recoveryPending) throw new Error('Restore or discard the recovery snapshot before opening another project.');
      if (opening || busy) throw new Error('Wait for the current operation to finish.');
      request = { file, token: randomUUID() };
      opening = request;
      const project = await projects.read(file);
      window.webContents.send('desktop:project', { ...project, token: opening.token });
    } catch (error) { if (request && opening === request) opening = null; showError('Could not open the project', error); }
  };
  const handle = (channel, handler) => ipcMain.handle(channel, (event, payload) => {
    if (!window || event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame || !event.senderFrame.url.startsWith(APP_URL)) throw new Error('Untrusted desktop request.');
    return handler(payload);
  });
  const openDialog = async () => {
    const chosen = await dialog.showOpenDialog(window, { filters: [{ name: 'VeriCivil project', extensions: ['vericivil', 'json'] }], properties: ['openFile'] });
    if (!chosen.canceled && chosen.filePaths[0]) await openFile(chosen.filePaths[0]);
  };
  handle('desktop:open', openDialog);
  handle('desktop:save', async payload => {
    const file = savePayload(payload);
    const isProject = ['json', 'vericivil'].includes(file.extension);
    if (isProject) projectContent(file.data.toString('utf8'));
    const selected = isProject && currentFile && !payload.saveAs ? { filePath: currentFile } : await dialog.showSaveDialog(window, {
      defaultPath: isProject && currentFile ? currentFile : file.name,
      filters: [{ name: FILE_TYPES[file.extension], extensions: [file.extension] }], properties: ['showOverwriteConfirmation'],
    });
    if (selected.canceled || !selected.filePath) return 'cancelled';
    await saveAtomically(selected.filePath, file.data);
    if (isProject) { currentFile = selected.filePath; await projects.remember(currentFile); buildMenu(); }
    return 'saved';
  });
  handle('desktop:ready', () => {
    rendererReady = true;
    if (startupFile && !recoveryPending) { const file = startupFile; startupFile = null; setImmediate(() => void openFile(file)); }
    return recoveryPending ? recovery : null;
  });
  handle('desktop:project-opened', async payload => {
    if (!opening || payload?.token !== opening.token || typeof payload.accepted !== 'boolean') throw new Error('Unknown project open request.');
    if (payload.accepted) { currentFile = opening.file; await projects.remember(currentFile); buildMenu(); }
    opening = null;
  });
  handle('desktop:new', async () => { if (recoveryPending) throw new Error('Resolve the recovery snapshot first.'); currentFile = null; await projects.saveRecovery(null); });
  handle('desktop:recovery', content => recoveryPending ? undefined : projects.saveRecovery(content));
  handle('desktop:resolve-recovery', async restored => { if (typeof restored !== 'boolean') throw new Error('Invalid recovery decision.'); if (!restored) await projects.saveRecovery(null); recoveryPending = false; recovery = null; startupFile = null; });
  handle('desktop:workspace', payload => { if (typeof payload?.dirty !== 'boolean' || typeof payload.busy !== 'boolean') throw new Error('Invalid workspace state.'); dirty = payload.dirty; busy = payload.busy; });
  handle('desktop:runtime-failure', () => diagnostics.record('worker_failed'));
  const { autoUpdater } = require('electron-updater');
  const config = require('./desktop-config.json');
  if (config.signedUpdates) autoUpdater.channel = config.updateChannel;
  const updates = new Updates(autoUpdater, { enabled: app.isPackaged && config.signedUpdates === true, version: app.getVersion(), isDirty: () => dirty || busy || recoveryPending,
    discover: async () => {
      const response = await fetch('https://api.github.com/repos/colewinstead/VeriCivil/releases/latest', { headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'VeriCivil-desktop' }, signal: AbortSignal.timeout(10000) });
      if (!response.ok) throw new Error('Release check unavailable.');
      return availableVersion(await response.json(), app.getVersion());
    },
    closeWindows: () => new Promise(resolve => {
      if (!window || window.isDestroyed()) return resolve(true);
      closingForUpdate = true;
      const target = window;
      const closed = () => { clearTimeout(timer); resolve(true); };
      const timer = setTimeout(() => { closingForUpdate = false; target.removeListener('closed', closed); resolve(false); }, 300);
      target.once('closed', closed);
      target.close();
    }), record: diagnostics.record,
  });
  updates.on('state', state => {
    if (state.status === 'error' && window?.isDestroyed()) { closingForUpdate = false; void createWindow().catch(error => showError('Restart VeriCivil to continue', error)); }
    else if (window && !window.isDestroyed()) window.webContents.send('desktop:update', state);
  });
  handle('desktop:update-state', () => updates.state);
  handle('desktop:update-action', action => updates.action(action));
  handle('desktop:downloads', () => shell.openExternal('https://vericivil.com/downloads'));
  const buildMenu = () => Menu.setApplicationMenu(Menu.buildFromTemplate([
    ...(process.platform === 'darwin' ? [{ role: 'appMenu' }] : []),
    { label: 'File', submenu: [
      { label: 'New project', accelerator: 'CmdOrCtrl+N', click: () => send('new') },
      { label: 'Open project…', accelerator: 'CmdOrCtrl+O', click: () => void openDialog().catch(error => showError('Could not open the project', error)) },
      { label: 'Open recent', submenu: projects.recent.length ? projects.recent.map(file => ({ label: path.basename(file), toolTip: file, click: () => void openFile(file) })) : [{ label: 'No recent projects', enabled: false }] },
      { label: 'Save project', accelerator: 'CmdOrCtrl+S', click: () => send('save') },
      { label: 'Save project as…', accelerator: 'CmdOrCtrl+Shift+S', click: () => send('save-as') },
      { type: 'separator' }, { role: process.platform === 'darwin' ? 'close' : 'quit' },
    ] },
    { role: 'editMenu' },
    { label: 'View', submenu: [{ role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' }, { type: 'separator' }, { role: 'togglefullscreen' }] },
    { role: 'windowMenu' },
    { role: 'help', submenu: [
      { label: 'Check for updates…', click: () => { send('updates'); void updates.action('check'); } },
      { label: 'Download latest version', click: () => void shell.openExternal('https://vericivil.com/downloads') },
      { label: 'Export diagnostics…', click: async () => {
        try {
          const selected = await dialog.showSaveDialog(window, { defaultPath: 'vericivil-diagnostics.json', filters: [{ name: 'Diagnostic report', extensions: ['json'] }] });
          if (!selected.canceled && selected.filePath) await saveAtomically(selected.filePath, diagnostics.bundle());
        } catch (error) { showError('Could not export diagnostics', error); }
      } },
      { label: 'About VeriCivil', click: () => dialog.showMessageBox(window, { message: 'VeriCivil Superelevation', detail: `Version ${app.getVersion()}\nCurrent desktop tools are free. Engineering calculations and project recovery stay on this computer.\n\nIndependently verify engineering criteria, inputs, results, and deliverables.` }) },
    ] },
  ]));
  buildMenu();
  await createWindow();
  if (app.isPackaged) {
    const firstCheck = setTimeout(() => void updates.action('check'), 10000); firstCheck.unref();
    const checks = setInterval(() => void updates.action('check'), 6 * 60 * 60 * 1000); checks.unref();
  }
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) void createWindow(); });
  app.on('window-all-closed', () => { if (process.platform !== 'darwin' && !closingForUpdate) app.quit(); });
  return window;
}
module.exports = { start };
