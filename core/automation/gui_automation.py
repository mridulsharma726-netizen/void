"""
VOID Precision GUI Automation Module
====================================

Implements precise window-level control using pywinauto (Windows) and
coordinates fallback actions using pyautogui (cross-platform).
All actions are strictly checked against SafetyGuard permissions.
"""

import os
import sys
import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("void.core.automation.gui_automation")

# Fallback indicators
PYWINAUTO_AVAILABLE = False
PYAUTOGUI_AVAILABLE = False

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    pass

if sys.platform == "win32":
    try:
        import pywinauto
        PYWINAUTO_AVAILABLE = True
    except ImportError:
        pass

class GUIAutomator:
    """Orchestrates secure GUI control using pywinauto or pyautogui."""
    
    def __init__(self):
        from server.backend.safety_guard import SafetyGuard
        self.guard = SafetyGuard()
        
    def _verify_allowed(self, action: str, target: str) -> bool:
        """Runs the action through SafetyGuard validation."""
        allowed, reason = self.guard.validate_action(action, target)
        if not allowed:
            logger.warning(f"[GUI AUTOMATION] Gated action BLOCKED: {action} on {target}. Reason: {reason}")
            raise PermissionError(f"Action blocked by SafetyGuard: {reason}")
        return True

    def click_window_control(self, window_title: str, control_name: str) -> bool:
        """Locates a window and clicks a specific control/button by name."""
        self._verify_allowed("click", f"{window_title} -> {control_name}")
        
        if not PYWINAUTO_AVAILABLE:
            logger.warning("[GUI AUTOMATION] pywinauto not available. Falling back to pyautogui coordinate search...")
            return self._pyautogui_fallback_click(control_name)
            
        try:
            # Connect to desktop window
            from pywinauto import Desktop
            app = Desktop(backend="uia")
            
            # Find window
            win = app.window(title_re=f".*{window_title}.*")
            if not win.exists():
                logger.error(f"[GUI AUTOMATION] Window '{window_title}' not found.")
                return False
                
            win.set_focus()
            
            # Find control inside window
            control = win.child_window(title=control_name, control_type="Button")
            if not control.exists():
                # Try generic search by name
                control = win.child_window(title=control_name)
                
            if not control.exists():
                logger.error(f"[GUI AUTOMATION] Control '{control_name}' not found in window '{window_title}'.")
                return False
                
            control.click_input()
            logger.info(f"[GUI AUTOMATION] Clicked control '{control_name}' in window '{window_title}'")
            return True
            
        except Exception as e:
            logger.error(f"[GUI AUTOMATION] pywinauto action failed: {e}")
            return self._pyautogui_fallback_click(control_name)

    def type_in_window_control(self, window_title: str, control_name: str, text: str) -> bool:
        """Locates a window control and types text into it."""
        self._verify_allowed("type", f"{window_title} -> {control_name}")
        
        if not PYWINAUTO_AVAILABLE:
            logger.warning("[GUI AUTOMATION] pywinauto not available. Falling back to pyautogui keyboard input...")
            return self._pyautogui_fallback_type(text)
            
        try:
            from pywinauto import Desktop
            app = Desktop(backend="uia")
            win = app.window(title_re=f".*{window_title}.*")
            if not win.exists():
                logger.error(f"[GUI AUTOMATION] Window '{window_title}' not found.")
                return False
                
            win.set_focus()
            control = win.child_window(title=control_name, control_type="Edit")
            if not control.exists():
                control = win.child_window(title=control_name)
                
            if not control.exists():
                logger.error(f"[GUI AUTOMATION] Edit control '{control_name}' not found in window '{window_title}'.")
                return False
                
            control.type_keys(text, with_spaces=True)
            logger.info(f"[GUI AUTOMATION] Typed text in control '{control_name}' of window '{window_title}'")
            return True
            
        except Exception as e:
            logger.error(f"[GUI AUTOMATION] pywinauto typing failed: {e}")
            return self._pyautogui_fallback_type(text)

    def _pyautogui_fallback_click(self, label: str) -> bool:
        """Falls back to pyautogui coordinate matching if pywinauto fails."""
        if not PYAUTOGUI_AVAILABLE:
            return False
            
        try:
            # We can use screen monitor or screen OCR to find coordinates of target label
            from tools.cv_control import take_screenshot
            from tools.screen_ocr import find_text_coordinates
            
            shot = take_screenshot("temp_fallback.png")
            if shot["status"] == "ok":
                coords = find_text_coordinates(shot["filepath"], label)
                if coords:
                    cx, cy = coords[0], coords[1]
                    pyautogui.click(cx, cy)
                    logger.info(f"[GUI AUTOMATION] PyAutoGUI fallback clicked '{label}' at ({cx}, {cy})")
                    return True
            return False
        except Exception as e:
            logger.error(f"[GUI AUTOMATION] PyAutoGUI fallback click failed: {e}")
            return False

    def _pyautogui_fallback_type(self, text: str) -> bool:
        """Falls back to writing text via pyautogui."""
        if not PYAUTOGUI_AVAILABLE:
            return False
        try:
            pyautogui.write(text, interval=0.05)
            logger.info("[GUI AUTOMATION] PyAutoGUI fallback typed text successfully.")
            return True
        except Exception as e:
            logger.error(f"[GUI AUTOMATION] PyAutoGUI fallback type failed: {e}")
            return False

# Singleton instance
_gui_automator_instance: Optional[GUIAutomator] = None

def get_gui_automator() -> GUIAutomator:
    """Returns singleton instance of GUIAutomator."""
    global _gui_automator_instance
    if _gui_automator_instance is None:
        _gui_automator_instance = GUIAutomator()
    return _gui_automator_instance
