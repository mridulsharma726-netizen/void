import requests
import logging
import threading
import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

# Explicit OLLAMA_URL - ensure correct endpoint
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

# Default model - can be overridden
MODEL = "llama3.2:3b"

# Developer mode state
developer_mode = False
developer_mode_lock = threading.Lock()

# Logging setup
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "brain.log")

def _ensure_log_dir():
    """Ensure logs directory exists."""
    os.makedirs(LOG_DIR, exist_ok=True)

def _log_brain(action: str, details: str = ""):
    """Log brain activities."""
    _ensure_log_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {action}: {details}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"[BRAIN LOG ERROR] {e}")

def enter_developer_mode() -> Dict[str, Any]:
    """Enable developer mode."""
    global developer_mode
    with developer_mode_lock:
        developer_mode = True
        _log_brain("DEVELOPER_MODE", "ENTERED")
        return {"status": "ok", "message": "Developer mode enabled. You can now modify files and run repairs."}

def exit_developer_mode() -> Dict[str, Any]:
    """Disable developer mode."""
    global developer_mode
    with developer_mode_lock:
        developer_mode = False
        _log_brain("DEVELOPER_MODE", "EXITED")
        return {"status": "ok", "message": "Developer mode disabled."}

def is_developer_mode() -> bool:
    """Check if developer mode is active."""
    with developer_mode_lock:
        return developer_mode

def create_plan(task: str) -> Dict[str, Any]:
    """
    Create a structured plan for a task.
    This is a simple planner that breaks down tasks into steps.
    """
    _log_brain("PLAN_CREATE", f"Task: {task}")
    
    # Simple task decomposition
    task_lower = task.lower()
    steps = []
    
    if "file" in task_lower or "modify" in task_lower:
        steps.append({
            "step": 1,
            "action": "analyze_file",
            "description": "Analyze target file structure"
        })
        steps.append({
            "step": 2,
            "action": "generate_diff",
            "description": "Generate diff preview"
        })
        steps.append({
            "step": 3,
            "action": "apply_changes",
            "description": "Apply changes with backup"
        })
    elif "repair" in task_lower or "fix" in task_lower:
        steps.append({
            "step": 1,
            "action": "run_diagnostics",
            "description": "Run system diagnostics"
        })
        steps.append({
            "step": 2,
            "action": "generate_plan",
            "description": "Generate repair plan"
        })
        steps.append({
            "step": 3,
            "action": "execute_repair",
            "description": "Execute repair steps"
        })
    elif "analyze" in task_lower or "diagnostic" in task_lower:
        steps.append({
            "step": 1,
            "action": "check_imports",
            "description": "Check import errors"
        })
        steps.append({
            "step": 2,
            "action": "check_modules",
            "description": "Check missing modules"
        })
        steps.append({
            "step": 3,
            "action": "check_endpoints",
            "description": "Check endpoint integrity"
        })
    else:
        # Generic task
        steps.append({
            "step": 1,
            "action": "understand_task",
            "description": "Understand task requirements"
        })
        steps.append({
            "step": 2,
            "action": "break_down",
            "description": "Break down into actionable steps"
        })
    
    return {
        "status": "ok",
        "task": task,
        "steps": steps,
        "total_steps": len(steps)
    }

def execute_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a plan with step-by-step progress.
    """
    _log_brain("PLAN_EXECUTE", f"Plan: {plan.get('task', 'unknown')}")
    
    steps = plan.get("steps", [])
    results = []
    
    for step in steps:
        step_num = step.get("step")
        action = step.get("action")
        
        result = {
            "step": step_num,
            "action": action,
            "status": "completed",
            "result": f"Executed: {action}"
        }
        results.append(result)
    
    return {
        "status": "ok",
        "plan": plan,
        "results": results,
        "all_completed": all(r.get("status") == "completed" for r in results)
    }

def reflect_on_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze execution result and provide feedback.
    """
    _log_brain("REFLECT", f"Result: {result}")
    
    reflection = {
        "status": "ok",
        "analysis": "",
        "recommendations": []
    }
    
    # Analyze the result
    if result.get("all_completed"):
        reflection["analysis"] = "All steps completed successfully."
        reflection["recommendations"].append("Task finished. Consider next actions.")
    else:
        failed_steps = [r for r in result.get("results", []) if r.get("status") == "failed"]
        reflection["analysis"] = f"{len(failed_steps)} step(s) failed."
        reflection["recommendations"].append("Review failed steps and retry.")
    
    return reflection

print(f"[VOID BRAIN INIT] OLLAMA_URL = {OLLAMA_URL}")
print(f"[VOID BRAIN INIT] MODEL = {MODEL}")

def ask_llm(prompt: str, model: str = None) -> str:
    """Ask the local LLM via Ollama (/api/chat) and return the response."""
    
    use_model = model or MODEL
    
    # Check if user is asking about creator
    prompt_lower = prompt.lower().strip()
    creator_keywords = [
        "who created you",
        "who made you",
        "who is your creator",
        "who built you",
        "who developed you",
        "who's your creator",
        "your creator",
    ]
    
    is_asking_creator = any(keyword in prompt_lower for keyword in creator_keywords)
    
    payload = {
        "model": use_model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }

    try:
        print(f"[VOID BRAIN REQUEST] model={use_model} prompt_len={len(prompt)} url={OLLAMA_URL}")
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        
        print(f"[VOID BRAIN RESPONSE] status={response.status_code} keys={list(data.keys())}")
        
        # Check for valid response format
        if not isinstance(data, dict):
            return "LLM returned invalid response format."
        
        if "message" not in data:
            return "LLM returned invalid response format: missing 'message' key."
        
        if not isinstance(data["message"], dict):
            return "LLM returned invalid response format: 'message' is not a dict."
        
        content = data["message"].get("content", "").strip()
        
        # Handle empty content
        if not content:
            print("[VOID BRAIN ERROR] LLM returned empty content")
            return "LLM returned empty content."
        
        # ONLY append identity if user asked about creator
        if is_asking_creator:
            content = "I was created by Mridul Sharma."
        
        print(f"[VOID BRAIN OUTPUT] content_len={len(content)}")
        return content

    except requests.exceptions.ConnectionError as e:
        print(f"[VOID BRAIN ERROR] ConnectionError - Is Ollama running at {OLLAMA_URL}? {e}")
        return f"Error connecting to Ollama: {str(e)}. Make sure Ollama is running."
    except requests.exceptions.Timeout as e:
        print(f"[VOID BRAIN ERROR] Timeout after 120s - model may be loading: {e}")
        return f"Ollama request timed out: {str(e)}."
    except requests.RequestException as e:
        print(f"[VOID BRAIN ERROR] RequestException: {e}")
        return f"Error connecting to Ollama: {str(e)}. Make sure Ollama is running."
    except KeyError as e:
        print(f"[VOID BRAIN ERROR] KeyError parsing response: {e}")
        return "LLM returned invalid response format."
    except Exception as e:
        print(f"[VOID BRAIN ERROR] Unexpected: {type(e).__name__}: {e}")
        return f"Unexpected error: {str(e)}"
