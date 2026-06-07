import os
import json
from pathlib import Path
from typing import List, Dict, Any

# Exclude directories
EXCLUDE_DIRS = {
    "node_modules", ".git", "build", "dist", "venv", ".venv", 
    "__pycache__", ".qodo", ".vscode", ".zencoder", ".zenflow", "backups"
}

# Non-text/binary extensions
BINARY_EXTENSIONS = {
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".tiff", ".webp",
    # Audio/Video
    ".mp3", ".wav", ".flac", ".ogg", ".mp4", ".mkv", ".avi", ".mov",
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # Archives
    ".zip", ".tar", ".gz", ".rar", ".7z",
    # Executables/Binaries
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".a", ".lib", ".class", ".jar"
}

class ProjectScanner:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir).resolve()
        self.data_dir = self.root_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.map_file_path = self.data_dir / "project_map.json"

    def is_binary(self, file_path: Path) -> bool:
        """Check if file is binary by extension or null-byte checking."""
        if file_path.suffix.lower() in BINARY_EXTENSIONS:
            return True
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                if b'\x00' in chunk:
                    return True
        except Exception:
            return True
        return False

    def detect_frameworks(self) -> List[str]:
        """Detect frameworks in the project by reading package files."""
        frameworks = []
        
        # Check requirements.txt or setup.py for Python frameworks
        req_file = self.root_dir / "requirements.txt"
        if req_file.exists():
            try:
                with open(req_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().lower()
                    if "fastapi" in content:
                        frameworks.append("FastAPI")
                    if "flask" in content:
                        frameworks.append("Flask")
                    if "django" in content:
                        frameworks.append("Django")
            except Exception:
                pass

        # Check package.json for JS/TS frameworks
        pkg_file = self.root_dir / "package.json"
        if pkg_file.exists():
            try:
                with open(pkg_file, "r", encoding="utf-8", errors="ignore") as f:
                    pkg_data = json.load(f)
                    deps = pkg_data.get("dependencies", {})
                    dev_deps = pkg_data.get("devDependencies", {})
                    all_deps = {**deps, **dev_deps}
                    
                    if "electron" in all_deps or "electron-builder" in all_deps:
                        frameworks.append("Electron")
                    if "react" in all_deps:
                        frameworks.append("React")
                    if "vue" in all_deps:
                        frameworks.append("Vue")
                    if "next" in all_deps:
                        frameworks.append("Next.js")
            except Exception:
                pass

        # Check pubspec.yaml for Dart/Flutter
        pubspec_file = self.root_dir / "pubspec.yaml"
        if pubspec_file.exists():
            try:
                with open(pubspec_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "flutter:" in content:
                        frameworks.append("Flutter")
                    else:
                        frameworks.append("Dart")
            except Exception:
                pass

        return frameworks

    def find_entry_points(self) -> List[str]:
        """Find common entry points in the workspace."""
        entry_points = []
        possible_entries = [
            "main.py", "app.py", "index.js", "app.js", "main.dart",
            "server/main.py", "server.js", "index.ts", "app.ts"
        ]
        for relative_path in possible_entries:
            path = self.root_dir / relative_path
            if path.exists() and path.is_file():
                entry_points.append(relative_path)
        return entry_points

    def scan(self) -> Dict[str, Any]:
        """Scan the project recursively and write the project_map.json."""
        files_list = []
        
        for root, dirs, files in os.walk(self.root_dir):
            # Prune directories in-place
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')]
            
            for file in files:
                if file.startswith('.'):
                    continue
                file_path = Path(root) / file
                rel_path = file_path.relative_to(self.root_dir)
                
                # Check binary file
                if self.is_binary(file_path):
                    continue
                
                try:
                    size = file_path.stat().st_size
                except Exception:
                    size = 0

                files_list.append({
                    "path": str(rel_path).replace("\\", "/"),
                    "size_bytes": size,
                    "suffix": file_path.suffix.lower()
                })

        frameworks = self.detect_frameworks()
        entry_points = self.find_entry_points()
        
        project_map = {
            "root": str(self.root_dir).replace("\\", "/"),
            "frameworks": frameworks,
            "entry_points": entry_points,
            "files": files_list
        }
        
        # Write to project_map.json
        with open(self.map_file_path, "w", encoding="utf-8") as f:
            json.dump(project_map, f, indent=2)
            
        return project_map
