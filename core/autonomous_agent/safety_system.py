import sys
import logging
from pathlib import Path
from typing import Dict, Any, Tuple

# Set path to include server directory so we can import safety_guard
ROOT_DIR = Path(__file__).parent.parent.parent
SERVER_DIR = ROOT_DIR / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

logger = logging.getLogger("void.autonomous_agent.safety")

try:
    from backend.safety_guard import SafetyGuard
except ImportError:
    # Standalone fallback if server cannot be imported
    class SafetyGuard:
        permission_level = 2.0
        def validate_action(self, action: str, target: str) -> Tuple[bool, str]:
            return True, "Approved"

class AgentSafetySystem:
    def __init__(self, root_dir: str = None):
        self.guard = SafetyGuard()
        if not root_dir:
            root_dir = str(ROOT_DIR)
        from core.autonomous_agent.sandbox_validator import SandboxValidator
        self.sandbox = SandboxValidator(root_dir)

    def get_level(self) -> float:
        """Get current safety level from the guard config."""
        # Reload config to get the latest state from disk
        if hasattr(self.guard, "load_config"):
            self.guard.load_config()
        return getattr(self.guard, "permission_level", 2.0)

    def check_file_action(self, action: str, file_path: str) -> Dict[str, Any]:
        """
        Check if a file action is permitted based on the safety level.
        Actions: "read", "write", "delete", "rename", "create"
        """
        level = self.get_level()
        action = action.lower().strip()

        # Level 1 (1.0) - View Only: Read only, no modifications.
        if level <= 1.0:
            if action == "read":
                return {"allowed": True, "requires_approval": False, "reason": "Read permitted in L1"}
            else:
                return {"allowed": False, "requires_approval": False, "reason": "L1 restricts all write/edit operations."}

        # Level 2 (2.0) - Suggest Changes: Generates diffs/plans, requires confirmation.
        if level <= 2.0:
            if action == "read":
                return {"allowed": True, "requires_approval": False, "reason": "Read permitted in L2"}
            else:
                return {"allowed": True, "requires_approval": True, "reason": "L2 edits require user confirmation."}

        # Level 3 (3.0) - Edit Files: Allows writes/edits with approval, no commands.
        if level <= 3.0:
            if action == "read":
                return {"allowed": True, "requires_approval": False, "reason": "Read permitted in L3"}
            else:
                return {"allowed": True, "requires_approval": True, "reason": "L3 edits require user approval."}

        # Level 3.5 (3.5) - Developer Session: Allows edits & build commands automatically,
        # but requires confirmation for destructive/non-whitelisted actions.
        if level <= 3.5:
            # File operations are automatically approved in L3.5/L4
            return {"allowed": True, "requires_approval": False, "reason": "L3.5 allows automatic file edits."}

        # Level 4 (4.0) - Fully Autonomous: Automatic approval for all writes.
        return {"allowed": True, "requires_approval": False, "reason": "L4 allows fully autonomous file operations."}

    def check_command_action(self, command: str) -> Dict[str, Any]:
        """
        Check if a shell command execution is permitted.
        """
        # Run command validation check using the sandbox validator
        sandbox_check = self.sandbox.validate_command(command)
        if not sandbox_check["allowed"]:
            return {"allowed": False, "requires_approval": False, "reason": sandbox_check["reason"]}

        level = self.get_level()
        cmd_lower = command.lower().strip()

        # Destructive terms check
        destructive_terms = [
            "rmdir /s", "del /f", "format ", "mkfs", "rm -rf", "shutdown",
            "reg delete", "reg add", "net user", "net share", "ipconfig /release",
            "powershell -command", "admin", "privilege", "bypass", "taskkill /f /im system"
        ]
        if any(term in cmd_lower for term in destructive_terms):
            return {"allowed": False, "requires_approval": False, "reason": "Command blocked: Destructive command terms detected."}

        # Levels 1, 2, 3 do not allow command executions at all.
        if level <= 3.0:
            return {"allowed": False, "requires_approval": False, "reason": f"Level {level} does not allow terminal execution."}

        # Level 3.5 (Developer Session) allows whitelisted build/test commands, but requires approval for others.
        if level <= 3.5:
            whitelisted_words = ["python", "pytest", "npm", "pip", "git", "flutter", "node", "cargo", "go", "gcc", "g++", "clang"]
            first_word = cmd_lower.split()[0] if cmd_lower.split() else ""
            if first_word in whitelisted_words:
                return {"allowed": True, "requires_approval": False, "reason": "Command whitelisted in L3.5"}
            else:
                return {"allowed": True, "requires_approval": True, "reason": "Non-whitelisted command in L3.5 requires confirmation."}

        # Level 4 (4.0) - Fully Autonomous allows all execution automatically.
        return {"allowed": True, "requires_approval": False, "reason": "Fully Autonomous mode allows all executions."}
