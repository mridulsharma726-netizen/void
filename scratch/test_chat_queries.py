import requests
import json

TOKEN = "531f3d7a63681c59f03673f539f539796f664e4a9ca507890e50f58fb979490a"
BASE_URL = "http://127.0.0.1:8003"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
PROXIES = {"http": None, "https": None}

def test_query(msg):
    print(f"\nQuery: {msg}")
    payload = {"message": msg}
    try:
        r = requests.post(f"{BASE_URL}/chat", headers=HEADERS, json=payload, proxies=PROXIES, timeout=30)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.json().get('reply')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_query("what is my favorite car?")
    test_query("what is Master Mridul's favorite car?")
    test_query("who am I?")
