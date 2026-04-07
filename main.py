"""
VOID Desktop AI Assistant - Main Backend
Stabilized version with FastAPI, Ollama, Voice, Memory, and Tools.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import requests
import datetime
import platform
import subprocess
from pathlib import Path
import json
import os
import re
import time
import sys

# Fix UTF-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VOID")

# Import system logger for self-engineering features
try:
    from core.logger import log_startup, log_error, log_repair, log_file_modification, log_command, log_diagnostics, log_event
    SYSTEM_LOGGER_AVAILABLE = True
except ImportError:
    SYSTEM_LOGGER_AVAILABLE = False
    # Fallback functions
    def log_startup(): pass
    def log_error(*args, **kwargs): pass
    def log_repair(*args, **kwargs): pass
    def log_file_modification(*args, **kwargs): pass
    def log_command(*args, **kwargs): pass
    def log_diagnostics(*args, **kwargs): pass
    def log_event(*args, **kwargs): pass

# System monitoring imports (psutil & GPUtil)
try:
    import psutil
    import GPUtil
    GPUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    GPUtil = None
    GPUTIL_AVAILABLE = False

# ============================================================================
# PROTECTED IMPORTS - Never crash backend startup
# ============================================================================

# Workflow imports
try:
    from workflows.workflow_engine import WorkflowEngine
    from workflows.workflow_library import WORKFLOWS
except Exception as e:
    print(f"[VOID WARNING] Workflow import failed: {e}")
    WorkflowEngine = None
    WORKFLOWS = {}

# Workflow Mode imports
try:
    from workflow_mode import is_workflow_command, build_workflow_steps
except Exception as e:
    print(f"[VOID WARNING] Workflow mode import failed: {e}")
    is_workflow_command = lambda x: False
    build_workflow_steps = lambda x: None

# Agent imports
try:
    from core.agent import VoidAgent
except Exception as e:
    print(f"[VOID WARNING] Agent import failed: {e}")
    VoidAgent = None

# Voice imports
try:
    from tools.voice_tts import VoiceTTS, speak as tts_speak, speak_async, stop_speaking as tts_stop, is_speaking
except Exception as e:
    print(f"[VOID WARNING] TTS import failed: {e}")
    VoiceTTS = None
    tts_speak = None
    speak_async = None
    tts_stop = None
    is_speaking = lambda: False

try:
    from tools.voice_stt import VoiceSTT
except Exception as e:
    print(f"[VOID WARNING] STT import failed: {e}")
    VoiceSTT = None

# Tools imports
try:
    from tools.system_stats import SystemStats
except Exception as e:
    print(f"[VOID WARNING] SystemStats import failed: {e}")
    SystemStats = None

# Network Scapy tools - Full toolkit
try:
    from tools.network_scapy import (
        ping_host, port_scan, sniff_packets, 
        traceroute_host, dns_lookup, validate_ip
    )
    SCAPY_TOOLS_AVAILABLE = True
except Exception as e:
    print(f"[VOID WARNING] Network Scapy tools import failed: {e}")
    SCAPY_TOOLS_AVAILABLE = False
    ping_host = port_scan = sniff_packets = traceroute_host = dns_lookup = None

try:
    from tools.file_status import FileStatus
except Exception as e:
    print(f"[VOID WARNING] FileStatus import failed: {e}")
    FileStatus = None

try:
    from tools.self_repair import repair_system as _repair_system_func
    repair_system = _repair_system_func
except Exception as e:
    print(f"[VOID WARNING] Self-repair import failed: {e}")
    repair_system = None

# PC Control imports
try:
    from tools.pc_control import open_app as pc_open_app, open_url as pc_open_url, open_folder as pc_open_folder, search_web as pc_search_web, play_youtube as pc_play_youtube
except Exception as e:
    print(f"[VOID WARNING] PC Control import failed: {e}")
    pc_open_app = None
    pc_open_url = None
    pc_open_folder = None
    pc_search_web = None
    pc_play_youtube = None

# Network ping intent (chat integration)
PING_INTENT_KEYWORDS = ["ping", "check latency", "is internet working"]

# Intent Detector
try:
    from tools.intent_detector import detect_intent
except Exception as e:
    print(f"[VOID WARNING] Intent detector import failed: {e}")
    detect_intent = None

# Agent Controller (LLM tool selection)
try:
    from tools.agent_controller import parse_action
except Exception as e:
    print(f"[VOID WARNING] Agent controller import failed: {e}")
    parse_action = None

# Command Interpreter
try:
    from core.command_interpreter import interpret_command, execute_command, is_void_command, APP_MAP
except Exception as e:
    print(f"[VOID WARNING] Command interpreter import failed: {e}")
    interpret_command = lambda x: None
    execute_command = lambda x: {"status": "error", "message": "Not available"}
    is_void_command = lambda x: False
    APP_MAP = {}

# Tool Registry
try:
    from tools.registry import tool_registry, execute_tool, parse_llm_tool_call
except Exception as e:
    print(f"[VOID WARNING] Tool registry import failed: {e}")
    tool_registry = None
    execute_tool = None
    parse_llm_tool_call = None

# Self-Modification imports (new)
try:
    from tools.error_interpreter import translate_exception, get_ui_error_response, format_diagnostics_error, interpret_error
    from tools.code_tools import read_file, write_file, list_project_files, restart_void, get_system_status
    from tools.self_modifier import (
        scan_project, analyze_file, rewrite_module, improve_system, 
        self_repair_workflow, handle_repair_command, handle_scan_command,
        handle_rewrite_command, handle_improve_command
    )
    SELF_MODIFICATION_AVAILABLE = True
except Exception as e:
    print(f"[VOID WARNING] Self-modification import failed: {e}")
    SELF_MODIFICATION_AVAILABLE = False
    translate_exception = None
    get_ui_error_response = None
    interpret_error = None

# ============================================================================
# STARTUP
# ============================================================================
print("=" * 60)
print("VOID BACKEND STABLE BUILD")
print("=" * 60)

# Log system startup
if SYSTEM_LOGGER_AVAILABLE:
    log_startup()

# App
app = FastAPI(title="VOID Backend", version="7.2-STABLE")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Config
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "llama3.2:3b"
OLLAMA_TIMEOUT = 90
DATA_DIR = "data"
MEMORY_FILE = os.path.join(DATA_DIR, "memory.json")
SERVER_START_TS = time.time()

# Stats
STATS = {
    "total_messages": 0,
    "tool_calls": 0,
    "chat_replies": 0,
    "memory_adds": 0,
    "memory_forgets": 0,
}

# ============================================================================
# CONDITIONAL INITIALIZATION
# ============================================================================

tts = None
if VoiceTTS:
    try:
        tts = VoiceTTS()
        print("[VOID TTS] Initialized")
    except Exception as e:
        print(f"[VOID WARNING] TTS init failed: {e}")

stt = None
if VoiceSTT:
    try:
        stt = VoiceSTT()
        print("[VOID STT] Initialized")
    except Exception as e:
        print(f"[VOID WARNING] STT init failed: {e}")

system_stats = None
if SystemStats:
    try:
        system_stats = SystemStats()
        print("[VOID SYSTEM STATS] Initialized")
    except Exception as e:
        print(f"[VOID WARNING] SystemStats init failed: {e}")

file_status = None
if FileStatus:
    try:
        file_status = FileStatus()
        print("[VOID FILE STATUS] Initialized")
    except Exception as e:
        print(f"[VOID WARNING] FileStatus init failed: {e}")

# ============================================================================
# SCHEMAS
# ============================================================================

class ChatRequest(BaseModel):
    text: Optional[str] = None
    message: Optional[str] = None

class FileStatusRequest(BaseModel):
    path: str

# ============================================================================
# APP MAP
# ============================================================================

# APP_MAP centralized in core.command_interpreter - import below

# Chat History
CHAT_HISTORY: List[Dict[str, str]] = []
MAX_HISTORY_MESSAGES = 20

def trim_history():
    global CHAT_HISTORY
    if len(CHAT_HISTORY) > MAX_HISTORY_MESSAGES:
        CHAT_HISTORY = CHAT_HISTORY[-MAX_HISTORY_MESSAGES:]

# ============================================================================
# MEMORY FUNCTIONS
# ============================================================================

def ensure_memory_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"facts": []}, f, indent=2, ensure_ascii=False)

def load_memory() -> Dict[str, Any]:
    ensure_memory_file()
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("facts"), list):
                return data
            return {"facts": []}
    except Exception:
        return {"facts": []}

def save_memory(mem: Dict[str, Any]):
    ensure_memory_file()
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(mem, f, indent=2, ensure_ascii=False)

def memory_count() -> int:
    return len(load_memory().get("facts", []))

def memory_as_text() -> str:
    facts = load_memory().get("facts", [])
    if not facts:
        return "No saved memory yet."
    return "\n".join([f"{i}. {fact}" for i, fact in enumerate(facts, start=1)])

def add_fact(fact: str) -> bool:
    fact = (fact or "").strip()
    if not fact:
        return False
    mem = load_memory()
    facts = mem.get("facts", [])
    for f in facts:
        if f.lower().strip() == fact.lower().strip():
            return False
    facts.append(fact)
    mem["facts"] = facts
    save_memory(mem)
    STATS["memory_adds"] += 1
    return True

def clear_memory():
    save_memory({"facts": []})

def forget_keyword(keyword: str) -> int:
    keyword = (keyword or "").strip().lower()
    if not keyword:
        return 0
    mem = load_memory()
    facts = mem.get("facts", [])
    new_facts = [f for f in facts if keyword not in f.lower()]
    removed = len(facts) - len(new_facts)
    mem["facts"] = new_facts
    save_memory(mem)
    return removed

def search_memory_keyword(keyword: str) -> List[str]:
    keyword = (keyword or "").strip().lower()
    if not keyword:
        return []
    mem = load_memory()
    facts = mem.get("facts", [])
    return [f for f in facts if keyword in f.lower()]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def clean_app_target(text: str) -> str:
    t = (text or "").strip().lower()
    junk_words = ["please", "now", "quickly", "fast", "for me", "bro", "boss", "sir", "open", "start", "launch", "close", "exit", "stop", "the", "a", "an"]
    for w in junk_words:
        t = t.replace(w, " ")
    return re.sub(r"\s+", " ", t).strip()

def best_app_match(target: str) -> str:
    t = (target or "").strip().lower()
    if t in APP_MAP:
        return t
    t2 = t.replace(" ", "")
    for k in APP_MAP.keys():
        if k.replace(" ", "") == t2:
            return k
    for k in APP_MAP.keys():
        if t in k:
            return k
    return t

def make_response(reply: str, tool_calls=None, workflow=None, memory=None):
    """Always return structured response with human-readable reply"""
    clean_reply = (reply or "").strip()
    
    # Strip JSON from reply
    if clean_reply.startswith("{"):
        clean_reply = "Processing complete."
    
    payload = {
        "reply": clean_reply,
        "meta": {
            "tool_calls": tool_calls or [],
            "memory": memory,
        },
    }
    if workflow is not None:
        payload["workflow"] = workflow
    return payload

def safe_json_extract(text: str) -> Optional[dict]:
    if not text:
        return None
    text = text.strip()
    stack = []
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if not stack:
                start = i
            stack.append(ch)
        elif ch == "}":
            if stack:
                stack.pop()
                if not stack and start != -1:
                    candidate = text[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        start = -1
                        continue
    return None

def compute_level(facts: int, tool_calls: int) -> int:
    score = facts * 3 + tool_calls
    if score < 10:
        return 1
    if score < 25:
        return 2
    if score < 50:
        return 3
    if score < 90:
        return 4
    return 5

# ============================================================================
# OLLAMA HEALTH CHECK FUNCTIONS
# ============================================================================

def check_ollama() -> bool:
    """
    Check if Ollama server is running and accessible.
    Returns True if Ollama is online, False otherwise.
    """
    try:
        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        return response.status_code == 200
    except Exception as e:
        print(f"[OLLAMA HEALTH CHECK] Failed: {e}")
        return False

# Global Ollama availability flag (checked once at startup)
OLLAMA_AVAILABLE = False

# Check Ollama at startup (non-blocking, 2s timeout)
print("[VOID INIT] Checking Ollama availability...")
OLLAMA_AVAILABLE = check_ollama()
print(f"[VOID INIT] Backend started | Ollama: {'YES' if OLLAMA_AVAILABLE else 'NO (offline mode)'}")

# ============================================================================
# FIRST RUN SETUP CHECK
# ============================================================================
SETUP_FLAG = "setup_done.flag"

def run_setup():
    """Run setup.py safely if needed."""
    flag_path = Path(SETUP_FLAG)
    if flag_path.exists():
        print(f"[VOID SETUP] Flag exists: {flag_path}")
        return True
    
    print("[VOID SETUP] Running first-time setup...")
    try:
        result = subprocess.run([sys.executable, "setup.py"], 
                              cwd=os.path.dirname(os.path.abspath(__file__)),
                              capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            print("[VOID SETUP] ✅ Complete")
            flag_path.write_text(f"Setup run at {time.ctime()}\n")
            return True
        else:
            print(f"[VOID SETUP] Warning: Exit {result.returncode}")
            print(f"STDERR: {result.stderr}")
    except Exception as e:
        print(f"[VOID SETUP] Error: {e}")
    
    flag_path.write_text(f"Setup attempted at {time.ctime()}\n")
    return False

run_setup()

# ============================================================================
# TOOL FUNCTIONS
# ============================================================================

def tool_open_app(app: str):
    STATS["tool_calls"] += 1
    try:
        name = best_app_match(clean_app_target(app))
        if name not in APP_MAP:
            return {"status": "error", "message": f"Unknown app: {app}"}
        cmd = APP_MAP[name]
        subprocess.Popen(["cmd", "/c", "start", "", cmd], shell=True)
        return {"status": "ok", "message": f"Opened {name}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def tool_open_url(url: str):
    STATS["tool_calls"] += 1
    try:
        subprocess.Popen(["cmd", "/c", "start", "", url], shell=True)
        return {"status": "ok", "message": f"Opened {url}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def tool_search_google(query: str):
    STATS["tool_calls"] += 1
    q = (query or "").strip()
    if not q:
        return {"status": "error", "message": "Missing search query"}
    url = "https://www.google.com/search?q=" + q.replace(" ", "+")
    return tool_open_url(url)

def tool_play_youtube(query: str):
    STATS["tool_calls"] += 1
    q = (query or "").strip()
    if not q:
        return {"status": "error", "message": "Missing YouTube query"}
    url = "https://www.youtube.com/results?search_query=" + q.replace(" ", "+")
    return tool_open_url(url)

# ============================================================================
# SYSTEM PROMPT
# ============================================================================

def build_system_prompt() -> str:
    mem_text = memory_as_text()
    prompt = f"""You are VOID, an offline AI assistant created by Mridul Sharma. 

SAVED MEMORY: {mem_text}

CONVERSATION RULES:
- Respond to greetings like "hello", "hi", "how are you" with friendly conversation
- Answer questions directly in plain text
- Be helpful and conversational

TOOL USE - When user requests an action, respond with:
ACTION: tool_name
ARGS: argument

Available tools:
- open_app (app_name) - Open applications like chrome, notepad, calculator
- open_url (url) - Open websites in browser
- open_folder (folder) - Open folders like downloads, documents
- search_google (query) - Search on Google
- play_youtube (query) - Search and play on YouTube
- system_info - Get system information
- time - Get current time

Example responses:
User: "open chrome"
ACTION: open_app
ARGS: chrome

User: "search for cats"
ACTION: search_google
ARGS: cats

User: "what time is it"
ACTION: time
ARGS: 

User: "hello"
Just respond naturally with conversation.

IMPORTANT:
- You are VOID, created by Mridul Sharma
- Use ACTION format only when tool/action is needed
- Default to plain text conversation
"""
    return prompt

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "ollama": OLLAMA_AVAILABLE
    }

@app.get("/stats")
def get_stats():
    uptime_sec = int(time.time() - SERVER_START_TS)
    facts = memory_count()
    level = compute_level(facts, STATS["tool_calls"])

    sys_data = {
        'cpu_usage': psutil.cpu_percent(interval=0.1) if psutil else 0,
        'ram_usage': psutil.virtual_memory().percent if psutil else 0,
        'network_online': True,
    }

    return {
        "uptime": uptime_sec,
        "messages": STATS["total_messages"],
        "tool_calls": STATS["tool_calls"],
        "memory_facts": facts,
        "void_level": level,
        "cpu_usage": sys_data['cpu_usage'],
        "ram_usage": sys_data['ram_usage'],
        "network_online": sys_data['network_online'],
    }

@app.post("/chat")
def chat(req: ChatRequest):
    global CHAT_HISTORY
    
    prompt = (req.message or req.text or "").strip()
    if not prompt:
        return {"reply": "Say something, Boss."}

    STATS["total_messages"] += 1

    # Simple tool interception
    lower = prompt.lower()
    if "time" in lower:
        t = get_time()
        STATS["chat_replies"] += 1
        return {"reply": f"{t['time']} on {t['day']}, {t['date']}"}

    if "memory" in lower:
        STATS["chat_replies"] += 1
        return {"reply": memory_as_text()}

    if lower.startswith("remember "):
        fact = prompt[9:].strip()
        add_fact(fact)
        STATS["chat_replies"] += 1
        return {"reply": "Remembered."}

    # LLM fallback if available
    if OLLAMA_AVAILABLE:
        try:
            messages = [{"role": "user", "content": prompt}]
            r = requests.post(OLLAMA_URL, json={"model": OLLAMA_MODEL, "messages": messages, "stream": False}, timeout=30)
            data = r.json()
            reply = data.get("message", {}).get("content", "No response.")
            STATS["chat_replies"] += 1
            return {"reply": reply}
        except:
            pass

    STATS["chat_replies"] += 1
    return {"reply": "VOID ready. What can I do for you?"}

@app.get("/time")
def get_time():
    STATS["tool_calls"] += 1
    now = datetime.datetime.now()
    return {
        "time": now.strftime("%I:%M %p"),
        "date": now.strftime("%d %b %Y"),
        "day": now.strftime("%A"),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

