const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// Backend process
let backendProcess = null;
let mainWindow = null;

// Backend ready
let backendReady = false;

// Keep alive config
const BACKEND_PORT = 8000;
const BACKEND_HOST = '127.0.0.1';

// Backend path
const BACKEND_DIR = path.join(__dirname, 'backend');
const SERVER_PY = path.join(BACKEND_DIR, 'server.py');

// Ensure backend dir
if (!fs.existsSync(BACKEND_DIR)) {
  fs.mkdirSync(BACKEND_DIR, { recursive: true });
}

// Backend health check
async function checkBackend() {
  try {
    const fetch = (await import('node-fetch')).default;
    const response = await fetch(`http://${BACKEND_HOST}:${BACKEND_PORT}/health`, { timeout: 2000 });
    backendReady = response.ok;
    return backendReady;
  } catch {
    backendReady = false;
    return false;
  }
}

// Start backend subprocess
function startBackend() {
  if (backendProcess) return;

  console.log('[ELECTRON] Starting backend...');
  backendProcess = spawn('python', ['-m', 'uvicorn', 'server:app', '--host', BACKEND_HOST, '--port', BACKEND_PORT.toString(), '--reload'], {
    cwd: BACKEND_DIR,
    stdio: 'pipe'
  });

  backendProcess.stdout.on('data', (data) => console.log(`[BACKEND] ${data}`));
  backendProcess.stderr.on('data', (data) => console.error(`[BACKEND ERR] ${data}`));

  backendProcess.on('close', (code) => {
    console.log(`[BACKEND] Exited with code ${code}`);
    backendProcess = null;
  });
}

// Create main window
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, 'desktop/assets/icon.ico.png'),
    titleBarStyle: 'hiddenInset',
    autoHideMenuBar: true,
    backgroundColor: '#0a0a0a'
  });

  // Dev tools
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.loadFile(path.join(__dirname, 'renderer/index.html'));

  // Backend status IPC
  ipcMain.handle('backend-status', () => ({ ready: backendReady, port: BACKEND_PORT }));

  // Restart backend IPC
  ipcMain.handle('restart-backend', () => {
    if (backendProcess) {
      backendProcess.kill();
    }
    setTimeout(startBackend, 1000);
    return { status: 'restarting' };
  });

  // Open file dialog
  ipcMain.handle('select-directory', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory']
    });
    return result.canceled ? null : result.filePaths[0];
  });
}

// App events
app.whenReady().then(async () => {
  startBackend();
  
  // Poll backend ready
  const interval = setInterval(async () => {
    await checkBackend();
    if (backendReady) {
      clearInterval(interval);
      createWindow();
    }
  }, 1000);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (backendProcess) backendProcess.kill();
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  if (backendProcess) backendProcess.kill();
});

// Graceful shutdown
process.on('SIGINT', () => {
  if (backendProcess) backendProcess.kill();
  app.quit();
});
