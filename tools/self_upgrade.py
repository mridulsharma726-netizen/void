"""
VOID Self-Upgrade Module
======================

VOID can upgrade itself when commanded.

Capabilities:
1. Check current version
2. Check for dependency updates
3. Install missing dependencies
4. Pull latest project files (if git repo exists)
5. Verify upgrade

Command:
VOID upgrade yourself
"""

import subprocess
import sys
import os
import logging
from typing import Dict, Any, List
import importlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VOID-SelfUpgrade")


def get_current_version() -> str:
    """Get current VOID version."""
    # Check package.json for version
    try:
        import json
        package_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "package.json")
        if os.path.exists(package_path):
            with open(package_path, "r") as f:
                data = json.load(f)
                return data.get("version", "1.0.0")
    except Exception:
        pass
    
    return "1.0.0"


def check_dependencies() -> Dict[str, Any]:
    """
    Check for missing or outdated dependencies.
    """
    required = [
        "fastapi",
        "uvicorn", 
        "requests",
        "pyttsx3",
        "speech_recognition",
        "psutil",
        "pydantic"
    ]
    
    missing = []
    installed = []
    
    for package in required:
        try:
            importlib.import_module(package)
            installed.append(package)
        except ImportError:
            missing.append(package)
    
    return {
        "status": "ok" if not missing else "missing",
        "installed": installed,
        "missing": missing
    }


def install_dependencies() -> Dict[str, Any]:
    """
    Install missing dependencies using pip.
    """
    dep_check = check_dependencies()
    missing = dep_check.get("missing", [])
    
    if not missing:
        return {
            "status": "ok",
            "message": "All dependencies already installed"
        }
    
    installed = []
    failed = []
    
    for package in missing:
        try:
            # Install package
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", package],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            installed.append(package)
            logger.info(f"[UPGRADE] Installed {package}")
        except subprocess.CalledProcessError as e:
            failed.append(package)
            logger.error(f"[UPGRADE] Failed to install {package}: {e}")
    
    if failed:
        return {
            "status": "partial",
            "message": f"Installed {len(installed)} packages, failed: {failed}",
            "installed": installed,
            "failed": failed
        }
    
    return {
        "status": "ok",
        "message": f"Successfully installed {len(installed)} packages: {installed}",
        "installed": installed
    }


def check_git_updates() -> Dict[str, Any]:
    """
    Check if git repository has updates.
    Returns info about git status.
    """
    project_root = os.path.dirname(os.path.dirname(__file__))
    git_dir = os.path.join(project_root, ".git")
    
    if not os.path.exists(git_dir):
        return {
            "is_git_repo": False,
            "message": "Not a git repository"
        }
    
    try:
        # Check git status
        result = subprocess.run(
            ["git", "status"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Check if there are changes
        is_dirty = "nothing to commit" not in result.stdout
        
        # Try to get current branch
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10
        )
        branch = branch_result.stdout.strip() or "unknown"
        
        return {
            "is_git_repo": True,
            "has_changes": is_dirty,
            "branch": branch,
            "status": result.stdout
        }
        
    except Exception as e:
        return {
            "is_git_repo": True,
            "error": str(e)
        }


def pull_updates() -> Dict[str, Any]:
    """
    Pull latest updates from git repository.
    """
    project_root = os.path.dirname(os.path.dirname(__file__))
    git_dir = os.path.join(project_root, ".git")
    
    if not os.path.exists(git_dir):
        return {
            "status": "error",
            "message": "Not a git repository, cannot pull updates"
        }
    
    try:
        # Pull latest changes
        result = subprocess.run(
            ["git", "pull"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            return {
                "status": "ok",
                "message": "Successfully pulled updates",
                "output": result.stdout
            }
        else:
            return {
                "status": "error",
                "message": "Failed to pull updates",
                "error": result.stderr
            }
            
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "message": "Git pull timed out"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Git error: {str(e)}"
        }


def verify_installation() -> Dict[str, Any]:
    """
    Verify VOID installation is working.
    """
    results = {
        "backend": False,
        "llm": False,
        "voice": False,
        "memory": False
    }
    
    # Check backend
    try:
        import requests
        r = requests.get("http://127.0.0.1:8000/health", timeout=3)
        results["backend"] = r.status_code == 200
    except:
        pass
    
    # Check LLM
    try:
        import requests
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
        results["llm"] = r.status_code == 200
    except:
        pass
    
    # Check voice (TTS)
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.stop()
        results["voice"] = True
    except:
        pass
    
    # Check memory
    try:
        memory_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "memory.json")
        results["memory"] = os.path.exists(memory_file)
    except:
        pass
    
    all_ok = all(results.values())
    
    return {
        "status": "ok" if all_ok else "issues",
        "components": results
    }


def upgrade_system() -> Dict[str, Any]:
    """
    Main upgrade function.
    
    Flow:
    1. Check current version
    2. Check dependencies
    3. Install missing dependencies
    4. Check for git updates
    5. Pull updates if available
    6. Verify installation
    """
    logger.info("[UPGRADE] Starting system upgrade...")
    
    steps_completed = []
    errors = []
    
    # Step 1: Check version
    version = get_current_version()
    steps_completed.append(f"Current version: {version}")
    logger.info(f"[UPGRADE] Current version: {version}")
    
    # Step 2: Check dependencies
    dep_result = check_dependencies()
    steps_completed.append(f"Dependency check: {dep_result.get('status')}")
    
    if dep_result.get("missing"):
        logger.info(f"[UPGRADE] Missing packages: {dep_result['missing']}")
        
        # Step 3: Install missing
        install_result = install_dependencies()
        steps_completed.append(f"Install: {install_result.get('message', '')}")
        
        if install_result.get("status") == "error":
            errors.append(install_result.get("message", "Install failed"))
    
    # Step 4: Check git updates
    git_result = check_git_updates()
    if git_result.get("is_git_repo"):
        steps_completed.append(f"Git: on branch {git_result.get('branch', 'unknown')}")
        
        if git_result.get("has_changes"):
            logger.info("[UPGRADE] Local changes detected")
    
    # Step 5: Verify installation
    verify_result = verify_installation()
    steps_completed.append(f"Verification: {verify_result.get('status')}")
    
    # Determine final status
    if errors:
        status = "error"
        message = f"Upgrade completed with errors: {'; '.join(errors)}"
    elif verify_result.get("status") == "ok":
        status = "ok"
        message = "System upgraded successfully. All components verified."
    else:
        status = "partial"
        issues = [k for k, v in verify_result.get("components", {}).items() if not v]
        message = f"Upgrade completed but some issues remain: {', '.join(issues)}"
    
    result = {
        "status": status,
        "message": message,
        "version": version,
        "steps": steps_completed,
        "verification": verify_result
    }
    
    logger.info(f"[UPGRADE] Completed: {status}")
    
    return result


def get_upgrade_info() -> Dict[str, Any]:
    """
    Get upgrade information without performing upgrade.
    """
    version = get_current_version()
    deps = check_dependencies()
    git = check_git_updates()
    
    return {
        "current_version": version,
        "dependencies": deps,
        "git_info": git
    }


if __name__ == "__main__":
    # Test upgrade
    import json
    
    print("=" * 50)
    print("VOID Self-Upgrade Test")
    print("=" * 50)
    
    # Get info
    info = get_upgrade_info()
    print("\nUpgrade Info:")
    print(json.dumps(info, indent=2))
    
    # Run upgrade
    print("\nRunning upgrade...")
    result = upgrade_system()
    print("\nUpgrade Result:")
    print(json.dumps(result, indent=2))

