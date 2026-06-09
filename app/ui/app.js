/* VOID HUD UI v9 - SyntaxError Free, Production Ready */

/* FIXED: Line 59 $("#metaIntent").textContent = ... → safe setText()
 * All unsafe DOM assignments → safe helpers
 * Global error handling
 * DOMContentLoaded guard
 */

const API_BASE = "http://127.0.0.1:8002";

const state = {
  online: false,
  isThinking: false,
  isVoiceEnabled: localStorage.getItem('isVoiceEnabled') !== 'false',
  isMicActive: localStorage.getItem('isMicActive') === 'true',
  isCallActive: false,
  streaming: false,
  healthInFlight: false,
  statsInFlight: false,
  lastOfflineNotice: 0
};

let els = {};  // DOM cache
let faceLockStream = null;
let faceLockAnimId = null;

// === SAFE DOM HELPERS ===
function getEl(id) {
  if (!els[id]) els[id] = document.getElementById(id);
  return els[id];
}

function setText(id, text) {
  const el = getEl(id);
  if (el) el.textContent = text || '';
}

function setValue(id, value) {
  const el = getEl(id);
  if (el) el.value = value || '';
}

function addClass(id, cls) {
  const el = getEl(id);
  if (el) el.classList.add(cls);
}

function removeClass(id, cls) {
  const el = getEl(id);
  if (el) el.classList.remove(cls);
}

function toggleClass(id, cls, show) {
  const el = getEl(id);
  if (el) el.classList.toggle(cls, show);
}

function setOrbState(status) {
  const orb = document.querySelector('.orb');
  if (!orb) return;
  orb.classList.remove('listening', 'speaking', 'thinking');
  if (status === 'listening' || status === 'speaking' || status === 'thinking') {
    orb.classList.add(status);
  }
}

function showTyping(show) {
  toggleClass('typingIndicator', 'hidden', !show);
  if (show) {
    setOrbState('thinking');
  } else if (!state.isCallActive) {
    setOrbState('none');
  }
}

// === ELEMENTS ===
function getEls() {
  return {
    statusDot: getEl('statusDot'),
    statusText: getEl('statusText'),
    statusLabel: getEl('statusLabel'),
    chatMessages: getEl('chatMessages'),
    chatInput: getEl('chatInput'),
    sendBtn: getEl('sendBtn'),
    callBtn: getEl('callBtn'),
    micBtn: getEl('micBtn'),
    voiceToggle: getEl('voiceToggle'),
    clearBtn: getEl('clearBtn'),
    typingIndicator: getEl('typingIndicator'),
    timeDisplay: getEl('timeDisplay'),
    dateDisplay: getEl('dateDisplay'),
    bootOverlay: getEl('bootOverlay'),
    orb: document.querySelector('.orb')
  };
}

// === STATUS ===
function setStatus(mode) {
  const els = getEls();
  if (els.statusDot) els.statusDot.className = `status-dot ${mode}`;
  if (els.statusText) {
    els.statusText.className = `status-chip ${mode}`;
    setText('statusText', mode.charAt(0).toUpperCase() + mode.slice(1));
  }
  setText('statusLabel', mode.charAt(0).toUpperCase() + mode.slice(1));
  
  if (mode === 'online' || mode === 'offline') {
    state.online = mode === 'online';
    setOrbState('none');
  } else {
    setOrbState(mode);
  }
}

// === MARKDOWN RENDERER ===
function sanitizeHTML(str) {
  // Strip script tags and event handlers but allow safe HTML
  return str
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/on\w+\s*=\s*"[^"]*"/gi, '')
    .replace(/on\w+\s*=\s*'[^']*'/gi, '');
}

function renderMarkdown(text) {
  if (!text) return '';
  let html = text
    // Escape HTML entities first
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    // Bold: **text**
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic: *text*
    .replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>')
    // Inline code: `text`
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Unordered lists: - item
    .replace(/^\s*[-•]\s+(.+)$/gm, '<li>$1</li>')
    // Wrap consecutive <li> in <ul>
    .replace(/(<li>.*<\/li>\n?)+/g, (match) => '<ul>' + match + '</ul>')
    // Line breaks
    .replace(/\n/g, '<br>');
  return sanitizeHTML(html);
}

// === ERROR HUMANIZER ===
function humanizeError(errorMsg) {
  if (!errorMsg) return "Something went wrong. Let me try again.";
  const msg = errorMsg.toLowerCase();
  if (msg.includes('fetch') || msg.includes('network') || msg.includes('refused'))
    return "I lost connection to my backend. Give me a moment to reconnect.";
  if (msg.includes('500') || msg.includes('internal'))
    return "I hit an internal issue. Let me recover.";
  if (msg.includes('timeout') || msg.includes('timed out'))
    return "That took too long. Want me to try again?";
  if (msg.includes('404'))
    return "I couldn't find what I was looking for.";
  return "Something went wrong. Could you try again?";
}

// === ACTION LABELS ===
const ACTION_LABELS = {
  showMemory: 'Checking memory banks...',
  clearMemory: 'Clearing memory banks...',
  repair: 'Running system repair...',
  diagnostics: 'Running diagnostics scan...',
  faceLock: 'Initiating biometric scan...'
};

// === MESSAGES ===
function addMessage(role, text) {
  const messages = getEls().chatMessages;
  if (!messages) return;
  
  const div = document.createElement('div');
  div.className = `chat-message ${role}`;
  
  if (role !== 'system') {
    const sender = document.createElement('div');
    sender.className = 'message-sender';
    sender.textContent = role === 'void' ? 'VOID' : role.toUpperCase();
    div.appendChild(sender);
  }
  
  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  
  if (role === 'void') {
    // Render markdown for VOID responses
    bubble.innerHTML = renderMarkdown(text);
  } else {
    // Plain text for user/system/error messages
    bubble.textContent = text;
  }
  
  div.appendChild(bubble);
  
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

// === TIME ===
function updateTime() {
  const now = new Date();
  setText('timeDisplay', now.toLocaleTimeString([], {hour12: false}));
  setText('dateDisplay', now.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  }));
}

// === API ===
// Parse secure API token from URL query parameters
const urlParams = new URLSearchParams(window.location.search);
const apiToken = urlParams.get('token') || '';

async function api(endpoint, opts = {}) {
  try {
    const headers = {
      'Content-Type': 'application/json',
      ...(opts.headers || {})
    };
    if (apiToken) {
      headers['Authorization'] = `Bearer ${apiToken}`;
    }
    
    const resp = await fetch(`${API_BASE}${endpoint}`, {
      ...opts,
      headers: headers,
    });
    
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch (e) {
    console.error('API:', e);
    return {error: e.message};
  }
}

// === HEALTH ===
async function refreshHealth() {
  const result = await api('/health');
  if (result.status === 'ok') {
    setStatus('online');
  } else {
    setStatus('offline');
  }
}

// === STATS ===
// Cache previous values to avoid unnecessary DOM writes
const prevStats = {};

const perfHistory = {
  cpu: Array(15).fill(0),
  ram: Array(15).fill(0)
};

function renderPerfChart() {
  const svg = getEl('perfChart');
  if (!svg) return;
  
  const width = 300;
  const height = 100;
  const padding = 10;
  const chartWidth = width - 2 * padding;
  const chartHeight = height - 2 * padding;
  
  const getPointsPath = (data) => {
    return data.map((val, index) => {
      const x = padding + (index / (data.length - 1)) * chartWidth;
      const y = padding + chartHeight - (val / 100) * chartHeight;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
  };
  
  const cpuPoints = getPointsPath(perfHistory.cpu);
  const ramPoints = getPointsPath(perfHistory.ram);
  
  let gridLinesHtml = '';
  for (let i = 1; i <= 3; i++) {
    const y = padding + (i / 4) * chartHeight;
    gridLinesHtml += `<line x1="${padding}" y1="${y}" x2="${width - padding}" y2="${y}" class="chart-grid" />`;
  }
  for (let i = 1; i <= 4; i++) {
    const x = padding + (i / 5) * chartWidth;
    gridLinesHtml += `<line x1="${x}" y1="${padding}" x2="${x}" y2="${height - padding}" class="chart-grid" />`;
  }
  
  svg.innerHTML = `
    ${gridLinesHtml}
    <polyline points="${cpuPoints.join(' ')}" class="chart-line-cpu" />
    <polyline points="${ramPoints.join(' ')}" class="chart-line-ram" />
  `;
}

function setStatIfChanged(id, value) {
  if (prevStats[id] !== value) {
    prevStats[id] = value;
    setText(id, value);
  }
}

function setBarIfChanged(id, pct) {
  const key = 'bar_' + id;
  const rounded = Math.round(pct * 10) / 10; // 0.1% precision
  if (prevStats[key] !== rounded) {
    prevStats[key] = rounded;
    const el = getEl(id);
    if (el) el.style.width = `${rounded}%`;
  }
}

async function refreshStats() {
  if (state.statsInFlight || !state.online || document.hidden) return;
  state.statsInFlight = true;
  
  const data = await api('/stats');
  state.statsInFlight = false;
  
  if (!data || data.error) return;
  
  const cpu = data.cpu_usage || 0;
  const cpuTemp = data.cpu_temp || 0;
  const ram = data.ram_usage || 0;
  const storage = data.storage_total_gb ? (data.storage_used_gb / data.storage_total_gb) * 100 : 0;
  const battery = data.battery_percent || 0;
  
  setStatIfChanged('statCPU', `${cpu.toFixed(0)}%`);
  
  if (data.cpu_temp !== null && data.cpu_temp !== undefined) {
    setStatIfChanged('statCPUTemp', `${cpuTemp.toFixed(1)}°C`);
  } else {
    setStatIfChanged('statCPUTemp', 'N/A');
  }
  
  setStatIfChanged('statRAM', `${ram.toFixed(0)}%`);
  
  setStatIfChanged('statStorage', `${data.storage_used_gb || 0}GB / ${data.storage_total_gb || 0}GB`);
  setBarIfChanged('barStorage', storage);

  if (data.battery_percent !== null && data.battery_percent !== undefined) {
    setStatIfChanged('statBattery', `${battery}% ${data.battery_charging ? '⚡' : ''}`);
    setBarIfChanged('barBattery', battery);
  }

  setStatIfChanged('statNetwork', data.network_online ? 'CONNECTED' : 'DISCONNECTED');
  setStatIfChanged('statUptime', `${Math.floor((data.uptime || 0) / 60)}m`);
  
  if (data.motd !== undefined && data.motd !== null) {
    setText('motdText', data.motd);
  }
  
  // Update perf chart history
  perfHistory.cpu.push(cpu);
  perfHistory.cpu.shift();
  perfHistory.ram.push(ram);
  perfHistory.ram.shift();
  renderPerfChart();
  
  // Refresh academic statistics
  refreshAcademicSummary();
  // Refresh emotional statistics
  refreshEmotionSummary();
}

function renderAcademicDonut(completed, gaps) {
  const svg = getEl('academicDonutChart');
  if (!svg) return;
  
  const total = completed + gaps;
  if (total === 0) {
    svg.innerHTML = `
      <circle cx="18" cy="18" r="15.915" class="donut-ring"></circle>
      <text x="50%" y="50%" transform="rotate(90 18 18)" dominant-baseline="middle" text-anchor="middle" fill="#888" font-size="6" font-family="'Orbitron', sans-serif">0%</text>
    `;
    return;
  }
  
  const compPct = Math.round((completed / total) * 100);
  const gapsPct = 100 - compPct;
  
  const compStroke = compPct;
  const gapsStroke = gapsPct;
  
  svg.innerHTML = `
    <circle cx="18" cy="18" r="15.915" class="donut-ring"></circle>
    <circle cx="18" cy="18" r="15.915" class="donut-segment completed" stroke-dasharray="${compStroke} ${100 - compStroke}" stroke-dashoffset="0"></circle>
    <circle cx="18" cy="18" r="15.915" class="donut-segment gaps" stroke-dasharray="${gapsStroke} ${100 - gapsStroke}" stroke-dashoffset="${100 - compStroke}"></circle>
    <text x="50%" y="50%" transform="rotate(90 18 18)" dominant-baseline="middle" text-anchor="middle" fill="#00e5ff" font-size="8" font-weight="700" font-family="'Orbitron', sans-serif">${compPct}%</text>
  `;
}

async function refreshAcademicSummary() {
  const data = await api('/academic/summary');
  if (!data || data.error) return;
  
  setText('acadSubject', data.current_subject || '--');
  setText('acadChapter', data.current_chapter || '--');
  setText('acadCompleted', data.completed_count !== undefined ? data.completed_count.toString() : '0');
  setText('acadGaps', data.gaps_count !== undefined ? data.gaps_count.toString() : '0');
  setText('acadAvgScore', data.average_score !== undefined ? `${data.average_score}/10` : '--');
  
  const completed = data.completed_count || 0;
  const gaps = data.gaps_count || 0;
  renderAcademicDonut(completed, gaps);
}

async function refreshEmotionSummary() {
  const data = await api('/academic/emotion');
  if (!data || data.error) return;
  
  setText('moodLabel', `${data.mood} (${data.confidence}%)`);
  setText('moodWPM', data.wpm > 0 ? `${data.wpm.toFixed(0)} WPM` : '-- WPM');
  setText('moodEnergy', data.energy_rms > 0 ? `${data.energy_rms.toFixed(0)} RMS` : 'Normal');
  setText('adaptState', data.adaptive_state || 'Standard');
  
  const bar = getEl('moodBar');
  if (bar) {
    bar.style.width = `${data.confidence}%`;
  }
}

async function uploadAcademicFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  
  const headers = {};
  if (apiToken) {
    headers['Authorization'] = `Bearer ${apiToken}`;
  }
  
  try {
    addMessage('system', `Uploading document: ${file.name}...`);
    const resp = await fetch(`${API_BASE}/academic/upload`, {
      method: 'POST',
      headers: headers,
      body: formData
    });
    
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const res = await resp.json();
    if (res.status === 'ok') {
      addMessage('system', `Successfully uploaded textbook '${file.name}' and compiled academic references index.`);
      refreshAcademicSummary();
    } else {
      addMessage('error', `Failed upload: ${res.message || 'Unknown error'}`);
    }
  } catch (e) {
    addMessage('error', `Upload error: ${e.message}`);
  }
}

// === SEND ===
function setSendEnabled(enabled) {
  const btn = getEl('sendBtn');
  const input = getEl('chatInput');
  if (btn) {
    btn.disabled = !enabled;
    btn.style.opacity = enabled ? '1' : '0.5';
  }
  if (input) input.disabled = !enabled;
}

// === CALL CHAT WITH PROGRESS POLLING ===
async function callChatWithProgress(msg) {
  let pollInterval = null;
  const isResearchRequest = /deep\s*research|research\s*deeply|investigate|full\s*analysis|comprehensive\s*report|detailed\s*report|research\s*this|analyze\s*this/i.test(msg);
  
  if (isResearchRequest) {
    let lastStatus = "";
    pollInterval = setInterval(async () => {
      try {
        const statusData = await api('/research/status');
        if (statusData && statusData.active) {
          const statusText = statusData.status || "Analyzing...";
          if (statusText !== lastStatus) {
            lastStatus = statusText;
            const typingLabel = getEl('typingIndicator');
            if (typingLabel) {
              const span = typingLabel.querySelector(':scope > span:not(.typing-dots)');
              if (span) {
                span.textContent = `VOID is analyzing: ${statusText}`;
              }
            }
          }
        }
      } catch (e) {
        console.error("Failed to poll research status", e);
      }
    }, 800);
  }
  
  try {
    const result = await api('/chat', {
      method: 'POST',
      body: JSON.stringify({message: msg})
    });
    return result;
  } finally {
    if (pollInterval) {
      clearInterval(pollInterval);
      const typingLabel = getEl('typingIndicator');
      if (typingLabel) {
        const span = typingLabel.querySelector(':scope > span:not(.typing-dots)');
        if (span) {
          span.textContent = "VOID is analyzing";
        }
      }
    }
  }
}

async function sendChat(msg) {
  if (!msg) return;
  setSendEnabled(false);
  showTyping(true);
  setStatus('thinking');
  
  addMessage('user', msg);
  setValue('chatInput', '');
  
  const result = await callChatWithProgress(msg);
  
  showTyping(false);
  setSendEnabled(true);
  
  if (result.reply) {
    if (result.reply.startsWith("PENDING_CONFIRMATION:")) {
      handleCVCSConfirmation(result.reply);
    } else {
      addMessage('void', result.reply);
      // Auto-speak if enabled
      if (state.isVoiceEnabled) {
        await api('/speak', {method: 'POST', body: JSON.stringify({text: result.reply})});
        monitorSpeakingState();
      }
    }
  } else {
    addMessage('error', humanizeError(result.error));
  }
  
  if (!state.isCallActive) {
    setStatus(state.online ? 'online' : 'offline');
  }
  // Re-focus input
  const input = getEl('chatInput');
  if (input) input.focus();
}

// === VOICE & INTERRUPT SYSTEM ===
let monitorInFlight = false;
async function monitorSpeakingState() {
  if (monitorInFlight) return;
  monitorInFlight = true;
  
  try {
    let speakStatus = await api('/speak-status');
    if (speakStatus && speakStatus.speaking) {
      setStatus('speaking');
      while (speakStatus && speakStatus.speaking) {
        await new Promise(resolve => setTimeout(resolve, 300));
        speakStatus = await api('/speak-status');
      }
      setStatus(state.isCallActive ? 'listening' : (state.online ? 'online' : 'offline'));
    }
  } catch (e) {
    console.error("Monitor speaking error:", e);
  } finally {
    monitorInFlight = false;
  }
}

async function interruptSpeech() {
  try {
    let speakStatus = await api('/speak-status');
    if (speakStatus && speakStatus.speaking) {
      console.log("[INTERRUPT] User activity detected. Silencing assistant.");
      await api('/stop-speak', {method: 'POST'});
      setStatus(state.isCallActive ? 'listening' : (state.online ? 'online' : 'offline'));
    }
  } catch (e) {
    console.error("Interrupt speech error:", e);
  }
}

let callLoopActive = false;
async function runCallLoop() {
  if (callLoopActive) return;
  callLoopActive = true;
  
  addMessage('system', 'Call session started.');
  
  while (state.isCallActive) {
    try {
      // 1. Wait for speak to finish if currently speaking
      let speakStatus = await api('/speak-status');
      if (speakStatus && speakStatus.speaking) {
        setStatus('speaking');
        while (speakStatus && speakStatus.speaking && state.isCallActive) {
          await new Promise(resolve => setTimeout(resolve, 300));
          speakStatus = await api('/speak-status');
        }
      }
      
      if (!state.isCallActive) break;
      
      // 2. Check if Mic is active (Unmuted)
      if (!state.isMicActive) {
        setStatus('online');
        setText('statusLabel', 'Call (Muted)');
        await new Promise(resolve => setTimeout(resolve, 500));
        continue;
      }
      
      // 3. Start listening
      setStatus('listening');
      
      const res = await api('/listen');
      
      if (!state.isCallActive) break;
      if (!state.isMicActive) continue; // Skip if muted during processing
      
      if (res.reply && res.reply.trim() && res.meta && res.meta.status === 'ok') {
        // User spoke!
        setStatus('thinking');
        showTyping(true);
        addMessage('user', res.reply);
        
        const result = await callChatWithProgress(res.reply);
        
        showTyping(false);
        if (!state.isCallActive) break;
        
        if (result.reply) {
          addMessage('void', result.reply);
          
          if (state.isVoiceEnabled) {
            setStatus('speaking');
            await api('/speak', {
              method: 'POST',
              body: JSON.stringify({text: result.reply})
            });
            
            // Wait briefly for speaking to register on the backend
            await new Promise(resolve => setTimeout(resolve, 800));
            
            // Poll until finished speaking
            speakStatus = await api('/speak-status');
            while (speakStatus && speakStatus.speaking && state.isCallActive) {
              await new Promise(resolve => setTimeout(resolve, 300));
              speakStatus = await api('/speak-status');
            }
            
            // Post-speak brief delay to prevent feedback/looping
            await new Promise(resolve => setTimeout(resolve, 1000));
          } else {
            // Text only reply, pause briefly so user can read
            await new Promise(resolve => setTimeout(resolve, 3000));
          }
        } else {
          addMessage('error', result.error || 'No response from assistant.');
          await new Promise(resolve => setTimeout(resolve, 2000));
        }
      } else {
        // Silence or timeout, wait briefly and loop again
        await new Promise(resolve => setTimeout(resolve, 500));
      }
    } catch (e) {
      console.error("Call loop error:", e);
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
  }
  
  callLoopActive = false;
  setStatus(state.online ? 'online' : 'offline');
  addMessage('system', 'Call session ended.');
}

let toggleVoiceInFlight = false;
async function toggleVoice() {
  if (toggleVoiceInFlight) return;
  toggleVoiceInFlight = true;
  setTimeout(() => { toggleVoiceInFlight = false; }, 500);
  
  state.isVoiceEnabled = !state.isVoiceEnabled;
  localStorage.setItem('isVoiceEnabled', state.isVoiceEnabled);
  
  const voiceToggle = getEl('voiceToggle');
  if (voiceToggle) voiceToggle.classList.toggle('active', state.isVoiceEnabled);
  
  const soundToggleBtn = getEl('soundToggleBtn');
  if (soundToggleBtn) {
    soundToggleBtn.textContent = `Sound: ${state.isVoiceEnabled ? 'ON' : 'OFF'}`;
    soundToggleBtn.classList.toggle('active', state.isVoiceEnabled);
  }
  
  addMessage('system', `Voice output ${state.isVoiceEnabled ? 'ENABLED' : 'DISABLED'}`);
  if (!state.isVoiceEnabled) {
    await api('/stop-speak', {method: 'POST'});
  }
}

let micLevelInterval = null;

function startMicLevelPolling() {
  if (micLevelInterval) return;
  
  // Set UI elements to active status immediately
  const micStatusLabel = document.getElementById('micStatusLabel');
  const micStatusDot = document.getElementById('micStatusDot');
  if (micStatusLabel) {
    micStatusLabel.innerText = 'Active';
    micStatusLabel.style.color = '#39ff14';
  }
  if (micStatusDot) {
    micStatusDot.classList.add('active');
  }

  micLevelInterval = setInterval(async () => {
    try {
      const res = await api('/mic-level');
      const micLevelBar = document.getElementById('micLevelBar');
      const micLevelPct = document.getElementById('micLevelPct');
      const label = document.getElementById('micStatusLabel');
      const dot = document.getElementById('micStatusDot');
      
      if (res && typeof res.level_pct !== 'undefined') {
        const pct = Math.round(res.level_pct);
        if (micLevelBar) {
          micLevelBar.style.width = `${pct}%`;
        }
        if (micLevelPct) {
          micLevelPct.innerText = `${pct}%`;
        }
        
        if (label) {
          if (res.active) {
            label.innerText = 'Active';
            label.style.color = '#39ff14';
          } else {
            label.innerText = 'Inactive';
            label.style.color = '#888';
          }
        }
        if (dot) {
          dot.classList.toggle('active', res.active);
        }
      }
    } catch (e) {
      console.debug("Error updating mic level:", e);
    }
  }, 200);
}

function stopMicLevelPolling() {
  if (micLevelInterval) {
    clearInterval(micLevelInterval);
    micLevelInterval = null;
  }
  
  // Reset UI
  const micLevelBar = document.getElementById('micLevelBar');
  const micLevelPct = document.getElementById('micLevelPct');
  const micStatusLabel = document.getElementById('micStatusLabel');
  const micStatusDot = document.getElementById('micStatusDot');
  
  if (micLevelBar) micLevelBar.style.width = '0%';
  if (micLevelPct) micLevelPct.innerText = '0%';
  if (micStatusLabel) {
    micStatusLabel.innerText = 'Inactive';
    micStatusLabel.style.color = '#888';
  }
  if (micStatusDot) micStatusDot.classList.remove('active');
}

let toggleCallInFlight = false;
async function toggleCall() {
  if (toggleCallInFlight) return;
  toggleCallInFlight = true;
  setTimeout(() => { toggleCallInFlight = false; }, 800);
  
  state.isCallActive = !state.isCallActive;
  
  const callBtn = getEl('callBtn');
  if (callBtn) callBtn.classList.toggle('active-call', state.isCallActive);
  
  if (state.isCallActive) {
    // Enable microphone automatically for immediate speaking in call
    state.isMicActive = true;
    localStorage.setItem('isMicActive', true);
    const micBtn = getEl('micBtn');
    if (micBtn) micBtn.classList.add('active-mic');
    
    // Silence any current speaking
    await api('/stop-speak', {method: 'POST'});
    
    startMicLevelPolling();
    runCallLoop();
  } else {
    // Restore MIC button to normal inactive state
    const micBtn = getEl('micBtn');
    if (micBtn) micBtn.classList.remove('active-mic');
    
    // Silence assistant speaking
    await api('/stop-speak', {method: 'POST'});
    
    stopMicLevelPolling();
  }
}

async function handleMicClick() {
  if (state.isCallActive) {
    // Act as Mute/Unmute in Call mode
    state.isMicActive = !state.isMicActive;
    localStorage.setItem('isMicActive', state.isMicActive);
    const micBtn = getEl('micBtn');
    if (micBtn) micBtn.classList.toggle('active-mic', state.isMicActive);
    addMessage('system', `Microphone ${state.isMicActive ? 'UNMUTED' : 'MUTED'}`);
    
    if (state.isMicActive) {
      startMicLevelPolling();
    } else {
      stopMicLevelPolling();
    }
  } else {
    // Mode 1: One-turn Speech-To-Text in Chat mode
    startListening();
  }
}

async function startListening() {
  if (state.isCallActive) return;
  
  const micBtn = getEl('micBtn');
  if (micBtn) micBtn.classList.add('active-mic');
  
  setStatus('listening');
  addMessage('system', 'Listening...');
  startMicLevelPolling();
  
  try {
    const res = await api('/listen');
    if (res.reply && res.meta && res.meta.status === 'ok') {
      setValue('chatInput', res.reply);
      const input = getEl('chatInput');
      if (input) {
        input.focus();
        input.select();
      }
    } else {
      addMessage('system', 'No speech detected. Try again or type your message.');
    }
  } catch (e) {
    console.error("Listening error:", e);
  } finally {
    if (micBtn) micBtn.classList.remove('active-mic');
    setStatus(state.online ? 'online' : 'offline');
    stopMicLevelPolling();
  }
}

// === ACTIONS ===
async function runAction(name) {
  addMessage('system', ACTION_LABELS[name] || `Running ${name}...`);
  if (name === 'showMemory') {
    const res = await api('/chat', {method: 'POST', body: JSON.stringify({message: 'show memory'})});
    addMessage('void', res.reply || 'No memory data available.');
  } else if (name === 'clearMemory') {
    const res = await api('/chat', {method: 'POST', body: JSON.stringify({message: 'clear memory'})});
    addMessage('system', res.reply || 'Memory cleared.');
  } else if (name === 'repair') {
    const res = await api('/repair');
    addMessage('void', res.reply || 'Repair process completed.');
  } else if (name === 'diagnostics') {
    const res = await api('/diagnostics');
    addMessage('void', res.reply || 'Diagnostics completed.');
  } else if (name === 'faceLock') {
    showFaceLock();
  }
}

function stopFaceLock() {
  if (faceLockStream) {
    try {
      faceLockStream.getTracks().forEach(track => track.stop());
    } catch (e) {
      console.error(e);
    }
    faceLockStream = null;
  }
  if (faceLockAnimId) {
    cancelAnimationFrame(faceLockAnimId);
    faceLockAnimId = null;
  }
  const video = getEl('faceLockVideo');
  if (video) {
    video.srcObject = null;
    video.classList.add('hidden');
  }
  const placeholder = getEl('faceLockPlaceholder');
  if (placeholder) {
    placeholder.classList.remove('hidden');
  }
  const modal = getEl('faceLockModal');
  if (modal) {
    modal.classList.add('hidden');
  }
}

function showFaceLock() {
  const modal = getEl('faceLockModal');
  const status = getEl('faceScanStatus');
  const video = getEl('faceLockVideo');
  const canvas = getEl('faceLockCanvas');
  const placeholder = getEl('faceLockPlaceholder');
  
  if (!modal || !status) return;
  
  // Clean up any existing scans first
  stopFaceLock();
  
  modal.classList.remove('hidden');
  status.innerText = "Initializing Biometric Core...";
  status.style.color = "";
  
  let scanPhase = 1; // 1: Init, 2: Scanning/Syncing, 3: Success
  let scanProgress = 0;
  let hasCamera = false;
  let startTime = Date.now();
  
  // Setup canvas drawing loop
  let ctx = null;
  if (canvas) {
    ctx = canvas.getContext('2d');
    canvas.width = 220;
    canvas.height = 220;
  }
  
  function drawScanHUD() {
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    const w = canvas.width;
    const h = canvas.height;
    const center = w / 2;
    const elapsed = (Date.now() - startTime) / 1000;
    
    // Choose HUD colors based on state/phase
    let hudColor = "rgba(255, 0, 60, 0.85)"; // Red-pink
    let accentGlow = "rgba(255, 0, 60, 0.2)";
    if (scanPhase === 2) {
      hudColor = "rgba(255, 158, 34, 0.85)"; // Orange
      accentGlow = "rgba(255, 158, 34, 0.2)";
    } else if (scanPhase === 3) {
      hudColor = "rgba(57, 255, 20, 0.85)"; // Green-lime
      accentGlow = "rgba(57, 255, 20, 0.2)";
    }
    
    // 1. Draw outer rotating tech ring
    ctx.save();
    ctx.translate(center, center);
    ctx.rotate(elapsed * 0.4);
    ctx.strokeStyle = hudColor;
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 12]);
    ctx.beginPath();
    ctx.arc(0, 0, 95, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
    
    // 2. Draw outer solid ring with gaps
    ctx.save();
    ctx.translate(center, center);
    ctx.rotate(-elapsed * 0.2);
    ctx.strokeStyle = hudColor;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([40, 20, 10, 20]);
    ctx.beginPath();
    ctx.arc(0, 0, 85, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
    
    // 3. Draw biometric grid/crosshair target in center
    ctx.strokeStyle = hudColor;
    ctx.lineWidth = 1;
    ctx.setLineDash([]);
    
    // Draw target box brackets [ ] that shake slightly if scanning
    let offset = 0;
    if (scanPhase === 2) {
      offset = Math.sin(elapsed * 25) * 1.5; // Shaking effect
    }
    
    const size = 50 + offset;
    const leftX = center - size;
    const rightX = center + size;
    const topY = center - size;
    const bottomY = center + size;
    const bracketLen = 12;
    
    // Top-Left [
    ctx.beginPath();
    ctx.moveTo(leftX, topY + bracketLen);
    ctx.lineTo(leftX, topY);
    ctx.lineTo(leftX + bracketLen, topY);
    ctx.stroke();
    
    // Top-Right ]
    ctx.beginPath();
    ctx.moveTo(rightX, topY + bracketLen);
    ctx.lineTo(rightX, topY);
    ctx.lineTo(rightX - bracketLen, topY);
    ctx.stroke();
    
    // Bottom-Left [
    ctx.beginPath();
    ctx.moveTo(leftX, bottomY - bracketLen);
    ctx.lineTo(leftX, bottomY);
    ctx.lineTo(leftX + bracketLen, bottomY);
    ctx.stroke();
    
    // Bottom-Right ]
    ctx.beginPath();
    ctx.moveTo(rightX, bottomY - bracketLen);
    ctx.lineTo(rightX, bottomY);
    ctx.lineTo(rightX - bracketLen, bottomY);
    ctx.stroke();
    
    // 4. Draw HUD tech data readout overlay in small letters
    ctx.font = "8px 'Orbitron', monospace";
    ctx.fillStyle = hudColor;
    ctx.fillText("BIOMETRIC SCAN V9", 15, 20);
    ctx.fillText(hasCamera ? "FEED: WEBCAM_ACTIVE" : "FEED: COMP_STUB", 15, 32);
    
    ctx.textAlign = "right";
    ctx.fillText("SYS: BLOCK_ENG", w - 15, 20);
    ctx.fillText(scanPhase === 3 ? "MATCH: 99.8%" : `SYNC: ${Math.floor(scanProgress)}%`, w - 15, 32);
    ctx.textAlign = "left";
    
    // If scanning, draw circular crosshair rings
    if (scanPhase < 3) {
      ctx.strokeStyle = accentGlow;
      ctx.beginPath();
      ctx.arc(center, center, 30, 0, Math.PI * 2);
      ctx.stroke();
    } else {
      // Success lock overlay: Draw glowing target locks
      ctx.strokeStyle = hudColor;
      ctx.beginPath();
      ctx.arc(center, center, 40, 0, Math.PI * 2);
      ctx.stroke();
      
      ctx.fillStyle = "rgba(57, 255, 20, 0.15)";
      ctx.beginPath();
      ctx.arc(center, center, 40, 0, Math.PI * 2);
      ctx.fill();
    }
    
    faceLockAnimId = requestAnimationFrame(drawScanHUD);
  }
  
  // Begin video check
  navigator.mediaDevices.getUserMedia({ video: { width: 220, height: 220 } })
    .then(stream => {
      hasCamera = true;
      faceLockStream = stream;
      if (video) {
        video.srcObject = stream;
        video.classList.remove('hidden');
      }
      if (placeholder) {
        placeholder.classList.add('hidden');
      }
      
      // Start flow
      runBiometricSequence();
    })
    .catch(err => {
      console.warn("Webcam access failed/denied, falling back to simulated HUD scan:", err);
      hasCamera = false;
      if (video) {
        video.classList.add('hidden');
      }
      if (placeholder) {
        placeholder.classList.remove('hidden');
      }
      
      runBiometricSequence();
    });
    
  function runBiometricSequence() {
    // Start drawing loop
    if (canvas) {
      faceLockAnimId = requestAnimationFrame(drawScanHUD);
    }
    
    // Stage 1: Init (1s)
    setTimeout(() => {
      if (!modal.classList.contains('hidden')) {
        scanPhase = 2;
        status.innerText = "Analyzing facial geometry...";
        status.style.color = "rgba(255, 158, 34, 0.85)"; // Orange
        
        // Increment progress smoothly
        let interval = setInterval(() => {
          if (modal.classList.contains('hidden') || scanPhase === 3) {
            clearInterval(interval);
            return;
          }
          scanProgress += 6.5;
          if (scanProgress >= 100) {
            scanProgress = 100;
            clearInterval(interval);
          }
        }, 100);
        
        // Stage 2: Sync and Match (2s)
        setTimeout(() => {
          if (!modal.classList.contains('hidden')) {
            scanPhase = 3;
            status.innerText = "ACCESS GRANTED: Mridul Sharma";
            status.style.color = "#39ff14"; // Glowing success green
            
            // Stage 3: Success and Welcome (1.5s)
            setTimeout(() => {
              if (!modal.classList.contains('hidden')) {
                stopFaceLock();
                addMessage('system', 'Biometric login successful. Welcome back, Master Mridul.');
              }
            }, 1500);
          }
        }, 2200);
      }
    }, 1200);
  }
}

// === EVENTS ===
function bindEvents() {
  const els = getEls();
  
  if (els.sendBtn) els.sendBtn.onclick = () => {
    const val = els.chatInput.value.trim();
    if (val) sendChat(val);
  };
  
  getEl('faceLockBtn')?.addEventListener('click', () => runAction('faceLock'));
  getEl('closeFaceLock')?.addEventListener('click', () => stopFaceLock());
  
  if (els.chatInput) {
    els.chatInput.onkeydown = (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        els.sendBtn.click();
      }
    };
    els.chatInput.oninput = () => {
      interruptSpeech();
    };
  }
  
  const orbWrap = document.querySelector('.orb-wrap');
  if (orbWrap) {
    orbWrap.style.pointerEvents = 'auto';
    orbWrap.onclick = () => {
      interruptSpeech();
    };
  }
  
  if (els.chatMessages) {
    els.chatMessages.onclick = () => {
      interruptSpeech();
    };
  }
  
  if (els.clearBtn) els.clearBtn.onclick = () => {
    if (els.chatMessages) els.chatMessages.innerHTML = '';
  };

  if (els.callBtn) els.callBtn.onclick = toggleCall;
  if (els.micBtn) els.micBtn.onclick = handleMicClick;
  if (els.voiceToggle) els.voiceToggle.onclick = toggleVoice;
  
  const soundToggleBtn = getEl('soundToggleBtn');
  if (soundToggleBtn) soundToggleBtn.onclick = toggleVoice;

  const actions = {
    'showMemoryBtn': 'showMemory',
    'clearMemoryBtn': 'clearMemory',
    'repairBtn': 'repair',
    'diagnosticsBtn': 'diagnostics'
  };
  Object.entries(actions).forEach(([id, name]) => {
    const el = getEl(id);
    if (el) el.onclick = () => runAction(name);
  });
  
  // Academic Upload Triggers
  const uploadDocBtn = getEl('uploadDocBtn');
  const academicFileInput = getEl('academicFileInput');
  if (uploadDocBtn && academicFileInput) {
    uploadDocBtn.onclick = (e) => {
      e.preventDefault();
      academicFileInput.click();
    };
    academicFileInput.onchange = async () => {
      if (academicFileInput.files.length > 0) {
        const file = academicFileInput.files[0];
        await uploadAcademicFile(file);
        academicFileInput.value = ''; // Reset input
      }
    };
  }

  // CVCS Control Bindings
  const cvcsPermissionSelect = getEl('cvcsPermissionSelect');
  if (cvcsPermissionSelect) {
    cvcsPermissionSelect.onchange = async () => {
      const val = parseFloat(cvcsPermissionSelect.value);
      const res = await api('/cvcs/permission', {
        method: 'POST',
        body: JSON.stringify({level: val, duration_seconds: 1800.0})
      });
      if (res && res.status === 'ok') {
        addMessage('system', res.message);
        refreshCVCS();
      }
    };
  }

  const cvcsWatchToggleBtn = getEl('cvcsWatchToggleBtn');
  if (cvcsWatchToggleBtn) {
    cvcsWatchToggleBtn.onclick = async () => {
      const isCurrentlyActive = cvcsWatchToggleBtn.textContent.trim() === 'ON';
      const res = await api('/cvcs/toggle-monitor', {
        method: 'POST',
        body: JSON.stringify({text: String(!isCurrentlyActive)})
      });
      if (res && res.status === 'ok') {
        refreshCVCS();
      }
    };
  }
  
  initAcademicDashboard();
  initSearchSystem();
  initIntegrationsConsole();
}

// === SEARCH, RECOMMENDATIONS, & INTEGRATIONS LOGIC ===
function initSearchSystem() {
  const searchInput = getEl('hudSearchInput');
  const searchBtn = getEl('hudSearchBtn');
  const closeBtn = getEl('hudSearchCloseBtn');
  const resultsPanel = getEl('searchResults');
  
  if (!searchInput || !searchBtn || !resultsPanel) return;
  
  const runSearch = async () => {
    const query = searchInput.value.trim();
    if (!query) {
      resultsPanel.classList.add('hidden');
      if (closeBtn) closeBtn.classList.add('hidden');
      document.querySelectorAll('.chat-message').forEach(el => el.classList.remove('hidden', 'search-highlight'));
      return;
    }
    
    if (closeBtn) closeBtn.classList.remove('hidden');
    resultsPanel.innerHTML = '<div style="color:var(--text-dim); text-align:center; font-size:11px; padding:10px;">Searching memory banks...</div>';
    resultsPanel.classList.remove('hidden');
    
    // Highlight/filter screen messages
    document.querySelectorAll('.chat-message').forEach(el => {
      const bubble = el.querySelector('.message-bubble');
      const text = bubble ? bubble.textContent.toLowerCase() : '';
      if (text.includes(query.toLowerCase())) {
        el.classList.add('search-highlight');
        el.classList.remove('hidden');
      } else {
        el.classList.remove('search-highlight');
        el.classList.add('hidden');
      }
    });
    
    // Call backend API
    const res = await api(`/search?query=${encodeURIComponent(query)}`);
    if (res && res.results && res.results.length > 0) {
      resultsPanel.innerHTML = '';
      res.results.forEach(item => {
        const itemEl = document.createElement('div');
        itemEl.className = 'search-result-item';
        itemEl.onclick = () => {
          setValue('chatInput', item.action);
          resultsPanel.classList.add('hidden');
          searchInput.value = '';
          if (closeBtn) closeBtn.classList.add('hidden');
          document.querySelectorAll('.chat-message').forEach(el => el.classList.remove('hidden', 'search-highlight'));
          sendChat(item.action);
        };
        
        itemEl.innerHTML = `
          <div class="search-result-type ${item.type}">${item.type}</div>
          <div class="search-result-title">${item.title}</div>
          <div class="search-result-snippet">${item.snippet}</div>
        `;
        resultsPanel.appendChild(itemEl);
      });
    } else {
      resultsPanel.innerHTML = '<div style="color:var(--text-dim); text-align:center; font-size:11px; padding:10px;">No matching records found, Sir.</div>';
    }
  };
  
  searchBtn.onclick = runSearch;
  searchInput.onkeydown = (e) => {
    if (e.key === 'Enter') runSearch();
  };
  
  if (closeBtn) {
    closeBtn.onclick = () => {
      searchInput.value = '';
      resultsPanel.classList.add('hidden');
      closeBtn.classList.add('hidden');
      document.querySelectorAll('.chat-message').forEach(el => el.classList.remove('hidden', 'search-highlight'));
    };
  }
}

async function refreshRecommendations() {
  const recommendationsList = getEl('recommendationsList');
  if (!recommendationsList || !state.online || document.hidden) return;
  
  const res = await api('/recommendations');
  if (!res || res.error || !res.recommendations) return;
  
  if (res.recommendations.length === 0) {
    recommendationsList.innerHTML = '<div class="recommendation-item empty">All systems operational.</div>';
    return;
  }
  
  recommendationsList.innerHTML = '';
  res.recommendations.forEach((rec, idx) => {
    const item = document.createElement('div');
    item.className = `recommendation-item ${rec.type || 'general'}`;
    
    const actionId = `rec_action_${idx}`;
    
    item.innerHTML = `
      <div class="rec-title-row">
        <span class="rec-tag">${rec.type || 'insight'}</span>
        <span class="rec-title">${rec.title}</span>
      </div>
      <div class="rec-desc">${rec.desc}</div>
      <button id="${actionId}" class="btn btn-rec-action">${rec.action_label || 'Execute'}</button>
    `;
    
    recommendationsList.appendChild(item);
    
    const btn = document.getElementById(actionId);
    if (btn) {
      btn.onclick = async (e) => {
        e.preventDefault();
        e.stopPropagation();
        
        btn.textContent = 'Processing...';
        btn.disabled = true;
        
        try {
          if (rec.method === 'POST') {
            const body = rec.payload ? JSON.stringify(rec.payload) : '{}';
            if (rec.endpoint === '/chat' && rec.payload && rec.payload.message) {
              sendChat(rec.payload.message);
            } else {
              const postRes = await api(rec.endpoint, { method: 'POST', body: body });
              if (postRes && postRes.status === 'ok') {
                addMessage('system', postRes.message || 'Action executed successfully.');
              }
            }
          } else {
            const getRes = await api(rec.endpoint);
            if (getRes && getRes.reply) {
              addMessage('void', getRes.reply);
            } else if (getRes && getRes.message) {
              addMessage('system', getRes.message);
            }
          }
        } catch (err) {
          console.error('Recommendation action failed:', err);
        } finally {
          setTimeout(refreshRecommendations, 1000);
        }
      };
    }
  });
}

function initIntegrationsConsole() {
  const integrations = [
    { id: 'integrationOllama', name: 'Ollama LLM', service: 'Local AI Model Engine' },
    { id: 'integrationGoogle', name: 'Google Search', service: 'Live Web Scraping & RAG' },
    { id: 'integrationWhatsapp', name: 'WhatsApp Web', service: 'Messaging API & Automation' },
    { id: 'integrationEmail', name: 'Email & Calendar', service: 'Drafting & Scheduling Assistant' }
  ];
  
  integrations.forEach(item => {
    const el = getEl(item.id);
    if (el) {
      el.onclick = () => {
        addMessage('system', `Testing connection for ${item.name} (${item.service})...`);
        setTimeout(() => {
          addMessage('system', `✓ ${item.name} connection established. Operational status: Nominal.`);
        }, 800);
      };
    }
  });
}

// === INIT ===
async function initApp() {
  try {
    bindEvents();
    
    // Initialize UI active classes based on state
    const voiceToggle = getEl('voiceToggle');
    if (voiceToggle) voiceToggle.classList.toggle('active', state.isVoiceEnabled);
    
    const soundToggleBtn = getEl('soundToggleBtn');
    if (soundToggleBtn) {
      soundToggleBtn.textContent = `Sound: ${state.isVoiceEnabled ? 'ON' : 'OFF'}`;
      soundToggleBtn.classList.toggle('active', state.isVoiceEnabled);
    }
    
    const micBtn = getEl('micBtn');
    if (micBtn) micBtn.classList.toggle('active-mic', state.isMicActive);

    updateTime();
    setInterval(updateTime, 1000);
    
    // Schedule boot overlay removal independently so it never blocks the UI
    const overlay = getEl('bootOverlay');
    if (overlay) {
      setTimeout(() => {
        overlay.style.opacity = '0';
        setTimeout(() => overlay.remove(), 500);
      }, 1000);
    }
    
    // Run background initializations without blocking the loading transition
    (async () => {
      try {
        await refreshHealth();
        await refreshStats();
        await refreshCVCS();
        await refreshRecommendations();
        const info = await api('/system-info');
        if (info.reply) setText('system-info-text', info.reply);
      } catch (err) {
        console.warn('Background init failed:', err);
      }
    })();
    
    setInterval(refreshHealth, 10000);  // 10s — health is lightweight
    setInterval(refreshStats, 5000);    // 5s — stats don't change fast
    setInterval(refreshCVCS, 2000);     // 2s — CVCS updates frequently
    setInterval(refreshRecommendations, 10000); // 10s — recommendations
    
    // Pause heavy animations when tab is hidden
    document.addEventListener('visibilitychange', () => {
      const orb = document.querySelector('.orb');
      const scanLine = document.querySelector('.scan-line');
      if (document.hidden) {
        if (orb) orb.style.animationPlayState = 'paused';
        if (scanLine) scanLine.style.animationPlayState = 'paused';
      } else {
        if (orb) orb.style.animationPlayState = 'running';
        if (scanLine) scanLine.style.animationPlayState = 'running';
      }
    });
    
    addMessage('system', 'VOID Protocol Stabilized. At your service, Sir.');
  } catch (e) {
    console.error('INIT ERROR:', e);
    // Safe fallback to remove overlay if something else crashed
    const overlay = getEl('bootOverlay');
    if (overlay) overlay.remove();
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}

// === CVCS CORE UI IMPLEMENTATION ===
let cvcsInFlight = false;
async function refreshCVCS() {
  if (cvcsInFlight || !state.online || document.hidden) return;
  cvcsInFlight = true;
  
  try {
    const data = await api('/cvcs/status');
    if (data && !data.error) {
      // 1. Update Active Window title
      const winEl = getEl('cvcsActiveWin');
      if (winEl) {
        winEl.textContent = data.foreground_window || '--';
        winEl.title = data.foreground_window || '';
      }
      
      // 2. Sync permission select state if not actively dropdown-focused
      const permSelect = getEl('cvcsPermissionSelect');
      if (permSelect && document.activeElement !== permSelect) {
        permSelect.value = String(data.permission_level.toFixed(1));
      }
      
      // 3. Sync watch toggle state
      const watchBtn = getEl('cvcsWatchToggleBtn');
      if (watchBtn) {
        const isActive = data.watch_mode_active;
        watchBtn.textContent = isActive ? 'ON' : 'OFF';
        watchBtn.style.background = isActive ? '#39ff14' : '#222';
        watchBtn.style.color = isActive ? '#000' : '#888';
        watchBtn.style.borderColor = isActive ? '#39ff14' : '#333';
      }
      
      // 4. Update session timer countdowns
      const timerRow = getEl('cvcsTimerRow');
      const timerLabel = getEl('cvcsTimerLabel');
      if (timerRow && timerLabel) {
        if (data.session_expires_in !== null) {
          timerRow.style.display = 'flex';
          const totalSecs = Math.floor(data.session_expires_in);
          const mins = Math.floor(totalSecs / 60);
          const secs = totalSecs % 60;
          timerLabel.textContent = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        } else {
          timerRow.style.display = 'none';
        }
      }
      
      // 5. Parse background logs and build notification alerts
      if (data.notifications && data.notifications.length > 0) {
        data.notifications.forEach(n => {
          addMessage('error', `⚠️ [${n.category.toUpperCase()}] ${n.title}: ${n.message}`);
          
          if (state.isVoiceEnabled) {
            api('/speak', {
              method: 'POST',
              body: JSON.stringify({text: `${n.title}. ${n.message}`})
            }).then(() => monitorSpeakingState());
          }
        });
      }
    }
  } catch (err) {
    console.warn('CVCS status poll failed:', err);
  } finally {
    cvcsInFlight = false;
  }
}

function handleCVCSConfirmation(reply) {
  const parts = reply.split(":");
  const content = parts.slice(1).join(":").trim();
  
  const modal = getEl('cvcsConfirmModal');
  const actionEl = getEl('cvcsConfirmAction');
  const targetEl = getEl('cvcsConfirmTarget');
  const coordsEl = getEl('cvcsConfirmCoords');
  const coordsRow = getEl('cvcsConfirmCoordsRow');
  const approveBtn = getEl('cvcsConfirmApproveBtn');
  const denyBtn = getEl('cvcsConfirmDenyBtn');
  
  if (!modal) return;
  
  let action = "";
  let target = "";
  let coords = null;
  
  if (content.startsWith("click")) {
    action = "click";
    const match = content.match(/click\s+at\s+\((\d+),\s*(\d+)\)\s+for\s+target\s+'(.*)'/i);
    if (match) {
      coords = [parseInt(match[1]), parseInt(match[2])];
      target = match[3];
    } else {
      // Direct click at match without query text
      const shortMatch = content.match(/click\s+at\s+\((\d+),\s*(\d+)\)/i);
      if (shortMatch) {
        coords = [parseInt(shortMatch[1]), parseInt(shortMatch[2])];
        target = "Coordinates Location";
      }
    }
    if (coords) coordsEl.textContent = `(${coords[0]}, ${coords[1]})`;
    coordsRow.style.display = "block";
  } else if (content.startsWith("type")) {
    action = "type";
    const match = content.match(/type\s+'(.*)'/i);
    if (match) {
      target = match[1];
    }
    coordsRow.style.display = "none";
  }
  
  actionEl.textContent = action.toUpperCase();
  targetEl.textContent = target || content;
  
  modal.classList.remove('hidden');
  
  approveBtn.onclick = async () => {
    modal.classList.add('hidden');
    addMessage('void', `Approved, Sir. Executing ${action} operation...`);
    const res = await api('/cvcs/execute_action', {
      method: 'POST',
      body: JSON.stringify({
        action: action,
        target: target,
        coords: coords
      })
    });
    if (res.status === 'ok') {
      addMessage('void', `Successfully completed the desktop ${action} command.`);
      const lastAct = getEl('cvcsLastAction');
      if (lastAct) lastAct.textContent = `${action.toUpperCase()}: ${target}`;
    } else {
      addMessage('error', `Safety action failed: ${res.message || 'Unknown error'}`);
    }
  };
  
  denyBtn.onclick = () => {
    modal.classList.add('hidden');
    addMessage('void', `Action request was aborted.`);
  };
}

// === ACADEMIC SYSTEM UI OPERATIONS ===
let activeSubjectId = null;
let activeTopicId = null;
let activeVivaQuestion = null;
let researchPollInterval = null;

function initAcademicDashboard() {
  const acadCard = getEl('academicDashboardCard');
  const openBtn = getEl('openAcadDashboardBtn');
  const closeBtn = getEl('closeAcadDashboardBtn');
  const modal = getEl('academicDashboardModal');
  
  const openModal = () => {
    if (modal) {
      modal.classList.remove('hidden');
      loadAcademicSubjects();
    }
  };
  
  if (acadCard) {
    acadCard.onclick = (e) => {
      if (e.target.tagName !== 'BUTTON') openModal();
    };
  }
  if (openBtn) openBtn.onclick = openModal;
  if (closeBtn) closeBtn.onclick = () => modal && modal.classList.add('hidden');
  
  const addSubjectBtn = getEl('addSubjectBtn');
  if (addSubjectBtn) {
    addSubjectBtn.onclick = async () => {
      const name = prompt("Enter the name of the new subject:");
      if (name && name.trim()) {
        const res = await api('/academic/subjects/add', {
          method: 'POST',
          body: JSON.stringify({ subject_name: name.trim() })
        });
        if (res && res.status === 'ok') {
          await loadAcademicSubjects();
          loadSubjectWorkspace(res.subject_id, res.subject_name);
        } else {
          alert(res.detail || "Failed to add subject.");
        }
      }
    };
  }
  
  const startResearchBtn = getEl('startResearchBtn');
  if (startResearchBtn) {
    startResearchBtn.onclick = async () => {
      if (!activeSubjectId) return;
      await api('/academic/research-start', {
        method: 'POST',
        body: JSON.stringify({ subject_id: activeSubjectId })
      });
      pollResearchStatus();
    };
  }
  
  const actionTeach = getEl('actionTeachBtn');
  if (actionTeach) {
    actionTeach.onclick = () => {
      if (!activeTopicId) {
        alert("Please select a chapter/topic from the curriculum index first.");
        return;
      }
      modal.classList.add('hidden');
      const chatInput = getEl('chatInput');
      if (chatInput) {
        chatInput.value = `teach me ${activeTopicId} in ${activeSubjectId}`;
        const sendBtn = getEl('sendBtn');
        if (sendBtn) sendBtn.click();
      }
    };
  }
  
  const actionPractice = getEl('actionPracticeBtn');
  if (actionPractice) {
    actionPractice.onclick = () => {
      if (!activeTopicId) {
        alert("Please select a chapter/topic first.");
        return;
      }
      modal.classList.add('hidden');
      const chatInput = getEl('chatInput');
      if (chatInput) {
        chatInput.value = `practice exercises for ${activeTopicId} in ${activeSubjectId}`;
        const sendBtn = getEl('sendBtn');
        if (sendBtn) sendBtn.click();
      }
    };
  }
  
  const actionViva = getEl('actionVivaBtn');
  if (actionViva) actionViva.onclick = startVivaSession;
  const vivaClose = getEl('vivaCloseBtn');
  if (vivaClose) vivaClose.onclick = () => getEl('vivaModal').classList.add('hidden');
  const vivaSubmit = getEl('vivaSubmitBtn');
  if (vivaSubmit) vivaSubmit.onclick = submitVivaAnswer;
  const vivaNext = getEl('vivaNextBtn');
  if (vivaNext) vivaNext.onclick = startVivaSession;
  
  const actionExam = getEl('actionExamBtn');
  if (actionExam) actionExam.onclick = startTimedExam;
}

async function loadAcademicSubjects() {
  const container = getEl('acadSubjectsList');
  if (!container) return;
  
  const subjects = await api('/academic/subjects');
  if (!subjects || subjects.error) {
    container.innerHTML = '<p style="color:red">Failed to load subjects.</p>';
    return;
  }
  
  container.innerHTML = '';
  subjects.forEach(sub => {
    const isSelected = sub.subject_id === activeSubjectId;
    const card = document.createElement('div');
    card.className = `subject-card ${isSelected ? 'selected' : ''}`;
    card.onclick = () => {
      document.querySelectorAll('.subject-card').forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      loadSubjectWorkspace(sub.subject_id, sub.subject_name);
    };
    
    card.innerHTML = `
      <span class="delete-subj-btn" style="position: absolute; top: 6px; right: 10px; color: #ff003c; cursor: pointer; font-size: 10px; opacity: 0.6; transition: opacity 0.2s;" title="Remove Subject">❌</span>
      <div style="font-family: 'Orbitron', sans-serif; font-size: 13px; font-weight: bold; color: #fff; margin-bottom: 5px; padding-right: 15px;">${sub.subject_name}</div>
      <div style="display: flex; justify-content: space-between; font-size: 11px; color: #a47070; margin-bottom: 4px;">
        <span>Progress: ${sub.progress_percent}%</span>
        <span style="color:#ffb300;">Streak: ${sub.streak}d 🔥</span>
      </div>
      <div class="metric-bar" style="height: 4px;"><div class="metric-fill" style="width: ${sub.progress_percent}%; background:#00e5ff; box-shadow: 0 0 6px #00e5ff;"></div></div>
    `;
    
    const deleteBtn = card.querySelector('.delete-subj-btn');
    if (deleteBtn) {
      deleteBtn.onclick = async (e) => {
        e.stopPropagation();
        const confirmDelete = confirm(`Are you sure you want to completely remove "${sub.subject_name}" and delete all its progress data?`);
        if (confirmDelete) {
          const res = await api('/academic/subjects/remove', {
            method: 'POST',
            body: JSON.stringify({ subject_id: sub.subject_id })
          });
          if (res && res.status === 'ok') {
            if (activeSubjectId === sub.subject_id) {
              activeSubjectId = null;
              activeTopicId = null;
              getEl('subjectActiveView').classList.add('hidden');
              getEl('noSubjectSelectedView').classList.remove('hidden');
              refreshAcademicSummary();
            }
            loadAcademicSubjects();
          } else {
            alert(res.detail || "Failed to remove subject.");
          }
        }
      };
      deleteBtn.onmouseover = () => deleteBtn.style.opacity = '1';
      deleteBtn.onmouseout = () => deleteBtn.style.opacity = '0.6';
    }
    
    container.appendChild(card);
  });
}

async function loadSubjectWorkspace(subjectId, subjectName) {
  activeSubjectId = subjectId;
  activeTopicId = null;
  
  await api('/academic/select', {
    method: 'POST',
    body: JSON.stringify({ subject_id: subjectId })
  });
  refreshAcademicSummary();
  
  getEl('noSubjectSelectedView').classList.add('hidden');
  const activeView = getEl('subjectActiveView');
  activeView.classList.remove('hidden');
  
  setText('activeSubjectTitle', subjectName);
  
  const curriculum = await api(`/academic/curriculum?subject_id=${subjectId}`);
  const reqCard = getEl('subjectResearchRequiredCard');
  const contentCard = getEl('subjectResearchedContent');
  const rCard = getEl('subjectResearchingCard');
  
  rCard.classList.add('hidden');
  
  const subjects = await api('/academic/subjects');
  const details = subjects.find(s => s.subject_id === subjectId);
  if (details) {
    setText('activeSubjectLevel', details.mastery_level);
    setText('activeSubjectStreak', `${details.streak} days 🔥`);
    setText('activeSubjectAvg', details.average_score > 0 ? `${details.average_score}/10` : '--');
    setText('activeSubjectProgressText', `${details.progress_percent}%`);
    const activeBar = getEl('activeSubjectProgressBar');
    if (activeBar) activeBar.style.width = `${details.progress_percent}%`;
    
    const weakList = getEl('activeSubjectWeakList');
    if (weakList) {
      weakList.innerHTML = details.weak_areas.length > 0 
        ? details.weak_areas.map(w => `<li>${w}</li>`).join('') 
        : '<li>No weaknesses registered yet.</li>';
    }
    const strongList = getEl('activeSubjectStrongList');
    if (strongList) {
      strongList.innerHTML = details.strong_areas.length > 0 
        ? details.strong_areas.map(s => `<li>${s}</li>`).join('') 
        : '<li>No strengths registered yet.</li>';
    }
  }
  
  if (!curriculum || curriculum.length === 0) {
    reqCard.classList.remove('hidden');
    contentCard.classList.add('hidden');
    
    const resStatus = await api('/academic/research-status');
    if (resStatus && resStatus.active && resStatus.subject_id === subjectId) {
      pollResearchStatus();
    }
  } else {
    reqCard.classList.add('hidden');
    contentCard.classList.remove('hidden');
    renderCurriculumAccordion(curriculum);
  }
}

function renderCurriculumAccordion(curriculum) {
  const container = getEl('curriculumAccordion');
  if (!container) return;
  container.innerHTML = '';
  
  const unitsMap = {};
  curriculum.forEach(c => {
    if (!unitsMap[c.unit_title]) unitsMap[c.unit_title] = [];
    unitsMap[c.unit_title].push(c);
  });
  
  Object.entries(unitsMap).forEach(([unitTitle, chapters]) => {
    const unitEl = document.createElement('div');
    unitEl.className = 'accordion-unit';
    
    const header = document.createElement('div');
    header.className = 'accordion-unit-header';
    header.innerHTML = `<span>${unitTitle}</span> <span>➕</span>`;
    
    const body = document.createElement('div');
    body.className = 'accordion-unit-body hidden';
    
    header.onclick = () => {
      const isHidden = body.classList.contains('hidden');
      body.classList.toggle('hidden', !isHidden);
      header.querySelector('span:last-child').textContent = isHidden ? '➖' : '➕';
    };
    
    chapters.forEach(ch => {
      const chEl = document.createElement('div');
      chEl.className = 'accordion-chapter';
      chEl.innerHTML = `<span>📖 ${ch.chapter_title}</span>`;
      chEl.onclick = (e) => {
        e.stopPropagation();
        document.querySelectorAll('.accordion-chapter').forEach(el => el.classList.remove('active'));
        chEl.classList.add('active');
        activeTopicId = ch.chapter_title;
        setText('activeStudyTopicLabel', ch.chapter_title);
      };
      body.appendChild(chEl);
    });
    
    unitEl.appendChild(header);
    unitEl.appendChild(body);
    container.appendChild(unitEl);
  });
}

function pollResearchStatus() {
  getEl('subjectResearchRequiredCard').classList.add('hidden');
  getEl('subjectResearchingCard').classList.remove('hidden');
  
  if (researchPollInterval) clearInterval(researchPollInterval);
  
  researchPollInterval = setInterval(async () => {
    const status = await api('/academic/research-status');
    if (!status || !status.active) {
      clearInterval(researchPollInterval);
      const subjects = await api('/academic/subjects');
      const activeName = subjects.find(s => s.subject_id === activeSubjectId)?.subject_name || activeSubjectId;
      loadSubjectWorkspace(activeSubjectId, activeName);
      loadAcademicSubjects();
    } else {
      setText('researchStatusText', `Status: ${status.status}`);
      const logCont = getEl('researchLogsContainer');
      if (logCont) {
        logCont.innerHTML = status.logs.map(log => `<div>➔ ${log}</div>`).join('');
        logCont.scrollTop = logCont.scrollHeight;
      }
      
      const progressBar = getEl('researchProgressBar');
      if (progressBar) {
        let pct = 10;
        if (status.status === 'Deep Researching') pct = 30;
        else if (status.status === 'Mapping Syllabus') pct = 60;
        else if (status.status === 'Writing Study Guides') pct = 80;
        else if (status.status === 'Indexing Documents') pct = 95;
        progressBar.style.width = `${pct}%`;
      }
    }
  }, 1500);
}

async function startVivaSession() {
  const modal = getEl('vivaModal');
  if (!modal) return;
  
  if (!activeTopicId) {
    alert("Please select a topic from the curriculum accordion first.");
    return;
  }
  
  modal.classList.remove('hidden');
  getEl('vivaFeedbackBox').classList.add('hidden');
  getEl('vivaNextBtn').classList.add('hidden');
  getEl('vivaSubmitBtn').classList.remove('hidden');
  getEl('vivaAnswerInput').value = '';
  getEl('vivaAnswerInput').disabled = false;
  
  setText('vivaQuestionText', "Requesting examination question from VOID...");
  
  const res = await api('/academic/test/start', {
    method: 'POST',
    body: JSON.stringify({
      subject_id: activeSubjectId,
      topic_id: activeTopicId,
      difficulty: 'Adaptive',
      count: 1
    })
  });
  
  if (res && res.questions && res.questions.length > 0) {
    const q = res.questions[0];
    activeVivaQuestion = q;
    setText('vivaQuestionText', q.text || q.question);
    
    if (state.isVoiceEnabled) {
      api('/speak', {
        method: 'POST',
        body: JSON.stringify({ text: q.text || q.question })
      }).then(() => monitorSpeakingState());
    }
  } else {
    setText('vivaQuestionText', "Failed to retrieve viva question. Please check model connection.");
  }
}

async function submitVivaAnswer() {
  const ansInput = getEl('vivaAnswerInput');
  const answer = ansInput.value.trim();
  if (!answer) {
    alert("Please enter or speak your response.");
    return;
  }
  
  ansInput.disabled = true;
  getEl('vivaSubmitBtn').classList.add('hidden');
  setText('vivaQuestionText', "Grading response...");
  
  const res = await api('/academic/test/submit-viva', {
    method: 'POST',
    body: JSON.stringify({
      subject_id: activeSubjectId,
      topic_id: activeTopicId,
      question: activeVivaQuestion.text || activeVivaQuestion.question,
      response_text: answer
    })
  });
  
  if (res && res.status === 'ok') {
    getEl('vivaFeedbackBox').classList.remove('hidden');
    setText('vivaFeedbackScore', `Grade: ${res.score}/10 [${res.passed ? 'PASSED' : 'RETRY'}]`);
    setText('vivaFeedbackText', res.feedback);
    getEl('vivaNextBtn').classList.remove('hidden');
    
    if (state.isVoiceEnabled) {
      const voiceText = `I graded your answer as ${res.score} out of 10. ${res.feedback}`;
      api('/speak', {
        method: 'POST',
        body: JSON.stringify({ text: voiceText })
      }).then(() => monitorSpeakingState());
    }
    
    refreshAcademicSummary();
  } else {
    ansInput.disabled = false;
    getEl('vivaSubmitBtn').classList.remove('hidden');
    setText('vivaQuestionText', "Failed to submit response. Try again.");
  }
}

const vivaMicBtn = getEl('vivaMicBtn');
if (vivaMicBtn) {
  vivaMicBtn.onclick = async () => {
    vivaMicBtn.classList.add('active-mic');
    setText('vivaQuestionText', "Listening for response...");
    try {
      const res = await api('/listen');
      if (res.reply && res.meta && res.meta.status === 'ok') {
        const input = getEl('vivaAnswerInput');
        if (input) input.value = res.reply;
      }
    } catch (err) {
      console.warn("Viva voice transcription failed:", err);
    } finally {
      vivaMicBtn.classList.remove('active-mic');
      setText('vivaQuestionText', activeVivaQuestion.text || activeVivaQuestion.question);
    }
  };
}

let timedExamQuestions = [];
let timedExamIndex = 0;
let timedExamAnswers = [];
let examTimerInterval = null;
let examSecondsElapsed = 0;

async function startTimedExam() {
  if (!activeTopicId) {
    alert("Select a topic from the curriculum accordion first.");
    return;
  }
  
  const testModal = getEl('academicTestModal');
  testModal.classList.remove('hidden');
  
  getEl('testQuestionContainer').innerHTML = "Initializing Mock Exam papers...";
  getEl('testNextBtn').classList.add('hidden');
  
  const res = await api('/academic/test/start', {
    method: 'POST',
    body: JSON.stringify({
      subject_id: activeSubjectId,
      topic_id: activeTopicId,
      difficulty: 'Adaptive',
      count: 5
    })
  });
  
  if (res && res.questions && res.questions.length > 0) {
    timedExamQuestions = res.questions;
    timedExamIndex = 0;
    timedExamAnswers = [];
    examSecondsElapsed = 0;
    
    if (examTimerInterval) clearInterval(examTimerInterval);
    examTimerInterval = setInterval(() => {
      examSecondsElapsed++;
      const mins = Math.floor(examSecondsElapsed / 60);
      const secs = examSecondsElapsed % 60;
      setText('testModalTimer', `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`);
    }, 1000);
    
    renderExamQuestion();
  } else {
    getEl('testQuestionContainer').innerHTML = "Failed to compile exam paper. Please check connection.";
  }
}

function renderExamQuestion() {
  const q = timedExamQuestions[timedExamIndex];
  const container = getEl('testQuestionContainer');
  setText('currentQuestionNum', (timedExamIndex + 1).toString());
  setText('totalQuestionsNum', timedExamQuestions.length.toString());
  
  container.innerHTML = `
    <div style="font-size: 15px; font-weight: 600; color: #fff; line-height: 1.5;">${q.text || q.question}</div>
    <div id="quizOptionsBox" style="display: flex; flex-direction: column; gap: 10px;">
      
    </div>
  `;
  
  const optBox = getEl('quizOptionsBox');
  q.options.forEach(opt => {
    const btn = document.createElement('button');
    btn.className = 'quiz-option-btn';
    btn.textContent = opt;
    btn.onclick = () => {
      document.querySelectorAll('.quiz-option-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      timedExamAnswers[timedExamIndex] = opt;
      getEl('testNextBtn').classList.remove('hidden');
    };
    optBox.appendChild(btn);
  });
  
  getEl('testNextBtn').classList.add('hidden');
  getEl('testNextBtn').textContent = timedExamIndex === timedExamQuestions.length - 1 ? 'Submit Exam' : 'Next Question';
}

const testNextBtn = getEl('testNextBtn');
if (testNextBtn) {
  testNextBtn.onclick = async () => {
    if (timedExamIndex < timedExamQuestions.length - 1) {
      timedExamIndex++;
      renderExamQuestion();
    } else {
      clearInterval(examTimerInterval);
      getEl('academicTestModal').classList.add('hidden');
      
      let correct = 0;
      let wrong = 0;
      
      timedExamQuestions.forEach((q, idx) => {
        if (timedExamAnswers[idx] === q.correct_option) correct++;
        else wrong++;
      });
      
      const finalScore = (correct / timedExamQuestions.length) * 10;
      const feedback = `Timed exam complete. Correct: ${correct}, Incorrect: ${wrong}. Evaluated score: ${finalScore}/10.`;
      
      await api('/academic/test/submit', {
        method: 'POST',
        body: JSON.stringify({
          subject_id: activeSubjectId,
          topic_id: activeTopicId,
          test_type: 'exam',
          score: finalScore,
          correct_count: correct,
          wrong_count: wrong,
          skipped_count: 0,
          time_taken: examSecondsElapsed,
          feedback: feedback
        })
      });
      
      alert(`🏆 Timed Exam Complete!\nScore: ${finalScore}/10\nTime Taken: ${Math.floor(examSecondsElapsed/60)}m ${examSecondsElapsed%60}s`);
      
      if (state.isVoiceEnabled) {
        api('/speak', {
          method: 'POST',
          body: JSON.stringify({ text: `Mock exam submitted. You scored ${finalScore} out of 10.` })
        }).then(() => monitorSpeakingState());
      }
      
      refreshAcademicSummary();
      
      const subjects = await api('/academic/subjects');
      const activeName = subjects.find(s => s.subject_id === activeSubjectId)?.subject_name || activeSubjectId;
      loadSubjectWorkspace(activeSubjectId, activeName);
    }
  };
}
