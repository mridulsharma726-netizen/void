"""
VOID Tool Registry and Execution Manager
Central registry for all tools with proper execution flow.
"""

from typing import Dict, Any, Callable, Optional
import json
import re

# Import tool functions
from tools.system_stats import SystemStats
from tools.voice_tts import speak as tts_speak, stop_speaking as tts_stop
from tools.voice_stt import VoiceSTT
import subprocess
import platform
import os
import datetime

# Initialize system stats
system_stats = SystemStats() if SystemStats else None

# Initialize STT if available
stt_engine = None
if VoiceSTT:
    try:
        stt_engine = VoiceSTT()
    except Exception:
        pass


class ToolRegistry:
    """
    Central registry for all VOID tools.
    Provides tool execution with proper error handling.
    """
    
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self._register_all_tools()
    
    def _register_all_tools(self):
        """Register all available tools."""
        
        # System Info
        self.register("system_info", self._tool_system_info, 
                    "Get system information (CPU, RAM, GPU, storage)")
        
        # Time
        self.register("time", self._tool_time,
                    "Get current time and date")
        
        # App Control
        self.register("open_app", self._tool_open_app,
                    "Open an application by name")
        
        # URL
        self.register("open_url", self._tool_open_url,
                    "Open a URL in browser")
        
        # Close App
        self.register("close_app", self._tool_close_app,
                    "Close an application")
        
        # Search
        self.register("search_google", self._tool_search_google,
                    "Search on Google")
        
        # YouTube
        self.register("play_youtube", self._tool_play_youtube,
                    "Play video on YouTube")
        
        # Voice - Listen
        self.register("listen_audio", self._tool_listen_audio,
                    "Listen for speech input")
        
        # Voice - Speak
        self.register("speak", self._tool_speak,
                    "Speak text via TTS")
        
        # Voice - Stop
        self.register("stop_speaking", self._tool_stop_speaking,
                    "Stop TTS speech")
        
        # File Status
        self.register("get_file_status", self._tool_file_status,
                    "Get file status information")
        
        # Folder Status
        self.register("get_folder_status", self._tool_folder_status,
                    "Get folder status information")
        
        # Screenshot
        self.register("screenshot", self._tool_screenshot,
                    "Take a screenshot")
        
        # Shutdown
        self.register("shutdown", self._tool_shutdown,
                    "Shutdown the computer")
        
        # Restart
        self.register("restart", self._tool_restart,
                    "Restart the computer")
        
        # Lock Screen
        self.register("lock_screen", self._tool_lock_screen,
                    "Lock the screen")
        
        # Search Files
        self.register("search_files", self._tool_search_files,
                    "Search for files")
    
    def register(self, name: str, func: Callable, description: str = ""):
        """Register a tool with name, function, and description."""
        self.tools[name] = {
            "func": func,
            "description": description
        }
    
    def get_tool(self, name: str) -> Optional[Callable]:
        """Get a tool function by name."""
        tool = self.tools.get(name)
        return tool["func"] if tool else None
    
    def list_tools(self) -> list:
        """List all available tool names."""
        return list(self.tools.keys())
    
    def execute(self, tool_name: str, args: Dict[str, Any] = None) -> str:
        """
        Execute a tool and return human-readable result.
        Never returns raw JSON to UI.
        """
        args = args or {}
        
        tool_func = self.get_tool(tool_name)
        if not tool_func:
            return f"Tool '{tool_name}' not found."
        
        try:
            result = tool_func(**args)
            
            # Convert dict results to readable strings
            if isinstance(result, dict):
                if result.get("status") == "ok":
                    return result.get("message", "Operation completed.")
                elif result.get("status") == "error":
                    return f"Error: {result.get('message', 'Unknown error')}"
                else:
                    # Format system stats nicely
                    return self._format_system_info(result)
            
            # Return string results as-is
            if isinstance(result, str):
                return result
            
            # Default formatting
            return str(result) if result else "Operation completed."
            
        except Exception as e:
            return f"Tool execution failed: {str(e)}"
    
    def _format_system_info(self, info: Dict) -> str:
        """Format system info for human-readable output."""
        lines = []
        
        if info.get("os"):
            lines.append(f"OS: {info.get('os')}")
        if info.get("processor"):
            lines.append(f"CPU: {info.get('processor')}")
        if info.get("cpu_usage"):
            lines.append(f"CPU Usage: {info.get('cpu_usage')}%")
        if info.get("ram_usage"):
            lines.append(f"RAM Usage: {info.get('ram_usage')}%")
        if info.get("gpu_usage"):
            lines.append(f"GPU Usage: {info.get('gpu_usage')}%")
        if info.get("storage_used_gb") and info.get("storage_total_gb"):
            lines.append(f"Storage: {info.get('storage_used_gb')}GB / {info.get('storage_total_gb')}GB")
        
        return " | ".join(lines) if lines else "System info unavailable."
    
    # ==================== TOOL IMPLEMENTATIONS ====================
    
    def _tool_system_info(self, **kwargs) -> Dict[str, Any]:
        """Get system information."""
        if system_stats:
            return system_stats.get_all_stats()
        return {"status": "error", "message": "System stats not available"}
    
    def _tool_time(self, **kwargs) -> str:
        """Get current time."""
        now = datetime.datetime.now()
        return f"🕒 {now.strftime('%I:%M %p')} • {now.strftime('%A, %d %b %Y')}"
    
    def _tool_open_app(self, app: str = "", **kwargs) -> Dict[str, Any]:
        """Open an application."""
        if not app:
            return {"status": "error", "message": "App name required"}
        
        # Map common app names
        app_map = {
            "chrome": "chrome",
            "edge": "msedge",
            "vscode": "code",
            "notepad": "notepad",
            "calculator": "calc",
            "cmd": "cmd",
            "terminal": "wt",
        }
        
        cmd = app_map.get(app.lower(), app)
        
        try:
            subprocess.Popen(["cmd", "/c", "start", "", cmd], shell=True)
            return {"status": "ok", "message": f"Opened {app}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _tool_open_url(self, url: str = "", **kwargs) -> Dict[str, Any]:
        """Open a URL."""
        if not url:
            return {"status": "error", "message": "URL required"}
        
        # Add https if missing
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        
        try:
            subprocess.Popen(["cmd", "/c", "start", "", url], shell=True)
            return {"status": "ok", "message": f"Opened {url}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _tool_close_app(self, app: str = "", **kwargs) -> Dict[str, Any]:
        """Close an application."""
        if not app:
            return {"status": "error", "message": "App name required"}
        
        exe_map = {
            "chrome": "chrome.exe",
            "edge": "msedge.exe",
            "vscode": "Code.exe",
            "notepad": "notepad.exe",
        }
        
        exe = exe_map.get(app.lower(), f"{app}.exe")
        
        try:
            subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True)
            return {"status": "ok", "message": f"Closed {app}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _tool_search_google(self, query: str = "", **kwargs) -> Dict[str, Any]:
        """Search on Google."""
        if not query:
            return {"status": "error", "message": "Search query required"}
        
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        return self._tool_open_url(url=url)
    
    def _tool_play_youtube(self, query: str = "", **kwargs) -> Dict[str, Any]:
        """Play on YouTube."""
        if not query:
            return {"status": "error", "message": "Search query required"}
        
        url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        return self._tool_open_url(url=url)
    
    def _tool_listen_audio(self, timeout: int = 5, phrase_time_limit: int = 6, **kwargs) -> str:
        """Listen for speech input."""
        if not stt_engine:
            return "Speech recognition not available."
        
        try:
            result = stt_engine.listen_once(timeout=timeout, phrase_time_limit=phrase_time_limit)
            if result.get("status") == "ok":
                return result.get("text", "")
            return result.get("text", "No speech detected.")
        except Exception as e:
            return f"Speech recognition error: {str(e)}"
    
    def _tool_speak(self, text: str = "", **kwargs) -> Dict[str, Any]:
        """Speak text via TTS."""
        if not text:
            return {"status": "error", "message": "No text to speak"}
        
        if tts_speak:
            return tts_speak(text)
        return {"status": "error", "message": "TTS not available"}
    
    def _tool_stop_speaking(self, **kwargs) -> Dict[str, Any]:
        """Stop TTS speech."""
        if tts_stop:
            return tts_stop()
        return {"status": "error", "message": "TTS not available"}
    
    def _tool_file_status(self, path: str = "", **kwargs) -> Dict[str, Any]:
        """Get file status."""
        if not path:
            return {"status": "error", "message": "Path required"}
        
        from tools.file_status import FileStatus
        fs = FileStatus()
        return fs.get_file_status(path)
    
    def _tool_folder_status(self, path: str = "", **kwargs) -> Dict[str, Any]:
        """Get folder status."""
        if not path:
            return {"status": "error", "message": "Path required"}
        
        from tools.file_status import FileStatus
        fs = FileStatus()
        return fs.get_folder_status(path)
    
    def _tool_screenshot(self, **kwargs) -> str:
        """Take a screenshot."""
        try:
            import pyautogui
            from PIL import Image
            
            # Get Pictures folder
            pictures = os.path.join(os.path.expanduser("~"), "Pictures")
            os.makedirs(pictures, exist_ok=True)
            
            # Generate filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"VOID_screenshot_{timestamp}.png"
            filepath = os.path.join(pictures, filename)
            
            # Capture
            img = pyautogui.screenshot()
            img.save(filepath)
            
            return f"Screenshot saved to Pictures/{filename}"
        except Exception as e:
            return f"Screenshot failed: {str(e)}"
    
    def _tool_shutdown(self, **kwargs) -> str:
        """Shutdown the computer."""
        try:
            if platform.system() == "Windows":
                subprocess.run(["shutdown", "/s", "/t", "10"], capture_output=True)
                return "Shutting down in 10 seconds..."
            else:
                return "Shutdown not supported on this OS"
        except Exception as e:
            return f"Shutdown failed: {str(e)}"
    
    def _tool_restart(self, **kwargs) -> str:
        """Restart the computer."""
        try:
            if platform.system() == "Windows":
                subprocess.run(["shutdown", "/r", "/t", "10"], capture_output=True)
                return "Restarting in 10 seconds..."
            else:
                return "Restart not supported on this OS"
        except Exception as e:
            return f"Restart failed: {str(e)}"
    
    def _tool_lock_screen(self, **kwargs) -> str:
        """Lock the screen."""
        try:
            if platform.system() == "Windows":
                subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], capture_output=True)
                return "Screen locked."
            else:
                return "Lock not supported on this OS"
        except Exception as e:
            return f"Lock failed: {str(e)}"
    
    def _tool_search_files(self, filename: str = "", **kwargs) -> str:
        """Search for files."""
        if not filename:
            return "Filename required for search."
        
        # Simple file search in user folder
        user_home = os.path.expanduser("~")
        matches = []
        
        for root, dirs, files in os.walk(user_home):
            # Skip certain directories
            dirs[:] = [d for d in dirs if d not in ['node_modules', '.git', 'AppData', 'venv']]
            
            for f in files:
                if filename.lower() in f.lower():
                    matches.append(os.path.join(root, f))
                    if len(matches) >= 10:  # Limit results
                        break
            
            if len(matches) >= 10:
                break
        
        if matches:
            return "Found: " + ", ".join(matches[:5])
        return f"No files found matching '{filename}'"


# Global registry instance
tool_registry = ToolRegistry()


def execute_tool(tool_name: str, args: Dict[str, Any] = None) -> str:
    """Execute a tool and return human-readable result."""
    return tool_registry.execute(tool_name, args)


def parse_llm_tool_call(response: str) -> Optional[Dict[str, Any]]:
    """
    Parse LLM response to extract tool call.
    Looks for JSON-like tool calls in the response.
    """
    if not response:
        return None
    
    response = response.strip()
    
    # Try to find JSON in the response
    # Look for patterns like {"type":"tool","tool":"xxx","args":{}}
    json_pattern = r'\{[^{}]*"type"\s*:\s*"tool"[^{}]*\}'
    match = re.search(json_pattern, response)
    
    if match:
        try:
            tool_call = json.loads(match.group(0))
            return tool_call
        except json.JSONDecodeError:
            pass
    
    return None


def should_use_tool(user_input: str) -> bool:
    """
    Determine if the user input requires a tool.
    """
    tool_keywords = [
        "open", "close", "start", "launch",
        "search", "google", "youtube",
        "time", "system info", "cpu", "memory", "ram",
        "screenshot", "shutdown", "restart", "lock",
        "remember", "recall", "forget",
        "play music", "volume",
    ]
    
    input_lower = user_input.lower()
    return any(keyword in input_lower for keyword in tool_keywords)

