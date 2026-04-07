// ========================================
// VOID HUD - Frontend JavaScript (STABILIZED)
// ========================================

const BACKEND_URL = "http://127.0.0.1:8000";

console.log("[VOID] Loading...");

// ========================================
// STATE
// ========================================
const state = {
  isOnline: false,
  isListening: false,
  isVoiceEnabled: false,
  isSoundEnabled: false,
  voidMode: 'normal',
  startupVoiceSpoken: false
};

// ========================================
// GLOBAL ERROR HANDLER - STEP 1 COMPLETE
// ========================================
window.onerror = function(msg, url, line, col, error) {
  console.error("GLOBAL ERROR:", msg, "at", line + ":" + col);
};

log("Global error handler active.");
};
</xai:function_call

<xai:function_call name="edit_file">
<parameter name="path">c:/Users/HP/OneDrive/Desktop/void/VOID/ui/app.js

// ========================================
// DOM HELPERS - SAFE ACCESS
// ========================================
function $(id) {
  const el = document.getElementById(id);
  return el;
}

function log(msg) {
  console.log("[VOID] " + msg);
}

function logError(msg, err) {
  console.error("[VOID ERROR] " + msg, err || "");
}

function logElement(id) {
  const el = $(id);
  console.log("[VOID] Element '" + id + "':", el ? "FOUND" : "MISSING");
  return el;
}

// ========================================
// API CALLS - WITH ENHANCED LOGGING
// ========================================
async function apiCall(endpoint, options = {}) {
  try {
    const url = BACKEND_URL + endpoint;
    console.log("FETCH REQUEST:", options.method || "GET", url);
    
    const response = await fetch(url, options);
    console.log("FETCH STATUS:", response.status, response.statusText);
    
    if (!response.ok) {
      throw new Error("HTTP " + response.status + " " + response.statusText);
    }
    
    const data = await response.json();
    console.log("API RESPONSE:", endpoint, data);
    return data;
  } catch (err) {
    logError("API call failed: " + endpoint, err);
    // Show error to user
    showError("Connection error: " + endpoint);
    return null;
  }
}

async function checkHealth() {
  return await apiCall("/health", { method: "GET" });
}

let lastStats = null; // Global cache for stats

async function fetchSystemCheck() {
  try {
    const res = await fetch("http://127.0.0.1:8000/system-check");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const status = await res.json();
    console.log("[SYSTEM CHECK]", status);
    return status;
  } catch (err) {
    console.error("[SYSTEM CHECK ERROR]", err);
    return null;
  }
}

async function updateSetupStatus() {
  const status = await fetchSystemCheck();
  if (!status) return;

  const icons = {
    python: $("setupPython"),
    requirements: $("setupRequirements"),
    ollama: $("setupOllama"),
    model: $("setupModel")
  };

  const instructions = $("setupInstructions");

  let hasError = false;
  Object.keys(status).forEach(key => {
    const icon = icons[key];
    if (icon) {
      if (status[key]) {
        icon.textContent = "✅";
        icon.className = "setup-status-icon ok";
      } else {
        icon.textContent = "❌";
        icon.className = "setup-status-icon error";
        hasError = true;
      }
    }
  });

  if (instructions) {
    instructions.classList.toggle("hidden", !hasError);
  }
}

async function fetchStats() {
  console.log("FETCHING STATS...");
  try {
    const res = await fetch("http://127.0.0.1:8000/stats");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const stats = await res.json();
    console.log("STATS DATA:", stats);
    lastStats = stats; // Cache successful fetch
    return stats;
  } catch (err) {
    console.error("STATS FETCH ERROR:", err);
    return lastStats; // Return cached on fail (panels hold value)
  }
}

async function sendChat(message) {
  console.log("CHAT INPUT:", message);
  
  const data = await apiCall("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: message })
  });
  
  console.log("CHAT OUTPUT:", data);
  return data;
}

async function speakText(text) {
  // Speak if EITHER voice mode OR sound mode is enabled
  if (!state.isVoiceEnabled && !state.isSoundEnabled) return;
  
  console.log("TTS REQUEST:", text);
  
  const result = await apiCall("/speak", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: text })
  });
  
  console.log("TTS RESULT:", result);
}

async function stopSpeaking() {
  await apiCall("/stop-speak", { method: "POST" });
}

async function startListening() {
  if (state.isListening) return;

  state.isListening = true;
  updateStatus("listening");

  // Visual: mic button → listening state
  const micBtn = $("micBtn");
  if (micBtn) micBtn.classList.add("mic-listening");

  console.log("[STT] Starting listening...");

  const data = await apiCall("/listen", { method: "POST" });

  state.isListening = false;
  updateStatus(state.isOnline ? "online" : "offline");

  // Visual: mic button → idle
  if (micBtn) {
    micBtn.classList.remove("mic-listening", "mic-processing");
    micBtn.classList.add("mic-idle");
    setTimeout(() => { if (micBtn) micBtn.classList.remove("mic-idle"); }, 500);
  }

  console.log("[VOID MIC RESPONSE]", JSON.stringify(data));

  if (!data) {
    // apiCall already showed error bubble
    return;
  }

  if (data.reply) {
    const input = $("chatInput");
    if (input) {
      input.value = data.reply;
      input.focus();
    }
    // Don't auto-send — let user review
  } else if (data.meta && data.meta.status === "error") {
    showError("Microphone error: " + (data.meta.error || "Unknown error"));
  }
}

// ========================================
// ERROR DISPLAY
// ========================================
function showError(message) {
  console.error("[VOID ERROR DISPLAY]", message);
  
  // Create error bubble
  const container = $("chatMessages");
  if (!container) return;
  
  const div = document.createElement("div");
  div.className = "chat-message void error";
  div.innerHTML = '<div class="message-bubble error-bubble">' + message + '</div>';
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  
  // Auto-remove after 5 seconds
  setTimeout(() => {
    div.style.opacity = "0.5";
  }, 5000);
}

// ========================================
// UI UPDATES - SAFE
// ========================================
function updateStatus(status) {
  const statusDot = $("statusDot");
  const statusText = $("statusText");
  
  // Guard against null elements
  if (!statusDot || !statusText) {
    logError("Status elements missing", null);
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

function updateStats(stats) {
  console.log("STATS RAW RESPONSE:", stats);
  
  if (!stats) {
    console.log("[VOID] No stats data to update");
    return;
  }

  // CORE STATS PANEL - Exact task fields (left panel priority)
  const uptimeEl = $("uptime") || $("statUptime");
  if (uptimeEl && stats.uptime !== undefined) {
    const secs = stats.uptime;
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    uptimeEl.textContent = h + "h " + m + "m";
  } else if (uptimeEl) {
    uptimeEl.textContent = "--";
  }

async function loadSystemInfo() {
  try {
    const res = await fetch("http://127.0.0.1:8000/system-info");
    const data = await res.json();

    const el = $("system-info-text");
    if (el) {
      el.innerText = `OS: ${data.os} | CPU: ${data.cpu}`;
    }
  } catch (err) {
    console.error("System info error:", err);
    const el = $("system-info-text");
    if (el) el.innerText = "OS: Unknown | CPU: Unknown";
  }
}

  const messagesEl = $("messages") || $("statMessages");
  if (messagesEl && stats.messages !== undefined) {
    messagesEl.textContent = stats.messages;
  } else if (messagesEl) {
    messagesEl.textContent = "0";
  }

  const toolCallsEl = $("tool_calls") || $("statToolCalls");
  if (toolCallsEl && stats.tool_calls !== undefined) {
    toolCallsEl.textContent = stats.tool_calls;
  } else if (toolCallsEl) {
    toolCallsEl.textContent = "0";
  }

  const memoryEl = $("memory") || $("statMemoryFacts");
  if (memoryEl && stats.memory_facts !== undefined) {
    memoryEl.textContent = stats.memory_facts;
  } else if (memoryEl) {
    memoryEl.textContent = "0";
  }

  const levelEl = $("level") || $("statVoidLevel");
  if (levelEl && stats.void_level !== undefined) {
    levelEl.textContent = stats.void_level;
  } else if (levelEl) {
    levelEl.textContent = "0";
  }

  // CPU - strict !== undefined check, 0 valid
  const cpuEl = $("statCPU");
  const cpuBar = $("barCPU");
  if (cpuEl && stats.cpu_usage !== undefined) {
    const cpuPct = Math.round(stats.cpu_usage);
    cpuEl.textContent = cpuPct + "%";
    if (cpuBar) cpuBar.style.width = Math.max(0, Math.min(100, cpuPct)) + "%";
  }

  // RAM - strict !== undefined check  
  const ramEl = $("statRAM");
  const ramBar = $("barRAM");
  if (ramEl && stats.ram_usage !== undefined) {
    const ramPct = Math.round(stats.ram_usage);
    ramEl.textContent = ramPct + "%";
    if (ramBar) ramBar.style.width = Math.max(0, Math.min(100, ramPct)) + "%";
  }

  // Storage/Disk % calculation
  const storageEl = $("statStorage");
  const storageBar = $("barStorage");
  if (storageEl && stats.storage_used_gb !== undefined && stats.storage_total_gb !== undefined && stats.storage_total_gb > 0) {
    const diskPct = Math.round((stats.storage_used_gb / stats.storage_total_gb) * 100);
    storageEl.textContent = diskPct + "%";
    if (storageBar) storageBar.style.width = Math.max(0, Math.min(100, diskPct)) + "%";
  }

  // Battery
  const batteryEl = $("statBattery");
  const batteryBar = $("barBattery");
  if (batteryEl && stats.battery_percent !== undefined && stats.battery_percent !== null) {
    const batPct = Math.round(stats.battery_percent);
    batteryEl.textContent = batPct + "%" + (stats.battery_charging ? " ⚡" : "");
    if (batteryBar) batteryBar.style.width = Math.max(0, Math.min(100, batPct)) + "%";
  }

  // Network - use backend field
  const netEl = $("statNetwork");
  if (netEl && stats.network_online !== undefined) {
    netEl.textContent = stats.network_online ? "Online" : "Offline";
  }

  // CPU Temp
  const cpuTempEl = $("statCPUTemp");
  const cpuTempBar = $("barCPUTemp");
  if (cpuTempEl && stats.cpu_temp !== undefined && stats.cpu_temp !== null) {
    cpuTempEl.textContent = Math.round(stats.cpu_temp) + "°C";
    if (cpuTempBar) cpuTempBar.style.width = Math.min(stats.cpu_temp / 120 * 100, 100) + "%";
  }

  // GPU Usage - COMPLETE GPU BLOCK - STEP 2
  const gpuEl = $("statGPU");
  const gpuBar = $("barGPU");
  if (gpuEl && stats.gpu_usage !== undefined && stats.gpu_usage !== null) {
    const gpuPct = Math.round(stats.gpu_usage);
    gpuEl.textContent = gpuPct + "%";
    if (gpuBar) gpuBar.style.width = Math.max(0, Math.min(100, gpuPct)) + "%";
  }
}

// END updateStats() - STEP 2 COMPLETE

async function loadSystemInfo() {
  try {
    const res = await fetch("http://127.0.0.1:8000/system-info");
    const data = await res.json();

    const el = $("system-info-text");
    if (el) {
      el.innerText = `OS: ${data.os} | CPU: ${data.cpu}`;
    }
  } catch (err) {
    console.error("System info error:", err);
    const el = $("system-info-text");
    if (el) el.innerText = "OS: Unknown | CPU: Unknown";
  }
}

// TOP LEVEL updateTime() EXTRACTED - STEP 4
function updateTime() {
  const now = new Date();
  const timeEl = $("timeDisplay");
  const dateEl = $("dateDisplay");
  
  if (timeEl) {
    timeEl.textContent = now.toLocaleTimeString("en-US", { 
      hour12: false, 
      hour: "2-digit", 
      minute: "2-digit", 
      second: "2-digit" 
    });
  }
  if (dateEl) {
    dateEl.textContent = now.toLocaleDateString("en-US", { 
      weekday: "long", 
      year: "numeric", 
      month: "long", 
      day: "numeric" 
    });
  }
}

function addMessage(sender, text) {
  const container = $("chatMessages");
  if (!container) {
    logError("chatMessages container not found", null);
    return;
  }
  
  const div = document.createElement("div");
  div.className = "chat-message " + sender;
  div.innerHTML = '<div class="message-bubble">' + text + '</div>';
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function showTyping(show) {
  const indicator = $("typingIndicator");
  if (!indicator) return;
  
  if (show) {
    indicator.classList.remove("hidden");
  } else {
    indicator.classList.add("hidden");
  }
}

function loadPreferences() {
  // Load voice preference from localStorage
  const voiceEnabled = localStorage.getItem("voiceEnabled") === "true";
  state.isVoiceEnabled = voiceEnabled;
  
  if (voiceEnabled) {
    const voiceToggle = $("voiceToggle");
    if (voiceToggle) voiceToggle.classList.add("active");
  }
  
  // Load sound preference
  const soundEnabled = localStorage.getItem("soundEnabled") === "true";
  state.isSoundEnabled = soundEnabled;
  
  const soundBtn = $("soundToggleBtn");
  if (soundBtn) {
    // Add active class if sound is enabled
    if (soundEnabled) {
      soundBtn.classList.add("active");
    }
    const label = soundBtn.querySelector("span:last-child");
    if (label) label.textContent = soundEnabled ? "Sound: ON" : "Sound: OFF";
  }
  
  // Load VOID mode
  const voidMode = localStorage.getItem("voidMode") || "normal";
  state.voidMode = voidMode;
  document.body.setAttribute("data-void-mode", voidMode);
  
  const modeSelect = $("voidModeSelect");
  if (modeSelect) modeSelect.value = voidMode;
  
  log("Preferences loaded: voice=" + state.isVoiceEnabled + ", sound=" + state.isSoundEnabled + ", mode=" + voidMode);
}

// ========================================
// EVENT HANDLERS - SAFE
// ========================================
function handleSend() {
  const input = $("chatInput");
  if (!input) return;

  const message = input.value.trim();
  if (!message) return;

  addMessage("user", message);
  input.value = "";

  showTyping(true);
  updateStatus("thinking");

  sendChat(message).then(response => {
    showTyping(false);

    // apiCall returns null when fetch fails and already shows an error bubble
    if (!response) {
      updateStatus(state.isOnline ? "online" : "offline");
      return;
    }

    updateStatus("online");

    if (response.reply) {
      addMessage("void", response.reply);
      
      // Phase 5 — TTS with error guard
      // Speak if EITHER voice mode OR sound mode is enabled
      if ((state.isVoiceEnabled || state.isSoundEnabled) && response.reply && response.reply.trim()) {
        console.log("[VOID TTS TRIGGERED]", response.reply);
        
        // Wrap in try/catch so it never breaks chat
        try {
          speakText(response.reply);
        } catch (ttsError) {
          console.error("[VOID TTS ERROR]", ttsError);
          // Silently fail - do not break chat
        }
      }
    } else {
      addMessage("void", "⚠️ No response received. Is Ollama running?");
    }
  }).catch(err => {
    showTyping(false);
    updateStatus("offline");
    addMessage("void", "⚠️ Error: " + err.message);
  });
}

function handleMicClick() {
  log("Mic clicked");
  startListening();
}

function handleVoiceToggle() {
  state.isVoiceEnabled = !state.isVoiceEnabled;
  
  const btn = $("voiceToggle");
  if (btn) {
    if (state.isVoiceEnabled) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
      stopSpeaking();
    }
  }
  
  // Save to localStorage
  localStorage.setItem("voiceEnabled", state.isVoiceEnabled);
  log("Voice enabled: " + state.isVoiceEnabled);
}

function handleClearChat() {
  log("Clear chat");
  const container = $("chatMessages");
  if (container) container.innerHTML = "";
  addMessage("void", "Chat cleared. How can I assist you?");
}

function handleSoundToggle() {
  state.isSoundEnabled = !state.isSoundEnabled;
  
  const soundBtn = $("soundToggleBtn");
  if (soundBtn) {
    // Add/remove active class for visual feedback
    if (state.isSoundEnabled) {
      soundBtn.classList.add("active");
    } else {
      soundBtn.classList.remove("active");
    }
    
    const label = soundBtn.querySelector("span:last-child");
    if (label) {
      label.textContent = state.isSoundEnabled ? "Sound: ON" : "Sound: OFF";
    }
  }
  
  // If turning sound OFF, stop any current speech
  if (!state.isSoundEnabled) {
    stopSpeaking();
  }
  
  localStorage.setItem("soundEnabled", state.isSoundEnabled);
  log("Sound enabled: " + state.isSoundEnabled);
}

function handleFaceLockOpen() {
  log("Face lock open");
  const modal = $("faceLockModal");
  if (modal) modal.classList.remove("hidden");
}

function handleFaceLockClose() {
  log("Face lock close");
  const modal = $("faceLockModal");
  if (modal) modal.classList.add("hidden");
}

function handleFileStatusOpen() {
  log("File status open");
  const panel = $("fileStatusPanel");
  if (panel) panel.classList.remove("hidden");
}

function handleNetworkToolsOpen() {
  log("Network tools open");
  const panel = $("networkToolsPanel");
  if (panel) panel.classList.remove("hidden");
}

function handleNetworkToolsClose() {
  log("Network tools close");
  const panel = $("networkToolsPanel");
  if (panel) panel.classList.add("hidden");
}

function handleFileStatusClose() {
  log("File status close");
  const panel = $("fileStatusPanel");
  if (panel) panel.classList.add("hidden");
}

function handleVoidModeChange(mode) {
  state.voidMode = mode;
  document.body.setAttribute("data-void-mode", mode);
  localStorage.setItem("voidMode", mode);
  log("Mode changed: " + mode);
}

// Side panel button handlers
async function handleShowMemory() {
  log("Show memory clicked");
  const response = await apiCall("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: "show memory" })
  });
  if (response && response.reply) {
    addMessage("void", response.reply);
  }
}

async function handleClearMemory() {
  log("Clear memory clicked");
  const response = await apiCall("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: "clear memory" })
  });
  if (response && response.reply) {
    addMessage("void", response.reply);
  }
}

async function handleRepair() {
  log("Repair clicked");
  const response = await apiCall("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: "repair yourself" })
  });
  if (response && response.reply) {
    addMessage("void", response.reply);
  }
}

async function handleDiagnostics() {
  log("Diagnostics clicked");
  const response = await apiCall("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: "run diagnostics" })
  });
  if (response && response.reply) {
    addMessage("void", response.reply);
  }
}

// ========================================
// FILE SCANNER FUNCTIONALITY
// ========================================
async function handleScanDirectory() {
  log("Scan directory clicked");
  
  const scopeSelect = $("scopeSelect");
  const fileTableBody = $("fileTableBody");
  
  if (!scopeSelect || !fileTableBody) {
    logError("File scanner elements missing", null);
    return;
  }
  
  const scope = scopeSelect.value;
  log("Scanning scope: " + scope);
  
  // Show loading state
  fileTableBody.innerHTML = '<tr><td colspan="4" class="no-data">Scanning...</td></tr>';
  
  try {
    // Call backend endpoint - use scope-based scanning
    const response = await apiCall("/file-status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: scope })
    });
    
    console.log("[VOID SCAN RESULT]", response);
    
    if (response && response.ok && response.file_status && response.file_status.files) {
      const files = response.file_status.files;
      
      if (files.length === 0) {
        fileTableBody.innerHTML = '<tr><td colspan="4" class="no-data">No files found</td></tr>';
        return;
      }
      
      // Populate table
      let html = "";
      for (const file of files) {
        html += '<tr>';
        html += '<td>' + escapeHtml(file.name || "Unknown") + '</td>';
        html += '<td>' + (file.size_kb !== undefined ? file.size_kb + " KB" : "--") + '</td>';
        html += '<td>' + (file.modified || "--") + '</td>';
        html += '<td>' + (file.status || "OK") + '</td>';
        html += '</tr>';
      }
      
      fileTableBody.innerHTML = html;
      log("Scan complete: " + files.length + " files");
    } else {
      // Fallback: try folder-status endpoint
      const folderResponse = await apiCall("/folder-status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: scope })
      });
      
      console.log("[VOID FOLDER SCAN RESULT]", folderResponse);
      
      if (folderResponse && folderResponse.ok && folderResponse.folder_status && folderResponse.folder_status.files) {
        const files = folderResponse.folder_status.files;
        
        if (files.length === 0) {
          fileTableBody.innerHTML = '<tr><td colspan="4" class="no-data">No files found</td></tr>';
          return;
        }
        
        let html = "";
        for (const file of files) {
          html += '<tr>';
          html += '<td>' + escapeHtml(file.name || "Unknown") + '</td>';
          html += '<td>' + (file.size_kb !== undefined ? file.size_kb + " KB" : "--") + '</td>';
          html += '<td>' + (file.modified || "--") + '</td>';
          html += '<td>' + (file.status || "OK") + '</td>';
          html += '</tr>';
        }
        
        fileTableBody.innerHTML = html;
        log("Scan complete: " + files.length + " files");
      } else {
        fileTableBody.innerHTML = '<tr><td colspan="4" class="no-data">Error scanning directory</td></tr>';
      }
    }
  } catch (err) {
    logError("Scan error", err);
    fileTableBody.innerHTML = '<tr><td colspan="4" class="no-data">Error: ' + err.message + '</td></tr>';
  }
}

// File search functionality
function handleFileSearch() {
  const searchInput = $("fileSearchInput");
  const fileTableBody = $("fileTableBody");
  
  if (!searchInput || !fileTableBody) return;
  
  const searchTerm = searchInput.value.toLowerCase().trim();
  const rows = fileTableBody.querySelectorAll("tr");
  
  rows.forEach(row => {
    if (searchTerm === "") {
      row.style.display = "";
    } else {
      const fileName = row.cells[0]?.textContent?.toLowerCase() || "";
      row.style.display = fileName.includes(searchTerm) ? "" : "none";
    }
  });
}

// Helper function to escape HTML
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// ========================================
// ATTACH EVENT LISTENERS - SAFE
// ========================================
function attachEventListeners() {
  log("Attaching event listeners...");
  
  // Send button
  const sendBtn = $("sendBtn");
  if (sendBtn) {
    sendBtn.addEventListener("click", handleSend);
    logElement("sendBtn");
  } else {
    logError("sendBtn NOT FOUND", null);
  }
  
  // Chat input
  const chatInput = $("chatInput");
  if (chatInput) {
    chatInput.addEventListener("keypress", function(e) {
      if (e.key === "Enter") handleSend();
    });
    logElement("chatInput");
  } else {
    logError("chatInput NOT FOUND", null);
  }
  
  // Mic button
  const micBtn = $("micBtn");
  if (micBtn) {
    micBtn.addEventListener("click", handleMicClick);
    logElement("micBtn");
  } else {
    logError("micBtn NOT FOUND", null);
  }
  
  // Voice toggle
  const voiceToggle = $("voiceToggle");
  if (voiceToggle) {
    voiceToggle.addEventListener("click", handleVoiceToggle);
    logElement("voiceToggle");
  } else {
    logError("voiceToggle NOT FOUND", null);
  }
  
  // Clear button
  const clearBtn = $("clearBtn");
  if (clearBtn) {
    clearBtn.addEventListener("click", handleClearChat);
    logElement("clearBtn");
  } else {
    logError("clearBtn NOT FOUND", null);
  }
  
  // Sound toggle
  const soundToggleBtn = $("soundToggleBtn");
  if (soundToggleBtn) {
    soundToggleBtn.addEventListener("click", handleSoundToggle);
    logElement("soundToggleBtn");
  } else {
    logError("soundToggleBtn NOT FOUND", null);
  }
  
  // Face lock
  const faceLockBtn = $("faceLockBtn");
  if (faceLockBtn) {
    faceLockBtn.addEventListener("click", handleFaceLockOpen);
    logElement("faceLockBtn");
  } else {
    logError("faceLockBtn NOT FOUND", null);
  }
  
  const closeFaceLock = $("closeFaceLock");
  if (closeFaceLock) {
    closeFaceLock.addEventListener("click", handleFaceLockClose);
    logElement("closeFaceLock");
  }
  
  // File status
  const fileStatusBtn = $("fileStatusBtn");
  if (fileStatusBtn) {
    fileStatusBtn.addEventListener("click", handleFileStatusOpen);
    logElement("fileStatusBtn");
  } else {
    logError("fileStatusBtn NOT FOUND", null);
  }
  
  const closeFileStatus = $("closeFileStatus");
  if (closeFileStatus) {
    closeFileStatus.addEventListener("click", handleFileStatusClose);
    logElement("closeFileStatus");
  }
  
  // VOID mode select
  const voidModeSelect = $("voidModeSelect");
  if (voidModeSelect) {
    voidModeSelect.addEventListener("change", function(e) {
      handleVoidModeChange(e.target.value);
    });
    logElement("voidModeSelect");
  } else {
    logError("voidModeSelect NOT FOUND", null);
  }
  
  // Side panel buttons - Show Memory
  const showMemBtn = $("showMemoryBtn");
  if (showMemBtn) {
    showMemBtn.addEventListener("click", handleShowMemory);
    logElement("showMemoryBtn");
  }
  
  // Side panel buttons - Clear Memory
  const clearMemBtn = $("clearMemoryBtn");
  if (clearMemBtn) {
    clearMemBtn.addEventListener("click", handleClearMemory);
    logElement("clearMemoryBtn");
  }
  
  // Side panel buttons - Repair
  const repairBtn = $("repairBtn");
  if (repairBtn) {
    repairBtn.addEventListener("click", handleRepair);
    logElement("repairBtn");
  }
  
  // Side panel buttons - Diagnostics
  const diagBtn = $("diagnosticsBtn");
  if (diagBtn) {
    diagBtn.addEventListener("click", handleDiagnostics);
    logElement("diagnosticsBtn");
  }
  
// ==== FILE SCANNER EVENT LISTENERS ====

  // Scan button
  const scanBtn = $("scanBtn");
  if (scanBtn) {
    scanBtn.addEventListener("click", handleScanDirectory);
    logElement("scanBtn");
  } else {
    logError("scanBtn NOT FOUND", null);
  }
  
  // File search input
  const fileSearchInput = $("fileSearchInput");
  if (fileSearchInput) {
    fileSearchInput.addEventListener("input", handleFileSearch);
    fileSearchInput.addEventListener("keypress", function(e) {
      if (e.key === "Enter") handleScanDirectory();
    });
    logElement("fileSearchInput");
  } else {
    logError("fileSearchInput NOT FOUND", null);
  }

  // ==== NETWORK TOOLS PANEL ====
  const networkToolsBtn = $("networkToolsBtn");
  if (networkToolsBtn) {
    networkToolsBtn.addEventListener("click", handleNetworkToolsOpen);
    logElement("networkToolsBtn");
  }

  const closeNetworkTools = $("closeNetworkTools");
  if (closeNetworkTools) {
    closeNetworkTools.addEventListener("click", handleNetworkToolsClose);
  }

  log("Event listeners attached");

}

// ========================================
// INIT
// ========================================
function initBootSequence() {
  log("🚀 BOOT: Force-killing overlays...");
  
  // IMMEDIATE FORCE KILL - NO TIMEOUT
  const boot = document.getElementById('bootOverlay');
  const welcome = document.getElementById('welcomeOverlay');
  
  if (boot) {
    boot.style.cssText = 'display: none !important; pointer-events: none !important; z-index: -999 !important;';
    log("✅ Boot overlay killed");
  }
  if (welcome) {
    welcome.classList.add('hidden');
    welcome.style.cssText = 'display: none !important; pointer-events: none !important;';
    log("✅ Welcome overlay killed");
  }
  
  // Unlock HUD
  document.querySelector('.hud-container').style.pointerEvents = 'auto';
  log("✅ HUD unlocked");
}

// Speak startup message once
async function speakStartupMessage() {
  if (state.startupVoiceSpoken) return;
  
  const health = await checkHealth();
  if (health && (health.status === "ok" || health.status === "healthy")) {
    state.startupVoiceSpoken = true;
    await speakText("VOID online. All systems operational.");
    log("Startup voice message spoken");
  }
}

function startPolling() {
  log("Starting polling...");
  
  // Time - every second
  updateTime();
  setInterval(updateTime, 1000);
  
  // Health check - every 5 seconds
  setInterval(async function() {
    const health = await checkHealth();
    if (health && (health.status === "ok" || health.status === "healthy")) {
      // First time going online - speak startup message
      if (!state.isOnline && !state.startupVoiceSpoken) {
        await speakStartupMessage();
      }
      updateStatus("online");
    } else {
      updateStatus("offline");
    }
  }, 5000);
  
  // Stats polling every 2 seconds - confirmed active
  console.log("[VOID STATS POLLING] Starting stats poll every 2s");
  setInterval(async () => {
    console.log("STATS INTERVAL RUN");
    const stats = await fetchStats();
    if (stats) updateStats(stats);
    
    // Update setup status
    updateSetupStatus();
  }, 2000);
  // Initial call
  fetchStats().then(updateStats);
  updateSetupStatus();
}

// ========================================
// MAIN ENTRY POINT
// ========================================
document.addEventListener("DOMContentLoaded", function() {
  log("DOM ready - starting init...");
  
  // Load preferences first
  loadPreferences();
  
  // Load system info once
  loadSystemInfo();
  
  // Attach event listeners
  attachEventListeners();
  
  // Setup refresh button
  const refreshBtn = $("setupRefresh");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", updateSetupStatus);
  }
  
  // Start boot sequence
  initBootSequence();
  
  // Start polling
  setTimeout(startPolling, 3000);
  
  // Add initial greeting
  setTimeout(function() {
    addMessage("void","Welcome sir, How can I assist you today?");
  }, 3500);
  
  log("Init complete");
});
