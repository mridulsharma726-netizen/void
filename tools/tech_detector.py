"""
VOID Static Technology & Framework Detector
=========================================

Performs fast, offline, deterministic static analysis on a directory
to discover programming languages, frameworks, databases, and config files.
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Set

# Directories to ignore during scanning
IGNORED_DIRS = {
    "node_modules", "venv", ".venv", ".git", "dist", "build",
    "__pycache__", ".cache", ".tox", ".mypy_cache", ".pytest_cache",
    ".next", ".nuxt", "coverage", ".idea", ".vscode", ".qodo",
    ".zencoder", ".zenflow", "env", ".env", "scratch", "logs"
}

def detect_technologies(project_path: str) -> Dict[str, Any]:
    """
    Statically analyzes the project directory to detect technologies.
    """
    project_path = os.path.abspath(project_path)
    if not os.path.isdir(project_path):
        return {
            "languages": [],
            "frameworks": [],
            "databases": [],
            "config_files": [],
            "has_git": False
        }

    detected_exts: Set[str] = set()
    config_files: List[str] = []
    
    # Trackers for parsing packages
    dependencies: Set[str] = set()
    requirements_libs: Set[str] = set()
    
    # Walk directory to gather extensions and config files
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        
        rel_root = os.path.relpath(root, project_path)
        if rel_root == ".":
            rel_root = ""
            
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext:
                detected_exts.add(ext)
                
            # Track standard config file names
            rel_file = os.path.join(rel_root, filename).replace("\\", "/") if rel_root else filename
            if filename in [
                "package.json", "requirements.txt", "pyproject.toml", "Cargo.toml",
                "go.mod", "tsconfig.json", "webpack.config.js", ".env", ".env.example",
                "Dockerfile", "docker-compose.yml", ".gitignore", "README.md", "setup.py"
            ]:
                config_files.append(rel_file)
                
                # Parse package.json
                if filename == "package.json":
                    try:
                        with open(os.path.join(root, filename), "r", encoding="utf-8", errors="ignore") as f:
                            pkg_data = json.load(f)
                            for dep_type in ["dependencies", "devDependencies"]:
                                if dep_type in pkg_data:
                                    dependencies.update(pkg_data[dep_type].keys())
                    except Exception:
                        pass
                
                # Parse requirements.txt
                elif filename == "requirements.txt":
                    try:
                        with open(os.path.join(root, filename), "r", encoding="utf-8", errors="ignore") as f:
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith("#"):
                                    # Strip version specifiers
                                    lib_name = re.split(r"==|>=|<=|>|<|~=", line)[0].strip().lower()
                                    if lib_name:
                                        requirements_libs.add(lib_name)
                    except Exception:
                        pass

    # Map extensions to languages
    lang_map = {
        ".py": "Python",
        ".js": "JavaScript",
        ".jsx": "React (JS)",
        ".ts": "TypeScript",
        ".tsx": "React (TS)",
        ".rs": "Rust",
        ".go": "Go",
        ".c": "C",
        ".cpp": "C++",
        ".h": "C/C++ Header",
        ".hpp": "C++ Header",
        ".cs": "C#",
        ".java": "Java",
        ".kt": "Kotlin",
        ".swift": "Swift",
        ".rb": "Ruby",
        ".php": "PHP",
        ".html": "HTML",
        ".css": "CSS",
        ".sh": "Bash",
        ".bat": "Batch",
        ".ps1": "PowerShell"
    }
    
    languages = sorted(list({lang_map[ext] for ext in detected_exts if ext in lang_map}))
    
    # Framework detection
    frameworks_set: Set[str] = set()
    
    # Python frameworks
    py_framework_map = {
        "fastapi": "FastAPI",
        "django": "Django",
        "flask": "Flask",
        "streamlit": "Streamlit",
        "numpy": "NumPy",
        "pandas": "Pandas",
        "scipy": "SciPy",
        "tensorflow": "TensorFlow",
        "torch": "PyTorch",
        "scikit-learn": "Scikit-Learn",
        "uvicorn": "Uvicorn",
        "pydantic": "Pydantic",
        "pytest": "PyTest"
    }
    for lib, name in py_framework_map.items():
        if lib in requirements_libs:
            frameworks_set.add(name)
            
    # Node/JS frameworks
    js_framework_map = {
        "react": "React",
        "electron": "Electron",
        "next": "Next.js",
        "express": "Express",
        "vue": "Vue.js",
        "angular": "Angular",
        "@angular/core": "Angular",
        "tailwindcss": "TailwindCSS",
        "vite": "Vite",
        "svelte": "Svelte",
        "react-native": "React Native"
    }
    for dep, name in js_framework_map.items():
        if dep in dependencies:
            frameworks_set.add(name)

    # Database detection
    databases_set: Set[str] = set()
    
    db_indicators = {
        "sqlite3": "SQLite",
        "sqlite": "SQLite",
        "psycopg2": "PostgreSQL",
        "asyncpg": "PostgreSQL",
        "pg": "PostgreSQL",
        "pymongo": "MongoDB",
        "mongodb": "MongoDB",
        "redis": "Redis",
        "mysql": "MySQL",
        "mysqlconnector": "MySQL",
        "sqlalchemy": "SQLAlchemy (ORM)",
        "prisma": "Prisma (ORM)",
        "mongoose": "Mongoose (ODM)"
    }
    
    # Check dependencies/requirements
    for indicator, db_name in db_indicators.items():
        if indicator in requirements_libs or indicator in dependencies:
            databases_set.add(db_name)
            
    # Check if SQLite .db file is on disk
    for ext in detected_exts:
        if ext in [".db", ".sqlite", ".sqlite3"]:
            databases_set.add("SQLite")

    # Git detection
    has_git = os.path.isdir(os.path.join(project_path, ".git"))

    # Default to static mapping of known folders for files like main.py, setup.py
    # If no frameworks found, check files for keywords
    if not frameworks_set:
        # Check files for FastAPI/Electron imports
        for filename in ["server/main.py", "main.py", "app.py"]:
            full_path = os.path.join(project_path, filename)
            if os.path.exists(full_path):
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if "fastapi" in content.lower():
                            frameworks_set.add("FastAPI")
                        if "flask" in content.lower():
                            frameworks_set.add("Flask")
                        if "django" in content.lower():
                            frameworks_set.add("Django")
                except Exception:
                    pass

    return {
        "languages": languages,
        "frameworks": sorted(list(frameworks_set)),
        "databases": sorted(list(databases_set)),
        "config_files": sorted(config_files),
        "has_git": has_git
    }

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    print(json.dumps(detect_technologies(path), indent=2))
