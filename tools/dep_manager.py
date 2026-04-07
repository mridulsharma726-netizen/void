"""
VOID Dependency Manager
======================

Auto-installs missing Python packages from requirements.txt
"""

import subprocess
import sys
import os
from typing import Dict, Any

REQUIREMENTS_PATH = "requirements.txt"

def check_dependencies() -> Dict[str, Any]:
    "Check which packages from requirements.txt are missing."

    missing = []
    try:
        with open(REQUIREMENTS_PATH, 'r') as f:
            required = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        for pkg in required:
            try:
                __import__(pkg.split('==')[0].split('>=')[0].split('<=')[0])
            except ImportError:
                missing.append(pkg)
    except FileNotFoundError:
        pass
    
    return {
        "required": required if 'required' in locals() else [],
        "missing_packages": missing,
        "all_installed": len(missing) == 0
    }

def install_dependencies() -> Dict[str, Any]:
    "Install missing dependencies."

    check = check_dependencies()
    missing = check["missing_packages"]
    
    installed = []
    failed = []
    
    for pkg in missing:
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", pkg
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            installed.append(pkg)
        except subprocess.CalledProcessError:
            failed.append(pkg)
    
    return {
        "installed": installed,
        "failed": failed,
        "success": len(failed) == 0
    }

if __name__ == "__main__":
    print("Checking dependencies...")
    deps = check_dependencies()
    print(f"Missing: {deps['missing_packages']}")
    
    if deps["missing_packages"]:
        print("Installing...")
        result = install_dependencies()
        print(f"Installed: {result['installed']}")
        print(f"Failed: {result['failed']}")
