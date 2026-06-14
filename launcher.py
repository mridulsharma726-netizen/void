#!/usr/bin/env python3
"""
VOID Launcher - Starts backend server + opens UI automatically
Usage: python launcher.py
"""

import os
import sys
import time
import subprocess
import webbrowser
import requests
import signal
import threading

# Ensure VOID root
VOID_ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(VOID_ROOT)
print(f"[LAUNCHER] VOID_ROOT: {VOID_ROOT}")

def check_ollama():
    """Check if Ollama running"""
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        return r.status_code == 200
    except:
        return False

def run_setup():
    """Run setup if needed"""
    setup_flag = os.path.join(VOID_ROOT, "setup_done.flag")
    if os.path.exists(setup_flag):
        print("[LAUNCHER] Setup flag exists, skipping")
        return True
    print("[LAUNCHER] Running setup.py...")
    try:
        result = subprocess.run([sys.executable, "setup.py"], cwd=VOID_ROOT, 
                               capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            print("[LAUNCHER] [OK] Setup complete")
            return True
        else:
            print(f"[LAUNCHER] Setup warning: {result.stderr[:200]}")
    except Exception as e:
        print(f"[LAUNCHER] Setup error: {e}")
    return False

def start_server():
    """Start uvicorn VOID.main:app"""
    cmd = [
        sys.executable, "-m", "uvicorn",
        "server.main:app", 
        "--host", "127.0.0.1",
        "--port", "8003",
        "--reload"
    ]
    print(f"[LAUNCHER] Starting server: {' '.join(cmd)}")
    return subprocess.Popen(cmd, cwd=VOID_ROOT)

def open_ui():
    """Open UI in default browser"""
    ui_path = os.path.join(VOID_ROOT, "app", "ui", "index.html")
    url = f"file:///{ui_path.replace(chr(92), '/').replace(':', '%3A')}"
    print(f"[LAUNCHER] Opening UI: {url}")
    webbrowser.open(url)

def signal_handler(sig, frame):
    print("\n[LAUNCHER] Shutting down...")
    sys.exit(0)

# Main launcher
def main():
    print("=V=O=I=D=  L=A=U=N=C=H=E=R=")
    print("Backend + UI Auto-Start")
    print("=======================")
    
    # Handlers
    signal.signal(signal.SIGINT, signal_handler)
    
    # 1. Setup
    run_setup()
    
    # 2. Ollama check
    ollama_ok = check_ollama()
    print(f"[LAUNCHER] Ollama: {'[OK] ONLINE' if ollama_ok else '[WARN] OFFLINE (chat limited)' }")
    if not ollama_ok:
        print("  Tip: 'ollama serve' then 'ollama pull llama3.2:3b'")
    
    # 3. Start server
    server = start_server()
    
    # 4. Wait startup
    print("[LAUNCHER] Waiting server startup (5s)...")
    time.sleep(5)
    
    # 5. Health check
    try:
        r = requests.get("http://127.0.0.1:8003/health", timeout=2)
        print(f"[LAUNCHER] Backend health: {'[OK] OK' if r.status_code == 200 else f'[FAIL] {r.status_code}'}")
    except Exception as e:
        print(f"[LAUNCHER] Backend health check failed: {e}")
    
    # 6. Open UI
    open_ui()
    
    print("\n[SUCCESS] VOID FULLY ONLINE!")
    print("- Backend: http://127.0.0.1:8003")
    print("- UI open in browser")
    print("- Ctrl+C to shutdown")
    print("=V=O=I=D= =" * 3)
    
    # Keep alive
    try:
        server.wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.terminate()
        print("[LAUNCHER] Server terminated.")

if __name__ == "__main__":
    main()
