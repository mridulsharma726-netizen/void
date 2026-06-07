import os
import shutil
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.autonomous_agent.safety_system import AgentSafetySystem
from tools.file_manager import generate_diff, _is_path_allowed, _get_backup_path

class AgentFileEngine:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir).resolve()
        self.safety = AgentSafetySystem()

    def _resolve_path(self, path: str) -> Path:
        """Resolve path to absolute, checking it is within project root."""
        resolved = (self.root_dir / path).resolve()
        if not str(resolved).startswith(str(self.root_dir)):
            raise PermissionError(f"Access denied: Path {path} is outside project root")
        return resolved

    def read_file(self, path: str) -> Dict[str, Any]:
        """Read file contents safely."""
        try:
            abs_path = self._resolve_path(path)
            
            # Check safety
            check = self.safety.check_file_action("read", str(abs_path))
            if not check["allowed"]:
                return {"status": "error", "message": check["reason"]}

            if not abs_path.exists():
                return {"status": "error", "message": "File not found"}
            if not abs_path.is_file():
                return {"status": "error", "message": "Path is not a file"}

            with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            return {
                "status": "ok",
                "content": content,
                "path": str(abs_path).replace("\\", "/")
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write content to file, creating backup and diff if file already exists."""
        try:
            abs_path = self._resolve_path(path)
            
            # Check safety
            check = self.safety.check_file_action("write", str(abs_path))
            if not check["allowed"]:
                return {"status": "error", "message": check["reason"]}
            if check["requires_approval"]:
                return {
                    "status": "pending_confirmation",
                    "action": "write",
                    "path": path,
                    "content": content,
                    "message": check["reason"]
                }

            original_content = ""
            backup_path = None
            if abs_path.exists() and abs_path.is_file():
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    original_content = f.read()
                
                # Perform backup
                try:
                    backup_path = _get_backup_path(str(abs_path))
                    shutil.copy2(abs_path, backup_path)
                except Exception as e:
                    return {"status": "error", "message": f"Failed to create backup: {e}"}

            diff = generate_diff(original_content, content) if original_content else None

            # Ensure parent directories exist
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)

            return {
                "status": "ok",
                "message": "File written successfully",
                "diff": diff,
                "backup": backup_path,
                "path": str(abs_path).replace("\\", "/")
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def create_file(self, path: str, content: str = "") -> Dict[str, Any]:
        """Create a new file with optional content."""
        try:
            abs_path = self._resolve_path(path)
            
            # Check safety
            check = self.safety.check_file_action("create", str(abs_path))
            if not check["allowed"]:
                return {"status": "error", "message": check["reason"]}
            if check["requires_approval"]:
                return {
                    "status": "pending_confirmation",
                    "action": "create",
                    "path": path,
                    "content": content,
                    "message": check["reason"]
                }

            if abs_path.exists():
                return {"status": "error", "message": "File already exists"}

            abs_path.parent.mkdir(parents=True, exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)

            return {
                "status": "ok",
                "message": "File created successfully",
                "path": str(abs_path).replace("\\", "/")
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def delete_file(self, path: str) -> Dict[str, Any]:
        """Delete a file safely."""
        try:
            abs_path = self._resolve_path(path)
            
            # Check safety
            check = self.safety.check_file_action("delete", str(abs_path))
            if not check["allowed"]:
                return {"status": "error", "message": check["reason"]}
            if check["requires_approval"]:
                return {
                    "status": "pending_confirmation",
                    "action": "delete",
                    "path": path,
                    "message": check["reason"]
                }

            if not abs_path.exists():
                return {"status": "error", "message": "File not found"}
            
            # Backup before deleting
            backup_path = _get_backup_path(str(abs_path))
            shutil.copy2(abs_path, backup_path)
            
            abs_path.unlink()

            return {
                "status": "ok",
                "message": "File deleted successfully",
                "backup": backup_path
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def rename_file(self, old_path: str, new_path: str) -> Dict[str, Any]:
        """Rename/move a file."""
        try:
            abs_old = self._resolve_path(old_path)
            abs_new = self._resolve_path(new_path)

            # Check safety on both locations
            check_old = self.safety.check_file_action("delete", str(abs_old))
            check_new = self.safety.check_file_action("create", str(abs_new))
            
            if not check_old["allowed"] or not check_new["allowed"]:
                return {"status": "error", "message": "Blocked by Safety System"}
            
            if check_old["requires_approval"] or check_new["requires_approval"]:
                return {
                    "status": "pending_confirmation",
                    "action": "rename",
                    "old_path": old_path,
                    "new_path": new_path,
                    "message": "Renaming requires user confirmation."
                }

            if not abs_old.exists():
                return {"status": "error", "message": f"Source file {old_path} not found"}
            if abs_new.exists():
                return {"status": "error", "message": f"Destination file {new_path} already exists"}

            # Backup
            backup_path = _get_backup_path(str(abs_old))
            shutil.copy2(abs_old, backup_path)

            abs_new.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(abs_old), str(abs_new))

            return {
                "status": "ok",
                "message": f"File renamed from {old_path} to {new_path}",
                "backup": backup_path
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def search_code(self, pattern: str, path: str = ".") -> Dict[str, Any]:
        """Search for a text pattern in codebase files recursively."""
        try:
            abs_search_path = self._resolve_path(path)
            
            # Check safety (read permission is required)
            check = self.safety.check_file_action("read", str(abs_search_path))
            if not check["allowed"]:
                return {"status": "error", "message": check["reason"]}

            matches = []
            regex = re.compile(pattern, re.IGNORECASE)

            # Recursive traversal
            for root, _, files in os.walk(abs_search_path):
                # Simple ignore lists
                if any(x in root for x in [".git", "node_modules", "venv", ".venv", "__pycache__"]):
                    continue
                for file in files:
                    file_path = Path(root) / file
                    try:
                        # Skip binary
                        with open(file_path, "rb") as f:
                            if b"\x00" in f.read(1024):
                                continue
                        
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            for i, line in enumerate(f, 1):
                                if regex.search(line):
                                    rel_file = file_path.relative_to(self.root_dir)
                                    matches.append({
                                        "file": str(rel_file).replace("\\", "/"),
                                        "line_number": i,
                                        "content": line.strip()
                                    })
                    except Exception:
                        pass
            
            return {
                "status": "ok",
                "matches": matches[:100]  # Limit to first 100 matches
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
