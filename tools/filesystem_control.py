import logging
import os
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger("void.filesystem_control")

def get_active_workspace() -> Path:
    """
    Retrieves the active workspace root Path from SQLite preferences,
    initializing it to a dedicated directory if not set.
    """
    from backend.memory_sqlite import get_preference, set_preference
    ws_path_str = get_preference("active_workspace")
    
    # We resolve the VOID root directory to determine default workspace path
    root_dir = Path(__file__).parent.parent
    
    if not ws_path_str:
        # Default to a dedicated sibling directory distinct from the install directory
        default_ws = root_dir.parent / "void_workspace"
        default_ws.mkdir(exist_ok=True, parents=True)
        ws_path_str = str(default_ws.resolve())
        set_preference("active_workspace", ws_path_str)
        
    return Path(ws_path_str).resolve()

def set_active_workspace(path: str) -> Dict[str, Any]:
    """
    Updates the active workspace root directory in SQLite preferences.
    """
    from backend.memory_sqlite import set_preference
    if not path or not path.strip():
        return {"status": "error", "message": "Workspace path cannot be empty, Sir."}
        
    p = Path(path).resolve()
    if not p.exists():
        return {"status": "error", "message": "Specified workspace directory does not exist, Sir."}
    if not p.is_dir():
        return {"status": "error", "message": "Specified path is not a directory, Sir."}
        
    ws_path_str = str(p)
    if set_preference("active_workspace", ws_path_str):
        logger.info(f"[WORKSPACE] Active workspace updated to: {ws_path_str}")
        return {"status": "ok", "message": f"Active workspace successfully set to: {ws_path_str}"}
    else:
        return {"status": "error", "message": "Failed to persist workspace configuration, Sir."}

def validate_path(path: str) -> Path:
    """
    Validates that the path is strictly within the active workspace root.
    Resolves relative path segments (..), symlinks, and performs bounds check.
    Raises ValueError if path is invalid or outside the workspace.
    """
    if not path or not path.strip():
        raise ValueError("Path cannot be empty, Sir.")
        
    workspace_root = get_active_workspace()
    
    p = Path(path)
    # If path is relative, make it relative to the workspace root
    if not p.is_absolute():
        p = workspace_root / p
        
    # Resolve to absolute real path, resolving symlinks and eliminating relative '..'
    resolved = p.resolve()
    
    # Boundary validation: ensure resolved path is under workspace_root
    try:
        resolved.relative_to(workspace_root)
    except ValueError:
        raise ValueError("Access Denied: Path is outside the active workspace, Sir.")
        
    return resolved

def list_directory(path: str = ".") -> Dict[str, Any]:
    """
    Lists directory contents securely scoped to the active workspace.
    """
    try:
        resolved = validate_path(path)
        if not resolved.exists():
            return {"status": "error", "message": "Directory not found, Sir."}
        if not resolved.is_dir():
            return {"status": "error", "message": "Path is not a directory, Sir."}
            
        logger.info(f"[FILESYSTEM] Listing directory: {resolved}")
        
        workspace_root = get_active_workspace()
        files = []
        for entry in resolved.iterdir():
            # Skip hidden files/folders (optional, e.g. .git, but let's list them cleanly)
            files.append({
                "name": entry.name,
                "is_dir": entry.is_dir(),
                "size": entry.stat().st_size if entry.is_file() else None
            })
            
        return {
            "status": "ok",
            "path": str(resolved.relative_to(workspace_root)).replace("\\", "/"),
            "files": files
        }
    except Exception as e:
        logger.error(f"[FILESYSTEM] Directory list failed for '{path}': {e}")
        return {"status": "error", "message": str(e)}

def read_file(path: str) -> Dict[str, Any]:
    """
    Reads file content securely scoped to the active workspace.
    Logs path accessed, never the content (privacy-by-default).
    """
    try:
        resolved = validate_path(path)
        if not resolved.exists():
            return {"status": "error", "message": "File not found, Sir."}
        if not resolved.is_file():
            return {"status": "error", "message": "Path is not a file, Sir."}
            
        logger.info(f"[FILESYSTEM] Reading file: {resolved}")
        
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
            
        workspace_root = get_active_workspace()
        return {
            "status": "ok",
            "path": str(resolved.relative_to(workspace_root)).replace("\\", "/"),
            "content": content
        }
    except Exception as e:
        logger.error(f"[FILESYSTEM] File read failed for '{path}': {e}")
        return {"status": "error", "message": str(e)}
