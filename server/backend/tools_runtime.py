import asyncio
import datetime as dt
import logging
import os
import platform
import subprocess
from typing import Any, Dict, Optional

import psutil

from backend.tool_schemas import ToolStatus, ToolOutput  # Schema integration

logger = logging.getLogger("void.tools_runtime")

class ToolRuntime:
    """Enhanced runtime with schema awareness and expanded tools."""

    def __init__(self):
        self.app_map = {
            # Common Windows apps
            "chrome": "chrome",
            "edge": "msedge",
            "firefox": "firefox",
            "vscode": "code",
            "vs code": "code",
            "visual studio code": "code",
            "notepad": "notepad",
            "notepad++": "notepad++",
            "calculator": "calc",
            "calc": "calc",
            "terminal": "wt.exe",  # Windows Terminal
            "cmd": "cmd",
            "powershell": "powershell",
            "explorer": "explorer",
        }

    async def execute(self, name: str, payload: Dict[str, Any] | None = None) -> 'ToolCall':
        """Schema-aware tool execution."""
        data = payload or {}
        started = dt.datetime.now()
        
        try:
            from core.tools.tool_orchestrator import ToolOrchestrator
            ToolOrchestrator().enforce_permission(name)
            
            if name == "time":
                output = self._time()
            elif name == "system_info":
                output = self._system_info()
            elif name == "open_app":
                output = self._open_app(data.get("app"))
            elif name == "close_app":
                output = self._close_app(data.get("app"))
            elif name == "open_url":
                output = self._open_url(data.get("url"))
            elif name == "search_google":
                query = data.get("query", "")
                url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
                output = self._open_url(url)
            elif name == "play_youtube":
                query = data.get("query", "")
                url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
                output = self._open_url(url)
            elif name == "open_folder":
                output = self._open_folder(data.get("path"))
            elif name == "run_command":
                output = self._run_command(data.get("command"))
            elif name == "file_manager":
                output = self._file_manager(data.get("path"), data.get("content"))
            elif name == "repair_self":
                output = await self._repair_self()
            elif name == "diagnostics":
                output = await self._diagnostics()
            elif name == "send_whatsapp":
                output = await self._send_whatsapp(data.get("contact"), data.get("message"))
            elif name == "read_whatsapp":
                output = await self._read_whatsapp()
            elif name == "find_file":
                output = await self._find_file(data.get("query"))
            elif name == "move_file_bulk":
                output = await self._move_file_bulk(data.get("extension"), data.get("source"), data.get("target"))
            elif name == "clean_duplicates":
                output = await self._clean_duplicates(data.get("folder"))
            elif name == "create_folder":
                output = await self._create_folder(data.get("folder_path"))
            elif name == "arrange_windows":
                output = await self._arrange_windows(data.get("layout"))
            elif name == "launch_workspace":
                output = await self._launch_workspace(data.get("workspace_name"))
            elif name == "research_competitors":
                output = await self._research_competitors(data.get("query"))
            elif name == "open_tabs":
                output = await self._open_tabs(data.get("count"), data.get("topic"))
            elif name == "download_file":
                output = await self._download_file(data.get("url"))
            elif name == "create_presentation":
                output = await self._create_presentation(data.get("topic"))
            elif name == "manage_email":
                output = await self._manage_email(data.get("sub_action"), data.get("email_id"), data.get("instructions"))
            elif name == "manage_calendar":
                output = await self._manage_calendar(data.get("sub_action"), data.get("raw_text"))
            elif name == "skipit_assistant":
                output = await self._skipit_assistant(data.get("sub_action"), data.get("days"))
            elif name == "smart_cart_assistant":
                output = await self._smart_cart_assistant(data.get("sub_action"))
            elif name == "business_intelligence":
                output = await self._business_intelligence()
            elif name == "agent_network":
                output = await self._agent_network(data.get("sub_action"), data.get("agent_type"), data.get("agent_instruction"))
            elif name == "self_modifier":
                output = await self._self_modifier(data.get("sub_action"), data.get("module"), data.get("instructions"))
            elif name == "self_optimizer":
                output = await self._self_optimizer(data.get("sub_action"), data.get("issue"))
            elif name == "cvcs_click":
                output = await self._cvcs_click(data.get("query"))
            elif name == "cvcs_type":
                output = await self._cvcs_type(data.get("text"))
            elif name == "cvcs_read_screen":
                output = await self._cvcs_read_screen()
            elif name == "cvcs_set_permission":
                output = await self._cvcs_set_permission(data.get("level"))
            elif name == "agent_scan":
                output = await self._agent_scan()
            elif name == "agent_explain":
                output = await self._agent_explain()
            elif name == "agent_code":
                output = await self._agent_code(data.get("instructions"))
            elif name == "agent_run_tests":
                output = await self._agent_run_tests()
            elif name == "agent_fix_errors":
                output = await self._agent_fix_errors(data.get("logs"))
            elif name == "start_meeting":
                output = await self._start_meeting()
            elif name == "stop_meeting":
                output = await self._stop_meeting()
            elif name == "recall_meeting":
                output = await self._recall_meeting(data.get("query"))
            elif name == "get_action_items":
                output = await self._get_action_items()
            elif name == "register_project":
                output = await self._register_project(data.get("path"))
            elif name == "scan_project_changes":
                output = await self._scan_project_changes(data.get("project_id"))
            elif name == "get_project_status":
                output = await self._get_project_status(data.get("project_name"))
            elif name == "query_recent_work":
                output = await self._query_recent_work(data.get("timeframe"))
            elif name == "continue_where_left_off":
                output = await self._continue_where_left_off(data.get("project_id"))
            elif name == "screenshot":
                output = await self._screenshot()
            elif name == "lock_computer":
                output = await self._lock_computer()
            elif name == "press_key":
                output = await self._press_key(data.get("key"))
            elif name == "mouse_control":
                output = await self._mouse_control(data.get("action"), data.get("x"), data.get("y"), data.get("amount"))
            elif name == "check_file_exists":
                output = await self._check_file_exists(data.get("path"))
            elif name == "list_directory":
                output = await self._list_directory(data.get("path"))
            elif name == "analyze_code":
                output = await self._analyze_code(data.get("path"))
            elif name == "long_term_memory":
                output = await self._long_term_memory(
                    data.get("category"), data.get("action"), data.get("key"), data.get("value")
                )
            elif name == "vision_analyze":
                output = await self._vision_analyze(data.get("image_path"), data.get("action"))
            elif name == "voice_speak":
                output = await self._voice_speak(data.get("text"))
            elif name == "git_summary":
                output = await self._git_summary(data.get("path"))
            elif name == "switch_to_window":
                output = await self._switch_to_window(data.get("title_query"))
            elif name == "read_active_window":
                output = await self._read_active_window()
            elif name == "read_clipboard":
                output = await self._read_clipboard()
            elif name == "write_clipboard":
                output = await self._write_clipboard(data.get("text"))
            elif name == "rename_file":
                output = await self._rename_file(data.get("old_path"), data.get("new_path"))
            elif name == "move_file":
                output = await self._move_file(data.get("source"), data.get("destination"))
            elif name == "delete_file":
                output = await self._delete_file(data.get("path"))
            elif name == "launch_vscode":
                output = await self._launch_vscode(data.get("path"))
            elif name == "launch_browser":
                output = await self._launch_browser(data.get("url"))
            elif name == "launch_terminal":
                output = await self._launch_terminal(data.get("command"))
            elif name == "weather":
                output = await self._weather(data.get("city"))
            elif name == "agent_refactor":
                output = await self._agent_refactor(data.get("file_path"))
            elif name == "change_motd":
                output = await self._change_motd(data.get("motd"))
            else:
                raise ValueError(f"Unknown tool: {name}")
                
                
        except Exception as exc:
            logger.error(f"Tool '{name}' runtime error: {exc}", exc_info=True)
            output = f"Runtime error: {str(exc)}"
        
        elapsed_ms = int((dt.datetime.now() - started).total_seconds() * 1000)
        logger.info(f"Runtime '{name}': {elapsed_ms}ms, success=True")
        
        # Note: Full ToolOutput validation done in ToolManager
        return type('ToolCall', (), {
            'name': name,
            'input': data,
            'output': output,
            'meta': {'runtime_ms': elapsed_ms}
        })()

    # === TOOL IMPLEMENTATIONS (enhanced) ===
    def _time(self) -> str:
        """Get formatted current time."""
        now = dt.datetime.now()
        return now.strftime("%I:%M %p | %A, %B %d, %Y")

    def _system_info(self) -> str:
        """Structured system stats."""
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage(os.path.abspath(os.sep))
        disk_pct = (disk.used / disk.total) * 100
        
        battery = psutil.sensors_battery()
        batt_str = f"{battery.percent}%" if battery else "N/A"
        charging_str = " (Charging)" if battery and battery.power_plugged else ""
        
        import socket
        try:
            socket.create_connection(("1.1.1.1", 53), timeout=1.5)
            network = "Online"
        except OSError:
            network = "Offline"
            
        return (f"OS: {platform.system()} {platform.release()} | "
                f"CPU: {cpu:.0f}% | RAM: {ram:.0f}% | "
                f"Disk: {disk_pct:.0f}% | "
                f"Battery: {batt_str}{charging_str} | "
                f"Network: {network}")

    def _open_app(self, app: Optional[str]) -> str:
        if not app or not app.strip():
            return "Error: app name required"
        target = app.strip().lower()
        cmd = self.app_map.get(target, target)
        
        # Guard: Check if the application executable exists in PATH or on disk
        import shutil
        if target not in self.app_map:
            if not shutil.which(cmd) and not os.path.exists(cmd):
                return f"❌ App '{app}' is not installed or cannot be found, Sir."
                
        try:
            subprocess.Popen(["cmd", "/c", "start", "", cmd], 
                           creationflags=subprocess.CREATE_NO_WINDOW)
            return f"✅ Opened '{app}'"
        except Exception as e:
            return f"❌ Failed to open '{app}': {e}"

    def _close_app(self, app: Optional[str]) -> str:
        if not app or not app.strip():
            return "Error: app name required"
        target = f"{app.strip().lower()}.exe"
        try:
            result = subprocess.run(["taskkill", "/F", "/IM", target], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return f"✅ Closed '{app}'"
            return f"⚠️ '{app}' not running or already closed"
        except Exception as e:
            return f"❌ Close failed: {e}"

    def _open_url(self, url: Optional[str]) -> str:
        if not url or not url.strip():
            return "Error: URL required"
        target = url.strip()
        if not target.startswith(("http://", "https://")):
            target = "https://" + target
        try:
            subprocess.Popen(["cmd", "/c", "start", "", target],
                           creationflags=subprocess.CREATE_NO_WINDOW)
            return f"✅ Opened {target[:50]}..."
        except Exception as e:
            return f"❌ URL open failed: {e}"

    def _resolve_folder_path(self, target: str) -> Optional[str]:
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
            workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
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

    def _open_folder(self, path: Optional[str]) -> str:
        if not path or not path.strip():
            return "Error: valid folder or file path required"
            
        target = path.strip()
        if os.path.exists(target):
            resolved_path = os.path.abspath(target)
        else:
            resolved_path = self._resolve_folder_path(path)
            
        if not resolved_path:
            return f"Error: folder or file not found: {path}"
            
        try:
            subprocess.Popen(["cmd", "/c", "start", "", os.path.normpath(resolved_path)], creationflags=subprocess.CREATE_NO_WINDOW)
            return f"✅ Opened: {resolved_path}"
        except Exception as e:
            return f"❌ Open failed: {e}"

    def _run_command(self, command: Optional[str]) -> str:
        if not command: return "Error: command required"
        from tools.pc_operator import PCOperator
        op = PCOperator()
        return op.run_command(command)

    def _file_manager(self, path: Optional[str], content: Optional[str] = None) -> str:
        if not path: return "Error: path required"
        from tools.pc_operator import PCOperator
        op = PCOperator()
        if content:
            return op.write_file(path, content)
        return op.read_file(path)

    async def _repair_self(self) -> str:
        try:
            from backend.repair_system import RepairSystem
            from backend.diagnostics import DiagnosticsEngine
            from backend.memory_manager import MemoryManager
            from main import DATA_DIR
            diag = DiagnosticsEngine()
            mem = MemoryManager(DATA_DIR)
            rs = RepairSystem(diag, mem)
            report = await rs.run()
            return f"Self-repair complete. Fixed {report.get('fixed_count', 0)} issues."
        except Exception as e:
            return f"Repair failed: {e}"

    async def _diagnostics(self) -> str:
        try:
            from backend.diagnostics import DiagnosticsEngine
            diag = DiagnosticsEngine()
            report = await diag.run()
            return f"Diagnostics complete. Status: {report.get('status', 'Unknown')}. Found {len(report.get('issues', []))} issues."
        except Exception as e:
            return f"Diagnostics failed: {e}"

    async def _send_whatsapp(self, contact: Optional[str], message: Optional[str]) -> str:
        if not contact:
            return (
                "I can certainly help you send a WhatsApp message, Sir. "
                "However, I need to know who the recipient is. "
                "Please specify it like this: send WhatsApp to [Contact] saying [Message] (for example: 'send WhatsApp to John saying I will be late')."
            )
        
        msg_text = message or ""
        try:
            from tools.whatsapp_control import send_whatsapp_message
            res = await asyncio.to_thread(send_whatsapp_message, contact, msg_text)
            if not msg_text and res.get("status") == "ok":
                return f"I have opened the WhatsApp chat with '{contact}' for you, Sir. What would you like to say?"
            return res.get("message", "WhatsApp send failed.")
        except Exception as e:
            return f"WhatsApp automation failed: {e}"

    async def _read_whatsapp(self) -> str:
        try:
            from tools.whatsapp_control import read_whatsapp_unread
            res = await asyncio.to_thread(read_whatsapp_unread)
            return res.get("message", "WhatsApp read failed.")
        except Exception as e:
            return f"WhatsApp automation failed: {e}"

    async def _find_file(self, query: Optional[str]) -> str:
        if not query: return "Error: search query required, Sir."
        try:
            from tools.file_helper import find_files
            res = await asyncio.to_thread(find_files, query)
            return res.get("message", "Search failed.")
        except Exception as e:
            return f"Search failed: {e}"

    async def _move_file_bulk(self, extension: Optional[str], source: Optional[str], target: Optional[str]) -> str:
        if not source or not target: return "Error: source and target directories required, Sir."
        try:
            from tools.file_helper import move_files
            res = await asyncio.to_thread(move_files, source, target, extension)
            return res.get("message", "Bulk move failed.")
        except Exception as e:
            return f"Bulk move failed: {e}"

    async def _clean_duplicates(self, folder: Optional[str]) -> str:
        if not folder: return "Error: folder path required, Sir."
        try:
            from tools.file_helper import delete_duplicates
            res = await asyncio.to_thread(delete_duplicates, folder)
            return res.get("message", "Duplicate cleanup failed.")
        except Exception as e:
            return f"Duplicate cleanup failed: {e}"

    async def _create_folder(self, folder_path: Optional[str]) -> str:
        if not folder_path: return "Error: folder path required, Sir."
        try:
            from tools.file_helper import create_folder
            res = await asyncio.to_thread(create_folder, folder_path)
            return res.get("message", "Folder creation failed.")
        except Exception as e:
            return f"Folder creation failed: {e}"

    async def _arrange_windows(self, layout: Optional[str]) -> str:
        if not layout: return "Error: layout mode required, Sir."
        try:
            from tools.window_helper import arrange_windows
            res = await asyncio.to_thread(arrange_windows, layout)
            return res.get("message", "Window arrangement failed.")
        except Exception as e:
            return f"Window arrangement failed: {e}"

    async def _launch_workspace(self, workspace_name: Optional[str]) -> str:
        if not workspace_name: return "Error: workspace name required, Sir."
        try:
            from tools.window_helper import launch_workspace
            res = await asyncio.to_thread(launch_workspace, workspace_name)
            return res.get("message", "Workspace initialization failed.")
        except Exception as e:
            return f"Workspace initialization failed: {e}"

    async def _research_competitors(self, query: Optional[str]) -> str:
        if not query: return "Error: query required, Sir."
        try:
            from tools.browser_helper import research_competitors
            res = await asyncio.to_thread(research_competitors, query)
            return res.get("message", "Research failed.")
        except Exception as e:
            return f"Research failed: {e}"

    async def _open_tabs(self, count: Optional[int], topic: Optional[str]) -> str:
        if not topic: return "Error: topic required, Sir."
        c = count or 5
        try:
            from tools.browser_helper import open_tabs
            res = await asyncio.to_thread(open_tabs, c, topic)
            return res.get("message", "Opening tabs failed.")
        except Exception as e:
            return f"Opening tabs failed: {e}"

    async def _download_file(self, url: Optional[str]) -> str:
        if not url: return "Error: URL required, Sir."
        try:
            from tools.browser_helper import download_file
            res = await asyncio.to_thread(download_file, url)
            return res.get("message", "Download failed.")
        except Exception as e:
            return f"Download failed: {e}"

    async def _create_presentation(self, topic: Optional[str]) -> str:
        if not topic: return "Error: presentation topic required, Sir."
        try:
            from tools.presentation_builder import build_presentation
            res = await asyncio.to_thread(build_presentation, topic)
            return res.get("message", "Presentation building failed.")
        except Exception as e:
            return f"Presentation building failed: {e}"

    async def _manage_email(self, sub_action: str, email_id: Optional[str], instructions: Optional[str]) -> str:
        try:
            from tools.email_helper import summarize_inbox, draft_reply
            if sub_action == "summarize" or not email_id:
                res = await asyncio.to_thread(summarize_inbox)
            else:
                inst = instructions or "Standard professional reply"
                res = await asyncio.to_thread(draft_reply, email_id, inst)
            return res.get("message", "Email action failed.")
        except Exception as e:
            return f"Email action failed: {e}"

    async def _manage_calendar(self, sub_action: str, raw_text: Optional[str]) -> str:
        try:
            from tools.calendar_helper import plan_week, schedule_from_text
            if sub_action == "plan_week":
                res = await asyncio.to_thread(plan_week)
            else:
                if not raw_text:
                    return "Error: schedule query text required, Sir."
                res = await asyncio.to_thread(schedule_from_text, raw_text)
            return res.get("message", "Calendar action failed.")
        except Exception as e:
            return f"Calendar action failed: {e}"

    async def _skipit_assistant(self, sub_action: str, days: Optional[int]) -> str:
        try:
            from tools import founder_assistant
            if sub_action == "bookings_today":
                res = await asyncio.to_thread(founder_assistant.get_bookings_today)
            elif sub_action == "inactive_listings":
                res = await asyncio.to_thread(founder_assistant.get_inactive_listings)
            elif sub_action == "inactive_users":
                d = days if days is not None else 60
                res = await asyncio.to_thread(founder_assistant.get_inactive_users, d)
            else:
                res = await asyncio.to_thread(founder_assistant.generate_weekly_report)
            return res.get("message", "SkipIt action failed.")
        except Exception as e:
            return f"SkipIt action failed: {e}"

    async def _smart_cart_assistant(self, sub_action: str) -> str:
        try:
            from tools import founder_assistant
            if sub_action == "pilot_performance":
                res = await asyncio.to_thread(founder_assistant.get_pilot_performance)
            elif sub_action == "revenue_projections":
                res = await asyncio.to_thread(founder_assistant.generate_revenue_projections)
            else:
                res = await asyncio.to_thread(founder_assistant.create_store_pitch_deck)
            return res.get("message", "Smart Cart action failed.")
        except Exception as e:
            return f"Smart Cart action failed: {e}"

    async def _business_intelligence(self) -> str:
        try:
            from tools import founder_assistant
            res = await asyncio.to_thread(founder_assistant.business_intelligence_recommendations)
            return res.get("message", "BI action failed.")
        except Exception as e:
            return f"BI action failed: {e}"

    async def _agent_network(self, sub_action: str, agent_type: Optional[str] = None, agent_instruction: Optional[str] = None) -> str:
        try:
            from tools import agent_network
            if sub_action == "spawn_network":
                res = await agent_network.spawn_agent_network()
            elif sub_action == "ask_agent":
                if not agent_type or not agent_instruction:
                    return "Error: agent_type and agent_instruction are required to delegate a task, Sir."
                res = await agent_network.ask_agent(agent_type, agent_instruction)
            elif sub_action == "list_agents":
                res = await asyncio.to_thread(agent_network.get_network_status)
            else:
                res = await asyncio.to_thread(agent_network.get_network_status)
            return res.get("message", "Agent Network action failed.")
        except Exception as e:
            return f"Agent Network action failed: {e}"

    async def _self_modifier(self, sub_action: str, module: Optional[str] = None, instructions: Optional[str] = None) -> str:
        try:
            from tools import self_modifier
            if sub_action == "rewrite_module":
                if not module:
                    return "Error: module parameter is required for rewriting, Sir."
                inst = instructions or "Improve and clean up any potential bugs"
                res = await asyncio.to_thread(self_modifier.rewrite_module, module, inst)
            elif sub_action == "improve_system":
                res = await asyncio.to_thread(self_modifier.improve_system)
            elif sub_action == "self_repair":
                res = await asyncio.to_thread(self_modifier.self_repair_workflow)
            else:
                res = await asyncio.to_thread(self_modifier.scan_project)
            return res.get("message", "Self-modifier action completed successfully.")
        except Exception as e:
            return f"Self-modifier action failed: {e}"

    async def _self_optimizer(self, sub_action: str, issue: Optional[str] = None) -> str:
        try:
            from tools import self_optimizer
            if sub_action == "auto_repair":
                if not issue:
                    return "Error: issue parameter is required for auto-repair, Sir."
                res = await asyncio.to_thread(self_optimizer.auto_repair, issue)
            elif sub_action == "repair_all":
                res = await asyncio.to_thread(self_optimizer.repair_all)
            else:
                res = await asyncio.to_thread(self_optimizer.check_performance)
            return res.get("message", "Self-optimizer action completed successfully.")
        except Exception as e:
            return f"Self-optimizer action failed: {e}"

    async def _cvcs_click(self, query: Optional[str]) -> str:
        from tools.registry import execute_tool
        return await asyncio.to_thread(execute_tool, "cvcs_click", {"query": query or ""})

    async def _cvcs_type(self, text: Optional[str]) -> str:
        from tools.registry import execute_tool
        return await asyncio.to_thread(execute_tool, "cvcs_type", {"text": text or ""})

    async def _cvcs_read_screen(self) -> str:
        from tools.registry import execute_tool
        return await asyncio.to_thread(execute_tool, "cvcs_read_screen", {})

    async def _cvcs_set_permission(self, level: Optional[float]) -> str:
        from tools.registry import execute_tool
        return await asyncio.to_thread(execute_tool, "cvcs_set_permission", {"level": level or 2.0})

    async def _agent_scan(self) -> str:
        from core.autonomous_agent import AutonomousAgent
        from pathlib import Path
        root = Path(__file__).parent.parent.parent
        agent = AutonomousAgent(str(root))
        res = await agent.scan_and_map()
        return f"Project scanned successfully. Technology stack: {res.get('frameworks')}. Entry points: {res.get('entry_points')}."

    async def _agent_explain(self) -> str:
        from core.autonomous_agent import AutonomousAgent
        from pathlib import Path
        root = Path(__file__).parent.parent.parent
        agent = AutonomousAgent(str(root))
        return await agent.explain_architecture()

    async def _agent_code(self, instructions: Optional[str]) -> str:
        if not instructions:
            return "Error: Coding instructions are required, Sir."
        from core.autonomous_agent import AutonomousAgent
        from pathlib import Path
        root = Path(__file__).parent.parent.parent
        agent = AutonomousAgent(str(root))
        res = await agent.process_intent(instructions)
        if res.get("status") == "pending_confirmation":
            return f"Action requires user confirmation: {res.get('message')}. Pending step: {res.get('pending_step')}."
        elif res.get("status") == "error":
            return f"Error applying changes: {res.get('message')}"
        return f"Successfully processed code modifications. Backup branch: {res.get('backup_branch')}."

    async def _agent_run_tests(self) -> str:
        from core.autonomous_agent import AutonomousAgent
        from pathlib import Path
        root = Path(__file__).parent.parent.parent
        agent = AutonomousAgent(str(root))
        res = await agent.terminal_engine.execute_command("pytest")
        if res.get("status") == "pending_confirmation":
            return f"Test command requires user confirmation: {res.get('message')}"
        if res.get("status") == "error":
            return f"Error executing tests: {res.get('message')}"
        return f"Tests executed. Exit Code: {res.get('exit_code')}.\nStdout:\n{res.get('stdout')}\nStderr:\n{res.get('stderr')}"

    async def _agent_fix_errors(self, logs: Optional[str]) -> str:
        if not logs:
            return "Error: Logs are required to fix errors, Sir."
        from core.autonomous_agent import AutonomousAgent
        from pathlib import Path
        root = Path(__file__).parent.parent.parent
        agent = AutonomousAgent(str(root))
        res = await agent.handle_build_error(logs)
        if res.get("status") == "error":
            return f"Error fixing build: {res.get('message')}"
        return f"Attempted to fix build error. Details: {res.get('message')}. Analysis:\n{res.get('analysis')}"

    async def _start_meeting(self) -> str:
        try:
            from tools.meeting_assistant import start_meeting
            res = await asyncio.to_thread(start_meeting)
            return res.get("message", "Meeting started.")
        except Exception as e:
            return f"Error starting meeting: {e}"

    async def _stop_meeting(self) -> str:
        try:
            from tools.meeting_assistant import stop_meeting
            res = await asyncio.to_thread(stop_meeting)
            return res.get("message", "Meeting stopped.")
        except Exception as e:
            return f"Error stopping meeting: {e}"

    async def _recall_meeting(self, query: Optional[str]) -> str:
        try:
            from tools.meeting_assistant import recall_meeting
            res = await asyncio.to_thread(recall_meeting, query or "")
            return res.get("message", "No meetings found.")
        except Exception as e:
            return f"Error recalling meeting: {e}"

    async def _get_action_items(self) -> str:
        try:
            from tools.meeting_assistant import get_action_items
            res = await asyncio.to_thread(get_action_items)
            return res.get("message", "No action items found.")
        except Exception as e:
            return f"Error getting action items: {e}"

    async def _register_project(self, path: str) -> str:
        try:
            from tools.project_intelligence import register_project
            res = await asyncio.to_thread(register_project, path or "")
            return res.get("message", "Project registered.")
        except Exception as e:
            return f"Error registering project: {e}"

    async def _scan_project_changes(self, project_id: Optional[str]) -> str:
        try:
            from tools.project_intelligence import scan_project_changes
            res = await asyncio.to_thread(scan_project_changes, project_id or "")
            return res.get("message", "Project changes scanned.")
        except Exception as e:
            return f"Error scanning project changes: {e}"

    async def _get_project_status(self, project_name: Optional[str]) -> str:
        try:
            from tools.project_intelligence import get_project_status
            res = await asyncio.to_thread(get_project_status, project_name or "")
            return res.get("message", "No status report found.")
        except Exception as e:
            return f"Error getting project status: {e}"

    async def _query_recent_work(self, timeframe: Optional[str]) -> str:
        try:
            from tools.project_intelligence import get_recent_work
            res = await asyncio.to_thread(get_recent_work, timeframe or "today")
            return res.get("message", "No recent work found.")
        except Exception as e:
            return f"Error querying recent work: {e}"

    async def _continue_where_left_off(self, project_id: Optional[str]) -> str:
        try:
            from tools.project_intelligence import continue_where_left_off
            res = await asyncio.to_thread(continue_where_left_off, project_id or "")
            return res.get("message", "Could not continue where left off.")
        except Exception as e:
            return f"Error executing continue where left off: {e}"

    async def _screenshot(self) -> str:
        try:
            from tools.system_control import take_screenshot
            res = await asyncio.to_thread(take_screenshot)
            return res.get("message", "Screenshot captured successfully.")
        except Exception as e:
            return f"Error taking screenshot: {e}"

    async def _lock_computer(self) -> str:
        try:
            import ctypes
            if platform.system() == "Windows":
                ctypes.windll.user32.LockWorkStation()
                return "Computer locked successfully, Sir."
            else:
                return "Locking computer is only supported on Windows, Sir."
        except Exception as e:
            return f"Error locking computer: {e}"

    async def _press_key(self, key: str) -> str:
        try:
            import pyautogui
            key_clean = key.strip().lower()
            if "+" in key_clean:
                keys = key_clean.split("+")
                pyautogui.hotkey(*[k.strip() for k in keys])
                return f"Successfully pressed hotkey combination: {key_clean}, Sir."
            else:
                pyautogui.press(key_clean)
                return f"Successfully pressed key: {key_clean}, Sir."
        except Exception as e:
            return f"Error pressing key: {e}"

    async def _mouse_control(self, action: str, x: Optional[int], y: Optional[int], amount: Optional[int]) -> str:
        try:
            import pyautogui
            act = action.strip().lower()
            if act == "click":
                pyautogui.click()
                return "Clicked at current position, Sir."
            elif act == "double_click":
                pyautogui.doubleClick()
                return "Double-clicked at current position, Sir."
            elif act == "right_click":
                pyautogui.rightClick()
                return "Right-clicked at current position, Sir."
            elif act == "move":
                if x is not None and y is not None:
                    pyautogui.moveTo(x, y)
                    return f"Moved mouse to coordinates ({x}, {y}), Sir."
                return "Error: missing coordinates for mouse move."
            elif act == "scroll":
                scroll_amount = amount if amount is not None else 100
                pyautogui.scroll(scroll_amount)
                return f"Scrolled mouse by {scroll_amount}, Sir."
            return f"Unknown mouse action: {action}"
        except Exception as e:
            return f"Error executing mouse action: {e}"

    async def _check_file_exists(self, path: str) -> str:
        try:
            exists = os.path.exists(path)
            status = "exists" if exists else "does not exist"
            return f"The file '{path}' {status}, Sir."
        except Exception as e:
            return f"Error checking file: {e}"

    async def _list_directory(self, path: Optional[str]) -> str:
        try:
            target_path = path or os.getcwd()
            items = os.listdir(target_path)
            files = [i for i in items if os.path.isfile(os.path.join(target_path, i))]
            dirs = [i for i in items if os.path.isdir(os.path.join(target_path, i))]
            return f"Contents of {target_path}, Sir:\nFolders: {', '.join(dirs) or 'None'}\nFiles: {', '.join(files) or 'None'}"
        except Exception as e:
            return f"Error listing directory: {e}"

    async def _analyze_code(self, path: Optional[str]) -> str:
        try:
            from tools.code_analyzer import CodebaseAnalyzer
            target_path = path or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            analyzer = CodebaseAnalyzer(target_path)
            res = analyzer.analyze()
            if res.get("status") == "ok":
                return f"Code Analysis Health Score: {res.get('health_score')}/100\nSummary: {res.get('summary')}\nDetails: {res.get('data')}"
            return f"Code Analysis failed: {res.get('message')}"
        except Exception as e:
            return f"Error running code analysis: {e}"

    async def _long_term_memory(self, category: str, action: str, key: Optional[str], value: Optional[str]) -> str:
        try:
            from core.memory.long_term_memory import LongTermMemory
            ltm = LongTermMemory()
            act = action.strip().lower()
            if act == "store":
                if not key or not value:
                    return "Error: key and value are required to store memory, Sir."
                success = ltm.store(category, key, value)
                return f"Memory stored successfully: {key} -> {value}, Sir." if success else "Failed to store memory."
            elif act == "retrieve":
                if not key:
                    return "Error: key is required to retrieve memory, Sir."
                val = ltm.retrieve(category, key)
                return f"Memory for {key} under {category}: {val}" if val else f"No memory found for {key} under {category}, Sir."
            elif act == "update":
                if not key or not value:
                    return "Error: key and value are required to update memory, Sir."
                success = ltm.update(category, key, value)
                return f"Memory updated successfully: {key} -> {value}, Sir." if success else "Failed to update memory."
            elif act == "forget":
                if not key:
                    return "Error: key is required to forget memory, Sir."
                success = ltm.forget(category, key)
                return f"Memory for {key} forgotten, Sir." if success else "Failed to delete memory."
            elif act == "search":
                if not key:
                    return "Error: query key is required to search memories, Sir."
                results = ltm.search(category, key)
                return f"Search results for query '{key}': {results}"
            elif act == "summarize":
                return ltm.summarize(category)
            else:
                return f"Unknown long term memory action: {action}"
        except Exception as e:
            return f"Error managing long term memory: {e}"

    async def _vision_analyze(self, image_path: Optional[str], action: str) -> str:
        try:
            from core.vision.vision_engine import VisionEngine
            from tools.system_control import take_screenshot, SCREENSHOT_PATH
            target_path = image_path
            if not target_path or not os.path.exists(target_path):
                # Auto capture screenshot first
                await asyncio.to_thread(take_screenshot)
                target_path = SCREENSHOT_PATH
            
            engine = VisionEngine()
            analysis = engine.analyze_screenshot(target_path)
            act = action.strip().lower()
            if act == "screenshot_analysis":
                return analysis.get("summary", "Analysis complete.")
            elif act == "ui_explanation":
                return engine.explain_ui_screenshot(analysis)
            elif act == "ocr":
                return f"OCR Text Extracted, Sir:\n{analysis.get('ocr_text', 'No text detected')}"
            elif act == "error_debugging":
                errors = analysis.get("detected_errors", [])
                if errors:
                    return f"Error Detected on Screen, Sir:\n" + "\n".join([f"- {e}" for e in errors])
                return "No obvious error text detected on screen, Sir."
            else:
                return f"Unknown vision action: {action}"
        except Exception as e:
            return f"Error running vision analysis: {e}"

    async def _voice_speak(self, text: str) -> str:
        try:
            from tools.voice_tts import speak_text_async
            try:
                await speak_text_async(text)
                return f"Spoken out loud: '{text}'"
            except Exception:
                from tools.tts_speaker import TTSSpeaker
                speaker = TTSSpeaker()
                speaker.speak(text)
                return f"Spoken out loud (fallback): '{text}'"
        except Exception as e:
            return f"Error simulating speech: {e}"

    async def _git_summary(self, path: Optional[str]) -> str:
        try:
            target = path or os.getcwd()
            res = subprocess.run(["git", "status", "-s"], capture_output=True, text=True, cwd=target, timeout=5)
            if res.returncode != 0:
                return f"Git is not initialized in {target} or failed: {res.stderr or res.stdout}"
            changes = res.stdout.strip()
            if not changes:
                return "Clean working directory. No changes, Sir."
            return f"Git changes in {target}, Sir:\n{changes}"
        except Exception as e:
            return f"Error running git summary: {e}"

    async def _switch_to_window(self, title_query: str) -> str:
        try:
            from tools.desktop_automation import switch_to_window
            success = switch_to_window(title_query)
            return f"Successfully switched to window matching '{title_query}', Sir." if success else f"Could not find or switch to window matching '{title_query}', Sir."
        except Exception as e:
            return f"Error switching window: {e}"

    async def _read_active_window(self) -> str:
        try:
            from tools.desktop_automation import get_active_window_title
            title = get_active_window_title()
            return f"Active window title: '{title}', Sir."
        except Exception as e:
            return f"Error reading active window: {e}"

    async def _read_clipboard(self) -> str:
        try:
            from tools.desktop_automation import read_clipboard
            text = read_clipboard()
            return f"Clipboard text, Sir: '{text}'" if text else "Clipboard is empty or contains non-text data, Sir."
        except Exception as e:
            return f"Error reading clipboard: {e}"

    async def _write_clipboard(self, text: str) -> str:
        try:
            from tools.desktop_automation import write_clipboard
            success = write_clipboard(text)
            return f"Successfully wrote '{text[:50]}...' to clipboard, Sir." if success else "Failed to write text to clipboard."
        except Exception as e:
            return f"Error writing to clipboard: {e}"

    async def _rename_file(self, old_path: str, new_path: str) -> str:
        try:
            from tools.desktop_automation import rename_file
            res = rename_file(old_path, new_path)
            return res.get("message", "File rename complete.")
        except Exception as e:
            return f"Error renaming file: {e}"

    async def _move_file(self, source: str, destination: str) -> str:
        try:
            from tools.desktop_automation import move_file
            res = move_file(source, destination)
            return res.get("message", "File move complete.")
        except Exception as e:
            return f"Error moving file: {e}"

    async def _delete_file(self, path: str) -> str:
        try:
            from tools.desktop_automation import delete_file_gated
            res = await delete_file_gated(path)
            return res.get("message", "File deletion complete.")
        except Exception as e:
            return f"Error deleting file: {e}"

    async def _launch_vscode(self, path: Optional[str]) -> str:
        try:
            cmd = ["cmd", "/c", "code"]
            if path:
                cmd.append(os.path.abspath(path))
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
            return f"Successfully launched Visual Studio Code{' on ' + path if path else ''}, Sir."
        except Exception as e:
            return f"Error launching VS Code: {e}"

    async def _launch_browser(self, url: Optional[str]) -> str:
        try:
            target = url or "https://www.google.com"
            import webbrowser
            webbrowser.open(target)
            return f"Successfully launched default browser opening '{target}', Sir."
        except Exception as e:
            return f"Error launching browser: {e}"

    async def _launch_terminal(self, command: Optional[str]) -> str:
        try:
            cmd = ["cmd.exe"]
            if command:
                cmd.extend(["/k", command])
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            return f"Successfully launched cmd terminal{' running ' + command if command else ''}, Sir."
        except Exception as e:
            return f"Error launching terminal: {e}"

    async def _weather(self, city: str) -> str:
        try:
            import random
            temp = random.randint(15, 28)
            acid_rain = random.choice([True, False])
            rain_str = "Acid rain levels: Nominal. Visibility: clear." if not acid_rain else "⚠️ Alert: Light Acid Rain detected. Shielding advised."
            return f"Weather reporting in the server runtime is currently generated using hardcoded randomized values and mock environments. (Sandbox Mock)\n\nLocal weather forecast for {city.upper()} // VOID Core Environment:\n- Temperature: {temp}°C\n- Humidity: 68%\n- {rain_str}"
        except Exception as e:
            return f"Error checking weather: {e}"

    def stats(self) -> Dict[str, Any]:
        """System stats for /stats endpoint."""
        disk = psutil.disk_usage(os.path.abspath(os.sep))
        battery = psutil.sensors_battery()
        return {
            "cpu_usage": psutil.cpu_percent(interval=0.1),
            "ram_usage": psutil.virtual_memory().percent,
            "storage_used_gb": round(disk.used / (1024**3), 1),
            "storage_total_gb": round(disk.total / (1024**3), 1),
            "battery_percent": round(battery.percent) if battery else None,
            "battery_charging": battery.power_plugged if battery else False,
            "network_online": True,  # Simplify
            "gpu_usage": None,  # Future
        }

    async def _agent_refactor(self, file_path: Optional[str]) -> str:
        """Runs the AutonomousAgent refactoring logic on a target file."""
        if not file_path:
            return "Error: File path is required for refactoring, Sir."
        try:
            from core.autonomous_agent import AutonomousAgent
            from pathlib import Path
            root = Path(__file__).parent.parent.parent
            agent = AutonomousAgent(str(root))
            res = await agent.refactor_code(file_path)
            if res.get("status") == "error":
                return f"Error refactoring: {res.get('message')}"
            return f"Refactored code successfully. Details: {res.get('message')}. Backup branch: {res.get('backup_branch')}."
        except Exception as e:
            return f"Failed to refactor file: {str(e)}"

    async def _change_motd(self, motd: Optional[str]) -> str:
        """Updates the global panel Message of the Day."""
        new_motd = (motd or "").strip()
        if not new_motd:
            return "Error: MOTD message content cannot be empty, Sir."
        try:
            import server.routes.admin as admin_route
            admin_route.MOTD = new_motd
            return f"Updated panel Message of the Day to: \"{new_motd}\""
        except Exception as e:
            return f"Failed to update Message of the Day: {str(e)}"

