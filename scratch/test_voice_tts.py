import requests
import json

TOKEN = "531f3d7a63681c59f03673f539f539796f664e4a9ca507890e50f58fb979490a"
BASE_URL = "http://127.0.0.1:8003"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
PROXIES = {"http": None, "https": None}

def test_speak():
    payload = {"text": "Hello Master Mridul, this is VOID. Voice system is online."}
    print("Sending /speak request...")
    try:
        r = requests.post(f"{BASE_URL}/speak", headers=HEADERS, json=payload, proxies=PROXIES, timeout=10)
        print("Status:", r.status_code)
        print("Response:", json.dumps(r.json(), indent=2))
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_speak()
