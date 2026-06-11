"""
VOID Tool Registry and Execution Manager
Central registry for all tools with proper execution flow.
"""

from typing import Dict, Any, Callable, Optional
import json
import re

# Import tool functions
try:
    from tools.system_stats import SystemStats
except ImportError:
    SystemStats = None

try:
    from tools.voice_tts import speak as tts_speak, stop_speaking as tts_stop
except ImportError:
    tts_speak, tts_stop = None, None

try:
    from tools.voice_stt import VoiceSTT
except ImportError:
    VoiceSTT = None
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
        
        # CVCS Tools
        self.register("cvcs_click", self._tool_cvcs_click,
                    "Click on a text element or button on the screen")
        self.register("cvcs_type", self._tool_cvcs_type,
                    "Type text at the cursor position")
        self.register("cvcs_read_screen", self._tool_cvcs_read_screen,
                    "Capture and read text or active applications on the screen")
        self.register("cvcs_set_permission", self._tool_cvcs_set_permission,
                    "Set the active desktop control permission level (1 to 4)")
        
        # WhatsApp Tools
        self.register("send_whatsapp", self._tool_send_whatsapp, "Send a WhatsApp message to a contact")
        self.register("read_whatsapp", self._tool_read_whatsapp, "Read unread WhatsApp messages")

        # PC/Operator Tools
        self.register("open_folder", self._tool_open_folder, "Open a system folder")
        self.register("run_command", self._tool_run_command, "Run a secure shell command")
        self.register("file_manager", self._tool_file_manager, "Read or write file content")
        self.register("find_file", self._tool_find_file, "Search recursively for files")
        self.register("move_file_bulk", self._tool_move_file_bulk, "Move files in bulk matching extensions")
        self.register("clean_duplicates", self._tool_clean_duplicates, "Delete duplicate files based on hash")
        self.register("create_folder", self._tool_create_folder, "Create a folder dynamically")
        self.register("arrange_windows", self._tool_arrange_windows, "Arrange visible windows side-by-side or tiled")
        self.register("launch_workspace", self._tool_launch_workspace, "Launch pre-defined dev workspace")

        # Browser, pptx, calendar, email, diagnostics, repair, and assistant tools
        self.register("research_competitors", self._tool_research_competitors, "Scrape and research competitor information")
        self.register("open_tabs", self._tool_open_tabs, "Open multiple web search browser tabs")
        self.register("download_file", self._tool_download_file, "Download a file programmatically")
        self.register("create_presentation", self._tool_create_presentation, "Build a PowerPoint presentation deck")
        self.register("manage_email", self._tool_manage_email, "Draft or summarize emails in sandbox")
        self.register("manage_calendar", self._tool_manage_calendar, "Schedule meetings or view calendar")
        self.register("skipit_assistant", self._tool_skipit_assistant, "Access SkipIt rental dashboard metrics")
        self.register("smart_cart_assistant", self._tool_smart_cart_assistant, "Access Smart Cart pilot metrics")
        self.register("business_intelligence", self._tool_business_intelligence, "Generate business recommendations")
        self.register("agent_network", self._tool_agent_network, "Spawn and query the specialized agent swarm")
        self.register("self_modifier", self._tool_self_modifier, "Modify codebase modules via AI")
        self.register("self_optimizer", self._tool_self_optimizer, "Optimize performance and repair modules")

        # Meeting Intelligence
        self.register("start_meeting", self._tool_start_meeting, "Start continuous meeting capture")
        self.register("stop_meeting", self._tool_stop_meeting, "Stop meeting capture and generate notes")
        self.register("recall_meeting", self._tool_recall_meeting, "Search and recall meeting notes")
        self.register("get_action_items", self._tool_get_action_items, "Show pending action items")

        # Project Intelligence
        self.register("register_project", self._tool_register_project, "Register and scan a project directory")
        self.register("scan_project_changes", self._tool_scan_project_changes, "Detect changes in a tracked project")
        self.register("get_project_status", self._tool_get_project_status, "Get status of a tracked project")
        self.register("query_recent_work", self._tool_query_recent_work, "Show recent work across projects")
        self.register("continue_where_left_off", self._tool_continue_where_left_off, "Continue where you left off in your project")

    
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
        """Search on Google with intelligent conversational query cleaning and real-time context retrieval."""
        if not query:
            return {"status": "error", "message": "Search query required"}
        
        # Clean up query from conversational prefixes and fillers
        cleaned = query.strip()
        
        # Remove conversational prefixes (handling common spelling variants like 'accross')
        prefixes_to_strip = [
            r"^(do\s+one\s+thing\s+)?(search|google|look\s+up)\s+(ac{1,2}ross|on|through)?\s*(the\s+internet|web|google)?\s*(for\s+)?",
            r"^do\s+one\s+thing\s+",
            r"^(can\s+you\s+)?(search|google|find)\s*(for\s+)?",
        ]
        
        for pat in prefixes_to_strip:
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()
            
        # Remove mid-phrase or trailing filler words
        fillers_to_strip = [
            r"\s+(ac{1,2}ross|on)\s+the\s+internet\s*$",
            r"\s+on\s+google\s*$",
            r"\s+on\s+the\s+web\s*$",
        ]
        
        for pat in fillers_to_strip:
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()
            
        # Fallback to original query if cleaning leaves it empty
        if not cleaned:
            cleaned = query.strip()
            
        # 1. Open the browser so the user sees Google Chrome opening (original UX)
        url = f"https://www.google.com/search?q={cleaned.replace(' ', '+')}"
        self._tool_open_url(url=url)
        
        # 2. Concurrently fetch real-time search snippets from DDG HTML (no API keys required!)
        search_results_summary = ""
        try:
            import requests
            import html as html_lib
            
            ddg_url = "https://html.duckduckgo.com/html/"
            ddg_data = {"q": cleaned}
            ddg_headers = {"User-Agent": "Mozilla/5.0"}
            
            r = requests.post(ddg_url, data=ddg_data, headers=ddg_headers, timeout=5)
            if r.status_code == 200:
                blocks = re.split(r'<div class="[^"]*result__body[^"]*"', r.text)
                extracted = []
                for block in blocks[1:]:
                    title_match = re.search(r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
                    snippet_match = re.search(r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', block, re.DOTALL)
                    
                    if title_match:
                        link = title_match.group(1)
                        if "/l/?uddg=" in link:
                            from urllib.parse import unquote
                            link_match = re.search(r'uddg=([^&]+)', link)
                            if link_match:
                                link = unquote(link_match.group(1))
                        
                        title = re.sub(r'<[^>]+>', '', title_match.group(2)).strip()
                        title = html_lib.unescape(title)
                        
                        snippet = ""
                        if snippet_match:
                            snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()
                            snippet = html_lib.unescape(snippet)
                            
                        extracted.append(f"- **{title}**\n  Link: {link}\n  Snippet: {snippet}")
                        if len(extracted) >= 5: # Limit to top 5 results for LLM context window
                            break
                if extracted:
                    search_results_summary = "\n\nReal-time Search Results:\n" + "\n".join(extracted)
        except Exception as e:
            # Fallback gracefully if connection fails or DDG blocks
            pass
            
        return {
            "status": "ok",
            "message": f"Opened Google Chrome search results for: '{cleaned}'.{search_results_summary}"
        }
    
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

    def _tool_cvcs_click(self, query: str = "", **kwargs) -> str:
        """Click on text or button on screen."""
        if not query:
            return "Please specify what you want me to click, Sir."
            
        try:
            from tools.cv_control import take_screenshot, find_text_coordinates
            from server.backend.safety_guard import SafetyGuard
            from tools.desktop_simulator import simulate_click
            
            guard = SafetyGuard()
            # Verify permission matrix
            allowed, reason = guard.validate_action("click", query)
            if not allowed:
                return f"Action blocked: {reason}"
                
            # Capture screen first
            shot = take_screenshot("cv_click_capture.png")
            if shot["status"] != "ok":
                return f"Failed to read screen for clicking: {shot.get('message')}"
                
            matches = find_text_coordinates(query, shot["filepath"])
            if not matches:
                # Fallback check: try Tesseract on active window crop
                from tools.cv_control import get_foreground_window_bounds, crop_image
                bounds = get_foreground_window_bounds()
                if bounds:
                    cropped = crop_image(shot["filepath"], bounds)
                    if cropped:
                        matches = find_text_coordinates(query, cropped)
                        # Offset crop coordinates back to screen pixels
                        for m in matches:
                            m["center"] = (m["center"][0] + bounds["left"], m["center"][1] + bounds["top"])
                            
            if not matches:
                return f"I couldn't locate '{query}' on your screen, Sir. Please make sure it is visible."
                
            target = matches[0]
            cx, cy = target["center"]
            
            # Double check Assisted Mode (Level 2)
            if guard.permission_level == 2.0:
                return f"PENDING_CONFIRMATION: click at ({cx}, {cy}) for target '{query}'"
                
            res = simulate_click(cx, cy)
            if res["status"] == "ok":
                guard.log_action("AGENT", "click", f"Clicked '{query}'", (cx, cy), True)
                return f"Successfully clicked '{query}' at coordinate position ({cx}, {cy}), Sir."
            else:
                guard.log_action("AGENT", "click", f"Click failed '{query}'", (cx, cy), False)
                return f"Failed clicking target: {res.get('message')}"
                
        except Exception as e:
            return f"Click execution encountered an error: {str(e)}"

    def _tool_cvcs_type(self, text: str = "", **kwargs) -> str:
        """Type text at current focused input cursor."""
        if not text:
            return "Please provide the text you wish to type, Sir."
            
        try:
            from server.backend.safety_guard import SafetyGuard
            from tools.desktop_simulator import simulate_type
            
            guard = SafetyGuard()
            allowed, reason = guard.validate_action("type", text)
            if not allowed:
                return f"Action blocked: {reason}"
                
            if guard.permission_level == 2.0:
                return f"PENDING_CONFIRMATION: type '{text}'"
                
            res = simulate_type(text)
            if res["status"] == "ok":
                guard.log_action("AGENT", "type", text, None, True)
                return "Successfully typed the text at focus cursor, Sir."
            else:
                guard.log_action("AGENT", "type", text, None, False)
                return f"Failed typing text: {res.get('message')}"
        except Exception as e:
            return f"Type execution failed: {str(e)}"

    def _tool_cvcs_read_screen(self, **kwargs) -> str:
        """Capture screen and describe foreground windows & parsed texts."""
        try:
            from tools.cv_control import take_screenshot, get_foreground_window_bounds, crop_image, scan_ocr_text
            
            # Identify active window
            bounds = get_foreground_window_bounds()
            shot = take_screenshot("cv_read_capture.png")
            if shot["status"] != "ok":
                return f"Could not capture screen: {shot.get('message')}"
                
            filepath = shot["filepath"]
            cropped_used = False
            
            if bounds:
                cropped = crop_image(filepath, bounds)
                if cropped:
                    filepath = cropped
                    cropped_used = True
                    
            words = scan_ocr_text(filepath)
            
            # Clean up cropped path
            if cropped_used:
                try:
                    os.remove(filepath)
                except Exception:
                    pass
                    
            unique_words = []
            for w in words:
                text = w["text"].strip()
                if text and text not in unique_words:
                    unique_words.append(text)
                    
            words_summary = ", ".join(unique_words[:40])
            if len(unique_words) > 40:
                words_summary += "..."
                
            # Fetch window title
            from server.backend.screen_monitor import get_monitor_instance
            monitor = get_monitor_instance()
            title = monitor.get_foreground_window_title()
            
            summary = f"I took a screen capture, Sir. "
            if title:
                summary += f"The active window is '**{title}**'. "
            else:
                summary += f"No active window title was detected. "
                
            if unique_words:
                summary += f"Here is the text I scanned: {words_summary}"
            else:
                summary += "I was unable to detect any readable text on the active pane."
                
            return summary
        except Exception as e:
            return f"Screen analysis failed: {str(e)}"

    def _tool_cvcs_set_permission(self, level: float = 2.0, **kwargs) -> str:
        """Change current computer control permission levels."""
        try:
            from server.backend.safety_guard import SafetyGuard
            guard = SafetyGuard()
            res = guard.set_permission_level(level)
            return res.get("message", "Permission updated.")
        except Exception as e:
            return f"Setting permission level failed: {str(e)}"

    def _tool_send_whatsapp(self, contact: str = "", message: str = "", **kwargs) -> Dict[str, Any]:
        """Send a WhatsApp message to a contact."""
        from tools.whatsapp_control import send_whatsapp_message
        return send_whatsapp_message(contact, message)

    def _tool_read_whatsapp(self, **kwargs) -> Dict[str, Any]:
        """Read unread WhatsApp messages."""
        from tools.whatsapp_control import read_whatsapp_unread
        return read_whatsapp_unread()

    def _tool_open_folder(self, path: str = "", **kwargs) -> Dict[str, Any]:
        """Open a system folder."""
        from tools.pc_control import open_folder
        return open_folder(path)

    def _tool_run_command(self, command: str = "", **kwargs) -> str:
        """Run a secure shell command."""
        from tools.pc_operator import PCOperator
        op = PCOperator()
        return op.run_command(command)

    def _tool_file_manager(self, path: str = "", content: str = None, **kwargs) -> str:
        """Read or write file content."""
        from tools.pc_operator import PCOperator
        op = PCOperator()
        if content:
            return op.write_file(path, content)
        return op.read_file(path)

    def _tool_find_file(self, query: str = "", **kwargs) -> Dict[str, Any]:
        """Search recursively for files."""
        from tools.file_helper import find_files
        return find_files(query)

    def _tool_move_file_bulk(self, source: str = "", target: str = "", extension: str = None, **kwargs) -> Dict[str, Any]:
        """Move files in bulk matching extensions."""
        from tools.file_helper import move_files
        return move_files(source, target, extension)

    def _tool_clean_duplicates(self, folder: str = "", **kwargs) -> Dict[str, Any]:
        """Delete duplicate files based on hash."""
        from tools.file_helper import delete_duplicates
        return delete_duplicates(folder)

    def _tool_create_folder(self, folder_path: str = "", **kwargs) -> Dict[str, Any]:
        """Create a folder dynamically."""
        from tools.file_helper import create_folder
        return create_folder(folder_path)

    def _tool_arrange_windows(self, layout: str = "", **kwargs) -> Dict[str, Any]:
        """Arrange visible windows side-by-side or tiled."""
        from tools.window_helper import arrange_windows
        return arrange_windows(layout)

    def _tool_launch_workspace(self, workspace_name: str = "", **kwargs) -> Dict[str, Any]:
        """Launch pre-defined dev workspace."""
        from tools.window_helper import launch_workspace
        return launch_workspace(workspace_name)

    def _tool_research_competitors(self, query: str = "", **kwargs) -> Dict[str, Any]:
        """Scrape and research competitor information."""
        from tools.browser_helper import research_competitors
        return research_competitors(query)

    def _tool_open_tabs(self, count: int = 5, topic: str = "", **kwargs) -> Dict[str, Any]:
        """Open multiple web search browser tabs."""
        from tools.browser_helper import open_tabs
        return open_tabs(count, topic)

    def _tool_download_file(self, url: str = "", **kwargs) -> Dict[str, Any]:
        """Download a file programmatically."""
        from tools.browser_helper import download_file
        return download_file(url)

    def _tool_create_presentation(self, topic: str = "", **kwargs) -> Dict[str, Any]:
        """Build a PowerPoint presentation deck."""
        from tools.presentation_builder import build_presentation
        return build_presentation(topic)

    def _tool_manage_email(self, sub_action: str = "summarize", email_id: str = None, instructions: str = None, **kwargs) -> Dict[str, Any]:
        """Draft or summarize emails in sandbox."""
        from tools.email_helper import summarize_inbox, draft_reply
        if sub_action == "summarize" or not email_id:
            return summarize_inbox()
        return draft_reply(email_id, instructions or "Standard professional reply")

    def _tool_manage_calendar(self, sub_action: str = "plan_week", raw_text: str = None, **kwargs) -> Dict[str, Any]:
        """Schedule meetings or view calendar."""
        from tools.calendar_helper import plan_week, schedule_from_text
        if sub_action == "plan_week":
            return plan_week()
        return schedule_from_text(raw_text or "")

    def _tool_skipit_assistant(self, sub_action: str = "weekly_report", days: int = 60, **kwargs) -> Dict[str, Any]:
        """Access SkipIt rental dashboard metrics."""
        from tools import founder_assistant
        if sub_action == "bookings_today":
            return founder_assistant.get_bookings_today()
        elif sub_action == "inactive_listings":
            return founder_assistant.get_inactive_listings()
        elif sub_action == "inactive_users":
            return founder_assistant.get_inactive_users(days)
        return founder_assistant.generate_weekly_report()

    def _tool_smart_cart_assistant(self, sub_action: str = "pilot_performance", **kwargs) -> Dict[str, Any]:
        """Access Smart Cart pilot metrics."""
        from tools import founder_assistant
        if sub_action == "pilot_performance":
            return founder_assistant.get_pilot_performance()
        elif sub_action == "revenue_projections":
            return founder_assistant.generate_revenue_projections()
        return founder_assistant.create_store_pitch_deck()

    def _tool_business_intelligence(self, **kwargs) -> Dict[str, Any]:
        """Generate business recommendations."""
        from tools import founder_assistant
        return founder_assistant.business_intelligence_recommendations()

    def _tool_agent_network(self, sub_action: str = "status", agent_type: str = None, agent_instruction: str = None, **kwargs) -> Dict[str, Any]:
        """Spawn and query the specialized agent swarm."""
        from tools import agent_network
        import asyncio
        loop = asyncio.get_event_loop()
        if sub_action == "spawn_network":
            if loop.is_running():
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, agent_network.spawn_agent_network())
                    return future.result()
            else:
                return loop.run_until_complete(agent_network.spawn_agent_network())
        elif sub_action == "ask_agent":
            if loop.is_running():
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, agent_network.ask_agent(agent_type, agent_instruction))
                    return future.result()
            else:
                return loop.run_until_complete(agent_network.ask_agent(agent_type, agent_instruction))
        return agent_network.get_network_status()

    def _tool_self_modifier(self, sub_action: str = "scan_project", module: str = None, instructions: str = None, **kwargs) -> Dict[str, Any]:
        """Modify codebase modules via AI."""
        from tools import self_modifier
        if sub_action == "rewrite_module":
            return self_modifier.rewrite_module(module, instructions or "Improve and clean up")
        elif sub_action == "improve_system":
            return self_modifier.improve_system()
        elif sub_action == "self_repair":
            return self_modifier.self_repair_workflow()
        return self_modifier.scan_project()

    def _tool_self_optimizer(self, sub_action: str = "check_performance", issue: str = None, **kwargs) -> Dict[str, Any]:
        """Optimize performance and repair modules."""
        from tools import self_optimizer
        if sub_action == "auto_repair":
            return self_optimizer.auto_repair(issue or "")
        elif sub_action == "repair_all":
            return self_optimizer.repair_all()
        return self_optimizer.check_performance()

    def _tool_start_meeting(self, **kwargs) -> Dict[str, Any]:
        """Start continuous meeting capture."""
        from tools import meeting_assistant
        return meeting_assistant.start_meeting()

    def _tool_stop_meeting(self, **kwargs) -> Dict[str, Any]:
        """Stop meeting capture and generate notes."""
        from tools import meeting_assistant
        return meeting_assistant.stop_meeting()

    def _tool_recall_meeting(self, query: str = "", **kwargs) -> Dict[str, Any]:
        """Search and recall meeting notes."""
        from tools import meeting_assistant
        return meeting_assistant.recall_meeting(query)

    def _tool_get_action_items(self, **kwargs) -> Dict[str, Any]:
        """Show pending action items."""
        from tools import meeting_assistant
        return meeting_assistant.get_action_items()

    def _tool_register_project(self, path: str = "", **kwargs) -> Dict[str, Any]:
        """Register and scan a project directory."""
        from tools import project_intelligence
        return project_intelligence.register_project(path)

    def _tool_scan_project_changes(self, project_id: str = "", **kwargs) -> Dict[str, Any]:
        """Detect changes in a tracked project."""
        from tools import project_intelligence
        return project_intelligence.scan_project_changes(project_id)

    def _tool_get_project_status(self, project_name: str = "", **kwargs) -> Dict[str, Any]:
        """Get status of a tracked project."""
        from tools import project_intelligence
        return project_intelligence.get_project_status(project_name)

    def _tool_query_recent_work(self, timeframe: str = "today", **kwargs) -> Dict[str, Any]:
        """Show recent work across projects."""
        from tools import project_intelligence
        return project_intelligence.get_recent_work(timeframe)

    def _tool_continue_where_left_off(self, project_id: str = "", **kwargs) -> Dict[str, Any]:
        """Continue where you left off in your project."""
        from tools import project_intelligence
        return project_intelligence.continue_where_left_off(project_id)

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
        "click", "type", "press shortcut", "hotkey", "double click",
        "read screen", "what is on my screen", "watch my screen",
        "meeting", "task", "action item",
        "track", "project", "register", "monitor", "scan", "status",
        "what changed", "what did i work", "recent work"
    ]
    
    input_lower = user_input.lower()
    return any(keyword in input_lower for keyword in tool_keywords)

