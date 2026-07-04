import logging
from typing import Dict, Any, List
from server.backend.tool_schemas import TOOL_REGISTRY, get_tool_spec

logger = logging.getLogger("void.tool_orchestrator")

class ToolOrchestrator:
    def __init__(self):
        # Security permissions classification
        self.permissions = {
            "run_command": "critical",
            "agent_code": "high",
            "self_modifier": "high",
            "delete_file": "high",
            "rename_file": "medium",
            "move_file": "medium",
            "open_app": "medium",
            "close_app": "medium",
            "cvcs_click": "medium",
            "cvcs_type": "medium",
            "mouse_control": "medium",
            "press_key": "medium"
        }

    def enforce_permission(self, name: str) -> None:
        """Enforces risk tier. Raises Exception if permission is denied."""
        perm = self.permissions.get(name, "low")
        if perm in ["high", "critical"]:
            from core.brain import is_developer_mode
            if not is_developer_mode():
                raise PermissionError(f"Action Denied: Tool '{name}' requires Developer Mode (Risk Tier: {perm.upper()}).")

    def get_tool_metadata(self, name: str) -> Dict[str, Any]:
        """Retrieve full structured tool metadata."""
        try:
            spec = get_tool_spec(name)
            input_model, output_model, timeout = spec
            
            # Retrieve schema dictionaries
            if hasattr(input_model, "model_json_schema"):
                input_schema = input_model.model_json_schema()
            elif hasattr(input_model, "schema"):
                input_schema = input_model.schema()
            else:
                input_schema = {}

            if hasattr(output_model, "model_json_schema"):
                output_schema = output_model.model_json_schema()
            elif hasattr(output_model, "schema"):
                output_schema = output_model.schema()
            else:
                output_schema = {}
            
            perm = self.permissions.get(name, "low")
            
            return {
                "name": name,
                "description": input_schema.get("description", f"Execution module for {name}."),
                "input_schema": input_schema,
                "output_schema": output_schema,
                "permission_level": perm,
                "health_status": "OK",
                "execution_timeout": timeout
            }
        except Exception as e:
            logger.error(f"Failed to generate metadata for tool '{name}': {e}")
            return {
                "name": name,
                "description": f"Execution module for {name}.",
                "input_schema": {},
                "output_schema": {},
                "permission_level": "low",
                "health_status": "DEGRADED",
                "execution_timeout": 5.0
            }

    def list_all_tools(self) -> List[Dict[str, Any]]:
        """List all structured tools available in VOID."""
        return [self.get_tool_metadata(name) for name in TOOL_REGISTRY.keys()]
