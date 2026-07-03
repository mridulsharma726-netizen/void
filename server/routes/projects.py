import logging
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from server.dependencies import (
    VoidSingletons, PermissionManager, DATA_DIR, ROOT_DIR, STATS
)

logger = logging.getLogger("void.routes.projects")

router = APIRouter()


class EngineeringProposeRequest(BaseModel):
    goal: str

class ProjectScanRequest(BaseModel):
    path: str

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


@router.post("/api/fs/read")
async def api_fs_read(req: FSReadRequest):
    """Read a file — no approval required."""
    try:
        from backend.fs_tools import get_fs_tools
        return get_fs_tools().read_file(req.path)
    except Exception as e:
        logger.error(f"[/api/fs/read] Error: {e}")
        return {"status": "error", "message": str(e)}



@router.post("/api/fs/write")
async def api_fs_write(req: FSWriteRequest):
    """Write a file — triggers user approval gate."""
    try:
        from backend.fs_tools import get_fs_tools
        return await get_fs_tools().write_file(req.path, req.content, req.encoding)
    except Exception as e:
        logger.error(f"[/api/fs/write] Error: {e}")
        return {"status": "error", "message": str(e)}



@router.post("/api/fs/list")
async def api_fs_list(req: FSListRequest):
    """List directory contents — no approval required."""
    try:
        from backend.fs_tools import get_fs_tools
        return get_fs_tools().list_directory(req.path, req.max_entries)
    except Exception as e:
        logger.error(f"[/api/fs/list] Error: {e}")
        return {"status": "error", "message": str(e)}



@router.post("/api/terminal/run")
async def api_terminal_run(req: TerminalRunRequest):
    """Execute a terminal command — triggers user approval gate."""
    try:
        from tools.terminal_tools import execute_sandboxed
        return await execute_sandboxed(req.command, cwd=req.cwd, timeout=req.timeout)
    except Exception as e:
        logger.error(f"[/api/terminal/run] Error: {e}")
        return {"status": "error", "message": str(e)}



@router.post("/api/build/plan")
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



@router.post("/api/build/execute")
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



@router.get("/api/intelligence-status")
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



@router.get("/api/engineering/proposal")
async def get_engineering_proposal():
    proposal_path = DATA_DIR / "pending_proposal.json"
    if proposal_path.exists():
        try:
            with open(proposal_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"error": f"Failed to load proposal: {e}"}
    return {"status": "empty", "message": "No pending proposals"}


@router.post("/api/engineering/propose")
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


@router.post("/api/engineering/approve")
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


@router.post("/api/engineering/reject")
async def reject_engineering_changes():
    proposal_path = DATA_DIR / "pending_proposal.json"
    if proposal_path.exists():
        proposal_path.unlink()
        return {"status": "ok", "message": "Proposal rejected and cleared"}
    return {"status": "error", "message": "No pending proposal to reject"}

# /time and /system-info extracted to routes/admin.py


# [Extracted Chat Route Block]


# [Extracted Chat Route Block]


@router.get("/api/tasks")
async def get_tasks():
    from core.autonomous_agent.task_planner import TaskPlanner
    planner = TaskPlanner()
    return {"status": "ok", "tasks": planner.list_tasks()}



@router.get("/api/tasks/{task_id}")
async def get_task_by_id(task_id: str):
    from core.autonomous_agent.task_planner import TaskPlanner
    planner = TaskPlanner()
    task = planner.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok", "task": task.to_dict()}



@router.post("/api/tasks/clear")
async def clear_tasks():
    from core.autonomous_agent.task_planner import TaskPlanner
    planner = TaskPlanner()
    planner.clear_tasks()
    return {"status": "ok", "message": "Tasks cleared successfully"}



@router.get("/projects/list")
async def get_projects_list():
    from backend.memory_sqlite import list_tracked_projects
    try:
        return list_tracked_projects()
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        return []


@router.post("/projects/scan")
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


@router.delete("/projects/delete/{project_id}")
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


@router.get("/projects/files/{project_id}")
async def get_project_files_endpoint(project_id: str):
    from backend.memory_sqlite import get_project_files
    try:
        files = get_project_files(project_id)
        return files
    except Exception as e:
        logger.error(f"Failed to list project files: {e}")
        return []


@router.get("/projects/details/{project_id}")
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

