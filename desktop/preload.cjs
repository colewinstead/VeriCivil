const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('vericivilDesktop', {
  preview: true,
  platform: process.platform,
  saveFile: (name, data) => ipcRenderer.invoke('desktop:save', { name, data }),
  onMenu: (callback) => {
    const listener = (_event, action) => callback(action);
    ipcRenderer.on('desktop:menu', listener);
    return () => ipcRenderer.removeListener('desktop:menu', listener);
  },
});
