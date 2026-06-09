import sys
import json
import requests
from pathlib import Path

# Add project root and server to path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "server"))

from server.main import get_or_generate_api_token

def test_integration():
    token = get_or_generate_api_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    queries = [
        "what is 25 * 4",
        "battery status",
        "what is the time",
        "what is the date today",
        "check file exists c:\\windows\\notepad.exe",
    ]
    
    print("--- Testing Chat Integration with Direct Tools ---")
    for q in queries:
        payload = {"message": q}
        try:
            r = requests.post("http://127.0.0.1:8002/chat", json=payload, headers=headers, timeout=10)
            if r.status_code == 200:
                resp = r.json()
                print(f"Query: {q!r}")
                print(f"Reply: {resp.get('reply')!r}")
                print(f"Meta: {resp.get('meta')!r}")
                print("-" * 50)
            else:
                print(f"Error {r.status_code} for query {q}: {r.text}")
        except Exception as e:
            print(f"Request failed for query {q}: {e}")

if __name__ == "__main__":
    test_integration()
