import requests
import json
import sqlite3

TOKEN = "531f3d7a63681c59f03673f539f539796f664e4a9ca507890e50f58fb979490a"
BASE_URL = "http://127.0.0.1:8003"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
PROXIES = {"http": None, "https": None}

def run():
    print("Clearing database tables...")
    # Clear history directly via SQLite to keep it clean, but keep facts/prefs if we want
    conn = sqlite3.connect("memory/data/memory.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history")
    cursor.execute("DELETE FROM facts")
    conn.commit()
    conn.close()

    # Add fact
    print("Adding fact...")
    payload = {"fact": "Master Mridul's favorite car is a BMW", "importance": 5}
    r = requests.post(f"{BASE_URL}/memory/add", headers=HEADERS, json=payload, proxies=PROXIES, timeout=5)
    print("Add status:", r.status_code)

    # Ask chat
    print("Asking chat...")
    payload = {"message": "what is my favorite car?"}
    r = requests.post(f"{BASE_URL}/chat", headers=HEADERS, json=payload, proxies=PROXIES, timeout=25)
    print("Chat status:", r.status_code)
    print("Reply:", r.json().get("reply"))

if __name__ == "__main__":
    run()
