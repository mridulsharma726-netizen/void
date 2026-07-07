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
    
    import sys
    import os
    is_pytest = any("pytest" in arg for arg in sys.argv) or any("pytest" in key for key in sys.modules)
    
    if not is_pytest and not os.environ.get("VOID_TESTING") == "true":
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
from routes.chat import router as chat_router
from routes.memory import router as memory_router
from routes.projects import router as projects_router
from routes.automation import router as automation_router
from routes.voice import router as voice_router
from routes.academic import router as academic_router
app.include_router(admin_router)
app.include_router(chat_router)
app.include_router(memory_router)
app.include_router(projects_router)
app.include_router(automation_router)
app.include_router(voice_router)
app.include_router(academic_router)

class WebSocketBypassCORSMiddleware(CORSMiddleware):
    async def __call__(self, scope, receive, send):
        logger.info(f"CORS SCOPE TYPE: {scope.get('type')}, PATH: {scope.get('path')}")
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)

app.add_middleware(WebSocketBypassCORSMiddleware, allow_origins=["*", "file://"], allow_origin_regex=".*", allow_methods=["*"], allow_headers=["*"])

# Exempt paths from token verification (like /health)
EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/ws/approval", "/metrics"}


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


# [Extracted Projects Route Block]


# [Extracted Projects Route Block]


# [Extracted Projects Route Block]


# [Extracted Projects Route Block]


# [Extracted Projects Route Block]


# [Extracted Projects Route Block]


# [Extracted Projects Route Block]

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

# [Extracted Projects Route Block]


# [Extracted Projects Route Block]


# [Extracted Projects Route Block]

# ---------------------------------------------------------------------------
# Terminal endpoint
# ---------------------------------------------------------------------------

# [Extracted Projects Route Block]

# ---------------------------------------------------------------------------
# Builder Agent endpoints
# ---------------------------------------------------------------------------
_pending_build_plans: Dict[str, Any] = {}  # plan_id → BuildPlan


# [Extracted Projects Route Block]


# [Extracted Projects Route Block]

# ---------------------------------------------------------------------------
# Intelligence Status (monitoring dashboard)
# ---------------------------------------------------------------------------

# [Extracted Projects Route Block]

# ---------------------------------------------------------------------------
# WebSocket — Approval Gate channel
# ---------------------------------------------------------------------------

# [Extracted Automation Route Block]


# [Extracted Automation Route Block]


# [Extracted Automation Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Voice Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]
