"""
VOID Filesystem Watchdog Module
===============================

Monitors specific folders for file changes (created, modified, deleted)
and runs registered automation workflows reactively.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger("void.core.automation.fs_watchdog")

class WatchdogHandler(FileSystemEventHandler):
    """Dispatches filesystem events to registered callbacks."""
    
    def __init__(self, callbacks: List[Callable[[str, str], None]]):
        super().__init__()
        self.callbacks = callbacks

    def on_any_event(self, event):
        # We only care about file modifications/creations/deletions
        if event.is_directory:
            return
            
        event_type = event.event_type  # 'created', 'modified', 'deleted'
        src_path = event.src_path
        
        logger.info(f"[WATCHDOG EVENT] File {event_type}: {src_path}")
        for callback in self.callbacks:
            try:
                callback(event_type, src_path)
            except Exception as e:
                logger.error(f"[WATCHDOG CALLBACK ERROR] Callback failed: {e}")

class FileSystemWatchdog:
    """Manages multiple folder watchers using watchdog observers."""
    
    def __init__(self):
        self.observer = Observer()
        self.watchers: Dict[str, Any] = {}  # path -> (watch_obj, handler, list of callbacks)
        self._started = False

    def watch_folder(self, folder_path: str, callback: Callable[[str, str], None]) -> bool:
        """Registers a folder to watch and adds a callback."""
        abs_path = os.path.abspath(folder_path)
        
        if not os.path.exists(abs_path):
            try:
                os.makedirs(abs_path, exist_ok=True)
            except Exception as e:
                logger.error(f"[WATCHDOG] Failed to create folder {abs_path}: {e}")
                return False
                
        if abs_path in self.watchers:
            # Append callback to existing path
            self.watchers[abs_path][2].append(callback)
            logger.info(f"[WATCHDOG] Added callback to existing watch path: {abs_path}")
            return True
            
        try:
            handler = WatchdogHandler([callback])
            watch_obj = self.observer.schedule(handler, abs_path, recursive=False)
            self.watchers[abs_path] = (watch_obj, handler, [callback])
            logger.info(f"[WATCHDOG] Started watching folder: {abs_path}")
            
            # Start observer if not already running
            self.start()
            return True
        except Exception as e:
            logger.error(f"[WATCHDOG] Failed to watch folder {abs_path}: {e}")
            return False

    def stop_watching(self, folder_path: str) -> bool:
        """Stops watching a specific folder."""
        abs_path = os.path.abspath(folder_path)
        if abs_path not in self.watchers:
            return False
            
        try:
            watch_obj = self.watchers[abs_path][0]
            self.observer.unschedule(watch_obj)
            del self.watchers[abs_path]
            logger.info(f"[WATCHDOG] Stopped watching folder: {abs_path}")
            return True
        except Exception as e:
            logger.error(f"[WATCHDOG] Failed to stop watching folder {abs_path}: {e}")
            return False

    def start(self):
        """Starts the main observer loop."""
        if not self._started:
            try:
                self.observer.start()
                self._started = True
                logger.info("[WATCHDOG] Observer thread started.")
            except Exception as e:
                logger.error(f"[WATCHDOG] Failed to start observer: {e}")

    def stop(self):
        """Stops the main observer loop."""
        if self._started:
            try:
                self.observer.stop()
                self.observer.join(timeout=2.0)
                self._started = False
                logger.info("[WATCHDOG] Observer thread stopped.")
            except Exception as e:
                logger.error(f"[WATCHDOG] Failed to stop observer cleanly: {e}")

    def list_active_watchers(self) -> List[Dict[str, Any]]:
        """Returns metadata about active watched paths for UI status routes."""
        active = []
        for path, (watch_obj, handler, callbacks) in self.watchers.items():
            active.append({
                "path": path,
                "callbacks_count": len(callbacks),
                "status": "active" if self._started else "paused"
            })
        return active

# Singleton instance
_fs_watchdog_instance: Optional[FileSystemWatchdog] = None

def get_fs_watchdog() -> FileSystemWatchdog:
    """Returns singleton instance of FileSystemWatchdog."""
    global _fs_watchdog_instance
    if _fs_watchdog_instance is None:
        _fs_watchdog_instance = FileSystemWatchdog()
    return _fs_watchdog_instance
