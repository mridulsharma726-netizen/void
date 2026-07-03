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
app.include_router(admin_router)

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
class SearchRequest(BaseModel):
    query: str
    max_results: int = 5
    news_mode: bool = False

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
@app.post("/api/search")
async def api_search(req: SearchRequest):
    """
    DuckDuckGo web search (no API key required).
    Returns structured results: title, url, snippet, source.
    """
    try:
        from search.duckduckgo_provider import get_provider
        provider = get_provider()
        if req.news_mode:
            results = provider.search_news(req.query, max_results=req.max_results)
        else:
            results = provider.search(req.query, max_results=req.max_results)

        # Log to memory
        try:
            from backend.memory_sqlite import store_search
            store_search(
                query=req.query,
                intent="news_query" if req.news_mode else "web_search",
                source="duckduckgo",
                result_count=len(results),
                web_used=not req.news_mode,
                news_used=req.news_mode,
                latency_ms=provider._last_latency_ms,
            )
        except Exception:
            pass

        return {"status": "ok", "query": req.query, "results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"[/api/search] Error: {e}")
        return {"status": "error", "message": str(e), "results": []}


# ---------------------------------------------------------------------------
# News endpoints
# ---------------------------------------------------------------------------
@app.get("/api/news")
async def api_news(n: int = 10, category: str = ""):
    """Return the most recent cached RSS news articles."""
    try:
        from news.rss_engine import get_engine
        engine = get_engine()
        if category:
            articles = engine.fetch_category(category)
        else:
            articles = engine.get_recent(n)
        return {
            "status": "ok",
            "articles": [a.to_dict() for a in articles],
            "count": len(articles),
        }
    except Exception as e:
        logger.error(f"[/api/news] Error: {e}")
        return {"status": "error", "message": str(e), "articles": []}


@app.get("/api/news/search")
async def api_news_search(q: str, n: int = 10):
    """Full-text search over cached RSS articles."""
    try:
        from news.rss_engine import get_engine
        engine = get_engine()
        articles = engine.search_articles(q, n)
        return {
            "status": "ok",
            "query": q,
            "articles": [a.to_dict() for a in articles],
            "count": len(articles),
        }
    except Exception as e:
        logger.error(f"[/api/news/search] Error: {e}")
        return {"status": "error", "message": str(e), "articles": []}


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

class LLMConfigRequest(BaseModel):
    routing_mode: Optional[str] = None
    kimi_api_key: Optional[str] = None
    kimi_model: Optional[str] = None
    local_model: Optional[str] = None
    fallback_enabled: Optional[bool] = None
    cloud_fallback: Optional[bool] = None
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    openai_base_url: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    gemini_base_url: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    anthropic_model: Optional[str] = None
    anthropic_base_url: Optional[str] = None
    active_provider: Optional[str] = None

@app.get("/api/llm/config")
async def get_llm_config():
    """Return the current LLM routing config for the settings form."""
    llm = VoidSingletons.get("llm")
    if llm and hasattr(llm, "router"):
        cfg = getattr(llm.router, "config", {})
        return {
            "routing_mode": cfg.get("routing_mode", "AUTO"),
            "cloud_fallback": cfg.get("fallback_enabled", True),
            "local_model": cfg.get("local_model", "qwen2.5:0.5b"),
            "openai_model": cfg.get("openai_model", "gpt-4o"),
            "openai_base_url": cfg.get("openai_base_url", "https://api.openai.com/v1"),
            "gemini_model": cfg.get("gemini_model", "gemini-1.5-flash"),
            "anthropic_model": cfg.get("anthropic_model", "claude-3-5-sonnet-20241022"),
            "kimi_model": cfg.get("kimi_model", "kimi-k2.7-code"),
            "active_provider": cfg.get("active_provider", "ollama"),
            "has_kimi_key": bool(cfg.get("kimi_api_key")),
            "has_openai_key": bool(cfg.get("openai_api_key")),
            "has_gemini_key": bool(cfg.get("gemini_api_key")),
            "has_anthropic_key": bool(cfg.get("anthropic_api_key"))
        }
    return {"routing_mode": "AUTO", "cloud_fallback": True}

@app.get("/api/llm/discovered-models")
async def get_discovered_models():
    """Returns dynamic model categories from Ollama tags."""
    llm = VoidSingletons.get("llm")
    if llm and hasattr(llm, "router") and hasattr(llm.router, "ollama_provider"):
        return llm.router.ollama_provider.discover_and_categorize_models()
    return {"Coding": [], "Reasoning": [], "Planning": [], "Vision": [], "Chat": [], "Lightweight": [], "Large": []}

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

@app.get("/api/llm/metrics")
async def get_llm_metrics():
    llm = VoidSingletons.get("llm")
    if llm and hasattr(llm, "router"):
        return llm.router.get_metrics()
    return {"error": "LLM client router not initialized"}

@app.post("/api/llm/config")
async def update_llm_config(req: LLMConfigRequest):
    llm = VoidSingletons.get("llm")
    if llm and hasattr(llm, "router"):
        clean_data = {k: v for k, v in req.dict().items() if v is not None}
        if "cloud_fallback" in clean_data:
            clean_data["fallback_enabled"] = clean_data.pop("cloud_fallback")
        llm.router.update_config(clean_data)
        return {"status": "ok", "config": llm.router.config}
    return {"error": "LLM client router not initialized"}

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

@app.get("/search")
async def search(query: str = ""):
    query = query.strip().lower()
    if not query:
        return {"status": "ok", "results": []}
    
    results = []
    
    # 1. Search memory facts
    try:
        from backend.memory_sqlite import search_facts
        facts = search_facts(query, limit=5)
        for f in facts:
            results.append({
                "type": "memory",
                "title": "Remembered Fact",
                "snippet": f.get("fact", ""),
                "action": f"Recall fact: {f.get('fact', '')}"
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
                    "snippet": content[:120] + ("..." if len(content) > 120 else ""),
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
            
            if query in sub_name.lower():
                results.append({
                    "type": "academic",
                    "title": f"Academic Subject: {sub_name}",
                    "snippet": f"Mastery: {sub['mastery_level']} | Progress: {sub['progress_percent']}%",
                    "action": f"study subject {sub_name}"
                })
                
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
        
    # 4. Search voice recordings (Phase 3)
    try:
        from backend.memory_sqlite import semantic_search_recordings
        sem_recs = semantic_search_recordings(query, limit=5)
        for r in sem_recs:
            snippet_text = r["summary"] or r["transcript"] or "No transcript content."
            results.append({
                "type": "recording",
                "title": f"Voice Recording #{r['id']}",
                "snippet": snippet_text[:120] + ("..." if len(snippet_text) > 120 else ""),
                "action": f"Explain what was discussed in the voice recording from {r['timestamp']}"
            })
    except Exception as e:
        logger.error(f"Search voice recordings failed: {e}")
        
    # 5. Search tracked projects (Phase 2)
    try:
        from backend.memory_sqlite import list_tracked_projects
        projects = list_tracked_projects()
        for p in projects:
            name = p.get("name", "")
            purpose = p.get("purpose", "")
            path = p.get("path", "")
            if query in name.lower() or query in purpose.lower():
                results.append({
                    "type": "project",
                    "title": f"Project: {name}",
                    "snippet": purpose[:120] + ("..." if len(purpose) > 120 else "") if purpose else path,
                    "action": f"Analyze my project {name}"
                })
    except Exception as e:
        logger.error(f"Search projects failed: {e}")
        
    # 6. Search active tasks (Phase 2)
    try:
        from core.autonomous_agent.task_planner import TaskPlanner
        planner = TaskPlanner()
        tasks = planner.list_tasks()
        for t in tasks:
            desc = t.get("description", "")
            if query in desc.lower():
                results.append({
                    "type": "task",
                    "title": f"Task: {desc[:50]}...",
                    "snippet": f"Status: {t.get('status', 'pending')}",
                    "action": f"Show details for task {t.get('task_id')}"
                })
    except Exception as e:
        logger.error(f"Search tasks failed: {e}")
        
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

@app.get("/api/ollama/status")
async def get_ollama_status():
    try:
        from backend.ollama_manager import ollama_manager
        return ollama_manager.get_status()
    except Exception as e:
        logger.error(f"Error getting Ollama status: {e}")
        return {"status": "offline", "active_model": "", "error_message": str(e)}

@app.post("/api/ollama/start")
async def start_ollama_service():
    try:
        from backend.ollama_manager import ollama_manager
        ollama_manager.check_connection()
        return ollama_manager.get_status()
    except Exception as e:
        logger.error(f"Error starting Ollama: {e}")
        return {"status": "offline", "error_message": str(e)}

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


@app.get("/api/search/global")
async def global_search(q: str):
    if not q or not q.strip():
        return {"status": "ok", "results": []}
        
    results = []
    
    # 1. Search recordings (semantic search + keyword search)
    try:
        from backend.memory_sqlite import semantic_search_recordings
        sem_recs = semantic_search_recordings(q, limit=5)
        for r in sem_recs:
            results.append({
                "type": "recording",
                "id": r["id"],
                "title": f"Voice Recording {r['timestamp']}",
                "subtitle": r["summary"] or (r["transcript"][:120] + "..." if r["transcript"] else ""),
                "path": r["recording_path"],
                "score": r["score"],
                "timestamp": r["timestamp"]
            })
    except Exception as e:
        logger.warning(f"Global search recordings failed: {e}")
        
    # 2. Search projects
    try:
        from backend.memory_sqlite import list_tracked_projects
        projects = list_tracked_projects()
        q_lower = q.lower()
        for p in projects:
            name = p.get("name", "")
            purpose = p.get("purpose", "")
            if q_lower in name.lower() or q_lower in purpose.lower():
                results.append({
                    "type": "project",
                    "id": p.get("project_id"),
                    "title": f"Project: {name}",
                    "subtitle": purpose[:120] + "..." if purpose else "No description",
                    "path": p.get("path"),
                    "score": 0.85
                })
    except Exception as e:
        logger.warning(f"Global search projects failed: {e}")
        
    # 3. Search facts (memories)
    try:
        from backend.memory_sqlite import search_facts
        facts = search_facts(q, limit=5)
        for f in facts:
            results.append({
                "type": "memory",
                "id": f.get("id"),
                "title": "Fact Memory",
                "subtitle": f.get("fact"),
                "score": f.get("score", 0.7),
                "timestamp": f.get("timestamp")
            })
    except Exception as e:
        logger.warning(f"Global search facts failed: {e}")
        
    # 4. Search tasks
    try:
        from core.autonomous_agent.task_planner import TaskPlanner
        planner = TaskPlanner()
        tasks = planner.list_tasks()
        q_lower = q.lower()
        for t in tasks:
            desc = t.get("description", "")
            if q_lower in desc.lower():
                results.append({
                    "type": "task",
                    "id": t.get("task_id"),
                    "title": f"Task: {desc[:50]}...",
                    "subtitle": f"Status: {t.get('status', 'pending')}",
                    "score": 0.8
                })
    except Exception as e:
        logger.warning(f"Global search tasks failed: {e}")
        
    # Sort results by score descending
    results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return {"status": "ok", "results": results}


# /tools/health extracted to routes/admin.py


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

@app.get("/research/status")
async def get_research_status():
    """Polled by UI to fetch live deep research progress log messages."""
    from backend.deep_research import ACTIVE_RESEARCH
    return ACTIVE_RESEARCH

# === PROJECTS API ===
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
@app.get("/memory/list")
async def list_memories():
    from backend.memory_sqlite import get_all_facts
    try:
        facts = get_all_facts()
        return {"status": "ok", "facts": facts}
    except Exception as e:
        logger.error(f"Failed to load memories: {e}")
        return {"status": "error", "facts": []}

class AddMemoryRequest(BaseModel):
    fact: str
    importance: int = 5

@app.post("/memory/add")
async def add_memory_endpoint(req: AddMemoryRequest):
    from backend.memory_sqlite import add_fact
    try:
        ok = add_fact(req.fact, req.importance)
        if ok:
            return {"status": "ok", "message": "Fact added to memory banks."}
        else:
            raise HTTPException(status_code=500, detail="Failed to add fact.")
    except Exception as e:
        logger.error(f"Failed to add memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class DeleteMemoryRequest(BaseModel):
    fact: str

@app.post("/memory/delete")
async def delete_memory_endpoint(req: DeleteMemoryRequest):
    from backend.memory_sqlite import remove_fact
    try:
        ok = remove_fact(req.fact)
        if ok:
            return {"status": "ok", "message": "Fact removed from memory banks."}
        else:
            raise HTTPException(status_code=500, detail="Fact not found or could not be deleted.")
    except Exception as e:
        logger.error(f"Failed to delete memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === MEETINGS API ===
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

def evaluate_math_locally(text: str) -> Optional[str]:
    """Deterministically detects and evaluates simple arithmetic math queries locally.
    Supports basic operations: +, -, *, /, %, ^, **, parentheses, and numbers.
    """
    cleaned = text.lower().strip()
    # Remove common prefix phrases
    cleaned = re.sub(
        r'^(?:void\s*,\s*|void\s+)?(?:what\s+is\s+the\s+value\s+of\s+|what\s+is\s+|what\'s\s+|calculate\s+|solve\s+|compute\s+)',
        '',
        cleaned
    )
    # Remove common suffix phrases/punctuation
    cleaned = re.sub(r'\s*(?:\?|please|sir)?$', '', cleaned).strip()
    
    # We must ensure it's not empty, and only contains arithmetic characters
    if not cleaned or not re.match(r'^[0-9\+\-\*\/\%\^\(\)\.\s]+$', cleaned):
        return None
        
    # Extra check: require at least one digit and one operator to avoid treating plain numbers as math
    if not any(c.isdigit() for c in cleaned) or not any(c in '+-*/%^()' for c in cleaned):
        return None
        
    try:
        expr = cleaned.replace('^', '**')
        # Evaluate safely without builtins
        val = eval(expr, {"__builtins__": {}}, {})
        if isinstance(val, float) and val.is_integer():
            val = int(val)
        return f"The calculation result is {val}, Sir."
    except Exception:
        return None


def humanize_tool_output_locally(action: str, params: Dict[str, Any], output: str, is_success: bool) -> str:
    """Provides natural cybernetic persona replies for direct tool execution outputs."""
    if not is_success:
        return f"⚠️ I encountered an issue executing {action.replace('_', ' ')}, Sir. Details: {output}"
        
    if action == "time":
        return f"The current time is {output}, Sir."
    elif action == "system_info":
        return f"Here is the system status, Sir:\n{output}"
    elif action == "open_app":
        app = params.get("app", "the application")
        return f"I have launched {app} for you, Sir."
    elif action == "close_app":
        app = params.get("app", "the application")
        return f"I have closed {app}, Sir."
    elif action == "open_url":
        url = params.get("url", "the URL")
        return f"I have opened the link {url} in your browser, Sir."
    elif action == "open_folder":
        path = params.get("path", "the folder or file")
        return f"I have opened the requested location: {path}, Sir."
    elif action == "screenshot":
        return "I have successfully captured a screenshot for you, Sir."
    elif action == "lock_computer":
        return "System workstation locked successfully, Sir."
    elif action == "press_key":
        key = params.get("key", "key")
        return f"Pressed key '{key}', Sir."
    elif action == "cvcs_type":
        return "Successfully typed the requested text, Sir."
    elif action == "mouse_control":
        act = params.get("action", "action")
        return f"Mouse {act} operation completed, Sir."
    elif action == "check_file_exists":
        return output
    elif action == "list_directory":
        return f"Here are the directory contents, Sir:\n{output}"
    elif action == "create_folder":
        return f"I have created the folder for you, Sir. Details: {output}"
    elif action == "file_manager":
        if params.get("content"):
            return "I have successfully written to the file, Sir."
        else:
            return f"Here is the file content, Sir:\n```\n{output}\n```"
            
    return f"Action {action} executed successfully, Sir. Result: {output}"


def log_chat_request(intent_detected: str, execution_path: str, tool_used: str, status: str, start_time: float, confidence: float = 1.0, endpoint: str = "None"):
    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    
    # Map parameters to requested fields
    detected_intent = intent_detected
    selected_tool = tool_used if tool_used != "None" else "None"
    confidence_score = f"{confidence:.2f}"
    endpoint_called = endpoint
    response_status = status
    execution_time = f"{elapsed_ms}ms"
    
    logger.info(
        f"\n[STRUCTURED LOG]\n"
        f"- Detected intent: {detected_intent}\n"
        f"- Selected tool: {selected_tool}\n"
        f"- Confidence score: {confidence_score}\n"
        f"- Endpoint called: {endpoint_called}\n"
        f"- Response status: {response_status}\n"
        f"- Execution time: {execution_time}\n"
    )


DIRECT_TOOLS = {
    "time", "system_info", "open_app", "close_app", "open_url", "open_folder",
    "screenshot", "lock_computer", "press_key", "mouse_control", 
    "check_file_exists", "list_directory", "create_folder", "cvcs_type",
    "file_manager"
}


@app.post("/chat")
async def chat(req: ChatRequest, background_tasks: BackgroundTasks = None):
    start_time = time.perf_counter()
    STATS["messages"] += 1
    text = (req.message or req.text or "").strip()
    if not text:
        log_chat_request("empty", "DIRECT_TOOL", "None", "Success", start_time)
        return {"reply": "?", "meta": {"intent": "empty"}}
        
    # Zero-latency greetings/identity intercept check
    norm_text = clean_intercept_text(text)
    intercept_reply = GREETINGS_INTERCEPTS.get(norm_text)
    
    if not intercept_reply:
        if norm_text in ["hello", "hi", "hey", "greetings", "yo"]:
            intercept_reply = GREETINGS_INTERCEPTS["hello"]
        elif norm_text in ["who are you", "whats your name"]:
            intercept_reply = GREETINGS_INTERCEPTS["who are you"]
        elif norm_text in ["who created you", "who is your creator", "who made you"]:
            intercept_reply = GREETINGS_INTERCEPTS["who created you"]

    if intercept_reply:
        def run_background_logging():
            try:
                from core.analytics.productivity_tracker import ProductivityTracker
                tracker = ProductivityTracker()
                tracker.log_event("chat", {"message_preview": text[:50]})
            except Exception as e:
                logger.error(f"Failed to log chat event in analytics: {e}")
            try:
                from backend import memory_sqlite
                memory_sqlite.add_xp(5)
            except Exception as e:
                logger.error(f"Failed to award XP for chat: {e}")
            try:
                memory = _get_memory()
                memory.remember_turn("user", text)
                memory.remember_turn("void", intercept_reply)
            except Exception as e:
                logger.error(f"Failed to record greeting in memory: {e}")
                
        if background_tasks:
            background_tasks.add_task(run_background_logging)
        else:
            asyncio.create_task(asyncio.to_thread(run_background_logging))
            
        log_chat_request("intercept", "DIRECT_TOOL", "None", "Success", start_time)
        return {"reply": intercept_reply, "meta": {"intent": "intercept", "latency_ms": 0}}

    try:
        from core.analytics.productivity_tracker import ProductivityTracker
        tracker = ProductivityTracker()
        tracker.log_event("chat", {"message_preview": text[:50]})
    except Exception as e:
        logger.error(f"Failed to log chat event in analytics: {e}")
    try:
        from backend import memory_sqlite
        memory_sqlite.add_xp(5)
    except Exception as e:
        logger.error(f"Failed to award XP for chat: {e}")
    
    memory = _get_memory()
    
    # -------------------------------------------------------------
    # ROUTING & HALLUCINATION ELIMINATION INTERCEPTS
    # -------------------------------------------------------------
    lower_text = text.lower().strip()
    
    # Autonomous Task Planner Intercept
    is_complex_workflow = (
        (("open vs code" in lower_text or "vscode" in lower_text) and
         ("scan" in lower_text or "explain" in lower_text or "test" in lower_text or "todo" in lower_text))
        or "task graph" in lower_text or "autonomous task" in lower_text or "execute workflow" in lower_text
    )
    
    if is_complex_workflow:
        from core.autonomous_agent.task_planner import TaskPlanner
        planner = TaskPlanner()
        root_task = planner.create_task_graph(text)
        
        async def run_task_graph():
            tm = VoidSingletons.get("tool_manager")
            await planner.execute_task_graph(root_task.id, tm)
            
        if background_tasks:
            background_tasks.add_task(run_task_graph)
        else:
            asyncio.create_task(run_task_graph())
            
        reply = (
            f"🤖 **Autonomous Task Planner Activated**, Sir!\n\n"
            f"I have initialized a task graph with ID `{root_task.id}` to accomplish your goal:\n"
            f"*\"{text}\"*\n\n"
            f"**Plan Details**:\n"
            f"1. Open Visual Studio Code\n"
            f"2. Register VOID Project Path\n"
            f"3. Scan codebase structure\n"
            f"4. Summarize architecture\n"
            f"5. Identify high-priority TODOs\n"
            f"6. Run the test suite\n\n"
            f"I am executing this workflow. You can monitor the live execution steps, progress, and logs in the **Tasks** console, Sir."
        )
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("task_planning", "DIRECT_TOOL", "TaskPlanner", "Success", start_time, confidence=1.0, endpoint="TaskPlanner.create_task_graph")
        return {"reply": reply, "meta": {"intent": "task_planning", "action": "execute", "task_id": root_task.id}}

    # Project Scanner Force Rules
    is_scan_project = any(p in lower_text for p in ["scan my current project", "scan my project", "scan project", "scan current project"])
    is_explain_project = any(p in lower_text for p in ["explain my project architecture", "explain project architecture", "explain codebase architecture", "explain my codebase architecture", "explain codebase"])
    
    if is_scan_project or is_explain_project:
        from core.autonomous_agent import AutonomousAgent
        from pathlib import Path
        root = Path(__file__).parent.parent
        agent = AutonomousAgent(str(root))
        
        if is_scan_project:
            res = await agent.scan_and_map()
            reply = f"🔍 **Project Scan Complete**, Sir!\n- **Technology Stack**: {', '.join(res.get('frameworks', [])) or 'None detected'}\n- **Entry Points**: {', '.join(res.get('entry_points', [])) or 'None detected'}\n- **Files Scanned**: {len(res.get('files', []))}"
            action_name = "agent_scan"
        else:
            reply = await agent.explain_architecture()
            action_name = "agent_explain"
            
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request(action_name, "DIRECT_TOOL", "AutonomousAgent", "Success", start_time, confidence=1.0, endpoint="AutonomousAgent.scan_and_map" if is_scan_project else "AutonomousAgent.explain_architecture")
        return {"reply": reply, "meta": {"intent": "command", "action": action_name}}
        
    # Memory Writes/Deletes
    is_remember = any(lower_text.startswith(prefix) for prefix in ["remember", "store", "save this"]) or "remember" in lower_text or "save this" in lower_text
    is_forget = lower_text.startswith("forget") or "forget that" in lower_text
    
    if is_remember:
        fact_text = text
        for prefix in [
            "please remember that my", "please remember that", "please remember my", "please remember",
            "remember that my", "remember that", "remember my", "remember",
            "store that my", "store that", "store my", "store",
            "save this that my", "save this that", "save this my", "save this", "save my"
        ]:
            if fact_text.lower().startswith(prefix):
                fact_text = fact_text[len(prefix):].strip()
                break
        
        fact_text_clean = fact_text.strip()
        if fact_text_clean.lower().startswith("that "):
            fact_text_clean = fact_text_clean[5:].strip()
        elif fact_text_clean.lower().startswith("to "):
            fact_text_clean = fact_text_clean[3:].strip()
            
        if fact_text_clean.endswith("."):
            fact_text_clean = fact_text_clean[:-1].strip()
            
        memory.add_fact(fact_text_clean)
        reply = f"I have stored that in memory, Sir: {fact_text_clean}"
        
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("memory_write", "DIRECT_TOOL", "SQLite", "Success", start_time, confidence=1.0, endpoint="memory_sqlite.add_fact")
        return {"reply": reply, "meta": {"intent": "memory", "action": "remember"}}
        
    if is_forget:
        forget_text = text
        for prefix in ["forget that my", "forget that", "forget my", "forget"]:
            if forget_text.lower().startswith(prefix):
                forget_text = forget_text[len(prefix):].strip()
                break
        
        forget_text_clean = forget_text.strip()
        if forget_text_clean.endswith("."):
            forget_text_clean = forget_text_clean[:-1].strip()
            
        all_facts = memory.list_facts()
        found_any = False
        for fact in all_facts:
            if forget_text_clean.lower() in fact.lower() or fact.lower() in forget_text_clean.lower():
                from backend.memory_manager import forget_fact
                forget_fact(fact)
                found_any = True
                
        if found_any:
            reply = f"I have removed that from memory, Sir: {forget_text_clean}"
            status = "Success"
        else:
            reply = f"I couldn't find a matching memory for '{forget_text_clean}', Sir."
            status = "Failure"
            
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("memory_delete", "DIRECT_TOOL", "SQLite", status, start_time, confidence=1.0, endpoint="memory_sqlite.forget_fact")
        return {"reply": reply, "meta": {"intent": "memory", "action": "forget"}}

    # -------------------------------------------------------------
    # AUDIO MEMORY RAG INTERCEPT (Phase 3)
    # -------------------------------------------------------------
    audio_memory_keywords = [
        "what happened while", "what did we discuss", "conversations happened", "was discussed this",
        "what tasks did i receive", "what were people talking about", "explain yesterday's", "explain yesterday",
        "when did someone mention", "summarize all conversations", "i didn't understand what they explained",
        "summarize our conversation", "what was said", "did anyone mention", "what did they say",
        "summarize what was discussed", "explain what they said", "any missed conversation", "what was discussed"
    ]
    is_audio_memory_query = any(kw in lower_text for kw in audio_memory_keywords) or (
        ("conversation" in lower_text or "discussion" in lower_text or "recording" in lower_text or "they said" in lower_text or "we talked" in lower_text)
        and any(w in lower_text for w in ["what", "who", "when", "summarize", "explain", "recall", "yesterday", "today", "week", "recent"])
    )
    
    if is_audio_memory_query:
        try:
            from backend.memory_sqlite import semantic_search_recordings, get_audio_recordings
            
            # Use semantic search as the primary retriever
            recordings = semantic_search_recordings(text, limit=3)
            
            # If the user is asking about a specific timeframe (e.g. today, yesterday), 
            # let's also fetch recent recordings by date to ensure we don't miss anything.
            recent_recs = []
            if "today" in lower_text or "this morning" in lower_text or "just now" in lower_text:
                recent_recs = get_audio_recordings(limit=5)
            elif "yesterday" in lower_text:
                from datetime import datetime, timedelta
                yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                all_recent = get_audio_recordings(limit=20)
                recent_recs = [r for r in all_recent if yesterday_str in r["timestamp"]]
                
            # Merge and de-duplicate
            seen_ids = {r["id"] for r in recordings}
            for r in recent_recs:
                if r["id"] not in seen_ids:
                    recordings.append(r)
                    seen_ids.add(r["id"])
                    
            if not recordings:
                reply = "I couldn't find any recorded conversations in my memory, Sir. Please make sure background recording is enabled and active."
            else:
                formatted_convs = []
                for idx, r in enumerate(recordings):
                    timestamp = r.get("timestamp", "Unknown time")
                    transcript = r.get("transcript", "")
                    summary = r.get("summary", "")
                    formatted_convs.append(
                        f"Conversation #{idx+1} (Date/Time: {timestamp})\n"
                        f"- Summary: {summary}\n"
                        f"- Transcript: {transcript}\n"
                    )
                formatted_conversations = "\n\n".join(formatted_convs)
                
                prompt = f"""
You are VOID, the highly advanced AI desktop assistant. The user is asking a question about their past conversations or background audio.
Answer the user's question accurately, clearly, and concisely, using only the provided conversation logs.

Retrieved Conversation Logs:
{formatted_conversations}

User Question:
{text}

Guidelines:
- Ground your answer strictly in the provided logs.
- If the logs do not contain the answer, say: "I couldn't find any mention of that in my recorded conversations, Sir."
- Avoid making up or inventing any details.
- Speak naturally and in a premium, helpful assistant tone (use "Sir", keep it professional but advanced).
"""
                from backend.llm_client import OllamaClient
                llm = VoidSingletons.get("llm") or OllamaClient()
                
                reply = await llm.router.chat(
                    history=[],
                    prompt=prompt,
                    system_prompt="You are VOID, an advanced AI assistant. You answer questions based on the provided conversation logs. Speak naturally like a human assistant."
                )
                
            memory.remember_turn("user", text)
            memory.remember_turn("void", reply)
            log_chat_request("memory_recall", "DIRECT_TOOL", "SQLite", "Success", start_time, confidence=1.0, endpoint="memory_sqlite.semantic_search_recordings")
            return {"reply": reply, "meta": {"intent": "memory_recall", "recordings_found": len(recordings)}}
        except Exception as e:
            logger.error(f"Error in audio memory RAG recall: {e}")
            reply = f"I encountered an error trying to search my conversation memory, Sir. Details: {e}"
            memory.remember_turn("user", text)
            memory.remember_turn("void", reply)
            return {"reply": reply, "meta": {"intent": "memory_recall", "error": str(e)}}
        
    # Memory Reads
    is_show_memory = "show memory database" in lower_text or lower_text in ["show memory", "show memory database", "show memory database."]
    is_deadline_query = "deadline" in lower_text or "my deadline" in lower_text
    
    if is_show_memory:
        facts = memory.list_facts()
        if not facts:
            reply = "Memory database is empty, Sir."
        else:
            facts_list = "\n".join([f"- {fact}" for fact in facts])
            reply = f"Here is the contents of the memory database, Sir:\n{facts_list}"
            
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("memory_read", "DIRECT_TOOL", "SQLite", "Success", start_time, confidence=1.0, endpoint="memory_sqlite.get_all_facts")
        return {"reply": reply, "meta": {"intent": "memory", "action": "show"}}
        
    if is_deadline_query:
        facts = memory.query_relevant(text, limit=3)
        if facts:
            reply = f"According to your memory database, Sir: {facts[0]}."
            status = "Success"
        else:
            reply = "I couldn't find any deadline in my memory database, Sir."
            status = "Failure"
            
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("memory_read", "DIRECT_TOOL", "SQLite", status, start_time, confidence=1.0, endpoint="memory_sqlite.query_semantic_facts")
        return {"reply": reply, "meta": {"intent": "memory", "action": "recall"}}
        
    # Telemetry and Diagnostics
    telemetry_keywords = [
        "system status", "current system status", "cpu", "ram", "storage",
        "battery", "temperature", "performance", "diagnostics", "computer health",
        "system info", "system stats", "computer stats", "pc health", "pc status"
    ]
    is_telemetry_query = any(kw in lower_text for kw in telemetry_keywords)
    
    if is_telemetry_query:
        stats_data = stats_collector.get_all_stats()
        cpu = stats_data.get("cpu_usage", 0)
        ram = stats_data.get("ram_usage", 0)
        ram_used = stats_data.get("ram_used_gb", 0)
        ram_total = stats_data.get("ram_total_gb", 0)
        storage_used = stats_data.get("storage_used_gb", 0)
        storage_total = stats_data.get("storage_total_gb", 0)
        battery = stats_data.get("battery_percent", "N/A")
        battery_plugged = "plugged in" if stats_data.get("battery_power_plugged") else "discharging"
        cpu_temp = stats_data.get("cpu_temp")
        temp_str = f", CPU Temp: {cpu_temp}°C" if cpu_temp else ""
        
        if any(w in lower_text for w in ["health", "diagnostics", "analyze", "check"]):
            cpu_status = "Healthy" if cpu < 80 else "High Load ⚠️"
            ram_status = "Healthy" if ram < 85 else "High Load ⚠️"
            storage_pct = (storage_used / (storage_total or 1)) * 100
            storage_status = "Healthy" if storage_pct < 90 else "Low Space ⚠️"
            
            reply = (
                f"📊 **Computer Health & Diagnostics Check**, Sir:\n"
                f"- **Overall Health**: Operational\n"
                f"- **CPU Status**: {cpu_status} (Currently at {cpu}%)\n"
                f"- **RAM Status**: {ram_status} ({ram}% used)\n"
                f"- **Storage Status**: {storage_status} ({storage_used} GB / {storage_total} GB)\n"
                f"- **Battery Level**: {battery}% ({battery_plugged})\n"
                f"- **Action Recommendation**: System diagnostics indicate operational stability."
            )
            intent_name = "diagnostics"
        else:
            reply = (
                f"🖥️ **System Telemetry & Health Report**, Sir:\n"
                f"- **CPU Usage**: {cpu}%{temp_str}\n"
                f"- **RAM Usage**: {ram}% ({ram_used} GB / {ram_total} GB)\n"
                f"- **Storage**: {storage_used} GB used / {storage_total} GB total\n"
                f"- **Battery**: {battery}% ({battery_plugged})"
            )
            intent_name = "system_status"
            
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request(intent_name, "DIRECT_TOOL", "SystemStats", "Success", start_time, confidence=1.0, endpoint="GET /stats")
        return {"reply": reply, "meta": {"intent": "system", "action": "stats"}}
        
    # Local Model discovery
    model_keywords = [
        "installed models", "ollama", "available models", "active model",
        "coding model", "vision model", "local ai models", "installed ai models",
        "list installed models", "list models"
    ]
    is_model_query = any(kw in lower_text for kw in model_keywords)
    
    if is_model_query:
        llm = VoidSingletons.get("llm") or OllamaClient()
        discovered = {"Coding": [], "Reasoning": [], "Planning": [], "Vision": [], "Chat": [], "Lightweight": [], "Large": []}
        if llm and hasattr(llm, "router") and hasattr(llm.router, "ollama_provider"):
            discovered = llm.router.ollama_provider.discover_and_categorize_models()
        
        active_model = "None"
        routing_mode = "AUTO"
        if llm and hasattr(llm, "router"):
            cfg = getattr(llm.router, "config", {})
            active_model = cfg.get("local_model", "qwen2.5:0.5b")
            routing_mode = cfg.get("routing_mode", "AUTO")
            
        all_models = []
        for cat, list_models in discovered.items():
            if list_models:
                all_models.extend(list_models)
                
        if not all_models:
            reply = (
                f"🤖 **Local AI Models Configuration**, Sir:\n"
                f"- **Active Local Model**: `{active_model}`\n"
                f"- **Routing Mode**: `{routing_mode}`\n"
                f"- **Discovered Models**: No local Ollama models detected. Please ensure the Ollama service is active and models are downloaded."
            )
        else:
            formatted_models = ", ".join([f"`{m}`" for m in all_models])
            reply = (
                f"🤖 **Local AI Models Configuration**, Sir:\n"
                f"- **Active Local Model**: `{active_model}`\n"
                f"- **Routing Mode**: `{routing_mode}`\n"
                f"- **Installed Models**: {formatted_models}"
            )
            
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("model_discovery", "DIRECT_TOOL", "OllamaProvider", "Success", start_time, confidence=1.0, endpoint="GET /api/llm/discovered-models")
        return {"reply": reply, "meta": {"intent": "system", "action": "discovered-models"}}
        
    # TODOs/Action Items
    is_todo_query = lower_text in ["show all todos", "show all todos.", "list todos", "what are my todos", "show todos"] or "todos" in lower_text or "todo" in lower_text
    
    if is_todo_query:
        from tools.meeting_assistant import get_action_items
        res = get_action_items()
        action_items = res.get("action_items", [])
        if not action_items:
            reply = "There are no pending action items or TODOs in my database, Sir."
        else:
            formatted = []
            for item in action_items:
                owner_str = f" (Assigned to: {item['owner']})" if item.get('owner') else ""
                deadline_str = f" [Due: {item['deadline']}]" if item.get('deadline') else ""
                formatted.append(f"- {item.get('description', 'Task')}{owner_str}{deadline_str}")
            reply = "Here are your pending action items and TODOs, Sir:\n" + "\n".join(formatted)
            
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("get_action_items", "DIRECT_TOOL", "MeetingAssistant", "Success", start_time, confidence=1.0, endpoint="tools.meeting_assistant.get_action_items")
        return {"reply": reply, "meta": {"intent": "command", "action": "get_action_items"}}
        
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
            llm = VoidSingletons.get("llm") or OllamaClient()
            logs = "\n".join(workflow_res.get("logs", []))
            is_ok = workflow_res.get("ok", True)
            reply = await llm.summarize_tool_output(text, "workflow", f"OK={is_ok}, Steps: {logs}", is_success=is_ok)
            
            memory.remember_turn("user", text)
            memory.remember_turn("void", reply)
            log_chat_request("workflow", "LLM_REQUIRED", "workflow_engine", "Success" if is_ok else "Failure", start_time)
            return {"reply": reply, "meta": {"intent": "workflow", "result": workflow_res}}
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            from tools.error_interpreter import interpret_error
            friendly_err = interpret_error(str(e))
            reply = f"⚠️ Workflow execution failed, Sir. {friendly_err}"
            memory.remember_turn("user", text)
            memory.remember_turn("void", reply)
            log_chat_request("workflow", "LLM_REQUIRED", "workflow_engine", "Failure", start_time)
            return {"reply": reply, "meta": {"intent": "workflow", "error": str(e)}}
    
    # Handle explicit memory commands
    if text.lower() == "show memory":
        reply = memory.get_summary()
        log_chat_request("show_memory", "DIRECT_TOOL", "None", "Success", start_time)
        return {"reply": reply, "meta": {"intent": "system"}}
    if text.lower() == "clear memory":
        memory.clear()
        log_chat_request("clear_memory", "DIRECT_TOOL", "None", "Success", start_time)
        return {"reply": "Memory banks have been purged, Sir.", "meta": {"intent": "system"}}

    # Deterministic Developer Mode & Self-Modification Intercepts
    norm_text_lower = text.lower().strip()
    
    if norm_text_lower in ["enter developer mode", "enable developer mode", "developer mode on"]:
        from core.brain import enable_developer_mode
        enable_developer_mode()
        reply = "🔓 **Developer Mode Enabled**, Sir. Write access, self-repairs, and system self-modifications are now fully unlocked. I am standing by for engineering commands."
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("enable_developer_mode", "DIRECT_TOOL", "None", "Success", start_time)
        return {"reply": reply, "meta": {"intent": "system"}}
        
    if norm_text_lower in ["exit developer mode", "disable developer mode", "developer mode off", "exit dev mode"]:
        from core.brain import disable_developer_mode
        disable_developer_mode()
        reply = "🔒 **Developer Mode Disabled**, Sir. System write access is locked. Operating in read-only safe mode."
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("disable_developer_mode", "DIRECT_TOOL", "None", "Success", start_time)
        return {"reply": reply, "meta": {"intent": "system"}}
        
    if norm_text_lower in ["show developer mode", "developer mode status", "is developer mode enabled"]:
        from core.brain import is_developer_mode
        status_str = "🔓 ENABLED (Write/Modify Unlocked)" if is_developer_mode() else "🔒 DISABLED (Read-Only Safe Mode)"
        reply = f"🤖 **Developer Mode Status**: {status_str}, Sir."
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("developer_mode_status", "DIRECT_TOOL", "None", "Success", start_time)
        return {"reply": reply, "meta": {"intent": "system"}}

    if norm_text_lower == "repair yourself" or norm_text_lower == "run self repair":
        from core.brain import is_developer_mode
        if not is_developer_mode():
            reply = "🔒 **Action Denied**: Developer mode is currently disabled, Sir. Please say *\"enter developer mode\"* to enable self-repair access."
            memory.remember_turn("user", text)
            memory.remember_turn("void", reply)
            log_chat_request("repair_yourself", "DIRECT_TOOL", "None", "Failure", start_time)
            return {"reply": reply, "meta": {"intent": "system"}}
            
        from tools.self_modifier import self_repair_workflow
        res = await asyncio.to_thread(self_repair_workflow)
        actions_taken_list = [a.get("action", str(a)) if isinstance(a, dict) else str(a) for a in res.get('actions_taken', [])]
        reply = f"🔧 **Self-Repair Execution Complete**, Sir!\n\n**Action Status**: {res.get('status').upper()}\n- **Actions Taken**: {', '.join(actions_taken_list) or 'None'}\n- **Message**: {res.get('message')}"
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("repair_yourself", "DIRECT_TOOL", "self_repair", "Success" if res.get('status') == 'ok' else "Failure", start_time)
        return {"reply": reply, "meta": {"intent": "system", "result": res}}

    if norm_text_lower.startswith("rewrite module ") or norm_text_lower.startswith("improve module "):
        from core.brain import is_developer_mode
        if not is_developer_mode():
            reply = "🔒 **Action Denied**: Developer mode is currently disabled, Sir. Please say *\"enter developer mode\"* to enable rewrite and file edit capabilities."
            memory.remember_turn("user", text)
            memory.remember_turn("void", reply)
            log_chat_request("rewrite_module", "DIRECT_TOOL", "None", "Failure", start_time)
            return {"reply": reply, "meta": {"intent": "system"}}
            
        cmd_words = "rewrite module " if norm_text_lower.startswith("rewrite module ") else "improve module "
        module_clause = text[len(cmd_words):].strip()
        
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
        log_chat_request("rewrite_module", "LLM_REQUIRED", "self_modifier", "Success" if res.get('status') == 'ok' else "Failure", start_time)
        return {"reply": reply, "meta": {"intent": "system", "result": res}}



    # Local Math Intercept
    math_reply = evaluate_math_locally(text)
    if math_reply is not None:
        memory.remember_turn("user", text)
        memory.remember_turn("void", math_reply)
        log_chat_request("math_calculation", "DIRECT_TOOL", "math_evaluator", "Success", start_time)
        return {"reply": math_reply, "meta": {"intent": "command", "action": "math_evaluator"}}

    history = memory.short_term[-10:]
    
    # Get singletons
    llm = VoidSingletons.get("llm") or OllamaClient()
    router = VoidSingletons.get("router")
    
    # Auto-learn user facts
    try:
        from backend.memory_manager import extract_and_remember
        extract_and_remember(text)
    except Exception as e:
        logger.error(f"Failed to auto-extract facts: {e}")
        
    orig_prompt = llm.system_prompt
    try:
        intent = None
        try:
            if router:
                intent = await router.classify(text)
        except Exception as e:
            logger.error(f"Intent classification failed: {e}. Falling back to pure chat mode.")
            
        try:
            from backend.emotion_engine import EmotionEngine
            engine = EmotionEngine()
            engine.process_turn(text)
            
            modifier = EmotionEngine.get_system_prompt_modifier()
            if modifier:
                llm.system_prompt = orig_prompt + modifier
            else:
                llm.system_prompt = orig_prompt

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
            log_chat_request(intent.action, "LLM_REQUIRED", "agent_assistant", "Success", start_time)
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
            if (not new_motd or "message of the day" in new_motd.lower() or "motd" in new_motd.lower() or 
                    new_motd.lower() in ["on the pannel", "on the panel", "pannel", "panel", "to the panel"]):
                prompt = (
                    "Generate a single short, extremely cool, motivating cyberpunk-style 'Message of the Day' "
                    "for a software engineer's desktop panel (max 10 words). speak naturally, do NOT include quotes, "
                    "do NOT explain, and keep it punchy and related to coding/focus."
                )
                generated = await asyncio.wait_for(llm.chat([], prompt), timeout=150.0)
                new_motd = generated.strip().strip('"').strip("'")
            
            global MOTD
            MOTD = new_motd
            final_reply = f"Understood, Sir. I have updated the panel's Message of the Day to: \"{new_motd}\""
            
        elif intent and (intent.intent == "command" or (intent.intent == "system" and intent.action in ["repair", "diagnostics"])):
            action_name = "repair_self" if intent.action == "repair" else intent.action
            if action_name in DIRECT_TOOLS:
                # Bypasses Ollama completely
                try:
                    tm = VoidSingletons.get("tool_manager")
                    result = await tm.execute(action_name, intent.params)
                    is_success = result.meta.get("status") != "FAIL"
                    final_reply = humanize_tool_output_locally(action_name, intent.params, result.output, is_success)
                    
                    memory.remember_turn("user", text)
                    memory.remember_turn("void", final_reply)
                    log_chat_request(intent.action, "DIRECT_TOOL", action_name, "Success" if is_success else "Failure", start_time)
                    return {"reply": final_reply, "meta": {"intent": intent.intent, "action": intent.action}}
                except Exception as tool_err:
                    logger.error(f"Direct tool execution failed: {tool_err}")
                    from tools.error_interpreter import interpret_error
                    friendly_err = interpret_error(str(tool_err))
                    final_reply = f"⚠️ Tool execution failed, Sir. {friendly_err}"
                    
                    memory.remember_turn("user", text)
                    memory.remember_turn("void", final_reply)
                    log_chat_request(intent.action, "DIRECT_TOOL", action_name, "Failure", start_time)
                    return {
                        "reply": final_reply,
                        "meta": {
                            "intent": intent.intent,
                            "action": intent.action,
                            "status": "error",
                            "error": str(tool_err),
                            "severity": "high"
                        }
                    }
            else:
                # LLM required to summarize tool output
                try:
                    tm = VoidSingletons.get("tool_manager")
                    result = await tm.execute(action_name, intent.params)
                    is_success = result.meta.get("status") != "FAIL"
                    
                    final_reply = await asyncio.wait_for(
                        llm.summarize_tool_output(text, action_name, result.output, is_success=is_success),
                        timeout=150.0
                    )
                    
                    memory.remember_turn("user", text)
                    memory.remember_turn("void", final_reply)
                    log_chat_request(intent.action, "LLM_REQUIRED", action_name, "Success" if is_success else "Failure", start_time)
                    return {"reply": final_reply, "meta": {"intent": intent.intent, "action": intent.action}}
                except asyncio.TimeoutError as time_err:
                    logger.error("LLM tool summarization timed out.")
                    from tools.error_interpreter import translate_exception
                    translated = translate_exception(time_err)
                    final_reply = f"⚠️ Action completed but LLM response timed out, Sir. Raw: {result.output[:100]}..."
                    log_chat_request(intent.action, "LLM_REQUIRED", action_name, "Failure", start_time)
                    return {
                        "reply": final_reply,
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
                    final_reply = f"⚠️ Tool execution failed, Sir. {friendly_err}"
                    log_chat_request(intent.action, "LLM_REQUIRED", action_name, "Failure", start_time)
                    return {
                        "reply": final_reply,
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
            # --- Ollama readiness pre-check ---
            try:
                ollama_up = await asyncio.wait_for(is_ollama_ready(), timeout=2.0)
                if not ollama_up:
                    logger.warning("[CHAT] Ollama not reachable — attempting auto-restart")
                    await asyncio.wait_for(ensure_ollama(), timeout=25.0)
                    ollama_up = await is_ollama_ready()
                if not ollama_up:
                    reply = "Ollama service is offline, Sir. I've attempted to restart it — please try again in a few seconds."
                    memory.remember_turn("user", text)
                    memory.remember_turn("void", reply)
                    log_chat_request(intent_name, "LLM_REQUIRED", "None", "Failure", start_time)
                    return {"reply": reply, "meta": {"intent": intent_name, "status": "error", "error": "OllamaOffline"}}
            except asyncio.TimeoutError:
                logger.error("[CHAT] Ollama readiness check timed out")
            # ----------------------------------
            try:
                final_reply = await asyncio.wait_for(
                    llm.chat(history, text),
                    timeout=150.0
                )
            except asyncio.TimeoutError as time_err:
                logger.error("LLM chat timed out.")
                from tools.error_interpreter import translate_exception
                translated = translate_exception(time_err)
                final_reply = "⚠️ Ollama is taking too long to generate a response, Sir. Please check if the service is loaded and running."
                log_chat_request(intent_name, "LLM_REQUIRED", "None", "Failure", start_time)
                return {
                    "reply": final_reply,
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
        
        # Single memory write (no duplicates) for deep research, academic, etc. fall-throughs
        memory.remember_turn("user", text)
        memory.remember_turn("void", final_reply)
        
        intent_name = intent.intent if intent else "pure_chat"
        action_name = intent.action if intent else None
        log_chat_request(action_name or intent_name, "LLM_REQUIRED", "None", "Success", start_time)
        return {"reply": final_reply, "meta": {"intent": intent_name, "action": action_name}}
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        from tools.error_interpreter import translate_exception
        translated = translate_exception(e)
        intent_name = intent.intent if intent else "pure_chat"
        action_name = intent.action if intent else None
        log_chat_request(action_name or intent_name, "LLM_REQUIRED", "None", "Failure", start_time)
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
