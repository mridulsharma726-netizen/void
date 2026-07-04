"""
VOID PC Control Module
Desktop control tools for opening apps, URLs, and folders.
"""

import subprocess
import os
import webbrowser
import platform


# App mappings for Windows
APP_MAP = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "browser": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "notepad": "notepad",
    "text editor": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "cmd": "cmd",
    "command prompt": "cmd",
    "terminal": "wt",
    "powershell": "powershell",
    "vscode": "code",
    "code": "code",
    "visual studio code": "code",
    "explorer": "explorer",
    "file explorer": "explorer",
    "spotify": "spotify",
    "discord": "discord",
    "steam": "steam",
    "teams": "teams",
    "zoom": "zoom",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
}

# Folder mappings
FOLDER_MAP = {
    "downloads": "Downloads",
    "documents": "Documents",
    "desktop": "Desktop",
    "pictures": "Pictures",
    "music": "Music",
    "videos": "Videos",
    "home": os.path.expanduser("~"),
    "~": os.path.expanduser("~"),
}


def open_app(app_name: str) -> dict:
    """
    Open an application by name.
    
    Args:
        app_name: Name of the application to open
        
    Returns:
        dict: {"status": "ok"|"error", "message": "..."}
    """
    app_lower = app_name.lower().strip()
    
    # Check if app is in our map
    if app_lower in APP_MAP:
        cmd = APP_MAP[app_lower]
        try:
            subprocess.Popen(["cmd", "/c", "start", "", cmd])
            return {"status": "ok", "message": f"Opening {app_name}"}
        except Exception as e:
            return {"status": "error", "message": f"Failed: {str(e)}"}
    
    # Try to open directly
    try:
        subprocess.Popen(["cmd", "/c", "start", "", app_name])
        return {"status": "ok", "message": f"Opening {app_name}"}
    except Exception as e:
        return {"status": "error", "message": f"App not found: {app_name}"}


def open_url(url: str) -> dict:
    """
    Open a URL in the default browser.
    
    Args:
        url: URL to open
        
    Returns:
        dict: {"status": "ok"|"error", "message": "..."}
    """
    # Add https:// if missing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    try:
        webbrowser.open(url)
        return {"status": "ok", "message": f"Opening {url}"}
    except Exception as e:
        return {"status": "error", "message": f"Failed: {str(e)}"}


def _resolve_folder_path(target: str) -> str | None:
    if not target:
        return None
    
    target = target.strip()
    target_lower = target.lower()
    
    # 1. Direct absolute path check
    if os.path.isabs(target) and os.path.exists(target) and os.path.isdir(target):
        return os.path.abspath(target)
        
    # 2. Map standard special folders (high priority)
    home = os.path.expanduser("~")
    folder_map = {
        "downloads": [os.path.join(home, "Downloads")],
        "documents": [os.path.join(home, "Documents"), os.path.join(home, "OneDrive", "Documents")],
        "desktop": [os.path.join(home, "Desktop"), os.path.join(home, "OneDrive", "Desktop")],
        "pictures": [os.path.join(home, "Pictures"), os.path.join(home, "OneDrive", "Pictures")],
        "music": [os.path.join(home, "Music")],
        "videos": [os.path.join(home, "Videos")],
        "home": [home],
        "~": [home],
    }
    
    if target_lower in folder_map:
        for p in folder_map[target_lower]:
            if os.path.exists(p) and os.path.isdir(p):
                return os.path.abspath(p)
                
    # 3. Direct relative path check (relative to current working directory)
    if os.path.exists(target) and os.path.isdir(target):
        return os.path.abspath(target)
        
    # Check if target is a path relative to workspace root
    try:
        workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    except Exception:
        workspace_root = os.getcwd()
        
    rel_workspace = os.path.join(workspace_root, target)
    if os.path.exists(rel_workspace) and os.path.isdir(rel_workspace):
        return os.path.abspath(rel_workspace)
                
    # 3. Scan base paths for case-insensitive matching directory names
    workspace_parent = os.path.dirname(workspace_root)
    base_dirs = [
        workspace_root,
        workspace_parent,
        home,
        os.path.join(home, "OneDrive"),
        os.path.join(home, "Desktop"),
        os.path.join(home, "OneDrive", "Desktop"),
        os.path.join(home, "Documents"),
        os.path.join(home, "OneDrive", "Documents"),
        os.path.join(home, "Downloads"),
        os.getcwd(),
        os.path.dirname(os.getcwd())
    ]
    
    # Clean duplicates and non-existing base paths while maintaining order
    unique_bases = []
    for b in base_dirs:
        b_abs = os.path.abspath(b)
        if os.path.exists(b_abs) and os.path.isdir(b_abs) and b_abs not in unique_bases:
            unique_bases.append(b_abs)
            
    # Try exact match (case-insensitive) of a subdirectory inside each base path
    for base in unique_bases:
        try:
            # Check if direct join exists
            direct_join = os.path.join(base, target)
            if os.path.exists(direct_join) and os.path.isdir(direct_join):
                return os.path.abspath(direct_join)
                
            # List immediate subdirectories and find case-insensitive match
            for item in os.listdir(base):
                item_path = os.path.join(base, item)
                if os.path.isdir(item_path):
                    if item.lower() == target_lower:
                        return os.path.abspath(item_path)
        except Exception:
            continue
            
    return None


def open_folder(folder_name: str) -> dict:
    """
    Open a system folder.
    
    Args:
        folder_name: Name of the folder to open
        
    Returns:
        dict: {"status": "ok"|"error", "message": "..."}
    """
    if not folder_name or not folder_name.strip():
        return {"status": "error", "message": "Folder name is required"}
        
    resolved_path = _resolve_folder_path(folder_name)
    
    if resolved_path:
        try:
            subprocess.Popen(["explorer", os.path.normpath(resolved_path)])
            return {"status": "ok", "message": f"Opening {resolved_path}"}
        except Exception as e:
            return {"status": "error", "message": f"Failed: {str(e)}"}
    else:
        return {"status": "error", "message": f"Folder not found: {folder_name}"}


def search_web(query: str) -> dict:
    """
    Search the web using Google.
    
    Args:
        query: Search query
        
    Returns:
        dict: {"status": "ok"|"error", "message": "..."}
    """
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    return open_url(url)


def play_youtube(query: str) -> dict:
    """
    Search and play YouTube video.
    
    Args:
        query: Search query
        
    Returns:
        dict: {"status": "ok"|"error", "message": "..."}
    """
    url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    return open_url(url)

