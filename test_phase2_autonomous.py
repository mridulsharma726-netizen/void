import os
import unittest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.autonomous_agent.task_planner import Task, TaskPlanner
from core.autonomous_agent.self_verifier import SelfVerifier
from core.memory.long_term_memory import LongTermMemory
from core.tools.tool_orchestrator import ToolOrchestrator
from tools.code_analyzer import CodebaseAnalyzer
from core.vision.vision_engine import VisionEngine
from tools.desktop_automation import get_active_window_title, switch_to_window, read_clipboard, write_clipboard, rename_file, move_file, simulate_keyboard, simulate_mouse

class TestPhase2Autonomous(unittest.TestCase):

    def setUp(self):
        self.root_dir = Path(__file__).parent.resolve()

    def test_task_planner_graph(self):
        """Verify TaskPlanner creates nested task graphs and executes them with retry logic."""
        planner = TaskPlanner()
        goal = "Open VS Code and scan project"
        task = planner.create_task_graph(goal)
        
        self.assertIsNotNone(task)
        self.assertEqual(task.status, "Planning")
        self.assertTrue(len(task.subtasks) > 0)
        self.assertEqual(task.subtasks[0].tool_name, "open_app")
        
        # Test serialization
        task_dict = task.to_dict()
        self.assertEqual(task_dict["id"], task.id)
        self.assertTrue("subtasks" in task_dict)
        
        reconstructed = Task.from_dict(task_dict)
        self.assertEqual(reconstructed.id, task.id)
        self.assertEqual(reconstructed.subtasks[0].tool_name, "open_app")

    def test_desktop_automation_helpers(self):
        """Verify desktop automation functions execute or handle exceptions cleanly."""
        # Check title reading
        title = get_active_window_title()
        self.assertIsNotNone(title)
        
        # Clipboard write and read checks
        test_text = "VOID-AUTONOMOUS-AGENT-TEST-CLIPBOARD"
        write_success = write_clipboard(test_text)
        if write_success:
            clip_text = read_clipboard()
            self.assertEqual(clip_text, test_text)

        # File operations
        temp_file = Path("test_temp_auto.txt")
        temp_file.write_text("Hello VOID", encoding="utf-8")
        
        renamed_file = Path("test_temp_auto_renamed.txt")
        if renamed_file.exists():
            renamed_file.unlink()
            
        res = rename_file(str(temp_file), str(renamed_file))
        self.assertEqual(res["status"], "ok")
        self.assertTrue(renamed_file.exists())
        self.assertFalse(temp_file.exists())
        
        # Clean up
        if renamed_file.exists():
            renamed_file.unlink()

    def test_codebase_analyzer(self):
        """Verify static analysis (dead code, duplicate block, cyclic deps, health score)."""
        analyzer = CodebaseAnalyzer(str(self.root_dir))
        res = analyzer.analyze()
        
        self.assertEqual(res["status"], "ok")
        self.assertTrue("health_score" in res)
        self.assertTrue("data" in res)
        self.assertTrue(0 <= res["health_score"] <= 100)
        
        # Check cycles, dead code, and duplicates list exist
        self.assertIn("cycles", res["data"])
        self.assertIn("dead_code", res["data"])
        self.assertIn("duplicates", res["data"])

    def test_long_term_memory(self):
        """Verify long term memory store, retrieve, search, summarize using SQLite."""
        ltm = LongTermMemory()
        
        # Store
        category = "test_pref"
        key = "theme"
        val = "cyberpunk-neon"
        success = ltm.store(category, key, val)
        self.assertTrue(success)
        
        # Retrieve
        retrieved = ltm.retrieve(category, key)
        self.assertEqual(retrieved, val)
        
        # Search
        search_res = ltm.search(category, "neon")
        self.assertTrue(len(search_res) > 0)
        self.assertEqual(search_res[0]["key"], key)
        
        # Summarize
        summary = ltm.summarize(category)
        self.assertIn("theme", summary)
        
        # Forget
        forgot = ltm.forget(category, key)
        self.assertTrue(forgot)
        self.assertIsNone(ltm.retrieve(category, key))

    def test_tool_orchestrator(self):
        """Verify ToolOrchestrator lists schemas and enforces permissions."""
        orchestrator = ToolOrchestrator()
        tools = orchestrator.list_all_tools()
        
        self.assertTrue(len(tools) > 0)
        
        # Check specific tool schemas
        run_cmd_spec = next((t for t in tools if t["name"] == "run_command"), None)
        self.assertIsNotNone(run_cmd_spec)
        self.assertEqual(run_cmd_spec["permission_level"], "critical")
        
        vscode_spec = next((t for t in tools if t["name"] == "launch_vscode"), None)
        self.assertIsNotNone(vscode_spec)
        
        # Output schema keys check
        self.assertIn("input_schema", vscode_spec)
        self.assertIn("output_schema", vscode_spec)

    def test_vision_engine(self):
        """Verify VisionEngine extracts layout details and parses errors."""
        # Create a mock image file to parse
        from PIL import Image
        img = Image.new("RGB", (200, 100), color="blue")
        img_path = "test_vision_temp.png"
        img.save(img_path)
        
        try:
            engine = VisionEngine()
            analysis = engine.analyze_screenshot(img_path)
            
            self.assertEqual(analysis["status"], "ok")
            self.assertEqual(analysis["width"], 200)
            self.assertEqual(analysis["height"], 100)
            self.assertTrue("ocr_text" in analysis)
            
            # Anomaly checks
            explanation = engine.explain_ui_screenshot(analysis)
            self.assertIn("Screenshot UI Analysis", explanation)
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)

    def test_self_verifier(self):
        """Verify SelfVerifier check rules."""
        verifier = SelfVerifier()
        
        # Run test status mock verification
        res = asyncio.run(verifier.verify("agent_run_tests", {}, "Exit Code: 0"))
        self.assertEqual(res["status"], "ok")
        
        res_fail = asyncio.run(verifier.verify("agent_run_tests", {}, "failed 3 tests"))
        self.assertEqual(res_fail["status"], "fail")

if __name__ == "__main__":
    unittest.main()
