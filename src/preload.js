const { contextBridge, ipcRenderer } = require('electron');

// Expose safe APIs to renderer
contextBridge.exposeInMainWorld('electronAPI', {
  backendStatus: () => ipcRenderer.invoke('backend-status'),
  restartBackend: () => ipcRenderer.invoke('restart-backend'),
  selectDirectory: () => ipcRenderer.invoke('select-directory')
});

// Window events
window.addEventListener('DOMContentLoaded', () => {
  // Backend status poll
  setInterval(async () => {
    if (window.electronAPI) {
      const status = await window.electronAPI.backendStatus();
      document.documentElement.setAttribute('data-backend-ready', status.ready);
    }
  }, 2000);
});
