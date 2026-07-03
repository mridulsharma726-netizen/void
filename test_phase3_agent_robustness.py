import os
import json
import unittest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from core.autonomous_agent.agent import AutonomousAgent
from core.autonomous_agent.file_engine import AgentFileEngine
from core.autonomous_agent.terminal_engine import AgentTerminalEngine
from core.autonomous_agent.git_integration import AgentGitIntegration

ROOT_DIR = Path(__file__).parent.resolve()

class TestPhase3AgentRobustness(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.agent = AutonomousAgent(str(ROOT_DIR))
        # Ensure it has a mock LLM client
        self.agent.llm = AsyncMock()

    @patch('core.autonomous_agent.agent.logger')
    async def test_llm_loud_failure_connection_refused(self, mock_logger):
        """Verify _call_llm logs a loud error and raises RuntimeError when connection is refused."""
        self.agent.llm.chat.side_effect = ConnectionRefusedError("Connection refused")
        
        with self.assertRaises(RuntimeError) as ctx:
            await self.agent._call_llm("test prompt")
            
        self.assertIn("Ollama failure", str(ctx.exception))
        mock_logger.error.assert_called()
        args, kwargs = mock_logger.error.call_args
        self.assertIn("LLM Call Failed", args[0])

    @patch('core.autonomous_agent.agent.logger')
    async def test_llm_loud_failure_timeout(self, mock_logger):
        """Verify _call_llm logs a loud error and raises RuntimeError when connection times out."""
        self.agent.llm.chat.side_effect = asyncio.TimeoutError("Timeout")
        
        with self.assertRaises(RuntimeError) as ctx:
            await self.agent._call_llm("test prompt")
            
        self.assertIn("Ollama failure", str(ctx.exception))
        mock_logger.error.assert_called()

    @patch('core.autonomous_agent.agent.logger')
    async def test_llm_degraded_mode_mock(self, mock_logger):
        """Verify that a standalone/mock client is logged as degraded mode."""
        class OllamaClient:
            async def chat(self, history, prompt):
                return "[DEGRADED MODE] Mock standalone"
        
        self.agent.llm = OllamaClient()
        resp = await self.agent._call_llm("test prompt")
        self.assertIn("[DEGRADED MODE]", resp)
        mock_logger.warning.assert_called_with("[AGENT] [DEGRADED MODE] Calling standalone fallback client.")

    async def test_generate_plan_malformed_json(self):
        """Verify generate_plan raises RuntimeError when LLM returns invalid JSON."""
        self.agent.llm.chat.return_value = "invalid-json-text"
        
        with self.assertRaises(RuntimeError) as ctx:
            await self.agent.generate_plan("make a file", ["test.py"])
            
        self.assertIn("Plan generation failed", str(ctx.exception))

    async def test_generate_plan_not_a_list(self):
        """Verify generate_plan raises RuntimeError when LLM returns JSON that is not a list."""
        self.agent.llm.chat.return_value = '{"type": "edit_file"}'
        
        with self.assertRaises(RuntimeError) as ctx:
            await self.agent.generate_plan("make a file", ["test.py"])
            
        self.assertIn("Plan generation failed", str(ctx.exception))

    @patch('backend.fs_tools.request_approval', new_callable=AsyncMock)
    async def test_execute_plan_write_approval_approved(self, mock_approve):
        """Verify that file write steps prompt the user and proceed when approved."""
        mock_approve.return_value = True
        
        plan = [{"type": "edit_file", "path": "scratch/test_temp.txt", "content": "hello world"}]
        
        # Mock safety check to require approval
        self.agent.safety.check_file_action = MagicMock(return_value={"allowed": True, "requires_approval": True, "reason": "L3"})
        self.agent.file_engine.write_file = MagicMock(return_value={"status": "ok"})
        self.agent.git.is_git_repo = MagicMock(return_value=False)
        
        res = await self.agent.execute_plan(plan)
        
        self.assertEqual(res["status"], "ok")
        mock_approve.assert_called_once()
        self.agent.file_engine.write_file.assert_called_once_with("scratch/test_temp.txt", "hello world", bypass_safety=True)

    @patch('backend.fs_tools.request_approval', new_callable=AsyncMock)
    async def test_execute_plan_write_approval_denied(self, mock_approve):
        """Verify that file write steps halt execution and return error when denied."""
        mock_approve.return_value = False
        
        plan = [{"type": "edit_file", "path": "scratch/test_temp.txt", "content": "hello world"}]
        
        self.agent.safety.check_file_action = MagicMock(return_value={"allowed": True, "requires_approval": True, "reason": "L3"})
        self.agent.file_engine.write_file = MagicMock()
        self.agent.git.is_git_repo = MagicMock(return_value=False)
        
        res = await self.agent.execute_plan(plan)
        
        self.assertEqual(res["status"], "error")
        self.assertIn("User denied file write approval", res["message"])
        mock_approve.assert_called_once()
        self.agent.file_engine.write_file.assert_not_called()

    @patch('backend.fs_tools.request_approval', new_callable=AsyncMock)
    async def test_execute_plan_command_approval_outside_allowlist(self, mock_approve):
        """Verify that terminal commands outside the allowlist trigger confirmation even if permitted by safety."""
        mock_approve.return_value = True
        
        plan = [{"type": "run_command", "command": "curl http://example.com"}]
        
        # safety check allows it but requires_approval is False (e.g. L3.5 or L4, but it is outside Phase 1 allowlist)
        self.agent.safety.check_command_action = MagicMock(return_value={"allowed": True, "requires_approval": False, "reason": "Allowed"})
        self.agent.terminal_engine.execute_command = AsyncMock(return_value={"status": "ok"})
        self.agent.git.is_git_repo = MagicMock(return_value=False)
        
        res = await self.agent.execute_plan(plan)
        
        self.assertEqual(res["status"], "ok")
        mock_approve.assert_called_once()
        self.agent.terminal_engine.execute_command.assert_called_once_with("curl http://example.com", bypass_safety=True)

    @patch('backend.fs_tools.request_approval', new_callable=AsyncMock)
    async def test_git_commit_gate_and_conventions(self, mock_approve):
        """Verify that git commit triggers the approval flow and enforces agent formatting."""
        mock_approve.return_value = True
        
        # Mock git status to return changes, so commit is triggered
        self.agent.git.is_git_repo = MagicMock(return_value=True)
        self.agent.git.status = MagicMock(return_value="M test.py")
        self.agent.git.add = MagicMock()
        self.agent.git.commit = AsyncMock(return_value="Committed")
        
        res = await self.agent.execute_plan([])
        
        self.assertEqual(res["status"], "ok")
        self.agent.git.commit.assert_called_once_with("VOID Auto-Commit: Autonomous Agent code modifications applied.")

if __name__ == '__main__':
    unittest.main()
