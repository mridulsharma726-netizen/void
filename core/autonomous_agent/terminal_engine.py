import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any

from core.autonomous_agent.safety_system import AgentSafetySystem

class AgentTerminalEngine:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir).resolve()
        self.log_file = self.root_dir / "logs" / "agent_terminal.log"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.safety = AgentSafetySystem(str(self.root_dir))

    def _log_command(self, command: str, status: str, exit_code: int = -1, output: str = ""):
        """Log command execution details to logs/agent_terminal.log."""
        try:
            import time
            timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
            log_entry = (
                f"[{timestamp}] Command: {command}\n"
                f"Status: {status} | Exit Code: {exit_code}\n"
                f"Output Preview: {output[:100].strip()}\n"
                f"{'-'*40}\n"
            )
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception:
            pass

    async def execute_command(self, command: str, bypass_safety: bool = False) -> Dict[str, Any]:
        """
        Run a terminal command asynchronously, verifying permissions first.
        """
        if not bypass_safety:
            # 1. Check safety system
            check = self.safety.check_command_action(command)
            if not check["allowed"]:
                self._log_command(command, f"BLOCKED: {check['reason']}")
                return {"status": "error", "message": check["reason"]}
                
            if check["requires_approval"]:
                return {
                    "status": "pending_confirmation",
                    "action": "execute",
                    "command": command,
                    "message": check["reason"]
                }

        # 2. Run command
        try:
            # Run in shell, within root_dir
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.root_dir)
            )

            stdout_bytes, stderr_bytes = await process.communicate()
            exit_code = process.returncode
            
            stdout = stdout_bytes.decode("utf-8", errors="ignore")
            stderr = stderr_bytes.decode("utf-8", errors="ignore")

            self._log_command(command, "SUCCESS" if exit_code == 0 else "FAIL", exit_code, stdout or stderr)

            return {
                "status": "ok",
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr
            }
        except Exception as e:
            self._log_command(command, f"EXCEPTION: {str(e)}")
            return {"status": "error", "message": str(e)}
