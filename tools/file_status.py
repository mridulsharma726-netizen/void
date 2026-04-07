import os
import datetime
from typing import List, Dict, Any, Optional


class FileStatus:
    """
    File and folder status scanner.
    Provides file metadata scanning for specified project folder scopes.
    Compatible with Python 3.12.
    """
    
    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize FileStatus scanner.
        
        Args:
            base_dir: Base directory to scan from. Defaults to 'VOID' directory.
        """
        if base_dir:
            self.base_dir = os.path.abspath(base_dir)
        else:
            # Default to the 'void' directory (parent of VOID/tools)
            self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "VOID"))
    
    def _get_scope_path(self, scope: str) -> str:
        """
        Get the full path for a given scope.
        
        Args:
            scope: Scope name ('ui', 'backend', 'root', 'logs')
        
        Returns:
            Full path to the scope directory
        """
        if scope == "ui":
            return os.path.join(self.base_dir, "ui")
        elif scope == "backend":
            return os.path.join(self.base_dir)
        elif scope == "root":
            # Go up one more level from VOID to the project root
            return os.path.join(self.base_dir, "..")
        elif scope == "logs":
            return os.path.join(self.base_dir, "..", "logs")
        else:
            return ""
    
    def _scan_directory(self, scan_path: str) -> List[Dict[str, Any]]:
        """
        Scan a directory and return file metadata.
        
        Args:
            scan_path: Path to directory to scan
        
        Returns:
            List of file metadata dictionaries
        """
        files_data: List[Dict[str, Any]] = []
        
        if not os.path.exists(scan_path):
            return files_data
        
        # Get relative path base (parent of VOID)
        base_path = os.path.join(self.base_dir, "..")
        
        for root, _, files in os.walk(scan_path):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                try:
                    stat = os.stat(file_path)
                    size_kb = round(stat.st_size / 1024, 2)
                    modified_ts = datetime.datetime.fromtimestamp(stat.st_mtime)
                    modified_str = modified_ts.strftime("%Y-%m-%d %H:%M")
                    
                    # Make name relative to the base_dir for cleaner output
                    relative_name = os.path.relpath(file_path, base_path).replace("\\", "/")
                    
                    files_data.append({
                        "name": relative_name,
                        "exists": True,
                        "size_kb": size_kb,
                        "modified": modified_str,
                        "status": "OK"
                    })
                except Exception as e:
                    # If there's an error accessing a file, still report it
                    relative_name = os.path.relpath(file_path, base_path).replace("\\", "/")
                    files_data.append({
                        "name": relative_name,
                        "exists": False,
                        "size_kb": 0,
                        "modified": "N/A",
                        "status": f"Error: {str(e)}"
                    })
        
        return files_data
    
    def get_file_status(self, path: str) -> Dict[str, Any]:
        """
        Get status of a specific file.
        
        Args:
            path: Path to the file
        
        Returns:
            Dictionary containing file status information
        """
        base_path = os.path.join(self.base_dir, "..")
        full_path = os.path.abspath(path)
        
        if not os.path.exists(full_path):
            return {
                "ok": False,
                "path": path,
                "exists": False,
                "error": f"Path not found: {path}"
            }
        
        if not os.path.isfile(full_path):
            return {
                "ok": False,
                "path": path,
                "exists": False,
                "error": f"Path is not a file: {path}"
            }
        
        try:
            stat = os.stat(full_path)
            relative_name = os.path.relpath(full_path, base_path).replace("\\", "/")
            
            return {
                "ok": True,
                "path": path,
                "name": relative_name,
                "exists": True,
                "size_kb": round(stat.st_size / 1024, 2),
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "status": "OK"
            }
        except Exception as e:
            return {
                "ok": False,
                "path": path,
                "exists": False,
                "error": str(e)
            }
    
    def get_folder_status(self, path: str) -> Dict[str, Any]:
        """
        Get status of files in a specific folder.
        
        Args:
            path: Path to the folder
        
        Returns:
            Dictionary containing folder status and file list
        """
        full_path = os.path.abspath(path)
        
        if not os.path.exists(full_path):
            return {
                "ok": False,
                "path": path,
                "files": [],
                "error": f"Path not found: {path}"
            }
        
        if not os.path.isdir(full_path):
            return {
                "ok": False,
                "path": path,
                "files": [],
                "error": f"Path is not a directory: {path}"
            }
        
        files_data = self._scan_directory(full_path)
        
        return {
            "ok": True,
            "path": path,
            "files": files_data,
            "file_count": len(files_data)
        }
    
    def get_scope_status(self, scope: str) -> Dict[str, Any]:
        """
        Scans the specified project folder scope and returns file metadata.
        
        Args:
            scope: Scope name ('ui', 'backend', 'root', 'logs')
        
        Returns:
            Dictionary containing scope status and file list
        """
        valid_scopes = ["ui", "backend", "root", "logs"]
        
        if scope not in valid_scopes:
            return {
                "ok": False,
                "scope": scope,
                "files": [],
                "error": f"Invalid scope. Must be {valid_scopes}."
            }
        
        scan_path = self._get_scope_path(scope)
        
        if not scan_path:
            return {
                "ok": False,
                "scope": scope,
                "files": [],
                "error": "Invalid scope configuration"
            }
        
        # Create logs directory if it doesn't exist
        if scope == "logs" and not os.path.exists(scan_path):
            os.makedirs(scan_path, exist_ok=True)
        
        if not os.path.exists(scan_path):
            return {
                "ok": False,
                "scope": scope,
                "files": [],
                "error": f"Path not found: {scan_path}"
            }
        
        files_data = self._scan_directory(scan_path)
        
        return {
            "ok": True,
            "scope": scope,
            "files": files_data,
            "file_count": len(files_data)
        }


# Backward compatibility: keep the old function for any direct imports
def get_file_status(scope: str) -> Dict[str, Any]:
    """
    Legacy function for backward compatibility.
    Prefer using the FileStatus class for better organization.
    """
    file_scanner = FileStatus()
    result = file_scanner.get_scope_status(scope)
    # Convert to old format if needed
    return {
        "ok": result.get("ok", False),
        "scope": scope,
        "files": result.get("files", []),
        "error": result.get("error", "")
    }
