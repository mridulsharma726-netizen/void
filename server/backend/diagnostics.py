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
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
ROOT_DIR = Path(__file__).parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Backend URL for health check
OLLAMA_URL = "http://127.0.0.1:11434/api/tags"
BACKEND_URL = "http://127.0.0.1:8002"


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
        details.append(f"Ollama Error: {str(e)}")

    # Check Backend
    # If we are already running inside the backend process, it is guaranteed to be online.
    # This prevents self-request deadlocks in single-threaded uvicorn environments.
    if "server.main" in sys.modules or "uvicorn" in sys.modules:
        details.append("Backend: OK")
    else:
        backend_ok = False
        for port in [8003, 8002]:
            try:
                r = requests.get(f"http://127.0.0.1:{port}/health", timeout=2)
                if r.status_code == 200:
                    details.append("Backend: OK")
                    backend_ok = True
                    break
            except Exception:
                continue
        if not backend_ok:
            details.append("Backend: Not running")
    
    # Determine status
    all_ok = all("OK" in d for d in details)
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
    Check if pyttsx3 engine and edge_tts are initialized.
    """
    details = []
    repairable = True
    
    try:
        import pyttsx3
        engine = pyttsx3.init()
        if engine:
            details.append("pyttsx3: OK")
            try:
                engine.stop()
            except:
                pass
        else:
            details.append("pyttsx3: Failed to initialize")
    except ImportError:
        details.append("pyttsx3: Not installed")
    except Exception as e:
        details.append(f"pyttsx3 Error: {str(e)}")

    try:
        import edge_tts
        details.append("edge-tts: OK")
    except ImportError:
        details.append("edge-tts: Not installed")
        repairable = False
    except Exception as e:
        details.append(f"edge-tts Error: {str(e)}")
        
    status = "ok" if ("pyttsx3: OK" in details or "edge-tts: OK" in details) else "error"
    
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
    
    memory_file = str(Path(__file__).parent.parent.parent / "memory" / "data" / "memory.json")
    
    # Check if directory exists
    data_dir = os.path.dirname(memory_file)
    if not os.path.exists(data_dir):
        details.append("Data directory: Missing")
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
    sys_issues = []
    if not system_details["error"]:
        if system_details.get("cpu", 0) > 95:
            sys_issues.append(f"CPU usage critical ({system_details['cpu']:.1f}%)")
        if system_details.get("ram", 0) > 95:
            sys_issues.append(f"RAM usage critical ({system_details['ram']:.1f}%)")
        if system_details.get("disk", 0) > 95:
            sys_issues.append(f"Disk storage critically low ({system_details['disk']:.1f}%)")

    if system_details["error"] or sys_issues:
        details["system"] = "error"
        issues.append({
            "component": "system",
            "status": "error",
            "details": "; ".join(sys_issues) if sys_issues else system_details["message"]
        })
    else:
        details["system"] = "ok"
    
    overall_status = "ok" if not issues else "error"
    
    return {
        "status": overall_status,
        "issues": issues,
        "details": details,
        "components": components
    }


def _get_system_info() -> Dict[str, Any]:
    """Get real system info with psutil/platform."""
    result = {"error": False, "message": ""}
    try:
        import platform
        import psutil
        
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage(os.path.abspath(os.sep))
        disk_pct = disk.percent
        os_name = platform.system()
        
        battery = psutil.sensors_battery()
        battery_pct = battery.percent if battery else None
        
        result["cpu"] = cpu
        result["ram"] = ram
        result["disk"] = disk_pct
        result["os"] = os_name
        
        msg = f"CPU: {cpu:.1f}%, RAM: {ram:.1f}%, Disk: {disk_pct:.1f}%, OS: {os_name}"
        if battery_pct is not None:
            msg += f", Battery: {battery_pct}%"
        result["message"] = msg
        
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
    details = diag.get("details", {})
    issues = diag.get("issues", [])
    
    # Create summary
    summary = {
        "overall": diag.get("status", "unknown"),
        "backend": details.get("backend", "unknown"),
        "voice": "ok" if all([
            details.get("stt") == "ok",
            details.get("tts") == "ok"
        ]) else "error",
        "memory": details.get("memory", "unknown"),
        "issues": len(issues)
    }
    
    return summary


class DiagnosticsEngine:
    """
    Diagnostics Orchestrator Class.
    Maintains API compatibility with expected consumer classes.
    """
    async def run(self) -> Dict[str, Any]:
        """Run full system diagnostics asynchronously."""
        return run_full_diagnostics()


if __name__ == "__main__":
    # Test diagnostics
    import json
    result = run_full_diagnostics()
    print(json.dumps(result, indent=2))
