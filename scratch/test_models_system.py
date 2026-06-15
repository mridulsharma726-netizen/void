import sys
from pathlib import Path
ROOT_DIR = Path(r"c:\Users\HP\OneDrive\Desktop\void\VOID")
sys.path.append(str(ROOT_DIR))
sys.path.append(str(ROOT_DIR / "server"))

import requests
from server.backend.llm_client import SYSTEM_PROMPT

url = "http://127.0.0.1:11434/api/chat"
model = "qwen2.5:0.5b"

payload = {
    "model": model,
    "messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "what do you think about god ?"}
    ],
    "stream": False
}
try:
    print(f"Querying {model} with 90s timeout...")
    r = requests.post(url, json=payload, timeout=90)
    print(f"\nModel: {model}")
    print(r.json().get("message", {}).get("content", ""))
except Exception as e:
    print(f"\nModel: {model} failed:", e)
