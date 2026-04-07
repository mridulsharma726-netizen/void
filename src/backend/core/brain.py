import requests
import os

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "llama3.2:3b"

def ask_llm(prompt):
  try:
    payload = {
      "model": MODEL,
      "messages": [{"role": "user", "content": prompt}],
      "stream": False
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"].strip()
  except requests.exceptions.ConnectionError:
    return "Ollama not running. Run 'ollama serve'"
  except Exception as e:
    return f"Brain error: {str(e)}"

def is_ollama_ready():
  try:
    r = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
    return r.status_code == 200
  except:
    return False
