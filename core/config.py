"""
VOID Core Configuration
=======================
"""

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"
DB_PATH = "data/void_memory.db"

# Shared APP_MAP for command interpreter and PC control
APP_MAP = {
    "chrome": "chrome",
    "google chrome": "chrome", 
    "browser": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "msedge": "msedge",
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "code": "code",
    "notepad": "notepad",
    "note": "notepad",
    "notes": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "cmd": "cmd",
    "command prompt": "cmd",
    "terminal": "wt",
    "powershell": "powershell",
    "explorer": "explorer",
    "file explorer": "explorer",
    "spotify": "spotify",
    "discord": "discord",
    "slack": "slack",
    "teams": "teams",
    "zoom": "zoom",
    "vlc": "vlc",
    "vlc media player": "vlc",
}

KILL_MAP = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "browser": "chrome.exe",
    "msedge": "msedge.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "notepad": "notepad.exe",
    "code": "Code.exe",
    "vscode": "Code.exe",
    "calculator": "Calculator.exe",
    "spotify": "Spotify.exe",
    "discord": "Discord.exe",
}
