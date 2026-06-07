import requests
try:
    r = requests.get("http://127.0.0.1:8000/stats", timeout=5)
    print(r.json())
except Exception as e:
    print(f"Error: {e}")
