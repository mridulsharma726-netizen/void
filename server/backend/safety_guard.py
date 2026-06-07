"""
VOID CVCS Safety Guard & Permission Manager
==========================================
Enforces the 5-tier safety permission model (Levels 1, 2, 3, 3.5, 4),
manages session timeouts (30-minute Level 3 session, IDE-scoped Level 3.5),
logs desktop actions, and prevents destructive actions.
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("void.cvcs.safety")

# Set paths
ROOT_DIR = Path(__file__).parent.parent.parent
CONFIG_PATH = ROOT_DIR / "memory" / "data" / "cvcs_config.json"
CONTROL_LOG_PATH = ROOT_DIR / "logs" / "desktop_control.log"

class SafetyGuard:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SafetyGuard, cls).__new__(cls, *args, **kwargs)
        return cls._instance
        
    def __init__(self):
        # Prevent re-initialization
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        
        # Default config
        self.permission_level = 2.0  # Level 2 (Assisted Control) is the safe default
        self.session_start_time = 0.0
        self.session_duration = 1800.0  # 30 minutes in seconds
        self.pre_warning_sent = False
        
        # IDE Process ID to track Level 3.5
        self.ide_process_name = "code.exe"
        self.ide_active = False
        
        self.load_config()
        
    def load_config(self):
        """Load state configuration from disk."""
        try:
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.permission_level = float(data.get("permission_level", 2.0))
                    self.session_start_time = float(data.get("session_start_time", 0.0))
                    self.session_duration = float(data.get("session_duration", 1800.0))
                    self.pre_warning_sent = bool(data.get("pre_warning_sent", False))
                    logger.info(f"[SAFETY] Loaded config: Level {self.permission_level}")
            else:
                self.save_config()
        except Exception as e:
            logger.error(f"[SAFETY] Error loading configuration: {e}")
            
    def save_config(self):
        """Save configuration state to disk."""
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "permission_level": self.permission_level,
                    "session_start_time": self.session_start_time,
                    "session_duration": self.session_duration,
                    "pre_warning_sent": self.pre_warning_sent
                }, f, indent=2)
        except Exception as e:
            logger.error(f"[SAFETY] Error saving configuration: {e}")
            
    def set_permission_level(self, level: float, duration_seconds: float = 1800.0) -> Dict[str, Any]:
        """
        Transition current permission level.
        Levels:
          1.0: View Only
          2.0: Assisted Control
          3.0: Authorized Session
          3.5: Developer Session
          4.0: Automation Mode
        """
        self.permission_level = float(level)
        self.pre_warning_sent = False
        
        if self.permission_level == 3.0:
            self.session_start_time = time.time()
            self.session_duration = duration_seconds
            logger.info(f"[SAFETY] Authorized Level 3 Session started for {duration_seconds}s")
        elif self.permission_level == 3.5:
            self.session_start_time = time.time()
            # Infinite duration, scoped by process state (tracked in checker)
            self.session_duration = 0.0 
            logger.info("[SAFETY] Authorized Level 3.5 Developer Session started (Scope: VS Code/IDE)")
        else:
            self.session_start_time = 0.0
            self.session_duration = 0.0
            
        self.save_config()
        
        level_names = {
            1.0: "Level 1 (View Only)",
            2.0: "Level 2 (Assisted Control)",
            3.0: "Level 3 (Authorized Session)",
            3.5: "Level 3.5 (Developer Session)",
            4.0: "Level 4 (Automation Mode)"
        }
        
        return {
            "status": "ok",
            "message": f"Permissions set to {level_names.get(self.permission_level, str(self.permission_level))}",
            "level": self.permission_level
        }
        
    def check_session_expiry(self) -> Optional[Dict[str, Any]]:
        """
        Check session timers. Downgrades to Level 2 automatically on expiration.
        Returns alert payloads if pre-timeout warnings should trigger.
        """
        now = time.time()
        
        # Check Level 3 session expiration
        if self.permission_level == 3.0:
            elapsed = now - self.session_start_time
            remaining = self.session_duration - elapsed
            
            if remaining <= 0:
                logger.warning("[SAFETY] Level 3 session expired. Downgrading to Level 2.")
                self.set_permission_level(2.0)
                self.log_action("SYSTEM", "SafetyGuard", "Downgrade (Session Expiry)", None, True)
                return {"event": "expired", "message": "Authorized control session has expired. Reverted to Level 2."}
                
            # Trigger warning at 5 minutes remaining (300 seconds)
            if remaining <= 300.0 and not self.pre_warning_sent:
                self.pre_warning_sent = True
                self.save_config()
                logger.info("[SAFETY] Issuing 5-minute Level 3 expiry warning.")
                return {
                    "event": "warning",
                    "message": "Authorized control session expires in 5 minutes.",
                    "remaining_seconds": int(remaining)
                }
                
        # Check Level 3.5 session validation
        elif self.permission_level == 3.5:
            # Verify if VS Code/IDE is still open
            if not self.check_ide_active():
                logger.warning("[SAFETY] IDE closed. Terminating Level 3.5 Developer Session.")
                self.set_permission_level(2.0)
                self.log_action("SYSTEM", "SafetyGuard", "Downgrade (IDE Closed)", None, True)
                return {"event": "expired", "message": "IDE closed. Developer session terminated."}
                
        return None
        
    def check_ide_active(self) -> bool:
        """Scan active process tables for standard developer environments."""
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                name = proc.info['name'].lower()
                if "code.exe" in name or "idea64.exe" in name or "studio64.exe" in name:
                    return True
        except Exception:
            # Fallback if psutil fails: assume True to avoid false-positive kickout
            return True
        return False
        
    def revoke_session(self) -> Dict[str, Any]:
        """Manually drop permissions immediately to Level 2."""
        logger.info("[SAFETY] Session manually revoked. Dropping to Level 2.")
        res = self.set_permission_level(2.0)
        self.log_action("USER", "SafetyGuard", "Manual Session Revoke", None, True)
        return res
        
    def handle_system_state_change(self, event: str) -> None:
        """Downgrade instantly during screen locks, logouts, or reboots."""
        logger.warning(f"[SAFETY] System event detected: {event}. Downgrading to Level 2 for security.")
        self.set_permission_level(2.0)
        self.log_action("SYSTEM", "SafetyGuard", f"Downgrade (Event: {event})", None, True)
        
    def validate_action(self, action: str, target: str) -> Tuple[bool, str]:
        """
        Verify if the given desktop command conforms to safety constraints.
        Returns: (is_allowed, reason_message)
        """
        action_lower = action.lower().strip()
        target_lower = target.lower().strip()
        
        # 1. Block destructive operations across all levels
        destructive_terms = [
            "rmdir /s", "del /f", "format ", "mkfs", "rm -rf", "shutdown",
            "reg delete", "reg add", "net user", "net share", "ipconfig /release",
            "powershell -command", "admin", "privilege", "bypass", "taskkill /f /im system"
        ]
        
        if any(term in target_lower for term in destructive_terms):
            return False, "Action blocked: Destructive command terms detected."
            
        # 2. Block system files access
        protected_paths = [
            "c:\\windows", "system32", "syswow64", "\\drivers", "\\appdata\\local\\microsoft"
        ]
        if any(path in target_lower for path in protected_paths):
            return False, "Action blocked: Interacting with system-protected paths is prohibited."
            
        # 3. Handle Permission Matrix Levels
        
        # Level 1 (View Only)
        if self.permission_level == 1.0:
            return False, "Action blocked: View Only Mode (Level 1) is active."
            
        # Level 2 (Assisted Control)
        if self.permission_level == 2.0:
            # In execution flow, this will raise a frontend prompt overlay
            return True, "Assisted Control: Action approved after manual confirmation."
            
        # Level 3.5 (Developer Session)
        if self.permission_level == 3.5:
            # Limit scopes: files edited or apps launched must match development processes
            allowed_ide_apps = ["code", "chrome", "firefox", "explorer", "cmd", "powershell", "wt", "git", "flutter"]
            if action_lower in ["open_app", "close_app"]:
                if not any(app in target_lower for app in allowed_ide_apps):
                    return False, f"Action blocked: Open/close of '{target}' is restricted outside of Developer Scope."
            return True, "Developer Session: Action within active workspace parameters."
            
        return True, "Action approved under active authorization session."
        
    def log_action(self, actor: str, action: str, target: str, coords: Optional[Tuple[int, int]] = None, authorized: bool = True):
        """Log desktop control action to the audit logs file."""
        try:
            CONTROL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            log_entry = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "actor": actor,
                "permission_level": self.permission_level,
                "action": action,
                "target": target,
                "coordinates": coords,
                "authorized": authorized
            }
            with open(CONTROL_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"[SAFETY] Logging action failed: {e}")
            
# Helper interface
def check_action_allowed(action: str, target: str) -> Tuple[bool, str]:
    guard = SafetyGuard()
    return guard.validate_action(action, target)
