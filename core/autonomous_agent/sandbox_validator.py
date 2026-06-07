import os
import re
from pathlib import Path
from typing import Dict, Any, List

class SandboxValidator:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir).resolve()
        
        # Dangerous executables or shell keywords
        self.banned_executables = {
            "rmdir", "del", "format", "mkfs", "shutdown", "reg", "net", 
            "ipconfig", "powershell", "cmd.exe", "curl", "wget", "scp", "ftp",
            "ssh", "sftp", "telnet", "nc", "netcat", "nmap", "dd", "chmod", 
            "chown", "sudo", "su", "passwd", "systemctl", "service"
        }
        
        # Blacklisted command substrings
        self.banned_patterns = [
            r"rm\s+-rf",
            r"dev/null",
            r"dev/urandom",
            r">\s*/etc",
            r">\s*/var",
            r">\s*/usr",
            r"system32",
            r"syswow64",
            r"registry",
            r"bypass",
            r"taskkill"
        ]

    def is_path_safe(self, path_str: str) -> bool:
        """Verify that any target path lies inside the root workspace folder."""
        try:
            target_path = Path(path_str).resolve()
            # If path is relative, resolve it against root_dir
            if not target_path.is_absolute():
                target_path = (self.root_dir / path_str).resolve()
            return self.root_dir in target_path.parents or target_path == self.root_dir
        except Exception:
            return False

    def validate_command(self, command: str) -> Dict[str, Any]:
        """
        Scan a command line string for safety issues.
        Returns:
            dict: {"allowed": bool, "reason": str}
        """
        cmd_strip = command.strip()
        if not cmd_strip:
            return {"allowed": False, "reason": "Command is empty."}

        # 1. Parse command parts
        parts = cmd_strip.split()
        first_word = parts[0].lower()
        # Clean extensions if absolute path to executable
        first_word = os.path.basename(first_word).split('.')[0]

        # 2. Check banned executables
        if first_word in self.banned_executables:
            return {
                "allowed": False,
                "reason": f"Banned executable execution detected: '{first_word}' is prohibited."
            }

        # 3. Check banned regex patterns
        for pattern in self.banned_patterns:
            if re.search(pattern, cmd_strip, re.IGNORECASE):
                return {
                    "allowed": False,
                    "reason": f"Banned command pattern detected matching: '{pattern}'"
                }

        # 4. Check path escape attempts
        # Look for double dots indicating directory traversal
        if ".." in cmd_strip:
            # Check if any path segments resolve outside root_dir
            for part in parts:
                if ".." in part:
                    # Clean potential command arguments or flags
                    clean_path = part.lstrip("-/\\").split("=")[-1]
                    if not self.is_path_safe(clean_path):
                        return {
                            "allowed": False,
                            "reason": f"Directory traversal warning: Path '{part}' goes outside authorized workspace."
                        }

        return {"allowed": True, "reason": "Command passed sandbox security screening."}
