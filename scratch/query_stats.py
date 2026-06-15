import requests
import json

TOKEN = "531f3d7a63681c59f03673f539f539796f664e4a9ca507890e50f58fb979490a"
BASE_URL = "http://127.0.0.1:8003"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
PROXIES = {"http": None, "https": None}

def run():
    r = requests.get(f"{BASE_URL}/stats", headers=HEADERS, proxies=PROXIES, timeout=5)
    print("Status Code:", r.status_code)
    print("Response JSON:")
    print(json.dumps(r.json(), indent=2))

if __name__ == "__main__":
    run()
