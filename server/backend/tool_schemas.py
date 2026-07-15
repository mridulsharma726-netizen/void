from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from enum import Enum

class ToolStatus(str, Enum):
    OK = "OK"
    FAIL = "FAIL"
    TIMEOUT = "TIMEOUT"

class ToolInput(BaseModel):
    app: Optional[str] = Field(None, description="App name to open/close")
    url: Optional[str] = Field(None, description="URL to open")
    query: Optional[str] = Field(None, description="Search query")
    path: Optional[str] = Field(None, description="File/path")
    command: Optional[str] = Field(None, description="Shell command")
    content: Optional[str] = Field(None, description="File content")

class ToolOutput(BaseModel):
    status: ToolStatus
    message: str
    data: Optional[Dict[str, Any]] = None

class TimeInput(ToolInput):
    pass

class TimeOutput(ToolOutput):
    time_str: Optional[str] = Field(None, description="Formatted current time")

class SystemInfoInput(ToolInput):
    pass

class SystemInfoOutput(ToolOutput):
    os_info: Optional[str] = None
    cpu_pct: Optional[float] = None
    ram_pct: Optional[float] = None

class OpenAppInput(ToolInput):
    app: str = Field(..., description="App executable/name")

class OpenAppOutput(ToolOutput):
    pass

class OpenUrlInput(ToolInput):
    url: str = Field(..., description="Valid URL")

class OpenUrlOutput(ToolOutput):
    pass

class SearchGoogleInput(ToolInput):
    query: str = Field(..., min_length=1)

class SearchGoogleOutput(ToolOutput):
    pass

class RunCommandInput(ToolInput):
    command: str = Field(..., description="Shell command")

class SendWhatsAppInput(ToolInput):
    contact: Optional[str] = Field(None, description="WhatsApp contact or group name")
    message: Optional[str] = Field(None, description="Text message to send")

class ReadWhatsAppInput(ToolInput):
    pass

class FindFileInput(ToolInput):
    query: str = Field(..., description="Query name to search for")

class MoveFileInput(ToolInput):
    extension: Optional[str] = Field(None, description="Optional extension/pattern constraint")
    source: str = Field(..., description="Source folder")
    target: str = Field(..., description="Target folder")

class CleanDuplicatesInput(ToolInput):
    folder: str = Field(..., description="Folder to clean duplicates in")

class CreateFolderInput(ToolInput):
    folder_path: str = Field(..., description="Folder path to create")

class ArrangeWindowsInput(ToolInput):
    layout: str = Field(..., description="Layout style (split, tile, maximize-all, minimize-all)")

class LaunchWorkspaceInput(ToolInput):
    workspace_name: str = Field(..., description="Name of the workspace to launch")

class ResearchCompetitorsInput(ToolInput):
    query: str = Field(..., description="Company or startup topic to research")

class OpenTabsInput(ToolInput):
    count: int = Field(5, description="Number of tabs to open")
    topic: str = Field(..., description="Topic of interest")

class DownloadFileInput(ToolInput):
    url: str = Field(..., description="URL of file to download")

class CreatePresentationInput(ToolInput):
    topic: str = Field(..., description="Topic of presentation")

class ManageEmailInput(ToolInput):
    sub_action: str = Field("summarize", description="Sub-action: 'summarize' or 'draft'")
    email_id: Optional[str] = Field(None, description="Optional ID of email to reply to")
    instructions: Optional[str] = Field(None, description="Optional instructions/reply text draft context")

class ManageCalendarInput(ToolInput):
    raw_text: Optional[str] = Field(None, description="Raw relative scheduling query for schedule_event")

class SkipItAssistantInput(ToolInput):
    sub_action: str = Field("weekly_report", description="Sub-action: bookings_today, inactive_listings, inactive_users, weekly_report")
    days: Optional[int] = Field(60, description="Inactivity threshold days for inactive_users query")

class SmartCartAssistantInput(ToolInput):
    sub_action: str = Field("pilot_performance", description="Sub-action: pilot_performance, revenue_projections, store_pitch_deck")

class BusinessIntelligenceInput(ToolInput):
    pass

class AgentNetworkInput(ToolInput):
    sub_action: str = Field("status", description="Sub-action: spawn_network, ask_agent, status, list_agents")
    agent_type: Optional[str] = Field(None, description="Target agent: research, coding, testing, security, planner")
    agent_instruction: Optional[str] = Field(None, description="Task instruction for the target agent")

class SelfModifierInput(ToolInput):
    sub_action: str = Field("scan_project", description="Sub-action: rewrite_module, scan_project, improve_system, self_repair")
    module: Optional[str] = Field(None, description="Module/file name to rewrite")
    instructions: Optional[str] = Field(None, description="Instructions/goals for code improvements")

class SelfOptimizerInput(ToolInput):
    sub_action: str = Field("check_performance", description="Sub-action: check_performance, auto_repair, repair_all")
    issue: Optional[str] = Field(None, description="Specific issue description to repair")

class CVCSClickInput(ToolInput):
    query: str = Field(..., description="Target button or text to click")

class CVCSTypeInput(ToolInput):
    text: str = Field(..., description="Text to type at active cursor")

class CVCSReadScreenInput(ToolInput):
    pass

class CVCSSetPermissionInput(ToolInput):
    level: float = Field(2.0, description="Permission level to enforce (1.0 to 4.0)")

class AgentScanInput(ToolInput):
    pass

class AgentExplainInput(ToolInput):
    pass

class AgentCodeInput(ToolInput):
    instructions: str = Field(..., description="Coding instructions or feature request")

class AgentRunTestsInput(ToolInput):
    pass

class AgentFixErrorsInput(ToolInput):
    logs: str = Field(..., description="Stack trace or build error logs to analyze and fix")

class StartMeetingInput(ToolInput):
    pass

class StopMeetingInput(ToolInput):
    pass

class RecallMeetingInput(ToolInput):
    query: Optional[str] = Field(None, description="Optional query string to search meetings")

class GetActionItemsInput(ToolInput):
    pass

class RegisterProjectInput(ToolInput):
    path: str = Field(..., description="Absolute path to the project directory to register")

class ScanProjectChangesInput(ToolInput):
    project_id: Optional[str] = Field(None, description="Optional ID of the project to scan. Scans first tracked project if omitted.")

class GetProjectStatusInput(ToolInput):
    project_name: Optional[str] = Field(None, description="Optional name of the project. Lists all tracked projects if omitted.")

class QueryRecentWorkInput(ToolInput):
    timeframe: Optional[str] = Field("today", description="Timeframe to query (e.g. today, yesterday, week)")

class ContinueWhereLeftOffInput(ToolInput):
    project_id: Optional[str] = Field(None, description="Optional ID of the project to resume. Uses active project if omitted.")

class ScreenshotInput(ToolInput):
    pass

class LockComputerInput(ToolInput):
    pass

class PressKeyInput(ToolInput):
    key: str = Field(..., description="Key to press or hotkey combination")

class MouseControlInput(ToolInput):
    action: str = Field(..., description="Mouse action (click, double_click, right_click, move, scroll)")
    x: Optional[int] = Field(None, description="X coordinate for move")
    y: Optional[int] = Field(None, description="Y coordinate for move")
    amount: Optional[int] = Field(None, description="Scroll amount")

class CheckFileExistsInput(ToolInput):
    path: str = Field(..., description="Path to check if exists")

class ListDirectoryInput(ToolInput):
    path: Optional[str] = Field(None, description="Directory path to list")

class AnalyzeCodeInput(ToolInput):
    path: Optional[str] = Field(None, description="Absolute path to codebase to analyze")

class LongTermMemoryInput(ToolInput):
    category: str = Field(..., description="Memory category, e.g. projects, preferences, coding_style, tasks, deadlines")
    action: str = Field("retrieve", description="Memory action: store, retrieve, update, forget, search, summarize")
    key: Optional[str] = Field(None, description="Key for memory lookup or storage")
    value: Optional[str] = Field(None, description="Value to store or update")

class VisionAnalyzeInput(ToolInput):
    image_path: Optional[str] = Field(None, description="Path to screenshot image. If omitted, captures screen first.")
    action: str = Field("screenshot_analysis", description="Action: screenshot_analysis, ui_explanation, ocr, error_debugging")

class VoiceSpeakInput(ToolInput):
    text: str = Field(..., description="Text content to speak out loud")

class GitSummaryInput(ToolInput):
    path: Optional[str] = Field(None, description="Path to git repository")

class SwitchToWindowInput(ToolInput):
    title_query: str = Field(..., description="Query matching title of target window")

class ReadActiveWindowInput(ToolInput):
    pass

class ReadClipboardInput(ToolInput):
    pass

class WriteClipboardInput(ToolInput):
    text: str = Field(..., description="Text to write to clipboard")

class RenameFileInput(ToolInput):
    old_path: str = Field(..., description="Original file path")
    new_path: str = Field(..., description="New target file path")

class MoveSingleFileInput(ToolInput):
    source: str = Field(..., description="Source file path")
    destination: str = Field(..., description="Destination folder/file path")

class DeleteFileInput(ToolInput):
    path: str = Field(..., description="Path to file/folder to delete")

class LaunchVSCodeInput(ToolInput):
    path: Optional[str] = Field(None, description="Workspace path to open in VS Code")

class LaunchBrowserInput(ToolInput):
    url: Optional[str] = Field(None, description="URL to open in browser")

class LaunchTerminalInput(ToolInput):
    command: Optional[str] = Field(None, description="Initial command to run in terminal")

class WeatherInput(ToolInput):
    city: str = Field("New York", description="City name to fetch weather for")

class AgentRefactorInput(ToolInput):
    file_path: str = Field(..., description="File path to refactor")

class ChangeMOTDInput(ToolInput):
    motd: str = Field(..., description="New Message of the Day text")

# Tool Registry - name → (input_model, output_model, timeout_sec)
# Registered with generous 25-second timeouts for Digital Employee operations
TOOL_REGISTRY = {
    "time": (TimeInput, ToolOutput, 2.0),
    "system_info": (SystemInfoInput, ToolOutput, 2.0),
    "open_app": (OpenAppInput, ToolOutput, 3.0),
    "close_app": (OpenAppInput, ToolOutput, 3.0),
    "open_url": (OpenUrlInput, ToolOutput, 3.5),
    "search_google": (SearchGoogleInput, ToolOutput, 5.0),
    "play_youtube": (SearchGoogleInput, ToolOutput, 5.0),
    "open_folder": (ToolInput, ToolOutput, 3.0),
    "run_command": (RunCommandInput, ToolOutput, 10.0),
    "file_manager": (ToolInput, ToolOutput, 5.0),
    "repair_self": (ToolInput, ToolOutput, 30.0),
    "diagnostics": (ToolInput, ToolOutput, 10.0),
    "send_whatsapp": (SendWhatsAppInput, ToolOutput, 30.0),
    "read_whatsapp": (ReadWhatsAppInput, ToolOutput, 30.0),
    "find_file": (FindFileInput, ToolOutput, 10.0),
    "move_file_bulk": (MoveFileInput, ToolOutput, 10.0),
    "clean_duplicates": (CleanDuplicatesInput, ToolOutput, 15.0),
    "create_folder": (CreateFolderInput, ToolOutput, 5.0),
    "arrange_windows": (ArrangeWindowsInput, ToolOutput, 5.0),
    "launch_workspace": (LaunchWorkspaceInput, ToolOutput, 10.0),
    "research_competitors": (ResearchCompetitorsInput, ToolOutput, 15.0),
    "open_tabs": (OpenTabsInput, ToolOutput, 5.0),
    "download_file": (DownloadFileInput, ToolOutput, 20.0),
    "create_presentation": (CreatePresentationInput, ToolOutput, 25.0),
    "manage_email": (ManageEmailInput, ToolOutput, 25.0),
    "manage_calendar": (ManageCalendarInput, ToolOutput, 25.0),
    "skipit_assistant": (SkipItAssistantInput, ToolOutput, 25.0),
    "smart_cart_assistant": (SmartCartAssistantInput, ToolOutput, 25.0),
    "business_intelligence": (BusinessIntelligenceInput, ToolOutput, 25.0),
    "agent_network": (AgentNetworkInput, ToolOutput, 25.0),
    "self_modifier": (SelfModifierInput, ToolOutput, 95.0),
    "self_optimizer": (SelfOptimizerInput, ToolOutput, 30.0),
    "cvcs_click": (CVCSClickInput, ToolOutput, 15.0),
    "cvcs_type": (CVCSTypeInput, ToolOutput, 10.0),
    "cvcs_read_screen": (CVCSReadScreenInput, ToolOutput, 15.0),
    "cvcs_set_permission": (CVCSSetPermissionInput, ToolOutput, 5.0),
    "agent_scan": (AgentScanInput, ToolOutput, 30.0),
    "agent_explain": (AgentExplainInput, ToolOutput, 45.0),
    "agent_code": (AgentCodeInput, ToolOutput, 95.0),
    "agent_run_tests": (AgentRunTestsInput, ToolOutput, 30.0),
    "agent_fix_errors": (AgentFixErrorsInput, ToolOutput, 60.0),
    "start_meeting": (StartMeetingInput, ToolOutput, 10.0),
    "stop_meeting": (StopMeetingInput, ToolOutput, 95.0),
    "recall_meeting": (RecallMeetingInput, ToolOutput, 10.0),
    "get_action_items": (GetActionItemsInput, ToolOutput, 10.0),
    "register_project": (RegisterProjectInput, ToolOutput, 180.0),
    "scan_project_changes": (ScanProjectChangesInput, ToolOutput, 15.0),
    "get_project_status": (GetProjectStatusInput, ToolOutput, 10.0),
    "query_recent_work": (QueryRecentWorkInput, ToolOutput, 15.0),
    "continue_where_left_off": (ContinueWhereLeftOffInput, ToolOutput, 15.0),
    "screenshot": (ScreenshotInput, ToolOutput, 10.0),
    "lock_computer": (LockComputerInput, ToolOutput, 5.0),
    "press_key": (PressKeyInput, ToolOutput, 5.0),
    "mouse_control": (MouseControlInput, ToolOutput, 5.0),
    "check_file_exists": (CheckFileExistsInput, ToolOutput, 5.0),
    "list_directory": (ListDirectoryInput, ToolOutput, 10.0),
    "analyze_code": (AnalyzeCodeInput, ToolOutput, 60.0),
    "long_term_memory": (LongTermMemoryInput, ToolOutput, 10.0),
    "vision_analyze": (VisionAnalyzeInput, ToolOutput, 20.0),
    "voice_speak": (VoiceSpeakInput, ToolOutput, 10.0),
    "git_summary": (GitSummaryInput, ToolOutput, 15.0),
    "switch_to_window": (SwitchToWindowInput, ToolOutput, 5.0),
    "read_active_window": (ReadActiveWindowInput, ToolOutput, 5.0),
    "read_clipboard": (ReadClipboardInput, ToolOutput, 5.0),
    "write_clipboard": (WriteClipboardInput, ToolOutput, 5.0),
    "rename_file": (RenameFileInput, ToolOutput, 5.0),
    "move_file": (MoveSingleFileInput, ToolOutput, 5.0),
    "delete_file": (DeleteFileInput, ToolOutput, 15.0),
    "launch_vscode": (LaunchVSCodeInput, ToolOutput, 10.0),
    "launch_browser": (LaunchBrowserInput, ToolOutput, 10.0),
    "launch_terminal": (LaunchTerminalInput, ToolOutput, 10.0),
    "weather": (WeatherInput, ToolOutput, 10.0),
    "agent_refactor": (AgentRefactorInput, ToolOutput, 95.0),
    "change_motd": (ChangeMOTDInput, ToolOutput, 5.0),
}

def get_tool_spec(name: str):
    """Get input/output models and timeout for tool."""
    return TOOL_REGISTRY.get(name, (ToolInput, ToolOutput, 4.0))

def validate_tool_input(name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate input against schema."""
    input_model, _, _ = get_tool_spec(name)
    return input_model(**data).dict()

def validate_tool_output(name: str, output: str) -> ToolOutput:
    """Parse/validate tool output."""
    _, output_model, _ = get_tool_spec(name)
    # Simple parsing for now; enhance with structured output later
    return output_model(status=ToolStatus.OK, message=output)
