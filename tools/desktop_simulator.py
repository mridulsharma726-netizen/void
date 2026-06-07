"""
VOID Desktop Simulator Module
=============================
Handles mouse movement, keyboard typing, scrolling, and key shortcut triggers.
Includes active DPI scaling compensation and failsafe bounds checking.
"""

import logging
import time
import ctypes
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger("void.cvcs.simulator")

# Attempt PyAutoGUI import
try:
    import pyautogui
    pyautogui.FAILSAFE = True  # Move mouse to corner (0,0) to raise FailSafeException
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    logger.warning("[SIMULATOR] pyautogui library not installed in active environment.")


def get_dpi_scaling() -> float:
    """
    Retrieve the current monitor's DPI scaling ratio under Windows.
    Defaults to 1.0 (100% scaling) on failure or non-Windows OS.
    """
    try:
        # Query Windows DPI Awareness setting
        shcore = ctypes.windll.shcore
        # Set awareness to Monitor-Aware (value=2)
        shcore.SetProcessDpiAwareness(2)
        
        # Get scaling for primary monitor (0, 0)
        hdc = ctypes.windll.user32.GetDC(0)
        # LOGPIXELSX is index 88 (pixels per logical inch)
        logical_dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
        ctypes.windll.user32.ReleaseDC(0, hdc)
        
        # Standard DPI is 96 (100% scaling)
        scaling = logical_dpi / 96.0
        logger.info(f"[SIMULATOR] Detected logical DPI: {logical_dpi} (Scaling: {scaling:.2f})")
        return scaling
    except Exception as e:
        logger.debug(f"[SIMULATOR] DPI scale detection fallback (using 1.0): {e}")
        return 1.0


def scale_coordinates(x: int, y: int, scaling: float) -> Tuple[int, int]:
    """
    Scale absolute pixel coordinates by the DPI scaling ratio.
    """
    if scaling <= 0:
        scaling = 1.0
    return int(x / scaling), int(y / scaling)


def check_bounds(x: int, y: int) -> bool:
    """
    Check if the target coordinate lies within physical screen resolution boundaries.
    """
    if not PYAUTOGUI_AVAILABLE:
        return False
    try:
        width, height = pyautogui.size()
        return 0 <= x <= width and 0 <= y <= height
    except Exception:
        return False


def simulate_mouse_move(x: int, y: int, duration: float = 0.3) -> Dict[str, Any]:
    """
    Move the mouse pointer smoothly to specified coordinates.
    """
    if not PYAUTOGUI_AVAILABLE:
        return {"status": "error", "message": "pyautogui library not available."}
        
    scaling = get_dpi_scaling()
    scaled_x, scaled_y = scale_coordinates(x, y, scaling)
    
    if not check_bounds(scaled_x, scaled_y):
        return {"status": "error", "message": f"Target coordinates ({x}, {y}) out of screen bounds."}
        
    try:
        pyautogui.moveTo(scaled_x, scaled_y, duration=duration)
        return {
            "status": "ok",
            "message": f"Moved mouse to ({scaled_x}, {scaled_y}) [Scaled from ({x}, {y})]"
        }
    except pyautogui.FailSafeException:
        logger.error("[SIMULATOR FAILSAFE] Failsafe triggered by user! Aborting.")
        return {"status": "error", "message": "Automation aborted: Failsafe triggered."}
    except Exception as e:
        return {"status": "error", "message": f"Mouse move failed: {e}"}


def simulate_click(x: int, y: int, button: str = "left", clicks: int = 1, duration: float = 0.3) -> Dict[str, Any]:
    """
    Simulate a mouse click (left/right/double) at specific coordinates.
    """
    if not PYAUTOGUI_AVAILABLE:
        return {"status": "error", "message": "pyautogui library not available."}
        
    scaling = get_dpi_scaling()
    scaled_x, scaled_y = scale_coordinates(x, y, scaling)
    
    if not check_bounds(scaled_x, scaled_y):
        return {"status": "error", "message": f"Target coordinates ({x}, {y}) out of screen bounds."}
        
    try:
        pyautogui.moveTo(scaled_x, scaled_y, duration=duration)
        pyautogui.click(scaled_x, scaled_y, button=button, clicks=clicks)
        return {
            "status": "ok",
            "message": f"Simulated {button} click ({clicks}x) at ({scaled_x}, {scaled_y}) [Scaled from ({x}, {y})]"
        }
    except pyautogui.FailSafeException:
        logger.error("[SIMULATOR FAILSAFE] Failsafe triggered by user! Aborting.")
        return {"status": "error", "message": "Automation aborted: Failsafe triggered."}
    except Exception as e:
        return {"status": "error", "message": f"Mouse click failed: {e}"}


def simulate_type(text: str, interval: float = 0.05) -> Dict[str, Any]:
    """
    Type text sequentially at the current focused cursor position.
    """
    if not PYAUTOGUI_AVAILABLE:
        return {"status": "error", "message": "pyautogui library not available."}
        
    try:
        pyautogui.write(text, interval=interval)
        # Truncate logged text for security/logs
        log_text = text[:15] + "..." if len(text) > 15 else text
        return {"status": "ok", "message": f"Typed text: '{log_text}'"}
    except pyautogui.FailSafeException:
        logger.error("[SIMULATOR FAILSAFE] Failsafe triggered by user! Aborting.")
        return {"status": "error", "message": "Automation aborted: Failsafe triggered."}
    except Exception as e:
        return {"status": "error", "message": f"Typing failed: {e}"}


def simulate_shortcut(keys: List[str]) -> Dict[str, Any]:
    """
    Press and release a list of keys simultaneously (e.g. ['ctrl', 'shift', 'p']).
    """
    if not PYAUTOGUI_AVAILABLE:
        return {"status": "error", "message": "pyautogui library not available."}
        
    try:
        pyautogui.hotkey(*keys)
        return {"status": "ok", "message": f"Executed hotkey shortcut: {'+'.join(keys)}"}
    except pyautogui.FailSafeException:
        return {"status": "error", "message": "Automation aborted: Failsafe triggered."}
    except Exception as e:
        return {"status": "error", "message": f"Shortcut trigger failed: {e}"}


def simulate_scroll(amount: int) -> Dict[str, Any]:
    """
    Scroll vertical mouse wheel. Positive amount scrolls up; negative scrolls down.
    """
    if not PYAUTOGUI_AVAILABLE:
        return {"status": "error", "message": "pyautogui library not available."}
        
    try:
        pyautogui.scroll(amount)
        direction = "up" if amount > 0 else "down"
        return {"status": "ok", "message": f"Scrolled mouse {direction} by {abs(amount)} clicks"}
    except pyautogui.FailSafeException:
        return {"status": "error", "message": "Automation aborted: Failsafe triggered."}
    except Exception as e:
        return {"status": "error", "message": f"Scrolling failed: {e}"}


def simulate_drag(start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> Dict[str, Any]:
    """
    Perform a drag-and-drop mouse sequence from start coordinates to end coordinates.
    """
    if not PYAUTOGUI_AVAILABLE:
        return {"status": "error", "message": "pyautogui library not available."}
        
    scaling = get_dpi_scaling()
    sx, sy = scale_coordinates(start_x, start_y, scaling)
    ex, ey = scale_coordinates(end_x, end_y, scaling)
    
    try:
        pyautogui.moveTo(sx, sy, duration=0.2)
        pyautogui.dragTo(ex, ey, duration=duration, button="left")
        return {"status": "ok", "message": f"Dragged cursor from ({sx}, {sy}) to ({ex}, {ey})"}
    except pyautogui.FailSafeException:
        return {"status": "error", "message": "Automation aborted: Failsafe triggered."}
    except Exception as e:
        return {"status": "error", "message": f"Drag simulation failed: {e}"}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing DPI Awareness:")
    scale = get_dpi_scaling()
    print(f"Active DPI Scaling Factor: {scale}")
    if PYAUTOGUI_AVAILABLE:
        size = pyautogui.size()
        print(f"Screen Resolution (Logical): {size}")
        print(f"Screen Resolution (Physical): ({int(size[0]*scale)}, {int(size[1]*scale)})")
