"""
VOID Core Brain Module
======================

Provides developer mode control and brain-level logging.
Used by: repair_system.py, file_manager.py, self_modifier.py
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger("void.brain")

# Developer mode flag — controls write access for repair/self-modification.
# Default True so self-repair and file operations work out of the box.
_developer_mode = True

# Project root
ROOT_DIR = Path(__file__).parent.parent


def is_developer_mode() -> bool:
    """Check if developer mode is enabled."""
    return _developer_mode


def enable_developer_mode():
    """Enable developer mode (allows file writes, repairs, upgrades)."""
    global _developer_mode
    _developer_mode = True
    _log_brain("DEV_MODE", "Developer mode ENABLED")


def disable_developer_mode():
    """Disable developer mode (read-only, safe mode)."""
    global _developer_mode
    _developer_mode = False
    _log_brain("DEV_MODE", "Developer mode DISABLED")


def toggle_developer_mode() -> bool:
    """Toggle developer mode and return the new state."""
    global _developer_mode
    _developer_mode = not _developer_mode
    state = "ENABLED" if _developer_mode else "DISABLED"
    _log_brain("DEV_MODE", f"Developer mode {state}")
    return _developer_mode


def _log_brain(action: str, details: str = ""):
    """
    Log brain-level events.
    
    Args:
        action: Action identifier (e.g., 'DIAGNOSTICS_START', 'REPAIR_EXECUTE')
        details: Human-readable details
    """
    msg = f"[BRAIN] {action}"
    if details:
        msg += f": {details}"
    logger.info(msg)


# Identity constants
OWNER_NAME = "Mridul Sharma"
ASSISTANT_NAME = "VOID"
ASSISTANT_TITLE = "Holographic Cybernetic Assistant"
