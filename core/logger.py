"""
VOID Core Logger Module
=======================

Provides structured event logging for self-modification and system events.
Used by: self_modifier.py
"""

import logging
import os
from datetime import datetime
from pathlib import Path

# Project root
ROOT_DIR = Path(__file__).parent.parent
LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Event log file
EVENT_LOG_FILE = LOG_DIR / "void_events.log"

# Standard logger
logger = logging.getLogger("void.events")


def log_event(event_type: str, details: str = "", level: str = "INFO"):
    """
    Log a system event.
    
    Args:
        event_type: Event category (e.g., 'STARTUP', 'REPAIR', 'UPGRADE')
        details: Human-readable event details
        level: Log level ('INFO', 'WARNING', 'ERROR')
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{event_type}] {details}"
    
    # Log to Python logger
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(log_level, f"[{event_type}] {details}")
    
    # Append to event log file
    try:
        with open(EVENT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception as e:
        logger.warning(f"Could not write to event log: {e}")


def log_file_modification(file_path: str, action: str, details: str = ""):
    """
    Log a file modification event for audit trail.
    
    Args:
        file_path: Path of the file being modified
        action: Action performed (e.g., 'rewrite_start', 'rewrite_success', 'backup_created')
        details: Additional details
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [FILE_MOD] [{action}] {file_path}"
    if details:
        entry += f" | {details}"
    
    logger.info(f"[FILE_MOD] [{action}] {file_path} | {details}")
    
    try:
        with open(EVENT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception as e:
        logger.warning(f"Could not write to event log: {e}")


def get_recent_events(count: int = 20) -> list:
    """
    Read recent events from the event log.
    
    Args:
        count: Number of recent events to return
        
    Returns:
        List of event strings (most recent last)
    """
    try:
        if EVENT_LOG_FILE.exists():
            with open(EVENT_LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return [line.strip() for line in lines[-count:] if line.strip()]
    except Exception as e:
        logger.warning(f"Could not read event log: {e}")
    return []
