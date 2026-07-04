import pytest
from core.tools.tool_orchestrator import ToolOrchestrator
from core.brain import enable_developer_mode, disable_developer_mode

def test_enforce_permission_blocks_critical_without_dev_mode():
    """Verify that a critical tool is blocked if developer mode is False."""
    orchestrator = ToolOrchestrator()
    
    # Disable developer mode for testing
    disable_developer_mode()
    
    try:
        with pytest.raises(PermissionError, match="Action Denied: Tool 'run_command' requires Developer Mode"):
            orchestrator.enforce_permission("run_command")
    finally:
        # Restore default state just in case
        enable_developer_mode()

def test_enforce_permission_allows_critical_with_dev_mode():
    """Verify that a critical tool is allowed if developer mode is True."""
    orchestrator = ToolOrchestrator()
    
    # Enable developer mode for testing
    enable_developer_mode()
    
    try:
        orchestrator.enforce_permission("run_command")
    except PermissionError:
        pytest.fail("enforce_permission raised PermissionError unexpectedly when developer mode is enabled.")

def test_enforce_permission_allows_low_risk_tool():
    """Verify that a low risk tool is allowed even if developer mode is False."""
    orchestrator = ToolOrchestrator()
    
    # Disable developer mode for testing
    disable_developer_mode()
    
    try:
        orchestrator.enforce_permission("time")
    except PermissionError:
        pytest.fail("enforce_permission raised PermissionError unexpectedly for a low risk tool.")
    finally:
        enable_developer_mode()
