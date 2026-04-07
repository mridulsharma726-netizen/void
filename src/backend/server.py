from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn
import os
import json
import time
import requests
import psutil
from datetime import datetime

app = FastAPI(title="VOID Backend for Electron")

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "llama3.2:3b" or "llama3.2"
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
MEMORY_FILE = os.path.join(DATA_DIR, "memory.json")

# Stats
STATS = {"messages": 0, "uptime": 0}
START_TIME = time.time()

class ChatRequest(BaseModel):
  message: str

def load_memory():
  try:
    with open(MEMORY_FILE, "r") as f:
      return json.load(f)
  except:
    return {"facts": []}

def save_memory(data):
  with open(MEMORY_FILE, "w") as f:
    json.dump(data, f, indent=2)

@app.get("/health")
async def health():
  return {"status": "ok", "ollama": requests.get("http://127.0.0.1:11434/api/tags", timeout=1).status_code == 200}

@app.get("/stats")
async def stats():
  uptime = int(time.time() - START_TIME)
  return {
    "uptime": uptime,
    "messages": STATS["messages"],
    "cpu_usage": psutil.cpu_percent(),
    "ram_usage": psutil.virtual_memory().percent,
    "memory_facts": len(load_memory().get("facts", []))
  }

@app.post("/chat")
async def chat(req: ChatRequest):
  STATS["messages"] += 1
  msg = req.message.strip()
  
  # Simple commands
  if "time" in msg.lower():
    now = datetime.now()
    return {"reply": now.strftime("%H:%M:%S %Y-%m-%d %A")}
  
  if "memory" in msg.lower():
    mem = load_memory()
    return {"reply": json.dumps(mem.get("facts", []), indent=2)[:500] + "..." if len(mem.get("facts", [])) > 5 else json.dumps(mem)}
  
  # Ollama
  try:
    r = requests.post(OLLAMA_URL, json={
      "model": MODEL,
      "messages": [{"role": "user", "content": msg}],
      "stream": False
    }, timeout=30)
    r.raise_for_status()
    data = r.json()
    reply = data["message"]["content"]
    return {"reply": reply}
  except:
    return {"reply": "Ollama offline. Use 'ollama serve' + model pull."}

if __name__ == "__main__":
  uvicorn.run(app, host="127.0.0.1", port=8000)
