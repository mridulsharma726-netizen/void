"""
VOID System Monitor Module
====================

Background monitoring for system health (CPU, RAM, Disk, Temperature).
Alerts the user when thresholds are exceeded.

Functions:
- check_system_health() -> List[dict]
- monitor_loop(interval: int, alert_callback)
- get_current_stats() -> dict
- set_thresholds(cpu, ram, disk, temp)
"""

import time
import logging
import psutil
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

# Configure logging
logger = logging.getLogger("VOID-SystemMonitor")

# Default thresholds
DEFAULT_CPU_THRESHOLD = 85  # percent
DEFAULT_RAM_THRESHOLD = 85  # percent
DEFAULT_DISK_THRESHOLD = 90  # percent
DEFAULT_TEMP_THRESHOLD = 80  # celsius

# Current thresholds
_cpu_threshold = DEFAULT_CPU_THRESHOLD
_ram_threshold = DEFAULT_RAM_THRESHOLD
_disk_threshold = DEFAULT_DISK_THRESHOLD
_temp_threshold = DEFAULT_TEMP_THRESHOLD

# Monitoring state
_monitoring = False
_last_alerts = []  # Track last alerts to avoid duplicate alerts


def set_thresholds(cpu: int = None, ram: int = None, disk: int = None, temp: int = None):
    """Set alert thresholds."""
    global _cpu_threshold, _ram_threshold, _disk_threshold, _temp_threshold
    
    if cpu is not None:
        _cpu_threshold = cpu
    if ram is not None:
        _ram_threshold = ram
    if disk is not None:
        _disk_threshold = disk
    if temp is not None:
        _temp_threshold = temp
    
    logger.info(f"Thresholds set: CPU>{_cpu_threshold}%, RAM>{_ram_threshold}%, Disk>{_disk_threshold}%, Temp>{_temp_threshold}°C")


def get_thresholds() -> Dict[str, int]:
    """Get current thresholds."""
    return {
        "cpu": _cpu_threshold,
        "ram": _ram_threshold,
        "disk": _disk_threshold,
        "temp": _temp_threshold
    }


def get_current_stats() -> Dict[str, Any]:
    """Get current system statistics."""
    stats = {}
    
    try:
        # CPU
        stats["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        stats["cpu_count"] = psutil.cpu_count()
        
        # CPU temperature (if available)
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                # Get first CPU temp reading
                for name, entries in temps.items():
                    if entries:
                        stats["cpu_temp"] = entries[0].current
                        break
        except Exception:
            pass
        
    except Exception as e:
        logger.error(f"CPU stats error: {e}")
    
    try:
        # RAM
        mem = psutil.virtual_memory()
        stats["ram_percent"] = mem.percent
        stats["ram_used_gb"] = round(mem.used / (1024**3), 2)
        stats["ram_total_gb"] = round(mem.total / (1024**3), 2)
    except Exception as e:
        logger.error(f"RAM stats error: {e}")
    
    try:
        # Disk
        disk = psutil.disk_usage("/")
        stats["disk_percent"] = disk.percent
        stats["disk_used_gb"] = round(disk.used / (1024**3), 2)
        stats["disk_total_gb"] = round(disk.total / (1024**3), 2)
    except Exception as e:
        logger.error(f"Disk stats error: {e}")
    
    try:
        # Battery
        battery = psutil.sensors_battery()
        if battery:
            stats["battery_percent"] = battery.percent
            stats["battery_charging"] = battery.power_plugged
    except Exception:
        pass
    
    stats["timestamp"] = datetime.now().isoformat()
    
    return stats


def check_system_health(include_ok: bool = False) -> List[Dict[str, Any]]:
    """
    Check system health and return alerts.
    
    Args:
        include_ok: If True, include "ok" status metrics
        
    Returns:
        List of alert dicts with severity, metric, value, message
    """
    global _last_alerts
    
    alerts = []
    stats = get_current_stats()
    
    # CPU check
    cpu = stats.get("cpu_percent", 0)
    if cpu > _cpu_threshold:
        alerts.append({
            "severity": "critical" if cpu > 95 else "warning",
            "metric": "cpu",
            "value": cpu,
            "threshold": _cpu_threshold,
            "message": f"CPU usage very high: {cpu:.1f}%"
        })
    elif include_ok:
        alerts.append({
            "severity": "ok",
            "metric": "cpu",
            "value": cpu,
            "message": f"CPU: {cpu:.1f}%"
        })
    
    # RAM check
    ram = stats.get("ram_percent", 0)
    if ram > _ram_threshold:
        alerts.append({
            "severity": "critical" if ram > 95 else "warning",
            "metric": "ram",
            "value": ram,
            "threshold": _ram_threshold,
            "message": f"RAM usage very high: {ram:.1f}%"
        })
    elif include_ok:
        alerts.append({
            "severity": "ok",
            "metric": "ram",
            "value": ram,
            "message": f"RAM: {ram:.1f}%"
        })
    
    # Disk check
    disk = stats.get("disk_percent", 0)
    if disk > _disk_threshold:
        alerts.append({
            "severity": "critical",
            "metric": "disk",
            "value": disk,
            "threshold": _disk_threshold,
            "message": f"Disk space critically low: {disk:.1f}%"
        })
    elif include_ok:
        alerts.append({
            "severity": "ok",
            "metric": "disk",
            "value": disk,
            "message": f"Disk: {disk:.1f}%"
        })
    
    # Temperature check
    temp = stats.get("cpu_temp")
    if temp:
        if temp > _temp_threshold:
            alerts.append({
                "severity": "critical" if temp > 90 else "warning",
                "metric": "temperature",
                "value": temp,
                "threshold": _temp_threshold,
                "message": f"CPU temperature high: {temp:.1f}°C"
            })
        elif include_ok:
            alerts.append({
                "severity": "ok",
                "metric": "temperature",
                "value": temp,
                "message": f"CPU Temp: {temp:.1f}°C"
            })
    
    # Battery check (if low)
    battery = stats.get("battery_percent")
    if battery is not None and not stats.get("battery_charging"):
        if battery < 15:
            alerts.append({
                "severity": "warning",
                "metric": "battery",
                "value": battery,
                "threshold": 15,
                "message": f"Battery low: {battery}%"
            })
    
    _last_alerts = alerts
    
    return alerts


def has_critical_alerts() -> bool:
    """Check if there are any critical alerts."""
    alerts = check_system_health()
    return any(a.get("severity") == "critical" for a in alerts)


def get_alert_messages() -> List[str]:
    """Get just the alert messages."""
    return [a["message"] for a in check_system_health()]


def monitor_loop(interval: int = 30, 
                alert_callback: Optional[Callable[[List[Dict]], None]] = None,
                tts_callback: Optional[Callable[[str], None]] = None,
                speak_alerts: bool = False):
    """
    Run the monitoring loop continuously.
    
    Args:
        interval: Seconds between checks (default 30)
        alert_callback: Function to call with alerts
        tts_callback: Function for text-to-speech (optional)
        speak_alerts: If True, speak alerts via TTS
    """
    global _monitoring
    
    _monitoring = True
    logger.info(f"[SYSTEM MONITOR] Started (interval: {interval}s)")
    
    # Keep track of last alert time to avoid spam
    last_alert_time = {}
    alert_cooldown = 300  # 5 minutes between same alerts
    
    while _monitoring:
        try:
            alerts = check_system_health()
            
            # Filter for new alerts only
            new_alerts = []
            current_time = time.time()
            
            for alert in alerts:
                key = alert["metric"]
                last_time = last_alert_time.get(key, 0)
                
                # Always report critical alerts, throttle warnings
                if alert["severity"] == "critical" or (current_time - last_time) > alert_cooldown:
                    new_alerts.append(alert)
                    last_alert_time[key] = current_time
            
            if new_alerts:
                logger.info(f"[SYSTEM MONITOR] Alerts: {len(new_alerts)}")
                
                for alert in new_alerts:
                    logger.warning(f"[SYSTEM ALERT] {alert['message']}")
                
                # Call alert callback
                if alert_callback:
                    try:
                        alert_callback(new_alerts)
                    except Exception as e:
                        logger.error(f"Alert callback error: {e}")
                
                # Speak alerts if enabled
                if speak_alerts and tts_callback:
                    for alert in new_alerts:
                        try:
                            tts_callback(alert["message"])
                        except Exception as e:
                            logger.error(f"TTS error: {e}")
            
            # Sleep until next check
            for _ in range(interval):
                if not _monitoring:
                    break
                time.sleep(1)
    
    logger.info("[SYSTEM MONITOR] Stopped")


def stop_monitor():
    """Stop the monitoring loop."""
    global _monitoring
    _monitoring = False
    logger.info("[SYSTEM MONITOR] Stop signal sent")


def is_monitoring() -> bool:
    """Check if monitor is running."""
    return _monitoring


# Convenience function for quick health check
def quick_check() -> str:
    """Get a quick health status string."""
    alerts = check_system_health()
    
    if not alerts:
        return "All systems healthy"
    
    warnings = [a for a in alerts if a["severity"] == "warning"]
    critical = [a for a in alerts if a["severity"] == "critical"]
    
    if critical:
        return f"CRITICAL: {', '.join([a['message'] for a in critical])}"
    elif warnings:
        return f"Warning: {', '.join([a['message'] for a in warnings])}"
    
    return "Systems nominal"


if __name__ == "__main__":
    # Test the monitor
    print("Testing system monitor...")
    
    # Get current stats
    stats = get_current_stats()
    print(f"Current stats: {stats}")
    
    # Check health
    alerts = check_system_health()
    print(f"Alerts: {alerts}")
    
    # Quick check
    print(f"Quick check: {quick_check()}")
    
    # Set custom thresholds
    set_thresholds(cpu=50, ram=50)
    alerts = check_system_health()
    print(f"Alerts with lower thresholds: {alerts}")

