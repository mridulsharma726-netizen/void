import requests
import json
import time

TOKEN = "531f3d7a63681c59f03673f539f539796f664e4a9ca507890e50f58fb979490a"
BASE_URL = "http://127.0.0.1:8003"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
PROXIES = {"http": None, "https": None}

def run_test():
    # 1. Open Notepad
    print("Opening Notepad...")
    r = requests.post(f"{BASE_URL}/open-app", headers=HEADERS, json={"app": "notepad"}, proxies=PROXIES)
    print("Open App Status:", r.status_code)
    time.sleep(2.0) # Wait for Notepad window to be active/focused

    # 2. Set permission level to 3.0
    print("Setting CVCS permission to 3.0 (Authorized Session)...")
    r = requests.post(f"{BASE_URL}/cvcs/permission", headers=HEADERS, json={"level": 3.0, "duration_seconds": 60}, proxies=PROXIES)
    print("Set Permission Status:", r.status_code)
    print("Set Permission Response:", r.json())

    # 3. Simulate typing
    print("Simulating typing...")
    payload = {
        "action": "type",
        "target": "Hello from VOID Audit Verification! PC Control system is fully functional."
    }
    r = requests.post(f"{BASE_URL}/cvcs/execute_action", headers=HEADERS, json=payload, proxies=PROXIES)
    print("Execute Action Status:", r.status_code)
    print("Execute Action Response:", r.json())

    # 4. Set permission back to 2.0 (Assisted Control)
    print("Restoring permission level to 2.0...")
    r = requests.post(f"{BASE_URL}/cvcs/permission", headers=HEADERS, json={"level": 2.0}, proxies=PROXIES)
    print("Restore Status:", r.status_code)

if __name__ == "__main__":
    run_test()
