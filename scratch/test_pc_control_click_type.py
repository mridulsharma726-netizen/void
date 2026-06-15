import requests
import json
import time

TOKEN = "531f3d7a63681c59f03673f539f539796f664e4a9ca507890e50f58fb979490a"
BASE_URL = "http://127.0.0.1:8003"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
PROXIES = {"http": None, "https": None}

def run_test():
    # 1. Set permission level to 3.0
    print("Setting CVCS permission to 3.0...")
    requests.post(f"{BASE_URL}/cvcs/permission", headers=HEADERS, json={"level": 3.0}, proxies=PROXIES)

    # 2. Click at 500, 500 to move mouse and focus Notepad
    print("Clicking at (500, 500)...")
    payload_click = {
        "action": "click",
        "target": "Notepad Center",
        "coords": [500, 500]
    }
    r = requests.post(f"{BASE_URL}/cvcs/execute_action", headers=HEADERS, json=payload_click, proxies=PROXIES)
    print("Click Status:", r.status_code)
    print("Click Response:", r.json())
    time.sleep(1.0)

    # 3. Simulate typing
    print("Simulating typing...")
    payload_type = {
        "action": "type",
        "target": "Hello! VOID PC Control verification completed successfully."
    }
    r = requests.post(f"{BASE_URL}/cvcs/execute_action", headers=HEADERS, json=payload_type, proxies=PROXIES)
    print("Type Status:", r.status_code)
    print("Type Response:", r.json())

    # 4. Restore permission to 2.0
    print("Restoring permission to 2.0...")
    requests.post(f"{BASE_URL}/cvcs/permission", headers=HEADERS, json={"level": 2.0}, proxies=PROXIES)

if __name__ == "__main__":
    run_test()
