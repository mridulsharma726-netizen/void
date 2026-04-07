import psutil
import platform
import GPUtil
from datetime import datetime

def get_system_stats():
  return {
    "cpu": psutil.cpu_percent(interval=0.1),
    "ram": psutil.virtual_memory().percent,
    "disk": psutil.disk_usage('/').percent,
    "platform": platform.system(),
    "uptime": time.time() - psutil.boot_time(),
    "gpu": get_gpu_stats() if 'gpu' in globals() else None
  }

def get_gpu_stats():
  try:
    gpus = GPUtil.getGPUs()
    if gpus:
      gpu = gpus[0]
      return {
        "load": gpu.load * 100,
        "temp": gpu.temperature,
        "memory": gpu.memoryUtil * 100
      }
  except:
    return None
