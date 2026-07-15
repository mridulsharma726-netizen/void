import os
import re
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

logger = logging.getLogger("void.routes.code_intelligence")
router = APIRouter()

# In-memory scan cache
_SCAN_CACHE: Dict[str, Dict[str, Any]] = {}

# Directories to ignore (kept lowercase for case-insensitive matches)
IGNORED_DIRS = {
    "node_modules", "venv", ".venv", ".git", "dist", "build",
    "__pycache__", ".cache", ".tox", ".mypy_cache", ".pytest_cache",
    ".next", ".nuxt", "coverage", ".idea", ".vscode", ".qodo",
    ".zencoder", ".zenflow", "env", ".env", "eggs", ".eggs",
    "scratch", "logs", ".gemini", ".agents"
}

# File extensions to scan
ALLOWED_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
    ".json", ".yaml", ".yml", ".md", ".txt", ".java", ".cpp",
    ".c", ".h", ".go", ".rs", ".rb", ".php", ".swift", ".kt",
    ".cs", ".sql", ".sh", ".bash"
}

# Language detection mapping
LANG_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".jsx": "JSX",
    ".tsx": "TSX",
    ".html": "HTML",
    ".css": "CSS",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".md": "Markdown",
    ".txt": "Text",
    ".java": "Java",
    ".cpp": "C/C++",
    ".c": "C/C++",
    ".h": "C/C++",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".cs": "C#",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Shell"
}

class ScanRequest(BaseModel):
    path: str

def get_language(ext: str) -> str:
    return LANG_MAP.get(ext, "Unknown")

def analyze_file(filepath: str, rel_path: str) -> Dict[str, Any]:
    """Analyze a single file for LOC, language, comments, health, dependencies, and dead code."""
    ext = os.path.splitext(filepath)[1].lower()
    language = get_language(ext)
    
    loc = 0
    todos = 0
    fixmes = 0
    hacks = 0
    has_docstring = False
    has_long_lines = False
    comments_count = 0
    
    filename = os.path.basename(filepath).lower()
    
    # 1. Skip analyzing lockfiles, minified files, or hidden files to prevent hangs
    is_lockfile = filename in ["package-lock.json", "yarn.lock", "pnpm-lock.yaml", "composer.lock"]
    is_minified_or_meta = filename.endswith(".min.js") or filename.endswith(".map") or filename.startswith(".")
    
    try:
        file_size = os.path.getsize(filepath)
    except Exception:
        file_size = 0
        
    if is_lockfile or is_minified_or_meta or file_size > 200 * 1024:
        # Fast non-blocking line counting
        try:
            with open(filepath, "rb") as f:
                loc = sum(1 for _ in f)
        except Exception:
            loc = 0
        return {
            "name": os.path.basename(filepath),
            "path": rel_path,
            "language": language,
            "loc": loc,
            "todos": 0,
            "fixmes": 0,
            "hacks": 0,
            "comments": 0,
            "imports": [],
            "dead_code_count": 0,
            "health": 90 if (is_lockfile or is_minified_or_meta) else 80
        }
        
    todo_pat = re.compile(r"\bTODO\b", re.IGNORECASE)
    fixme_pat = re.compile(r"\bFIXME\b", re.IGNORECASE)
    hack_pat = re.compile(r"\bHACK\b", re.IGNORECASE)
    
    content = ""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        logger.warning(f"Could not read {filepath}: {e}")
        
    lines = content.splitlines()
    loc = len(lines)
    
    # Check for docstrings in Python files
    if ext == ".py":
        if '"""' in content or "'''" in content:
            has_docstring = True
    else:
        has_docstring = True # Non-python files don't get penalized for docstrings
        
    # Dependency and Import Extraction
    imports = []
    if ext == ".py":
        import_matches = re.findall(r"^(?:import\s+(\w+)|from\s+(\w+)\s+import)", content, re.MULTILINE)
        for m in import_matches:
            imp = m[0] or m[1]
            if imp and imp not in imports:
                imports.append(imp)
    elif ext in [".js", ".ts", ".jsx", ".tsx"]:
        # matches: import ... from '...' or require('...')
        es6_imports = re.findall(r"import\s+.*?\s+from\s+['\"](.*?)['\"]", content)
        commonjs_imports = re.findall(r"require\(['\"](.*?)['\"]\)", content)
        for imp in es6_imports + commonjs_imports:
            if imp not in imports:
                imports.append(imp)
                
    # Simple dead code detection helper (e.g. defined functions/classes never referenced elsewhere in same file)
    dead_code_count = 0
    if ext == ".py":
        # Find all def func_name(args):
        funcs = re.findall(r"def\s+(\w+)\s*\(", content)
        for f_name in funcs:
            # If function name is only found once in the file, it is unused/dead code (just the definition)
            # Ignore dunder methods like __init__, etc.
            if not f_name.startswith("__"):
                if content.count(f_name) <= 1:
                    dead_code_count += 1
                    
    for line in lines:
        if len(line) > 120:
            has_long_lines = True
        if todo_pat.search(line):
            todos += 1
        if fixme_pat.search(line):
            fixmes += 1
        if hack_pat.search(line):
            hacks += 1
            
        # Simple comment checker
        stripped = line.strip()
        if ext == ".py" and stripped.startswith("#"):
            comments_count += 1
        elif ext in [".js", ".ts", ".jsx", ".tsx", ".java", ".cpp", ".c", ".h", ".cs", ".go", ".php", ".swift", ".kt"] and (stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*")):
            comments_count += 1
            
    # Calculate health score: start at 100
    score = 100
    if loc > 500:
        score -= 10
    if loc > 1000:
        score -= 20
    
    # TODO density penalization
    total_todos = todos + fixmes + hacks
    if loc > 0:
        todo_density = (total_todos / loc) * 100
        if todo_density > 2.0:
            score -= 15
            
    if ext == ".py" and not has_docstring:
        score -= 10
    if has_long_lines:
        score -= 5
        
    score = max(0, min(100, score))
    
    return {
        "name": os.path.basename(filepath),
        "path": rel_path,
        "language": language,
        "loc": loc,
        "todos": todos,
        "fixmes": fixmes,
        "hacks": hacks,
        "comments": comments_count,
        "imports": imports,
        "dead_code_count": dead_code_count,
        "health": score
    }

def build_tree_and_analyze(project_path: str) -> Dict[str, Any]:
    project_path = os.path.abspath(project_path)
    project_name = os.path.basename(project_path)
    
    files_list = []
    file_count = 0
    max_files = 1000 # Hard cap of 1000 files to keep scans lightning fast
    
    # To build the nested folder tree, we will collect file summaries and form the nodes dynamically.
    root_node = {
        "name": project_name,
        "type": "directory",
        "path": "",
        "children": {}
    }
    
    for root, dirs, files in os.walk(project_path):
        # Prune ignored directories in-place (case-insensitive)
        dirs[:] = [d for d in dirs if d.lower() not in IGNORED_DIRS and not d.startswith(".")]
        
        # Stop traversing further if the file count cap has been reached
        if file_count >= max_files:
            dirs[:] = []
            continue
            
        rel_dir = os.path.relpath(root, project_path).replace("\\", "/")
        if rel_dir == ".":
            rel_dir = ""
            
        for file in files:
            if file_count >= max_files:
                break
                
            ext = os.path.splitext(file)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue
                
            full_path = os.path.join(root, file)
            rel_path = os.path.join(rel_dir, file).replace("\\", "/") if rel_dir else file
            
            file_data = analyze_file(full_path, rel_path)
            files_list.append(file_data)
            file_count += 1
            
            # Insert file into the tree
            parts = rel_path.split("/")
            current = root_node
            current_path = ""
            
            for part in parts[:-1]:
                current_path = f"{current_path}/{part}" if current_path else part
                if part not in current["children"]:
                    current["children"][part] = {
                        "name": part,
                        "type": "directory",
                        "path": current_path,
                        "children": {}
                    }
                current = current["children"][part]
                
            # Now add the file itself as a leaf node
            file_name = parts[-1]
            current["children"][file_name] = {
                "name": file_name,
                "type": "file",
                "path": rel_path,
                "language": file_data["language"],
                "health": file_data["health"],
                "loc": file_data["loc"]
            }
            
    # Helper to convert children dict to list recursively
    def clean_tree(node):
        if "children" in node:
            children_dict = node["children"]
            node["children"] = []
            # Sort directories first, then files
            for key in sorted(children_dict.keys()):
                child = children_dict[key]
                clean_tree(child)
                node["children"].append(child)
            node["children"].sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))
            
    clean_tree(root_node)
    
    # Compile statistics
    total_files = len(files_list)
    total_loc = sum(f["loc"] for f in files_list)
    total_todos = sum(f["todos"] for f in files_list)
    total_fixmes = sum(f["fixmes"] for f in files_list)
    total_hacks = sum(f["hacks"] for f in files_list)
    avg_health = sum(f["health"] for f in files_list) / total_files if total_files > 0 else 100
    dead_code_total = sum(f["dead_code_count"] for f in files_list)
    
    lang_counts = {}
    for f in files_list:
        lang_counts[f["language"]] = lang_counts.get(f["language"], 0) + f["loc"]
        
    return {
        "project_name": project_name,
        "path": project_path,
        "tree": root_node,
        "files": files_list,
        "stats": {
            "total_files": total_files,
            "total_loc": total_loc,
            "total_todos": total_todos,
            "total_fixmes": total_fixmes,
            "total_hacks": total_hacks,
            "avg_health": round(avg_health, 1),
            "dead_code_count": dead_code_total,
            "languages": lang_counts
        }
    }

@router.post("/api/code-intel/scan")
async def scan_project_deep(req: ScanRequest):
    if not os.path.exists(req.path) or not os.path.isdir(req.path):
        raise HTTPException(status_code=400, detail="Invalid project directory path")
        
    try:
        scan_id = str(uuid.uuid4())
        import asyncio
        # Execute CPU-heavy filesystem search on a background thread pool to keep FastAPI event loop responsive
        result = await asyncio.to_thread(build_tree_and_analyze, req.path)
        _SCAN_CACHE[scan_id] = result
        return {
            "status": "ok",
            "scan_id": scan_id,
            "project_name": result["project_name"],
            "tree": result["tree"],
            "stats": result["stats"],
            "files": [
                {
                    "path": f["path"],
                    "language": f["language"],
                    "loc": f["loc"],
                    "health": f["health"],
                    "todos": f["todos"],
                    "dead_code": f["dead_code_count"]
                } for f in result["files"]
            ]
        }
    except Exception as e:
        logger.error(f"Failed to scan project code intelligence: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/code-intel/stats/{scan_id}")
async def get_scan_stats(scan_id: str):
    if scan_id not in _SCAN_CACHE:
        raise HTTPException(status_code=404, detail="Scan session not found")
    return {
        "status": "ok",
        "stats": _SCAN_CACHE[scan_id]["stats"]
    }

@router.get("/api/code-intel/health/{scan_id}")
async def get_scan_health(scan_id: str):
    if scan_id not in _SCAN_CACHE:
        raise HTTPException(status_code=404, detail="Scan session not found")
    return {
        "status": "ok",
        "files": [
            {
                "path": f["path"],
                "health": f["health"],
                "loc": f["loc"],
                "language": f["language"],
                "todos": f["todos"]
            } for f in _SCAN_CACHE[scan_id]["files"]
        ]
    }
