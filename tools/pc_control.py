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
            subprocess.Popen(["cmd", "/c", "start", "", cmd], shell=True)
            return {"status": "ok", "message": f"Opening {app_name}"}
        except Exception as e:
            return {"status": "error", "message": f"Failed: {str(e)}"}
    
    # Try to open directly
    try:
        subprocess.Popen(["cmd", "/c", "start", "", app_name], shell=True)
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


def open_folder(folder_name: str) -> dict:
    """
    Open a system folder.
    
    Args:
        folder_name: Name of the folder to open
        
    Returns:
        dict: {"status": "ok"|"error", "message": "..."}
    """
    folder_lower = folder_name.lower().strip()
    
    # Get special folder path
    if folder_lower in FOLDER_MAP:
        folder_path = FOLDER_MAP[folder_lower]
    else:
        # Try user's folder
        folder_path = os.path.expanduser(f"~/{folder_name}")
    
    if os.path.exists(folder_path):
        try:
            subprocess.Popen(["explorer", folder_path])
            return {"status": "ok", "message": f"Opening {folder_name}"}
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

