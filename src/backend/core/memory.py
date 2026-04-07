import os
import json
from datetime import datetime

DATA_DIR = "data"
MEMORY_FILE = os.path.join(DATA_DIR, "memory.json")

os.makedirs(DATA_DIR, exist_ok=True)

def load_memory():
  try:
    with open(MEMORY_FILE, 'r') as f:
      data = json.load(f)
      return data.get('facts', [])
  except:
    return []

def save_memory(facts):
  data = {
    'facts': facts,
    'last_updated': datetime.now().isoformat()
  }
  with open(MEMORY_FILE, 'w') as f:
    json.dump(data, f, indent=2)

def add_fact(fact):
  facts = load_memory()
  facts.append({
    'fact': fact,
    'timestamp': datetime.now().isoformat()
  })
  save_memory(facts)
  return True

def get_memory_summary():
  facts = load_memory()
  return f"{len(facts)} facts stored"
