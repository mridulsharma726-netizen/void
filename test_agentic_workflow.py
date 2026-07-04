import unittest
import os
import shutil
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.autonomous_agent.agent import AutonomousAgent
from core.autonomous_agent.sandbox_validator import SandboxValidator
from workflows.workflow_engine import WorkflowEngine

class TestAgenticWorkflow(unittest.TestCase):
    def setUp(self):
        self.workspace_dir = Path(__file__).parent.resolve()
        self.agent = AutonomousAgent(str(self.workspace_dir))
        self.engine = WorkflowEngine(tools={})

    def test_sandbox_validator(self):
        validator = SandboxValidator(str(self.workspace_dir))
        
        # Test safe command
        safe_res = validator.validate_command("python test_system.py")
        self.assertTrue(safe_res["allowed"])
        
        # Test banned executable
        banned_exe_res = validator.validate_command("shutdown -r now")
        self.assertFalse(banned_exe_res["allowed"])
        self.assertIn("prohibited", banned_exe_res["reason"].lower())
        
        # Test banned pattern (rm -rf / etc)
        dangerous_pattern_res = validator.validate_command("rm -rf /")
        self.assertFalse(dangerous_pattern_res["allowed"])
        self.assertIn("banned command pattern", dangerous_pattern_res["reason"].lower())
        
        # Test directory traversal
        traversal_res = validator.validate_command("cat ../../../some_file.txt")
        self.assertFalse(traversal_res["allowed"])
        self.assertIn("directory traversal warning", traversal_res["reason"].lower())

    def test_workflow_engine_high_risk_detection(self):
        # High risk action delete_file
        context_high = {"description": "rm -rf some_file.py", "previous_results": {}}
        res = self.engine._execute_action("execute_repair", context_high)
        self.assertEqual(res.get("status"), "pending_confirmation")
        self.assertIn("high-risk", res.get("message"))
        
        # Safe action
        context_safe = {"description": "analyze_file_safe.py", "previous_results": {}}
        # Mock analyze file
        with patch.object(self.engine, "_action_analyze_file") as mock_analyze:
            mock_analyze.return_value = {"success": True, "message": "Analyzed successfully"}
            res_safe = self.engine._execute_action("analyze_file", context_safe)
            self.assertTrue(res_safe.get("success"))

    def test_workflow_engine_async_pending_confirmation(self):
        # Run async step that needs confirmation
        step = {
            "id": "1",
            "action": "execute_repair",
            "description": "rm -rf some_file.py",
            "status": "pending",
            "retries": 0,
            "depends_on": []
        }
        
        # We need to run this in asyncio
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                self.engine._execute_single_step_async(step, "test_workflow_123", [step])
            )
            self.assertEqual(result.get("status"), "pending_confirmation")
            self.assertEqual(step["status"], "pending_confirmation")
        finally:
            loop.close()

    def test_agent_git_backup_triggers(self):
        # 1. Single file edit plan -> Should NOT trigger git backup
        single_edit_plan = [
            {"type": "edit_file", "path": "temp_edit.py", "content": "print('hello')"}
        ]
        
        # Mock git repo to return True and mock create_backup_branch
        self.agent.git.is_git_repo = MagicMock(return_value=True)
        self.agent.git.status = MagicMock(return_value="")
        self.agent.git.create_backup_branch = MagicMock(return_value="void-backup-test")
        
        # Mock file_engine write
        self.agent.file_engine.write_file = MagicMock(return_value={"status": "ok"})
        
        # Mock safety check to bypass confirmation gate during test
        self.agent.safety.check_file_action = MagicMock(return_value={"allowed": True, "requires_approval": False})
        
        loop = asyncio.new_event_loop()
        try:
            res = loop.run_until_complete(self.agent.execute_plan(single_edit_plan))
            self.assertEqual(res["status"], "ok")
            # Create backup should NOT be called since it's a single file rewrite
            self.agent.git.create_backup_branch.assert_not_called()
            
            # 2. Multi-file edit plan -> Should trigger git backup
            self.agent.git.create_backup_branch.reset_mock()
            multi_edit_plan = [
                {"type": "edit_file", "path": "temp_edit1.py", "content": "print('hello 1')"},
                {"type": "edit_file", "path": "temp_edit2.py", "content": "print('hello 2')"}
            ]
            res_multi = loop.run_until_complete(self.agent.execute_plan(multi_edit_plan))
            self.assertEqual(res_multi["status"], "ok")
            # Create backup should be called since it is a multi-file rewrite
            self.agent.git.create_backup_branch.assert_called_once()
        finally:
            loop.close()

if __name__ == "__main__":
    unittest.main()
