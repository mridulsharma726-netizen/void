import time
import platform
import logging
import sys
import os
import threading
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from server.dependencies import (
    VoidSingletons, APP_START, STATS, PermissionManager, check_all_tools, DATA_DIR, is_ollama_ready
)
from tools.system_stats import SystemStats
from backend.diagnostics import DiagnosticsEngine
from backend.repair_system import RepairSystem
from backend.memory_manager import MemoryManager

logger = logging.getLogger("void.routes.admin")

router = APIRouter()

MOTD = "Stay focused. Build fast. Keep it local."
stats_collector = SystemStats()

@router.get("/health")
async def health():
    """Lightweight health check — no heavy tool scanning."""
    return {
        "status": "ok",
        "backend": "running",
        "uptime": int(time.time() - APP_START)
    }

@router.get("/stats")
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

@router.get("/time")
async def get_time():
    return {"reply": time.strftime("%I:%M %p"), "meta": {"timestamp": time.time()}}

@router.get("/system-info")
async def system_info():
    return {
        "reply": f"System: {platform.system()} {platform.release()}",
        "meta": {"platform": platform.platform()}
    }

@router.get("/tools/health")
async def tools_health():
    """Full tool health."""
    return await check_all_tools()

@router.get("/repair")
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

@router.get("/diagnostics")
async def diagnostics(dep=Depends(PermissionManager.check_admin)):
    """Run full diagnostics."""
    try:
        diag = DiagnosticsEngine()
        report = await diag.run()
        return {"reply": f"Diagnostics complete. Status: {report.get('status', 'Unknown')}", "meta": report}
    except Exception as e:
        logger.error(f"Diagnostics failed: {e}")
        return {"reply": "Diagnostics failed.", "meta": {"error": str(e)}}

@router.post("/restart")
async def restart_server():
    def do_restart():
        time.sleep(0.5)
        os.execv(sys.executable, [sys.executable] + sys.argv)
        
    threading.Thread(target=do_restart, daemon=True).start()
    return {"status": "ok", "message": "Restarting server..."}

@router.get("/system/ping-services")
async def ping_services():
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            res = await client.get("http://127.0.0.1:11434")
            ollama_ok = (res.status_code == 200 or "Ollama" in res.text)
    except Exception:
        pass
        
    search_ok = False
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            res = await client.get("https://www.google.com")
            search_ok = (res.status_code == 200)
    except Exception:
        pass
        
    return {
        "ollama": "connected" if ollama_ok else "offline",
        "google": "connected" if search_ok else "offline"
    }

@router.get("/system/health-details")
async def get_system_health_details():
    ollama_ok = await is_ollama_ready()
    db_ok = False
    try:
        from backend.memory_sqlite import get_all_facts
        get_all_facts()
        db_ok = True
    except:
        pass
        
    voice_ok = False
    try:
        for t in threading.enumerate():
            if t.name == "void_voice_listener" or "voice" in t.name.lower():
                voice_ok = True
                break
    except:
        pass
        
    tool_ok = False
    try:
        tools_res = await check_all_tools()
        if tools_res.get("status") and tools_res.get("status").upper() == "OK":
            tool_ok = True
    except:
        pass
    return {
        "backend": "healthy",
        "ollama": "healthy" if ollama_ok else "failed",
        "database": "healthy" if db_ok else "failed",
        "voice": "healthy" if voice_ok else "failed",
        "tools": "healthy" if tool_ok else "failed"
    }

@router.get("/api/metrics")
async def get_unified_metrics():
    try:
        from backend.metrics_service import metrics_collector
        return metrics_collector.collect_all()
    except Exception as e:
        logger.error(f"Error getting unified metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
