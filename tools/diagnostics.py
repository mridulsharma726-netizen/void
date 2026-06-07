"""
VOID Diagnostics Wrapper
Bridges tools.diagnostics calls to server/backend/diagnostics.py.
"""

import sys
import os
from pathlib import Path

# Add server directory to path if not present
VOID_ROOT = Path(__file__).parent.parent
SERVER_DIR = VOID_ROOT / "server"

if str(SERVER_DIR) not in sys.path:
    sys.path.append(str(SERVER_DIR))

# Import actual diagnostics from backend
try:
    from backend.diagnostics import (
        run_full_diagnostics,
        get_quick_status,
        get_diagnostics,
        DiagnosticsEngine,
        check_backend,
        check_stt,
        check_tts,
        check_memory,
        check_dependencies,
        check_tool_modules,
        check_internet
    )
except ImportError:
    # If standard import fails, try relative to server folder
    import sys
    sys.path.insert(0, str(SERVER_DIR))
    from backend.diagnostics import (
        run_full_diagnostics,
        get_quick_status,
        get_diagnostics,
        DiagnosticsEngine,
        check_backend,
        check_stt,
        check_tts,
        check_memory,
        check_dependencies,
        check_tool_modules,
        check_internet
    )
