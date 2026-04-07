# 🚀 VOID - CORRECT STARTUP PROCEDURE

## ✅ Prerequisites

1. **Python 3.11** installed
2. **Ollama** installed and running
   - Download: https://ollama.com/download
   - Run: `ollama serve`
   - Pull model: `ollama pull llama3.2:3b`
3. **FFplay** (for TTS) - already configured at:
   - `C:\Users\HP\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffplay.exe`

---

## 🔧 METHOD 1: Backend Only (FastAPI)

### Step 1: Navigate to VOID directory
```powershell
cd C:\Users\HP\OneDrive\Desktop\void\VOID
```

### Step 2: Activate virtual environment
```powershell
.\venv\Scripts\activate
```

### Step 3: Install/Update dependencies (first time or after updates)
```powershell
pip install -r requirements.txt
```

### Step 4: Start backend server
```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

✅ Backend will be running at: **http://127.0.0.1:8000**

### Step 5: Open UI in browser
- Open your browser and go to: `file:///C:/Users/HP/OneDrive/Desktop/void/VOID/ui/index.html`
- Or use Live Server extension in VS Code

---

## 🖥️ METHOD 2: Electron Desktop App (Recommended)

### Step 1: Navigate to desktop directory
```powershell
cd C:\Users\HP\OneDrive\Desktop\void\VOID\desktop
```

### Step 2: Install Electron dependencies (first time only)
```powershell
npm install
```

### Step 3: Start Electron app
```powershell
npm start
```

✅ This will:
- Auto-start the FastAPI backend
- Load the UI in an Electron window
- Handle everything automatically

---

## 🛠️ Troubleshooting

### Problem: Port 8000 already in use
**Solution:**
```powershell
# Find processes using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID with actual process ID)
taskkill /F /PID <PID>
```

### Problem: Multiple Python processes running
**Solution:**
```powershell
# List all Python processes
tasklist | findstr python

# Kill all Python processes
taskkill /F /IM python.exe
```

### Problem: Ollama not responding
**Solution:**
```powershell
# Check if Ollama is running
ollama list

# Restart Ollama
# Close Ollama from system tray and restart it
```

### Problem: TTS not working
**Solution:**
1. Check if edge-tts is installed: `pip show edge-tts`
2. Verify ffplay.exe path in `VOID/tools/voice_tts.py`
3. Test TTS: Visit `http://127.0.0.1:8000/tts-test`

### Problem: Voice input not working
**Solution:**
1. Check microphone permissions
2. Test with: `python -c "import speech_recognition as sr; print(sr.Microphone.list_microphone_names())"`

---

## 📋 Verification Checklist

After starting VOID, verify all features:

- [ ] Backend health: http://127.0.0.1:8000/health returns `{"status":"ok"}`
- [ ] UI loads and shows "ONLINE" status (green dot)
- [ ] Stats panel updates (uptime, messages, etc.)
- [ ] Send a chat message: "time"
- [ ] Test tool: "open notepad"
- [ ] Test workflow: "open chrome then search cats"
- [ ] Test memory: "remember my favorite color is blue"
- [ ] Test memory recall: "show memory"
- [ ] Test TTS: Toggle "VOICE: ON" and send a message
- [ ] Test voice input: Click 🎙 button
- [ ] Test identity: Ask "who created you" → Should say "I was created by Mridul Sharma."

---

## ⚠️ IMPORTANT NOTES

1. **DO NOT run server.py** - It's deprecated. Use `main.py` instead.
2. **Always activate venv** before running Python commands
3. **Make sure Ollama is running** before starting VOID
4. **Voice toggle persists** in localStorage - it remembers your preference
5. **Stop TTS** by toggling voice OFF or sending /stop-speak

---

## 🎯 Quick Start Commands

### Backend (PowerShell):
```powershell
cd C:\Users\HP\OneDrive\Desktop\void\VOID
.\venv\Scripts\activate
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

### Electron (PowerShell):
```powershell
cd C:\Users\HP\OneDrive\Desktop\void\VOID\desktop
npm start
```

---

## 📝 File Structure (Reference)

```
VOID/
├── main.py                 ✅ REAL BACKEND (use this)
├── server.py               ❌ DEPRECATED (don't use)
├── requirements.txt        ✅ Updated with edge-tts
├── core/
│   ├── brain.py           ✅ Fixed identity rule
│   ├── config.py          ✅ Fixed model name
│   ├── router.py
│   ├── intent_router.py
│   ├── memory.py
│   └── internet.py
├── tools/
│   ├── voice_tts.py       ✅ Working TTS
│   ├── voice_stt.py       ✅ Added listen() wrapper
│   └── system_tools.py
├── workflows/
│   ├── workflow_engine.py
│   └── workflow_library.py
├── ui/
│   ├── index.html
│   ├── style.css
│   └── app.js             ✅ COMPLETE FRONTEND CODE
├── desktop/
│   ├── main.js            ✅ Electron entry point
│   └── package.json
└── venv/                  ✅ Virtual environment
```

---

**Created by Mridul Sharma** 🚀
