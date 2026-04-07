"""
VOID Diagnostics Module
======================

Safe, non-destructive system diagnostics.
Checks backend services, STT, TTS, memory, dependencies, and tools.

Enhanced with:
- Python dependency checks
- Tool module integrity checks
- Extended repair capabilities
"""

import os
import sys
import requests
import importlib
from typing import Dict, Any, List

# Backend URL for health check
OLLAMA_URL = "http://127.0.0.1:11434/api/tags"
BACKEND_URL = "http://127.0.0.1:8000"


def check_backend() -> Dict[str, Any]:
    """
    Check if backend services are healthy.
    Returns:
        {
            "status": "ok" | "error",
            "details": "...",
            "repairable": True/False
        }
    """
    details = []
    repairable = False
    
    # Check Ollama
    try:
        r = requests.get(OLLAMA_URL, timeout=3)
        if r.status_code == 200:
            details.append("Ollama: OK")
        else:
            details.append(f"Ollama: HTTP {r.status_code}")
    except requests.exceptions.ConnectionError:
        details.append("Ollama: Not running")
    except requests.exceptions.Timeout:
        details.append("Ollama: Timeout")
    except Exception as e:
        details.append(f"Ollama: {str(e)}")
    
    # Check FastAPI backend
    try:
        r = requests.get(f"{BACKEND_URL}/health", timeout=3)
        if r.status_code == 200:
            details.append("Backend: OK")
        else:
            details.append(f"Backend: HTTP {r.status_code}")
    except requests.exceptions.ConnectionError:
        details.append("Backend: Not running")
    except requests.exceptions.Timeout:
        details.append("Backend: Timeout")
    except Exception as e:
        details.append(f"Backend: {str(e)}")
    
    # Determine status
    all_ok = any("OK" in d for d in details)
    status = "ok" if all_ok else "error"
    
    return {
        "status": status,
        "details": " | ".join(details) if details else "No checks performed",
        "repairable": False  # Backend services cannot be reinitialized by app
    }


def check_stt() -> Dict[str, Any]:
    """
    Check if SpeechRecognition + microphone available.
    Attempts lightweight initialization.
    """
    details = []
    repairable = True
    
    try:
        import speech_recognition as sr
        
        # Try to create recognizer
        recognizer = sr.Recognizer()
        details.append("Recognizer: OK")
        
        # Try to get microphone list
        mics = sr.Microphone.list_microphone_names()
        if mics and len(mics) > 0:
            details.append(f"Microphones: {len(mics)} found")
        else:
            details.append("Microphones: None found")
            repairable = False
            
    except ImportError:
        details.append("SpeechRecognition: Not installed")
        repairable = False
    except AttributeError:
        details.append("SpeechRecognition: Version incompatible")
        repairable = False
    except Exception as e:
        details.append(f"STT Error: {str(e)}")
        repairable = True  # May be fixable by reinit
    
    status = "ok" if "Recognizer: OK" in details else "error"
    
    return {
        "status": status,
        "details": " | ".join(details),
        "repairable": repairable
    }


def check_tts() -> Dict[str, Any]:
    """
    Check if pyttsx3 engine is initialized.
    """
    details = []
    repairable = True
    
    try:
        import pyttsx3
        
        # Try to init engine (non-destructive)
        engine = pyttsx3.init()
        if engine:
            details.append("pyttsx3: OK")
            # Don't run engine, just check it exists
            try:
                engine.stop()
            except:
                pass
        else:
            details.append("pyttsx3: Failed to initialize")
            
    except ImportError:
        details.append("pyttsx3: Not installed")
        repairable = False
    except Exception as e:
        details.append(f"TTS Error: {str(e)}")
        repairable = True
    
    status = "ok" if "pyttsx3: OK" in details else "error"
    
    return {
        "status": status,
        "details": " | ".join(details),
        "repairable": repairable
    }


def check_memory() -> Dict[str, Any]:
    """
    Check memory file accessibility (memory.json).
    """
    details = []
    repairable = True
    
    memory_file = "data/memory.json"
    
    # Check if directory exists
    data_dir = os.path.dirname(memory_file)
    if not os.path.exists(data_dir):
        details.append("Data directory: Missing")
        # Try to create
        try:
            os.makedirs(data_dir, exist_ok=True)
            details.append("Data directory: Created")
        except Exception as e:
            details.append(f"Cannot create directory: {e}")
            repairable = False
    else:
        details.append("Data directory: OK")
    
    # Check if file exists
    if os.path.exists(memory_file):
        details.append("Memory file: Exists")
        # Try to read
        try:
            with open(memory_file, "r") as f:
                data = f.read()
                if data:
                    details.append("Memory file: Readable")
                else:
                    details.append("Memory file: Empty")
        except PermissionError:
            details.append("Memory file: Permission denied")
            repairable = False
        except Exception as e:
            details.append(f"Memory file: {str(e)}")
    else:
        details.append("Memory file: Not found")
        # Try to create
        try:
            with open(memory_file, "w") as f:
                f.write('{"facts": []}')
            details.append("Memory file: Created")
        except Exception as e:
            details.append(f"Cannot create: {str(e)}")
            repairable = False
    
    # Check writeability
    if os.path.exists(memory_file):
        try:
            with open(memory_file, "a") as f:
                f.write("")
            details.append("Memory file: Writable")
        except Exception as e:
            details.append(f"Memory file: Not writable - {str(e)}")
            repairable = False
    
    status = "ok" if any("OK" in d or "Created" in d or "Writable" in d for d in details) else "error"
    
    return {
        "status": status,
        "details": " | ".join(details),
        "repairable": repairable
    }


def check_dependencies() -> Dict[str, Any]:
    """
    Check if required Python dependencies are installed.
    """
    details = []
    repairable = True
    
    required_packages = [
        "fastapi",
        "uvicorn",
        "requests",
        "pyttsx3",
        "speech_recognition",
        "psutil",
        "pydantic"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            details.append(f"{package}: OK")
        except ImportError:
            details.append(f"{package}: Missing")
            missing_packages.append(package)
            repairable = True
    
    status = "ok" if not missing_packages else "error"
    
    return {
        "status": status,
        "details": " | ".join(details),
        "repairable": repairable,
        "missing_packages": missing_packages
    }


def check_tool_modules() -> Dict[str, Any]:
    """
    Check if all tool modules can be imported.
    """
    details = []
    repairable = True
    
    tool_modules = [
        "tools.voice_tts",
        "tools.voice_stt",
        "tools.system_stats",
        "tools.file_status",
        "tools.diagnostics",
        "tools.self_repair",
        "tools.system_tools",
    ]
    
    broken_modules = []
    
    for module_name in tool_modules:
        try:
            importlib.import_module(module_name)
            details.append(f"{module_name}: OK")
        except ImportError as e:
            details.append(f"{module_name}: Import failed")
            broken_modules.append({"module": module_name, "error": str(e)})
        except Exception as e:
            details.append(f"{module_name}: Error - {str(e)}")
            broken_modules.append({"module": module_name, "error": str(e)})
    
    status = "ok" if not broken_modules else "error"
    
    return {
        "status": status,
        "details": " | ".join(details),
        "repairable": len(broken_modules) > 0,
        "broken_modules": broken_modules
    }


def check_internet() -> Dict[str, Any]:
    """
    Check internet connectivity.
    """
    details = []
    repairable = False
    
    try:
        r = requests.get("http://www.google.com", timeout=5)
        if r.status_code == 200:
            details.append("Internet: Connected")
            status = "ok"
        else:
            details.append(f"Internet: HTTP {r.status_code}")
            status = "error"
    except requests.exceptions.ConnectionError:
        details.append("Internet: Not connected")
        status = "error"
    except requests.exceptions.Timeout:
        details.append("Internet: Timeout")
        status = "error"
    except Exception as e:
        details.append(f"Internet: {str(e)}")
        status = "error"
    
    return {
        "status": status,
        "details": " | ".join(details),
        "repairable": repairable
    }


def run_full_diagnostics() -> Dict[str, Any]:
    """
    Run all diagnostics checks - EXACT SPEC FORMAT.
    Returns:
        {
            "status": "ok" | "error",
            "issues": [...],
            "details": {
                "backend": "ok",
                "stt": "ok",
                "tts": "ok", 
                "memory": "ok",
                "system": "ok"
            }
        }
    """
    components = {
        "backend": check_backend(),
        "stt": check_stt(),
        "tts": check_tts(),
        "memory": check_memory(),
        "dependencies": check_dependencies(),
        "tool_modules": check_tool_modules(),
        "internet": check_internet()
    }
    
    # Exact spec format
    details = {}
    issues = []
    
    for name, data in components.items():
        status = data["status"]
        details[name] = status
        
        if status == "error":
            issues.append({
                "component": name,
                "status": status,
                "details": data["details"]
            })
    
    # System info with psutil/platform
    system_details = _get_system_info()
    details["system"] = "ok" if not system_details["error"] else "error"
    if system_details["error"]:
        issues.append({
            "component": "system",
            "status": "error",
            "details": system_details["message"]
        })
    
    overall_status = "ok" if not issues else "error"
    
    return {
        "status": overall_status,
        "issues": issues,
        "details": details
    }


def _get_system_info() -> Dict[str, Any]:
    """Get real system info with psutil/platform."""
    result = {"error": False, "message": ""}
    try:
        import platform
        import psutil
        
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        os_name = platform.system()
        
        result["cpu"] = cpu
        result["ram"] = ram
        result["os"] = os_name
        result["message"] = f"CPU: {cpu}%, RAM: {ram}%, OS: {os_name}"
        
    except ImportError as e:
        result["error"] = True
        result["message"] = f"Missing psutil/platform: {str(e)}"
    except Exception as e:
        result["error"] = True
        result["message"] = f"System info error: {str(e)}"
    
    return result


def get_diagnostics() -> Dict[str, Any]:
    """Get full diagnostics as dict."""
    return run_full_diagnostics()


def get_quick_status() -> Dict[str, Any]:
    """
    Get quick status summary for UI display.
    """
    diag = run_full_diagnostics()
    
    # Create summary
    summary = {
        "overall": diag.get("overall_status", "unknown"),
        "backend": diag.get("components", {}).get("backend", {}).get("status", "unknown"),
        "voice": "ok" if all([
            diag.get("components", {}).get("stt", {}).get("status") == "ok",
            diag.get("components", {}).get("tts", {}).get("status") == "ok"
        ]) else "error",
        "memory": diag.get("components", {}).get("memory", {}).get("status", "unknown"),
        "issues": diag.get("total_issues", 0)
    }
    
    return summary


if __name__ == "__main__":
    # Test diagnostics
    import json
    result = run_full_diagnostics()
    print(json.dumps(result, indent=2))
