import os
import re
import json
from pathlib import Path
from typing import List, Dict, Set, Optional, Any

# Regex for imports
PYTHON_IMPORT_RE = re.compile(r'^\s*(?:import\s+(\w+)|from\s+(\.?\w+)\s+import)', re.MULTILINE)
JS_IMPORT_RE = re.compile(r'(?:import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]|require\s*\(\s*[\'"]([^\'"]+)[\'"]\))')

class AgentContextEngine:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir).resolve()
        self.project_map_path = self.root_dir / "data" / "project_map.json"

    def _read_project_map(self) -> Dict[str, Any]:
        """Read the scanned project map if it exists."""
        if self.project_map_path.exists():
            try:
                with open(self.project_map_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"files": []}

    def parse_imports(self, file_path: Path) -> Set[str]:
        """Parse imported module names/paths from a file."""
        imports = set()
        if not file_path.exists() or not file_path.is_file():
            return imports

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Python imports
            if file_path.suffix == ".py":
                for match in PYTHON_IMPORT_RE.finditer(content):
                    # Match group 1 is import x, group 2 is from y import z
                    imp = match.group(1) or match.group(2)
                    if imp:
                        # Normalize relative imports
                        imports.add(imp.split('.')[0])
            
            # JS/TS imports
            elif file_path.suffix in [".js", ".jsx", ".ts", ".tsx"]:
                for match in JS_IMPORT_RE.finditer(content):
                    imp = match.group(1) or match.group(2)
                    if imp:
                        # Extract basename or relative file path
                        if imp.startswith('.'):
                            imports.add(os.path.basename(imp))
                        else:
                            imports.add(imp)

        except Exception:
            pass

        return imports

    def build_import_graph(self) -> Dict[str, Set[str]]:
        """Build a dependency graph of files within the project."""
        graph = {}
        project_map = self._read_project_map()
        
        for f_info in project_map.get("files", []):
            rel_path = f_info["path"]
            abs_path = self.root_dir / rel_path
            graph[rel_path] = self.parse_imports(abs_path)

        return graph

    def get_relevant_files(self, query: str, target_file: Optional[str] = None, max_files: int = 5) -> List[str]:
        """
        Retrieves a list of files relevant to the query and target file.
        Uses import traversal and keyword similarity.
        """
        relevant = []
        project_map = self._read_project_map()
        all_files = [f["path"] for f in project_map.get("files", [])]

        if not all_files:
            # Fallback to manual listing of root files if no project map
            all_files = [str(p.relative_to(self.root_dir)).replace("\\", "/") 
                         for p in self.root_dir.glob("**/*") if p.is_file()]

        # 1. Add target file first
        if target_file and target_file in all_files:
            relevant.append(target_file)

        # 2. Traverse imports of target file
        if target_file:
            abs_target = self.root_dir / target_file
            imports = self.parse_imports(abs_target)
            
            # Find files in project matching the import names
            for imp in imports:
                for f in all_files:
                    f_name = os.path.basename(f)
                    # Check if import matches name of a project file
                    if imp.lower() in f_name.lower() or f_name.lower().startswith(imp.lower()):
                        if f not in relevant:
                            relevant.append(f)

        # 3. Add files matching query keywords
        query_words = [w.lower() for w in re.findall(r'\w+', query) if len(w) > 3]
        keyword_matches = []
        for f in all_files:
            if f in relevant:
                continue
            
            score = 0
            f_lower = f.lower()
            for word in query_words:
                if word in f_lower:
                    score += 5
            
            if score > 0:
                keyword_matches.append((f, score))

        # Sort by match score
        keyword_matches.sort(key=lambda x: x[1], reverse=True)
        for f, _ in keyword_matches:
            if len(relevant) < max_files:
                relevant.append(f)
            else:
                break

        # Fallback: if list is still small, add common entry points/config files
        common_files = ["requirements.txt", "package.json", "setup.py", "server/main.py"]
        for cf in common_files:
            if len(relevant) < max_files and cf in all_files and cf not in relevant:
                relevant.append(cf)

        return relevant[:max_files]
