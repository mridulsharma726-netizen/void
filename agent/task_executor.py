"""
VOID Task Executor Module
====================

Executes plans created by the task planner.

Functions:
- execute_plan(plan: List[dict]) -> Dict[str, Any]
- execute_step(step: dict) -> Dict[str, Any]
"""

import logging
import time
from typing import List, Dict, Any

logger = logging.getLogger("VOID-TaskExecutor")

# Import tools (with fallback)
try:
    from tools.system_tools import open_app as _open_app
    from tools.system_tools import open_url as _open_url
except Exception:
    _open_app = None
    _open_url = None

try:
    from tools.system_tools import search_google as _search_google
except Exception:
    _search_google = None

try:
    from tools.system_tools import play_youtube as _play_youtube
except Exception:
    _play_youtube = None


def open_folder(folder_path: str) -> Dict[str, Any]:
    """Open a folder in Windows Explorer."""
    try:
        import subprocess
        subprocess.Popen(["explorer", folder_path])
        return {"status": "ok", "message": f"Opened folder: {folder_path}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def open_terminal() -> Dict[str, Any]:
    """Open Windows Terminal."""
    try:
        import subprocess
        subprocess.Popen(["wt.exe"])
        return {"status": "ok", "message": "Opened Terminal"}
    except Exception:
        # Try cmd as fallback
        try:
            subprocess.Popen(["cmd"])
            return {"status": "ok", "message": "Opened CMD"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


def execute_step(step: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a single step from a plan.
    
    Args:
        step: Dict with tool, args, description
        
    Returns:
        Dict with status and message
    """
    tool = step.get("tool", "")
    args = step.get("args")
    description = step.get("description", "")
    
    logger.info(f"[EXECUTOR] Executing: {description or tool}")
    
    try:
        if tool == "open_app":
            if _open_app:
                result = _open_app(args)
                return {"status": "ok", "message": result.get("message", "App opened")}
            else:
                return {"status": "ok", "message": f"Would open app: {args}"}
        
        elif tool == "open_url":
            if _open_url:
                result = _open_url(args)
                return {"status": "ok", "message": result.get("message", "URL opened")}
            else:
                return {"status": "ok", "message": f"Would open URL: {args}"}
        
        elif tool == "search_google":
            if _search_google:
                result = _search_google(args)
                return {"status": "ok", "message": result.get("message", "Search initiated")}
            else:
                return {"status": "ok", "message": f"Would search: {args}"}
        
        elif tool == "play_youtube":
            if _play_youtube:
                result = _play_youtube(args)
                return {"status": "ok", "message": result.get("message", "Playing")}
            else:
                return {"status": "ok", "message": f"Would play: {args}"}
        
        elif tool == "open_folder":
            result = open_folder(args)
            return result
        
        elif tool == "open_terminal":
            result = open_terminal()
            return result
        
        elif tool == "wait":
            # Wait for specified seconds
            wait_time = args or 1
            time.sleep(wait_time)
            return {"status": "ok", "message": f"Waited {wait_time}s"}
        
        else:
            return {"status": "error", "message": f"Unknown tool: {tool}"}
    
    except Exception as e:
        logger.error(f"[EXECUTOR] Error: {e}")
        return {"status": "error", "message": str(e)}


def execute_plan(plan: List[Dict[str, Any]], 
                delay_between: float = 0.5,
                stop_on_error: bool = False) -> Dict[str, Any]:
    """
    Execute a complete plan.
    
    Args:
        plan: List of step dicts
        delay_between: Seconds between steps
        stop_on_error: Stop execution if a step fails
        
    Returns:
        Dict with results of all steps
    """
    if not plan:
        return {
            "status": "error",
            "message": "No plan to execute",
            "results": []
        }
    
    logger.info(f"[EXECUTOR] Starting plan with {len(plan)} steps")
    
    results = []
    completed = 0
    failed = 0
    
    for i, step in enumerate(plan):
        step_num = i + 1
        description = step.get("description", f"Step {step_num}")
        
        logger.info(f"[EXECUTOR] Step {step_num}/{len(plan)}: {description}")
        
        result = execute_step(step)
        result["step"] = step_num
        result["description"] = description
        
        results.append(result)
        
        if result["status"] == "ok":
            completed += 1
            logger.info(f"[EXECUTOR] Step {step_num} OK")
        else:
            failed += 1
            logger.error(f"[EXECUTOR] Step {step_num} FAILED: {result.get('message')}")
            
            if stop_on_error:
                logger.warning("[EXECUTOR] Stopping due to error")
                break
        
        # Delay between steps (but not after last)
        if i < len(plan) - 1 and delay_between > 0:
            time.sleep(delay_between)
    
    # Build summary
    status = "completed" if failed == 0 else ("partial" if completed > 0 else "failed")
    
    summary = {
        "status": status,
        "total_steps": len(plan),
        "completed": completed,
        "failed": failed,
        "results": results
    }
    
    logger.info(f"[EXECUTOR] Plan complete: {completed}/{len(plan)} successful")
    
    return summary


def execute_plan_verbose(plan: List[Dict[str, Any]]) -> str:
    """
    Execute a plan and return verbose output.
    
    Returns:
        Human-readable string with all results
    """
    if not plan:
        return "No plan provided."
    
    results = execute_plan(plan)
    
    lines = []
    lines.append(f"📋 Executing {results['total_steps']} steps...")
    lines.append("")
    
    for result in results.get("results", []):
        step_num = result.get("step", "?")
        desc = result.get("description", "Unknown")
        status = "✅" if result["status"] == "ok" else "❌"
        
        lines.append(f"{status} Step {step_num}: {desc}")
        
        if result["status"] != "ok":
            lines.append(f"   Error: {result.get('message', 'Unknown')}")
    
    lines.append("")
    lines.append(f"📊 Result: {results['completed']}/{results['total_steps']} successful")
    
    return "\n".join(lines)


# ============================================================================
# QUICK EXECUTION FUNCTIONS
# ============================================================================

def quick_execute(prompt: str) -> Dict[str, Any]:
    """
    Quick execution from a simple prompt.
    Tries to parse and execute common commands.
    """
    prompt_lower = prompt.lower().strip()
    
    # Simple patterns
    if prompt_lower.startswith("open "):
        app_name = prompt[5:].strip()
        return execute_step({
            "tool": "open_app",
            "args": app_name,
            "description": f"Open {app_name}"
        })
    
    if prompt_lower.startswith("search "):
        query = prompt[7:].strip()
        return execute_step({
            "tool": "search_google",
            "args": query,
            "description": f"Search: {query}"
        })
    
    if prompt_lower.startswith("play "):
        query = prompt[5:].strip()
        return execute_step({
            "tool": "play_youtube",
            "args": query,
            "description": f"Play: {query}"
        })
    
    return {"status": "error", "message": "Could not parse command"}


if __name__ == "__main__":
    # Test executor
    print("Testing task executor...")
    
    # Simple step
    print("\n1. Testing single step:")
    result = execute_step({
        "tool": "open_app",
        "args": "notepad",
        "description": "Open Notepad"
    })
    print(f"Result: {result}")
    
    # Full plan
    print("\n2. Testing full plan:")
    plan = [
        {"tool": "open_app", "args": "notepad", "description": "Open Notepad"},
        {"tool": "wait", "args": 1, "description": "Wait 1 second"},
        {"tool": "open_app", "args": "chrome", "description": "Open Chrome"}
    ]
    
    summary = execute_plan(plan)
    print(f"Summary: {summary}")

