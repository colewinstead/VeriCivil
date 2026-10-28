const { contextBridge, ipcRenderer } = require('electron');

function subscribe(channel, callback) {
  const listener = (_event, value) => callback(value);
  ipcRenderer.on(channel, listener);
  return () => ipcRenderer.removeListener(channel, listener);
}
contextBridge.exposeInMainWorld('vericivilDesktop', {
  access: 'free',
  platform: process.platform,
  saveFile: (name, data, saveAs = false) => ipcRenderer.invoke('desktop:save', { name, data, saveAs }),
  onMenu: callback => subscribe('desktop:menu', callback),
  onProject: callback => subscribe('desktop:project', callback),
  openProjectDialog: () => ipcRenderer.invoke('desktop:open'),
  projectOpened: (token, accepted) => ipcRenderer.invoke('desktop:project-opened', { token, accepted }),
  ready: () => ipcRenderer.invoke('desktop:ready'),
  newProject: () => ipcRenderer.invoke('desktop:new'),
  saveRecovery: content => ipcRenderer.invoke('desktop:recovery', content),
  resolveRecovery: restored => ipcRenderer.invoke('desktop:resolve-recovery', restored),
  workspaceState: (dirty, busy) => ipcRenderer.invoke('desktop:workspace', { dirty, busy }),
  reportRuntimeFailure: () => ipcRenderer.invoke('desktop:runtime-failure'),
  onUpdate: callback => subscribe('desktop:update', callback),
  updateState: () => ipcRenderer.invoke('desktop:update-state'),
  updateAction: action => ipcRenderer.invoke('desktop:update-action', action),
  openDownloads: () => ipcRenderer.invoke('desktop:downloads'),
});
