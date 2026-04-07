"""
VOID Code Tools Module
====================

File operations and system control for self-modification.

Features:
- read_file(path) - Read file contents
- write_file(path, content) - Write content to file  
- list_project_files(root) - List files in directory
- restart_void() - Restart the backend

Security:
- Restricted to allowed directories: tools/, core/, modules/, ui/
- Backup before write operations
- Protected critical files that cannot be modified
- Syntax validation for Python files before saving
"""

import os
import sys
import json
import shutil
import subprocess
import ast
from typing import Dict, Any, List, Optional
from datetime import datetime

# ============================================================================
# CONSTANTS
# ============================================================================

# Base directory for the project
VOID_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Allowed directories for file operations (security restriction)
ALLOWED_DIRECTORIES = [
    "tools",
    "core", 
    "modules",
    "ui",
    "workflows",
    "agent",
    "data",
]

# File extensions that can be edited
ALLOWED_EXTENSIONS = [
    ".py",    # Python files
    ".js",    # JavaScript files
    ".json",  # JSON files
    ".html",  # HTML files
    ".css",   # CSS files
    ".md",    # Markdown files
    ".txt",   # Text files
]

# CRITICAL FILES THAT CANNOT BE MODIFIED
# These files are essential for backend startup
PROTECTED_FILES = [
    "main.py",
    "server.py",
    "desktop/main.js",
    "package.json",
    "requirements.txt",
    "venv",
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "env",
]

# Backup directory
BACKUP_DIR = os.path.join(VOID_ROOT, "data", "backups")


# ============================================================================
# PERMISSION CHECKS
# ============================================================================

def is_protected(path: str) -> bool:
    """
    Check if a file path is protected (critical system file).
    
    Args:
        path: File path to check (relative or absolute)
        
    Returns:
        True if path is protected, False otherwise
    """
    # Normalize path - convert to forward slashes for consistent comparison
    path = os.path.normpath(path).replace("\\", "/").lower()
    
    # Check each protected pattern
    for protected in PROTECTED_FILES:
        protected_normalized = protected.replace("\\", "/").lower()
        if protected_normalized in path:
            return True
    
    return False


def is_path_allowed(path: str) -> bool:
    """
    Check if a file path is allowed for operations.
    
    Args:
        path: File path to check
        
    Returns:
        True if path is allowed, False otherwise
    """
    # Normalize path
    path = os.path.abspath(path)
    
    # Get relative path from VOID root
    try:
        rel_path = os.path.relpath(path, VOID_ROOT)
    except ValueError:
        return False
    
    # Check if path starts with allowed directory
    for allowed_dir in ALLOWED_DIRECTORIES:
        if rel_path.startswith(allowed_dir + os.sep) or rel_path == allowed_dir:
            return True
    
    return False


def is_extension_allowed(path: str) -> bool:
    """
    Check if file extension is allowed for editing.
    
    Args:
        path: File path to check
        
    Returns:
        True if extension is allowed, False otherwise
    """
    _, ext = os.path.splitext(path)
    return ext.lower() in ALLOWED_EXTENSIONS


def get_safe_path(path: str) -> Optional[str]:
    """
    Get a safe absolute path if allowed, None otherwise.
    
    Args:
        path: Relative or absolute file path
        
    Returns:
        Safe absolute path or None if not allowed
    """
    # Convert to absolute path
    if not os.path.isabs(path):
        abs_path = os.path.join(VOID_ROOT, path)
    else:
        abs_path = path
    
    # Normalize
    abs_path = os.path.abspath(abs_path)
    
    # Check permissions
    if not is_path_allowed(abs_path):
        return None
    
    return abs_path


# ============================================================================
# FILE OPERATIONS
# ============================================================================

def read_file(path: str) -> Dict[str, Any]:
    """
    Read file contents.
    
    Args:
        path: File path (relative to VOID_ROOT or absolute)
        
    Returns:
        Dictionary with status and content
    """
    try:
        # Get safe path
        safe_path = get_safe_path(path)
        if safe_path is None:
            return {
                "status": "error",
                "message": f"Access denied. Cannot read files outside allowed directories: {ALLOWED_DIRECTORIES}"
            }
        
        # Check if file exists
        if not os.path.exists(safe_path):
            return {
                "status": "error",
                "message": f"File not found: {path}"
            }
        
        # Check if it's a file (not directory)
        if not os.path.isfile(safe_path):
            return {
                "status": "error",
                "message": f"Path is a directory, not a file: {path}"
            }
        
        # Read file content
        with open(safe_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Get file info
        file_info = {
            "path": safe_path,
            "relative_path": os.path.relpath(safe_path, VOID_ROOT),
            "size": os.path.getsize(safe_path),
            "modified": datetime.fromtimestamp(os.path.getmtime(safe_path)).isoformat(),
            "lines": len(content.splitlines())
        }
        
        return {
            "status": "ok",
            "content": content,
            "file_info": file_info
        }
        
    except PermissionError:
        return {
            "status": "error",
            "message": "Permission denied to read this file."
        }
    except UnicodeDecodeError:
        return {
            "status": "error",
            "message": "Cannot read file - encoding not supported. Try binary mode."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error reading file: {str(e)}"
        }


def write_file(path: str, content: str, create_backup: bool = True) -> Dict[str, Any]:
    """
    Write content to file with optional backup.
    
    Args:
        path: File path (relative to VOID_ROOT or absolute)
        content: Content to write
        create_backup: Whether to create backup before writing
        
    Returns:
        Dictionary with status and details
    """
    try:
        # Get safe path
        safe_path = get_safe_path(path)
        if safe_path is None:
            return {
                "status": "error",
                "message": f"Access denied. Cannot write to files outside allowed directories: {ALLOWED_DIRECTORIES}"
            }
        
        # Check extension
        if not is_extension_allowed(safe_path):
            return {
                "status": "error",
                "message": f"File type not allowed. Allowed types: {ALLOWED_EXTENSIONS}"
            }
        
        # Create backup if file exists
        backup_path = None
        if create_backup and os.path.exists(safe_path):
            backup_path = _create_backup(safe_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        
        # Write content
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return {
            "status": "ok",
            "message": f"File written successfully: {path}",
            "backup": backup_path,
            "bytes_written": len(content.encode('utf-8'))
        }
        
    except PermissionError:
        return {
            "status": "error",
            "message": "Permission denied to write this file."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error writing file: {str(e)}"
        }


def _create_backup(file_path: str) -> Optional[str]:
    """
    Create a backup of a file.
    
    Args:
        file_path: Path to file to backup
        
    Returns:
        Path to backup file or None if failed
    """
    try:
        # Create backup directory
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # Generate backup filename with timestamp
        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{name}_backup_{timestamp}{ext}"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        # Copy file
        shutil.copy2(file_path, backup_path)
        
        return backup_path
        
    except Exception as e:
        print(f"[BACKUP ERROR] Failed to create backup: {e}")
        return None


def list_project_files(root: str = None, recursive: bool = True) -> Dict[str, Any]:
    """
    List files in project directory.
    
    Args:
        root: Root directory (relative to VOID_ROOT, defaults to root)
        recursive: Whether to list recursively
        
    Returns:
        Dictionary with file listing
    """
    try:
        # Determine root path
        if root is None:
            search_root = VOID_ROOT
        else:
            safe_root = get_safe_path(root)
            if safe_root is None:
                return {
                    "status": "error",
                    "message": f"Access denied. Cannot list outside allowed directories."
                }
            search_root = safe_root
        
        if not os.path.exists(search_root):
            return {
                "status": "error",
                "message": f"Directory not found: {root}"
            }
        
        if not os.path.isdir(search_root):
            return {
                "status": "error",
                "message": f"Not a directory: {root}"
            }
        
        # Collect files
        files = []
        
        if recursive:
            for dirpath, dirnames, filenames in os.walk(search_root):
                # Skip certain directories
                dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != '__pycache__']
                
                for filename in filenames:
                    if not filename.startswith('.'):
                        full_path = os.path.join(dirpath, filename)
                        rel_path = os.path.relpath(full_path, VOID_ROOT)
                        
                        # Check if in allowed directory
                        if is_path_allowed(full_path):
                            files.append({
                                "path": rel_path,
                                "size": os.path.getsize(full_path),
                                "modified": datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat()
                            })
        else:
            for item in os.listdir(search_root):
                full_path = os.path.join(search_root, item)
                if os.path.isfile(full_path) and not item.startswith('.'):
                    rel_path = os.path.relpath(full_path, VOID_ROOT)
                    if is_path_allowed(full_path):
                        files.append({
                            "path": rel_path,
                            "size": os.path.getsize(full_path),
                            "modified": datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat()
                        })
        
        return {
            "status": "ok",
            "files": files,
            "count": len(files),
            "root": os.path.relpath(search_root, VOID_ROOT)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error listing files: {str(e)}"
        }


def get_file_diff(path: str, new_content: str) -> Dict[str, Any]:
    """
    Get diff between current file content and new content.
    
    Args:
        path: File path
        new_content: New content to compare
        
    Returns:
        Dictionary with diff information
    """
    try:
        # Get current content
        current = read_file(path)
        
        if current["status"] != "ok":
            return current
        
        old_content = current["content"]
        
        # Simple line-by-line diff
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        
        diff = {
            "added": len(new_lines) - len(old_lines),
            "total_old": len(old_lines),
            "total_new": len(new_lines),
            "has_changes": old_content != new_content
        }
        
        return {
            "status": "ok",
            "diff": diff,
            "can_proceed": True
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error getting diff: {str(e)}"
        }


# ============================================================================
# SYSTEM OPERATIONS
# ============================================================================

def restart_void() -> Dict[str, Any]:
    """
    Restart the VOID backend server.
    
    Returns:
        Dictionary with status and message
    """
    try:
        # Get the main script path
        main_script = os.path.join(VOID_ROOT, "main.py")
        
        if not os.path.exists(main_script):
            return {
                "status": "error",
                "message": "Cannot find main.py to restart."
            }
        
        # Start new process
        subprocess.Popen(
            [sys.executable, main_script],
            cwd=VOID_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
        )
        
        return {
            "status": "ok",
            "message": "VOID backend restart initiated. Please wait a moment..."
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to restart: {str(e)}"
        }


def get_system_status() -> Dict[str, Any]:
    """
    Get current system status.
    
    Returns:
        Dictionary with system status
    """
    return {
        "status": "ok",
        "root_directory": VOID_ROOT,
        "allowed_directories": ALLOWED_DIRECTORIES,
        "allowed_extensions": ALLOWED_EXTENSIONS,
        "backup_directory": BACKUP_DIR,
        "platform": sys.platform
    }


# ============================================================================
# SYNTAX VALIDATION
# ============================================================================

def validate_python(code: str) -> Dict[str, Any]:
    """
    Validate Python code syntax before saving.
    
    Args:
        code: Python code to validate
        
    Returns:
        Dictionary with validation result
    """
    try:
        ast.parse(code)
        return {
            "valid": True,
            "status": "ok"
        }
    except SyntaxError as e:
        return {
            "valid": False,
            "status": "error",
            "error_type": "syntax_error",
            "message": f"Syntax error at line {e.lineno}: {e.msg}",
            "line": e.lineno,
            "offset": e.offset
        }
    except Exception as e:
        return {
            "valid": False,
            "status": "error",
            "error_type": "validation_error",
            "message": str(e)
        }


def validate_javascript(code: str) -> Dict[str, Any]:
    """
    Basic JavaScript syntax validation.
    Note: This is a basic check, not a full parser.
    
    Args:
        code: JavaScript code to validate
        
    Returns:
        Dictionary with validation result
    """
    # Basic checks for common syntax errors
    errors = []
    
    # Check for unmatched braces
    open_braces = code.count('{')
    close_braces = code.count('}')
    if open_braces != close_braces:
        errors.append(f"Unmatched braces: {open_braces} open, {close_braces} close")
    
    # Check for unmatched parentheses
    open_parens = code.count('(')
    close_parens = code.count(')')
    if open_parens != close_parens:
        errors.append(f"Unmatched parentheses: {open_parens} open, {close_parens} close")
    
    # Check for unmatched brackets
    open_brackets = code.count('[')
    close_brackets = code.count(']')
    if open_brackets != close_brackets:
        errors.append(f"Unmatched brackets: {open_brackets} open, {close_brackets} close")
    
    if errors:
        return {
            "valid": False,
            "status": "error",
            "error_type": "syntax_error",
            "message": "; ".join(errors)
        }
    
    return {
        "valid": True,
        "status": "ok"
    }


def validate_code(code: str, file_path: str) -> Dict[str, Any]:
    """
    Validate code based on file extension.
    
    Args:
        code: Code to validate
        file_path: File path to determine language
        
    Returns:
        Dictionary with validation result
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".py":
        return validate_python(code)
    elif ext == ".js":
        return validate_javascript(code)
    else:
        # No validation for other file types
        return {"valid": True, "status": "ok"}


def restore_backup(backup_path: str, original_path: str) -> bool:
    """
    Restore a file from backup.
    
    Args:
        backup_path: Path to backup file
        original_path: Path to restore to
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, original_path)
            return True
        return False
    except Exception as e:
        print(f"[RESTORE ERROR] Failed to restore backup: {e}")
        return False


def safe_write_file(path: str, content: str, create_backup: bool = True) -> Dict[str, Any]:
    """
    Write content to file with syntax validation and backup.
    
    This is the safe version that:
    1. Checks if file is protected
    2. Validates syntax before writing
    3. Creates backup before writing
    4. Restores backup if validation fails
    
    Args:
        path: File path (relative to VOID_ROOT or absolute)
        content: Content to write
        create_backup: Whether to create backup before writing
        
    Returns:
        Dictionary with status and details
    """
    # Step 1: Check if file is protected
    if is_protected(path):
        return {
            "status": "error",
            "error_type": "protected",
            "message": f"Rewrite blocked: critical system file '{path}' cannot be modified."
        }
    
    # Step 2: Validate code syntax before writing
    validation = validate_code(content, path)
    if not validation.get("valid"):
        return {
            "status": "error",
            "error_type": "validation_failed",
            "message": f"Rewrite aborted: generated code contains syntax errors. {validation.get('message', '')}"
        }
    
    # Step 3: Create backup before writing
    backup_path = None
    full_path = path
    if not os.path.isabs(path):
        full_path = os.path.join(VOID_ROOT, path)
    
    if create_backup and os.path.exists(full_path):
        backup_path = _create_backup(full_path)
    
    # Step 4: Write the content
    write_result = write_file(path, content, create_backup=False)
    
    # Step 5: If write failed, restore backup
    if write_result.get("status") != "ok":
        if backup_path and os.path.exists(backup_path):
            restore_backup(backup_path, full_path)
        return write_result
    
    return {
        "status": "ok",
        "message": f"File written successfully: {path}",
        "backup": backup_path,
        "validated": True
    }


# ============================================================================
# SEARCH OPERATIONS
# ============================================================================

def search_in_files(query: str, file_pattern: str = "*.py") -> Dict[str, Any]:
    """
    Search for a string in files.
    
    Args:
        query: Search query
        file_pattern: File pattern to search (e.g., "*.py")
        
    Returns:
        Dictionary with search results
    """
    try:
        import glob
        
        results = []
        
        # Search in allowed directories
        for allowed_dir in ALLOWED_DIRECTORIES:
            dir_path = os.path.join(VOID_ROOT, allowed_dir)
            if os.path.exists(dir_path):
                pattern = os.path.join(dir_path, "**", file_pattern)
                files = glob.glob(pattern, recursive=True)
                
                for filepath in files:
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()
                            lines = content.splitlines()
                            
                        # Search in file
                        matches = []
                        for i, line in enumerate(lines, 1):
                            if query.lower() in line.lower():
                                matches.append({
                                    "line": i,
                                    "content": line.strip()
                                })
                        
                        if matches:
                            results.append({
                                "file": os.path.relpath(filepath, VOID_ROOT),
                                "matches": matches
                            })
                    except:
                        pass
        
        return {
            "status": "ok",
            "query": query,
            "results": results,
            "files_found": len(results)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Search failed: {str(e)}"
        }


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    # Test code tools
    import json
    
    print("VOID Code Tools Test")
    print("=" * 50)
    
    # Test list files
    result = list_project_files("tools")
    print(f"\nList files in tools/: {result.get('count', 0)} files")
    
    # Test read file
    result = read_file("tools/error_interpreter.py")
    print(f"Read error_interpreter.py: {result['status']}")
    
    # Test system status
    result = get_system_status()
    print(f"System status: {result['status']}")

