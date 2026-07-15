# VOID — Program Structure and Features Inventory

This document lists all active features of the VOID project, where they are defined, and the complete codebase file tree.

---

## 📂 Codebase Program Tree

```
VOID/
├── app/                             # Frontend Cockpit (Electron)
│   ├── main.js                      # Electron main entry point
│   ├── package.json                 # Node package configuration
│   └── ui/                          # HUD User Interface
│       ├── index.html               # Main dashboard UI
│       ├── app.js                   # Client state management, polling, charts
│       └── style.css                # Futuristic HUD glassmorphic styles
├── server/                          # Backend API Engine (FastAPI)
│   ├── main.py                      # Server initialization and routes
│   ├── requirements.txt             # Python libraries
│   ├── schemas.py                   # Pydantic validation schemas
│   └── backend/                     # Submodules and Logic layers
│       ├── admin.py                 # Admin configurations & health checks
│       ├── audio_memory_service.py  # Background mic recordings
│       ├── builder_agent.py         # Autonomous builder logic
│       ├── llm_client.py            # Local Ollama facades
│       ├── ollama_manager.py        # Ollama server daemon watcher
│       ├── memory_manager.py        # RAG embedding-based memory manager
│       ├── memory_sqlite.py         # SQLite data access objects (DAO)
│       └── providers/               # LLM Provider Interfaces
│           ├── router.py            # Multi-Brain routing engine (Gemini/Claude/Ollama)
│           ├── ollama_local.py      # Local Ollama integration
│           ├── gemini_compatible.py # Google Gemini API integration
│           └── anthropic_compatible.py # Anthropic Claude API integration
├── tools/                           # Host OS Automations
│   ├── pc_control.py                # App launch, URL execution, folder opening
│   ├── cv_control.py                # OCR, screen cropping, bounds detection
│   ├── system_stats.py              # Telemetry (CPU, RAM, Disk, battery)
│   ├── voice_listener.py            # Continuous voice control wrapper
│   ├── voice_stt.py                 # Speech transcription logic
│   └── voice_tts.py                 # Speech generation logic
└── memory/                          # Local Database & User Profile
    └── data/
        └── memory.db                # SQLite database (history, facts, preferences)
```

---

## 🛠️ Complete Features Inventory

### 1. Chat System & Greetings Intercept
* **Description**: Processes user chats, instantly resolves greetings and creators query intercepts, and routes others to the LLM.
* **Files**: [server/main.py](file:///c:/Users/HP/OneDrive/Desktop/void/VOID/server/main.py)
* **Status**: **Working**

### 2. Multi-Brain LLM Provider Router
* **Description**: Supports local Ollama engines as well as Cloud APIs (Gemini, Claude, ChatGPT, and Kimi). Allows saving keys in settings and handles routing.
* **Files**: [server/backend/providers/router.py](file:///c:/Users/HP/OneDrive/Desktop/void/VOID/server/backend/providers/router.py)
* **Status**: **Working**

### 3. Voice Control (STT & TTS)
* **Description**: Listens for wake words ( Hey Jarvis ) and commands. Synthesizes replies out loud using Edge-TTS.
* **Files**: [tools/voice_stt.py](file:///c:/Users/HP/OneDrive/Desktop/void/VOID/tools/voice_stt.py), [tools/voice_listener.py](file:///c:/Users/HP/OneDrive/Desktop/void/VOID/tools/voice_listener.py), [tools/voice_tts.py](file:///c:/Users/HP/OneDrive/Desktop/void/VOID/tools/voice_tts.py)
* **Status**: **Working**

### 4. Vector Memory (RAG)
* **Description**: Stores facts and retrieves relevant past notes using SQLite and cosine-similarity searches on local embeddings.
* **Files**: [server/backend/memory_manager.py](file:///c:/Users/HP/OneDrive/Desktop/void/VOID/server/backend/memory_manager.py)
* **Status**: **Working**

### 5. Code Intelligence & scan
* **Description**: Recursively scans files up to 1000 items, skips lockfiles and large logs (e.g. `.gemini` logs), computes health scores, and draws HTML5 Canvas charts representing file trees, dependencies, and code sizes.
* **Files**: [server/routes/code_intelligence.py](file:///c:/Users/HP/OneDrive/Desktop/void/VOID/server/routes/code_intelligence.py)
* **Status**: **Working**

### 6. PC Control & Automation
* **Description**: Launches system apps, triggers YouTube search playbacks, opens folders, captures screenshots, and monitors processes.
* **Files**: [tools/pc_control.py](file:///c:/Users/HP/OneDrive/Desktop/void/VOID/tools/pc_control.py)
* **Status**: **Working**

### 7. Live Information Dashboard
* **Description**: Fetches meteorological reports (Weather), digital clock arrays, stock market price tickers, and RSS news feeds.
* **Files**: [server/routes/live_intel.py](file:///c:/Users/HP/OneDrive/Desktop/void/VOID/server/routes/live_intel.py)
* **Status**: **Working**

### 8. System Telemetry & Metrics
* **Description**: Polls host machine CPU, RAM, Disk space, and network latency, rendering real-time animated gauges.
* **Files**: [tools/system_stats.py](file:///c:/Users/HP/OneDrive/Desktop/void/VOID/tools/system_stats.py)
* **Status**: **Working**

---

## 🧪 Testing Instructions

To run all unit and integration tests across these features, use the virtual environment's pytest command:
```bash
# Run feature tests
venv\Scripts\pytest.exe tests/test_new_features.py -v

# Run system routing tests
venv\Scripts\pytest.exe test_routing_upgrade.py -v

# Run security checks
venv\Scripts\pytest.exe tests/test_security_hardening.py -v
```
