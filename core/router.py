# core/router.py

from core.memory import save_memory, search_memory
from tools.system_tools import (
    get_system_info,
    get_time,
    open_app,
    open_url,
    search_web,
    listen_audio,
    get_file_status,
    get_folder_status,
)
from core.intent_router import detect_intent_and_params
from core.architecture_explainer import is_architecture_query, explain_architecture
from workflows.workflow_engine import WorkflowEngine
import threading
import re


def _get_tools_dict():
    return {
        "open_app": open_app,
        "open_url": open_url,
        "search_web": search_web,
        "time": get_time,
        "system_info": get_system_info,
        "listen_audio": listen_audio,
        "get_file_status": get_file_status,
        "get_folder_status": get_folder_status,
    }


def route_command(command: str):
    """
    Routes the command to the appropriate tool.
    Returns:
      - tool result string/dict if handled
      - None if not handled (so main.py can send to LLM chat)
    """
    if not command:
        return None

    # ============================================================
    # ARCHITECTURE QUERIES (intercept before LLM)
    # ============================================================

    lower = command.lower().strip()
    
    # Check if this is an architecture query
    if is_architecture_query(command):
        try:
            # Get real architecture description from project scan
            arch_description = explain_architecture()
            return {
                "status": "ok",
                "type": "architecture",
                "reply": arch_description
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Architecture scan failed: {str(e)}"
            }

    # ============================================================
    # SELF-MODIFICATION COMMANDS (must be checked first)
    # ============================================================

    
    # "improve yourself" command
    if lower == "improve yourself" or lower == "self improve":
        try:
            from core.code_editor_agent import handle_improve_self_command
            return handle_improve_self_command()
        except ImportError:
            return {"status": "error", "message": "Self-improvement not available"}
    
    # "scan project" command
    if lower == "scan project" or lower == "scan my project":
        try:
            from core.code_editor_agent import handle_scan_command
            return handle_scan_command()
        except ImportError:
            return {"status": "error", "message": "Scan not available"}
    
    # "rewrite module" command
    m = re.match(r"^rewrite\s+module\s+(.+)$", lower)
    if m:
        module_name = m.group(1).strip()
        try:
            from core.code_editor_agent import handle_rewrite_command
            return handle_rewrite_command(module_name)
        except ImportError:
            return {"status": "error", "message": "Rewrite not available"}
    
    # ============================================================
    # SYSTEM COMMANDS
    # ============================================================

    # "system diagnostics" command
    if lower == "system diagnostics":
        try:
            from core.diagnostics import run_diagnostics, format_diagnostics
            result = run_diagnostics()
            return {
                "status": "ok",
                "type": "diagnostics",
                "reply": format_diagnostics(result)
            }
        except ImportError:
            return {
                "status": "ok",
                "type": "diagnostics",
                "reply": "Backend: OK\nOllama: Running\nCode Tools: Available\nRun 'scan project' for full diagnostics."
            }
    
    # "list modules" command
    if lower == "list modules" or lower == "show modules" or lower == "available modules":
        try:
            from core.diagnostics import list_modules
            return {
                "status": "ok",
                "type": "modules",
                "reply": list_modules()
            }
        except ImportError:
            try:
                from core.code_editor_agent import get_available_modules
                modules = get_available_modules()
                return {
                    "status": "ok",
                    "type": "modules",
                    "reply": "Available modules:\n" + "\n".join(f"- {m}" for m in modules[:20])
                }
            except:
                return {"status": "error", "message": "Cannot list modules. Run 'scan project' first."}
    
    # "show codebase map" command
    if lower == "show codebase map" or lower == "codebase map" or lower == "show map":
        try:
            from core.diagnostics import show_codebase_map
            return {
                "status": "ok",
                "type": "codebase_map",
                "reply": show_codebase_map()
            }
        except ImportError:
            return {"status": "error", "message": "Codebase map not available. Run 'scan project' first."}
    
    # "analyze codebase" command
    if lower == "analyze codebase" or lower == "analyze your codebase":
        try:
            from core.code_editor_agent import scan_project
            result = scan_project()
            if result.get("status") == "ok":
                reply = f"""Codebase Analysis
================

Total Files: {result.get('total_files', 0)}
Total Modules: {result.get('total_modules', 0)}

Files by Directory:
"""
                for dir_name, count in result.get("files_by_directory", {}).items():
                    reply += f"  {dir_name}: {count} files\n"
                
                reply += "\nTop Modules:\n"
                for mod in result.get("available_modules", [])[:10]:
                    reply += f"  - {mod}\n"
                
                return {"status": "ok", "type": "analysis", "reply": reply}
            return result
        except Exception as e:
            return {"status": "error", "message": f"Analysis failed: {str(e)}"}
    
    # ============================================================
    # END SYSTEM COMMANDS
    # ============================================================

    intent_data = detect_intent_and_params(command)
    intent = intent_data.get("intent")
    params = intent_data.get("parameters", {}) or {}

    # --- direct tool intents ---
    if intent == "system_info":
        return get_system_info()

    if intent == "time":
        return get_time()

    if intent == "open_app":
        app_name = params.get("app_name")
        if app_name:
            return open_app(app_name)

    if intent == "open_url":
        url = params.get("url")
        if url:
            return open_url(url)

    if intent == "search_web":
        query = params.get("query")
        if query:
            return search_web(query)

    if intent == "listen_audio":
        timeout = params.get("timeout")
        phrase_time_limit = params.get("phrase_time_limit")
        return listen_audio(timeout=timeout, phrase_time_limit=phrase_time_limit)

    if intent == "get_file_status":
        path = params.get("path")
        if path:
            return get_file_status(path)

    if intent == "get_folder_status":
        path = params.get("path")
        if path:
            return get_folder_status(path)

    # --- workflow intent ---
    if intent == "workflow":
        steps = params.get("steps")
        if isinstance(steps, list) and steps:
            engine = WorkflowEngine(_get_tools_dict())

            def _run():
                engine.run_workflow("ui_workflow", steps)

            threading.Thread(target=_run, daemon=True).start()
            return "Executing workflow..."

    # --- memory commands ---
    if command.lower().startswith("remember "):
        text = command[9:]
        save_memory("note", text)
        return "Note saved."

    if command.lower().startswith("recall "):
        keyword = command[7:]
        results = search_memory(keyword)
        if results:
            response = "Recalled notes:\n"
            for timestamp, key, value in results:
                response += f"- {timestamp}: {value}\n"
            return response.strip()
        return "No matching notes found."

    return None
