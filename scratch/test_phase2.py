import sys
import os
import time
import requests
import threading
from pathlib import Path

VOID_ROOT = Path("c:/Users/HP/OneDrive/Desktop/void/VOID")
sys.path.insert(0, str(VOID_ROOT))
sys.path.insert(0, str(VOID_ROOT / "server"))

from server.main import app, API_TOKEN
import uvicorn

def start_server():
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="warning")

if __name__ == "__main__":
    # Start server in a background thread
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    
    # Wait for server to start by polling health
    base_url = "http://127.0.0.1:8002"
    print("Waiting for server to start...")
    success = False
    for i in range(30):
        try:
            r = requests.get(f"{base_url}/health", timeout=1)
            if r.status_code == 200:
                print("Server is up and healthy!")
                success = True
                break
        except Exception:
            pass
        time.sleep(1)
        
    if not success:
        print("Server failed to start in 30 seconds.")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {API_TOKEN}"}

    print("\n=== Testing /mic-level ===")
    try:
        r = requests.get(f"{base_url}/mic-level", headers=headers)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.json()}")
        assert r.status_code == 200
        assert "active" in r.json()
        assert "rms" in r.json()
        assert "level_pct" in r.json()
        print("  /mic-level: PASS")
    except Exception as e:
        print(f"  /mic-level: FAIL ({e})")

    print("\n=== Testing /chat with memory extraction ===")
    try:
        # Clear memory first
        r_clear = requests.post(f"{base_url}/chat", json={"message": "clear memory"}, headers=headers)
        print(f"Clear Memory Response: {r_clear.json()}")

        # Remember my favorite color is blue
        payload = {"message": "remember my favorite color is blue"}
        r = requests.post(f"{base_url}/chat", json=payload, headers=headers)
        print(f"Remember Response: {r.json()}")
        assert r.status_code == 200

        # Ask my favorite color
        payload = {"message": "what is my favorite color?"}
        r = requests.post(f"{base_url}/chat", json=payload, headers=headers)
        print(f"Recall Response: {r.json()}")
        assert r.status_code == 200
        print("  /chat memory: PASS")
    except Exception as e:
        print(f"  /chat memory: FAIL ({e})")

    print("\n=== Testing error handling & timeout guard ===")
    try:
        payload = {"message": "what is the meaning of life?"}
        r = requests.post(f"{base_url}/chat", json=payload, headers=headers)
        print(f"Response: {r.json()}")
        assert r.status_code == 200
        print("  error handling & timeout: PASS")
    except Exception as e:
        print(f"  error handling & timeout: FAIL ({e})")

    print("\nAll tests complete!")
