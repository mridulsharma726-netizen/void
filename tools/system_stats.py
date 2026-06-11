import psutil
import shutil
import time
import platform
from typing import Dict, Any, Optional

# GPU stats are optional - wrap in try/except for compatibility
try:
    import GPUtil
    GPUUTIL_AVAILABLE = True
except Exception:
    GPUUTIL_AVAILABLE = False

# CPU info - optional
try:
    import cpuinfo
    CPUINFO_AVAILABLE = True
except Exception:
    CPUINFO_AVAILABLE = False

   
class SystemStats:
    """
    System statistics collector for CPU, RAM, storage, battery, and GPU.
    Handles missing libraries gracefully by returning None for unavailable stats.
    Compatible with Python 3.12.
    """
    _cached_processor_info = None
    
    def __init__(self):
        self._stats_cache: Dict[str, Any] = {}
        self._cache_duration = 2.0  # seconds (increased from 1.0 to reduce CPU overhead)
        self._last_update = 0.0
        
        # Resolve processor info once to prevent heavy CPU overhead on stats refresh
        if SystemStats._cached_processor_info is None:
            SystemStats._cached_processor_info = platform.processor()
            if CPUINFO_AVAILABLE:
                try:
                    info = cpuinfo.get_cpu_info()
                    SystemStats._cached_processor_info = info.get("brand_raw", platform.processor())
                except Exception:
                    pass
        self._processor_info = SystemStats._cached_processor_info
    
    def _should_refresh(self) -> bool:
        """Check if cache should be refreshed."""
        return time.time() - self._last_update > self._cache_duration
    
    def _get_cpu_stats(self) -> Dict[str, Any]:
        """Get CPU statistics."""
        cpu_stats = {
            "cpu_usage": 0,
            "cpu_temp": None,
            "processor": self._processor_info,
        }
        
        # Non-blocking CPU usage
        cpu_stats["cpu_usage"] = psutil.cpu_percent(interval=None) if psutil else 0.0
        cpu_stats["cpu_temp"] = None
        # CPU temperature (might not be available on all systems)
        if psutil and hasattr(psutil, "sensors_temperatures"):
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    # Try common temperature sensor names
                    for sensor_name in ["coretemp", "cpu_thermal", "cpu_temp", "k10temp"]:
                        if sensor_name in temps and temps[sensor_name]:
                            cpu_stats["cpu_temp"] = temps[sensor_name][0].current
                            break
            except Exception:
                pass  # Temperature not available
        
        return cpu_stats
    
    def _get_ram_stats(self) -> Dict[str, Any]:
        """Get RAM statistics."""
        ram_stats = {
            "ram_usage": 0,
            "ram_used_gb": 0,
            "ram_total_gb": 0,
        }
        
        ram_stats["ram_usage"] = (psutil.virtual_memory().percent if psutil else 0.0)
        ram_stats["ram_used_gb"] = round((psutil.virtual_memory().used / (1024**3)) if psutil else 0, 2)
        ram_stats["ram_total_gb"] = round((psutil.virtual_memory().total / (1024**3)) if psutil else 8, 2)
        
        return ram_stats
    
    def _get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        storage_stats = {
            "storage_used_gb": 0,
            "storage_total_gb": 0,
        }
        
        try:
            # Get disk usage for the root partition (works on Windows and Linux)
            if platform.system() == "Windows":
                # On Windows, try C: drive
                drive = r"C:\\"
            else:
                drive = "/"
            
            total, used, free = shutil.disk_usage(drive)
            storage_stats["storage_total_gb"] = round(total / (1024**3), 2)
            storage_stats["storage_used_gb"] = round(used / (1024**3), 2)
        except Exception:
            pass  # Keep storage stats at 0
        
        return storage_stats
    
    def _get_battery_stats(self) -> Dict[str, Any]:
        """Get battery statistics."""
        battery_stats = {
            "battery_percent": None,
            "battery_charging": None,
        }
        
        if psutil and hasattr(psutil, "sensors_battery"):
            try:
                battery = psutil.sensors_battery()
                if battery:
                    battery_stats["battery_percent"] = battery.percent
                    battery_stats["battery_charging"] = battery.power_plugged
            except Exception:
                pass  # Keep battery stats at None
        
        return battery_stats
    
    def _get_gpu_stats(self) -> Dict[str, Any]:
        """Get GPU statistics. Returns None for GPU stats if unavailable."""
        gpu_stats = {
            "gpu_usage": None,
            "gpu_temp": None,
        }
        
        # GPU stats are optional - only attempt if GPUtil is available
        if not GPUUTIL_AVAILABLE:
            return gpu_stats
        
        try:
            gpus = GPUtil.getGPUs()
            if gpus and len(gpus) > 0:
                # For simplicity, taking the first GPU
                gpu = gpus[0]
                gpu_stats["gpu_usage"] = gpu.load * 100
                gpu_stats["gpu_temp"] = gpu.temperature
        except Exception:
            pass  # Keep GPU stats at None
        
        return gpu_stats
    
    def get_all_stats(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Gather all system statistics including CPU, RAM, storage, battery, and GPU.
        
        Args:
            use_cache: If True, uses cached values if recent enough (default: True)
        
        Returns:
            Dictionary containing all system statistics
        """
        # Use cached stats if valid and requested
        if use_cache and not self._should_refresh():
            return self._stats_cache.copy()
        
        # Collect all stats
        stats: Dict[str, Any] = {
            "os": platform.system(),
            "os_version": platform.version(),
            "processor": platform.processor(),
            "network_online": True,  # Assume online for now
            "uptime_seconds": int(time.time()),
            "fps": None,  # Not directly available from psutil
            "void_level": 1,  # This will be calculated in main.py
            "messages": 0,  # This will be calculated in main.py
            "tool_calls": 0,  # This will be calculated in main.py
            "memory_facts": 0,  # This will be calculated in main.py
        }
        
        # Merge all stats
        stats.update(self._get_cpu_stats())
        stats.update(self._get_ram_stats())
        stats.update(self._get_storage_stats())
        stats.update(self._get_battery_stats())
        stats.update(self._get_gpu_stats())
        
        # Update cache
        self._stats_cache = stats.copy()
        self._last_update = time.time()
        
        return stats
    
    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        stats = self.get_all_stats(use_cache=False)
        return stats.get("cpu_usage", 0)
    
    def get_ram_usage(self) -> float:
        """Get current RAM usage percentage."""
        stats = self.get_all_stats(use_cache=False)
        return stats.get("ram_usage", 0)
    
    def get_storage_usage(self) -> Dict[str, float]:
        """Get storage usage information."""
        stats = self.get_all_stats(use_cache=False)
        return {
            "used_gb": stats.get("storage_used_gb", 0),
            "total_gb": stats.get("storage_total_gb", 0),
        }
    
    def get_battery_status(self) -> Optional[Dict[str, Any]]:
        """Get battery status information."""
        stats = self.get_all_stats(use_cache=False)
        if stats.get("battery_percent") is not None:
            return {
                "percent": stats.get("battery_percent"),
                "charging": stats.get("battery_charging"),
            }
        return None
    
    def get_gpu_status(self) -> Optional[Dict[str, Any]]:
        """Get GPU status information."""
        stats = self.get_all_stats(use_cache=False)
        if stats.get("gpu_usage") is not None:
            return {
                "usage": stats.get("gpu_usage"),
                "temperature": stats.get("gpu_temp"),
            }
        return None


# Backward compatibility: keep the old function for any direct imports
def get_system_stats() -> Dict[str, Any]:
    """
    Legacy function for backward compatibility.
    Prefer using the SystemStats class for better performance with caching.
    """
    stats_collector = SystemStats()
    return stats_collector.get_all_stats()
