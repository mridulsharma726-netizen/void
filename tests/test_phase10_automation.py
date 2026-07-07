import os
import sys
import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
if str(ROOT_DIR / "server") not in sys.path:
    sys.path.append(str(ROOT_DIR / "server"))

from core.automation.fs_watchdog import FileSystemWatchdog
from core.automation.gui_automation import GUIAutomator

class TestPhase10Automation(unittest.TestCase):
    
    def setUp(self):
        self.test_dir = ROOT_DIR / "tests" / "watchdog_test_temp"
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(exist_ok=True)

    def tearDown(self):
        if self.test_dir.exists():
            try:
                shutil.rmtree(self.test_dir)
            except Exception:
                pass

    def test_watchdog_registration_and_event(self):
        """Verify that a folder watcher can be registered and callback triggers on file creation."""
        watchdog = FileSystemWatchdog()
        
        callback_called = False
        captured_event = ""
        captured_path = ""
        
        def test_cb(event_type, path):
            nonlocal callback_called, captured_event, captured_path
            callback_called = True
            captured_event = event_type
            captured_path = path
            
        success = watchdog.watch_folder(str(self.test_dir), test_cb)
        self.assertTrue(success)
        
        # Verify it lists in active watchers
        active = watchdog.list_active_watchers()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["path"], os.path.abspath(str(self.test_dir)))
        
        # Manually trigger handler event (mocking watchdog system event)
        handler = watchdog.watchers[os.path.abspath(str(self.test_dir))][1]
        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.event_type = "created"
        mock_event.src_path = str(self.test_dir / "new_file.txt")
        
        handler.on_any_event(mock_event)
        
        self.assertTrue(callback_called)
        self.assertEqual(captured_event, "created")
        self.assertEqual(captured_path, str(self.test_dir / "new_file.txt"))
        
        # Clean up
        watchdog.stop_watching(str(self.test_dir))
        watchdog.stop()

    def test_gui_automation_permission_gating(self):
        """Verify that GUIAutomator checks SafetyGuard before running actions."""
        automator = GUIAutomator()
        
        # Mock SafetyGuard to block action
        with patch.object(automator.guard, "validate_action", return_value=(False, "Restricted by user")):
            with self.assertRaises(PermissionError):
                automator.click_window_control("Notepad", "File")
                
            with self.assertRaises(PermissionError):
                automator.type_in_window_control("Notepad", "Edit", "Hello world")

    def test_gui_automation_fallback_path(self):
        """Verify that GUIAutomator executes fallbacks when pywinauto is unavailable."""
        automator = GUIAutomator()
        
        # Mock SafetyGuard to ALLOW action
        with patch.object(automator.guard, "validate_action", return_value=(True, "Allowed")):
            # Force fallback by patching PYWINAUTO_AVAILABLE to False
            with patch("core.automation.gui_automation.PYWINAUTO_AVAILABLE", False):
                # Mock fallback methods
                automator._pyautogui_fallback_click = MagicMock(return_value=True)
                automator._pyautogui_fallback_type = MagicMock(return_value=True)
                
                click_ok = automator.click_window_control("Notepad", "File")
                self.assertTrue(click_ok)
                automator._pyautogui_fallback_click.assert_called_once_with("File")
                
                type_ok = automator.type_in_window_control("Notepad", "Edit", "Hello")
                self.assertTrue(type_ok)
                automator._pyautogui_fallback_type.assert_called_once_with("Hello")

if __name__ == "__main__":
    unittest.main()
