import os
import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("void.agent_memory")

class CodebaseMemory:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir).resolve()
        self.data_dir = self.root_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.data_dir / "project_memory.json"
        
        # Load or initialize memory state
        self.memory_data = self.load_memory()

    def load_memory(self) -> Dict[str, Any]:
        """Load the memory state from disk."""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.debug(f"Failed to load memory state: {e}")
        
        # Initialize default structure
        return {
            "architecture_summary": "",
            "technology_stack": [],
            "apis": {},
            "db_layouts": {},
            "file_relationships": {},
            "file_states": {}  # file_path -> {hash: str, mtime: float, size: int}
        }

    def save_memory(self):
        """Save the current memory state to disk."""
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.memory_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save memory state: {e}")

    def compute_hash(self, file_path: Path) -> str:
        """Compute the SHA256 hash of a file."""
        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.debug(f"Failed to compute hash for {file_path}: {e}")
            return ""

    def has_file_changed(self, file_path: str) -> bool:
        """
        Check if a file has changed since the last memory update by comparing
        mtime, size, and hash.
        """
        abs_path = self.root_dir / file_path
        if not abs_path.exists():
            return file_path in self.memory_data["file_states"]

        try:
            stat = abs_path.stat()
            mtime = stat.st_mtime
            size = stat.st_size
        except Exception as e:
            logger.debug(f"Failed to stat file {abs_path}: {e}")
            return True

        state = self.memory_data["file_states"].get(file_path)
        if not state:
            return True

        if state.get("mtime") != mtime or state.get("size") != size:
            # Fallback to computing content hash to confirm if content actually changed
            current_hash = self.compute_hash(abs_path)
            return state.get("hash") != current_hash

        return False

    def update_file_state(self, file_path: str) -> bool:
        """
        Update the tracked hash/mtime for a file. Returns True if changed,
        False otherwise.
        """
        abs_path = self.root_dir / file_path
        if not abs_path.exists():
            if file_path in self.memory_data["file_states"]:
                del self.memory_data["file_states"][file_path]
                self.save_memory()
                return True
            return False

        try:
            stat = abs_path.stat()
            mtime = stat.st_mtime
            size = stat.st_size
            current_hash = self.compute_hash(abs_path)
        except Exception as e:
            logger.debug(f"Failed to update file state for {abs_path}: {e}")
            return False

        state = self.memory_data["file_states"].get(file_path)
        changed = False

        if not state or state.get("hash") != current_hash:
            self.memory_data["file_states"][file_path] = {
                "hash": current_hash,
                "mtime": mtime,
                "size": size
            }
            self.save_memory()
            changed = True

        return changed

    # Getters and setters for metadata
    def get_architecture_summary(self) -> str:
        return self.memory_data.get("architecture_summary", "")

    def set_architecture_summary(self, summary: str):
        self.memory_data["architecture_summary"] = summary
        self.save_memory()

    def get_technology_stack(self) -> list:
        return self.memory_data.get("technology_stack", [])

    def set_technology_stack(self, stack: list):
        self.memory_data["technology_stack"] = stack
        self.save_memory()

    def get_apis(self) -> Dict[str, Any]:
        return self.memory_data.get("apis", {})

    def update_api(self, name: str, details: Any):
        self.memory_data["apis"][name] = details
        self.save_memory()

    def get_db_layouts(self) -> Dict[str, Any]:
        return self.memory_data.get("db_layouts", {})

    def update_db_layout(self, table_name: str, layout: Any):
        self.memory_data["db_layouts"][table_name] = layout
        self.save_memory()
