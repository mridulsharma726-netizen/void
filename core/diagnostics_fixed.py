"""
VOID System Diagnostics - FULL VERSION (Syntax Fixed)
=====================================

Comprehensive health checks for all VOID components.
Implements all functions required by self_repair.py.
"""

import os
import json
import importlib
import subprocess
import sys
import platform
from typing import Dict, Any, List

VOID_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Global flags for risky modules
REQUESTS_AVAILABLE = False
SR_AVAILABLE = False
PYTTsx3_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None

# Existing basic checks (now safe)
def check_backend_status():
    if not REQUESTS_AVAILABLE:
        return {"name": "Backend", "status": "error", "details": "requests not available"}
    try:
        r = requests.get("http://127.0.0.1:8000/health", timeout=2)
        return {"name": "Backend", "status": "ok" if r.status_code == 200 else "error", "details": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"name": "Backend", "status": "error", "details": str(e)}

def check_ollama_status():
    if not REQUESTS_AVAILABLE:
        return {"name": "Ollama", "status": "error", "details": "requests not available"}
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        if r.status_code == 200:
            return {"name": "Ollama", "status": "ok", "details": "Running"}
        return {"name": "Ollama", "status": "error", "details": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"name": "Ollama", "status": "error", "details": str(e)}

def check_code_tools():
    try:
        from tools.code_tools import read_file
        return {"name": "Code Tools", "status": "ok", "details": "Available"}
    except Exception as e:
        return {"name": "Code Tools", "status": "error", "details": str(e)}

def check_memory():
    try:
        from core.memory import save_memory
        return {"name": "Memory", "status": "ok", "details": "Working"}
    except Exception as e:
        return {"name": "Memory", "status": "error", "details": str(e)}

def check_codebase_map():
    map_file = os.path.join(VOID_ROOT, "data", "codebase_map.json")
    if not os.path.exists(map_file):
        return {"name": "Codebase Map", "status": "warning", "details": "Run scan project"}
    try:
        with open(map_file) as f:
            m = json.load(f)
        return {"name": "Codebase Map", "status": "ok", "details": f"{len(m)} modules"}
    except:
        return {"name": "Codebase Map", "status": "error", "details": "Corrupted"}

# STT check (safe)
def check_stt():
    \"\"\"Check Speech-to-Text (STT).\"\"\"
    try:
        import speech_recognition as sr
        r = sr.Recognizer()
        return {"name": "STT", "status": "ok", "details": "SpeechRecognition loaded", "repairable": True}
    except ImportError:
        return {"name": "STT", "status": "error", "details": "SpeechRecognition not installed", "repairable": True}
    except Exception as e:
        return {"name": "STT", "status": "error", "details": str(e), "repairable": True}

# TTS check (safe)
def check_tts():
    \"\"\"Check Text-to-Speech (TTS).\"\"\"
    try:
        import pyttsx3
        engine = pyttsx3.init()
        return {"name": "TTS", "status": "ok", "details": "pyttsx3 loaded", "repairable": True}
    except ImportError:
        return {"name": "TTS", "status": "error", "details": "pyttsx3 not installed", "repairable": True}
    except Exception as e:
        return {"name": "TTS", "status": "error", "details": str(e), "repairable": True}

def check_dependencies():
    \"\"\"Check required packages.\"\"\"
    from tools.dep_manager import check_dependencies
    deps = check_dependencies()
    status = "ok" if deps["all_installed"] else "error"
    details = f"{len(deps['missing_packages'])} missing: {deps['missing_packages']}"
    return {"name": "Dependencies", "status": status, "details": details, "repairable": True}

def check_tool_modules():
    \"\"\"Check critical tool modules.\"\"\"
    tool_modules = [
        "tools.voice_tts", "tools.voice_stt", "tools.system_stats",
        "tools.file_status", "tools.self_repair", "tools.code_tools"
    ]
    broken = []
    for mod_name in tool_modules:
        try:
            importlib.import_module(mod_name)
        except ImportError as e:
            broken.append({"module": mod_name, "error": str(e)})
    status = "ok" if not broken else "error"
    details = f"{len(broken)} broken modules"
    return {"name": "Tool Modules", "status": status, "details": details, "repairable": True}

def check_tools():
    \"\"\"Comprehensive tool check.\"\"\"
    checks = [check_code_tools, check_dependencies, check_tool_modules]
    results = []
    errors = 0
    for chk in checks:
        r = chk()
        results.append(r)
        if r["status"] == "error":
            errors += 1
    status = "ok" if errors == 0 else "error"
    return {"name": "Tools", "status": status, "details": f"{errors} tool errors", "components": results, "repairable": True}

# FULL DIAGNOSTICS
def run_full_diagnostics():
    \"\"\"Run complete VOID diagnostics.\"\"\"
    all_checks = [
        check_backend_status,
        check_ollama_status,
        check_stt,
        check_tts, 
        check_memory,
        check_dependencies,
        check_tool_modules,
        check_codebase_map,
        check_tools
    ]
    
    results = []
    components = {}
    total_issues = 0
    
    for chk in all_checks:
        try:
            r = chk()
            results.append(r)
            comp_name = r["name"]
            components[comp_name] = r
            if r["status"] == "error":
                total_issues += 1
        except Exception as e:
            components["unknown"] = {"status": "error", "details": str(e)}
            total_issues += 1
    
    overall_status = "healthy" if total_issues == 0 else "degraded" if total_issues < 3 else "critical"
    
    return {
        "overall_status": overall_status,
        "status": "ok",
        "total_issues": total_issues,
        "components": components,
        "summary": {"checks": len(all_checks), "issues": total_issues},
        "results": results
    }

# Legacy compatibility
def run_diagnostics():
    return run_full_diagnostics()

def format_diagnostics(result):
    lines = ["=" * 50, "VOID FULL DIAGNOSTICS", "=" * 50]
    s = result.get("summary", {})
    lines.append(f"Overall: {result.get('overall_status', 'unknown').upper()}")
    lines.append(f"Issues: {s.get('issues', 0)}/{s.get('checks', 0)}")
    lines.append("")
    
    components = result.get("components", {})
    for name, comp in components.items():
        sym = "✓" if comp.get("status") == "ok" else "⚠" if comp.get("status") == "warning" else "✗"
        details = comp.get("details", "")
        lines.append(f"{sym} {name}: {details}")
    
    lines.append("=" * 50)
    return "\n".join(lines)

def list_modules():
    map_file = os.path.join(VOID_ROOT, "data", "codebase_map.json")
    if not os.path.exists(map_file):
        return "No map. Run 'scan project' first."
    try:
        with open(map_file) as f:
            m = json.load(f)
        lines = ["=" * 50, f"{len(m)} MODULES FOUND", "=" * 50]
        for mod in sorted(m.keys()):
            lines.append(f"  {mod}")
        lines.append("=" * 50)
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"

def show_codebase_map():
    return list_modules()
