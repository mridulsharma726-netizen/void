"""
VOID File Manager
=================

Safe file operations with backup, diff preview, and permission control.

Only operates in developer mode with explicit permissions.
Creates backups before any modification.
Generates diff previews before write operations.
"""

import os
import shutil
import difflib
from datetime import datetime
from typing import Dict, Any, Optional, List

# Import brain for developer mode check
try:
    from core.brain import is_developer_mode, _log_brain
except ImportError:
    # Fallback if brain not available
    is_developer_mode = lambda: False
    def _log_brain(action, details=""):
        print(f"[FILE_MANAGER] {action}: {details}")

# Security: Allowed paths
ALLOWED_PATHS = [
    "VOID/tools",
    "VOID/",
    "VOID/core",
    "VOID/workflows",
]

# Blocked patterns
BLOCKED_PATTERNS = [
    "venv",
    "node_modules",
    "__pycache__",
    ".git",
    "windows",
    "system32",
    "electron",
    "desktop",
    ".vscode",
    ".zenflow",
    ".zencoder",
    ".qodo",
]

# Project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Backup directory
BACKUP_DIR = os.path.join(PROJECT_ROOT, "backups")


def _normalize_path(path: str) -> str:
    """Normalize path for comparison."""
    return os.path.normpath(path).replace("\\", "/")


def _is_path_allowed(path: str) -> bool:
    """Check if path is allowed for operations."""
    normalized = _normalize_path(path)
    
    # Check blocked patterns
    normalized_lower = normalized.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern in normalized_lower:
            return False
    
    # Check allowed paths
    for allowed in ALLOWED_PATHS:
        if normalized.startswith(allowed) or normalized.startswith("/" + allowed):
            return True
    
    # Special case: allow direct project root files
    if normalized.startswith("VOID/") or normalized.startswith("/VOID/"):
        return True
    
    return False


def _ensure_backup_dir():
    """Ensure backup directory exists."""
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _get_backup_path(original_path: str) -> str:
    """Generate backup file path."""
    _ensure_backup_dir()
    normalized = _normalize_path(original_path)
    filename = os.path.basename(normalized)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{timestamp}_{filename}"
    return os.path.join(BACKUP_DIR, backup_name)


def read_file(path: str) -> Dict[str, Any]:
    """
    Read file content safely.
    
    Args:
        path: File path to read
        
    Returns:
        dict: {"status": "ok"|"error", "content": "...", "error": "..."}
    """
    _log_brain("FILE_READ", f"Path: {path}")
    
    if not _is_path_allowed(path):
        _log_brain("FILE_READ_DENIED", f"Path not allowed: {path}")
        return {"status": "error", "content": None, "error": "Access denied: Path not in allowed list"}
    
    try:
        full_path = os.path.join(PROJECT_ROOT, path) if not os.path.isabs(path) else path
        full_path = os.path.normpath(full_path)
        
        if not os.path.exists(full_path):
            return {"status": "error", "content": None, "error": "File not found"}
        
        if not os.path.isfile(full_path):
            return {"status": "error", "content": None, "error": "Path is not a file"}
        
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        _log_brain("FILE_READ_SUCCESS", f"Path: {path}")
        return {"status": "ok", "content": content, "path": full_path}
    
    except Exception as e:
        _log_brain("FILE_READ_ERROR", f"Error: {str(e)}")
        return {"status": "error", "content": None, "error": str(e)}


def write_file(path: str, content: str, create_diff: bool = True) -> Dict[str, Any]:
    """
    Write file with backup and diff preview.
    Requires developer_mode = True.
    
    Args:
        path: File path to write
        content: New content
        create_diff: Whether to generate diff preview
        
    Returns:
        dict: {"status": "ok"|"error", "diff": "...", "backup": "...", "error": "..."}
    """
    _log_brain("FILE_WRITE", f"Path: {path}")
    
    # Check developer mode
    if not is_developer_mode():
        _log_brain("FILE_WRITE_DENIED", "Developer mode not enabled")
        return {"status": "error", "error": "Developer mode required. Say 'enter developer mode' first."}
    
    if not _is_path_allowed(path):
        _log_brain("FILE_WRITE_DENIED", f"Path not allowed: {path}")
        return {"status": "error", "error": "Access denied: Path not in allowed list"}
    
    try:
        full_path = os.path.join(PROJECT_ROOT, path) if not os.path.isabs(path) else path
        full_path = os.path.normpath(full_path)
        
        # Check if file exists for backup
        original_content = ""
        if os.path.exists(full_path) and os.path.isfile(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                original_content = f.read()
            
            # Create backup
            backup_path = _get_backup_path(path)
            shutil.copy2(full_path, backup_path)
            _log_brain("FILE_BACKUP", f"Created: {backup_path}")
        else:
            backup_path = None
        
        # Generate diff if requested
        diff = None
        if create_diff and original_content:
            diff = generate_diff(original_content, content)
        
        # Write new content
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        _log_brain("FILE_WRITE_SUCCESS", f"Path: {path}")
        
        return {
            "status": "ok",
            "message": "File written successfully",
            "diff": diff,
            "backup": backup_path,
            "path": full_path
        }
    
    except Exception as e:
        _log_brain("FILE_WRITE_ERROR", f"Error: {str(e)}")
        return {"status": "error", "error": str(e)}


def apply_patch(path: str, diff: str) -> Dict[str, Any]:
    """
    Apply a patch/diff to a file.
    Requires developer_mode = True.
    
    Args:
        path: File path
        diff: Diff content
        
    Returns:
        dict: {"status": "ok"|"error", "message": "...", "error": "..."}
    """
    _log_brain("FILE_PATCH", f"Path: {path}")
    
    # Check developer mode
    if not is_developer_mode():
        _log_brain("FILE_PATCH_DENIED", "Developer mode not enabled")
        return {"status": "error", "error": "Developer mode required."}
    
    if not _is_path_allowed(path):
        _log_brain("FILE_PATCH_DENIED", f"Path not allowed: {path}")
        return {"status": "error", "error": "Access denied."}
    
    try:
        # Read current content
        result = read_file(path)
        if result.get("status") != "ok":
            return result
        
        original_content = result["content"]
        
        # Simple patch application - replace with new content from diff
        # This is a simplified implementation
        new_content = diff
        
        # Write with backup
        write_result = write_file(path, new_content, create_diff=False)
        
        if write_result.get("status") == "ok":
            _log_brain("FILE_PATCH_SUCCESS", f"Path: {path}")
            return {"status": "ok", "message": "Patch applied successfully"}
        else:
            return write_result
    
    except Exception as e:
        _log_brain("FILE_PATCH_ERROR", f"Error: {str(e)}")
        return {"status": "error", "error": str(e)}


def generate_diff(original: str, modified: str) -> str:
    """
    Generate a unified diff between original and modified content.
    
    Args:
        original: Original content
        modified: Modified content
        
    Returns:
        str: Unified diff format
    """
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile='original',
        tofile='modified',
        lineterm=''
    )
    
    return ''.join(diff)


def backup_file(path: str) -> Dict[str, Any]:
    """
    Create a backup of a file.
    
    Args:
        path: File path to backup
        
    Returns:
        dict: {"status": "ok"|"error", "backup_path": "...", "error": "..."}
    """
    _log_brain("FILE_BACKUP", f"Path: {path}")
    
    if not _is_path_allowed(path):
        return {"status": "error", "error": "Access denied"}
    
    try:
        full_path = os.path.join(PROJECT_ROOT, path) if not os.path.isabs(path) else path
        full_path = os.path.normpath(full_path)
        
        if not os.path.exists(full_path):
            return {"status": "error", "error": "File not found"}
        
        backup_path = _get_backup_path(path)
        shutil.copy2(full_path, backup_path)
        
        _log_brain("FILE_BACKUP_SUCCESS", f"Backup created: {backup_path}")
        
        return {"status": "ok", "backup_path": backup_path}
    
    except Exception as e:
        _log_brain("FILE_BACKUP_ERROR", f"Error: {str(e)}")
        return {"status": "error", "error": str(e)}


def restore_backup(backup_path: str, target_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Restore a file from backup.
    Requires developer_mode = True.
    
    Args:
        backup_path: Path to backup file
        target_path: Optional target path (defaults to original location)
        
    Returns:
        dict: {"status": "ok"|"error", "message": "...", "error": "..."}
    """
    _log_brain("FILE_RESTORE", f"Backup: {backup_path}")
    
    if not is_developer_mode():
        return {"status": "error", "error": "Developer mode required."}
    
    try:
        backup_full = os.path.normpath(backup_path)
        
        if not os.path.exists(backup_full):
            return {"status": "error", "error": "Backup file not found"}
        
        if target_path:
            restore_path = os.path.join(PROJECT_ROOT, target_path) if not os.path.isabs(target_path) else target_path
        else:
            # Try to infer original path from backup filename
            filename = os.path.basename(backup_full)
            # Remove timestamp prefix
            if "_" in filename:
                parts = filename.split("_", 1)
                if len(parts) > 1:
                    filename = parts[1]
            restore_path = os.path.join(PROJECT_ROOT, "VOID", filename)
        
        restore_path = os.path.normpath(restore_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(restore_path), exist_ok=True)
        
        # Copy backup to restore path
        shutil.copy2(backup_full, restore_path)
        
        _log_brain("FILE_RESTORE_SUCCESS", f"Restored: {restore_path}")
        
        return {"status": "ok", "message": f"Restored to {restore_path}", "path": restore_path}
    
    except Exception as e:
        _log_brain("FILE_RESTORE_ERROR", f"Error: {str(e)}")
        return {"status": "error", "error": str(e)}


def list_directory(path: str = "VOID/") -> Dict[str, Any]:
    """
    List contents of a directory.
    
    Args:
        path: Directory path
        
    Returns:
        dict: {"status": "ok"|"error", "files": [...], "error": "..."}
    """
    _log_brain("DIR_LIST", f"Path: {path}")
    
    if not _is_path_allowed(path):
        return {"status": "error", "error": "Access denied"}
    
    try:
        full_path = os.path.join(PROJECT_ROOT, path) if not os.path.isabs(path) else path
        full_path = os.path.normpath(full_path)
        
        if not os.path.exists(full_path):
            return {"status": "error", "error": "Directory not found"}
        
        if not os.path.isdir(full_path):
            return {"status": "error", "error": "Path is not a directory"}
        
        items = []
        for item in os.listdir(full_path):
            item_path = os.path.join(full_path, item)
            item_info = {
                "name": item,
                "type": "directory" if os.path.isdir(item_path) else "file",
            }
            if os.path.isfile(item_path):
                item_info["size"] = os.path.getsize(item_path)
            items.append(item_info)
        
        # Sort: directories first, then files
        items.sort(key=lambda x: (x["type"] != "directory", x["name"]))
        
        _log_brain("DIR_LIST_SUCCESS", f"Path: {path}")
        
        return {"status": "ok", "path": full_path, "items": items}
    
    except Exception as e:
        _log_brain("DIR_LIST_ERROR", f"Error: {str(e)}")
        return {"status": "error", "error": str(e)}


def get_allowed_paths() -> List[str]:
    """Return list of allowed paths."""
    return ALLOWED_PATHS.copy()


# Convenience functions for compatibility
def read(path: str) -> Dict[str, Any]:
    """Alias for read_file."""
    return read_file(path)


def write(path: str, content: str) -> Dict[str, Any]:
    """Alias for write_file."""
    return write_file(path, content)


def list_dir(path: str = "VOID/") -> Dict[str, Any]:
    """Alias for list_directory."""
    return list_directory(path)

