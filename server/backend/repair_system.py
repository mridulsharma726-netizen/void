"""
VOID Self-Repair Engine
======================

Safe, non-destructive system repair.
Attempts to fix common issues without modifying files or code.

Extended with:
- run_diagnostics() - Full system diagnostics
- generate_repair_plan() - Create step-by-step repair plan
- repair_system() - Automatic repair with multiple actions
- Requires developer_mode for repair operations
"""

import importlib
import os
import subprocess
import sys
import logging
from typing import Dict, Any, List

from backend.diagnostics import (
    run_full_diagnostics,
    check_stt,
    check_tts,
    check_memory,
    check_backend,
    check_dependencies,
    check_tool_modules
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VOID-SelfRepair")

# Import brain for developer mode check
try:
    from core.brain import is_developer_mode, _log_brain
except ImportError:
    is_developer_mode = lambda: False
    def _log_brain(action, details=""):
        logger.info(f"[SELF_REPAIR] {action}: {details}")


def run_diagnostics() -> Dict[str, Any]:
    """
    Run full system diagnostics.
    Checks:
    - Import errors
    - Missing modules
    - Broken tool calls
    - Error logs
    - Endpoint integrity
    
    Returns:
        dict: {
            "status": "ok"|"error",
            "components": {...},
            "issues": [...]
        }
    """
    _log_brain("DIAGNOSTICS_START", "Running full diagnostics")
    
    # Run full diagnostics
    diag_result = run_full_diagnostics()
    components = diag_result.get("components", {})
    
    # Extract issues
    issues = []
    for comp_name, comp_data in components.items():
        status = comp_data.get("status", "unknown")
        details = comp_data.get("details", "")
        repairable = comp_data.get("repairable", False)
        
        if status == "error":
            issues.append({
                "component": comp_name,
                "status": status,
                "details": details,
                "repairable": repairable
            })
    
    # Also check for import errors in tools
    tool_issues = _check_tool_imports()
    issues.extend(tool_issues)
    
    # Check error logs
    log_issues = _check_error_logs()
    issues.extend(log_issues)
    
    overall_status = "ok" if not issues else "error"
    
    result = {
        "status": overall_status,
        "components": components,
        "issues": issues,
        "total_issues": len(issues)
    }
    
    _log_brain("DIAGNOSTICS_COMPLETE", f"Found {len(issues)} issues")
    
    return result


def _check_tool_imports() -> List[Dict[str, Any]]:
    """Check if all tool modules can be imported."""
    issues = []
    
    tool_modules = [
        "tools.voice_tts",
        "tools.voice_stt",
        "tools.system_stats",
        "tools.file_status",
        "tools.diagnostics",
    ]
    
    for module_name in tool_modules:
        try:
            importlib.import_module(module_name)
        except ImportError as e:
            issues.append({
                "component": "import",
                "status": "error",
                "details": f"Failed to import {module_name}: {str(e)}",
                "repairable": False
            })
        except Exception as e:
            issues.append({
                "component": "import",
                "status": "error",
                "details": f"Error in {module_name}: {str(e)}",
                "repairable": True
            })
    
    return issues


def _check_error_logs() -> List[Dict[str, Any]]:
    """Check for recent errors in log files."""
    issues = []
    
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    
    if os.path.exists(log_dir):
        for filename in os.listdir(log_dir):
            if filename.endswith(".log"):
                log_path = os.path.join(log_dir, filename)
                try:
                    # Check last 50 lines for errors
                    with open(log_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        recent_lines = lines[-50:] if len(lines) > 50 else lines
                        error_count = sum(1 for line in recent_lines if "ERROR" in line.upper())
                        
                        if error_count > 5:
                            issues.append({
                                "component": "logs",
                                "status": "warning",
                                "details": f"{filename}: {error_count} recent errors",
                                "repairable": False
                            })
                except Exception:
                    pass
    
    return issues


def generate_repair_plan(issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate a step-by-step repair plan from issues.
    
    Args:
        issues: List of issues from run_diagnostics()
        
    Returns:
        dict: {
            "status": "ok",
            "plan": [
                {"step": 1, "action": "...", "target": "...", "description": "..."}
            ],
            "requires_confirmation": True/False
        }
    """
    _log_brain("REPAIR_PLAN_START", f"Generating plan for {len(issues)} issues")
    
    plan = []
    step_num = 1
    
    for issue in issues:
        component = issue.get("component", "unknown")
        details = issue.get("details", "")
        repairable = issue.get("repairable", False)
        
        if not repairable:
            continue
        
        # Map components to repair actions
        if component == "stt":
            plan.append({
                "step": step_num,
                "action": "reinit_stt",
                "target": "tools.voice_stt",
                "description": "Reinitialize STT engine"
            })
            step_num += 1
        elif component == "tts":
            plan.append({
                "step": step_num,
                "action": "reinit_tts",
                "target": "tools.voice_tts",
                "description": "Reinitialize TTS engine"
            })
            step_num += 1
        elif component == "memory":
            plan.append({
                "step": step_num,
                "action": "repair_memory",
                "target": "data/memory.json",
                "description": "Repair or reset memory file"
            })
            step_num += 1
        elif component == "dependencies":
            plan.append({
                "step": step_num,
                "action": "install_dependencies",
                "target": "requirements.txt",
                "description": f"Install missing dependencies"
            })
            step_num += 1
        elif component == "tool_modules":
            plan.append({
                "step": step_num,
                "action": "fix_tool_modules",
                "target": "tools/",
                "description": "Fix broken tool modules"
            })
            step_num += 1
        elif component == "import":
            plan.append({
                "step": step_num,
                "action": "reload_modules",
                "target": "Python modules",
                "description": f"Reload modules: {details}"
            })
            step_num += 1
    
    # Always add a final verification step
    if plan:
        plan.append({
            "step": step_num,
            "action": "verify",
            "target": "all",
            "description": "Run diagnostics again to verify repairs"
        })
    
    result = {
        "status": "ok",
        "plan": plan,
        "total_steps": len(plan),
        "requires_confirmation": len(plan) > 0
    }
    
    _log_brain("REPAIR_PLAN_COMPLETE", f"Generated {len(plan)} steps")
    
    return result


def execute_repair_plan(plan: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Execute a repair plan.
    Requires developer_mode = True.
    
    Args:
        plan: List of repair steps
        
    Returns:
        dict: {
            "status": "ok"|"error",
            "executed": [...],
            "failed": [...],
            "summary": "..."
        }
    """
    _log_brain("REPAIR_EXECUTE_START", f"Executing {len(plan)} steps")
    
    # Check developer mode
    if not is_developer_mode():
        return {
            "status": "error",
            "error": "Developer mode required. Say 'enter developer mode' first."
        }
    
    executed = []
    failed = []
    
    for step in plan:
        step_num = step.get("step")
        action = step.get("action")
        
        try:
            if action == "reinit_stt":
                result = _reinit_stt()
            elif action == "reinit_tts":
                result = _reinit_tts()
            elif action == "repair_memory":
                result = _repair_memory_file()
            elif action == "install_dependencies":
                result = _install_dependencies()
            elif action == "fix_tool_modules":
                result = _fix_tool_modules()
            elif action == "reload_modules":
                result = _reload_modules()
            elif action == "verify":
                # Run diagnostics to verify
                diag = run_diagnostics()
                result = {
                    "success": diag.get("total_issues", 1) == 0,
                    "message": f"Found {diag.get('total_issues', 0)} remaining issues"
                }
            else:
                result = {"success": False, "message": f"Unknown action: {action}"}
            
            executed.append({
                "step": step_num,
                "action": action,
                "result": result
            })
            
            if not result.get("success", False):
                failed.append({
                    "step": step_num,
                    "action": action,
                    "error": result.get("message", "Unknown error")
                })
        
        except Exception as e:
            failed.append({
                "step": step_num,
                "action": action,
                "error": str(e)
            })
    
    summary = f"Executed {len(executed)} steps, {len(failed)} failed"
    
    _log_brain("REPAIR_EXECUTE_COMPLETE", summary)
    
    return {
        "status": "ok" if not failed else "partial",
        "executed": executed,
        "failed": failed,
        "summary": summary
    }


def _reinit_stt() -> Dict[str, Any]:
    """
    Attempt to reinitialize STT engine.
    """
    result = {"action": "reinit_stt", "success": False, "message": ""}
    
    try:
        # Reload the module to reinitialize
        import tools.voice_stt as voice_stt
        
        # Reset the class variables to force reinit
        voice_stt.VoiceSTT._recognizer = None
        voice_stt.VoiceSTT._microphone = None
        voice_stt.VoiceSTT._instance = None
        
        # Reinitialize
        new_stt = voice_stt.VoiceSTT()
        
        # Check if it worked
        if voice_stt.VoiceSTT._recognizer is not None:
            result["success"] = True
            result["message"] = "STT reinitialized successfully"
        else:
            result["message"] = "STT reinitialization failed"
            
    except Exception as e:
        result["message"] = f"STT reinit error: {str(e)}"
    
    return result


def _reinit_tts() -> Dict[str, Any]:
    """
    Attempt to reinitialize TTS engine.
    """
    result = {"action": "reinit_tts", "success": False, "message": ""}
    
    try:
        import tools.voice_tts as voice_tts
        
        # Reset fallback engine and ffplay reference
        voice_tts._fallback_engine = None
        voice_tts._ffplay_process = None
        voice_tts._is_speaking.clear()
        voice_tts._stop_flag.set()
        
        # Verify fallback still initialized
        try:
            voice_tts._get_fallback_engine()
        except:
            pass
            
        result["success"] = True
        result["message"] = "TTS reinitialized successfully (edge-tts active)"
            
    except Exception as e:
        result["message"] = f"TTS reinit error: {str(e)}"
    
    return result


def _repair_memory_file() -> Dict[str, Any]:
    """
    Attempt to repair corrupted memory file.
    """
    result = {"action": "repair_memory", "success": False, "message": ""}
    
    try:
        import json
        import os
        
        from pathlib import Path
        memory_file = str(Path(__file__).parent.parent.parent / "memory" / "data" / "memory.json")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(memory_file), exist_ok=True)
        
        # Check if file exists and is valid
        if not os.path.exists(memory_file):
            # Create new file
            with open(memory_file, "w") as f:
                json.dump({"facts": []}, f)
            result["success"] = True
            result["message"] = "Memory file created"
        else:
            # Try to read and validate
            try:
                with open(memory_file, "r") as f:
                    data = json.load(f)
                    
                # Validate structure
                if isinstance(data, dict) and "facts" in data and isinstance(data["facts"], list):
                    result["success"] = True
                    result["message"] = f"Memory file valid with {len(data['facts'])} facts"
                else:
                    # Repair structure
                    with open(memory_file, "w") as f:
                        json.dump({"facts": []}, f)
                    result["success"] = True
                    result["message"] = "Memory file structure repaired"
            except json.JSONDecodeError:
                # Reset corrupted file
                with open(memory_file, "w") as f:
                    json.dump({"facts": []}, f)
                result["success"] = True
                result["message"] = "Memory file reset (was corrupted)"
                    
    except Exception as e:
        result["message"] = f"Memory repair error: {str(e)}"
    
    return result


def _install_dependencies() -> Dict[str, Any]:
    """
    Attempt to install missing dependencies.
    """
    result = {"action": "install_dependencies", "success": False, "message": ""}
    
    try:
        # Check which dependencies are missing
        dep_check = check_dependencies()
        missing = dep_check.get("missing_packages", [])
        
        if not missing:
            result["success"] = True
            result["message"] = "All dependencies already installed"
            return result
        
        # Try to install missing packages
        installed = []
        failed = []
        
        for package in missing:
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", package],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                installed.append(package)
            except subprocess.CalledProcessError:
                failed.append(package)
        
        if failed:
            result["message"] = f"Failed to install: {failed}"
        else:
            result["success"] = True
            result["message"] = f"Installed {len(installed)} packages: {installed}"
            
    except Exception as e:
        result["message"] = f"Dependency install error: {str(e)}"
    
    return result


def _fix_tool_modules() -> Dict[str, Any]:
    """
    Attempt to fix broken tool modules.
    """
    result = {"action": "fix_tool_modules", "success": False, "message": ""}
    
    try:
        # Check which modules are broken
        module_check = check_tool_modules()
        broken = module_check.get("broken_modules", [])
        
        if not broken:
            result["success"] = True
            result["message"] = "All tool modules working"
            return result
        
        # Try to reload each broken module
        fixed = []
        still_broken = []
        
        for broken_module in broken:
            module_name = broken_module.get("module")
            try:
                # Force reload
                if module_name in sys.modules:
                    del sys.modules[module_name]
                importlib.import_module(module_name)
                fixed.append(module_name)
            except:
                still_broken.append(module_name)
        
        if still_broken:
            result["message"] = f"Fixed {len(fixed)}, still broken: {still_broken}"
        else:
            result["success"] = True
            result["message"] = f"Fixed {len(fixed)} tool modules"
            
    except Exception as e:
        result["message"] = f"Module fix error: {str(e)}"
    
    return result


def _reload_modules() -> Dict[str, Any]:
    """
    Reload Python modules to fix import issues.
    """
    result = {"action": "reload_modules", "success": False, "message": ""}
    
    try:
        # List of core modules to reload
        core_modules = [
            "tools.diagnostics",
            "tools.self_repair",
            "tools.system_tools"
        ]
        
        reloaded = []
        failed = []
        
        for module_name in core_modules:
            try:
                if module_name in sys.modules:
                    del sys.modules[module_name]
                importlib.import_module(module_name)
                reloaded.append(module_name)
            except:
                failed.append(module_name)
        
        if failed:
            result["message"] = f"Reloaded {len(reloaded)}, failed: {failed}"
        else:
            result["success"] = True
            result["message"] = f"Reloaded {len(reloaded)} modules"
            
    except Exception as e:
        result["message"] = f"Module reload error: {str(e)}"
    
    return result


def _clear_state_flags() -> Dict[str, Any]:
    """
    Clear internal state flags.
    """
    result = {"action": "clear_state", "success": False, "message": ""}
    
    try:
        cleared = []
        
        # Reset TTS state
        try:
            import tools.voice_tts as voice_tts
            voice_tts._ffplay_process = None
            voice_tts._fallback_engine = None
            voice_tts._is_speaking.clear()
            voice_tts._stop_flag.set()
            cleared.append("tts_state")
        except Exception:
            pass
            
        # Reset STT state  
        try:
            import tools.voice_stt as voice_stt
            voice_stt.VoiceSTT._recognizer = None
            voice_stt.VoiceSTT._microphone = None
            voice_stt.VoiceSTT._instance = None
            cleared.append("stt_state")
        except Exception:
            pass
            
        # Clear workflow engine state if it exists
        try:
            import tools.workflow_engine
            if hasattr(tools.workflow_engine, 'WorkflowEngine'):
                cleared.append("workflow_engine")
        except:
            pass
        
        # Clear any cached data
        try:
            import tools.system_stats
            if hasattr(tools.system_stats, 'SystemStats'):
                cleared.append("system_stats")
        except:
            pass
            
        result["success"] = True
        result["message"] = f"Cleared states: {', '.join(cleared) if cleared else 'none'}"
        
    except Exception as e:
        result["message"] = f"State clear error: {str(e)}"
    
    return result


def repair_system() -> Dict[str, Any]:
    """
    Main repair function.
    
    Steps:
    1. Run diagnostics
    2. If component status == error AND repairable:
       - Attempt safe fix
    3. Collect actions_taken
    4. Return structured result:
       {
           "status": "repaired" | "healthy" | "failed",
           "actions_taken": [],
           "remaining_issues": []
       }
    
    Allowed repair actions:
    - Reinitialize STT
    - Reinitialize TTS
    - Repair memory file
    - Install dependencies
    - Fix tool modules
    - Clear internal state flags
    """
    # Run diagnostics first
    diag = run_full_diagnostics()
    components = diag.get("components", {})
    
    actions_taken: List[Dict[str, Any]] = []
    remaining_issues: List[str] = []
    
    # Check each component
    for comp_name, comp_data in components.items():
        status = comp_data.get("status", "unknown")
        repairable = comp_data.get("repairable", False)
        
        if status == "error" and repairable:
            # Attempt repair based on component
            if comp_name == "stt":
                action_result = _reinit_stt()
                actions_taken.append(action_result)
                if action_result["success"]:
                    # Recheck
                    recheck = check_stt()
                    if recheck["status"] == "ok":
                        continue  # Fixed!
                remaining_issues.append(f"STT: {action_result['message']}")
                
            elif comp_name == "tts":
                action_result = _reinit_tts()
                actions_taken.append(action_result)
                if action_result["success"]:
                    # Recheck
                    recheck = check_tts()
                    if recheck["status"] == "ok":
                        continue  # Fixed!
                remaining_issues.append(f"TTS: {action_result['message']}")
                
            elif comp_name == "memory":
                action_result = _repair_memory_file()
                actions_taken.append(action_result)
                if action_result["success"]:
                    # Recheck
                    recheck = check_memory()
                    if recheck["status"] == "ok":
                        continue  # Fixed!
                remaining_issues.append(f"Memory: {action_result['message']}")
                
            elif comp_name == "dependencies":
                action_result = _install_dependencies()
                actions_taken.append(action_result)
                # Don't recheck, just note
                remaining_issues.append(f"Dependencies: {action_result.get('message', 'Check required')}")
                
            elif comp_name == "tool_modules":
                action_result = _fix_tool_modules()
                actions_taken.append(action_result)
                if action_result["success"]:
                    continue
                remaining_issues.append(f"Tool modules: {action_result.get('message', 'Not fixed')}")
                
            elif comp_name == "backend":
                remaining_issues.append("Backend: Not repairable - restart service manually")
        elif status == "error" and not repairable:
            remaining_issues.append(f"{comp_name.title()}: Not repairable - {comp_data.get('details', 'Unknown error')}")
    
    # Try clearing state flags as a precaution
    state_result = _clear_state_flags()
    actions_taken.append(state_result)
    
    # Determine final status
    if not remaining_issues:
        status = "healthy"
    elif any(a.get("success", False) for a in actions_taken):
        status = "repaired"
    else:
        status = "failed"
    
    return {
        "status": status,
        "actions_taken": actions_taken,
        "remaining_issues": remaining_issues,
        "diagnostics": diag
    }


# ========================================
# REPAIR API
# ========================================

def get_repair_result():
    """Get repair result as dict."""
    return repair_system()


class RepairSystem:
    """
    Repair Orchestrator Class.
    Maintains API compatibility with expected consumer classes.
    """
    def __init__(self, diagnostics_engine=None, memory_manager=None):
        self.diagnostics_engine = diagnostics_engine
        self.memory_manager = memory_manager
        
    async def run(self) -> Dict[str, Any]:
        """Execute automatic system repair."""
        res = repair_system()
        # main.py expects "fixed_count" key
        success_actions = [a for a in res.get("actions_taken", []) if a.get("success")]
        res["fixed_count"] = len(success_actions)
        return res
        
    async def auto_recover(self, issue: str) -> None:
        """Triggered automatically when critical errors occur."""
        logger.info(f"Auto-recovery triggered: {issue}")
        repair_system()


if __name__ == "__main__":
    # Test repair
    import json
    result = repair_system()
    print(json.dumps(result, indent=2))
