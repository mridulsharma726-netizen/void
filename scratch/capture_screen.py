import requests
import shutil
import os

TOKEN = "531f3d7a63681c59f03673f539f539796f664e4a9ca507890e50f58fb979490a"
BASE_URL = "http://127.0.0.1:8003"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
PROXIES = {"http": None, "https": None}

def run():
    print("Calling screenshot API...")
    try:
        r = requests.get(f"{BASE_URL}/cvcs/screenshot", headers=HEADERS, proxies=PROXIES, timeout=15)
        print("Status:", r.status_code)
        print("Response:", r.json())
        
        src = "memory/data/screenshots/current.png"
        dst = r"C:\Users\HP\.gemini\antigravity\brain\1f209b24-78d8-46b8-a356-17dfe2eed5c3\hud_screen.png"
        if os.path.exists(src):
            shutil.copy(src, dst)
            print("Copied screenshot to artifacts directory:", dst)
        else:
            print("Screenshot file not found at:", src)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    run()
