// VOID Renderer - HUD Logic
const API_BASE = 'http://127.0.0.1:8000';

// DOM
const $ = id => document.getElementById(id);
const bootScreen = $('bootScreen');
const hud = $('hud');
const backendStatus = $('backend-status');
const coreOrb = $('coreOrb');
const chatArea = $('chatArea');
const chatInput = $('chatInput');
const sendBtn = $('sendBtn');
const micBtn = $('micBtn');
const restartBtn = $('restartBtn');
const diagnosticsBtn = $('diagnosticsBtn');

// State
let isBackendReady = false;
let statsInterval = null;

// Backend poll
async function pollBackend() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    isBackendReady = res.ok;
    document.body.setAttribute('data-backend-ready', isBackendReady);
  } catch {
    isBackendReady = false;
  }
  updateBackendUI();
}

// UI updates
function updateBackendUI() {
  if (backendStatus) {
    backendStatus.textContent = isBackendReady ? 'ONLINE' : 'OFFLINE';
    backendStatus.className = isBackendReady ? 'online' : 'offline';
  }
  if (coreOrb) {
    coreOrb.style.opacity = isBackendReady ? '1' : '0.4';
  }
}

// Stats fetch
async function fetchStats() {
  try {
    const res = await fetch(`${API_BASE}/stats`);
    const stats = await res.json();
    // Update bars (example)
    if (stats.cpu_usage) $('cpu-bar').style.width = `${stats.cpu_usage}%`;
    if (stats.ram_usage) $('ram-bar').style.width = `${stats.ram_usage}%`;
  } catch {}
}

// Chat send
async function sendChat(message) {
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    });
    const data = await res.json();
    addMessage('void', data.reply || 'No response');
  } catch (e) {
    addMessage('error', `Chat error: ${e.message}`);
  }
}

function addMessage(sender, text) {
  const div = document.createElement('div');
  div.className = `message ${sender}`;
  div.textContent = text;
  chatArea.appendChild(div);
  chatArea.scrollTop = chatArea.scrollHeight;
}

// Event listeners
sendBtn.addEventListener('click', () => {
  const msg = chatInput.value.trim();
  if (msg && isBackendReady) {
    addMessage('user', msg);
    chatInput.value = '';
    sendChat(msg);
  }
});

chatInput.addEventListener('keypress', e => {
  if (e.key === 'Enter') sendBtn.click();
});

restartBtn.addEventListener('click', async () => {
  if (window.electronAPI) {
    await window.electronAPI.restartBackend();
    addMessage('system', 'Backend restarting...');
  }
});

diagnosticsBtn.addEventListener('click', async () => {
  if (isBackendReady) sendChat('run diagnostics');
});

// Mic (placeholder)
micBtn.addEventListener('click', () => {
  addMessage('system', 'Voice input (TBD)');
});

// Init
document.addEventListener('DOMContentLoaded', () => {
  pollBackend();
  setInterval(pollBackend, 2000);
  
  if (statsInterval) clearInterval(statsInterval);
  statsInterval = setInterval(fetchStats, 3000);
  
  // Hide boot
  setTimeout(() => {
    bootScreen.classList.add('hidden');
    hud.classList.remove('hidden');
    addMessage('system', 'VOID Desktop ready. Backend: ' + (isBackendReady ? 'ONLINE' : 'OFFLINE'));
  }, 3000);
});
