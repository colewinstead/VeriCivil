const { app, BrowserWindow, dialog, ipcMain, Menu, net, protocol, session, shell } = require('electron');
const { saveAtomically } = require('./files.cjs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { APP_URL, FILE_TYPES, assetPath, savePayload, websiteUrl } = require('./security.cjs');

protocol.registerSchemesAsPrivileged([{ scheme: 'vericivil', privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true } }]);
app.setName('VeriCivil Desktop Preview');

async function start() {
  await app.whenReady();
  protocol.handle('vericivil', (request) => {
    try { return net.fetch(pathToFileURL(assetPath(request.url, path.join(__dirname, 'renderer'))).href); }
    catch { return new Response('Not found', { status: 404 }); }
  });
  // The preview is deliberately offline; shared browser analytics cannot leave this process.
  session.defaultSession.webRequest.onBeforeRequest({ urls: ['http://*/*', 'https://*/*', 'ws://*/*', 'wss://*/*'] }, (_request, callback) => {
    callback({ cancel: true });
  });
  session.defaultSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  let window;
  const createWindow = async () => {
    window = new BrowserWindow({ width: 1440, height: 960, minWidth: 1040, minHeight: 700,
      title: 'Superelevation · VeriCivil Desktop Preview', show: false,
      backgroundColor: '#10201b',
      webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true },
    });
    window.webContents.setWindowOpenHandler(({ url }) => {
      if (websiteUrl(url)) void shell.openExternal(url);
      return { action: 'deny' };
    });
    window.webContents.on('will-navigate', (event, url) => { if (!url.startsWith(APP_URL)) event.preventDefault(); });
    window.webContents.on('will-prevent-unload', (event) => {
      if (dialog.showMessageBoxSync(window, { type: 'question', buttons: ['Keep working', 'Discard changes'],
        defaultId: 0, cancelId: 0, message: 'Close this unsaved project?', detail: 'Save your project before closing to keep your changes.' }) === 1) event.preventDefault();
    });
    await window.loadURL(APP_URL);
    window.show();
    return window;
  };
  ipcMain.handle('desktop:save', async (event, payload) => {
    if (!window || event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame || !event.senderFrame.url.startsWith(APP_URL)) throw new Error('Untrusted desktop request.');
    const file = savePayload(payload);
    const selected = await dialog.showSaveDialog(window, { defaultPath: file.name,
      filters: [{ name: FILE_TYPES[file.extension], extensions: [file.extension] }], properties: ['showOverwriteConfirmation'],
    });
    if (selected.canceled || !selected.filePath) return 'cancelled';
    await saveAtomically(selected.filePath, file.data);
    return 'saved';
  });
  const send = (action) => window?.webContents.send('desktop:menu', action);
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    ...(process.platform === 'darwin' ? [{ role: 'appMenu' }] : []),
    { label: 'File', submenu: [
      { label: 'New project', accelerator: 'CmdOrCtrl+N', click: () => send('new') },
      { label: 'Open project…', accelerator: 'CmdOrCtrl+O', click: () => send('open') },
      { label: 'Save project…', accelerator: 'CmdOrCtrl+S', click: () => send('save') },
      { type: 'separator' }, { role: process.platform === 'darwin' ? 'close' : 'quit' },
    ] },
    { role: 'editMenu' },
    { label: 'View', submenu: [{ role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' }, { type: 'separator' }, { role: 'togglefullscreen' }] },
    { role: 'windowMenu' },
    { role: 'help', submenu: [{ label: 'About this preview', click: () => dialog.showMessageBox(window, { message: 'VeriCivil Desktop Preview', detail: `Version ${app.getVersion()}\nLocal calculation runtime. Evaluation tools are enabled; production licensing and signed distribution are not included.\n\nIndependently verify engineering criteria, inputs, results, and deliverables.` }) }] },
  ]));
  await createWindow();
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) void createWindow(); });
  app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
  return window;
}

module.exports = { start };
