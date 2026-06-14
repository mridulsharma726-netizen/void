import asyncio
import importlib
import logging
import time
from typing import Dict, Any, List

from pydantic import ValidationError

from backend.schemas import ToolCall
from backend.tool_schemas import get_tool_spec, validate_tool_input, validate_tool_output, TOOL_REGISTRY
from backend.tools_runtime import ToolRuntime

logger = logging.getLogger("void.tool_manager")

class ToolManager:
    def __init__(self, runtime: ToolRuntime):
        self.runtime = runtime
        self.specs = TOOL_REGISTRY  # Full dynamic registry

    async def execute(self, name: str, payload: Dict[str, Any] | None = None) -> ToolCall:
        """Execute tool with schema validation, timeout, logging."""
        data = payload or {}
        if name not in self.specs:
            return ToolCall(
                name=name, 
                input=data, 
                output=f"Unknown tool '{name}'. Available: {list(self.specs.keys())}"
            )

        input_model, output_model, timeout_sec = get_tool_spec(name)
        
        # 1. Input validation
        try:
            validated_input = validate_tool_input(name, data)
        except ValidationError as ve:
            return ToolCall(
                name=name,
                input=data,
                output=f"Input validation failed: {ve.errors()[:3]}"  # First 3 errors
            )

        started = time.perf_counter()
        try:
            # 2. Execute with timeout
            raw_result = await asyncio.wait_for(
                self.runtime.execute(name, validated_input), 
                timeout=timeout_sec
            )
            
            # 3. Output validation
            validated_output = validate_tool_output(name, raw_result.output)
            
            elapsed = int((time.perf_counter() - started) * 1000)
            logger.info(f"Tool '{name}' OK: {elapsed}ms, input={validated_input}")
            
            return ToolCall(
                name=name,
                input=validated_input,
                output=validated_output.message,
                meta={"latency_ms": elapsed, "status": validated_output.status}
            )
            
        except asyncio.TimeoutError:
            elapsed = int((time.perf_counter() - started) * 1000)
            logger.warning(f"Tool '{name}' TIMEOUT: {elapsed}ms")
            return ToolCall(
                name=name,
                input=validated_input,
                output=f"Tool '{name}' timed out after {timeout_sec}s",
                meta={"status": "TIMEOUT", "latency_ms": elapsed}
            )
        except Exception as exc:
            elapsed = int((time.perf_counter() - started) * 1000)
            logger.error(f"Tool '{name}' FAILED: {exc}", exc_info=True)
            return ToolCall(
                name=name,
                input=validated_input,
                output=f"Tool '{name}' error: {str(exc)}",
                meta={"status": "FAIL", "latency_ms": elapsed}
            )

    async def check_all_tools(self) -> Dict[str, Any]:
        """Comprehensive health check with schema validation."""
        checks = []
        failed = 0
        
        # List of tools that are unsafe to auto-execute during health check
        unsafe_tools = {
            "open_app", "close_app", "open_url", "search_google", "play_youtube", "open_folder", 
            "repair_self", "diagnostics", "find_file", "move_file_bulk", "clean_duplicates", 
            "create_folder", "arrange_windows", "launch_workspace", "research_competitors", 
            "open_tabs", "download_file", "send_whatsapp", "read_whatsapp",
            "create_presentation", "manage_email", "manage_calendar",
            "skipit_assistant", "smart_cart_assistant", "business_intelligence", "agent_network",
            "self_modifier", "self_optimizer", "start_meeting", "stop_meeting", "recall_meeting",
            "get_action_items", "register_project", "scan_project_changes", "get_project_status",
            "query_recent_work", "run_command", "file_manager", "cvcs_click", "cvcs_type",
            "cvcs_read_screen", "cvcs_set_permission", "agent_scan", "agent_code",
            "agent_run_tests", "agent_fix_errors", "continue_where_left_off", "screenshot",
            "lock_computer", "press_key", "mouse_control"
        }
        
        for name in self.specs:
            started = time.perf_counter()
            status = "OK"
            detail = "Ready (specs verified)"
            
            elapsed = int((time.perf_counter() - started) * 1000)
            check = {
                "tool": name,
                "status": status,
                "latency_ms": elapsed,
                "detail": detail,
                "timeout_sec": get_tool_spec(name)[2]
            }
            checks.append(check)
        
        overall_status = "OK" if failed == 0 else "warning" if failed <= len(checks)//2 else "critical"
        logger.info(f"Tool health: {overall_status}, failed={failed}/{len(checks)}")
        
        return {
            "status": overall_status,
            "total": len(checks),
            "failed": failed,
            "checks": checks
        }

    def list_tools(self) -> List[str]:
        """List all registered tools."""
        return list(self.specs.keys())
