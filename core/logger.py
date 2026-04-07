"""
VOID System Logger
=================

Centralized logging for self-engineering system.

Features:
- System startup logging
- Error logging
- Repair action logging
- File modification tracking

Log file: logs/system.log

"""

import os
import sys
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


# ============================================================================
# LOG LEVELS
# ============================================================================

class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ============================================================================
# LOGGER SETUP
# ============================================================================

# Get VOID root directory
VOID_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Log directory
LOG_DIR = os.path.join(VOID_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Main system log file
SYSTEM_LOG = os.path.join(LOG_DIR, "system.log")


def _get_logger(name: str = "VOID-System") -> logging.Logger:
    """
    Get or create a logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # File handler - main system log
    file_handler = logging.FileHandler(SYSTEM_LOG, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# Get the main logger
logger = _get_logger()


# ============================================================================
# LOGGING FUNCTIONS
# ============================================================================

def log_startup():
    """Log system startup."""
    logger.info("=" * 60)
    logger.info("VOID SYSTEM STARTUP")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info(f"Platform: {sys.platform}")
    logger.info(f"Python: {sys.version}")
    logger.info("=" * 60)


def log_error(error_type: str, message: str, details: Optional[str] = None):
    """
    Log an error.
    
    Args:
        error_type: Type of error
        message: Error message
        details: Optional detailed error info
    """
    log_msg = f"ERROR | {error_type} | {message}"
    if details:
        log_msg += f" | Details: {details}"
    logger.error(log_msg)


def log_repair(action: str, target: str, result: str):
    """
    Log a repair action.
    
    Args:
        action: Action performed (e.g., "restart", "reload")
        target: Target of the action
        result: Result (success/failure)
    """
    logger.info(f"REPAIR | Action: {action} | Target: {target} | Result: {result}")


def log_file_modification(file_path: str, action: str, details: Optional[str] = None):
    """
    Log a file modification.
    
    Args:
        file_path: Path to file
        action: Action performed (create/edit/delete)
        details: Optional details
    """
    log_msg = f"FILE_MOD | {action} | {file_path}"
    if details:
        log_msg += f" | {details}"
    logger.info(log_msg)


def log_command(command: str, result: str):
    """
    Log a terminal command execution.
    
    Args:
        command: Command that was executed
        result: Result of execution
    """
    logger.info(f"COMMAND | {command} | Result: {result}")


def log_diagnostics(component: str, status: str, details: Optional[str] = None):
    """
    Log diagnostics result.
    
    Args:
        component: Component checked
        status: Status (ok/error/warning)
        details: Optional details
    """
    log_msg = f"DIAG | {component} | Status: {status}"
    if details:
        log_msg += f" | {details}"
    logger.info(log_msg)


def log_event(event_type: str, message: str, data: Optional[Dict[str, Any]] = None):
    """
    Log a generic event.
    
    Args:
        event_type: Type of event
        message: Event message
        data: Optional data dictionary
    """
    log_msg = f"EVENT | {event_type} | {message}"
    if data:
        import json
        try:
            log_msg += f" | Data: {json.dumps(data)}"
        except:
            pass
    logger.info(log_msg)


def log_warning(message: str, details: Optional[str] = None):
    """
    Log a warning.
    
    Args:
        message: Warning message
        details: Optional details
    """
    log_msg = f"WARNING | {message}"
    if details:
        log_msg += f" | {details}"
    logger.warning(log_msg)


def log_info(message: str):
    """
    Log an info message.
    
    Args:
        message: Message to log
    """
    logger.info(f"INFO | {message}")


def log_critical(message: str, details: Optional[str] = None):
    """
    Log a critical message.
    
    Args:
        message: Critical message
        details: Optional details
    """
    log_msg = f"CRITICAL | {message}"
    if details:
        log_msg += f" | {details}"
    logger.critical(log_msg)


# ============================================================================
# READ LOGS
# ============================================================================

def get_recent_logs(lines: int = 100, log_file: str = SYSTEM_LOG) -> list:
    """
    Get recent log entries.
    
    Args:
        lines: Number of lines to retrieve
        log_file: Path to log file
        
    Returns:
        List of log lines
    """
    try:
        if not os.path.exists(log_file):
            return []
        
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            return all_lines[-lines:]
    except Exception as e:
        return [f"Error reading log: {str(e)}"]


def search_logs(query: str, log_file: str = SYSTEM_LOG) -> list:
    """
    Search logs for a query.
    
    Args:
        query: Search query
        log_file: Path to log file
        
    Returns:
        List of matching lines
    """
    try:
        if not os.path.exists(log_file):
            return []
        
        results = []
        query_lower = query.lower()
        
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                if query_lower in line.lower():
                    results.append(line.strip())
        
        return results
    except Exception as e:
        return [f"Error searching log: {str(e)}"]


def get_log_summary(log_file: str = SYSTEM_LOG) -> Dict[str, Any]:
    """
    Get a summary of logs.
    
    Args:
        log_file: Path to log file
        
    Returns:
        Dictionary with log summary
    """
    try:
        if not os.path.exists(log_file):
            return {
                "status": "error",
                "message": "Log file not found"
            }
        
        stats = {
            "total_lines": 0,
            "errors": 0,
            "warnings": 0,
            "repairs": 0,
            "file_mods": 0,
            "last_entry": None
        }
        
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            stats["total_lines"] = len(lines)
            
            for line in lines:
                line_upper = line.upper()
                if "ERROR" in line_upper:
                    stats["errors"] += 1
                if "WARNING" in line_upper:
                    stats["warnings"] += 1
                if "REPAIR" in line_upper:
                    stats["repairs"] += 1
                if "FILE_MOD" in line_upper:
                    stats["file_mods"] += 1
            
            if lines:
                stats["last_entry"] = lines[-1].strip()
        
        return {
            "status": "ok",
            "summary": stats
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    # Test logging
    print("VOID Logger Test")
    print("=" * 50)
    
    log_startup()
    log_info("Test info message")
    log_warning("Test warning message")
    log_error("TEST_ERROR", "This is a test error")
    log_repair("reload", "tools.voice_stt", "success")
    log_file_modification("tools/test.py", "create", "New test file")
    
    # Get summary
    summary = get_log_summary()
    print(f"\nLog Summary: {summary}")

