const { app, BrowserWindow } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

// ========================================
// CONFIGURATION
// ========================================
const ROOT_DIR = path.join(__dirname, "..");
const BACKEND_HOST = "127.0.0.1";
const BACKEND_PORT = "8000";
const HEALTH_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}/health`;
// Phase 3: Poll every 500ms up to 15 times
const MAX_HEALTH_CHECKS = 15;
const HEALTH_CHECK_INTERVAL = 500;

// ========================================
// STATE
// ========================================
let win = null;
let backendProcess = null;
let hasSpokenStartup = false;

// ========================================
// LOGGING
// ========================================
function log(level, message) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [${level}] ${message}`);
}

function logInfo(message) {
  log("INFO", message);
}

function logError(message) {
  log("ERROR", message);
}

// ========================================
// BACKEND MANAGEMENT
// ========================================
function getPythonExecutable() {
  // Try to find venv python first
  const venvPaths = [
    path.join(ROOT_DIR, "venv", "Scripts", "python.exe"),
    path.join(ROOT_DIR, ".venv", "Scripts", "python.exe"),
    path.join(ROOT_DIR, "env", "Scripts", "python.exe"),
  ];

  for (const venvPath of venvPaths) {
    try {
      require("fs").accessSync(venvPath);
      return venvPath;
    } catch (e) {
      // Continue to next path
    }
  }

  // Fallback to system python
  return "python";
}

function isBackendRunning() {
  return new Promise((resolve) => {
    const http = require("http");
    const req = http.get(HEALTH_URL, (res) => {
      resolve(res.statusCode === 200);
    });
    req.on("error", () => {
      resolve(false);
    });
    req.setTimeout(1000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForBackend() {
  logInfo("[VOID BACKEND START] Starting backend process...");

  // Check if backend is already running first
  const alreadyRunning = await isBackendRunning();
  if (alreadyRunning) {
    logInfo("[VOID BACKEND] Already running, skipping spawn");
    return true;
  }

  const pythonExe = getPythonExecutable();
  logInfo("[VOID] Using Python: " + pythonExe);

  // Start backend with spawn (NOT exec, NO shell=true)
  // Phase 3: Uses uvicorn with correct parameters, NO --reload
  backendProcess = spawn(pythonExe, ["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"], {
    cwd: ROOT_DIR,
    stdio: ["ignore", "pipe", "pipe"],
    detached: false,
  });

  // Handle backend stdout
  backendProcess.stdout.on("data", (data) => {
    console.log(`[BACKEND] ${data.toString().trim()}`);
  });

  // Handle backend stderr
  backendProcess.stderr.on("data", (data) => {
    console.error(`[BACKEND ERROR] ${data.toString().trim()}`);
  });

  // Handle backend exit
  backendProcess.on("exit", (code) => {
    logInfo(`[VOID BACKEND STOP] Backend exited with code ${code}`);
    backendProcess = null;
  });

  // Handle spawn errors
  backendProcess.on("error", (err) => {
    logError(`[VOID BACKEND ERROR] Failed to start: ${err.message}`);
    backendProcess = null;
  });

  // Poll for health - Phase 3: every 500ms up to 15 times
  for (let i = 0; i < MAX_HEALTH_CHECKS; i++) {
    await new Promise((resolve) => setTimeout(resolve, HEALTH_CHECK_INTERVAL));

    const running = await isBackendRunning();
    if (running) {
      logInfo("[VOID HEALTH OK] Backend is healthy");
      return true;
    }

    logInfo(`[VOID HEALTH CHECK] Waiting for backend... (${i + 1}/${MAX_HEALTH_CHECKS})`);
  }

  logError("[VOID HEALTH ERROR] Backend failed to become healthy");
  return false;
}

function killBackend() {
  if (backendProcess) {
    logInfo("[VOID BACKEND STOP] Killing backend process...");

    // On Windows, use taskkill to kill process tree
    if (process.platform === "win32") {
      spawn("taskkill", ["/pid", backendProcess.pid.toString(), "/f", "/t"], {
        stdio: "ignore",
      });
    } else {
      backendProcess.kill("SIGTERM");
    }

    backendProcess = null;
  }
}

// ========================================
// WINDOW MANAGEMENT
// ========================================
function createWindow() {
  win = new BrowserWindow({
    width: 1200,
    height: 720,
    resizable: true,
    alwaysOnTop: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: false,  // 🛡️ Fix event blocking
      webSecurity: false,
      allowRunningInsecureContent: true,
    },
  });

  // Phase 3: Load the correct UI path
  const uiPath = path.join(ROOT_DIR, "ui", "index.html");
  logInfo("[VOID UI] Loading: " + uiPath);
  win.loadFile(uiPath);

  // Only open DevTools in development mode
  if (process.env.NODE_ENV === "development" || process.argv.includes("--dev")) {
    win.webContents.openDevTools();
  }

  // Handle window close
  win.on("closed", () => {
    win = null;
  });

  logInfo("[VOID UI INITIALIZED] Window created successfully");
}

// ========================================
// STARTUP SEQUENCE
// ========================================
async function startApp() {
  try {
    // Wait for backend to be healthy
    const healthy = await waitForBackend();

    if (!healthy) {
      // Phase 3: Show error dialog if backend fails
      const { dialog } = require("electron");
      dialog.showErrorBox("Backend Error", "Failed to start VOID backend. Please ensure Ollama is running and try again.");
      app.quit();
      return;
    }

    // Create window after backend is healthy
    createWindow();

  } catch (err) {
    logError(`Startup error: ${err.message}`);
    app.quit();
  }
}

// ========================================
// APP LIFECYCLE
// ========================================
app.whenReady().then(startApp);

app.on("window-all-closed", () => {
  killBackend();
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  killBackend();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// Prevent multiple instances
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });
}
