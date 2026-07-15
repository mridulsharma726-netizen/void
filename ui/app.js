// ========================================
// VOID HUD - Frontend JavaScript (REWRITTEN)
// ========================================

const BACKEND_URL = "http://127.0.0.1:8000";

// ========================================
// STATE
// ========================================
const state = {
  isOnline: false,
  isListening: false,
  isSending: false,        // FIX: guard against concurrent sends
  isVoiceEnabled: false,
  isSoundEnabled: false,
  voidMode: "normal",
  startupVoiceSpoken: false,
};

// Interval handles so we can stop them if needed
const intervals = {
  time: null,
  health: null,
  stats: null,
};

// ========================================
// DOM HELPERS
// ========================================
function $(id) {
  return document.getElementById(id);
}

function log(msg) {
  console.log("[VOID] " + msg);
}

function logError(msg, err) {
  console.error("[VOID ERROR] " + msg, err || "");
}

// FIX: Properly escape HTML to prevent XSS
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// ========================================
// GLOBAL ERROR HANDLER
// ========================================
window.onerror = function (msg, url, line, col) {
  console.error("[VOID GLOBAL ERROR]", msg, "at line", line + ":" + col);
};

window.onunhandledrejection = function (event) {
  console.error("[VOID UNHANDLED PROMISE]", event.reason);
};

// ========================================
// API CALLS
// ========================================
async function apiCall(endpoint, options = {}) {
  try {
    const url = BACKEND_URL + endpoint;
    const response = await fetch(url, options);

    if (!response.ok) {
      throw new Error("HTTP " + response.status + " " + response.statusText);
    }

    const data = await response.json();
    return data;
  } catch (err) {
    logError("API call failed [" + endpoint + "]", err);
    showError("Connection error: " + endpoint);
    return null;
  }
}

// FIX: checkHealth no longer has a separate fetch — uses the shared apiCall helper
async function checkHealth() {
  return await apiCall("/health", { method: "GET" });
}

// FIX: fetchStats uses apiCall for consistent error handling; stale data is
// only returned if at least one successful fetch has occurred
let lastStats = null;

async function fetchStats() {
  const stats = await apiCall("/stats", { method: "GET" });
  if (stats) {
    lastStats = stats;
    return stats;
  }
  // Return stale data only if we have it; null otherwise
  return lastStats;
}

// FIX: fetchSystemCheck uses apiCall for consistent handling
async function fetchSystemCheck() {
  return await apiCall("/system-check", { method: "GET" });
}

async function sendChat(message) {
  return await apiCall("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
}

// FIX: speakText is fire-and-forget by design; callers don't need to await it
function speakText(text) {
  if (!state.isVoiceEnabled && !state.isSoundEnabled) return;
  apiCall("/speak", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  }).catch((err) => logError("TTS failed", err));
}

function stopSpeaking() {
  apiCall("/stop-speak", { method: "POST" }).catch((err) =>
    logError("Stop-speak failed", err)
  );
}

async function startListening() {
  if (state.isListening) return;

  state.isListening = true;
  updateStatus("listening");

  const micBtn = $("micBtn");
  if (micBtn) micBtn.classList.add("mic-listening");

  // FIX: try/finally guarantees cleanup even if apiCall throws unexpectedly
  try {
    const data = await apiCall("/listen", { method: "POST" });

    if (!data) return;

    if (data.reply) {
      const input = $("chatInput");
      if (input) {
        input.value = data.reply;
        input.focus();
      }
    } else if (data.meta && data.meta.status === "error") {
      showError("Microphone error: " + (data.meta.error || "Unknown error"));
    }
  } finally {
    // FIX: always reset listening state
    state.isListening = false;
    updateStatus(state.isOnline ? "online" : "offline");

    if (micBtn) {
      micBtn.classList.remove("mic-listening", "mic-processing");
      micBtn.classList.add("mic-idle");
      setTimeout(() => micBtn.classList.remove("mic-idle"), 500);
    }
  }
}

// ========================================
// ERROR DISPLAY
// ========================================
function showError(message) {
  logError(message);
  const container = $("chatMessages");
  if (!container) return;

  const div = document.createElement("div");
  div.className = "chat-message void error";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble error-bubble";
  // FIX: use textContent instead of innerHTML to avoid XSS
  bubble.textContent = message;

  div.appendChild(bubble);
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;

  setTimeout(() => {
    div.style.opacity = "0.5";
  }, 5000);
}

// ========================================
// UI UPDATES
// ========================================
function updateStatus(status) {
  const statusDot = $("statusDot");
  const statusText = $("statusText");

  if (!statusDot || !statusText) {
    logError("Status elements missing");
    return;
  }

  statusDot.className = "status-dot";

  switch (status) {
    case "online":
      statusDot.classList.add("online");
      statusText.textContent = "Online";
      state.isOnline = true;
      break;
    case "listening":
      statusDot.classList.add("listening");
      statusText.textContent = "Listening";
      state.isOnline = true;
      break;
    case "thinking":
      statusDot.classList.add("thinking");
      statusText.textContent = "Processing";
      state.isOnline = true;
      break;
    default:
      statusText.textContent = "Offline";
      state.isOnline = false;
  }
}

// FIX: Removed dual-ID lookups (e.g. $("uptime") || $("statUptime")).
// All element IDs are now consistent with a single canonical ID per stat.
function updateStats(stats) {
  if (!stats) return;

  const setEl = (id, value) => {
    const el = $(id);
    if (el && value !== undefined && value !== null) el.textContent = value;
  };

  const setBar = (id, pct) => {
    const bar = $(id);
    if (bar) bar.style.width = Math.max(0, Math.min(100, pct)) + "%";
  };

  // Uptime
  if (stats.uptime !== undefined) {
    const h = Math.floor(stats.uptime / 3600);
    const m = Math.floor((stats.uptime % 3600) / 60);
    setEl("statUptime", h + "h " + m + "m");
  } else {
    setEl("statUptime", "--");
  }

  setEl("statMessages", stats.messages ?? "0");
  setEl("statToolCalls", stats.tool_calls ?? "0");
  setEl("statMemoryFacts", stats.memory_facts ?? "0");
  setEl("statVoidLevel", stats.void_level ?? "0");

  if (stats.cpu_usage !== undefined) {
    const pct = Math.round(stats.cpu_usage);
    setEl("statCPU", pct + "%");
    setBar("barCPU", pct);
  }

  if (stats.ram_usage !== undefined) {
    const pct = Math.round(stats.ram_usage);
    setEl("statRAM", pct + "%");
    setBar("barRAM", pct);
  }

  if (stats.storage_used_gb !== undefined && stats.storage_total_gb > 0) {
    const pct = Math.round((stats.storage_used_gb / stats.storage_total_gb) * 100);
    setEl("statStorage", pct + "%");
    setBar("barStorage", pct);
  }

  if (stats.battery_percent !== undefined && stats.battery_percent !== null) {
    const pct = Math.round(stats.battery_percent);
    setEl("statBattery", pct + "%" + (stats.battery_charging ? " ⚡" : ""));
    setBar("barBattery", pct);
  }

  if (stats.network_online !== undefined) {
    setEl("statNetwork", stats.network_online ? "Online" : "Offline");
  }

  if (stats.cpu_temp !== undefined && stats.cpu_temp !== null) {
    setEl("statCPUTemp", Math.round(stats.cpu_temp) + "°C");
    setBar("barCPUTemp", Math.min((stats.cpu_temp / 120) * 100, 100));
  }

  if (stats.gpu_usage !== undefined && stats.gpu_usage !== null) {
    const pct = Math.round(stats.gpu_usage);
    setEl("statGPU", pct + "%");
    setBar("barGPU", pct);
  }
}

// FIX: updateSetupStatus moved OUT of the stats polling loop — setup rarely changes
async function updateSetupStatus() {
  const status = await fetchSystemCheck();
  if (!status) return;

  const iconMap = {
    python: "setupPython",
    requirements: "setupRequirements",
    ollama: "setupOllama",
    model: "setupModel",
  };

  let hasError = false;

  Object.entries(iconMap).forEach(([key, elId]) => {
    const icon = $(elId);
    if (!icon) return;
    if (status[key]) {
      icon.textContent = "✅";
      icon.className = "setup-status-icon ok";
    } else {
      icon.textContent = "❌";
      icon.className = "setup-status-icon error";
      hasError = true;
    }
  });

  const instructions = $("setupInstructions");
  if (instructions) instructions.classList.toggle("hidden", !hasError);
}

// ========================================
// SYSTEM INFO
// ========================================
// FIX: now uses apiCall for consistent error handling
async function loadSystemInfo() {
  const data = await apiCall("/system-info", { method: "GET" });
  const el = $("system-info-text");
  if (!el) return;
  el.innerText = data
    ? "OS: " + data.os + " | CPU: " + data.cpu
    : "OS: Unknown | CPU: Unknown";
}

// ========================================
// TIME
// ========================================
function updateTime() {
  const now = new Date();
  const timeEl = $("timeDisplay");
  const dateEl = $("dateDisplay");

  if (timeEl) {
    timeEl.textContent = now.toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  if (dateEl) {
    dateEl.textContent = now.toLocaleDateString("en-US", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  }
}

// ========================================
// CHAT UI HELPERS
// ========================================
// FIX: text is now escaped before insertion — no XSS possible
function addMessage(sender, text) {
  const container = $("chatMessages");
  if (!container) {
    logError("chatMessages container not found");
    return;
  }

  const div = document.createElement("div");
  div.className = "chat-message " + sender;

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.textContent = text; // safe: textContent, not innerHTML

  div.appendChild(bubble);
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function showTyping(show) {
  const indicator = $("typingIndicator");
  if (!indicator) return;
  indicator.classList.toggle("hidden", !show);
}

// FIX: disable/enable input and button during send
function setSendingState(sending) {
  state.isSending = sending;
  const btn = $("sendBtn");
  const input = $("chatInput");
  if (btn) btn.disabled = sending;
  if (input) input.disabled = sending;
}

// ========================================
// PREFERENCES
// ========================================
function loadPreferences() {
  const voiceEnabled = localStorage.getItem("voiceEnabled") === "true";
  state.isVoiceEnabled = voiceEnabled;
  const voiceToggle = $("voiceToggle");
  if (voiceToggle) voiceToggle.classList.toggle("active", voiceEnabled);

  const soundEnabled = localStorage.getItem("soundEnabled") === "true";
  state.isSoundEnabled = soundEnabled;
  const soundBtn = $("soundToggleBtn");
  if (soundBtn) {
    soundBtn.classList.toggle("active", soundEnabled);
    const label = soundBtn.querySelector("span:last-child");
    if (label) label.textContent = soundEnabled ? "Sound: ON" : "Sound: OFF";
  }

  const voidMode = localStorage.getItem("voidMode") || "normal";
  state.voidMode = voidMode;
  document.body.setAttribute("data-void-mode", voidMode);
  const modeSelect = $("voidModeSelect");
  if (modeSelect) modeSelect.value = voidMode;

  log("Preferences: voice=" + voiceEnabled + ", sound=" + soundEnabled + ", mode=" + voidMode);
}

// ========================================
// EVENT HANDLERS
// ========================================
async function handleSend() {
  // FIX: guard against concurrent sends
  if (state.isSending) return;

  const input = $("chatInput");
  if (!input) return;

  const message = input.value.trim();
  if (!message) return;

  addMessage("user", message);
  input.value = "";
  showTyping(true);
  updateStatus("thinking");
  setSendingState(true);

  try {
    const response = await sendChat(message);
    updateStatus(state.isOnline ? "online" : "offline");

    if (!response) return;

    updateStatus("online");

    if (response.reply) {
      addMessage("void", response.reply);
      // FIX: speakText is fire-and-forget; no invalid try/catch needed
      speakText(response.reply);
    } else {
      addMessage("void", "⚠️ No response received. Is Ollama running?");
    }
  } catch (err) {
    updateStatus("offline");
    addMessage("void", "⚠️ Error: " + err.message);
  } finally {
    showTyping(false);
    setSendingState(false);
  }
}

function handleMicClick() {
  startListening();
}

function handleVoiceToggle() {
  state.isVoiceEnabled = !state.isVoiceEnabled;
  const btn = $("voiceToggle");
  if (btn) btn.classList.toggle("active", state.isVoiceEnabled);
  if (!state.isVoiceEnabled) stopSpeaking();
  localStorage.setItem("voiceEnabled", state.isVoiceEnabled);
  log("Voice: " + state.isVoiceEnabled);
}

function handleClearChat() {
  const container = $("chatMessages");
  if (container) container.innerHTML = "";
  addMessage("void", "Chat cleared. How can I assist you?");
}

function handleSoundToggle() {
  state.isSoundEnabled = !state.isSoundEnabled;
  const soundBtn = $("soundToggleBtn");
  if (soundBtn) {
    soundBtn.classList.toggle("active", state.isSoundEnabled);
    const label = soundBtn.querySelector("span:last-child");
    if (label) label.textContent = state.isSoundEnabled ? "Sound: ON" : "Sound: OFF";
  }
  if (!state.isSoundEnabled) stopSpeaking();
  localStorage.setItem("soundEnabled", state.isSoundEnabled);
  log("Sound: " + state.isSoundEnabled);
}

function togglePanel(id, show) {
  const panel = $(id);
  if (panel) panel.classList.toggle("hidden", !show);
}

function handleVoidModeChange(mode) {
  state.voidMode = mode;
  document.body.setAttribute("data-void-mode", mode);
  localStorage.setItem("voidMode", mode);
  log("Mode: " + mode);
}

// ========================================
// SIDE PANEL ACTIONS (shared helper)
// ========================================
async function sendCommand(command) {
  const response = await sendChat(command);
  if (response && response.reply) addMessage("void", response.reply);
}

// ========================================
// FILE SCANNER
// ========================================
async function handleScanDirectory() {
  const scopeSelect = $("scopeSelect");
  const fileTableBody = $("fileTableBody");

  if (!scopeSelect || !fileTableBody) {
    logError("File scanner elements missing");
    return;
  }

  const scope = scopeSelect.value;
  fileTableBody.innerHTML = '<tr><td colspan="4" class="no-data">Scanning...</td></tr>';

  function renderFiles(files) {
    if (!files || files.length === 0) {
      fileTableBody.innerHTML = '<tr><td colspan="4" class="no-data">No files found</td></tr>';
      return;
    }

    // FIX: escapeHtml applied to all dynamic file data to prevent XSS
    const rows = files.map((file) =>
      "<tr>" +
      "<td>" + escapeHtml(file.name || "Unknown") + "</td>" +
      "<td>" + (file.size_kb !== undefined ? escapeHtml(String(file.size_kb)) + " KB" : "--") + "</td>" +
      "<td>" + escapeHtml(file.modified || "--") + "</td>" +
      "<td>" + escapeHtml(file.status || "OK") + "</td>" +
      "</tr>"
    );

    fileTableBody.innerHTML = rows.join("");
    log("Scan complete: " + files.length + " files");
  }

  // Try /file-status first, then fall back to /folder-status
  const primary = await apiCall("/file-status", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: scope }),
  });

  if (primary?.ok && primary?.file_status?.files) {
    renderFiles(primary.file_status.files);
    return;
  }

  const fallback = await apiCall("/folder-status", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: scope }),
  });

  if (fallback?.ok && fallback?.folder_status?.files) {
    renderFiles(fallback.folder_status.files);
  } else {
    fileTableBody.innerHTML = '<tr><td colspan="4" class="no-data">Error scanning directory</td></tr>';
  }
}

function handleFileSearch() {
  const searchInput = $("fileSearchInput");
  const fileTableBody = $("fileTableBody");
  if (!searchInput || !fileTableBody) return;

  const term = searchInput.value.toLowerCase().trim();
  fileTableBody.querySelectorAll("tr").forEach((row) => {
    const name = (row.cells[0]?.textContent || "").toLowerCase();
    row.style.display = !term || name.includes(term) ? "" : "none";
  });
}

// ========================================
// ATTACH EVENT LISTENERS
// ========================================
function attachEventListeners() {
  log("Attaching event listeners...");

  const on = (id, event, handler) => {
    const el = $(id);
    if (el) {
      el.addEventListener(event, handler);
    } else {
      logError("Element not found: #" + id);
    }
  };

  on("sendBtn", "click", handleSend);
  on("chatInput", "keypress", (e) => { if (e.key === "Enter") handleSend(); });
  on("micBtn", "click", handleMicClick);
  on("voiceToggle", "click", handleVoiceToggle);
  on("clearBtn", "click", handleClearChat);
  on("soundToggleBtn", "click", handleSoundToggle);

  on("faceLockBtn", "click", () => togglePanel("faceLockModal", true));
  on("closeFaceLock", "click", () => togglePanel("faceLockModal", false));
  on("fileStatusBtn", "click", () => togglePanel("fileStatusPanel", true));
  on("closeFileStatus", "click", () => togglePanel("fileStatusPanel", false));
  on("networkToolsBtn", "click", () => togglePanel("networkToolsPanel", true));
  on("closeNetworkTools", "click", () => togglePanel("networkToolsPanel", false));

  on("voidModeSelect", "change", (e) => handleVoidModeChange(e.target.value));

  on("showMemoryBtn", "click", () => sendCommand("show memory"));
  on("clearMemoryBtn", "click", () => sendCommand("clear memory"));
  on("repairBtn", "click", () => sendCommand("repair yourself"));
  on("diagnosticsBtn", "click", () => sendCommand("run diagnostics"));

  on("scanBtn", "click", handleScanDirectory);
  on("fileSearchInput", "input", handleFileSearch);
  on("fileSearchInput", "keypress", (e) => { if (e.key === "Enter") handleScanDirectory(); });

  // FIX: setupRefresh attached here alongside other listeners
  on("setupRefresh", "click", updateSetupStatus);

  log("Event listeners attached");
}

// ========================================
// BOOT SEQUENCE
// ========================================
function initBootSequence() {
  log("Running boot sequence...");

  setTimeout(() => {
    const boot = $("bootOverlay");
    if (boot) boot.style.display = "none";

    const welcome = $("welcomeOverlay");
    if (!welcome) return;

    welcome.classList.remove("hidden");

    // FIX: cleaner nested timeout with single transition
    setTimeout(() => {
      welcome.style.transition = "opacity 0.5s ease";
      welcome.style.opacity = "0";
      setTimeout(() => {
        welcome.classList.add("hidden");
        welcome.style.opacity = "";
        welcome.style.transition = "";
      }, 500);
    }, 2000);
  }, 2500);
}

// ========================================
// POLLING
// ========================================
function startPolling() {
  log("Starting polling...");

  // Time: every second
  updateTime();
  intervals.time = setInterval(updateTime, 1000);

  // Health: every 5 seconds
  // FIX: startup voice is triggered here using the health result already fetched —
  // no second checkHealth() call inside speakStartupMessage
  intervals.health = setInterval(async () => {
    const health = await checkHealth();
    const isHealthy = health && (health.status === "ok" || health.status === "healthy");

    if (isHealthy) {
      updateStatus("online");

      if (!state.startupVoiceSpoken) {
        state.startupVoiceSpoken = true;
        speakText("VOID online. All systems operational.");
        log("Startup voice spoken");
      }
    } else {
      updateStatus("offline");
    }
  }, 5000);

  // Stats: every 3 seconds (was 2s; reduced unnecessary load)
  // FIX: updateSetupStatus removed from here — it's fetched once on load + on button click
  intervals.stats = setInterval(async () => {
    const stats = await fetchStats();
    if (stats) updateStats(stats);
  }, 3000);
}

// ========================================
// MAIN ENTRY POINT
// ========================================
document.addEventListener("DOMContentLoaded", async function () {
  log("DOM ready — starting init...");

  loadPreferences();
  attachEventListeners();

  // Load system info and setup status once on startup
  await loadSystemInfo();
  await updateSetupStatus();

  initBootSequence();

  // FIX: do an immediate stats fetch before polling starts
  const initialStats = await fetchStats();
  if (initialStats) updateStats(initialStats);

  // Start polling after boot animation
  setTimeout(startPolling, 3000);

  // Welcome message
  setTimeout(() => {
    addMessage("void", "Welcome sir, how can I assist you today?");
  }, 3500);

  log("Init complete");
});