"""
VOID Core Codebase Map Module
==============================

Provides module path resolution and protected path checking
for the self-modification system.

Used by: tools/self_modifier.py
"""

import os
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

# Project root
ROOT_DIR = Path(__file__).parent.parent

# Map file location
MAP_FILE = ROOT_DIR / "data" / "codebase_map.json"

# Protected directories — cannot be modified by self-modifier
PROTECTED_DIRS = {
    "venv", ".git", "node_modules", "__pycache__",
    ".vscode", ".qodo", ".zencoder", ".zenflow",
    "desktop",  # Electron app — modify carefully
}

# Protected files — never modify these
PROTECTED_FILES = {
    "requirements.txt", "package.json", "package-lock.json",
    ".gitignore", "setup.py", "setup_done.flag",
}

# Allowed directories for self-modification
ALLOWED_DIRS = {"tools", "core", "workflows", "server", "app"}


def generate_codebase_map() -> Dict[str, str]:
    """
    Scan the project and generate a map of module names to file paths.
    
    Returns:
        Dict mapping module/file names to their relative paths
    """
    module_map = {}
    
    for allowed_dir in ALLOWED_DIRS:
        dir_path = ROOT_DIR / allowed_dir
        if not dir_path.exists():
            continue
        
        for root, dirs, files in os.walk(dir_path):
            # Skip protected subdirectories
            dirs[:] = [d for d in dirs if d not in PROTECTED_DIRS]
            
            for filename in files:
                if not filename.endswith(".py"):
                    continue
                if filename.startswith("__"):
                    continue
                
                full_path = Path(root) / filename
                rel_path = str(full_path.relative_to(ROOT_DIR)).replace("\\", "/")
                
                # Register by various name patterns
                module_name = filename[:-3]  # strip .py
                module_map[module_name] = rel_path
                
                # Also register with directory prefix
                dir_name = Path(root).name
                if dir_name != allowed_dir:
                    module_map[f"{dir_name}/{module_name}"] = rel_path
                module_map[f"{allowed_dir}/{module_name}"] = rel_path
                
                # Full dotted module path
                dotted = rel_path.replace("/", ".").replace("\\", ".")[:-3]
                module_map[dotted] = rel_path
    
    # Save to file
    try:
        MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(MAP_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "map": module_map,
                "generated_at": datetime.now().isoformat(),
                "total_modules": len(module_map),
            }, f, indent=2)
    except Exception:
        pass
    
    return module_map


def load_codebase_map() -> Dict[str, str]:
    """
    Load the codebase map from disk, or generate if missing.
    
    Returns:
        Dict mapping module names to file paths
    """
    try:
        if MAP_FILE.exists():
            with open(MAP_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            module_map = data.get("map", {})
            if module_map:
                return module_map
    except Exception:
        pass
    
    # Generate fresh
    return generate_codebase_map()


def get_module_path(module_name: str) -> Optional[str]:
    """
    Get the file path for a module name.
    
    Args:
        module_name: Module name (e.g., "voice_tts", "tools/voice_tts", "tools.voice_tts")
        
    Returns:
        Relative file path or None
    """
    module_map = load_codebase_map()
    return module_map.get(module_name)


def resolve_module_path(module_name: str) -> Optional[str]:
    """
    Resolve a module name to an absolute file path.
    
    Tries multiple resolution strategies:
    1. Direct map lookup
    2. Common directory prefixes (tools/, core/, server/, workflows/)
    3. Direct file path check
    
    Args:
        module_name: Module name or path
        
    Returns:
        Absolute file path or None
    """
    # Strategy 1: Map lookup
    rel_path = get_module_path(module_name)
    if rel_path:
        abs_path = ROOT_DIR / rel_path
        if abs_path.exists():
            return str(abs_path)
    
    # Strategy 2: Try common directory prefixes
    name = module_name.replace(".", "/")
    candidates = [
        ROOT_DIR / f"{name}.py",
        ROOT_DIR / "tools" / f"{name}.py",
        ROOT_DIR / "core" / f"{name}.py",
        ROOT_DIR / "server" / f"{name}.py",
        ROOT_DIR / "server" / "backend" / f"{name}.py",
        ROOT_DIR / "workflows" / f"{name}.py",
    ]
    
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    
    # Strategy 3: Direct path
    direct = Path(module_name)
    if direct.exists():
        return str(direct)
    
    return None


def is_protected_path(path: str) -> bool:
    """
    Check if a file path is in a protected location.
    
    Args:
        path: File path (relative or absolute)
        
    Returns:
        True if the path is protected and should not be modified
    """
    # Normalize
    path_str = str(path).replace("\\", "/")
    
    # Check protected directories
    for protected_dir in PROTECTED_DIRS:
        if f"/{protected_dir}/" in path_str or path_str.startswith(f"{protected_dir}/"):
            return True
    
    # Check protected files
    filename = os.path.basename(path_str)
    if filename in PROTECTED_FILES:
        return True
    
    # Check if in allowed directory
    rel_path = path_str
    if str(ROOT_DIR) in path_str:
        try:
            rel_path = str(Path(path_str).relative_to(ROOT_DIR))
        except ValueError:
            pass
    
    # If not in any allowed directory, it's protected
    rel_path = rel_path.replace("\\", "/")
    parts = rel_path.split("/")
    if parts and parts[0] not in ALLOWED_DIRS:
        return True
    
    return False


def list_modules(directory: str = None) -> List[Dict[str, str]]:
    """
    List all known modules, optionally filtered by directory.
    
    Args:
        directory: Optional directory filter (e.g., "tools", "core")
        
    Returns:
        List of dicts with 'name' and 'path' keys
    """
    module_map = load_codebase_map()
    results = []
    seen_paths = set()
    
    for name, path in module_map.items():
        if path in seen_paths:
            continue
        if directory and not path.startswith(f"{directory}/"):
            continue
        
        seen_paths.add(path)
        results.append({"name": name, "path": path})
    
    return sorted(results, key=lambda x: x["path"])
