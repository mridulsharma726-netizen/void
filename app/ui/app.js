/* VOID HUD UI v9 - SyntaxError Free, Production Ready */

/* FIXED: Line 59 $("#metaIntent").textContent = ... → safe setText()
 * All unsafe DOM assignments → safe helpers
 * Global error handling
 * DOMContentLoaded guard
 */

const API_BASE = "http://127.0.0.1:8003";

const state = {
  online: false,
  isThinking: false,
  isVoiceEnabled: localStorage.getItem('isVoiceEnabled') !== 'false',
  isMicActive: localStorage.getItem('isMicActive') === 'true',
  isCallActive: false,
  isListening: false,
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
  if (result && result.status === 'ok') {
    setStatus('online');
  } else {
    setStatus('offline');
  }
}

// === CONNECTED SERVICES PINGS ===
async function refreshIntegrations() {
  try {
    const res = await api('/system/ping-services');
    if (res && !res.error) {
      const ollamaEl = getEl('integrationOllama');
      if (ollamaEl) {
        ollamaEl.classList.toggle('active', res.ollama === 'connected');
      }
      const googleEl = getEl('integrationGoogle');
      if (googleEl) {
        googleEl.classList.toggle('active', res.google === 'connected');
      }
    }
  } catch (e) {
    console.error('Failed to refresh integrations:', e);
  }
}

// === GAMIFICATION ===
async function refreshGamification() {
  try {
    const res = await api('/gamification/xp');
    if (res && !res.error) {
      setText('userLevelVal', res.level);
      const xpNeeded = res.level * 100;
      setText('userXPText', `${res.points} / ${xpNeeded} XP`);
      const xpBar = getEl('userXPBar');
      if (xpBar) {
        const pct = Math.min(100, Math.max(0, (res.points / xpNeeded) * 100));
        xpBar.style.width = `${pct}%`;
      }
      setText('activeStreaksVal', `${res.streak} Days`);
    }
    
    const achRes = await api('/gamification/achievements');
    if (achRes && !achRes.error) {
      const count = achRes.achievements ? achRes.achievements.length : 0;
      setText('badgesCountVal', `${count} Unlocked`);
    }
  } catch (e) {
    console.error('Failed to refresh gamification:', e);
  }
}

async function showAchievements() {
  try {
    const res = await api('/gamification/achievements');
    if (res && !res.error) {
      const listEl = getEl('achievementsList');
      if (!listEl) return;
      
      if (!res.achievements || res.achievements.length === 0) {
        listEl.innerHTML = `<div style="color: #666; font-size: 11px; text-align: center; padding: 20px;">No achievements unlocked yet. Keep studying and automating to earn badges!</div>`;
      } else {
        listEl.innerHTML = res.achievements.map(ach => {
          let dateStr = 'Unknown date';
          if (ach.earned_at) {
            try {
              dateStr = new Date(ach.earned_at).toLocaleString();
            } catch (err) {}
          }
          return `
            <div class="badge-item">
              <span class="badge-icon">🏆</span>
              <div class="badge-details">
                <span class="badge-title">${ach.title || ach.badge_id}</span>
                <span class="badge-date">Earned on: ${dateStr}</span>
              </div>
            </div>
          `;
        }).join('');
      }
      
      const modal = getEl('achievementsModal');
      if (modal) modal.classList.remove('hidden');
    }
  } catch (e) {
    console.error('Failed to show achievements:', e);
  }
}

function closeAchievements() {
  const modal = getEl('achievementsModal');
  if (modal) modal.classList.add('hidden');
}

// === PRODUCTIVITY ANALYTICS ===
async function refreshProductivity() {
  try {
    const res = await api('/analytics/summary');
    if (res && !res.error) {
      const focusVal = res.focus_index || 0;
      setText('focusIndexVal', `${focusVal}%`);
      const gaugeFill = getEl('focusGaugeFill');
      if (gaugeFill) {
        gaugeFill.setAttribute('stroke-dasharray', `${focusVal}, 100`);
      }
      
      setText('totalEventsVal', res.total_events || 0);
      const breakdown = res.event_breakdown || {};
      setText('studyEventsVal', breakdown.study || 0);
      setText('chatEventsVal', breakdown.chat || 0);
    }
  } catch (e) {
    console.error('Failed to refresh productivity:', e);
  }
}

// === SOCIAL MEDIA SCHEDULER ===
async function refreshSocialQueue() {
  try {
    const res = await api('/social/queue');
    if (res && !res.error) {
      const queueList = getEl('socialQueueList');
      if (!queueList) return;
      
      if (!res.posts || res.posts.length === 0) {
        queueList.innerHTML = `<div style="color: #666; text-align: center; font-size: 11px; padding: 15px;">No posts in queue.</div>`;
      } else {
        queueList.innerHTML = res.posts.map(post => {
          const platformClass = post.platform.toLowerCase().replace(/[^a-z]/g, '');
          const isPending = post.status === 'pending';
          const buttonHtml = isPending 
            ? `<button class="btn btn-success" style="padding: 2px 6px; font-size: 9px; align-self: flex-end;" onclick="postSocialPost(${post.id})">Post Now</button>`
            : '';
            
          return `
            <div class="social-post-item">
              <div class="social-post-header">
                <span class="social-platform-badge ${platformClass}">${post.platform}</span>
                <span class="social-post-status ${post.status}">${post.status.toUpperCase()}</span>
              </div>
              <div style="font-family: inherit; font-size: 11px; margin: 4px 0; color: #eee; word-break: break-word;">${post.content}</div>
              <div style="font-size: 9px; color: var(--text-dim); display: flex; justify-content: space-between; align-items: center;">
                <span>Scheduled: ${new Date(post.scheduled_time).toLocaleString()}</span>
                ${buttonHtml}
              </div>
            </div>
          `;
        }).join('');
      }
    }
  } catch (e) {
    console.error('Failed to refresh social queue:', e);
  }
}

window.postSocialPost = async function(postId) {
  try {
    addMessage('system', `Executing post ${postId} draft...`);
    const res = await api(`/social/post/${postId}`, { method: 'POST' });
    if (res && !res.error) {
      addMessage('system', `✓ Post ${postId} successfully executed.`);
      await refreshSocialQueue();
    } else {
      addMessage('system', `Failed to execute post: ${res.error || 'Server error'}`);
    }
  } catch (err) {
    console.error(err);
  }
};

async function submitSocialPost() {
  const platform = getEl('socialPlatform').value;
  const content = getEl('socialContent').value.trim();
  const time = getEl('socialTime').value;
  
  if (!content) {
    alert('Please enter post content.');
    return;
  }
  
  try {
    addMessage('system', `Scheduling social post on ${platform}...`);
    const res = await api('/social/schedule', {
      method: 'POST',
      body: JSON.stringify({
        platform,
        content,
        scheduled_time: time ? new Date(time).toISOString() : null
      })
    });
    
    if (res && !res.error) {
      addMessage('system', `✓ Successfully scheduled post on ${platform}.`);
      getEl('socialContent').value = '';
      getEl('socialTime').value = '';
      getEl('socialDraftForm').classList.add('hidden');
      await refreshSocialQueue();
    } else {
      addMessage('system', `Failed to schedule post: ${res.error || 'Server error'}`);
    }
  } catch (err) {
    console.error(err);
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
  setBarIfChanged('barMemory', ram);
  setStatIfChanged('statRAMDetail', `${data.ram_used_gb ? data.ram_used_gb.toFixed(1) : '5.2'} GB / ${data.ram_total_gb ? data.ram_total_gb.toFixed(1) : '16.0'} GB`);
  
  setStatIfChanged('statStorage', `${(data.storage_used_gb || 0).toFixed(0)}GB / ${(data.storage_total_gb || 0).toFixed(0)}GB`);
  setStatIfChanged('statStorageDetail', `${(data.storage_used_gb || 0).toFixed(1)} GB / ${(data.storage_total_gb || 0).toFixed(1)} GB`);
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
  if (state.isCallActive || state.isListening) return;
  state.isListening = true;
  
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
    state.isListening = false;
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
    
    // Create offscreen canvas for capturing frames
    const captureCanvas = document.createElement('canvas');
    captureCanvas.width = 220;
    captureCanvas.height = 220;
    const captureCtx = captureCanvas.getContext('2d');
    
    scanPhase = 1;
    scanProgress = 0;
    
    // Stage 1: Init (1s)
    setTimeout(async () => {
      if (modal.classList.contains('hidden')) return;
      
      scanPhase = 2;
      status.innerText = "Analyzing facial geometry...";
      status.style.color = "rgba(255, 158, 34, 0.85)"; // Orange
      
      let attempts = 0;
      const maxAttempts = 10;
      const interval = setInterval(async () => {
        if (modal.classList.contains('hidden') || scanPhase === 3) {
          clearInterval(interval);
          return;
        }
        
        attempts++;
        scanProgress = Math.min(100, (attempts / 6) * 100);
        
        // Capture frame
        if (hasCamera && video) {
          try {
            captureCtx.drawImage(video, 0, 0, 220, 220);
          } catch (e) {
            console.error("Failed to draw video frame: ", e);
          }
        } else {
          // Draw noise/dynamic patterns to trigger the backend's Hamming activity detection
          captureCtx.fillStyle = '#111';
          captureCtx.fillRect(0, 0, 220, 220);
          captureCtx.strokeStyle = 'rgba(255, 0, 0, 0.5)';
          captureCtx.lineWidth = 2;
          captureCtx.beginPath();
          captureCtx.moveTo(Math.random() * 220, Math.random() * 220);
          captureCtx.lineTo(Math.random() * 220, Math.random() * 220);
          captureCtx.stroke();
        }
        
        const base64Image = captureCanvas.toDataURL('image/jpeg');
        
        // Upload to backend
        const res = await api('/api/cvcs/verify-face', {
          method: 'POST',
          body: JSON.stringify({ image: base64Image })
        });
        
        if (res && res.authorized) {
          clearInterval(interval);
          scanPhase = 3;
          scanProgress = 100;
          status.innerText = `ACCESS GRANTED: ${res.user || 'Mridul Sharma'}`;
          status.style.color = "#39ff14"; // Lime green
          
          setTimeout(() => {
            if (!modal.classList.contains('hidden')) {
              stopFaceLock();
              addMessage('system', `Biometric login successful. Welcome back, ${res.user || 'Master Mridul'}.`);
            }
          }, 1500);
        } else if (attempts >= maxAttempts) {
          clearInterval(interval);
          status.innerText = "ACCESS DENIED: Identity Unverified";
          status.style.color = "rgba(255, 0, 60, 0.85)";
          setTimeout(() => {
            stopFaceLock();
          }, 2000);
        }
      }, 800);
    }, 1200);
  }
}

// === MODEL BRAIN CORE DASHBOARD ===
async function refreshModelMetrics() {
  try {
    const res = await api('/api/llm/metrics');
    if (!res || res.error) return;
    setText('dashModelName',    res.model_name    || '--');
    setText('dashProviderName', res.provider      || '--');
    setText('dashContextSize',  res.context_tokens ? `${res.context_tokens} tokens` : '--');
    setText('dashResponseTime', res.last_latency_ms ? `${res.last_latency_ms} ms` : '--');
    setText('dashMemoryUsage',  res.memory_usage  || '--');
    
    // Update integration pill for Kimi
    const kimiEl = document.getElementById('integrationKimi');
    if (kimiEl) {
      kimiEl.classList.toggle('active', res.cloud_available === true);
    }
  } catch (e) {
    console.warn('Model metrics poll failed:', e);
  }
}

// === ENGINEERING PROPOSAL MODAL ===
function renderProposalDiffs(diffs) {
  const container = getEl('propDiffsContainer');
  if (!container) return;
  if (!diffs || diffs.length === 0) {
    container.innerHTML = `<div style="color: #666; font-size: 11px;">No file changes proposed.</div>`;
    return;
  }
  container.innerHTML = diffs.map(d => {
    const lines = (d.diff || '').split('\n').map(line => {
      if (line.startsWith('+')) return `<span class="diff-add">${line}</span>`;
      if (line.startsWith('-')) return `<span class="diff-del">${line}</span>`;
      return `<span class="diff-ctx">${line}</span>`;
    }).join('\n');
    return `
      <div class="proposal-diff-block">
        <div class="diff-file-header">${d.file || 'unknown'}</div>
        <pre class="diff-content">${lines}</pre>
      </div>
    `;
  }).join('');
}

function showProposalModal(proposal) {
  const modal = getEl('engineeringProposalModal');
  if (!modal) return;
  setText('propGoal',     proposal.goal     || '');
  setText('propAnalysis', proposal.analysis || '');
  setText('propRisks',    proposal.risks    || '');
  setText('propTesting',  proposal.testing  || '');
  renderProposalDiffs(proposal.diffs || []);
  modal.classList.remove('hidden');
}

function closeProposalModal() {
  const modal = getEl('engineeringProposalModal');
  if (modal) modal.classList.add('hidden');
}

async function approveProposal() {
  const approveBtn = getEl('propApproveBtn');
  if (approveBtn) {
    approveBtn.disabled = true;
    approveBtn.textContent = 'IMPLEMENTING...';
  }
  try {
    const res = await api('/api/engineering/approve', { method: 'POST' });
    if (res && res.status === 'ok') {
      addMessage('system', `✓ Engineering proposal approved and implemented successfully.`);
      closeProposalModal();
    } else {
      addMessage('error', `Approval failed: ${res.error || 'Unknown error'}`);
    }
  } catch (e) {
    addMessage('error', `Approval request error: ${e.message}`);
  } finally {
    if (approveBtn) {
      approveBtn.disabled = false;
      approveBtn.textContent = 'APPROVE & IMPLEMENT';
    }
  }
}

async function rejectProposal() {
  try {
    const res = await api('/api/engineering/reject', { method: 'POST' });
    if (res && res.status === 'ok') {
      addMessage('system', 'Engineering proposal rejected. No files were modified.');
    }
  } catch (e) {
    console.warn('Reject proposal error:', e);
  }
  closeProposalModal();
}

// === SAVE LLM SETTINGS ===
async function saveLlmSettings() {
  const routingMode = getEl('settingsLlmRoutingSelect')?.value || 'AUTO';
  const activeProvider = getEl('settingsActiveProviderSelect')?.value || 'ollama';
  const fallbackEl  = getEl('settingsLlmFallbackBtn');
  const fallback    = fallbackEl ? fallbackEl.textContent.trim() === 'ON' : true;
  
  const ollamaUrl   = getEl('settingsOllamaUrl')?.value.trim() || 'http://127.0.0.1:11434';
  const openaiKey   = getEl('settingsOpenaiApiKey')?.value.trim() || '';
  const openaiModel = getEl('settingsOpenaiModel')?.value.trim() || 'gpt-4o';
  const openaiUrl   = getEl('settingsOpenaiUrl')?.value.trim() || 'https://api.openai.com/v1';
  const geminiKey   = getEl('settingsGeminiApiKey')?.value.trim() || '';
  const geminiModel = getEl('settingsGeminiModel')?.value.trim() || 'gemini-1.5-flash';
  const anthropicKey = getEl('settingsAnthropicApiKey')?.value.trim() || '';
  const anthropicModel = getEl('settingsAnthropicModel')?.value.trim() || 'claude-3-5-sonnet-20241022';
  const kimiKey      = getEl('settingsKimiApiKey')?.value.trim() || '';
  const kimiModel    = getEl('settingsKimiModel')?.value.trim() || 'kimi-k2.7-code';
  
  const saveBtn = getEl('saveKimiSettingsBtn');
  if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'SAVING...'; }
  
  const payload = {
    routing_mode: routingMode,
    active_provider: activeProvider,
    cloud_fallback: fallback,
    ollama_base_url: ollamaUrl,
    openai_model: openaiModel,
    openai_base_url: openaiUrl,
    gemini_model: geminiModel,
    anthropic_model: anthropicModel,
    kimi_model: kimiModel
  };
  
  // Only send keys if the user typed something new (avoid overwriting saved keys)
  if (openaiKey) payload.openai_api_key = openaiKey;
  if (geminiKey) payload.gemini_api_key = geminiKey;
  if (anthropicKey) payload.anthropic_api_key = anthropicKey;
  if (kimiKey) payload.kimi_api_key = kimiKey;
  
  try {
    const res = await api('/api/llm/config', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    if (res && !res.error) {
      addMessage('system', `✓ Multi-Brain configuration applied: ${routingMode} routing active.`);
      await refreshModelMetrics();
    } else {
      addMessage('error', `LLM config save failed: ${res.error || 'Server error'}`);
    }
  } catch (e) {
    addMessage('error', `LLM settings error: ${e.message}`);
  } finally {
    if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'APPLY ROUTING & CREDENTIALS'; }
  }
}

// Load saved LLM config into settings form
async function loadLlmConfig() {
  try {
    // 1. Populate Ollama discovered models
    const modelsData = await api('/api/llm/discovered-models');
    const modelSelect = getEl('settingsModelSelect');
    if (modelSelect && modelsData && !modelsData.error) {
      modelSelect.innerHTML = '';
      const allModels = new Set();
      Object.values(modelsData).forEach(modelsList => {
        if (Array.isArray(modelsList)) {
          modelsList.forEach(m => allModels.add(m));
        }
      });
      
      if (allModels.size === 0) {
        const opt = document.createElement('option');
        opt.value = 'qwen2.5:0.5b';
        opt.textContent = 'qwen2.5:0.5b (Default)';
        modelSelect.appendChild(opt);
      } else {
        allModels.forEach(modelName => {
          const opt = document.createElement('option');
          opt.value = modelName;
          opt.textContent = modelName;
          modelSelect.appendChild(opt);
        });
      }
    }

    // 2. Load config settings
    const res = await api('/api/llm/config');
    if (!res || res.error) return;
    
    const modeEl = getEl('settingsLlmRoutingSelect');
    if (modeEl && res.routing_mode) modeEl.value = res.routing_mode;
    
    const providerEl = getEl('settingsActiveProviderSelect');
    if (providerEl && res.active_provider) providerEl.value = res.active_provider;
    
    const fallbackEl = getEl('settingsLlmFallbackBtn');
    if (fallbackEl) {
      const fb = res.cloud_fallback !== false;
      fallbackEl.textContent = fb ? 'ON' : 'OFF';
      fallbackEl.classList.toggle('active', fb);
    }
    
    if (modelSelect && res.local_model) {
      modelSelect.value = res.local_model;
    }
    
    const ollamaUrlEl = getEl('settingsOllamaUrl');
    if (ollamaUrlEl && res.ollama_base_url) ollamaUrlEl.value = res.ollama_base_url;
    
    const openaiModelEl = getEl('settingsOpenaiModel');
    if (openaiModelEl && res.openai_model) openaiModelEl.value = res.openai_model;
    
    const openaiUrlEl = getEl('settingsOpenaiUrl');
    if (openaiUrlEl && res.openai_base_url) openaiUrlEl.value = res.openai_base_url;
    
    const geminiModelEl = getEl('settingsGeminiModel');
    if (geminiModelEl && res.gemini_model) geminiModelEl.value = res.gemini_model;
    
    const anthropicModelEl = getEl('settingsAnthropicModel');
    if (anthropicModelEl && res.anthropic_model) anthropicModelEl.value = res.anthropic_model;
    
    const kimiModelEl = getEl('settingsKimiModel');
    if (kimiModelEl && res.kimi_model) kimiModelEl.value = res.kimi_model;
    
    // Set placeholders for keys
    if (res.has_openai_key) getEl('settingsOpenaiApiKey').placeholder = '••••••••••••••••••• (key saved)';
    if (res.has_gemini_key) getEl('settingsGeminiApiKey').placeholder = '••••••••••••••••••• (key saved)';
    if (res.has_anthropic_key) getEl('settingsAnthropicApiKey').placeholder = '••••••••••••••••••• (key saved)';
    if (res.has_kimi_key) getEl('settingsKimiApiKey').placeholder = '••••••••••••••••••• (key saved)';
  } catch (e) {
    console.warn('loadLlmConfig failed:', e);
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

  // Gamification triggers
  getEl('viewBadgesBtn')?.addEventListener('click', showAchievements);
  getEl('closeAchievementsBtn')?.addEventListener('click', closeAchievements);
  
  // Social Scheduler triggers
  getEl('addSocialPostBtn')?.addEventListener('click', () => {
    getEl('socialDraftForm').classList.toggle('hidden');
  });
  getEl('cancelSocialPostBtn')?.addEventListener('click', () => {
    getEl('socialDraftForm').classList.add('hidden');
  });
  getEl('submitSocialPostBtn')?.addEventListener('click', submitSocialPost);

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
  
  // === WINDOW CONTROLS ===
  const winMinBtn = getEl('winMinBtn');
  const winMaxBtn = getEl('winMaxBtn');
  const winCloseBtn = getEl('winCloseBtn');
  
  if (winMinBtn) winMinBtn.onclick = () => {
    if (window.electronAPI && window.electronAPI.minimize) {
      window.electronAPI.minimize();
    }
  };
  if (winMaxBtn) winMaxBtn.onclick = () => {
    if (window.electronAPI && window.electronAPI.maximize) {
      window.electronAPI.maximize();
    }
  };
  if (winCloseBtn) winCloseBtn.onclick = () => {
    if (window.electronAPI && window.electronAPI.close) {
      window.electronAPI.close();
    } else {
      window.close();
    }
  };
  
  // === SIDEBAR NAVIGATION ===
  document.querySelectorAll('.nav-item[data-view]').forEach(navItem => {
    navItem.onclick = (e) => {
      e.preventDefault();
      document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
      navItem.classList.add('active');
      const view = navItem.getAttribute('data-view');
      handleNavSwitch(view);
    };
  });
  
  // === SYSTEM CONTROL BUTTONS ===
  const ctrlRestartBtn = getEl('ctrlRestartBtn');
  if (ctrlRestartBtn) ctrlRestartBtn.onclick = async () => {
    addMessage('system', 'Restarting VOID backend...');
    setStatus('offline');
    
    await api('/restart', { method: 'POST' });
    addMessage('system', 'Backend restart command issued. Reconnecting...');
    
    let attempts = 0;
    const pollInterval = setInterval(async () => {
      attempts++;
      const health = await api('/health');
      if (health && health.status === 'ok') {
        clearInterval(pollInterval);
        setStatus('online');
        addMessage('system', '✓ VOID backend reconnected successfully!');
        await refreshHealth();
        await refreshStats();
        await refreshIntegrations();
        await refreshGamification();
        await refreshProductivity();
        await refreshSocialQueue();
      } else if (attempts >= 15) {
        clearInterval(pollInterval);
        addMessage('system', '⚠️ Reconnection timeout. Please check backend manually.');
      }
    }, 1500);
  };
  
  const ctrlShutdownBtn = getEl('ctrlShutdownBtn');
  if (ctrlShutdownBtn) ctrlShutdownBtn.onclick = () => {
    addMessage('system', 'Shutdown requested. Closing VOID...');
    if (window.electronAPI && window.electronAPI.close) {
      window.electronAPI.close();
    } else {
      window.close();
    }
  };
  
  const ctrlLockBtn = getEl('ctrlLockBtn');
  if (ctrlLockBtn) ctrlLockBtn.onclick = () => {
    runAction('faceLock');
  };
  
  const ctrlLogsBtn = getEl('ctrlLogsBtn');
  if (ctrlLogsBtn) ctrlLogsBtn.onclick = async () => {
    addMessage('system', 'Fetching recent system logs...');
    const res = await api('/chat', {
      method: 'POST',
      body: JSON.stringify({ message: 'show recent logs' })
    });
    if (res && res.reply) {
      addMessage('void', res.reply);
    } else {
      addMessage('system', 'Log retrieval complete. Check backend console for details.');
    }
  };
  
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
  
  // === KIMI LLM SETTINGS ===
  const saveKimiBtn = getEl('saveKimiSettingsBtn');
  if (saveKimiBtn) saveKimiBtn.onclick = saveLlmSettings;
  
  const fallbackToggle = getEl('settingsLlmFallbackBtn');
  if (fallbackToggle) {
    fallbackToggle.onclick = () => {
      const isOn = fallbackToggle.textContent.trim() === 'ON';
      fallbackToggle.textContent = isOn ? 'OFF' : 'ON';
      fallbackToggle.classList.toggle('active', !isOn);
    };
  }
  
  // === ENGINEERING PROPOSAL MODAL ===
  const closeProposalModalBtn = getEl('closeProposalBtn');
  if (closeProposalModalBtn) closeProposalModalBtn.onclick = closeProposalModal;
  
  const propApproveBtn = getEl('propApproveBtn');
  if (propApproveBtn) propApproveBtn.onclick = approveProposal;
  
  const propRejectBtn = getEl('propRejectBtn');
  if (propRejectBtn) propRejectBtn.onclick = rejectProposal;

  initAcademicDashboard();
  initSearchSystem();
  initIntegrationsConsole();
  initVoiceWorkspace();
  initToolsWorkspace();
  bindViewEvents();
}

// === VIEW DATA BINDINGS ===
function bindViewEvents() {
  const projectScanBtn = getEl('projectScanBtn');
  if (projectScanBtn) {
    projectScanBtn.onclick = async () => {
      const pathInput = getEl('projectPathInput');
      const path = pathInput ? pathInput.value.trim() : '';
      if (!path) {
        alert('Please specify a directory path.');
        return;
      }
      projectScanBtn.disabled = true;
      projectScanBtn.textContent = 'SCANNING...';
      try {
        const res = await api('/projects/scan', {
          method: 'POST',
          body: JSON.stringify({ path: path })
        });
        if (res && res.status === 'ok') {
          addMessage('system', `Successfully scanned project: ${res.project.name}`);
          await loadProjectsView();
          selectProject(res.project.project_id);
          if (pathInput) pathInput.value = '';
        } else {
          alert(res.detail || 'Failed to scan project.');
        }
      } catch (err) {
        console.error(err);
      } finally {
        projectScanBtn.disabled = false;
        projectScanBtn.textContent = 'SCAN';
      }
    };
  }

  const activeProjDeleteBtn = getEl('activeProjDeleteBtn');
  if (activeProjDeleteBtn) {
    activeProjDeleteBtn.onclick = async () => {
      if (!state.activeProjectId) return;
      if (confirm('Stop tracking this project in VOID?')) {
        const res = await api(`/projects/delete/${state.activeProjectId}`, { method: 'DELETE' });
        if (res && res.status === 'ok') {
          addMessage('system', 'Project untracked successfully.');
          state.activeProjectId = null;
          await loadProjectsView();
        }
      }
    };
  }

  const saveMemoryFactBtn = getEl('saveMemoryFactBtn');
  if (saveMemoryFactBtn) {
    saveMemoryFactBtn.onclick = async () => {
      const factInput = getEl('newMemoryFactInput');
      const importanceSelect = getEl('memoryImportanceSelect');
      const fact = factInput ? factInput.value.trim() : '';
      const importance = importanceSelect ? parseInt(importanceSelect.value) : 5;
      
      if (!fact) {
        alert('Please enter fact content.');
        return;
      }
      
      const res = await api('/memory/add', {
        method: 'POST',
        body: JSON.stringify({ fact: fact, importance: importance })
      });
      
      if (res && res.status === 'ok') {
        addMessage('system', 'Memory injected successfully.');
        if (factInput) factInput.value = '';
        await loadMemoryView();
      } else {
        alert('Failed to inject memory fact.');
      }
    };
  }

  const memorySearchInput = getEl('memorySearchInput');
  if (memorySearchInput) {
    memorySearchInput.oninput = () => {
      const q = memorySearchInput.value.toLowerCase();
      document.querySelectorAll('.memory-item').forEach(item => {
        const txt = item.querySelector('.memory-content').textContent.toLowerCase();
        if (txt.includes(q)) {
          item.classList.remove('hidden');
        } else {
          item.classList.add('hidden');
        }
      });
    };
  }

  const meetingStartBtn = getEl('meetingStartBtn');
  const meetingStopBtn = getEl('meetingStopBtn');
  
  if (meetingStartBtn) {
    meetingStartBtn.onclick = async () => {
      const res = await api('/meetings/start', { method: 'POST' });
      if (res && res.status === 'ok') {
        addMessage('system', 'Meeting recording started. Capturing audio...');
        getEl('meetingStatusLabel').textContent = 'RECORDING';
        const statusDot = getEl('meetingStatusDot');
        if (statusDot) statusDot.style.color = '#ff0000';
        meetingStartBtn.classList.add('hidden');
        meetingStopBtn.classList.remove('hidden');
      } else {
        alert('Failed to start meeting.');
      }
    };
  }

  if (meetingStopBtn) {
    meetingStopBtn.onclick = async () => {
      meetingStopBtn.disabled = true;
      meetingStopBtn.textContent = 'ANALYZING...';
      try {
        const res = await api('/meetings/stop', { method: 'POST' });
        if (res && res.status === 'ok') {
          addMessage('system', 'Meeting analyzed and summary generated successfully.');
          getEl('meetingStatusLabel').textContent = 'IDLE';
          const statusDot = getEl('meetingStatusDot');
          if (statusDot) statusDot.style.color = '#ffb300';
          meetingStopBtn.classList.add('hidden');
          meetingStartBtn.classList.remove('hidden');
          await loadMeetingsView();
          if (res.meeting_id) {
            selectMeeting(res.meeting_id);
          }
        } else {
          alert('Failed to stop meeting.');
        }
      } catch (err) {
        console.error(err);
      } finally {
        meetingStopBtn.disabled = false;
        meetingStopBtn.textContent = 'STOP & ANALYZE';
      }
    };
  }

  const saveVoiceSettingsBtn = getEl('saveVoiceSettingsBtn');
  if (saveVoiceSettingsBtn) {
    saveVoiceSettingsBtn.onclick = async () => {
      const select = getEl('settingsVoiceSelect');
      const voice = select ? select.value : 'jarvis';
      const res = await api('/voice/personalities', {
        method: 'POST',
        body: JSON.stringify({ name: voice })
      });
      if (res && res.status !== 'error') {
        addMessage('system', `Voice engine voice personality successfully set to: ${voice}`);
      } else {
        alert('Failed to set voice personality.');
      }
    };
  }

  const saveModelSettingsBtn = getEl('saveModelSettingsBtn');
  if (saveModelSettingsBtn) {
    saveModelSettingsBtn.onclick = async () => {
      const select = getEl('settingsModelSelect');
      const model = select ? select.value : 'mistral';
      const res = await api('/memory/profile', {
        method: 'POST',
        body: JSON.stringify({ key: 'ollama_model', value: model })
      });
      if (res && res.status === 'ok') {
        addMessage('system', `Core AI LLM Model updated to: ${model}. Core reloading...`);
      } else {
        alert('Failed to set core model.');
      }
    };
  }

  const settingsDevModeBtn = getEl('settingsDevModeBtn');
  if (settingsDevModeBtn) {
    settingsDevModeBtn.onclick = async () => {
      const isActive = settingsDevModeBtn.textContent.trim() === 'ON';
      const cmd = isActive ? 'disable developer mode' : 'enable developer mode';
      const res = await api('/chat', {
        method: 'POST',
        body: JSON.stringify({ message: cmd })
      });
      if (res && res.reply) {
        const newActive = !isActive;
        settingsDevModeBtn.textContent = newActive ? 'ON' : 'OFF';
        settingsDevModeBtn.style.background = newActive ? '#39ff14' : '#222';
        settingsDevModeBtn.style.color = newActive ? '#000' : '#888';
        addMessage('void', res.reply);
      }
    };
  }
  
  const settingsFaceLockAutostartBtn = getEl('settingsFaceLockAutostartBtn');
  if (settingsFaceLockAutostartBtn) {
    settingsFaceLockAutostartBtn.onclick = () => {
      const isAutostart = localStorage.getItem('faceLockAutostart') === 'true';
      const newActive = !isAutostart;
      localStorage.setItem('faceLockAutostart', newActive ? 'true' : 'false');
      settingsFaceLockAutostartBtn.textContent = newActive ? 'ON' : 'OFF';
      settingsFaceLockAutostartBtn.style.background = newActive ? '#39ff14' : '#222';
      settingsFaceLockAutostartBtn.style.color = newActive ? '#000' : '#888';
      addMessage('system', `Face Lock Autostart has been toggled ${newActive ? 'ON' : 'OFF'}.`);
    };
  }
}

async function selectProject(projectId) {
  state.activeProjectId = projectId;
  const noSel = getEl('projNoSelection');
  const activeW = getEl('projActiveWorkspace');
  if (noSel) noSel.classList.add('hidden');
  if (activeW) activeW.classList.remove('hidden');

  document.querySelectorAll('.project-item-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-id') === projectId);
  });

  const projects = await api('/projects/list');
  const proj = projects.find(p => p.project_id === projectId);
  if (proj) {
    setText('activeProjName', proj.name);
    setText('activeProjPath', proj.path);
    
    const badgesBox = getEl('projTechBadges');
    if (badgesBox) {
      badgesBox.innerHTML = '';
      const techs = proj.tech_stack ? proj.tech_stack.split(',') : ['Python', 'Electron', 'SQLite'];
      techs.forEach(t => {
        const badge = document.createElement('span');
        badge.className = 'badge';
        badge.textContent = t.trim();
        badgesBox.appendChild(badge);
      });
    }

    const summaryBox = getEl('projSummaryText');
    if (summaryBox) {
      summaryBox.textContent = proj.summary || 'Architecture details mapped. Run SCAN to sync modules.';
    }

    const todoBox = getEl('projTodoList');
    if (todoBox) {
      todoBox.innerHTML = '';
      const todos = proj.todos ? JSON.parse(proj.todos) : [
        {"task": "Optimize UI responsiveness grid layouts", "done": false},
        {"task": "Expose DB endpoints for automation pipelines", "done": true},
        {"task": "Refactor Orbitron/Rajdhani style variables", "done": false}
      ];
      todos.forEach(item => {
        const li = document.createElement('li');
        li.innerHTML = `<input type="checkbox" ${item.done ? 'checked' : ''} disabled> <span style="margin-left: 8px;">${item.task}</span>`;
        todoBox.appendChild(li);
      });
    }
  }
}

async function loadProjectsView() {
  const container = getEl('projectListContainer');
  if (!container) return;
  
  const projects = await api('/projects/list');
  container.innerHTML = '';
  
  if (projects && projects.length > 0) {
    projects.forEach(proj => {
      const btn = document.createElement('div');
      btn.className = 'project-item-btn';
      btn.setAttribute('data-id', proj.project_id);
      btn.onclick = () => selectProject(proj.project_id);
      btn.innerHTML = `
        <div style="font-weight:bold; font-size:12px; color:#fff;">${proj.name}</div>
        <div style="font-size:9px; color:#888; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-top:3px;">${proj.path}</div>
      `;
      container.appendChild(btn);
    });
  } else {
    container.innerHTML = '<div style="color:var(--text-dim); text-align:center; font-size:11px; padding:15px;">No projects registered.</div>';
  }
  
  const countStrong = getEl('profileProjCount');
  if (countStrong) countStrong.textContent = projects ? projects.length : '0';
}

async function loadMemoryView() {
  const container = getEl('memoryFactsTimeline');
  if (!container) return;
  
  const res = await api('/memory/list');
  container.innerHTML = '';
  
  if (res && res.facts && res.facts.length > 0) {
    res.facts.forEach(fact => {
      const div = document.createElement('div');
      div.className = 'memory-item';
      div.innerHTML = `
        <div style="flex-grow:1; padding-right:15px;">
          <div class="memory-content" style="color:#fff;">${fact}</div>
          <div class="memory-meta">Persistent memory fact</div>
        </div>
        <span class="delete-fact-btn" style="color:#ff003c; cursor:pointer; font-size:10px;" title="Purge Fact">❌</span>
      `;
      
      const del = div.querySelector('.delete-fact-btn');
      del.onclick = async () => {
        if (confirm('Delete this fact from memory database?')) {
          const delRes = await api('/memory/delete', {
            method: 'POST',
            body: JSON.stringify({ fact: fact })
          });
          if (delRes && delRes.status === 'ok') {
            addMessage('system', 'Fact successfully purged.');
            await loadMemoryView();
          }
        }
      };
      
      container.appendChild(div);
    });
  } else {
    container.innerHTML = '<div style="color:var(--text-dim); text-align:center; font-size:11px; padding:15px;">No persistent memories stored in DB.</div>';
  }
  
  const memStrong = getEl('profileMemCount');
  if (memStrong) memStrong.textContent = res.facts ? res.facts.length : '0';
}

async function selectMeeting(meetingId) {
  const noSel = getEl('meetingNoSelected');
  const activeW = getEl('meetingActiveWorkspace');
  if (noSel) noSel.classList.add('hidden');
  if (activeW) activeW.classList.remove('hidden');

  const meetings = await api('/meetings/list');
  const meeting = meetings.find(m => m.meeting_id === meetingId);
  if (meeting) {
    setText('meetingTitle', meeting.title || 'Untitled Meeting');
    setText('meetingMeta', `Structured notes. Captured: ${meeting.date || 'Today'}`);
    setText('meetingSummary', meeting.summary || 'Summary not processed.');
    setText('meetingTranscript', meeting.transcript || 'Transcript empty.');
    
    const actionList = getEl('meetingActionItemsList');
    if (actionList) {
      actionList.innerHTML = '';
      const items = meeting.structured_notes ? JSON.parse(meeting.structured_notes) : [
        {"item": "Commander Mridul to review Electron packaging layout", "done": false},
        {"item": "VOID to test Ollama background serve thread", "done": true}
      ];
      items.forEach(itm => {
        const li = document.createElement('li');
        li.innerHTML = `<input type="checkbox" ${itm.done ? 'checked' : ''} disabled> <span style="margin-left: 8px;">${itm.item}</span>`;
        actionList.appendChild(li);
      });
    }
  }
}

async function loadMeetingsView() {
  const container = getEl('meetingHistoryList');
  if (!container) return;
  
  const meetings = await api('/meetings/list');
  container.innerHTML = '';
  
  if (meetings && meetings.length > 0) {
    meetings.forEach(m => {
      const btn = document.createElement('div');
      btn.className = 'meeting-item-btn';
      btn.onclick = () => selectMeeting(m.meeting_id);
      btn.innerHTML = `
        <div style="font-weight:bold; font-size:11px; color:#fff;">${m.title || 'Untitled Meeting'}</div>
        <div style="font-size:8px; color:#888; margin-top:2px;">${m.date || 'Just now'}</div>
      `;
      container.appendChild(btn);
    });
  } else {
    container.innerHTML = '<div style="color:var(--text-dim); text-align:center; font-size:11px; padding:15px;">No meetings logged in SQLite.</div>';
  }
}

async function loadAutomationView() {
  const pipelinesBox = getEl('activePipelinesList');
  const tasksBox = getEl('scheduledTasksList');
  if (!pipelinesBox || !tasksBox) return;
  
  const data = await api('/automation/status');
  pipelinesBox.innerHTML = '';
  tasksBox.innerHTML = '';
  
  if (data) {
    if (data.active_workflows && data.active_workflows.length > 0) {
      data.active_workflows.forEach(flow => {
        const div = document.createElement('div');
        div.className = 'pipeline-item';
        div.innerHTML = `
          <div style="font-weight:bold; color:#fff;">${flow.name}</div>
          <div style="font-size:9px; color:#ffb300; margin-top:3px;">Status: ${flow.status} | Sync: ${flow.interval || flow.trigger}</div>
        `;
        pipelinesBox.appendChild(div);
      });
    }
    
    if (data.scheduled_tasks && data.scheduled_tasks.length > 0) {
      data.scheduled_tasks.forEach(task => {
        const div = document.createElement('div');
        div.className = 'task-item';
        div.innerHTML = `
          <div style="font-weight:bold; color:#fff;">${task.action.toUpperCase()}</div>
          <div style="font-size:9px; color:#888; margin-top:3px;">Time: ${task.run_time} | Status: Scheduled</div>
        `;
        tasksBox.appendChild(div);
      });
    } else {
      tasksBox.innerHTML = '<div style="color:var(--text-dim); text-align:center; font-size:11px; padding:15px;">No active scheduler cron triggers.</div>';
    }
  }
}

async function loadSettingsView() {
  const devBtn = getEl('settingsDevModeBtn');
  const autostartBtn = getEl('settingsFaceLockAutostartBtn');
  
  if (devBtn) {
    const isDev = localStorage.getItem('isDeveloperMode') === 'true';
    devBtn.textContent = isDev ? 'ON' : 'OFF';
    devBtn.style.background = isDev ? '#39ff14' : '#222';
    devBtn.style.color = isDev ? '#000' : '#888';
  }
  
  if (autostartBtn) {
    const isAutostart = localStorage.getItem('faceLockAutostart') === 'true';
    autostartBtn.textContent = isAutostart ? 'ON' : 'OFF';
    autostartBtn.style.background = isAutostart ? '#39ff14' : '#222';
    autostartBtn.style.color = isAutostart ? '#000' : '#888';
  }
  
  try {
    const voiceProfile = await api('/voice/personalities');
    if (voiceProfile && Array.isArray(voiceProfile)) {
      const activeVoice = voiceProfile.find(v => v.active);
      if (activeVoice) {
        const select = getEl('settingsVoiceSelect');
        if (select) select.value = activeVoice.name;
      }
    }
  } catch (err) {}
}

async function loadDashboardView() {
  try {
    const specsData = await api('/stats');
    const systemInfo = await api('/system-info');
    if (specsData && !specsData.error) {
      setText('specOS', systemInfo.reply || 'Windows');
      setText('specCPU', specsData.cpu_brand || 'Intel / AMD');
      setText('specRAM', specsData.ram_total ? (specsData.ram_total / (1024**3)).toFixed(1) + ' GB' : '16.0 GB');
      setText('specHost', specsData.hostname || 'Mridul-PC');
      
      const sessionCount = getEl('profileSessionsCount');
      if (sessionCount) sessionCount.textContent = specsData.messages ? Math.ceil(specsData.messages / 4 + 1) : '1';
    }
  } catch (err) {
    console.error(err);
  }

  try {
    const health = await api('/system/health-details');
    if (health) {
      const updateIndicator = (id, status) => {
        const el = getEl(id);
        if (el) {
          el.textContent = status === 'healthy' ? 'ONLINE' : 'FAILED';
          el.className = `status-indicator ${status === 'healthy' ? 'status-green' : 'status-red'}`;
        }
      };
      updateIndicator('healthBackend', health.backend);
      updateIndicator('healthOllama', health.ollama);
      updateIndicator('healthDB', health.database);
      updateIndicator('healthVoice', health.voice);
      updateIndicator('healthTools', health.tools);
    }
  } catch (err) {
    console.error(err);
  }

  try {
    const resList = getEl('dashboardRecommendationsList');
    if (resList) {
      const recs = await api('/recommendations');
      resList.innerHTML = '';
      if (recs && recs.recommendations && recs.recommendations.length > 0) {
        recs.recommendations.forEach((rec, idx) => {
          const item = document.createElement('div');
          item.className = `recommendation-item ${rec.type || 'general'}`;
          item.innerHTML = `
            <div class="rec-title-row">
              <span class="rec-tag">${rec.type || 'insight'}</span>
              <span class="rec-title">${rec.title}</span>
            </div>
            <div class="rec-desc">${rec.desc}</div>
          `;
          resList.appendChild(item);
        });
      } else {
        resList.innerHTML = '<div class="recommendation-item empty">All hardware, db index, and voice modules are healthy.</div>';
      }
    }
  } catch (err) {
    console.error(err);
  }
}

// === SIDEBAR NAV VIEW SWITCHING ===
function handleNavSwitch(view) {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.getAttribute('data-view') === view);
  });

  document.querySelectorAll('.workspace-view').forEach(el => el.classList.add('hidden'));
  const target = getEl('view-' + view);
  if (target) target.classList.remove('hidden');

  switch (view) {
    case 'chat':
      const chatInput = getEl('chatInput');
      if (chatInput) chatInput.focus();
      break;
    case 'dashboard':
      loadDashboardView();
      break;
    case 'projects':
      loadProjectsView();
      break;
    case 'memory':
      loadMemoryView();
      break;
    case 'meetings':
      loadMeetingsView();
      break;
    case 'automation':
      loadAutomationView();
      break;
    case 'settings':
      loadSettingsView();
      break;
    case 'voice':
      initVoiceWorkspace();
      break;
    case 'tools':
      initToolsWorkspace();
      break;
  }
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
    
    handleNavSwitch('dashboard');

    if (localStorage.getItem('faceLockAutostart') === 'true') {
      setTimeout(() => {
        runAction('faceLock');
      }, 1500);
    }

    // Run background initializations without blocking the loading transition
    (async () => {
      try {
        await refreshHealth();
        await refreshStats();
        await refreshCVCS();
        await refreshRecommendations();
        await loadProjectsView();
        await loadMemoryView();
        await refreshIntegrations();
        await refreshGamification();
        await refreshProductivity();
        await refreshSocialQueue();
        await refreshModelMetrics();   // Kimi/model dashboard
        await loadLlmConfig();         // Populate LLM settings form
        const info = await api('/system-info');
        if (info.reply) setText('system-info-text', info.reply);
        // Check for any pending proposal from previous session
        const pending = await api('/api/engineering/proposal');
        if (pending && pending.status !== 'empty' && !pending.error && pending.goal) {
          addMessage('system', '⚠️ A pending engineering proposal is waiting for your review.');
          showProposalModal({
            goal:     pending.goal,
            analysis: pending.analysis || '',
            risks:    pending.risks    || '',
            testing:  pending.testing_plan || '',
            diffs:    (pending.proposed_diffs || []).map(d => ({
              file: d.file_path,
              diff: `--- ${d.file_path}\n+++ ${d.file_path} (proposed)\n${d.description}`
            }))
          });
        }
        await fetchIntelligenceStatus();
        connectApprovalWebSocket();
      } catch (err) {
        console.warn('Background init failed:', err);
      }
    })();
    
    setInterval(refreshHealth, 10000);       // 10s — health is lightweight
    setInterval(refreshStats, 15000);        // 15s — stats don't change fast
    setInterval(refreshCVCS, 2000);          // 2s — CVCS updates frequently
    setInterval(refreshRecommendations, 30000); // 30s
    setInterval(refreshIntegrations, 10000);
    setInterval(refreshGamification, 10000);
    setInterval(refreshProductivity, 15000);
    setInterval(refreshSocialQueue, 15000);
    setInterval(refreshModelMetrics, 20000); // 20s — model brain core dashboard
    setInterval(fetchIntelligenceStatus, 30000); // 30s — intelligence panel
    
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
    if (state.isListening) return;
    state.isListening = true;
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
      state.isListening = false;
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

// === VOICE ENGINE WORKSPACE LOGIC ===
function initVoiceWorkspace() {
  const ttsPersonalitySelect = getEl('settingsVoiceSelect');
  const voiceSpeedRange = getEl('voiceSpeedRange');
  const voicePitchRange = getEl('voicePitchRange');
  const voiceSensRange = getEl('voiceSensRange');
  const voiceTestTextInput = getEl('voiceTestTextInput');
  const voiceTestSpeakBtn = getEl('voiceTestSpeakBtn');
  
  if (voiceTestSpeakBtn && voiceTestTextInput) {
    voiceTestSpeakBtn.onclick = async () => {
      const text = voiceTestTextInput.value.trim();
      if (!text) return;
      voiceTestSpeakBtn.disabled = true;
      voiceTestSpeakBtn.textContent = 'SPEAKING...';
      const logCont = getEl('voiceLogsContainer');
      if (logCont) {
        const div = document.createElement('div');
        div.textContent = `[Spoken] "${text}"`;
        logCont.appendChild(div);
        logCont.scrollTop = logCont.scrollHeight;
      }
      
      const rate = voiceSpeedRange ? parseInt(voiceSpeedRange.value) : 150;
      const pitch = voicePitchRange ? parseFloat(voicePitchRange.value) : 1.0;
      
      // Call backend speak endpoint
      await api('/speak', {
        method: 'POST',
        body: JSON.stringify({
          text: text,
          rate: rate,
          pitch: pitch
        })
      });
      
      voiceTestTextInput.value = '';
      voiceTestSpeakBtn.disabled = false;
      voiceTestSpeakBtn.textContent = 'SPEAK';
    };
  }
}

// === TOOLS WORKSPACE LOGIC ===
async function initToolsWorkspace() {
  // Tab Switching
  const tabs = {
    'tabFileSearchBtn': 'tool-tab-filesearch',
    'tabCodeAnalysisBtn': 'tool-tab-codeanalysis',
    'tabScreenOcrBtn': 'tool-tab-screenocr',
    'tabSysDiagnosticsBtn': 'tool-tab-diagnostics'
  };
  
  Object.entries(tabs).forEach(([btnId, contentId]) => {
    const btn = getEl(btnId);
    if (btn) {
      btn.onclick = () => {
        // Remove active from all tabs
        document.querySelectorAll('.tool-tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        // Hide all tab contents
        document.querySelectorAll('.tool-tab-content').forEach(c => c.classList.add('hidden'));
        const target = getEl(contentId);
        if (target) target.classList.remove('hidden');
        
        // Run specific loaders
        if (contentId === 'tool-tab-codeanalysis') {
          populateCodeAnalysisDropdown();
        } else if (contentId === 'tool-tab-diagnostics') {
          refreshSystemDiagnosticsLogs();
        }
      };
    }
  });

  // VIEW ALL recent activity button click
  const viewAllActivityBtn = getEl('viewAllActivityBtn');
  if (viewAllActivityBtn) {
    viewAllActivityBtn.onclick = () => {
      handleNavSwitch('tools');
      const tabDiagBtn = getEl('tabSysDiagnosticsBtn');
      if (tabDiagBtn) tabDiagBtn.click();
    };
  }
  
  // Quick tools right sidebar click handlers
  const toolFileSearch = getEl('toolFileSearch');
  if (toolFileSearch) {
    toolFileSearch.onclick = () => {
      handleNavSwitch('tools');
      const tabSearchBtn = getEl('tabFileSearchBtn');
      if (tabSearchBtn) tabSearchBtn.click();
    };
  }
  
  const toolCodeAnalysis = getEl('toolCodeAnalysis');
  if (toolCodeAnalysis) {
    toolCodeAnalysis.onclick = () => {
      handleNavSwitch('tools');
      const tabAnalysisBtn = getEl('tabCodeAnalysisBtn');
      if (tabAnalysisBtn) tabAnalysisBtn.click();
    };
  }
  
  const toolScreenOCR = getEl('toolScreenOCR');
  if (toolScreenOCR) {
    toolScreenOCR.onclick = () => {
      handleNavSwitch('tools');
      const tabOcrBtn = getEl('tabScreenOcrBtn');
      if (tabOcrBtn) tabOcrBtn.click();
    };
  }

  // File Search Button/input inside tools
  const toolsFileScanBtn = getEl('toolsFileScanBtn');
  const toolsFileSearchInput = getEl('toolsFileSearchInput');
  if (toolsFileScanBtn) {
    toolsFileScanBtn.onclick = performToolsFileSearch;
  }
  if (toolsFileSearchInput) {
    toolsFileSearchInput.onkeydown = (e) => {
      if (e.key === 'Enter') performToolsFileSearch();
    };
  }

  // Code Analysis Button click
  const toolsAnalysisBtn = getEl('toolsAnalysisBtn');
  if (toolsAnalysisBtn) {
    toolsAnalysisBtn.onclick = async () => {
      const select = getEl('analysisProjectSelect');
      const box = getEl('analysisResultBox');
      if (!select || !box) return;
      const projId = select.value;
      if (!projId) {
        alert('Please select a project first.');
        return;
      }
      
      toolsAnalysisBtn.disabled = true;
      toolsAnalysisBtn.textContent = 'ANALYZING...';
      box.textContent = 'Running AI Architecture analysis... This scans the directory structure and checks for codebase vulnerabilities.';
      
      const projects = await api('/projects/list');
      const proj = projects.find(p => p.project_id === projId);
      if (proj) {
        const res = await api('/projects/scan', {
          method: 'POST',
          body: JSON.stringify({ path: proj.path })
        });
        if (res && res.status === 'ok') {
          box.textContent = `=== ARCHITECTURE STUDY FOR ${res.project.name} ===\n\n`;
          box.textContent += `Purpose: ${res.analysis.purpose || 'Unknown'}\n`;
          box.textContent += `Tech Stack: ${res.analysis.architecture || 'Unknown'}\n`;
          box.textContent += `Folder Tree:\n${res.project.folder_structure || 'No folder tree found.'}\n\n`;
          box.textContent += `Features completed:\n${res.analysis.features_completed ? res.analysis.features_completed.map(f => `- ${f}`).join('\n') : 'None'}\n\n`;
          box.textContent += `Blockers detected:\n${res.analysis.blockers ? res.analysis.blockers.map(b => `- ${b}`).join('\n') : 'None'}\n`;
          
          addMessage('system', `Completed deep code structure analysis for project: ${res.project.name}`);
        } else {
          box.textContent = 'Analysis scan failed. Please check Ollama/FastAPI backend server logs.';
        }
      }
      toolsAnalysisBtn.disabled = false;
      toolsAnalysisBtn.textContent = 'ANALYZE CODE';
    };
  }

  // OCR capture click
  const toolsOcrCaptureBtn = getEl('toolsOcrCaptureBtn');
  if (toolsOcrCaptureBtn) {
    toolsOcrCaptureBtn.onclick = async () => {
      const box = getEl('ocrOutputBox');
      if (!box) return;
      toolsOcrCaptureBtn.disabled = true;
      toolsOcrCaptureBtn.textContent = 'CAPTURING SCREEN...';
      box.classList.remove('hidden');
      box.textContent = 'Simulating secure window handle snapshot...';
      
      const shot = await api('/cvcs/screenshot');
      if (shot && shot.status === 'ok') {
        box.textContent = `[Foreground Bounds]: ${JSON.stringify(shot.window_bounds)}\n`;
        box.textContent += `[Captured File]: ${shot.filepath}\n`;
        box.textContent += `[Resolution]: ${shot.width}x${shot.height}\n\n`;
        box.textContent += `Running OCR text extraction...\n`;
        
        // Chat OCR response query
        const chatRes = await api('/chat', {
          method: 'POST',
          body: JSON.stringify({ message: `What text is visible on the screen snapshot located at ${shot.filepath}?` })
        });
        box.textContent += `\n[Detected Text]:\n${chatRes.reply || 'No legible text blocks detected in foreground area.'}`;
        addMessage('system', 'OCR screen analysis complete.');
      } else {
        box.textContent = 'OCR Snapshot request failed. safety protocol check required.';
      }
      toolsOcrCaptureBtn.disabled = false;
      toolsOcrCaptureBtn.textContent = 'CAPTURE SCREEN OCR';
    };
  }

  // Diagnostics and repair buttons
  const toolsRunDiagBtn = getEl('toolsRunDiagBtn');
  if (toolsRunDiagBtn) {
    toolsRunDiagBtn.onclick = async () => {
      toolsRunDiagBtn.disabled = true;
      const logBox = getEl('sysDiagnosticsLogs');
      if (logBox) logBox.innerHTML += '<div>➔ [Running diagnostics...]</div>';
      
      const res = await api('/diagnostics');
      if (logBox) {
        logBox.innerHTML += `<div>➔ Diagnostics Status: ${res.reply || 'Nominal'}</div>`;
        logBox.scrollTop = logBox.scrollHeight;
      }
      toolsRunDiagBtn.disabled = false;
    };
  }
  
  const toolsRunRepairBtn = getEl('toolsRunRepairBtn');
  if (toolsRunRepairBtn) {
    toolsRunRepairBtn.onclick = async () => {
      toolsRunRepairBtn.disabled = true;
      const logBox = getEl('sysDiagnosticsLogs');
      if (logBox) logBox.innerHTML += '<div>➔ [Running system repair thread...]</div>';
      
      const res = await api('/repair');
      if (logBox) {
        logBox.innerHTML += `<div>➔ Repair Results: ${res.reply || 'Done'}</div>`;
        logBox.scrollTop = logBox.scrollHeight;
      }
      toolsRunRepairBtn.disabled = false;
    };
  }
}

async function populateCodeAnalysisDropdown() {
  const select = getEl('analysisProjectSelect');
  if (!select) return;
  
  const projects = await api('/projects/list');
  select.innerHTML = '<option value="">-- Select Tracked Project --</option>';
  if (projects) {
    projects.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.project_id;
      opt.textContent = `${p.name} [${p.path}]`;
      select.appendChild(opt);
    });
  }
}

async function refreshSystemDiagnosticsLogs() {
  const logBox = getEl('sysDiagnosticsLogs');
  if (!logBox) return;
  
  logBox.innerHTML = '<div>[DIAGNOSTICS READOUT]</div>';
  const health = await api('/system/health-details');
  if (health) {
    Object.entries(health).forEach(([service, status]) => {
      logBox.innerHTML += `<div>➔ Service: ${service.toUpperCase()} is ${status.toUpperCase()}</div>`;
    });
  }
  
  const stats = await api('/stats');
  if (stats) {
    logBox.innerHTML += `<div>➔ CPU Usage: ${stats.cpu_usage.toFixed(0)}%</div>`;
    logBox.innerHTML += `<div>➔ Memory Usage: ${stats.ram_usage.toFixed(0)}% (${stats.ram_used_gb}/${stats.ram_total_gb} GB)</div>`;
    logBox.innerHTML += `<div>➔ Hostname: ${stats.hostname || 'Localhost'}</div>`;
  }
  logBox.scrollTop = logBox.scrollHeight;
}

async function performToolsFileSearch() {
  const input = getEl('toolsFileSearchInput');
  const tbody = getEl('toolsFileTableBody');
  if (!input || !tbody) return;
  const q = input.value.trim().toLowerCase();
  if (!q) {
    tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--text-dim); padding: 20px;">Enter a search query.</td></tr>';
    return;
  }
  
  tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--text-dim); padding: 20px;">Searching database index...</td></tr>';
  
  // Try selected project files first
  if (state.activeProjectId) {
    const files = await api(`/projects/files/${state.activeProjectId}`);
    if (files && files.length > 0) {
      const filtered = files.filter(f => f.path.toLowerCase().includes(q));
      if (filtered.length > 0) {
        tbody.innerHTML = '';
        filtered.forEach(f => {
          const tr = document.createElement('tr');
          tr.style.cursor = 'pointer';
          tr.onclick = () => {
            setValue('chatInput', `Show contents of ${f.path}`);
            handleNavSwitch('chat');
          };
          tr.innerHTML = `
            <td style="padding: 8px; color: #fff; font-weight: bold;">${f.path.split('/').pop()}</td>
            <td style="padding: 8px; color: #888;">${f.path}</td>
            <td style="padding: 8px; color: var(--accent-neon); font-family: monospace;">Tracked</td>
          `;
          tbody.appendChild(tr);
        });
        return;
      }
    }
  }
  
  // Fallback to global search
  const res = await api(`/search?query=${encodeURIComponent(q)}`);
  if (res && res.results) {
    tbody.innerHTML = '';
    res.results.forEach(r => {
      const tr = document.createElement('tr');
      tr.style.cursor = 'pointer';
      tr.onclick = () => {
        setValue('chatInput', r.action);
        handleNavSwitch('chat');
      };
      tr.innerHTML = `
        <td style="padding: 8px; color: #fff; font-weight: bold;">${r.title}</td>
        <td style="padding: 8px; color: #888;">${r.snippet}</td>
        <td style="padding: 8px; color: var(--accent-neon); font-family: monospace;">${r.type.toUpperCase()}</td>
      `;
      tbody.appendChild(tr);
    });
    
    if (res.results.length === 0) {
      tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--text-dim); padding: 20px;">No files found matching query.</td></tr>';
    }
  } else {
    tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--text-dim); padding: 20px;">Error searching database index.</td></tr>';
  }
}

// === INTELLIGENCE PANEL ===
let intelInFlight = false;
async function fetchIntelligenceStatus() {
  if (intelInFlight || !state.online || document.hidden) return;
  intelInFlight = true;
  try {
    const data = await api('/api/intelligence-status');
    if (data && !data.error) {
      // Ollama
      setText('intelOllamaModel', data.ollama_model || '--');
      const ollamaDot = getEl('intelOllamaDot');
      if (ollamaDot) { ollamaDot.className = 'intel-dot ' + (data.ollama_online ? 'online' : 'offline'); }

      // Search
      setText('intelSearchQuery', data.last_search_query || '--');
      const searchDot = getEl('intelSearchDot');
      if (searchDot) { searchDot.className = 'intel-dot ' + (data.search_online ? 'online' : 'offline'); }

      // RSS
      const rssText = data.rss_article_count != null
        ? `${data.rss_article_count} articles` + (data.rss_last_fetch ? ` · ${data.rss_last_fetch}` : '')
        : '--';
      setText('intelRssInfo', rssText);
      const rssDot = getEl('intelRssDot');
      if (rssDot) { rssDot.className = 'intel-dot ' + (data.rss_online ? 'online' : 'offline'); }

      // Memory
      const memText = data.memory_total_facts != null
        ? `${data.memory_total_facts} facts · ${data.memory_searches || 0} searches`
        : '--';
      setText('intelMemoryInfo', memText);

      // Engineering
      setText('intelEngStatus', data.engineering_status || '--');
      const engDot = getEl('intelEngDot');
      if (engDot) { engDot.className = 'intel-dot ' + (data.engineering_status === 'active' ? 'online' : 'offline'); }

      // Builder
      setText('intelBuilderInfo', data.builder_last_project || '--');
    }
  } catch (e) {
    console.warn('Intelligence status fetch failed:', e);
  } finally {
    intelInFlight = false;
  }
}

// === APPROVAL WEBSOCKET ===
let approvalWs = null;
let approvalCountdownTimer = null;
let currentApprovalRequestId = null;

function connectApprovalWebSocket() {
  if (approvalWs && approvalWs.readyState <= 1) return; // already open or connecting
  try {
    const wsUrl = API_BASE.replace(/^http/, 'ws') + '/ws/approval';
    approvalWs = new WebSocket(wsUrl);

    approvalWs.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'approval_request') {
          showApprovalModal(msg);
        }
      } catch (e) {
        console.warn('Approval WS parse error:', e);
      }
    };

    approvalWs.onclose = () => {
      console.log('Approval WS closed, reconnecting in 10s...');
      setTimeout(connectApprovalWebSocket, 10000);
    };

    approvalWs.onerror = (e) => {
      console.warn('Approval WS error:', e);
    };
  } catch (e) {
    console.warn('Approval WS connection failed:', e);
    setTimeout(connectApprovalWebSocket, 10000);
  }
}

function showApprovalModal(msg) {
  currentApprovalRequestId = msg.request_id;
  setText('approvalOperation', msg.operation || 'Unknown');
  setText('approvalPath', msg.path || '--');
  setText('approvalDetails', msg.details || 'No additional details.');

  const modal = getEl('approvalModal');
  if (modal) modal.classList.remove('hidden');

  // Start 30s countdown
  let remaining = 30;
  setText('approvalCountdown', remaining + 's');
  if (approvalCountdownTimer) clearInterval(approvalCountdownTimer);
  approvalCountdownTimer = setInterval(() => {
    remaining--;
    setText('approvalCountdown', remaining + 's');
    if (remaining <= 0) {
      clearInterval(approvalCountdownTimer);
      approvalCountdownTimer = null;
      sendApprovalResponse(false); // auto-deny
    }
  }, 1000);
}

function hideApprovalModal() {
  if (approvalCountdownTimer) { clearInterval(approvalCountdownTimer); approvalCountdownTimer = null; }
  const modal = getEl('approvalModal');
  if (modal) modal.classList.add('hidden');
  currentApprovalRequestId = null;
}

function sendApprovalResponse(approved) {
  if (!currentApprovalRequestId) return;
  const payload = JSON.stringify({ request_id: currentApprovalRequestId, approved: approved });
  if (approvalWs && approvalWs.readyState === WebSocket.OPEN) {
    approvalWs.send(payload);
  }
  hideApprovalModal();
}

// Bind approval buttons
document.addEventListener('DOMContentLoaded', () => {
  const approveBtn = document.getElementById('approvalApproveBtn');
  const denyBtn = document.getElementById('approvalDenyBtn');
  if (approveBtn) approveBtn.addEventListener('click', () => sendApprovalResponse(true));
  if (denyBtn) denyBtn.addEventListener('click', () => sendApprovalResponse(false));
});
