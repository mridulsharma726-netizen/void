process.env.ELECTRON_DISABLE_SECURITY_WARNINGS = 'true';

const { app, BrowserWindow, dialog, ipcMain, Menu } = require("electron");
const path = require("path");
const { spawn, execSync } = require("child_process");
const http = require("http");

const isPackaged = app.isPackaged;
const ROOT_DIR = isPackaged
  ? path.resolve(path.dirname(app.getPath('exe')), '..', '..', '..')
  : path.resolve(__dirname, '..'); // VOID root
const BACKEND_HOST = "127.0.0.1";
const BACKEND_PORT = "8003";
const HEALTH_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}/health`;

let mainWindow;
let backendProc;

function log(level, message) {
  console.log(`[${new Date().toISOString()}] [${level.toUpperCase()}] ${message}`);
}

async function isBackendReady() {
  return new Promise(resolve => {
    const req = http.get(HEALTH_URL, { timeout: 2000 }, res => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => resolve(false));
  });
}

function cleanupPort8003() {
  if (process.platform !== 'win32') return;
  try {
    log('info', `Checking for zombie processes on port ${BACKEND_PORT}...`);
    const output = execSync(`netstat -ano | findstr :${BACKEND_PORT}`).toString();
    const lines = output.split('\n');
    const pidsToKill = new Set();
    for (const line of lines) {
      if (line.includes('LISTENING') || line.includes('TIME_WAIT')) {
        const parts = line.trim().split(/\s+/);
        const pid = parts[parts.length - 1];
        if (pid && pid !== '0' && !isNaN(pid)) {
          pidsToKill.add(parseInt(pid, 10));
        }
      }
    }
    for (const pid of pidsToKill) {
      log('info', `Killing zombie process tree for PID ${pid} holding port ${BACKEND_PORT}...`);
      try {
        execSync(`taskkill /f /t /pid ${pid}`);
      } catch (err) {
        log('warn', `Failed to kill PID ${pid}: ${err.message}`);
      }
    }
  } catch (e) {
    // netstat returns exit code 1 if no matches are found, which is normal
    log('info', `No active processes found on port ${BACKEND_PORT}.`);
  }
}

async function startBackend() {
  // Clear any existing zombie servers holding port
  cleanupPort8003();

  if (await isBackendReady()) {
    log('info', 'Backend already running');
    return true;
  }

  // Detect virtual environment python first
  const fs = require('fs');
  let pythonExe = 'python';
  const venvPython = path.join(ROOT_DIR, 'venv', 'Scripts', 'python.exe');
  if (fs.existsSync(venvPython)) {
    pythonExe = venvPython;
    log('info', `Detected virtual environment python at: ${pythonExe}`);
  } else {
    log('info', `Virtual environment python not found at ${venvPython}, using system python`);
  }

  log('info', `Starting backend with ${pythonExe}`);
  
  backendProc = spawn(pythonExe, [
    '-m', 'uvicorn', 
    'server.main:app', 
    '--host', BACKEND_HOST, 
    '--port', BACKEND_PORT,
    '--reload'  // Dev mode
  ], {
    cwd: ROOT_DIR,
    stdio: 'pipe',
    shell: true  // Windows compatibility
  });

  backendProc.stdout.on('data', data => log('backend', data.toString().trim()));
  backendProc.stderr.on('data', data => log('backend-err', data.toString().trim()));

  // Wait max 60s
  for (let i = 0; i < 120; i++) {
    if (await isBackendReady()) {
      log('success', 'Backend ready!');
      return true;
    }
    await new Promise(r => setTimeout(r, 500));
  }

  log('error', 'Backend failed to start');
  return false;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 850,
    titleBarStyle: 'hidden',
    resizable: true,
    alwaysOnTop: false,
    backgroundColor: '#050505',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false,  // Allow local file loads
      preload: path.join(__dirname, 'preload.js')
    }
  });

  const template = [
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' }
      ]
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    }
  ];
  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
  mainWindow.setMenuBarVisibility(false);

  // === IPC Window Controls ===
  ipcMain.on('window-minimize', () => {
    if (mainWindow) mainWindow.minimize();
  });
  ipcMain.on('window-maximize', () => {
    if (mainWindow) {
      if (mainWindow.isMaximized()) {
        mainWindow.unmaximize();
      } else {
        mainWindow.maximize();
      }
    }
  });
  ipcMain.on('window-close', () => {
    if (mainWindow) mainWindow.close();
  });

  // ✅ ABSOLUTE PATH TO UI
  const uiPath = path.join(ROOT_DIR, 'app', 'ui', 'index.html');
  log('info', `Loading UI: ${uiPath}`);
  
  // Verify file exists
  const fs = require('fs');
  if (!fs.existsSync(uiPath)) {
    dialog.showErrorBox('UI Missing', `Cannot find ${uiPath}\nCheck app/ui/index.html exists`);
    app.quit();
    return;
  }
  
  // Load secure API token for local authentication
  const configPath = path.join(ROOT_DIR, 'memory', 'data', 'secure_config.json');
  let token = '';
  try {
    if (fs.existsSync(configPath)) {
      const configData = JSON.parse(fs.readFileSync(configPath, 'utf8'));
      token = configData.api_token || '';
      log('info', 'Secure API token successfully retrieved.');
    } else {
      log('warn', `Secure config not found at ${configPath}. The backend will generate it.`);
    }
  } catch (e) {
    log('error', `Failed reading secure API token: ${e}`);
  }
  
  mainWindow.loadURL(require('url').format({
    pathname: uiPath,
    protocol: 'file:',
    slashes: true,
    query: { token: token }
  }));
  
  mainWindow.webContents.on('did-fail-load', (e, code, desc) => {
    log('error', `Load failed: ${code} ${desc}`);
  });
  
  mainWindow.webContents.on('did-finish-load', () => {
    log('success', 'UI loaded');
    // Open DevTools only once, in detached mode
    if (process.env.NODE_ENV !== 'production') {
      mainWindow.webContents.openDevTools({ mode: 'detach' });
    }
  });
}

app.whenReady().then(async () => {
  const { session } = require('electron');
  session.defaultSession.webRequest.onBeforeSendHeaders(
    { urls: ['ws://*/*', 'wss://*/*', 'http://127.0.0.1/*', 'http://localhost/*'] },
    (details, callback) => {
      const originKey = Object.keys(details.requestHeaders).find(k => k.toLowerCase() === 'origin');
      if (originKey && details.requestHeaders[originKey] === 'file://') {
        details.requestHeaders[originKey] = `http://${BACKEND_HOST}:${BACKEND_PORT}`;
      }
      callback({ cancel: false, requestHeaders: details.requestHeaders });
    }
  );

  const backendOk = await startBackend();
  if (!backendOk) {
    dialog.showErrorBox('Backend Error', 'Backend failed to start.\nCheck python main.py manually.');
    return;
  }
  createWindow();
});

app.on('window-all-closed', () => {
  if (backendProc) {
    log('info', 'Terminating backend process tree...');
    if (process.platform === 'win32') {
      try {
        execSync(`taskkill /f /t /pid ${backendProc.pid}`);
      } catch (e) {
        log('error', `Failed to recursively kill backend: ${e.message}`);
      }
    } else {
      backendProc.kill();
    }
  }
  app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
