import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("void.routes.pc_hub")
router = APIRouter()

# Request schemas
class OpenAppRequest(BaseModel):
    app_name: str

class OpenUrlRequest(BaseModel):
    url: str

class PlayYoutubeRequest(BaseModel):
    query: str

class OpenFolderRequest(BaseModel):
    folder_name: str

class RunActionRequest(BaseModel):
    action: str
    params: Optional[Dict[str, Any]] = None

# Safe import helpers
def get_pc_control():
    try:
        import tools.pc_control as pc
        return pc
    except Exception as e:
        logger.error(f"Failed to import pc_control: {e}")
        return None

def get_system_control():
    try:
        import tools.system_control as sys_ctrl
        return sys_ctrl
    except Exception as e:
        logger.error(f"Failed to import system_control: {e}")
        return None

def get_system_stats_module():
    try:
        import tools.system_stats as sys_stats
        return sys_stats
    except Exception as e:
        logger.error(f"Failed to import system_stats: {e}")
        return None


@router.post("/api/pc/open-app")
async def api_pc_open_app(req: OpenAppRequest):
    pc = get_pc_control()
    if not pc:
        raise HTTPException(status_code=500, detail="PC control module unavailable")
    try:
        res = pc.open_app(req.app_name)
        return res
    except Exception as e:
        logger.error(f"Error opening app {req.app_name}: {e}")
        return {"status": "error", "message": str(e)}

@router.post("/api/pc/open-url")
async def api_pc_open_url(req: OpenUrlRequest):
    pc = get_pc_control()
    if not pc:
        raise HTTPException(status_code=500, detail="PC control module unavailable")
    try:
        res = pc.open_url(req.url)
        return res
    except Exception as e:
        logger.error(f"Error opening URL {req.url}: {e}")
        return {"status": "error", "message": str(e)}

@router.post("/api/pc/play-youtube")
async def api_pc_play_youtube(req: PlayYoutubeRequest):
    pc = get_pc_control()
    if not pc:
        raise HTTPException(status_code=500, detail="PC control module unavailable")
    try:
        res = pc.play_youtube(req.query)
        return res
    except Exception as e:
        logger.error(f"Error playing YouTube for {req.query}: {e}")
        return {"status": "error", "message": str(e)}

@router.post("/api/pc/open-folder")
async def api_pc_open_folder(req: OpenFolderRequest):
    pc = get_pc_control()
    if not pc:
        raise HTTPException(status_code=500, detail="PC control module unavailable")
    try:
        res = pc.open_folder(req.folder_name)
        return res
    except Exception as e:
        logger.error(f"Error opening folder {req.folder_name}: {e}")
        return {"status": "error", "message": str(e)}

@router.post("/api/pc/close-app")
async def api_pc_close_app(req: OpenAppRequest):
    sys_ctrl = get_system_control()
    if not sys_ctrl:
        raise HTTPException(status_code=500, detail="System control module unavailable")
    try:
        res = sys_ctrl.close_app(req.app_name)
        return res
    except Exception as e:
        logger.error(f"Error closing app {req.app_name}: {e}")
        return {"status": "error", "message": str(e)}

@router.post("/api/pc/run-action")
async def api_pc_run_action(req: RunActionRequest):
    sys_ctrl = get_system_control()
    if not sys_ctrl:
        raise HTTPException(status_code=500, detail="System control module unavailable")
        
    action = req.action.lower().strip()
    try:
        if action == "screenshot":
            return sys_ctrl.take_screenshot()
        elif action == "list_apps":
            limit = 20
            if req.params and "limit" in req.params:
                limit = int(req.params["limit"])
            apps = sys_ctrl.list_running_apps(limit)
            return {"status": "ok", "apps": apps}
        elif action == "clean_temp":
            return sys_ctrl.clean_temp_files()
        elif action == "empty_recycle":
            return sys_ctrl.empty_recycle_bin()
        elif action == "system_stats":
            stats_mod = get_system_stats_module()
            if stats_mod:
                return {"status": "ok", "stats": stats_mod.get_system_stats()}
            return {"status": "error", "message": "System stats module unavailable"}
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")
    except Exception as e:
        logger.error(f"Error running action {action}: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/api/pc/system-info")
async def api_pc_system_info():
    stats_mod = get_system_stats_module()
    if not stats_mod:
        raise HTTPException(status_code=500, detail="System stats module unavailable")
    try:
        stats = stats_mod.get_system_stats()
        return {"status": "ok", "stats": stats}
    except Exception as e:
        logger.error(f"Error fetching system info: {e}")
        return {"status": "error", "message": str(e)}
