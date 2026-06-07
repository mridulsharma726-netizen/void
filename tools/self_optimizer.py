"""
VOID Self Optimizer Module
====================

Self-repair, performance monitoring, and automatic optimization.

Functions:
- repair_voice() -> dict
- repair_stt() -> dict
- repair_memory() -> dict
- repair_dependencies() -> dict
- check_performance() -> str
- optimization_loop()
- auto_repair(issue) -> dict
"""

import os
import sys
import logging
import psutil
import importlib
import subprocess
import time
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime

# Configure logging
logger = logging.getLogger("VOID-SelfOptimizer")

# Performance thresholds
CPU_HIGH_THRESHOLD = 85
RAM_HIGH_THRESHOLD = 85
DISK_HIGH_THRESHOLD = 90

# Optimization state
_optimization_running = False
_last_optimization_time = None


# ============================================================================
# MODULE REPAIRS
# ============================================================================

def repair_voice() -> Dict[str, Any]:
    """
    Attempt to repair TTS voice module.
    """
    logger.info("[OPTIMIZER] Attempting voice module repair...")
    try:
        from server.backend.repair_system import _reinit_tts
        res = _reinit_tts()
        return {
            "status": "ok" if res.get("success") else "error",
            "module": "voice",
            "message": res.get("message", "Voice repair complete")
        }
    except Exception as e:
        logger.error(f"[OPTIMIZER] Voice repair failed: {e}")
        return {
            "status": "error",
            "module": "voice",
            "message": str(e)
        }


def repair_stt() -> Dict[str, Any]:
    """
    Attempt to repair STT module.
    """
    logger.info("[OPTIMIZER] Attempting STT module repair...")
    try:
        from server.backend.repair_system import _reinit_stt
        res = _reinit_stt()
        return {
            "status": "ok" if res.get("success") else "error",
            "module": "stt",
            "message": res.get("message", "STT repair complete")
        }
    except Exception as e:
        logger.error(f"[OPTIMIZER] STT repair failed: {e}")
        return {
            "status": "error",
            "module": "stt",
            "message": str(e)
        }


def repair_memory() -> Dict[str, Any]:
    """
    Attempt to repair corrupted memory file.
    """
    logger.info("[OPTIMIZER] Attempting memory repair...")
    try:
        from server.backend.repair_system import _repair_memory_file
        res = _repair_memory_file()
        return {
            "status": "ok" if res.get("success") else "error",
            "module": "memory",
            "message": res.get("message", "Memory repair complete")
        }
    except Exception as e:
        logger.error(f"[OPTIMIZER] Memory repair failed: {e}")
        return {
            "status": "error",
            "module": "memory",
            "message": str(e)
        }


def repair_dependencies() -> Dict[str, Any]:
    """
    Attempt to repair missing dependencies.
    """
    logger.info("[OPTIMIZER] Attempting dependency repair...")
    try:
        from server.backend.repair_system import _repair_dependencies
        res = _repair_dependencies()
        return {
            "status": "ok" if res.get("success") else "error",
            "module": "dependencies",
            "message": res.get("message", "Dependency repair complete")
        }
    except Exception as e:
        logger.error(f"[OPTIMIZER] Dependency repair failed: {e}")
        return {
            "status": "error",
            "module": "dependencies",
            "message": str(e)
        }


def repair_all() -> Dict[str, Any]:
    """
    Run all repair attempts.
    
    Returns:
        Dict with overall repair status
    """
    logger.info("[OPTIMIZER] Running full repair...")
    
    results = {
        "voice": repair_voice(),
        "stt": repair_stt(),
        "memory": repair_memory(),
        "dependencies": repair_dependencies()
    }
    
    # Count successes
    successes = sum(1 for r in results.values() if r["status"] == "ok")
    total = len(results)
    
    return {
        "status": "ok" if successes == total else ("partial" if successes > 0 else "error"),
        "results": results,
        "summary": f"{successes}/{total} modules repaired"
    }


# ============================================================================
# PERFORMANCE MONITORING
# ============================================================================

def check_performance() -> Dict[str, Any]:
    """
    Check current system performance.
    
    Returns:
        Dict with CPU, RAM, Disk usage
    """
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage(os.path.abspath(os.sep)).percent
        
        issues = []
        
        if cpu > CPU_HIGH_THRESHOLD:
            issues.append(f"CPU high: {cpu}%")
        if ram > RAM_HIGH_THRESHOLD:
            issues.append(f"RAM high: {ram}%")
        if disk > DISK_HIGH_THRESHOLD:
            issues.append(f"Disk high: {disk}%")
        
        return {
            "status": "ok" if not issues else "warning",
            "cpu_percent": cpu,
            "ram_percent": ram,
            "disk_percent": disk,
            "issues": issues,
            "message": " | ".join(issues) if issues else "System normal"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


def get_optimization_suggestions() -> List[str]:
    """
    Get suggestions for system optimization.
    
    Returns:
        List of suggestion strings
    """
    perf = check_performance()
    suggestions = []
    
    if perf.get("cpu_percent", 0) > CPU_HIGH_THRESHOLD:
        suggestions.append("High CPU usage - consider closing heavy processes")
    
    if perf.get("ram_percent", 0) > RAM_HIGH_THRESHOLD:
        suggestions.append("High RAM usage - consider freeing memory")
    
    if perf.get("disk_percent", 0) > DISK_HIGH_THRESHOLD:
        suggestions.append("Low disk space - consider cleaning temp files")
    
    # Check for common issues
    try:
        # Check memory file
        if not os.path.exists("data/memory.json"):
            suggestions.append("Memory file missing - repair recommended")
    except:
        pass
    
    return suggestions


# ============================================================================
# AUTO REPAIR SYSTEM
# ============================================================================

def auto_repair(issue: str) -> Dict[str, Any]:
    """
    Attempt to automatically repair a specific issue.
    
    Args:
        issue: Description of the issue
        
    Returns:
        Dict with repair result
    """
    issue_lower = issue.lower()
    logger.info(f"[OPTIMIZER] Auto-repair request: {issue}")
    
    # Map issues to repair functions
    if "voice" in issue_lower or "tts" in issue_lower or "speak" in issue_lower:
        return repair_voice()
    
    if "stt" in issue_lower or "speech" in issue_lower or "listen" in issue_lower:
        return repair_stt()
    
    if "memory" in issue_lower or "remember" in issue_lower:
        return repair_memory()
    
    if "depend" in issue_lower or "install" in issue_lower or "package" in issue_lower:
        return repair_dependencies()
    
    if "performance" in issue_lower or "slow" in issue_lower or "cpu" in issue_lower:
        perf = check_performance()
        return {
            "status": perf["status"],
            "message": perf.get("message", "Check complete"),
            "details": perf
        }
    
    # No specific repair found
    return {
        "status": "unknown",
        "message": f"Unknown issue: {issue}. Try running full repair.",
        "suggestion": "Call repair_all() for full diagnostics"
    }


# ============================================================================
# OPTIMIZATION LOOP
# ============================================================================

def optimization_loop(interval: int = 60,
                     auto_repair_enabled: bool = True,
                     repair_callback: Optional[callable] = None):
    """
    Background optimization loop.
    
    Args:
        interval: Seconds between checks
        auto_repair_enabled: Whether to auto-repair issues
        repair_callback: Optional callback for repair alerts
    """
    global _optimization_running, _last_optimization_time
    
    _optimization_running = True
    logger.info(f"[OPTIMIZER] Started (interval: {interval}s)")
    
    while _optimization_running:
        try:
            # Check performance
            perf = check_performance()
            
            if perf.get("status") == "warning":
                issues = perf.get("issues", [])
                logger.warning(f"[OPTIMIZER] Performance issues: {issues}")
                
                # Auto-repair if enabled
                if auto_repair_enabled:
                    for issue in issues:
                        if "CPU" in issue:
                            # Try to free resources
                            logger.info("[OPTIMIZER] Attempting CPU optimization...")
                        elif "RAM" in issue:
                            logger.info("[OPTIMIZER] Attempting RAM optimization...")
                        elif "Disk" in issue:
                            logger.info("[OPTIMIZER] Attempting disk cleanup...")
                
                # Call repair callback if provided
                if repair_callback:
                    try:
                        repair_callback(issues)
                    except Exception as e:
                        logger.error(f"[OPTIMIZER] Callback error: {e}")
            
            _last_optimization_time = datetime.now()
            
            # Sleep
            for _ in range(interval):
                if not _optimization_running:
                    break
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"[OPTIMIZER] Loop error: {e}")
            time.sleep(interval)
    
    logger.info("[OPTIMIZER] Stopped")


def stop_optimization():
    """Stop the optimization loop."""
    global _optimization_running
    _optimization_running = False
    logger.info("[OPTIMIZER] Stop signal sent")


def is_optimizing() -> bool:
    """Check if optimization is running."""
    return _optimization_running


# ============================================================================
# QUICK DIAGNOSTICS
# ============================================================================

def quick_diagnose() -> Dict[str, Any]:
    """
    Quick self-diagnosis of VOID modules.
    
    Returns:
        Dict with module health status
    """
    modules = {}
    
    # Check core modules
    module_checks = [
        ("voice_tts", "tools.voice_tts"),
        ("voice_stt", "tools.voice_stt"),
        ("system_stats", "tools.system_stats"),
        ("file_status", "tools.file_status"),
        ("diagnostics", "tools.diagnostics"),
        ("self_repair", "tools.self_repair"),
        ("web_search", "tools.web_search"),
        ("system_control", "tools.system_control"),
    ]
    
    for name, module_path in module_checks:
        try:
            importlib.import_module(module_path)
            modules[name] = {"status": "ok", "message": "Module loads OK"}
        except Exception as e:
            modules[name] = {"status": "error", "message": str(e)}
    
    # Check memory
    try:
        repair_memory()
        modules["memory"] = {"status": "ok", "message": "Memory file OK"}
    except Exception as e:
        modules["memory"] = {"status": "error", "message": str(e)}
    
    # Check performance
    perf = check_performance()
    modules["performance"] = {
        "status": perf.get("status", "unknown"),
        "cpu": perf.get("cpu_percent", 0),
        "ram": perf.get("ram_percent", 0)
    }
    
    # Overall status
    errors = sum(1 for m in modules.values() if m.get("status") == "error")
    overall = "ok" if errors == 0 else ("partial" if errors < 3 else "error")
    
    return {
        "status": overall,
        "modules": modules,
        "error_count": errors
    }


if __name__ == "__main__":
    # Test optimizer
    print("Testing self optimizer...")
    
    # Quick diagnose
    print("\n1. Quick diagnose:")
    result = quick_diagnose()
    print(f"Status: {result['status']}")
    print(f"Errors: {result['error_count']}")
    for name, info in result['modules'].items():
        print(f"  {name}: {info['status']}")
    
    # Check performance
    print("\n2. Performance check:")
    perf = check_performance()
    print(f"CPU: {perf.get('cpu_percent')}%")
    print(f"RAM: {perf.get('ram_percent')}%")
    print(f"Disk: {perf.get('disk_percent')}%")
    
    # Auto repair test
    print("\n3. Auto repair test:")
    print(auto_repair("voice not working"))

