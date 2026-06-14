import os
import subprocess
from pathlib import Path
from typing import Dict, Any, List

EXCLUDE_DIRS = {
    "node_modules", ".git", "build", "dist", "venv", ".venv", 
    "__pycache__", ".qodo", ".vscode", ".zencoder", ".zenflow", "backups"
}

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".tiff", ".webp",
    ".mp3", ".wav", ".flac", ".ogg", ".mp4", ".mkv", ".avi", ".mov",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".a", ".lib", ".class", ".jar"
}

class ProjectContextCompressor:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir).resolve()

    def get_modified_files(self) -> List[str]:
        """Gets modified files via git if available, otherwise returns empty list."""
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"], 
                cwd=str(self.root_dir), 
                capture_output=True, 
                text=True, 
                timeout=2.0
            )
            if res.returncode == 0:
                files = []
                for line in res.stdout.splitlines():
                    if len(line) > 3:
                        path_str = line[3:].strip()
                        files.append(path_str.replace("\\", "/"))
                return files
        except Exception:
            pass
        return []

    def get_directory_tree(self) -> str:
        """Returns a string representing a simplified folder structure tree."""
        tree = []
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
            rel_root = Path(root).relative_to(self.root_dir)
            indent = "  " * len(rel_root.parts)
            if str(rel_root) != ".":
                tree.append(f"{indent}📁 {rel_root.name}/")
            for f in files:
                if f.startswith("."):
                    continue
                suffix = Path(f).suffix.lower()
                if suffix in BINARY_EXTENSIONS:
                    continue
                tree.append(f"{indent}  📄 {f}")
        return "\n".join(tree[:150])  # Cap at 150 items to prevent explosion

    def build_compressed_context(self) -> str:
        """Assembles a highly compressed project context for large models."""
        modified_files = self.get_modified_files()
        tree_str = self.get_directory_tree()
        
        context = []
        context.append("[PROJECT OVERVIEW]")
        context.append(f"Root: {self.root_dir.name}")
        context.append(f"Structure Tree:\n{tree_str}\n")
        
        # Read and preview key files: entry points, requirements, configs, and modified files
        priority_files = []
        
        # Standard priority entrypoints
        standard_entries = ["server/main.py", "package.json", "requirements.txt", "app/ui/app.js"]
        for relative_path in standard_entries:
            path = self.root_dir / relative_path
            if path.exists() and path.is_file():
                priority_files.append(relative_path)
                
        # Add git modified files
        for mod_f in modified_files:
            if mod_f not in priority_files:
                path = self.root_dir / mod_f
                if path.exists() and path.is_file() and path.suffix.lower() not in BINARY_EXTENSIONS:
                    priority_files.append(mod_f)
                    
        # Cap files previews at 8 files to prevent context explosion
        priority_files = priority_files[:8]
        
        context.append("[PRIORITY FILE PREVIEWS]")
        for rel_f in priority_files:
            path = self.root_dir / rel_f
            try:
                size = path.stat().st_size
                is_mod = " (Modified)" if rel_f in modified_files else ""
                context.append(f"--- File: {rel_f}{is_mod} | Size: {size} bytes ---")
                
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(1500)  # Read first 1,500 characters
                    context.append(content)
                    if size > 1500:
                        context.append("... [Content Truncated to fit Context Bounds] ...")
                context.append("")
            except Exception as e:
                context.append(f"Could not read {rel_f}: {e}")
                
        # List other metadata for all files
        context.append("[METADATA OF REMAINING FILES]")
        count = 0
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
            for file in files:
                if file.startswith("."):
                    continue
                file_path = Path(root) / file
                rel_path = file_path.relative_to(self.root_dir)
                rel_path_str = str(rel_path).replace("\\", "/")
                
                if rel_path_str in priority_files:
                    continue
                if file_path.suffix.lower() in BINARY_EXTENSIONS:
                    continue
                    
                try:
                    size = file_path.stat().st_size
                    context.append(f"- {rel_path_str} ({size} bytes)")
                    count += 1
                except Exception:
                    pass
                if count > 80:  # Cap list
                    context.append("- ... [Additional files list truncated]")
                    break
            if count > 80:
                break
                
        return "\n".join(context)
