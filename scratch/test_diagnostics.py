import requests
import json

TOKEN = "531f3d7a63681c59f03673f539f539796f664e4a9ca507890e50f58fb979490a"
BASE_URL = "http://127.0.0.1:8003"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
PROXIES = {"http": None, "https": None}

def test_endpoint(path, is_exempt=False):
    print(f"\nTesting {path}...")
    try:
        headers = {} if is_exempt else HEADERS
        r = requests.get(f"{BASE_URL}{path}", headers=headers, proxies=PROXIES, timeout=15)
        print("Status:", r.status_code)
        print("Response:", json.dumps(r.json(), indent=2))
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_endpoint("/health", is_exempt=True)
    test_endpoint("/tools/health")
    test_endpoint("/system/health-details")
