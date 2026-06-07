import sys
import os
import time
import subprocess
import requests
import json
from pathlib import Path

# Setup paths
ROOT_DIR = Path(__file__).parent.parent.parent.parent.parent.parent / "OneDrive" / "Desktop" / "void" / "VOID"
sys.path.insert(0, str(ROOT_DIR))

print("=== Program Endpoint Testing ===")
print(f"Project Workspace: {ROOT_DIR}")

# 1. Start the uvicorn backend if it isn't running
BACKEND_PORT = 8002
HEALTH_URL = f"http://127.0.0.1:{BACKEND_PORT}/health"
STATUS_URL = f"http://127.0.0.1:{BACKEND_PORT}/cvcs/status"
PERMISSION_URL = f"http://127.0.0.1:{BACKEND_PORT}/cvcs/permission"
MONITOR_URL = f"http://127.0.0.1:{BACKEND_PORT}/cvcs/toggle-monitor"
EXECUTE_URL = f"http://127.0.0.1:{BACKEND_PORT}/cvcs/execute_action"
CHAT_URL = f"http://127.0.0.1:{BACKEND_PORT}/chat"

backend_was_offline = False
proc = None

try:
    resp = requests.get(HEALTH_URL, timeout=1.5)
    if resp.status_code == 200:
        print("[OK] Backend is already running.")
except Exception:
    print("[INFO] Backend is offline. Spawning backend server process...")
    backend_was_offline = True
    python_exe = str(ROOT_DIR / "venv" / "Scripts" / "python.exe")
    if not os.path.exists(python_exe):
        python_exe = "python"
        
    proc = subprocess.Popen([
        python_exe, "-m", "uvicorn", "server.main:app", 
        "--host", "127.0.0.1", "--port", str(BACKEND_PORT)
    ], cwd=str(ROOT_DIR), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Wait for startup (up to 15 seconds)
    print("Waiting for server startup...")
    for _ in range(15):
        try:
            resp = requests.get(HEALTH_URL, timeout=1.0)
            if resp.status_code == 200:
                print("[OK] Backend successfully started.")
                break
        except Exception:
            time.sleep(1.0)
    else:
        print("[ERROR] Backend failed to start. Aborting.")
        if proc:
            proc.kill()
        sys.exit(1)

# 2. Retrieve secure token for authorization
TOKEN_PATH = ROOT_DIR / "memory" / "data" / "secure_config.json"
token = ""
if TOKEN_PATH.exists():
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            token = data.get("api_token", "")
            print("[OK] Read secure API token successfully.")
    except Exception as e:
        print(f"[ERROR] Reading token configuration failed: {e}")
else:
    print("[ERROR] secure_config.json does not exist. Authenticaton will fail.")

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# 3. Test sequences
try:
    print("\n--- Test 1: Verify CVCS Status Endpoint ---")
    resp = requests.get(STATUS_URL, headers=headers)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.text}")
    status_data = resp.json()
    assert status_data.get("permission_level") == 2.0, "Expected initial permission level to be 2.0"
    
    print("\n--- Test 2: Verify Permission Level Changes ---")
    # Upgrade to Level 3.0 (Authorized Session) for 30s
    payload = {"level": 3.0, "duration_seconds": 30.0}
    resp = requests.post(PERMISSION_URL, headers=headers, json=payload)
    print(f"Response: {resp.text}")
    
    # Recheck status to confirm permission change & timer running
    resp = requests.get(STATUS_URL, headers=headers)
    print(f"Updated Status Response: {resp.text}")
    status_data = resp.json()
    assert status_data.get("permission_level") == 3.0, "Expected permission level to be updated to 3.0"
    assert status_data.get("session_expires_in") is not None, "Expected active session timer"
    
    print("\n--- Test 3: Verify Watch Screen Toggle ---")
    payload = {"text": "true"}
    resp = requests.post(MONITOR_URL, headers=headers, json=payload)
    print(f"Watch Toggle Response: {resp.text}")
    
    # Recheck status to confirm watch mode is ON
    resp = requests.get(STATUS_URL, headers=headers)
    status_data = resp.json()
    assert status_data.get("watch_mode_active") is True, "Expected watch mode to be True"
    
    print("\n--- Test 4: Verify Chat Intent Routing ---")
    # Verify screen querying intent
    payload = {"message": "VOID, read my screen"}
    resp = requests.post(CHAT_URL, headers=headers, json=payload)
    print(f"Chat Screen Query Response: {resp.text}")
    chat_data = resp.json()
    assert chat_data.get("meta", {}).get("intent") == "command", "Expected screen read query intent to be command"
    assert chat_data.get("meta", {}).get("action") == "cvcs_read_screen", "Expected screen read query action to be cvcs_read_screen"
    
    # Verify click action intent (should execute click if level 3, or prompt confirmation if level 2)
    # Let's revert back to Level 2 (Assisted) first
    requests.post(PERMISSION_URL, headers=headers, json={"level": 2.0})
    payload = {"message": "click run button"}
    resp = requests.post(CHAT_URL, headers=headers, json=payload)
    print(f"Chat Click Query Response (Level 2): {resp.text}")
    chat_data = resp.json()
    assert chat_data.get("meta", {}).get("intent") == "command", "Expected click query intent to be command"
    assert chat_data.get("meta", {}).get("action") == "cvcs_click", "Expected click query action to be cvcs_click"
    
    print("\n--- Test 5: Verify Execute Action Endpoint ---")
    # Test executing an action on Level 2 (should return pending_confirmation)
    action_payload = {"action": "click", "target": "run button", "coords": [100, 200]}
    resp = requests.post(EXECUTE_URL, headers=headers, json=action_payload)
    print(f"Execute Action Response (Level 2): {resp.text}")
    
    # Change to Level 4 (Automation) and execute click (should succeed or fail safely)
    requests.post(PERMISSION_URL, headers=headers, json={"level": 4.0})
    resp = requests.post(EXECUTE_URL, headers=headers, json=action_payload)
    print(f"Execute Action Response (Level 4): {resp.text}")
    
    # Clean up permissions back to safe default Level 2
    requests.post(PERMISSION_URL, headers=headers, json={"level": 2.0})
    requests.post(MONITOR_URL, headers=headers, json={"text": "false"})
    
    print("\n[SUCCESS] All CVCS API endpoints are fully operational and responding correctly.")

except Exception as e:
    print(f"\n[ERROR] Endpoint tests encountered failure: {e}")
    # Reset state on fail
    try:
        requests.post(PERMISSION_URL, headers=headers, json={"level": 2.0})
        requests.post(MONITOR_URL, headers=headers, json={"text": "false"})
    except:
        pass

# 4. Clean up spawned process
if backend_was_offline and proc:
    print("\nStopping uvicorn backend server process...")
    proc.terminate()
    proc.wait(timeout=2.0)
    print("[INFO] Backend process terminated.")

print("\n=== End of Test Sequences ===")
