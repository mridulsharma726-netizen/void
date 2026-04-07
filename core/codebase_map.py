"""
VOID Codebase Map Generator
===========================

Generates and maintains a map of the project architecture.

Features:
- generate_codebase_map() - Scan and generate module map
- load_codebase_map() - Load existing map
- save_codebase_map() - Save map to file
- get_module_path() - Get module path from map

Map is saved to: data/codebase_map.json

"""

import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

# ============================================================================
# CONSTANTS
# ============================================================================

# Project root directory
VOID_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Directories to scan
SCAN_DIRECTORIES = [
    "tools",
    "core",
    "modules",
    "agent",
    "workflows",
    "data",
    "ui",
]

# Directories to exclude from scanning (protected)
PROTECTED_DIRECTORIES = [
    "venv",
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "env",
]

# File extensions to include
ALLOWED_EXTENSIONS = [
    ".py",
    ".js",
    ".json",
    ".html",
    ".css",
    ".md",
    ".txt",
]

# Map file path
MAP_FILE = os.path.join(VOID_ROOT, "data", "codebase_map.json")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _should_include_file(filepath: str) -> bool:
    """
    Check if file should be included in the map.
    
    Args:
        filepath: Path to file
        
    Returns:
        True if should include, False otherwise
    """
    # Check extension
    _, ext = os.path.splitext(filepath)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        return False
    
    # Check if in protected directory
    filepath_lower = filepath.lower()
    for protected in PROTECTED_DIRECTORIES:
        if protected in filepath_lower:
            return False
    
    return True


def _get_module_name(filepath: str, root: str) -> str:
    """
    Get module name from file path.
    
    Args:
        filepath: Full file path
        root: Root directory
        
    Returns:
        Module name (without extension)
    """
    # Get relative path
    rel_path = os.path.relpath(filepath, root)
    
    # Remove extension
    name_without_ext = os.path.splitext(rel_path)[0]
    
    # Convert path separator to dots for Python modules
    # e.g., "tools/voice_tts" -> "voice_tts"
    # But "core/agent" -> "agent" (since agent is a directory)
    
    # Get just the filename without path
    filename = os.path.basename(name_without_ext)
    
    return filename


# ============================================================================
# MAIN FUNCTIONS
# ============================================================================

def generate_codebase_map(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Scan the project and generate a codebase map.
    
    Args:
        force_refresh: Force regeneration even if map exists
        
    Returns:
        Dictionary with map data and statistics
    """
    # Check if we already have a map and don't need to refresh
    if not force_refresh and os.path.exists(MAP_FILE):
        try:
            with open(MAP_FILE, 'r', encoding='utf-8') as f:
                existing_map = json.load(f)
            if existing_map and len(existing_map) > 0:
                return {
                    "status": "ok",
                    "message": "Using existing codebase map",
                    "map": existing_map,
                    "total_modules": len(existing_map)
                }
        except:
            pass
    
    # Generate new map
    module_map: Dict[str, str] = {}
    scan_results: List[Dict[str, Any]] = []
    
    for directory in SCAN_DIRECTORIES:
        dir_path = os.path.join(VOID_ROOT, directory)
        
        if not os.path.exists(dir_path):
            continue
        
        # Walk through directory
        for root, dirs, files in os.walk(dir_path):
            # Filter out protected directories
            dirs[:] = [d for d in dirs if d not in PROTECTED_DIRECTORIES]
            
            for filename in files:
                if not _should_include_file(filename):
                    continue
                
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, VOID_ROOT)
                
                # Get module name
                module_name = _get_module_name(filepath, VOID_ROOT)
                
                # Add to map (only if not already present)
                if module_name not in module_map:
                    module_map[module_name] = rel_path
                    
                    scan_results.append({
                        "module": module_name,
                        "path": rel_path,
                        "directory": directory
                    })
    
    # Ensure data directory exists
    os.makedirs(os.path.dirname(MAP_FILE), exist_ok=True)
    
    # Save map to file
    try:
        with open(MAP_FILE, 'w', encoding='utf-8') as f:
            json.dump(module_map, f, indent=2, ensure_ascii=False)
        save_status = "ok"
    except Exception as e:
        save_status = str(e)
    
    return {
        "status": "ok",
        "message": f"Generated codebase map with {len(module_map)} modules",
        "map": module_map,
        "total_modules": len(module_map),
        "scan_results": scan_results,
        "saved": save_status
    }


def load_codebase_map() -> Dict[str, str]:
    """
    Load existing codebase map from file.
    
    Returns:
        Dictionary mapping module names to file paths
    """
    if not os.path.exists(MAP_FILE):
        return {}
    
    try:
        with open(MAP_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}


def save_codebase_map(module_map: Dict[str, str]) -> bool:
    """
    Save codebase map to file.
    
    Args:
        module_map: Dictionary mapping module names to paths
        
    Returns:
        True if successful
    """
    try:
        os.makedirs(os.path.dirname(MAP_FILE), exist_ok=True)
        with open(MAP_FILE, 'w', encoding='utf-8') as f:
            json.dump(module_map, f, indent=2, ensure_ascii=False)
        return True
    except:
        return False


def get_module_path(module_name: str) -> Optional[str]:
    """
    Get the file path for a module name.
    
    Args:
        module_name: Name of the module (e.g., "voice_tts")
        
    Returns:
        Full file path if found, None otherwise
    """
    # First try loading from map
    module_map = load_codebase_map()
    
    if module_name in module_map:
        path = module_map[module_name]
        full_path = os.path.join(VOID_ROOT, path)
        if os.path.exists(full_path):
            return path
    
    # If not in map, try to resolve directly
    return resolve_module_path(module_name)


def resolve_module_path(module_name: str) -> Optional[str]:
    """
    Resolve a module name to its file path.
    
    Searches in these directories:
    - tools/
    - core/
    - modules/
    - agent/
    - workflows/
    - data/
    
    Args:
        module_name: Name of the module (e.g., "voice_tts")
        
    Returns:
        Relative path if found, None otherwise
    """
    # Clean the module name
    module_name = module_name.strip()
    
    # Remove .py extension if provided
    if module_name.endswith('.py'):
        module_name = module_name[:-3]
    
    # Possible paths to check
    possible_paths = [
        f"tools/{module_name}.py",
        f"core/{module_name}.py",
        f"core/agents/{module_name}.py",
        f"modules/{module_name}.py",
        f"agent/{module_name}.py",
        f"workflows/{module_name}.py",
        f"data/{module_name}.json",
        f"data/{module_name}.py",
    ]
    
    # Also check without directory prefix (in case it's a top-level file)
    possible_paths.extend([
        f"tools/{module_name}.py",
        f"core/{module_name}.py",
    ])
    
    # Check each possible path
    for rel_path in possible_paths:
        full_path = os.path.join(VOID_ROOT, rel_path)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            return rel_path
    
    return None


def is_protected_path(path: str) -> bool:
    """
    Check if a path is in a protected directory.
    
    Args:
        path: File path to check
        
    Returns:
        True if protected
    """
    path_lower = path.lower()
    
    for protected in PROTECTED_DIRECTORIES:
        if protected in path_lower:
            return True
    
    return False


def get_all_modules() -> List[str]:
    """
    Get list of all available module names.
    
    Returns:
        List of module names
    """
    module_map = load_codebase_map()
    return sorted(module_map.keys())


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("VOID Codebase Map Test")
    print("=" * 50)
    
    # Generate map
    result = generate_codebase_map(force_refresh=True)
    print(f"Status: {result['status']}")
    print(f"Modules: {result['total_modules']}")
    
    # Test resolve_module_path
    print("\nTesting resolve_module_path:")
    test_modules = ["voice_tts", "voice_stt", "brain", "memory", "agent_loop"]
    
    for mod in test_modules:
        path = resolve_module_path(mod)
        print(f"  {mod} -> {path}")
    
    # Test get_module_path
    print("\nTesting get_module_path:")
    for mod in test_modules:
        path = get_module_path(mod)
        print(f"  {mod} -> {path}")
    
    # Get all modules
    print(f"\nAll modules: {len(get_all_modules())}")

