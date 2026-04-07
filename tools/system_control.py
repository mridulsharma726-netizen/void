"""
VOID System Control Module
====================

Advanced PC control: process management, file operations, system utilities.

Functions:
- list_running_apps() -> List[dict]
- close_app(name) -> dict
- kill_heavy_process() -> dict
- clean_temp_files() -> dict
- open_common_folder(name) -> dict
- get_system_usage() -> dict
"""

import os
import sys
import shutil
import logging
import psutil
import subprocess
import tempfile
from typing import List, Dict, Any
from datetime import datetime

# Configure logging
logger = logging.getLogger("VOID-SystemControl")

# Protected system processes that should never be killed
PROTECTED_PROCESSES = [
    "system", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe",
    "svchost.exe", "winlogon.exe", "dwm.exe", "explorer.exe",
    "taskhostw.exe", "RuntimeBroker.exe", "SearchIndexer.exe",
    "sihost.exe", "ctfmon.exe", "conhost.exe", "dllhost.exe",
    "fontdrvhost.exe", "wmiprvse.exe", "audiodg.exe", "Memory Compression"
]


def _is_protected(process_name: str) -> bool:
    """Check if a process is protected (system essential)."""
    process_lower = process_name.lower()
    for protected in PROTECTED_PROCESSES:
        if protected.lower() in process_lower:
            return True
    return False


# ============================================================================
# PROCESS MANAGEMENT
# ============================================================================

def list_running_apps(limit: int = 20) -> List[Dict[str, Any]]:
    """
    List running applications/processes.
    
    Returns:
        List of dicts with pid, name, cpu_percent, memory_percent
    """
    processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            info = proc.info
            # Skip system processes
            if not _is_protected(info['name']):
                processes.append({
                    'pid': info['pid'],
                    'name': info['name'],
                    'cpu': info.get('cpu_percent') or 0,
                    'memory': info.get('memory_percent') or 0
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    # Sort by CPU usage descending
    processes.sort(key=lambda x: x['cpu'], reverse=True)
    
    return processes[:limit]


def list_all_processes() -> List[Dict[str, Any]]:
    """List all running processes including system ones."""
    processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
        try:
            info = proc.info
            processes.append({
                'pid': info['pid'],
                'name': info['name'],
                'cpu': round(info.get('cpu_percent') or 0, 1),
                'memory': round(info.get('memory_percent') or 0, 1),
                'status': info.get('status', 'unknown')
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    return processes


def close_app(name: str) -> Dict[str, Any]:
    """
    Close an application by name.
    
    Args:
        name: Application name (e.g., "chrome", "notepad")
        
    Returns:
        Dict with status and closed app name
    """
    name_lower = name.lower()
    closed = []
    
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            proc_name = proc.info['name']
            if name_lower in proc_name.lower() and not _is_protected(proc_name):
                proc.kill()
                closed.append(proc_name)
                logger.info(f"[SYSTEM CONTROL] Closed: {proc_name}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            pass
    
    if closed:
        # Remove duplicates
        closed = list(set(closed))
        return {
            "status": "ok",
            "closed": ", ".join(closed),
            "count": len(closed)
        }
    else:
        return {
            "status": "error",
            "message": f"Could not find or close '{name}'"
        }


def kill_heavy_process(count: int = 1) -> Dict[str, Any]:
    """
    Kill the highest CPU consuming process(es).
    
    Args:
        count: Number of processes to kill (default 1)
        
    Returns:
        Dict with killed process names
    """
    processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            info = proc.info
            if not _is_protected(info['name']):
                processes.append({
                    'pid': info['pid'],
                    'name': info['name'],
                    'cpu': info.get('cpu_percent') or 0
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    # Sort by CPU usage
    processes.sort(key=lambda x: x['cpu'], reverse=True)
    
    killed = []
    for proc in processes[:count]:
        try:
            p = psutil.Process(proc['pid'])
            p.kill()
            killed.append(proc['name'])
            logger.info(f"[SYSTEM CONTROL] Killed heavy process: {proc['name']} (CPU: {proc['cpu']}%)")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if killed:
        return {
            "status": "ok",
            "killed": killed,
            "count": len(killed)
        }
    else:
        return {
            "status": "error",
            "message": "No processes could be killed"
        }


def get_process_info(pid: int) -> Dict[str, Any]:
    """Get detailed info about a specific process."""
    try:
        proc = psutil.Process(pid)
        return {
            "pid": proc.pid,
            "name": proc.name(),
            "cpu": proc.cpu_percent(interval=0.1),
            "memory_mb": proc.memory_info().rss / 1024 / 1024,
            "status": proc.status(),
            "create_time": datetime.fromtimestamp(proc.create_time()).isoformat(),
            "cmdline": proc.cmdline()
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        return {"status": "error", "message": str(e)}


# ============================================================================
# FILE OPERATIONS
# ============================================================================

def clean_temp_files() -> Dict[str, Any]:
    """
    Clean temporary files from system temp directories.
    
    Returns:
        Dict with cleaning results
    """
    cleaned_files = 0
    cleaned_size = 0
    errors = []
    
    # Get temp directories
    temp_dirs = [
        tempfile.gettempdir(),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Temp'),
        "C:/Windows/Temp"
    ]
    
    for temp_dir in temp_dirs:
        if not os.path.exists(temp_dir):
            continue
            
        try:
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                try:
                    if os.path.isfile(item_path):
                        size = os.path.getsize(item_path)
                        os.remove(item_path)
                        cleaned_files += 1
                        cleaned_size += size
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        cleaned_files += 1
                except (PermissionError, OSError) as e:
                    errors.append(f"{item}: {str(e)}")
        except Exception as e:
            errors.append(f"Dir {temp_dir}: {str(e)}")
    
    cleaned_mb = cleaned_size / 1024 / 1024
    
    return {
        "status": "ok",
        "files_cleaned": cleaned_files,
        "size_mb": round(cleaned_mb, 2),
        "errors": errors[:5]  # Limit error count
    }


def clean_browser_cache(browser: str = "all") -> Dict[str, Any]:
    """
    Clean browser cache.
    
    Args:
        browser: "chrome", "firefox", "edge", or "all"
    """
    cleaned = []
    
    user_home = os.path.expanduser("~")
    
    browser_paths = {
        "chrome": os.path.join(user_home, "AppData", "Local", "Google", "Chrome", "User Data", "Default", "Cache"),
        "firefox": os.path.join(user_home, "AppData", "Local", "Mozilla", "Firefox", "Profiles"),
        "edge": os.path.join(user_home, "AppData", "Local", "Microsoft", "Edge", "User Data", "Default", "Cache")
    }
    
    if browser == "all":
        targets = browser_paths
    else:
        targets = {browser: browser_paths.get(browser, "")}
    
    for name, path in targets.items():
        if not path or not os.path.exists(path):
            continue
            
        try:
            size_before = sum(os.path.getsize(os.path.join(dirpath, f)) 
                            for dirpath, _, files in os.walk(path) 
                            for f in files)
            
            # Just report, don't actually delete to be safe
            cleaned.append({
                "browser": name,
                "cache_size_mb": round(size_before / 1024 / 1024, 2),
                "status": "detected"
            })
        except Exception as e:
            cleaned.append({"browser": name, "error": str(e)})
    
    return {
        "status": "ok",
        "browsers": cleaned
    }


def get_disk_usage(path: str = "C:") -> Dict[str, Any]:
    """Get disk usage for a drive."""
    try:
        usage = psutil.disk_usage(path)
        return {
            "path": path,
            "total_gb": round(usage.total / 1024**3, 2),
            "used_gb": round(usage.used / 1024**3, 2),
            "free_gb": round(usage.free / 1024**3, 2),
            "percent": usage.percent
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============================================================================
# COMMON FOLDERS
# ============================================================================

COMMON_FOLDERS = {
    "desktop": os.path.join(os.path.expanduser("~"), "Desktop"),
    "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
    "documents": os.path.join(os.path.expanduser("~"), "Documents"),
    "pictures": os.path.join(os.path.expanduser("~"), "Pictures"),
    "music": os.path.join(os.path.expanduser("~"), "Music"),
    "videos": os.path.join(os.path.expanduser("~"), "Videos"),
    "projects": os.path.join(os.path.expanduser("~"), "Desktop", "Projects"),
}


def open_common_folder(name: str) -> Dict[str, Any]:
    """
    Open a common Windows folder.
    
    Args:
        name: "desktop", "downloads", "documents", "pictures", "music", "videos", "projects"
    """
    name_lower = name.lower()
    
    if name_lower in COMMON_FOLDERS:
        folder_path = COMMON_FOLDERS[name_lower]
    else:
        return {
            "status": "error",
            "message": f"Unknown folder: {name}"
        }
    
    if not os.path.exists(folder_path):
        # Try to create it
        try:
            os.makedirs(folder_path, exist_ok=True)
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Folder does not exist and could not create: {e}"
            }
    
    try:
        # Open in Explorer
        subprocess.Popen(["explorer", folder_path])
        return {
            "status": "ok",
            "opened": name_lower,
            "path": folder_path
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


def list_folder_contents(path: str = None) -> Dict[str, Any]:
    """List contents of a folder."""
    if not path:
        path = os.path.expanduser("~")
    
    try:
        items = []
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            is_dir = os.path.isdir(item_path)
            items.append({
                "name": item,
                "type": "folder" if is_dir else "file",
                "size_mb": 0 if is_dir else round(os.path.getsize(item_path) / 1024 / 1024, 2)
            })
        
        return {
            "status": "ok",
            "path": path,
            "items": items[:50]  # Limit to 50 items
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============================================================================
# SYSTEM UTILITIES
# ============================================================================

def get_system_usage() -> Dict[str, Any]:
    """Get current system resource usage."""
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        
        return {
            "cpu_percent": cpu,
            "ram_percent": memory.percent,
            "ram_used_gb": round(memory.used / 1024**3, 2),
            "ram_total_gb": round(memory.total / 1024**3, 2),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / 1024**3, 2)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def take_screenshot() -> Dict[str, Any]:
    """Take a screenshot (requires pyautogui)."""
    try:
        import pyautogui
        import datetime
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(os.path.expanduser("~"), "Desktop", f"VOID_screenshot_{timestamp}.png")
        
        pyautogui.screenshot(save_path)
        
        return {
            "status": "ok",
            "saved_to": save_path
        }
    except ImportError:
        return {
            "status": "error",
            "message": "pyautogui not installed"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


def empty_recycle_bin() -> Dict[str, Any]:
    """Empty the Windows Recycle Bin."""
    try:
        import ctypes
        SHEmptyRecycleBin = ctypes.windll.shell32.SHEmptyRecycleBin
        SHEmptyRecycleBin(None, None, 0x00000001 | 0x00000002)  # SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI
        return {"status": "ok", "message": "Recycle bin emptied"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============================================================================
# NATURAL LANGUAGE PARSING
# ============================================================================

def parse_control_command(prompt: str) -> Dict[str, Any]:
    """
    Parse natural language PC control commands.
    
    Handles:
    - "close [app]"
    - "show running apps"
    - "kill heavy process"
    - "clean temp files"
    - "open [folder]"
    """
    prompt_lower = prompt.lower()
    
    # Close app
    if "close" in prompt_lower:
        # Extract app name
        app = prompt_lower.replace("close", "").strip()
        if app:
            return {"action": "close_app", "name": app}
    
    # List processes
    if "running" in prompt_lower and ("app" in prompt_lower or "process" in prompt_lower):
        return {"action": "list_apps"}
    
    # Kill heavy process
    if "kill" in prompt_lower and "heavy" in prompt_lower:
        return {"action": "kill_heavy"}
    
    # Clean temp
    if "clean" in prompt_lower and "temp" in prompt_lower:
        return {"action": "clean_temp"}
    
    # Open folder
    if "open" in prompt_lower and any(f in prompt_lower for f in COMMON_FOLDERS.keys()):
        for folder_name in COMMON_FOLDERS.keys():
            if folder_name in prompt_lower:
                return {"action": "open_folder", "name": folder_name}
    
    # System usage
    if "system" in prompt_lower and "usage" in prompt_lower:
        return {"action": "system_usage"}
    
    return {"action": "unknown"}


if __name__ == "__main__":
    # Test system control
    print("Testing system control...")
    
    # List apps
    print("\n1. Running apps:")
    apps = list_running_apps(5)
    for app in apps:
        print(f"  {app['name']}: CPU {app['cpu']}%")
    
    # System usage
    print("\n2. System usage:")
    usage = get_system_usage()
    print(f"  CPU: {usage.get('cpu_percent')}%")
    print(f"  RAM: {usage.get('ram_percent')}%")
    
    # Disk
    print("\n3. Disk usage:")
    disk = get_disk_usage("C:")
    print(f"  {disk}")

