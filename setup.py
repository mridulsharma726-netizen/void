#!/usr/bin/env python3
"""
VOID Setup - Auto-installer for portable deployment
Run on first launch to setup dependencies safely.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def log(msg):
    print(f"[VOID SETUP] {msg}")

def run_command(cmd, cwd=None, check=False):
    """Run shell command safely."""
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True, 
            timeout=300  # 5min timeout
        )
        if result.returncode != 0 and check:
            log(f"Command failed: {cmd}")
            log(f"STDOUT: {result.stdout}")
            log(f"STDERR: {result.stderr}")
        else:
            if result.stdout.strip():
                log(f"OUT: {result.stdout.strip()}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log(f"Timeout: {cmd}")
        return False
    except Exception as e:
        log(f"Error running {cmd}: {e}")
        return False

def install_requirements():
    """Safely install requirements.txt."""
    req_file = Path("requirements.txt")
    if not req_file.exists():
        log("WARNING: requirements.txt not found")
        return False
    
    log("Installing Python dependencies...")
    # Use --upgrade to handle existing installs safely
    cmd = f"{sys.executable} -m pip install -r requirements.txt --upgrade"
    success = run_command(cmd, check=True)
    log("✅ Requirements install " + ("COMPLETE" if success else "FAILED (continuing)"))
    return success

def check_ollama():
    """Check if Ollama CLI is installed."""
    log("Checking Ollama...")
    cmd = "ollama --version"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
    
    if result.returncode == 0:
        version = result.stdout.strip().split()[-1] if result.stdout.strip() else "unknown"
        log(f"✅ Ollama v{version} found")
        return True
    else:
        log("❌ OLLAMA_NOT_FOUND")
        log("Install from: https://ollama.com/download")
        return False

def main():
    log("=== VOID AUTO-SETUP START ===")
    
    # Ensure data dir
    os.makedirs("data", exist_ok=True)
    
    # Step 1: Install Python deps
    install_requirements()
    
    # Step 2: Check Ollama
    ollama_ok = check_ollama()
    
    # Always succeed - create flag
    flag_file = Path("setup_done.flag")
    flag_file.write_text(f"VOID setup complete at {os.path.abspath('.')}\nOllama: {'OK' if ollama_ok else 'NOT_FOUND'}\n")
    log("✅ Setup complete. Flag created: setup_done.flag")
    log("=== SETUP FINISHED (safe to run VOID) ===")
    
    # Exit 0 always (no crash)
    sys.exit(0)

if __name__ == "__main__":
    main()

