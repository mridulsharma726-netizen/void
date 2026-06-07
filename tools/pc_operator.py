import os
import subprocess
import platform
import shutil
import logging
from typing import Dict, Any, List

logger = logging.getLogger("void.pc_operator")

class PCOperator:
    """Advanced PC operations: File system, Browser control, and Shell."""
    
    def __init__(self):
        self.os = platform.system()

    def list_files(self, path: str) -> List[str]:
        try:
            return os.listdir(path)
        except Exception as e:
            return [str(e)]

    def read_file(self, path: str) -> str:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read(5000) # Limit to 5k chars
        except Exception as e:
            return str(e)

    def write_file(self, path: str, content: str) -> str:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote to {path}"
        except Exception as e:
            return str(e)

    def run_command(self, command: str) -> str:
        """Run a shell command safely using terminal_tools."""
        try:
            from tools.terminal_tools import run_command as secure_run
            res = secure_run(command, timeout=15)
            if res.get("status") == "ok":
                return (res.get("output", "") + "\n" + res.get("error", "")).strip()
            else:
                return f"Error: {res.get('error', res.get('message', 'Unknown execution error'))}"
        except Exception as e:
            return str(e)

    def open_browser_tab(self, url: str) -> str:
        try:
            import webbrowser
            webbrowser.open(url)
            return f"Opened {url} in default browser."
        except Exception as e:
            return str(e)

    def get_running_processes(self) -> List[str]:
        try:
            import psutil
            return [p.info['name'] for p in psutil.process_iter(['name'])][:20]
        except:
            return ["Unable to list processes"]
