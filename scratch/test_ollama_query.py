import sys
from pathlib import Path
ROOT_DIR = Path(r"c:\Users\HP\OneDrive\Desktop\void\VOID")
sys.path.append(str(ROOT_DIR))
sys.path.append(str(ROOT_DIR / "server"))

import requests
import json
from server.backend.llm_client import SYSTEM_PROMPT

url = "http://127.0.0.1:11434/api/chat"
model = "qwen2.5:0.5b"

payload2 = {
    "model": model,
    "messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "what do you think about god ?"}
    ],
    "stream": False
}

try:
    print("Querying qwen2.5:0.5b with 60s timeout...")
    r2 = requests.post(url, json=payload2, timeout=60)
    print("Test 2 (Full system prompt):")
    print(r2.json().get("message", {}).get("content", ""))
except Exception as e:
    print("Test 2 failed:", e)
