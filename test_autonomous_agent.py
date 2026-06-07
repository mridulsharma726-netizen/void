import os
import json
import unittest
from pathlib import Path

from core.autonomous_agent.scanner import ProjectScanner
from core.autonomous_agent.memory import CodebaseMemory
from core.autonomous_agent.lang_detect import detect_language
from core.autonomous_agent.safety_system import AgentSafetySystem
from server.backend.safety_guard import SafetyGuard

ROOT_DIR = Path(__file__).parent.resolve()

class TestAutonomousAgent(unittest.TestCase):
    def test_language_detection(self):
        """Verify that language detection correctly identifies common extensions and shebangs."""
        self.assertEqual(detect_language("test.py"), "Python")
        self.assertEqual(detect_language("test.js"), "JavaScript")
        self.assertEqual(detect_language("test.ts"), "TypeScript")
        self.assertEqual(detect_language("test.cpp"), "C++")
        self.assertEqual(detect_language("test.go"), "Go")
        self.assertEqual(detect_language("test.rs"), "Rust")
        self.assertEqual(detect_language("test.html"), "HTML")
        self.assertEqual(detect_language("test.css"), "CSS")
        self.assertEqual(detect_language("test.sh"), "Bash")

    def test_technology_scan(self):
        """Verify the project scanner traverses directory and detects frameworks."""
        scanner = ProjectScanner(str(ROOT_DIR))
        res = scanner.scan()
        
        self.assertIn("root", res)
        self.assertIn("files", res)
        self.assertTrue(isinstance(res["files"], list))
        
        # Check that it detected FastAPI or Electron from requirements.txt or package.json
        frameworks = res.get("frameworks", [])
        self.assertTrue(isinstance(frameworks, list))
        self.assertTrue("FastAPI" in frameworks or "Electron" in frameworks)

    def test_safety_system_limits(self):
        """Verify safety system behavior across L1-L4 permission levels."""
        safety = AgentSafetySystem()
        guard = SafetyGuard()
        
        # Save original permission level
        if hasattr(guard, "load_config"):
            guard.load_config()
        original_level = guard.permission_level

        try:
            # 1. Level 1.0 (View Only)
            guard.set_permission_level(1.0)
            file_check = safety.check_file_action("write", "dummy.py")
            self.assertFalse(file_check["allowed"])
            
            cmd_check = safety.check_command_action("pytest")
            self.assertFalse(cmd_check["allowed"])

            # 2. Level 2.0 (Assisted)
            guard.set_permission_level(2.0)
            file_check = safety.check_file_action("write", "dummy.py")
            self.assertTrue(file_check["allowed"])
            self.assertTrue(file_check["requires_approval"])

            # 3. Level 3.5 (Developer Session)
            guard.set_permission_level(3.5)
            # Whitelisted command should run automatically
            cmd_check = safety.check_command_action("python --version")
            self.assertTrue(cmd_check["allowed"])
            self.assertFalse(cmd_check["requires_approval"])
            
            # Non-whitelisted command should require confirmation
            cmd_check = safety.check_command_action("notepad")
            self.assertTrue(cmd_check["allowed"])
            self.assertTrue(cmd_check["requires_approval"])
            
            # Destructive command should be blocked
            cmd_check = safety.check_command_action("rmdir /s /q Windows")
            self.assertFalse(cmd_check["allowed"])

            # 4. Level 4.0 (Automation Mode)
            guard.set_permission_level(4.0)
            cmd_check = safety.check_command_action("notepad")
            self.assertTrue(cmd_check["allowed"])
            self.assertFalse(cmd_check["requires_approval"])
            
        finally:
            # Reset to original level
            guard.set_permission_level(original_level)

    def test_incremental_memory(self):
        """Verify memory manager tracks file modifications incrementally using hashes."""
        import tempfile
        import shutil
        
        # Create a temp directory
        temp_dir = tempfile.mkdtemp()
        try:
            project_dir = Path(temp_dir)
            
            # Initialize codebase memory
            memory = CodebaseMemory(str(project_dir))
            
            # Create dummy file
            dummy_file = project_dir / "foo.py"
            with open(dummy_file, "w", encoding="utf-8") as f:
                f.write("print('hello')")
            
            rel_path = "foo.py"
            
            # Update file state
            self.assertTrue(memory.update_file_state(rel_path))
            self.assertFalse(memory.has_file_changed(rel_path))
            
            # Modify file
            with open(dummy_file, "w", encoding="utf-8") as f:
                f.write("print('hello world')")
            self.assertTrue(memory.has_file_changed(rel_path))
            
            # Update state again
            self.assertTrue(memory.update_file_state(rel_path))
            self.assertFalse(memory.has_file_changed(rel_path))
        finally:
            # Clean up temp dir
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    unittest.main()
