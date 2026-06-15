import requests
import json
import time

TOKEN = "531f3d7a63681c59f03673f539f539796f664e4a9ca507890e50f58fb979490a"
BASE_URL = "http://127.0.0.1:8003"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
PROXIES = {"http": None, "https": None} # Disable proxy lookup for local requests

def run_test(name, func):
    print(f"\n==================== {name} ====================")
    try:
        func()
    except Exception as e:
        print(f"FAILED with error: {e}")

def test_health():
    r = requests.get(f"{BASE_URL}/health", proxies=PROXIES, timeout=5)
    print(f"Status: {r.status_code}")
    print(f"Body: {json.dumps(r.json(), indent=2)}")

def test_memory_add_direct():
    payload = {"fact": "Master Mridul's favorite car is a BMW", "importance": 5}
    r = requests.post(f"{BASE_URL}/memory/add", headers=HEADERS, proxies=PROXIES, json=payload, timeout=5)
    print(f"Status: {r.status_code}")
    print(f"Body: {json.dumps(r.json(), indent=2)}")

def test_memory_list():
    r = requests.get(f"{BASE_URL}/memory/list", headers=HEADERS, proxies=PROXIES, timeout=5)
    print(f"Status: {r.status_code}")
    print(f"Body: {json.dumps(r.json(), indent=2)}")

def test_chat_recall():
    payload = {"message": "what is my favorite car?"}
    r = requests.post(f"{BASE_URL}/chat", headers=HEADERS, proxies=PROXIES, json=payload, timeout=20)
    print(f"Status: {r.status_code}")
    print(f"Body: {json.dumps(r.json(), indent=2)}")

if __name__ == "__main__":
    run_test("Health Test", test_health)
    run_test("Direct Memory Add Test", test_memory_add_direct)
    run_test("Memory List Test", test_memory_list)
    run_test("Memory Recall Test", test_chat_recall)
