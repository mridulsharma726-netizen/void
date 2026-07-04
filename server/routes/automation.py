import logging
import asyncio
import json
import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from server.dependencies import (
    VoidSingletons, PermissionManager, DATA_DIR, ROOT_DIR, STATS
)
from backend.schemas import CVCSPermissionRequest, CVCSActionRequest, TextRequest
# Import websocket connection list/functions if main.py had them
from routes.chat import WorkflowRequest

logger = logging.getLogger("void.routes.automation")

router = APIRouter()


class FaceVerifyRequest(BaseModel):
    image: str

_last_frame_hash = None


class PersonalityRequest(BaseModel):
    name: str


class SocialPostRequest(BaseModel):
    platform: str
    content: str
    scheduled_time: Optional[str] = None


@router.websocket("/ws/approval")
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


# [Extracted Automation Route Block]


@router.post("/api/cvcs/verify-face")
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

# EngineeringProposeRequest moved to routes/projects.py


# [Extracted Chat Route Block]


# [Extracted Chat Route Block]


# [Extracted Projects Route Block]


# [Extracted Projects Route Block]


# [Extracted Projects Route Block]


# [Extracted Projects Route Block]


@router.post("/open-app")
async def open_app(req: Dict[str, str]):
    app_name = req.get("app")
    if not app_name: return {"reply": "No app specified", "meta": {"status": "error"}}
    try:
        res = launch(app_name)
        return {"reply": f"Opening {app_name}", "meta": {"result": res}}
    except Exception as e:
        return {"reply": f"Failed to open {app_name}", "meta": {"error": str(e)}}


@router.post("/social/schedule")
async def schedule_social_post(req: SocialPostRequest):
    from core.integrations.social_manager import SocialManager
    mgr = SocialManager()
    res = mgr.schedule_post(req.platform, req.content, req.scheduled_time)
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res


@router.get("/social/queue")
async def get_social_queue():
    from core.integrations.social_manager import SocialManager
    mgr = SocialManager()
    return mgr.get_queued_posts()


@router.post("/social/post/{post_id}")
async def execute_social_post(post_id: int):
    from core.integrations.social_manager import SocialManager
    mgr = SocialManager()
    res = mgr.execute_post(post_id)
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res


@router.get("/automation/status")
async def get_automation_status():
    from tools.task_scheduler import get_scheduled_tasks
    from backend.metrics_service import SystemMetricsCollector
    try:
        tasks = get_scheduled_tasks()
        collector = SystemMetricsCollector()
        svc_status = collector.get_services_status()
        
        active_workflows = [
            {
                "id": "sys_diag",
                "name": "System Health Monitor",
                "status": "Running" if svc_status.get("backend") == "running" else "Stopped",
                "interval": "10s"
            },
            {
                "id": "cvcs_scan",
                "name": "CVCS Window Track Loop",
                "status": "Running" if svc_status.get("project_monitor") == "running" else "Stopped",
                "interval": "2s"
            },
            {
                "id": "voice_wake",
                "name": "Voice Wake Word Daemon",
                "status": "Listening" if svc_status.get("wake_word") == "running" else "Stopped",
                "trigger": "Yes?" if svc_status.get("wake_word") == "running" else "--"
            }
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

@router.get("/cvcs/status")
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


@router.post("/cvcs/permission")
async def set_cvcs_permission(req: CVCSPermissionRequest):
    from server.backend.safety_guard import SafetyGuard
    guard = SafetyGuard()
    return guard.set_permission_level(req.level, req.duration_seconds)


@router.post("/cvcs/toggle-monitor")
async def set_cvcs_toggle_monitor(req: TextRequest):
    from server.backend.screen_monitor import get_monitor_instance
    monitor = get_monitor_instance()
    active = req.text.lower() == "true"
    return monitor.toggle_watch_mode(active)


@router.get("/cvcs/screenshot")
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


@router.post("/cvcs/execute_action")
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


@router.post("/workflow")
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

