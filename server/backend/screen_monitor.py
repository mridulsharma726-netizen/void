"""
VOID CVCS Screen Monitor & Watch Loop
====================================
Observes foreground window titles, terminal/editor logs, and system events.
Executes safety-polling cycles (every 10s) and triggers alerts on build failures,
crashes, or compiler errors.
"""

import time
import logging
import asyncio
import threading
import ctypes
from typing import Dict, Any, List, Optional
from pathlib import Path

# Import local controllers
try:
    from tools.cv_control import get_foreground_window_bounds, take_screenshot, crop_image, scan_ocr_text
    from server.backend.safety_guard import SafetyGuard
    CVCS_LIBS_AVAILABLE = True
except ImportError:
    CVCS_LIBS_AVAILABLE = False

logger = logging.getLogger("void.cvcs.monitor")

class ScreenMonitor:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ScreenMonitor, cls).__new__(cls, *args, **kwargs)
        return cls._instance
        
    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        
        self.watch_mode_active = False
        self.monitor_thread = None
        self.running = False
        self.notifications_queue: List[Dict[str, Any]] = []
        
        # Last states to avoid duplicate alerts
        self.last_foreground_title = ""
        self.last_error_signature = ""
        
    def add_notification(self, category: str, title: str, message: str):
        """Append a status alert notification for HUD polling."""
        logger.info(f"[MONITOR ALERT] {category.upper()}: {title} - {message}")
        self.notifications_queue.append({
            "timestamp": time.time(),
            "category": category,
            "title": title,
            "message": message,
            "read": False
        })
        
    def get_unread_notifications(self) -> List[Dict[str, Any]]:
        """Retrieve and clear queued screen alerts."""
        unread = [n for n in self.notifications_queue if not n["read"]]
        for n in unread:
            n["read"] = True
        return unread
        
    def toggle_watch_mode(self, active: bool) -> Dict[str, Any]:
        """Activate or deactivate the 10-second polling and event monitors."""
        self.watch_mode_active = active
        if active:
            if not self.running:
                self.start_monitor_loop()
            return {"status": "ok", "message": "Screen monitoring enabled."}
        else:
            return {"status": "ok", "message": "Screen monitoring disabled."}
            
    def get_foreground_window_title(self) -> str:
        """Fetch foreground window title using ctypes (Windows)."""
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd:
                return ""
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
                return buffer.value.strip()
        except Exception as e:
            logger.debug(f"[MONITOR] Error getting window title: {e}")
        return ""
        
    def scan_terminal_for_errors(self, screenshot_path: str) -> Optional[str]:
        """
        If VS Code or IDE is open, crop terminal boundaries (bottom 30% of window)
        and scan for error signatures using Tesseract.
        """
        bounds = get_foreground_window_bounds()
        if not bounds:
            return None
            
        # Crop to terminal segment (bottom 30% panel height)
        term_left = bounds["left"]
        term_top = bounds["top"] + int(bounds["height"] * 0.7)
        term_w = bounds["width"]
        term_h = int(bounds["height"] * 0.3)
        
        cropped_path = crop_image(screenshot_path, {
            "left": term_left,
            "top": term_top,
            "width": term_w,
            "height": term_h
        })
        
        if not cropped_path or not Path(cropped_path).exists():
            return None
            
        try:
            # Perform OCR on terminal text
            words = scan_ocr_text(cropped_path)
            full_line = " ".join([w["text"] for w in words]).lower()
            
            # Simple error signatures scan
            error_keywords = ["error", "exception", "failed", "build failure", "warning"]
            detected_keywords = [kw for kw in error_keywords if kw in full_line]
            
            if detected_keywords:
                # Clean up cropped path to avoid space bloat
                try:
                    os.remove(cropped_path)
                except Exception:
                    pass
                return f"Terminal Alert: Detected keywords: {', '.join(detected_keywords)}"
        except Exception as e:
            logger.debug(f"[MONITOR] Terminal OCR check failed: {e}")
            
        # Clean up temporary cropped file
        if cropped_path:
            try:
                os.remove(cropped_path)
            except Exception:
                pass
                
        return None
        
    def start_monitor_loop(self):
        """Spawn monitor loop in background thread."""
        if self.running:
            return
        self.running = True
        self.monitor_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("[MONITOR] Background screen monitor thread started.")
        
    def stop_monitor_loop(self):
        """Stop background monitor thread."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
            self.monitor_thread = None
        logger.info("[MONITOR] Background screen monitor thread stopped.")
        
    def _run_loop(self):
        """Continuous safe polling execution (10s intervals + event triggers)."""
        while self.running:
            try:
                if not CVCS_LIBS_AVAILABLE:
                    time.sleep(2.0)
                    continue
                    
                # 1. Enforce safety session validation timeouts
                guard = SafetyGuard()
                expiry_alert = guard.check_session_expiry()
                if expiry_alert:
                    self.add_notification(
                        "security",
                        "Session Status",
                        expiry_alert["message"]
                    )
                    
                # 2. Check window transitions
                title = self.get_foreground_window_title()
                if title and title != self.last_foreground_title:
                    self.last_foreground_title = title
                    logger.debug(f"[MONITOR] Focus transition: {title}")
                    
                # 3. Handle active screen inspections (if Watch Mode is toggled on)
                if self.watch_mode_active:
                    # Take primary screen capture
                    shot = take_screenshot("monitor_inspect.png")
                    if shot["status"] == "ok" and ("vscode" in title.lower() or "visual studio code" in title.lower()):
                        # Inspect code terminal segment for failures
                        error_alert = self.scan_terminal_for_errors(shot["filepath"])
                        if error_alert and error_alert != self.last_error_signature:
                            self.last_error_signature = error_alert
                            self.add_notification(
                                "build",
                                "IDE Build Issue Detected",
                                error_alert
                            )
                            
            except Exception as e:
                logger.error(f"[MONITOR] Exception in process loop: {e}")
                
            # Perform 10 seconds safety poll sleep
            time.sleep(10.0)
            
# Helper interface
def get_monitor_instance() -> ScreenMonitor:
    return ScreenMonitor()
