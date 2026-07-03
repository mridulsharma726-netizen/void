import asyncio
import json
import logging
import time
import requests
import sys
import os
import secrets
import subprocess
import platform
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import Request, HTTPException, Depends
from pydantic import BaseModel

# Add project root and server to path
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
if str(ROOT_DIR / "server") not in sys.path:
    sys.path.append(str(ROOT_DIR / "server"))

from backend.intent_router import IntentRouter
from backend.llm_client import OllamaClient
from backend.memory_manager import MemoryManager
from backend.tools_runtime import ToolRuntime
from backend.tool_manager import ToolManager
from backend.validator import ResponseValidator
from core.brain import is_developer_mode

logger = logging.getLogger("void.dependencies")

APP_START = time.time()
DATA_DIR = ROOT_DIR / "memory" / "data"
DATA_DIR.mkdir(exist_ok=True, parents=True)

STATS = {"messages": 0, "tools": 0}

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
        try:
            from backend.llm_client import OllamaClient
            llm = OllamaClient()
            resp = await asyncio.to_thread(requests.get, llm.tags_url, timeout=2)
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                if llm.model not in models and f"{llm.model}:latest" not in models:
                    logger.info(f"Model {llm.model} missing. Attempting to pull...")
                    subprocess.Popen(["ollama", "pull", llm.model], close_fds=True)
        except:
            pass
        return True
    try:
        logger.info("Starting ollama serve...")
        p = await asyncio.to_thread(lambda: subprocess.Popen(
            ["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True
        ))
        for _ in range(15):
            if await is_ollama_ready():
                logger.info("Ollama ready")
                return True
            await asyncio.sleep(1.0)
    except Exception as e:
        logger.error(f"Ollama start failed: {e}")
    return False

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

class PermissionManager:
    """Verifies Guest, User, Developer, and Admin permissions."""
    
    @staticmethod
    def check_user(request: Request):
        return True
        
    @staticmethod
    def check_developer(request: Request):
        if not is_developer_mode():
            raise HTTPException(
                status_code=403,
                detail="Action Denied: Developer Mode is currently disabled."
            )
        return True
        
    @staticmethod
    def check_admin(request: Request):
        if not is_developer_mode():
            raise HTTPException(
                status_code=403,
                detail="Action Denied: Admin actions require Developer Mode."
            )
        return True
