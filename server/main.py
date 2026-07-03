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
from typing import Dict, Any, List, Optional

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

# --- Real-Time Intelligence Upgrade imports (lazy — fail silently if deps missing) ---
try:
    from fastapi import WebSocket, WebSocketDisconnect
    _WS_AVAILABLE = True
except ImportError:
    _WS_AVAILABLE = False

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
        reader, writer = await asyncio.wait_for(asyncio.open_connection('127.0.0.1', 11434), timeout=1.0)
        writer.close()
        await writer.wait_closed()
        return True
    except:
        return False

async def ensure_ollama():
    if await is_ollama_ready():
        # Check if model exists
        try:
            from backend.llm_client import OllamaClient
            llm = OllamaClient()
            resp = await asyncio.to_thread(requests.get, llm.tags_url, timeout=2)
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                if llm.model not in models and f"{llm.model}:latest" not in models:
                    logger.info(f"Model {llm.model} missing. Attempting to pull...")
                    # Non-blocking pull
                    subprocess.Popen(["ollama", "pull", llm.model], close_fds=True)
        except:
            pass
        return True
    try:
        logger.info("Starting ollama serve...")
        p = await asyncio.to_thread(lambda: subprocess.Popen(
            ["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True
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
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = VoidSingletons._instances.get("main_loop")
            
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(run_chat(), loop)
        else:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                new_loop.run_until_complete(run_chat())
            finally:
                new_loop.close()
    except Exception as e:
        logger.error(f"[WAKE WORD BACKGROUND] Loop submission error: {e}")

async def run_background_startup():
    """Background task to run heavy startup checks, tool validation, model checks, and services."""
    logger.info("[BACKGROUND STARTUP] Starting background initialization tasks...")
    # 1. Ollama
    try:
        ollama_ok = await ensure_ollama()
    except Exception as e:
        logger.error(f"[BACKGROUND STARTUP] Ollama check failed: {e}")
        ollama_ok = False

    # 2. Singletons test
    singles = ["router", "llm", "tool_manager", "validator"]
    failed = []
    for s in singles:
        try:
            inst = VoidSingletons.get(s)
            if not inst:
                failed.append(s)
        except Exception as e:
            logger.error(f"[BACKGROUND STARTUP] Singleton {s} initialization failed: {e}")
            failed.append(s)

    # 3. Tools
    try:
        tools_ok = await check_all_tools()
        tools_status = tools_ok.get("status", "error")
    except Exception as e:
        logger.error(f"[BACKGROUND STARTUP] Tools check failed: {e}")
        tools_status = "error"

    # 4. Non-blocking LLM warmup
    try:
        llm = VoidSingletons.get("llm")
        if llm:
            logger.info("[BACKGROUND STARTUP] Warming up LLM Client (pre-loading model)...")
            await llm.warmup()
    except Exception as e:
        logger.error(f"[BACKGROUND STARTUP] LLM warmup failed: {e}")

    # 5. Start Wake Word service as background daemon
    try:
        from tools.voice_listener import start_voice_loop_thread, set_command_callback, set_activation_phrase
        set_activation_phrase("Yes?")
        set_command_callback(process_voice_command)
        global _voice_thread
        _voice_thread = start_voice_loop_thread()
        logger.info("[BACKGROUND STARTUP] Wake word background daemon successfully initiated.")
    except Exception as e:
        logger.error(f"[BACKGROUND STARTUP] Failed to start wake word daemon: {e}")

    # Proactively apply Windows audio ducking registry fix on startup
    try:
        import platform
        if platform.system() == "Windows":
            import winreg
            key_path = r"Software\Microsoft\Multimedia\Audio"
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            except FileNotFoundError:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            winreg.SetValueEx(key, "UserDuckingPreference", 0, winreg.REG_DWORD, 3)
            winreg.CloseKey(key)
            logger.info("[BACKGROUND STARTUP] Proactively applied Windows Audio Ducking registry fix (UserDuckingPreference=3).")
    except Exception as e:
        logger.warning(f"[BACKGROUND STARTUP] Could not proactively apply Audio Ducking fix: {e}")

    # 6. Start CVCS Monitor Loop
    try:
        from server.backend.screen_monitor import get_monitor_instance
        monitor = get_monitor_instance()
        monitor.start_monitor_loop()
        logger.info("[BACKGROUND STARTUP] CVCS background monitor loop initiated.")
    except Exception as e:
        logger.error(f"[BACKGROUND STARTUP] Failed to start CVCS monitor: {e}")

    # 6a. Start Ollama Connection Manager (Phase 3)
    try:
        from backend.ollama_manager import ollama_manager
        ollama_manager.start()
        logger.info("[BACKGROUND STARTUP] Ollama Connection Manager started.")
    except Exception as e:
        logger.error(f"[BACKGROUND STARTUP] Failed to start Ollama Manager: {e}")

    # 6b. Start Audio Memory Service (Phase 3)
    try:
        from backend.audio_memory_service import audio_memory_service
        from backend.memory_sqlite import get_preference
        pref = get_preference("bg_recording_enabled")
        audio_memory_service.is_enabled = (pref == "true")
        audio_memory_service.start()
        logger.info(f"[BACKGROUND STARTUP] Audio Memory Service started (enabled={audio_memory_service.is_enabled}).")
    except Exception as e:
        logger.error(f"[BACKGROUND STARTUP] Failed to start Audio Memory Service: {e}")

    # 7. Clean up dead projects and auto-register current workspace
    try:
        import os
        from backend.memory_sqlite import list_tracked_projects, delete_project
        from tools.project_intelligence import register_project
        
        projects = list_tracked_projects()
        default_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        
        # Clean up dead projects (paths that do not exist)
        for proj in projects:
            p_path = proj.get("path")
            if not p_path or not os.path.isdir(p_path):
                logger.info(f"[BACKGROUND STARTUP] Purging dead project from DB: {proj.get('name')} ({p_path})")
                delete_project(proj.get("project_id"))
                
        # Re-fetch projects list after cleanup
        projects = list_tracked_projects()
        is_registered = False
        for proj in projects:
            if os.path.abspath(proj["path"]) == default_root:
                is_registered = True
                break
                
        if not is_registered:
            logger.info(f"[BACKGROUND STARTUP] Auto-registering project workspace at: {default_root}")
            res = await asyncio.to_thread(register_project, default_root)
            logger.info(f"[BACKGROUND STARTUP] Workspace auto-registration complete: {res.get('status')}")
    except Exception as proj_err:
        logger.error(f"[BACKGROUND STARTUP] Project workspace check/registration failed: {proj_err}")

    logger.info(f"[BACKGROUND STARTUP] Complete: ollama={ollama_ok}, singles_failed={len(failed)}, tools={tools_status}")


_voice_thread = None

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for VOID."""
    logger.info("VOID startup...")
    # Register the main running event loop
    VoidSingletons._instances["main_loop"] = asyncio.get_running_loop()
    # Spawn startup tasks in background to keep startup time near zero
    asyncio.create_task(run_background_startup())

    # --- Real-Time Intelligence: start RSS background poller ---
    try:
        from news.rss_engine import get_engine as get_rss_engine
        rss_engine = get_rss_engine()
        rss_engine.start_background_fetch()
        logger.info("[LIFESPAN] RSS news engine started (background polling active).")
    except Exception as _rss_err:
        logger.warning(f"[LIFESPAN] RSS engine could not start: {_rss_err}")

    yield

    logger.info("VOID shutdown...")
    
    # Stop Ollama manager (Phase 3)
    try:
        from backend.ollama_manager import ollama_manager
        ollama_manager.stop()
        logger.info("[LIFESPAN] Ollama Connection Manager stopped.")
    except Exception:
        pass
        
    # Stop Audio Memory Service (Phase 3)
    try:
        from backend.audio_memory_service import audio_memory_service
        audio_memory_service.stop()
        logger.info("[LIFESPAN] Audio Memory Service stopped.")
    except Exception:
        pass

    # Stop RSS engine
    try:
        from news.rss_engine import get_engine as get_rss_engine
        get_rss_engine().stop_background_fetch()
    except Exception:
        pass
    
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

# Register sub-routers
from routes.admin import router as admin_router
from routes.chat import router as chat_router, WorkflowRequest
from routes.memory import router as memory_router
app.include_router(admin_router)
app.include_router(chat_router)
app.include_router(memory_router)

class WebSocketBypassCORSMiddleware(CORSMiddleware):
    async def __call__(self, scope, receive, send):
        logger.info(f"CORS SCOPE TYPE: {scope.get('type')}, PATH: {scope.get('path')}")
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)

app.add_middleware(WebSocketBypassCORSMiddleware, allow_origins=["*", "file://"], allow_origin_regex=".*", allow_methods=["*"], allow_headers=["*"])

# Exempt paths from token verification (like /health)
EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/ws/approval"}

class SecureTokenAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        logger.info(f"ASGI SCOPE TYPE: {scope.get('type')}, PATH: {scope.get('path')}")
        if scope["type"] == "websocket":
            query_string = scope.get("query_string", b"").decode("latin-1")
            import urllib.parse
            query_params = urllib.parse.parse_qs(query_string)
            token = query_params.get("token", [None])[0]
            
            if not token:
                headers = {k.decode('latin-1').lower(): v.decode('latin-1') for k, v in scope.get('headers', [])}
                auth_header = headers.get("sec-websocket-protocol") or headers.get("authorization")
                if auth_header:
                    if auth_header.startswith("Bearer "):
                        token = auth_header.split(" ")[1]
                    else:
                        token = auth_header
            
            if token != API_TOKEN:
                logger.warning(f"WebSocket connection denied: invalid token {token}")
                event = await receive()
                if event["type"] == "websocket.connect":
                    await send({"type": "websocket.close", "code": 4001})
                return
            
            await self.app(scope, receive, send)
            return

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from fastapi import Request
        from fastapi.responses import JSONResponse
        import time

        request = Request(scope, receive)
        start = time.time()

        is_exempt = request.method == "OPTIONS" or request.url.path in EXEMPT_PATHS

        if not is_exempt:
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                response = JSONResponse(
                    status_code=401,
                    content={"status": "error", "message": "Access Denied: Missing Authorization Header"}
                )
                # Apply CORS headers for direct response
                response.headers["Access-Control-Allow-Origin"] = "*"
                await response(scope, receive, send)
                return

            try:
                scheme, token = auth_header.split()
                if scheme.lower() != "bearer" or token != API_TOKEN:
                    response = JSONResponse(
                        status_code=401,
                        content={"status": "error", "message": "Access Denied: Invalid Security Token"}
                    )
                    response.headers["Access-Control-Allow-Origin"] = "*"
                    await response(scope, receive, send)
                    return
            except Exception:
                response = JSONResponse(
                    status_code=401,
                    content={"status": "error", "message": "Access Denied: Malformed Authorization Header"}
                )
                response.headers["Access-Control-Allow-Origin"] = "*"
                await response(scope, receive, send)
                return

        status_code = [200]

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code[0] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = (time.time() - start) * 1000
            logger.info(f"{request.method} {request.url.path} - {status_code[0]} - {duration:.0f}ms")

app.add_middleware(SecureTokenAuthMiddleware)

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

# === ENDPOINTS (Extracted to routes/) ===

# =============================================================================
# REAL-TIME INTELLIGENCE ENDPOINTS
# =============================================================================

# ---------------------------------------------------------------------------
# Request/Response models for new endpoints
# ---------------------------------------------------------------------------

# [Extracted Chat Route Block]

class FSReadRequest(BaseModel):
    path: str

class FSWriteRequest(BaseModel):
    path: str
    content: str
    encoding: str = "utf-8"

class FSListRequest(BaseModel):
    path: str = "."
    max_entries: int = 200

class TerminalRunRequest(BaseModel):
    command: str
    cwd: Optional[str] = None
    timeout: int = 120

class BuildPlanRequest(BaseModel):
    requirements: str
    target_dir: str = "."

class BuildExecuteRequest(BaseModel):
    plan_id: str
    target_dir: str = "."
    batch_approve: bool = True

class ApprovalResponse(BaseModel):
    request_id: str
    approved: bool

# ---------------------------------------------------------------------------
# Search endpoint
# ---------------------------------------------------------------------------

# [Extracted Chat Route Block]

# ---------------------------------------------------------------------------
# News endpoints
# ---------------------------------------------------------------------------

# [Extracted Chat Route Block]


# [Extracted Chat Route Block]

# ---------------------------------------------------------------------------
# File System endpoints
# ---------------------------------------------------------------------------
@app.post("/api/fs/read")
async def api_fs_read(req: FSReadRequest):
    """Read a file — no approval required."""
    try:
        from backend.fs_tools import get_fs_tools
        return get_fs_tools().read_file(req.path)
    except Exception as e:
        logger.error(f"[/api/fs/read] Error: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/fs/write")
async def api_fs_write(req: FSWriteRequest):
    """Write a file — triggers user approval gate."""
    try:
        from backend.fs_tools import get_fs_tools
        return await get_fs_tools().write_file(req.path, req.content, req.encoding)
    except Exception as e:
        logger.error(f"[/api/fs/write] Error: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/fs/list")
async def api_fs_list(req: FSListRequest):
    """List directory contents — no approval required."""
    try:
        from backend.fs_tools import get_fs_tools
        return get_fs_tools().list_directory(req.path, req.max_entries)
    except Exception as e:
        logger.error(f"[/api/fs/list] Error: {e}")
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Terminal endpoint
# ---------------------------------------------------------------------------
@app.post("/api/terminal/run")
async def api_terminal_run(req: TerminalRunRequest):
    """Execute a terminal command — triggers user approval gate."""
    try:
        from tools.terminal_tools import execute_sandboxed
        return await execute_sandboxed(req.command, cwd=req.cwd, timeout=req.timeout)
    except Exception as e:
        logger.error(f"[/api/terminal/run] Error: {e}")
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Builder Agent endpoints
# ---------------------------------------------------------------------------
_pending_build_plans: Dict[str, Any] = {}  # plan_id → BuildPlan

@app.post("/api/build/plan")
async def api_build_plan(req: BuildPlanRequest):
    """Generate a project build plan. Does NOT write any files."""
    try:
        from backend.builder_agent import get_builder
        builder = get_builder()
        plan = builder.plan(req.requirements)
        _pending_build_plans[plan.id] = plan

        # Log build decision
        try:
            from backend.memory_sqlite import store_build_decision
            store_build_decision(
                project=plan.project_name,
                decision=f"Generated {plan.project_type} scaffold",
                rationale=req.requirements,
                tech_stack=", ".join(plan.tech_stack),
                approved=False,
            )
        except Exception:
            pass

        return {"status": "ok", "plan": builder.plan_to_dict(plan)}
    except Exception as e:
        logger.error(f"[/api/build/plan] Error: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/build/execute")
async def api_build_execute(req: BuildExecuteRequest):
    """Execute a previously generated build plan."""
    plan = _pending_build_plans.get(req.plan_id)
    if not plan:
        return {"status": "error", "message": f"Plan '{req.plan_id}' not found. Generate a plan first."}
    try:
        from backend.builder_agent import get_builder
        builder = get_builder()
        result = await builder.execute_plan(plan, req.target_dir, req.batch_approve)

        # Mark decision as approved
        try:
            from backend.memory_sqlite import store_build_decision
            store_build_decision(
                project=plan.project_name,
                decision="Build plan executed",
                rationale=f"Created {len(result.files_created)} files at {result.target_dir}",
                tech_stack=", ".join(plan.tech_stack),
                approved=result.success,
            )
        except Exception:
            pass

        return {
            "status": "ok" if result.success else "partial",
            "plan_id": result.plan_id,
            "files_created": result.files_created,
            "files_skipped": result.files_skipped,
            "errors": result.errors,
            "target_dir": result.target_dir,
            "elapsed_seconds": result.elapsed_seconds,
        }
    except Exception as e:
        logger.error(f"[/api/build/execute] Error: {e}")
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Intelligence Status (monitoring dashboard)
# ---------------------------------------------------------------------------
@app.get("/api/intelligence-status")
async def api_intelligence_status():
    """Return real-time status of all intelligence subsystems."""
    status: Dict[str, Any] = {"status": "ok", "components": {}}

    # Ollama / LLM
    ollama_ok = False
    try:
        ollama_ok = await is_ollama_ready()
        llm = VoidSingletons.get("llm")
        status["components"]["ollama"] = {
            "status": "online" if ollama_ok else "offline",
            "model": llm.model if llm else "unknown",
        }
    except Exception as e:
        status["components"]["ollama"] = {"status": "error", "message": str(e)}

    # DuckDuckGo Search
    try:
        from search.duckduckgo_provider import get_provider
        status["components"]["search"] = get_provider().status()
    except Exception as e:
        status["components"]["search"] = {"status": "unavailable", "message": str(e)}

    # RSS Engine
    try:
        from news.rss_engine import get_engine
        status["components"]["rss"] = get_engine().status()
    except Exception as e:
        status["components"]["rss"] = {"status": "unavailable", "message": str(e)}

    # Memory
    try:
        from backend.memory_sqlite import get_recent_searches, get_user_patterns
        recent = get_recent_searches(5)
        patterns = get_user_patterns(5)
        status["components"]["memory"] = {
            "status": "online",
            "recent_searches": len(recent),
            "top_intents": patterns,
        }
    except Exception as e:
        status["components"]["memory"] = {"status": "error", "message": str(e)}

    # Engineering Mode
    try:
        from backend.engineering_mode import get_engineering_mode
        status["components"]["engineering"] = get_engineering_mode().status()
    except Exception as e:
        status["components"]["engineering"] = {"status": "unavailable", "message": str(e)}

    # Builder Agent
    try:
        from backend.builder_agent import get_builder
        status["components"]["builder"] = get_builder().status()
    except Exception as e:
        status["components"]["builder"] = {"status": "unavailable", "message": str(e)}

    # FS Tools
    try:
        from backend.fs_tools import get_fs_tools
        status["components"]["fs_tools"] = get_fs_tools().status()
    except Exception as e:
        status["components"]["fs_tools"] = {"status": "unavailable", "message": str(e)}

    # Terminal Tools
    try:
        from tools.terminal_tools import get_terminal_status
        status["components"]["terminal"] = get_terminal_status()
    except Exception as e:
        status["components"]["terminal"] = {"status": "unavailable", "message": str(e)}

    # Flatten response for UI compatibility
    flat_status = {
        "status": "ok",
        "ollama_model": status["components"].get("ollama", {}).get("model", "unknown"),
        "ollama_online": ollama_ok,
        "last_search_query": status["components"].get("search", {}).get("last_query", ""),
        "search_online": status["components"].get("search", {}).get("status") == "ready",
        "rss_article_count": status["components"].get("rss", {}).get("cache", {}).get("total_articles", 0),
        "rss_last_fetch": status["components"].get("rss", {}).get("last_fetch", ""),
        "rss_online": status["components"].get("rss", {}).get("status") == "running",
        "memory_total_facts": 0,
        "memory_searches": 0,
        "engineering_status": "active" if status["components"].get("engineering", {}).get("active") else "idle",
        "builder_last_project": status["components"].get("builder", {}).get("last_plan_name", "") or "--",
        "components": status["components"]
    }

    try:
        from backend.memory_sqlite import get_all_facts, DB_FILE
        flat_status["memory_total_facts"] = len(get_all_facts())
        
        # Count searches from SQLite directly
        import sqlite3
        conn = sqlite3.connect(str(DB_FILE))
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM search_history")
        flat_status["memory_searches"] = cursor.fetchone()[0]
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to fetch memory status details: {e}")

    return flat_status


# ---------------------------------------------------------------------------
# WebSocket — Approval Gate channel
# ---------------------------------------------------------------------------
@app.websocket("/ws/approval")
async def ws_approval(websocket: WebSocket):
    """
    WebSocket channel for the user approval gate.

    The Electron UI connects here to:
    - RECEIVE approval_request events (show modal)
    - SEND back user decisions {request_id, approved: true/false}
    """
    try:
        await websocket.accept()
        from backend.fs_tools import register_approval_ws, unregister_approval_ws, resolve_approval
        register_approval_ws(websocket)
        logger.info("[WS/approval] Client connected")
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                    request_id = msg.get("request_id", "")
                    approved = bool(msg.get("approved", False))
                    if request_id:
                        resolved = resolve_approval(request_id, approved)
                        logger.info(
                            f"[WS/approval] Resolved {request_id}: "
                            f"{'APPROVED' if approved else 'DENIED'} (found={resolved})"
                        )
                except Exception as parse_err:
                    logger.warning(f"[WS/approval] Invalid message: {parse_err}")
        except Exception:
            pass
        finally:
            unregister_approval_ws(websocket)
            logger.info("[WS/approval] Client disconnected")
    except Exception as e:
        logger.error(f"[WS/approval] Error: {e}")

# /stats extracted to routes/admin.py


# [Extracted Chat Route Block]


# [Extracted Chat Route Block]


# [Extracted Chat Route Block]

class FaceVerifyRequest(BaseModel):
    image: str

_last_frame_hash = None

@app.post("/api/cvcs/verify-face")
async def verify_face_endpoint(req: FaceVerifyRequest):
    global _last_frame_hash
    try:
        from PIL import Image
        import base64
        from io import BytesIO
        
        header, encoded = req.image.split(",", 1) if "," in req.image else ("", req.image)
        image_data = base64.b64decode(encoded)
        img = Image.open(BytesIO(image_data))
        
        width, height = img.size
        if width <= 0 or height <= 0:
            raise ValueError("Invalid dimensions")
            
        img_small = img.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
        pixels = list(img_small.getdata())
        avg = sum(pixels) / 64
        diff_bits = "".join(["1" if p > avg else "0" for p in pixels])
        frame_hash = int(diff_bits, 2)
        
        activity_detected = False
        if _last_frame_hash is not None:
            hamming = bin(frame_hash ^ _last_frame_hash).count("1")
            if hamming > 0:
                activity_detected = True
                
        _last_frame_hash = frame_hash
        
        return {
            "status": "ok",
            "message": "Access Granted, Sir.",
            "authorized": True,
            "user": "Mridul Sharma",
            "metrics": {
                "resolution": f"{width}x{height}",
                "activity": "Live Feed Verified" if activity_detected else "Syncing Frame..."
            }
        }
    except Exception as e:
        logger.error(f"Face verification failed: {e}")
        return {
            "status": "error",
            "message": f"Biometric scan failed: {e}",
            "authorized": False
        }

class EngineeringProposeRequest(BaseModel):
    goal: str


# [Extracted Chat Route Block]


# [Extracted Chat Route Block]

@app.get("/api/engineering/proposal")
async def get_engineering_proposal():
    proposal_path = DATA_DIR / "pending_proposal.json"
    if proposal_path.exists():
        try:
            with open(proposal_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"error": f"Failed to load proposal: {e}"}
    return {"status": "empty", "message": "No pending proposals"}

@app.post("/api/engineering/propose")
async def propose_engineering_changes(req: EngineeringProposeRequest):
    llm = VoidSingletons.get("llm")
    if not llm:
        return {"status": "error", "message": "LLM not initialized"}
        
    from backend.project_analyzer import ProjectContextCompressor
    compressor = ProjectContextCompressor(str(ROOT_DIR))
    context_str = compressor.build_compressed_context()
    
    sys_prompt = """You are the VOID Advanced Engineering Brain.
Analyze the user's coding/architecture goal and generate a structured engineering proposal.
You must respond with a single valid JSON object. Do not wrap it in markdown code blocks or add explanations.

JSON Schema:
{
  "goal": "string",
  "analysis": "string detailing dependencies and architecture design",
  "affected_files": ["string"],
  "required_changes": "string",
  "risks": "string detailing risks and constraints",
  "implementation_order": ["string"],
  "testing_plan": "string",
  "proposed_diffs": [
    {
      "file_path": "string (path relative to project root)",
      "action": "create | modify | delete",
      "description": "string describing what changes in this file",
      "original_content": "string (the current file content, or empty if creating)",
      "proposed_content": "string (the complete proposed content of the file)"
    }
  ]
}
"""
    prompt = f"Project Context:\n{context_str}\n\nUser Goal: {req.goal}\n\nPlease generate the engineering proposal JSON."
    
    try:
        provider = None
        if hasattr(llm, "router"):
            provider = llm.router.kimi_provider
            
        if not provider or not provider.api_key:
            provider = llm
            
        res_str = await provider.chat([], prompt, system_prompt=sys_prompt)
        
        clean_str = res_str.strip()
        if clean_str.startswith("```"):
            lines = clean_str.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_str = "\n".join(lines).strip()
            
        proposal = json.loads(clean_str)
        
        proposal_path = DATA_DIR / "pending_proposal.json"
        with open(proposal_path, "w", encoding="utf-8") as f:
            json.dump(proposal, f, indent=4)
            
        return proposal
    except Exception as e:
        logger.error(f"Failed to generate engineering proposal: {e}", exc_info=True)
        return {"status": "error", "message": f"Proposal generation failed: {e}"}

@app.post("/api/engineering/approve")
async def approve_engineering_changes():
    proposal_path = DATA_DIR / "pending_proposal.json"
    if not proposal_path.exists():
        return {"status": "error", "message": "No pending proposal to approve"}
        
    try:
        with open(proposal_path, "r", encoding="utf-8") as f:
            proposal = json.load(f)
            
        applied_files = []
        import shutil
        for diff in proposal.get("proposed_diffs", []):
            f_path = ROOT_DIR / diff["file_path"]
            action = diff.get("action", "modify").lower()
            
            f_path.parent.mkdir(parents=True, exist_ok=True)
            
            if f_path.exists() and f_path.is_file():
                backup = f_path.with_suffix(f_path.suffix + ".bak")
                shutil.copy2(f_path, backup)
                
            if action in ["create", "modify"]:
                with open(f_path, "w", encoding="utf-8") as file_out:
                    file_out.write(diff["proposed_content"])
                applied_files.append(diff["file_path"])
            elif action == "delete":
                if f_path.exists():
                    f_path.unlink()
                applied_files.append(f"{diff['file_path']} (Deleted)")
                
        proposal_path.unlink()
        
        return {"status": "ok", "message": f"Applied changes successfully to: {', '.join(applied_files)}"}
    except Exception as e:
        logger.error(f"Failed to apply proposed changes: {e}")
        return {"status": "error", "message": f"Execution failed: {e}"}

@app.post("/api/engineering/reject")
async def reject_engineering_changes():
    proposal_path = DATA_DIR / "pending_proposal.json"
    if proposal_path.exists():
        proposal_path.unlink()
        return {"status": "ok", "message": "Proposal rejected and cleared"}
    return {"status": "error", "message": "No pending proposal to reject"}

# /time and /system-info extracted to routes/admin.py


# [Extracted Chat Route Block]


# [Extracted Chat Route Block]

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

# ProfileRequest moved to routes/memory.py


# [Extracted Memory Route Block]


# [Extracted Memory Route Block]

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

@app.get("/api/voice/wake-word/status")
async def get_wake_word_status():
    try:
        from tools.voice_listener import is_listening
        return {"active": is_listening()}
    except Exception as e:
        logger.error(f"Error checking wake word status: {e}")
        return {"active": False, "error": str(e)}

@app.post("/api/voice/wake-word/toggle")
async def toggle_wake_word(req: dict = None):
    global _voice_thread
    try:
        from tools.voice_listener import is_listening, stop_voice_loop, start_voice_loop_thread
        
        target = None
        if req and "active" in req:
            target = req["active"]
            
        current = is_listening()
        if target is None:
            target = not current
            
        if target == current:
            return {"active": current}
            
        if target:
            from tools.voice_listener import set_command_callback, set_activation_phrase
            set_activation_phrase("Yes?")
            set_command_callback(process_voice_command)
            _voice_thread = start_voice_loop_thread()
            # Wait briefly to let it start and set _listening = True
            await asyncio.sleep(0.5)
        else:
            stop_voice_loop()
            # Wait briefly to let it stop
            await asyncio.sleep(0.5)
            
        return {"active": is_listening()}
    except Exception as e:
        logger.error(f"Error toggling wake word: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/voice/wake-word/fix-ducking")
async def fix_audio_ducking():
    try:
        import platform
        if platform.system() != "Windows":
            return {"status": "error", "message": "Audio ducking configuration is only supported on Windows."}
            
        import winreg
        key_path = r"Software\Microsoft\Multimedia\Audio"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        except FileNotFoundError:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            
        # 3 = Do nothing when communications activity is detected
        winreg.SetValueEx(key, "UserDuckingPreference", 0, winreg.REG_DWORD, 3)
        winreg.CloseKey(key)
        
        logger.info("[VOICE ENGINE] Registry fix applied: UserDuckingPreference set to 3 (Do nothing)")
        return {"status": "success", "message": "Windows Communications Ducking preference updated to 'Do Nothing'. Please restart the system or browser/application for the changes to fully apply."}
    except Exception as e:
        logger.error(f"Failed to fix audio ducking: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update registry: {str(e)}")


# ===========================================================================
# OLLAMA & AUDIO RECORDING & GLOBAL SEARCH ENDPOINTS (Phase 3)
# ===========================================================================


# [Extracted Chat Route Block]


# [Extracted Chat Route Block]

@app.get("/api/recordings")
async def get_recordings_list(q: str = "", limit: int = 50, offset: int = 0):
    try:
        from backend.memory_sqlite import get_audio_recordings
        recordings = get_audio_recordings(search_query=q, limit=limit, offset=offset)
        return {"status": "ok", "recordings": recordings}
    except Exception as e:
        logger.error(f"Error listing recordings: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/recordings/{id}")
async def get_recording_detail(id: int):
    try:
        from backend.memory_sqlite import get_audio_recording
        recording = get_audio_recording(id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")
            
        # Load word-level timestamps from transcript JSON if available
        words = []
        import json
        json_path = recording["recording_path"].replace(".wav", "_transcript.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    words = data.get("words", [])
            except Exception as ex:
                logger.warning(f"Could not read transcript JSON: {ex}")
        recording["words"] = words
        
        return {"status": "ok", "recording": recording}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recording detail: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/recordings/{id}/audio")
async def get_recording_audio(id: int):
    try:
        from backend.memory_sqlite import get_audio_recording
        recording = get_audio_recording(id)
        if not recording or not os.path.exists(recording["recording_path"]):
            raise HTTPException(status_code=404, detail="Audio file not found")
        from fastapi.responses import FileResponse
        return FileResponse(recording["recording_path"], media_type="audio/wav")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming recording audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/recordings/{id}")
async def delete_recording(id: int):
    try:
        from backend.memory_sqlite import get_audio_recording, delete_audio_recording
        recording = get_audio_recording(id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")
        
        # Delete local files
        path = recording["recording_path"]
        for suffix in [".wav", "_transcript.json", "_summary.json"]:
            file_to_del = path if suffix == ".wav" else path.replace(".wav", suffix)
            try:
                if os.path.exists(file_to_del):
                    os.remove(file_to_del)
            except Exception as e:
                logger.warning(f"Could not delete file {file_to_del}: {e}")
                
        success = delete_audio_recording(id)
        return {"status": "ok" if success else "error"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting recording: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/recordings/toggle")
async def toggle_recordings(req: dict = None):
    try:
        from backend.audio_memory_service import audio_memory_service
        active = req.get("active") if req else None
        if active is None:
            active = not audio_memory_service.is_enabled
        audio_memory_service.enable_recording(active)
        return {"status": "ok", "active": audio_memory_service.is_enabled}
    except Exception as e:
        logger.error(f"Error toggling background recording: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/recordings/status")
async def get_recordings_status():
    try:
        from backend.audio_memory_service import audio_memory_service
        mics = audio_memory_service.get_microphones()
        return {
            "status": "ok",
            "active": audio_memory_service.is_enabled,
            "microphones": mics,
            "current_device": audio_memory_service.device_index
        }
    except Exception as e:
        logger.error(f"Error getting recordings status: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/recordings/select-device")
async def select_recording_device(req: dict = None):
    try:
        index = req.get("index") if req else None
        if index is None:
            raise HTTPException(status_code=400, detail="index is required")
        from backend.audio_memory_service import audio_memory_service
        audio_memory_service.select_device(index)
        return {"status": "ok", "current_device": audio_memory_service.device_index}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error selecting recording device: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/recordings/{id}/favorite")
async def toggle_favorite_recording(id: int):
    try:
        from backend.memory_sqlite import toggle_audio_recording_favorite
        success = toggle_audio_recording_favorite(id)
        return {"status": "ok" if success else "error"}
    except Exception as e:
        logger.error(f"Error favoriting recording {id}: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/recordings/{id}/pin")
async def toggle_pin_recording(id: int):
    try:
        from backend.memory_sqlite import toggle_audio_recording_pinned
        success = toggle_pin_recording(id)
        return {"status": "ok" if success else "error"}
    except Exception as e:
        logger.error(f"Error pinning recording {id}: {e}")
        return {"status": "error", "message": str(e)}

# /api/metrics extracted to routes/admin.py

@app.post("/api/recordings/start")
async def start_recording_api(req: dict = None):
    try:
        mode = req.get("mode", "continuous") if req else "continuous"
        from backend.audio_memory_service import audio_memory_service
        audio_memory_service.start_manual_recording(mode)
        return {"status": "ok", "active": True, "mode": mode}
    except Exception as e:
        logger.error(f"Error starting manual recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/recordings/stop")
async def stop_recording_api():
    try:
        from backend.audio_memory_service import audio_memory_service
        audio_memory_service.stop_manual_recording()
        return {"status": "ok", "active": False}
    except Exception as e:
        logger.error(f"Error stopping manual recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/recordings/{id}/bookmark")
async def add_recording_bookmark_api(id: int, req: dict = None):
    try:
        timestamp = req.get("timestamp", 0.0) if req else 0.0
        label = req.get("label", "Bookmark") if req else "Bookmark"
        from backend.memory_sqlite import add_bookmark
        success = add_bookmark(id, timestamp, label)
        return {"status": "ok" if success else "error"}
    except Exception as e:
        logger.error(f"Error adding bookmark: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/recordings/{id}/rename")
async def rename_recording_api(id: int, req: dict = None):
    try:
        title = req.get("title") if req else None
        if not title:
            raise HTTPException(status_code=400, detail="title is required")
        from backend.memory_sqlite import get_audio_recording
        recording = get_audio_recording(id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")
        
        old_path = Path(recording["recording_path"])
        import re
        clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title)
        new_name = f"{clean_title}.wav"
        new_path = old_path.parent / new_name
        
        if old_path.exists():
            os.rename(old_path, new_path)
            
        for suffix in ["_transcript.json", "_summary.json"]:
            old_json = Path(str(old_path).replace(".wav", suffix))
            new_json = Path(str(new_path).replace(".wav", suffix))
            if old_json.exists():
                os.rename(old_json, new_json)
                
        from backend.memory_sqlite import DB_FILE
        import sqlite3
        conn = sqlite3.connect(str(DB_FILE))
        cursor = conn.cursor()
        cursor.execute("UPDATE audio_recordings SET recording_path = ? WHERE id = ?", (str(new_path), id))
        conn.commit()
        conn.close()
        
        return {"status": "ok", "new_path": str(new_path)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error renaming recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recordings/{id}/export/{format}")
async def export_recording_api(id: int, format: str):
    try:
        from backend.memory_sqlite import get_audio_recording
        recording = get_audio_recording(id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")
            
        if format == "audio":
            if not os.path.exists(recording["recording_path"]):
                raise HTTPException(status_code=404, detail="Audio file not found")
            from fastapi.responses import FileResponse
            return FileResponse(recording["recording_path"], filename=os.path.basename(recording["recording_path"]))
            
        elif format == "transcript":
            from fastapi.responses import PlainTextResponse
            content = recording.get("transcript", "")
            return PlainTextResponse(content, headers={"Content-Disposition": f"attachment; filename=transcript_{id}.txt"})
            
        elif format == "summary":
            from fastapi.responses import PlainTextResponse
            content = f"# Summary for Recording #{id}\n\n"
            content += f"**Timestamp**: {recording.get('timestamp')}\n"
            content += f"**Duration**: {recording.get('duration')} seconds\n"
            content += f"**Mode**: {recording.get('mode')}\n\n"
            content += f"## AI Summary\n{recording.get('summary')}\n\n"
            
            content += "## Action Items\n"
            for item in recording.get("action_items", []):
                content += f"- [ ] {item}\n"
            content += "\n"
            
            content += "## Tasks Detected\n"
            for item in recording.get("tasks", []):
                content += f"- {item}\n"
            content += "\n"
            
            content += "## People Mentioned\n"
            content += ", ".join(recording.get("names", [])) + "\n\n"
            
            content += "## Keywords\n"
            content += ", ".join(recording.get("keywords", [])) + "\n"
            
            return PlainTextResponse(content, headers={"Content-Disposition": f"attachment; filename=summary_{id}.md"})
            
        else:
            raise HTTPException(status_code=400, detail="Invalid export format")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# [Extracted Chat Route Block]

@app.get("/api/tasks")
async def get_tasks():
    from core.autonomous_agent.task_planner import TaskPlanner
    planner = TaskPlanner()
    return {"status": "ok", "tasks": planner.list_tasks()}


@app.get("/api/tasks/{task_id}")
async def get_task_by_id(task_id: str):
    from core.autonomous_agent.task_planner import TaskPlanner
    planner = TaskPlanner()
    task = planner.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok", "task": task.to_dict()}


@app.post("/api/tasks/clear")
async def clear_tasks():
    from core.autonomous_agent.task_planner import TaskPlanner
    planner = TaskPlanner()
    planner.clear_tasks()
    return {"status": "ok", "message": "Tasks cleared successfully"}


@app.get("/api/tools")
async def get_all_tools_metadata():
    from core.tools.tool_orchestrator import ToolOrchestrator
    orchestrator = ToolOrchestrator()
    return {"status": "ok", "tools": orchestrator.list_all_tools()}

# /repair and /diagnostics extracted to routes/admin.py


# [Extracted Chat Route Block]

@app.get("/projects/list")
async def get_projects_list():
    from backend.memory_sqlite import list_tracked_projects
    try:
        return list_tracked_projects()
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        return []

class ProjectScanRequest(BaseModel):
    path: str

@app.post("/projects/scan")
async def scan_project_endpoint(req: ProjectScanRequest):
    import os
    from tools.project_intelligence import register_project, scan_project_changes, get_project_status
    from backend.memory_sqlite import list_tracked_projects
    try:
        if not os.path.exists(req.path) or not os.path.isdir(req.path):
            raise HTTPException(status_code=400, detail="Invalid directory path")
        proj_abs = os.path.abspath(req.path)
        projects = list_tracked_projects()
        target_proj = None
        for p in projects:
            if os.path.normcase(p["path"]) == os.path.normcase(proj_abs):
                target_proj = p
                break
        
        if not target_proj:
            res = register_project(proj_abs)
            if res.get("status") == "error":
                raise HTTPException(status_code=500, detail=res.get("message", "Registration failed"))
            projects = list_tracked_projects()
            for p in projects:
                if os.path.normcase(p["path"]) == os.path.normcase(proj_abs):
                    target_proj = p
                    break
        
        if not target_proj:
            raise HTTPException(status_code=500, detail="Failed to register project in memory database")
        
        scan_res = scan_project_changes(target_proj["project_id"])
        status_res = get_project_status(target_proj["name"])
        
        return {
            "status": "ok",
            "project": target_proj,
            "scan": scan_res,
            "analysis": status_res
        }
    except Exception as e:
        logger.error(f"Project scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/projects/delete/{project_id}")
async def delete_project_endpoint(project_id: str):
    from backend.memory_sqlite import delete_project
    try:
        ok = delete_project(project_id)
        if ok:
            return {"status": "ok", "message": f"Project {project_id} deleted."}
        else:
            raise HTTPException(status_code=500, detail="Delete operation returned false")
    except Exception as e:
        logger.error(f"Failed to delete project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/projects/files/{project_id}")
async def get_project_files_endpoint(project_id: str):
    from backend.memory_sqlite import get_project_files
    try:
        files = get_project_files(project_id)
        return files
    except Exception as e:
        logger.error(f"Failed to list project files: {e}")
        return []

@app.get("/projects/details/{project_id}")
async def get_project_details_endpoint(project_id: str):
    from backend.memory_sqlite import get_project
    try:
        project = get_project(project_id)
        if project:
            return project
        raise HTTPException(status_code=404, detail="Project not found")
    except Exception as e:
        logger.error(f"Failed to get project details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === MEMORY API ===

# [Extracted Memory Route Block]

# AddMemoryRequest and DeleteMemoryRequest moved to routes/memory.py


# [Extracted Memory Route Block]

@app.get("/meetings/list")
async def list_meetings():
    from backend.memory_sqlite import get_recent_meetings
    try:
        return get_recent_meetings(limit=50)
    except Exception as e:
        logger.error(f"Failed to list meetings: {e}")
        return []

@app.post("/meetings/start")
async def start_meeting_endpoint():
    from tools.meeting_assistant import start_meeting
    try:
        res = start_meeting()
        return res
    except Exception as e:
        logger.error(f"Failed to start meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/meetings/stop")
async def stop_meeting_endpoint():
    from tools.meeting_assistant import stop_meeting
    try:
        res = stop_meeting()
        return res
    except Exception as e:
        logger.error(f"Failed to stop meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/meetings/action-items")
async def get_meetings_action_items():
    from tools.meeting_assistant import get_action_items
    try:
        res = get_action_items()
        return res
    except Exception as e:
        logger.error(f"Failed to get meeting action items: {e}")
        return {"action_items": []}

# === AUTOMATION API ===
@app.get("/automation/status")
async def get_automation_status():
    from tools.task_scheduler import get_scheduled_tasks
    try:
        tasks = get_scheduled_tasks()
        active_workflows = [
            {"id": "sys_diag", "name": "System Health Monitor", "status": "Running", "interval": "10s"},
            {"id": "cvcs_scan", "name": "CVCS Window Track Loop", "status": "Running", "interval": "2s"},
            {"id": "voice_wake", "name": "Voice Wake Word Daemon", "status": "Listening", "trigger": "Yes?"}
        ]
        return {
            "scheduled_tasks": tasks,
            "active_workflows": active_workflows
        }
    except Exception as e:
        logger.error(f"Failed to get automation status: {e}")
        return {"scheduled_tasks": [], "active_workflows": []}

# /system/health-details extracted to routes/admin.py

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

class FlashcardCreateRequest(BaseModel):
    subject_id: str
    topic_id: str
    front: str
    back: str

class FlashcardReviewRequest(BaseModel):
    card_id: int
    quality: int

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
    if ext not in [".txt", ".md", ".pdf", ".pptx"]:
        raise HTTPException(status_code=400, detail="Unsupported file format. Only PDF, TXT, MD, and PPTX files are allowed.")
        
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
    try:
        from backend import memory_sqlite
        memory_sqlite.add_xp(int(req.score * 5))
    except Exception as e:
        logger.error(f"Failed to award XP for MCQ test: {e}")
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
    try:
        from backend import memory_sqlite
        memory_sqlite.add_xp(int(score * 8))
    except Exception as e:
        logger.error(f"Failed to award XP for viva test: {e}")
    
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

@app.post("/academic/flashcards")
async def create_flashcard_endpoint(req: FlashcardCreateRequest):
    from tools.academic_progress import add_flashcard
    ok = add_flashcard(req.subject_id, req.topic_id, req.front, req.back)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to create flashcard.")
    return {"status": "ok", "message": "Flashcard created successfully."}

@app.get("/academic/flashcards/due")
async def get_due_flashcards_endpoint(subject_id: str = None):
    from tools.academic_progress import get_due_flashcards
    return get_due_flashcards(subject_id)

@app.post("/academic/flashcards/review")
async def review_flashcard_endpoint(req: FlashcardReviewRequest):
    if req.quality < 0 or req.quality > 5:
        raise HTTPException(status_code=400, detail="Quality score must be between 0 and 5 inclusive.")
    from tools.academic_progress import review_flashcard
    res = review_flashcard(req.card_id, req.quality)
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

@app.get("/academic/schedule")
async def get_study_schedule_endpoint(subject_id: str = None):
    from tools.academic_progress import generate_study_schedule
    return generate_study_schedule(subject_id)

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

# Chat helper functions and constants moved to routes/chat.py



# [Extracted Chat Route Block]

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

# /restart and /system/ping-services extracted to routes/admin.py

@app.get("/gamification/xp")
async def get_gamification_xp():
    try:
        from backend import memory_sqlite
        xp_data = memory_sqlite.get_xp()
        streaks = memory_sqlite.get_streaks()
        max_streak = 0
        if streaks:
            max_streak = max([s.get("streak_count", 0) for s in streaks])
        return {"status": "ok", "points": xp_data.get("points", 0), "level": xp_data.get("level", 1), "streak": max_streak}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/gamification/achievements")
async def get_gamification_achievements():
    try:
        from backend import memory_sqlite
        achievements = memory_sqlite.get_achievements()
        return {"status": "ok", "achievements": achievements}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8003)
