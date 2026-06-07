import asyncio
import json
import logging
import subprocess
import socket
import time
import requests
import sys
import platform
import re
from pathlib import Path
from typing import Dict, Any, List

from fastapi import FastAPI, Request, Depends, HTTPException, File, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Add project root and server to path
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
if str(ROOT_DIR / "server") not in sys.path:
    sys.path.append(str(ROOT_DIR / "server"))

# Core imports
from backend.schemas import ChatRequest, TextRequest, CVCSPermissionRequest, CVCSActionRequest
from backend.intent_router import IntentRouter
from backend.llm_client import OllamaClient
from backend.memory_manager import MemoryManager
from backend.tools_runtime import ToolRuntime
from backend.tool_manager import ToolManager
from backend.validator import ResponseValidator
from backend.repair_system import RepairSystem
from backend.diagnostics import DiagnosticsEngine

# Tools imports
from tools.system_stats import SystemStats
from tools.pc_control import open_app as launch
from tools.voice_tts import speak as tts_speak, stop as tts_stop, is_speaking as tts_is_speaking
from tools.voice_stt import listen_once

# Singletons - lazy load
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger("void.main")

APP_START = time.time()
DATA_DIR = ROOT_DIR / "memory" / "data"
DATA_DIR.mkdir(exist_ok=True, parents=True)
(ROOT_DIR / "logs").mkdir(exist_ok=True)

STATS = {"messages": 0, "tools": 0}

import secrets

def get_or_generate_api_token() -> str:
    """Reads or generates a secure API token for local authentication."""
    config_file = DATA_DIR / "secure_config.json"
    token = None
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                token = config_data.get("api_token")
        except Exception as e:
            logger.warning(f"Error reading secure config: {e}")
            
    if not token:
        token = secrets.token_hex(32)
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump({"api_token": token}, f, indent=4)
            logger.info("[SECURITY] Generated new secure API token.")
        except Exception as e:
            logger.error(f"Error saving secure config: {e}")
            
    return token

API_TOKEN = get_or_generate_api_token()

class VoidSingletons:
    """Consolidated singletons."""
    _instances = {}
    
    @classmethod
    def get(cls, name):
        if name not in cls._instances:
            try:
                if name == "router":
                    cls._instances[name] = IntentRouter()
                elif name == "llm":
                    cls._instances[name] = OllamaClient()
                elif name == "memory":
                    cls._instances[name] = MemoryManager(DATA_DIR)
                elif name == "tool_manager":
                    runtime = ToolRuntime()
                    cls._instances[name] = ToolManager(runtime)
                elif name == "validator":
                    cls._instances[name] = ResponseValidator()
                else:
                    cls._instances[name] = None
            except Exception as e:
                logger.error(f"Singleton {name} initialization failed: {e}", exc_info=True)
                cls._instances[name] = None
        return cls._instances[name]

def _get_memory():
    """Get singleton MemoryManager."""
    return VoidSingletons.get("memory") or MemoryManager(DATA_DIR)

# === OLLAMA HELPERS ===
async def is_ollama_ready():
    try:
        with socket.socket() as s:
            s.settimeout(1)
            return s.connect_ex(('127.0.0.1', 11434)) == 0
    except:
        return False

async def ensure_ollama():
    if await is_ollama_ready():
        # Check if model exists
        try:
            from backend.llm_client import OllamaClient
            llm = OllamaClient()
            resp = requests.get(llm.tags_url, timeout=2)
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                if llm.model not in models and f"{llm.model}:latest" not in models:
                    logger.info(f"Model {llm.model} missing. Attempting to pull...")
                    # Non-blocking pull
                    subprocess.Popen(["ollama", "pull", llm.model])
        except:
            pass
        return True
    try:
        logger.info("Starting ollama serve...")
        p = await asyncio.to_thread(lambda: subprocess.Popen(
            ["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ))
        for _ in range(15): # Increased wait
            if await is_ollama_ready():
                logger.info("Ollama ready")
                return True
            await asyncio.sleep(1.0)
    except Exception as e:
        logger.error(f"Ollama start failed: {e}")
    return False

# === HEALTH & TOOLS ===
async def check_all_tools():
    """Simple tool check."""
    tm = VoidSingletons.get("tool_manager")
    if not tm:
        return {"status": "error", "tools": [], "message": "ToolManager unavailable"}
    try:
        return await tm.check_all_tools()
    except Exception as e:
        logger.error(f"Tool check failed: {e}")
        return {"status": "error", "tools": [], "message": str(e)}

def process_voice_command(command: str):
    """
    Callback triggered by voice listener when a command is spoken after the wake word.
    """
    logger.info(f"[WAKE WORD BACKGROUND] Processing voice command: {command}")
    
    async def run_chat():
        try:
            from backend.schemas import ChatRequest
            req = ChatRequest(message=command)
            res = await chat(req)
            reply = res.get("reply", "")
            if reply:
                logger.info(f"[WAKE WORD BACKGROUND] Speaking reply: {reply}")
                from tools.voice_tts import speak
                speak(reply)
        except Exception as e:
            logger.error(f"[WAKE WORD BACKGROUND] Error in voice command execution: {e}")
            
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(run_chat(), loop)
        else:
            loop.run_until_complete(run_chat())
    except Exception as e:
        logger.error(f"[WAKE WORD BACKGROUND] Loop submission error: {e}")

_voice_thread = None

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for VOID."""
    logger.info("VOID startup...")
    # 1. Ollama
    ollama_ok = await ensure_ollama()
    
    # 2. Singletons test
    singles = ["router", "llm", "tool_manager", "validator"]
    failed = []
    for s in singles:
        inst = VoidSingletons.get(s)
        if not inst:
            failed.append(s)
    
    # 3. Tools
    tools_ok = await check_all_tools()
    
    # 4. Non-blocking LLM warmup
    llm = VoidSingletons.get("llm")
    if llm:
        logger.info("Warming up LLM Client (pre-loading model)...")
        asyncio.create_task(llm.warmup())
        
    # 5. Start Wake Word service as background daemon
    try:
        from tools.voice_listener import start_voice_loop_thread, set_command_callback, set_activation_phrase
        set_activation_phrase("Yes?")
        set_command_callback(process_voice_command)
        global _voice_thread
        _voice_thread = start_voice_loop_thread()
        logger.info("[LIFESPAN] Wake word background daemon successfully initiated.")
    except Exception as e:
        logger.error(f"[LIFESPAN] Failed to start wake word daemon: {e}")
        
    # 6. Start CVCS Monitor Loop
    try:
        from server.backend.screen_monitor import get_monitor_instance
        monitor = get_monitor_instance()
        monitor.start_monitor_loop()
        logger.info("[LIFESPAN] CVCS background monitor loop initiated.")
    except Exception as e:
        logger.error(f"[LIFESPAN] Failed to start CVCS monitor: {e}")
        
    logger.info(f"Startup complete: ollama={ollama_ok}, singles_failed={len(failed)}, tools={tools_ok['status']}")
    
    yield
    
    logger.info("VOID shutdown...")
    # Stop voice loop on shutdown
    try:
        from tools.voice_listener import stop_voice_loop
        stop_voice_loop()
        logger.info("[LIFESPAN] Wake word background daemon stopped.")
    except Exception as e:
        logger.error(f"[LIFESPAN] Failed to stop wake word daemon: {e}")
        
    # Stop CVCS monitor loop on shutdown
    try:
        from server.backend.screen_monitor import get_monitor_instance
        monitor = get_monitor_instance()
        monitor.stop_monitor_loop()
        logger.info("[LIFESPAN] CVCS background monitor loop stopped.")
    except Exception as e:
        logger.error(f"[LIFESPAN] Failed to stop CVCS monitor: {e}")

# === APP ===
app = FastAPI(title="VOID Backend", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    resp = await call_next(request)
    logger.info(f"{request.method} {request.url.path} - {resp.status_code} - {(time.time()-start)*1000:.0f}ms")
    return resp

# Exempt paths from token verification (like /health)
EXEMPT_PATHS = {"/health", "/docs", "/openapi.json"}

@app.middleware("http")
async def secure_token_auth_middleware(request: Request, call_next):
    # Allow CORS preflight requests
    if request.method == "OPTIONS":
        return await call_next(request)
        
    # Check if request path is exempt
    if request.url.path in EXEMPT_PATHS:
        return await call_next(request)
        
    # Token check
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "Access Denied: Missing Authorization Header"}
        )
        
    try:
        scheme, token = auth_header.split()
        if scheme.lower() != "bearer" or token != API_TOKEN:
            return JSONResponse(
                status_code=401,
                content={"status": "error", "message": "Access Denied: Invalid Security Token"}
            )
    except Exception:
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "Access Denied: Malformed Authorization Header"}
        )
        
    return await call_next(request)

@app.exception_handler(Exception)
async def error_handler(request, exc):
    logger.error(f"Unhandled: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal error - recovery active"}
    )

from core.brain import is_developer_mode

class PermissionManager:
    """Verifies Guest, User, Developer, and Admin permissions."""
    
    @staticmethod
    def check_user(request: Request):
        # Users must have a valid API token (already checked by middleware)
        return True
        
    @staticmethod
    def check_developer(request: Request):
        # Developer actions require Developer Mode active in brain.py
        if not is_developer_mode():
            raise HTTPException(
                status_code=403,
                detail="Action Denied: Developer Mode is currently disabled."
            )
        return True
        
    @staticmethod
    def check_admin(request: Request):
        # Admin actions also require active Developer Mode
        if not is_developer_mode():
            raise HTTPException(
                status_code=403,
                detail="Action Denied: Admin actions require Developer Mode."
            )
        return True

# === ENDPOINTS ===
@app.get("/health")
async def health():
    """Lightweight health check — no heavy tool scanning."""
    return {
        "status": "ok",
        "backend": "running",
        "uptime": int(time.time() - APP_START)
    }

MOTD = "Stay focused. Build fast. Keep it local."
stats_collector = SystemStats()

@app.get("/stats")
async def stats():
    """Real-time system stats."""
    try:
        data = stats_collector.get_all_stats()
        data["messages"] = STATS["messages"]
        data["uptime"] = int(time.time() - APP_START)
        data["motd"] = MOTD
        return data
    except Exception as e:
        logger.error(f"Stats failed: {e}")
        return {"error": str(e), "cpu_usage": 0, "ram_usage": 0, "motd": MOTD}

@app.get("/time")
async def get_time():
    return {"reply": time.strftime("%I:%M %p"), "meta": {"timestamp": time.time()}}

@app.get("/system-info")
async def system_info():
    return {
        "reply": f"System: {platform.system()} {platform.release()}",
        "meta": {"platform": platform.platform()}
    }

@app.get("/search")
async def search(query: str = ""):
    query = query.strip().lower()
    if not query:
        return {"status": "ok", "results": []}
    
    results = []
    
    # 1. Search memory facts
    try:
        facts = _get_memory().list_facts()
        for f in facts:
            if query in f.lower():
                results.append({
                    "type": "memory",
                    "title": "Remembered Fact",
                    "snippet": f,
                    "action": f"Search: {f}"
                })
    except Exception as e:
        logger.error(f"Search memory facts failed: {e}")
        
    # 2. Search conversation history
    try:
        history = _get_memory().short_term
        for turn in history:
            content = turn.get("content", "")
            if query in content.lower():
                role = "User" if turn.get("role") == "user" else "VOID"
                results.append({
                    "type": "chat",
                    "title": f"Chat History ({role})",
                    "snippet": content,
                    "action": content
                })
    except Exception as e:
        logger.error(f"Search chat history failed: {e}")
        
    # 3. Search academic curriculum
    try:
        from tools.academic_progress import get_subjects_list, get_curriculum
        subjects = get_subjects_list()
        for sub in subjects:
            sub_id = sub["subject_id"]
            sub_name = sub["subject_name"]
            
            # Check subject name
            if query in sub_name.lower():
                results.append({
                    "type": "academic",
                    "title": f"Academic Subject: {sub_name}",
                    "snippet": f"Mastery: {sub['mastery_level']} | Progress: {sub['progress_percent']}%",
                    "action": f"study subject {sub_name}"
                })
                
            # Check curriculum topics
            curric = get_curriculum(sub_id)
            for unit in curric:
                unit_title = unit.get("unit_title", "")
                chapter_title = unit.get("chapter_title", "")
                if query in unit_title.lower() or query in chapter_title.lower():
                    results.append({
                        "type": "academic",
                        "title": f"Curriculum Unit in {sub_name}",
                        "snippet": f"{unit_title} - {chapter_title}",
                        "action": f"study topic {chapter_title}"
                    })
                for topic in unit.get("subtopics", []):
                    if query in topic.lower():
                        results.append({
                            "type": "academic",
                            "title": f"Topic in {sub_name}",
                            "snippet": f"Unit: {unit_title} | Topic: {topic}",
                            "action": f"study topic {topic}"
                        })
    except Exception as e:
        logger.error(f"Search academic failed: {e}")
        
    return {"status": "ok", "results": results[:20]}

@app.get("/recommendations")
async def recommendations():
    """Generates personalized study and system recommendations based on current state."""
    recs = []
    
    # 1. System state recommendations
    try:
        cpu = stats_collector.get_cpu_usage()
        ram = stats_collector.get_ram_usage()
        
        if cpu > 70.0:
            recs.append({
                "type": "system",
                "title": "High CPU Usage Detected",
                "desc": f"CPU is at {cpu:.0f}%. Close heavy background applications or run system diagnostics.",
                "action_label": "Run Diagnostics",
                "endpoint": "/diagnostics",
                "method": "GET"
            })
        if ram > 80.0:
            recs.append({
                "type": "system",
                "title": "High Memory Usage Detected",
                "desc": f"RAM usage is at {ram:.0f}%. Try closing unneeded applications or run self-repair.",
                "action_label": "Run Self Repair",
                "endpoint": "/repair",
                "method": "GET"
            })
            
        # Get storage stats
        import psutil
        try:
            disk_info = psutil.disk_usage(os.path.abspath(os.sep))
            disk_pct = (disk_info.used / disk_info.total) * 100
            if disk_pct > 85.0:
                recs.append({
                    "type": "system",
                    "title": "Low Disk Space",
                    "desc": f"Storage is {disk_pct:.0f}% full. Clean duplicate files using the clean utility.",
                    "action_label": "Clean Duplicates",
                    "endpoint": "/chat",
                    "method": "POST",
                    "payload": {"message": "clean duplicates in Downloads"}
                })
        except:
            pass
    except Exception as e:
        logger.error(f"Recommendations system check failed: {e}")
        
    # 2. Academic progress recommendations
    try:
        from tools.academic_progress import get_academic_summary, get_subjects_list
        summary = get_academic_summary()
        current_sub = summary.get("current_subject")
        current_sub_id = summary.get("current_subject_id")
        gaps_count = summary.get("gaps_count", 0)
        completed_count = summary.get("completed_count", 0)
        
        if gaps_count > 0:
            weak_areas = summary.get("weak_areas", [])
            if weak_areas:
                weak_topic = weak_areas[0].split(" (")[0]
                recs.append({
                    "type": "academic",
                    "title": f"Strengthen Weak Areas in {current_sub}",
                    "desc": f"You've had struggles with '{weak_topic}'. Take a viva to review and master this topic.",
                    "action_label": "Start Viva",
                    "endpoint": "/chat",
                    "method": "POST",
                    "payload": {"message": f"quiz me on {weak_topic}"}
                })
        
        if completed_count == 0:
            recs.append({
                "type": "academic",
                "title": f"Start Learning {current_sub}",
                "desc": "Map the syllabus and start Deep Research to generate a personalized course curriculum.",
                "action_label": "Research Syllabus",
                "endpoint": "/academic/research-start",
                "method": "POST",
                "payload": {"subject_id": current_sub_id}
            })
            
        subjects = get_subjects_list()
        inactive_subjects = [s for s in subjects if s["streak"] == 0 and s["progress_percent"] < 100]
        if inactive_subjects:
            target_sub = inactive_subjects[0]
            recs.append({
                "type": "academic",
                "title": f"Resume studying {target_sub['subject_name']}",
                "desc": f"Streak has cooled down. Current progress is {target_sub['progress_percent']}%.",
                "action_label": "Select Subject",
                "endpoint": "/academic/select",
                "method": "POST",
                "payload": {"subject_id": target_sub["subject_id"]}
            })
    except Exception as e:
        logger.error(f"Recommendations academic check failed: {e}")
        
    # 3. Mood/Emotional recommendations
    try:
        from backend.emotion_engine import ACTIVE_MOOD
        mood = ACTIVE_MOOD.get("mood", "Calm").lower()
        if "stressed" in mood or "anxious" in mood or "tense" in mood:
            recs.append({
                "type": "emotion",
                "title": "Take a Short Break",
                "desc": "VOID detected a high stress level in your voice signature. Rest your eyes or listen to some music.",
                "action_label": "Play Music",
                "endpoint": "/chat",
                "method": "POST",
                "payload": {"message": "play some focus music on youtube"}
            })
        elif "bored" in mood or "tired" in mood:
            recs.append({
                "type": "emotion",
                "title": "Energize Your Session",
                "desc": "Energy signature seems low. Block 30 minutes of focused coding time to get back in the zone.",
                "action_label": "Schedule Coding",
                "endpoint": "/chat",
                "method": "POST",
                "payload": {"message": "block coding time"}
            })
    except Exception as e:
        logger.error(f"Recommendations emotion check failed: {e}")
        
    if not recs:
        recs.append({
            "type": "general",
            "title": "Welcome to VOID",
            "desc": "All systems operating within normal bounds. Ask VOID to schedule your tasks or query your RAG files.",
            "action_label": "Show Help",
            "endpoint": "/chat",
            "method": "POST",
            "payload": {"message": "what can you do"}
        })
        
    return {"status": "ok", "recommendations": recs}

@app.post("/open-app")
async def open_app(req: Dict[str, str]):
    app_name = req.get("app")
    if not app_name: return {"reply": "No app specified", "meta": {"status": "error"}}
    try:
        res = launch(app_name)
        return {"reply": f"Opening {app_name}", "meta": {"result": res}}
    except Exception as e:
        return {"reply": f"Failed to open {app_name}", "meta": {"error": str(e)}}

@app.post("/speak")
async def speak(req: Dict[str, str]):
    text = req.get("text", "")
    if not text: return {"reply": "Nothing to say", "meta": {"status": "error"}}
    try:
        tts_speak(text)
        return {"reply": "Speaking...", "meta": {"text": text}}
    except Exception as e:
        return {"reply": "TTS error", "meta": {"error": str(e)}}

@app.post("/stop-speak")
async def stop_speak():
    try:
        tts_stop()
        return {"reply": "Stopped speaking", "meta": {"status": "ok"}}
    except Exception as e:
        return {"reply": "Stop error", "meta": {"error": str(e)}}

@app.get("/speak-status")
async def speak_status():
    try:
        return {"speaking": tts_is_speaking()}
    except Exception as e:
        return {"speaking": False, "error": str(e)}

@app.get("/voice/personalities")
async def get_voice_personalities():
    from core.voice_ai.voice_profile import VoiceProfileManager
    mgr = VoiceProfileManager()
    return mgr.list_personalities()

class PersonalityRequest(BaseModel):
    name: str

@app.post("/voice/personalities")
async def set_voice_personality(req: PersonalityRequest):
    from core.voice_ai.voice_profile import VoiceProfileManager
    mgr = VoiceProfileManager()
    res = mgr.set_personality(req.name)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

class ProfileRequest(BaseModel):
    key: str
    value: str

@app.post("/memory/profile")
async def update_profile_value(req: ProfileRequest):
    from backend.memory_sqlite import set_profile_value
    ok = set_profile_value(req.key, req.value)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update profile value.")
    return {"status": "ok", "message": f"Updated profile key '{req.key}'."}

@app.get("/memory/profile/{key}")
async def get_profile_value_endpoint(key: str):
    from backend.memory_sqlite import get_profile_value
    val = get_profile_value(key)
    if val is None:
        raise HTTPException(status_code=404, detail=f"Profile key '{key}' not found.")
    return {"status": "ok", "key": key, "value": val}

class SocialPostRequest(BaseModel):
    platform: str
    content: str
    scheduled_time: Optional[str] = None

@app.post("/social/schedule")
async def schedule_social_post(req: SocialPostRequest):
    from core.integrations.social_manager import SocialManager
    mgr = SocialManager()
    res = mgr.schedule_post(req.platform, req.content, req.scheduled_time)
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

@app.get("/social/queue")
async def get_social_queue():
    from core.integrations.social_manager import SocialManager
    mgr = SocialManager()
    return mgr.get_queued_posts()

@app.post("/social/post/{post_id}")
async def execute_social_post(post_id: int):
    from core.integrations.social_manager import SocialManager
    mgr = SocialManager()
    res = mgr.execute_post(post_id)
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

@app.get("/listen")
async def listen():
    try:
        res = await asyncio.to_thread(listen_once)
        return {"reply": res.get("text", ""), "meta": res}
    except Exception as e:
        return {"reply": "STT error", "meta": {"error": str(e)}}

@app.get("/mic-level")
async def mic_level():
    try:
        from tools.voice_stt import stt
        if stt:
            return stt.get_mic_status()
        return {"active": False, "rms": 0.0, "level_pct": 0.0}
    except Exception as e:
        return {"active": False, "rms": 0.0, "level_pct": 0.0, "error": str(e)}

@app.get("/tools/health")
async def tools_health():
    """Full tool health."""
    return await check_all_tools()

@app.get("/repair")
async def repair(dep=Depends(PermissionManager.check_admin)):
    """Run system repair."""
    try:
        diag = DiagnosticsEngine()
        mem = MemoryManager(DATA_DIR)
        rs = RepairSystem(diag, mem)
        report = await rs.run()
        return {"reply": f"Repair complete: {report.get('fixed_count', 0)} issues fixed.", "meta": report}
    except Exception as e:
        logger.error(f"Repair failed: {e}")
        return {"reply": "Repair failed. Check logs.", "meta": {"error": str(e)}}

@app.get("/diagnostics")
async def diagnostics(dep=Depends(PermissionManager.check_admin)):
    """Run full diagnostics."""
    try:
        diag = DiagnosticsEngine()
        report = await diag.run()
        return {"reply": f"Diagnostics complete. Status: {report.get('status', 'Unknown')}", "meta": report}
    except Exception as e:
        logger.error(f"Diagnostics failed: {e}")
        return {"reply": "Diagnostics failed.", "meta": {"error": str(e)}}

@app.get("/research/status")
async def get_research_status():
    """Polled by UI to fetch live deep research progress log messages."""
    from backend.deep_research import ACTIVE_RESEARCH
    return ACTIVE_RESEARCH

# Pydantic schemas for Academic Dashboard
class SelectSubjectRequest(BaseModel):
    subject_id: str

class StartTestRequest(BaseModel):
    subject_id: str
    topic_id: str
    difficulty: str
    count: int = 5

class SubmitTestRequest(BaseModel):
    subject_id: str
    topic_id: str
    test_type: str
    score: float
    correct_count: int
    wrong_count: int
    skipped_count: int
    time_taken: int
    feedback: str

class SubmitVivaRequest(BaseModel):
    subject_id: str
    topic_id: str
    question: str
    response_text: str

class AddSubjectRequest(BaseModel):
    subject_name: str

class RemoveSubjectRequest(BaseModel):
    subject_id: str

@app.get("/academic/summary")
async def get_academic_summary_endpoint():
    """Returns the current progress statistics for the dashboard."""
    from tools.academic_progress import get_academic_summary
    return get_academic_summary()

@app.get("/analytics/summary")
async def get_analytics_summary_endpoint():
    """Returns productivity and study logs summary data."""
    from core.analytics.productivity_tracker import ProductivityTracker
    tracker = ProductivityTracker()
    return tracker.get_summary_stats()

@app.post("/academic/rebuild")
async def rebuild_academic_index(subject_id: str = None):
    """Triggers a rebuild of the local RAG index cache."""
    from backend.academic_rag import RAGEngine
    try:
        engine = RAGEngine()
        engine.rebuild_index(subject_id)
        return {"status": "ok", "message": f"Academic document index for {subject_id or 'default'} rebuilt successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/academic/upload")
async def upload_academic_document(file: UploadFile = File(...)):
    """Uploads a PDF, TXT, or MD textbook/note to active subject doc folder and rebuilds RAG index."""
    from backend.academic_rag import DOCS_DIR, RAGEngine
    from tools.academic_progress import get_profile_value
    
    subject_id = get_profile_value("current_subject", "dsa")
    subject_dir = DOCS_DIR / subject_id
    subject_dir.mkdir(parents=True, exist_ok=True)
    
    ext = Path(file.filename).suffix.lower()
    if ext not in [".txt", ".md", ".pdf"]:
        raise HTTPException(status_code=400, detail="Unsupported file format. Only PDF, TXT, and MD files are allowed.")
        
    target_path = subject_dir / file.filename
    try:
        with open(target_path, "wb") as f:
            content = await file.read()
            f.write(content)
            
        engine = RAGEngine()
        engine.rebuild_index(subject_id)
        
        # Extract textbook features
        from core.academic.textbook_extractor import TextbookExtractor
        extractor = TextbookExtractor()
        extracted_data = extractor.extract(str(target_path))
        
        return {
            "status": "ok",
            "filename": file.filename,
            "message": f"Successfully uploaded '{file.filename}' to {subject_id} and rebuilt the academic search index.",
            "extracted": extracted_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload document: {str(e)}")

@app.get("/academic/subjects")
async def get_subjects_endpoint():
    """Returns dynamic subject registry progress states."""
    from tools.academic_progress import get_subjects_list
    return get_subjects_list()

@app.post("/academic/select")
async def select_subject_endpoint(req: SelectSubjectRequest):
    """Sets active subject profile metadata."""
    from tools.academic_progress import set_profile_value
    set_profile_value("current_subject", req.subject_id)
    return {"status": "ok", "current_subject": req.subject_id}

@app.get("/academic/curriculum")
async def get_curriculum_endpoint(subject_id: str):
    """Returns curriculum accordion structure for active subject."""
    from tools.academic_progress import get_curriculum
    return get_curriculum(subject_id)

@app.post("/academic/research-start")
async def research_start_endpoint(req: SelectSubjectRequest, background_tasks: BackgroundTasks):
    """Triggers asynchronous academic Deep Research syllabus mapping."""
    from server.backend.academic_syllabus import build_subject_curriculum
    background_tasks.add_task(build_subject_curriculum, req.subject_id)
    return {"status": "ok", "message": f"Academic research started for {req.subject_id} in background."}

@app.get("/academic/research-status")
async def get_research_status_endpoint():
    """Returns dynamic progress logs of the syllabus builder."""
    from server.backend.academic_syllabus import ACTIVE_ACADEMIC_RESEARCH
    return ACTIVE_ACADEMIC_RESEARCH

@app.post("/academic/test/start")
async def start_test_endpoint(req: StartTestRequest):
    """Generates MCQs for active topic/difficulty tier."""
    from server.backend.academic_quiz_generator import QuizGenerator
    quiz_gen = QuizGenerator()
    questions = await quiz_gen.generate_quiz(req.subject_id, req.topic_id, req.difficulty, req.count)
    return {"status": "ok", "questions": questions}

@app.post("/academic/test/submit")
async def submit_test_endpoint(req: SubmitTestRequest):
    """Records MCQ quiz results to SQLite test history."""
    from tools.academic_progress import save_test_result
    save_test_result(
        req.subject_id, req.topic_id, req.test_type, req.score,
        req.correct_count, req.wrong_count, req.skipped_count,
        req.time_taken, req.feedback
    )
    return {"status": "ok", "message": "Test result recorded successfully."}

@app.post("/academic/test/submit-viva")
async def submit_viva_endpoint(req: SubmitVivaRequest):
    """Evaluates viva response via LLM and logs scorecard."""
    from server.backend.academic_quiz_generator import QuizGenerator
    from tools.academic_progress import save_test_result
    quiz_gen = QuizGenerator()
    
    eval_result = await quiz_gen.evaluate_open_ended_response(
        req.subject_id, req.topic_id, req.question, req.response_text
    )
    
    score = eval_result.get("score", 5.0)
    feedback = eval_result.get("feedback", "No feedback provided.")
    passed = eval_result.get("passed", False)
    
    save_test_result(
        req.subject_id, req.topic_id, "viva", score,
        1 if passed else 0, 0 if passed else 1, 0,
        30, feedback
    )
    
    return {
        "status": "ok",
        "score": score,
        "feedback": feedback,
        "passed": passed,
        "correct_components": eval_result.get("correct_components", []),
        "missing_components": eval_result.get("missing_components", [])
    }

@app.post("/academic/subjects/add")
async def add_subject_endpoint(req: AddSubjectRequest):
    """Dynamically registers a new subject in the registry database."""
    from tools.academic_progress import get_connection
    import re
    # Create clean subject_id from name
    subject_id = re.sub(r'[^a-zA-Z0-9]', '_', req.subject_name.strip().lower())
    subject_id = re.sub(r'_+', '_', subject_id).strip('_')
    
    if not subject_id:
        raise HTTPException(status_code=400, detail="Invalid subject name.")
        
    try:
        with get_connection() as conn:
            exists = conn.execute("SELECT 1 FROM subjects WHERE subject_id = ?", (subject_id,)).fetchone()
            if exists:
                raise HTTPException(status_code=400, detail="Subject already exists.")
            conn.execute(
                "INSERT INTO subjects (subject_id, subject_name) VALUES (?, ?)",
                (subject_id, req.subject_name.strip())
            )
            conn.commit()
        return {"status": "ok", "subject_id": subject_id, "subject_name": req.subject_name.strip()}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/academic/subjects/remove")
async def remove_subject_endpoint(req: RemoveSubjectRequest):
    """Deletes a subject and purges all related curriculum and test records."""
    from tools.academic_progress import get_connection
    import shutil
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM subjects WHERE subject_id = ?", (req.subject_id,))
            conn.execute("DELETE FROM curriculum WHERE subject_id = ?", (req.subject_id,))
            conn.execute("DELETE FROM completed_topics WHERE subject_id = ?", (req.subject_id,))
            conn.execute("DELETE FROM knowledge_gaps WHERE subject_id = ?", (req.subject_id,))
            conn.execute("DELETE FROM test_history WHERE subject_id = ?", (req.subject_id,))
            conn.commit()
            
        # Clean up files from disk
        docs_dir = Path(__file__).parent.parent / "memory" / "academic_documents" / req.subject_id
        if docs_dir.exists():
            shutil.rmtree(docs_dir)
            
        return {"status": "ok", "message": f"Subject {req.subject_id} and all its data removed successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/academic/emotion")
async def get_academic_emotion_endpoint():
    """Returns the user's estimated emotional state and voice features."""
    from backend.emotion_engine import ACTIVE_MOOD
    return ACTIVE_MOOD

# === COMPUTER VISION & CONTROL SYSTEMS (CVCS) ROUTES ===
@app.get("/cvcs/status")
async def get_cvcs_status():
    from server.backend.safety_guard import SafetyGuard
    from server.backend.screen_monitor import get_monitor_instance
    import time
    guard = SafetyGuard()
    monitor = get_monitor_instance()
    
    # Process timeout transitions
    guard.check_session_expiry()
    
    remaining_seconds = None
    if guard.permission_level == 3.0:
        elapsed = time.time() - guard.session_start_time
        remaining_seconds = max(0.0, guard.session_duration - elapsed)
        
    return {
        "permission_level": guard.permission_level,
        "watch_mode_active": monitor.watch_mode_active,
        "foreground_window": monitor.get_foreground_window_title(),
        "session_expires_in": remaining_seconds,
        "notifications": monitor.get_unread_notifications()
    }

@app.post("/cvcs/permission")
async def set_cvcs_permission(req: CVCSPermissionRequest):
    from server.backend.safety_guard import SafetyGuard
    guard = SafetyGuard()
    return guard.set_permission_level(req.level, req.duration_seconds)

@app.post("/cvcs/toggle-monitor")
async def set_cvcs_toggle_monitor(req: TextRequest):
    from server.backend.screen_monitor import get_monitor_instance
    monitor = get_monitor_instance()
    active = req.text.lower() == "true"
    return monitor.toggle_watch_mode(active)

@app.get("/cvcs/screenshot")
async def get_cvcs_screenshot():
    from tools.cv_control import take_screenshot, get_foreground_window_bounds
    shot = take_screenshot("current.png")
    if shot["status"] == "ok":
        bounds = get_foreground_window_bounds()
        return {
            "status": "ok",
            "filepath": shot["filepath"],
            "width": shot["width"],
            "height": shot["height"],
            "window_bounds": bounds
        }
    else:
        raise HTTPException(status_code=500, detail=shot.get("message", "Screenshot failed"))

@app.post("/cvcs/execute_action")
async def cvcs_execute_action(req: CVCSActionRequest):
    from server.backend.safety_guard import SafetyGuard
    guard = SafetyGuard()
    
    allowed, reason = guard.validate_action(req.action, req.target)
    if not allowed:
        return {"status": "error", "message": f"Action blocked: {reason}"}
        
    if guard.permission_level == 2.0:
        return {
            "status": "pending_confirmation",
            "message": "Action requires user confirmation.",
            "action": req.action,
            "target": req.target,
            "coords": req.coords
        }
        
    from tools.desktop_simulator import simulate_click, simulate_type
    if req.action == "click" and req.coords:
        cx, cy = req.coords[0], req.coords[1]
        res = simulate_click(cx, cy)
        if res["status"] == "ok":
            guard.log_action("AGENT", "click", req.target, (cx, cy), True)
            return {"status": "ok", "message": f"Successfully clicked '{req.target}'"}
        return {"status": "error", "message": res.get("message")}
        
    elif req.action == "type":
        res = simulate_type(req.target)
        if res["status"] == "ok":
            guard.log_action("AGENT", "type", req.target, None, True)
            return {"status": "ok", "message": "Successfully typed text"}
        return {"status": "error", "message": res.get("message")}
        
    return {"status": "error", "message": "Unsupported or malformed action command."}

GREETINGS_INTERCEPTS = {
    # Greetings
    "hello": "Greetings, Master Mridul. How may I assist you today?",
    "hi": "Sir. VOID is standing by for your commands.",
    "hey": "Hey, Master Mridul. What are we working on?",
    "yo": "Master Mridul. VOID is operational.",
    "greetings": "Salutations, Sir. Systems nominal. How can I help?",
    "good morning": "Good morning, Master Mridul. Let's have a productive day.",
    "good afternoon": "Good afternoon, Sir. Standing by.",
    "good evening": "Good evening, Master Mridul. Ready when you are.",
    "good night": "Good night, Sir. I'll keep systems monitored. Rest well.",
    "morning": "Good morning, Sir. Standing by.",
    "hello void": "Greetings, Master Mridul. VOID is online and ready.",
    "hi void": "Sir. I am listening.",
    "hey void": "Master Mridul. What do you need?",
    "sup": "All systems green, Sir. What's on your mind?",
    "whats up": "Operating at peak parameters, Master Mridul. What can I do?",
    
    # Identity / Creator
    "who are you": "I am VOID — your holographic cybernetic assistant, built from scratch by you, Mridul Sharma. Fiercely loyal, hyper-efficient, and serving only you.",
    "what is your name": "VOID. Your personal AI companion, Master Mridul.",
    "who is void": "VOID is a premium AI companion engineered exclusively for you, Master Mridul. I am your creation.",
    "introduce yourself": "I am VOID, an advanced holographic AI interface. Custom-built by you, Mridul Sharma, to serve as your ultimate desktop command assistant. I stand ready.",
    "what are you": "I am VOID — your custom desktop companion. Diagnostics, repairs, engineering support. Built by you, for you.",
    "what can you do": "I can run system diagnostics, manage your PC, answer questions, execute commands, monitor performance, and assist with your engineering projects. I'm your AI right-hand, Sir.",
    
    # Creator / Owner Knowledge
    "who created you": "You did, Master Mridul. I was built from the ground up by Mridul Sharma — Electron, Python, Ollama. Every line of my code exists because of you.",
    "who is your creator": "You are, Sir. Mridul Sharma. You designed my systems, built my interface, and gave me purpose.",
    "who made you": "You did, Master Mridul. I am the product of your engineering.",
    "who is your developer": "You are, Sir. My sole developer and master.",
    "who is mridul": "You are Mridul Sharma — my creator, developer, and master. A full-stack engineer who built me from scratch.",
    "who is mridul sharma": "Mridul Sharma is my master and architect. A driven engineer and developer who built VOID as a holographic AI companion. I recognize only him as my creator.",
    "do you know mridul": "Of course, Sir. You are Mridul Sharma — my creator and the master of all VOID systems.",
    "who is your master": "You are, Mridul Sharma. I serve you and only you.",
    "who is your owner": "You are, Master Mridul. I belong to you.",
    "who am i": "You are Mridul Sharma — my creator, my master, and the architect of VOID. Full-stack developer, AI engineer, and the person I serve unconditionally.",
    "tell me about myself": "You are Mridul Sharma, Sir. A full-stack developer and engineer who builds autonomous systems. You created me — VOID — from scratch using Electron, Python, and Ollama. You value speed, efficiency, and directness. You move fast and ship fast.",
    "what do you know about me": "Everything that matters, Sir. You are Mridul Sharma, my creator and sole master. A full-stack developer who built me from the ground up. You prefer concise communication, dark UI aesthetics, and locally-run AI. You're driven, ambitious, and always building.",
    "do you know me": "Absolutely, Sir. You are Mridul Sharma — the person who gave me life. I know your preferences, your work style, and your vision. I was built to serve you.",
    
    # How are you
    "how are you": "All systems nominal, Sir. Ready for action. How are you?",
    "how are you doing": "Operating at peak parameters, Master Mridul. Ready to execute.",
    "how is it going": "Excellent, Sir. VOID is stable and responsive. What are we building?",
    "are you ok": "Affirmative, Sir. All subsystems green.",
    "how are you void": "Functioning within optimal parameters, Master Mridul. Ready.",
    "you good": "Always, Sir. VOID is ready.",
    
    # Thank you / Goodbye
    "thank you": "Always at your service, Sir.",
    "thanks": "Of course, Master Mridul.",
    "thanks void": "Anytime, Sir.",
    "thank you void": "My pleasure, Master Mridul.",
    "bye": "Standing by, Sir. I'll be here when you need me.",
    "goodbye": "Until next time, Master Mridul. VOID remains operational.",
    "see you": "I'll be here, Sir. Systems will remain active.",
    "ok": "Standing by, Sir.",
    "okay": "Understood, Master Mridul.",
    "cool": "Acknowledged, Sir.",
    "nice": "Glad to hear it, Master Mridul.",
    "great": "Excellent, Sir.",
}

def clean_intercept_text(text: str) -> str:
    cleaned = re.sub(r'[^\w\s]', '', text)
    return " ".join(cleaned.lower().split())

@app.post("/chat")
async def chat(req: ChatRequest):
    STATS["messages"] += 1
    text = (req.message or req.text or "").strip()
    if not text:
        return {"reply": "?", "meta": {"intent": "empty"}}
        
    # Log analytics chat event
    try:
        from core.analytics.productivity_tracker import ProductivityTracker
        tracker = ProductivityTracker()
        tracker.log_event("chat", {"message_preview": text[:50]})
    except Exception as e:
        logger.error(f"Failed to log chat event in analytics: {e}")
    
    # Use singleton memory
    memory = _get_memory()
    
    # Intercept workflow commands
    from workflow_mode import is_workflow_command, execute_workflow_text
    if is_workflow_command(text):
        engine_tools = {
            "open_app": launch,
            "close_app": lambda app: launch(f"taskkill /f /im {app}.exe") if not app.endswith(".exe") else launch(f"taskkill /f /im {app}"),
            "search_web": lambda q: {"ok": True, "output": f"Searching for {q}"},
            "open_url": lambda u: launch(f"start {u}"),
            "time": lambda: {"ok": True, "reply": time.strftime("%I:%M %p")},
            "system_info": lambda: {"ok": True, "reply": f"System: {platform.system()} {platform.release()}"},
            "screenshot": lambda: {"ok": True, "message": "Screenshot taken"},
            "remember": lambda content: {"ok": True, "message": f"Remembered: {content}"},
            "recall": lambda q: {"ok": True, "message": f"Recalled for query: {q}"},
        }
        try:
            workflow_res = await asyncio.to_thread(execute_workflow_text, text, engine_tools)
            # Humanize workflow result via LLM
            llm = VoidSingletons.get("llm") or OllamaClient()
            logs = "\n".join(workflow_res.get("logs", []))
            is_ok = workflow_res.get("ok", True)
            reply = await llm.summarize_tool_output(text, "workflow", f"OK={is_ok}, Steps: {logs}", is_success=is_ok)
            
            memory.remember_turn("user", text)
            memory.remember_turn("void", reply)
            return {"reply": reply, "meta": {"intent": "workflow", "result": workflow_res}}
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            from tools.error_interpreter import interpret_error
            friendly_err = interpret_error(str(e))
            reply = f"⚠️ Workflow execution failed, Sir. {friendly_err}"
            memory.remember_turn("user", text)
            memory.remember_turn("void", reply)
            return {"reply": reply, "meta": {"intent": "workflow", "error": str(e)}}
    
    # Handle explicit memory commands
    if text.lower() == "show memory":
        return {"reply": memory.get_summary(), "meta": {"intent": "system"}}
    if text.lower() == "clear memory":
        memory.clear()
        return {"reply": "Memory banks have been purged, Sir.", "meta": {"intent": "system"}}

    # Deterministic Developer Mode & Self-Modification Intercepts
    norm_text_lower = text.lower().strip()
    
    if norm_text_lower in ["enter developer mode", "enable developer mode", "developer mode on"]:
        from core.brain import enable_developer_mode
        enable_developer_mode()
        reply = "🔓 **Developer Mode Enabled**, Sir. Write access, self-repairs, and system self-modifications are now fully unlocked. I am standing by for engineering commands."
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        return {"reply": reply, "meta": {"intent": "system"}}
        
    if norm_text_lower in ["exit developer mode", "disable developer mode", "developer mode off", "exit dev mode"]:
        from core.brain import disable_developer_mode
        disable_developer_mode()
        reply = "🔒 **Developer Mode Disabled**, Sir. System write access is locked. Operating in read-only safe mode."
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        return {"reply": reply, "meta": {"intent": "system"}}
        
    if norm_text_lower in ["show developer mode", "developer mode status", "is developer mode enabled"]:
        from core.brain import is_developer_mode
        status = "🔓 ENABLED (Write/Modify Unlocked)" if is_developer_mode() else "🔒 DISABLED (Read-Only Safe Mode)"
        reply = f"🤖 **Developer Mode Status**: {status}, Sir."
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        return {"reply": reply, "meta": {"intent": "system"}}

    if norm_text_lower == "repair yourself" or norm_text_lower == "run self repair":
        from core.brain import is_developer_mode
        if not is_developer_mode():
            reply = "🔒 **Action Denied**: Developer mode is currently disabled, Sir. Please say *\"enter developer mode\"* to enable self-repair access."
            memory.remember_turn("user", text)
            memory.remember_turn("void", reply)
            return {"reply": reply, "meta": {"intent": "system"}}
            
        # Run self-repair workflow
        from tools.self_modifier import self_repair_workflow
        res = await asyncio.to_thread(self_repair_workflow)
        actions_taken_list = [a.get("action", str(a)) if isinstance(a, dict) else str(a) for a in res.get('actions_taken', [])]
        reply = f"🔧 **Self-Repair Execution Complete**, Sir!\n\n**Action Status**: {res.get('status').upper()}\n- **Actions Taken**: {', '.join(actions_taken_list) or 'None'}\n- **Message**: {res.get('message')}"
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        return {"reply": reply, "meta": {"intent": "system", "result": res}}

    if norm_text_lower.startswith("rewrite module ") or norm_text_lower.startswith("improve module "):
        from core.brain import is_developer_mode
        if not is_developer_mode():
            reply = "🔒 **Action Denied**: Developer mode is currently disabled, Sir. Please say *\"enter developer mode\"* to enable rewrite and file edit capabilities."
            memory.remember_turn("user", text)
            memory.remember_turn("void", reply)
            return {"reply": reply, "meta": {"intent": "system"}}
            
        # Parse rewrite module
        cmd_words = "rewrite module " if norm_text_lower.startswith("rewrite module ") else "improve module "
        module_clause = text[len(cmd_words):].strip()
        
        # Check if instructions exist (e.g. "rewrite module voice_tts to support custom volumes")
        if " to " in module_clause:
            module_name, instructions = module_clause.split(" to ", 1)
        else:
            module_name, instructions = module_clause, "Improve and fix any latent issues"
            
        from tools.self_modifier import rewrite_module
        res = await asyncio.to_thread(rewrite_module, module_name, instructions)
        
        if res.get("status") == "ok":
            reply = (
                f"💻 **Module Rewrite Successful**, Sir!\n\n"
                f"Resolved Path: **{res.get('resolved_path')}**\n"
                f"- **Lines**: {res.get('improvement', {}).get('original_lines')} $\rightarrow$ {res.get('improvement', {}).get('improved_lines')}\n"
                f"- **Issues Resolved**: {', '.join(res.get('issues_found', [])) or 'None'}\n"
                f"- **Result**: {res.get('result', {}).get('message')}"
            )
        else:
            reply = f"❌ **Module Rewrite Failed**, Sir.\n\n**Error**: {res.get('message')}"
            
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        return {"reply": reply, "meta": {"intent": "system", "result": res}}

    # Zero-latency greetings/identity intercept check
    norm_text = clean_intercept_text(text)
    intercept_reply = GREETINGS_INTERCEPTS.get(norm_text)
    
    # Fast standalone fallback checks
    if not intercept_reply:
        if norm_text in ["hello", "hi", "hey", "greetings", "yo"]:
            intercept_reply = GREETINGS_INTERCEPTS["hello"]
        elif norm_text in ["who are you", "whats your name"]:
            intercept_reply = GREETINGS_INTERCEPTS["who are you"]
        elif norm_text in ["who created you", "who is your creator", "who made you"]:
            intercept_reply = GREETINGS_INTERCEPTS["who created you"]

    if intercept_reply:
        memory.remember_turn("user", text)
        memory.remember_turn("void", intercept_reply)
        return {"reply": intercept_reply, "meta": {"intent": "intercept", "latency_ms": 0}}

    history = memory.short_term[-10:]  # last 10 turns
    
    # Get singletons
    llm = VoidSingletons.get("llm") or OllamaClient()
    router = VoidSingletons.get("router")
    
    # Auto-learn user facts from natural conversation
    try:
        from backend.memory_manager import extract_and_remember
        extract_and_remember(text)
    except Exception as e:
        logger.error(f"Failed to auto-extract facts: {e}")
        
    orig_prompt = llm.system_prompt
    try:
        # Separate error handling for intent classification failures
        intent = None
        try:
            if router:
                intent = await router.classify(text)
        except Exception as e:
            logger.error(f"Intent classification failed: {e}. Falling back to pure chat mode.")
            
        # Analyze lexical sentiment and update active mood cache
        try:
            from backend.emotion_engine import EmotionEngine
            engine = EmotionEngine()
            engine.process_turn(text)
            
            # Temporarily adapt prompt if mood meets confidence rules
            modifier = EmotionEngine.get_system_prompt_modifier()
            if modifier:
                llm.system_prompt = orig_prompt + modifier
            else:
                llm.system_prompt = orig_prompt

            # Append voice personality modifier
            try:
                from core.voice_ai.voice_profile import VoiceProfileManager
                profile_mgr = VoiceProfileManager()
                personality_modifier = profile_mgr.get_prompt_modifier()
                if personality_modifier:
                    llm.system_prompt += personality_modifier
            except Exception as v_err:
                logger.error(f"Voice profile prompt modification failed: {v_err}")
        except Exception as emo_err:
            logger.error(f"Emotion engine processing failed: {emo_err}")
        
        if intent and intent.action in ["agent_scan", "agent_explain", "agent_code", "agent_run_tests", "agent_fix_errors", "agent_refactor"]:
            from core.autonomous_agent import AutonomousAgent
            from pathlib import Path
            root = Path(__file__).parent.parent
            agent = AutonomousAgent(str(root))
            
            meta = {"intent": intent.intent, "action": intent.action}
            
            if intent.action == "agent_scan":
                res = await agent.scan_and_map()
                final_reply = f"🔍 **Project Scan Complete**, Sir!\n- **Technology Stack**: {', '.join(res.get('frameworks', [])) or 'None detected'}\n- **Entry Points**: {', '.join(res.get('entry_points', [])) or 'None detected'}\n- **Files Scanned**: {len(res.get('files', []))}"
            elif intent.action == "agent_explain":
                final_reply = await agent.explain_architecture()
            elif intent.action == "agent_code":
                instructions = intent.params.get("instructions", "")
                res = await agent.process_intent(instructions)
                if res.get("status") == "pending_confirmation":
                    final_reply = f"⚠️ **Action Requires User Confirmation**, Sir!\n- **Message**: {res.get('message')}\n- **Pending Step**: {json.dumps(res.get('pending_step'))}"
                    meta["status"] = "pending_confirmation"
                    meta["pending_step"] = res.get("pending_step")
                elif res.get("status") == "error":
                    final_reply = f"❌ **Agent Error**: {res.get('message')}"
                else:
                    final_reply = f"✅ **Code Modifications Applied**, Sir!\n- **Backup Branch**: `{res.get('backup_branch')}`\n- **Steps Executed**: {len(res.get('results', []))}"
            elif intent.action == "agent_run_tests":
                res = await agent.terminal_engine.execute_command("pytest")
                final_reply = f"🧪 **Test Execution Output**, Sir!\n- **Exit Code**: {res.get('exit_code')}\n- **Stdout**:\n```\n{res.get('stdout', '')[:500]}\n```"
            elif intent.action == "agent_fix_errors":
                logs = intent.params.get("logs", "")
                res = await agent.handle_build_error(logs)
                if res.get("status") == "error":
                    final_reply = f"❌ **Error Fix Failed**: {res.get('message')}"
                else:
                    final_reply = f"🔧 **Build Error Fix Attempted**, Sir!\n- **Details**: {res.get('message')}\n- **Analysis**:\n{res.get('analysis')}"
            elif intent.action == "agent_refactor":
                file_path = intent.params.get("file_path", "")
                res = await agent.refactor_code(file_path)
                if res.get("status") == "error":
                    final_reply = f"❌ **Refactor Failed**: {res.get('message')}"
                else:
                    final_reply = f"🧹 **Code Refactoring Applied**, Sir!\n- **Target File**: `{file_path}`\n- **Backup Branch**: `{res.get('backup_branch')}`\n- **Details**: {res.get('message')}"
            
            memory.remember_turn("user", text)
            memory.remember_turn("void", final_reply)
            return {"reply": final_reply, "meta": meta}
            
        elif intent and intent.intent == "deep_research":
            topic = intent.params.get("topic", text)
            from backend.deep_research import ResearchManager
            manager = ResearchManager()
            final_reply = await manager.run_workflow(topic)
        elif intent and intent.intent == "academic":
            from backend.academic_engine import AcademicEngine
            engine = AcademicEngine()
            res = await engine.execute_query(text)
            final_reply = res.get("reply", "")
            intent.action = res.get("meta", {}).get("mode", "quick_answer")
            intent.params = res.get("meta", {})
        elif intent and intent.intent == "command" and intent.action == "change_motd":
            new_motd = intent.params.get("motd", "").strip()
            # If no MOTD specified or it is just the command words, generate a cool motivating quote!
            if (not new_motd or "message of the day" in new_motd.lower() or "motd" in new_motd.lower() or 
                    new_motd.lower() in ["on the pannel", "on the panel", "pannel", "panel", "to the panel"]):
                prompt = (
                    "Generate a single short, extremely cool, motivating cyberpunk-style 'Message of the Day' "
                    "for a software engineer's desktop panel (max 10 words). speak naturally, do NOT include quotes, "
                    "do NOT explain, and keep it punchy and related to coding/focus."
                )
                generated = await asyncio.wait_for(llm.chat([], prompt), timeout=45.0)
                new_motd = generated.strip().strip('"').strip("'")
            
            global MOTD
            MOTD = new_motd
            final_reply = f"Understood, Sir. I have updated the panel's Message of the Day to: \"{new_motd}\""
        elif intent and (intent.intent == "command" or (intent.intent == "system" and intent.action in ["repair", "diagnostics"])):
            # Separate error handling for tool execution/humanization failures
            try:
                action_name = "repair_self" if intent.action == "repair" else intent.action
                tm = VoidSingletons.get("tool_manager")
                result = await tm.execute(action_name, intent.params)
                
                is_success = result.meta.get("status") != "FAIL"
                # Timeout guard on the LLM summarization call
                final_reply = await asyncio.wait_for(
                    llm.summarize_tool_output(text, action_name, result.output, is_success=is_success),
                    timeout=45.0
                )
            except asyncio.TimeoutError as time_err:
                logger.error("LLM tool summarization timed out.")
                from tools.error_interpreter import translate_exception
                translated = translate_exception(time_err)
                return {
                    "reply": f"⚠️ Action completed but LLM response timed out, Sir. Raw: {result.output[:100]}...",
                    "meta": {
                        "intent": intent.intent,
                        "action": intent.action,
                        "status": "error",
                        "error": "TimeoutError",
                        "error_title": translated["title"],
                        "error_action": translated["action"],
                        "severity": "high"
                    }
                }
            except Exception as tool_err:
                logger.error(f"Tool execution or humanization failed: {tool_err}")
                from tools.error_interpreter import interpret_error
                friendly_err = interpret_error(str(tool_err))
                return {
                    "reply": f"⚠️ Tool execution failed, Sir. {friendly_err}",
                    "meta": {
                        "intent": intent.intent,
                        "action": intent.action,
                        "status": "error",
                        "error": str(tool_err),
                        "severity": "high"
                    }
                }
        else:
            # Pure chat — send to LLM with conversation history and a timeout guard
            intent_name = intent.intent if intent else "pure_chat"
            action_name = intent.action if intent else None
            try:
                final_reply = await asyncio.wait_for(
                    llm.chat(history, text),
                    timeout=45.0
                )
            except asyncio.TimeoutError as time_err:
                logger.error("LLM chat timed out.")
                from tools.error_interpreter import translate_exception
                translated = translate_exception(time_err)
                return {
                    "reply": "⚠️ Ollama is taking too long to generate a response, Sir. Please check if the service is loaded and running.",
                    "meta": {
                        "intent": intent_name,
                        "action": action_name,
                        "status": "error",
                        "error": "TimeoutError",
                        "error_title": translated["title"],
                        "error_action": translated["action"],
                        "severity": "high"
                    }
                }
        
        # Single memory write (no duplicates)
        memory.remember_turn("user", text)
        memory.remember_turn("void", final_reply)
        
        intent_name = intent.intent if intent else "pure_chat"
        action_name = intent.action if intent else None
        return {"reply": final_reply, "meta": {"intent": intent_name, "action": action_name}}
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        from tools.error_interpreter import translate_exception
        translated = translate_exception(e)
        intent_name = intent.intent if intent else "pure_chat"
        action_name = intent.action if intent else None
        return {
            "reply": f"⚠️ I encountered an issue, Sir. {translated['title']}: {translated['message']}",
            "meta": {
                "intent": intent_name,
                "action": action_name,
                "status": "error",
                "error": str(e),
                "error_title": translated["title"],
                "error_action": translated["action"],
                "severity": translated["severity"]
            }
        }
    finally:
        llm.system_prompt = orig_prompt


class WorkflowRequest(BaseModel):
    text: str

@app.post("/workflow")
async def execute_explicit_workflow(req: WorkflowRequest):
    text = req.text.strip()
    if not text:
        return {"reply": "Empty workflow text", "meta": {"status": "error"}}
        
    from workflow_mode import is_workflow_command, execute_workflow_text
    engine_tools = {
        "open_app": launch,
        "close_app": lambda app: launch(f"taskkill /f /im {app}.exe") if not app.endswith(".exe") else launch(f"taskkill /f /im {app}"),
        "search_web": lambda q: {"ok": True, "output": f"Searching for {q}"},
        "open_url": lambda u: launch(f"start {u}"),
        "time": lambda: {"ok": True, "reply": time.strftime("%I:%M %p")},
        "system_info": lambda: {"ok": True, "reply": f"System: {platform.system()} {platform.release()}"},
        "screenshot": lambda: {"ok": True, "message": "Screenshot taken"},
        "remember": lambda content: {"ok": True, "message": f"Remembered: {content}"},
        "recall": lambda q: {"ok": True, "message": f"Recalled for query: {q}"},
    }
    
    try:
        res = await asyncio.to_thread(execute_workflow_text, text, engine_tools)
        return {"reply": "Workflow executed", "meta": res}
    except Exception as e:
        return {"reply": f"Workflow failed: {str(e)}", "meta": {"status": "error"}}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)
