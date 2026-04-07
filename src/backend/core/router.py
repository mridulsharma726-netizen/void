from core.brain import ask_llm
from core.memory import add_fact, get_memory_summary
import psutil
from datetime import datetime
import time

def route_command(msg):
  msg_lower = msg.lower().strip()
  
  if 'time' in msg_lower or 'clock' in msg_lower:
    now = datetime.now()
    return now.strftime("%H:%M %p - %Y-%m-%d %A")
  
  if msg_lower.startswith('remember '):
    fact = msg[9:].strip()
    add_fact(fact)
    return "Fact remembered."
  
  if 'memory' in msg_lower:
    return get_memory_summary()
  
  if 'stats' in msg_lower or 'system' in msg_lower:
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    return f"CPU: {cpu}%, RAM: {ram}%"
  
  # LLM fallback
  return ask_llm(msg)

if __name__ == '__main__':
  print(route_command("test"))
