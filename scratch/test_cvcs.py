import sys
import os
from pathlib import Path

# Ensure project root is in path
ROOT_DIR = Path(__file__).parent.parent.parent.parent.parent.parent / "OneDrive" / "Desktop" / "void" / "VOID"
sys.path.insert(0, str(ROOT_DIR))

print("=== Diagnostic Verification Script ===")
print(f"Project root resolved: {ROOT_DIR}")
print(f"Python executable: {sys.executable}")

try:
    import pyautogui
    print("[OK] PyAutoGUI imported successfully.")
    print(f"  pyautogui size: {pyautogui.size()}")
except Exception as e:
    print(f"[ERROR] PyAutoGUI import failed: {e}")

try:
    import mss
    print("[OK] mss imported successfully.")
    with mss.mss() as sct:
        print(f"  mss monitors: {sct.monitors}")
except Exception as e:
    print(f"[ERROR] mss import failed: {e}")

try:
    import pytesseract
    print("[OK] pytesseract imported successfully.")
except Exception as e:
    print(f"[ERROR] pytesseract import failed: {e}")

try:
    from tools.desktop_simulator import get_dpi_scaling
    print(f"[OK] tools.desktop_simulator.get_dpi_scaling works. Value: {get_dpi_scaling()}")
except Exception as e:
    print(f"[ERROR] tools.desktop_simulator load failed: {e}")

try:
    from tools.cv_control import get_foreground_window_bounds
    print(f"[OK] tools.cv_control.get_foreground_window_bounds works. Value: {get_foreground_window_bounds()}")
except Exception as e:
    print(f"[ERROR] tools.cv_control load failed: {e}")

try:
    from server.backend.safety_guard import SafetyGuard
    guard = SafetyGuard()
    print(f"[OK] server.backend.safety_guard.SafetyGuard compiles and instantiates. Level: {guard.permission_level}")
except Exception as e:
    print(f"[ERROR] server.backend.safety_guard load failed: {e}")

try:
    from server.backend.screen_monitor import ScreenMonitor
    monitor = ScreenMonitor()
    print("[OK] server.backend.screen_monitor.ScreenMonitor compiles and instantiates.")
except Exception as e:
    print(f"[ERROR] server.backend.screen_monitor load failed: {e}")

print("=== Diagnostics Complete ===")
