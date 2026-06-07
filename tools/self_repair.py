"""
VOID Self-Repair Wrapper
Bridges tools.self_repair calls to server/backend/repair_system.py.
"""

import sys
import os
from pathlib import Path

# Add server directory to path if not present
VOID_ROOT = Path(__file__).parent.parent
SERVER_DIR = VOID_ROOT / "server"

if str(SERVER_DIR) not in sys.path:
    sys.path.append(str(SERVER_DIR))

# Import actual repair from backend
try:
    from backend.repair_system import (
        repair_system,
        get_repair_result,
        RepairSystem
    )
except ImportError:
    # If standard import fails, try relative to server folder
    import sys
    sys.path.insert(0, str(SERVER_DIR))
    from backend.repair_system import (
        repair_system,
        get_repair_result,
        RepairSystem
    )
