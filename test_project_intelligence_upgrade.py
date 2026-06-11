"""
VOID Project Intelligence System Upgrade Tests
==============================================
Tests database migrations, extended project metadata, blocker detection, 
workspace state collection, and RAG context prompt enrichment.
"""

import sys
import os
import shutil
import tempfile
import unittest
import json
from pathlib import Path

# Add VOID root to path
VOID_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(VOID_ROOT))
sys.path.insert(0, str(VOID_ROOT / "server"))

from backend.memory_sqlite import (
    init_db,
    save_project,
    get_project,
    get_active_project,
    list_tracked_projects,
    update_project_field
)
from tools.project_intelligence import (
    detect_project_blockers,
    get_workspace_state,
    register_project,
    continue_where_left_off
)
from backend.llm_client import OllamaClient


class TestProjectIntelligenceUpgrade(unittest.TestCase):
    def setUp(self):
        # Ensure database is initialized
        init_db()
        
        # Create a temporary test project directory
        self.test_dir = tempfile.mkdtemp(prefix="void_test_project_")
        
        # 1. Create requirements.txt
        with open(os.path.join(self.test_dir, "requirements.txt"), "w", encoding="utf-8") as f:
            f.write("requests==2.32.5\n")
            
        # 2. Create main.py with various blockers
        code_content = """# Test python file
import os
import requests
import nonexistent_lib # Missing dependency

from core.missing_file import foo # Broken local import

def empty_stub():
    pass

def not_implemented_stub():
    \"\"\"This is a stub\"\"\"
    raise NotImplementedError

def active_function():
    print("This function is active")
    model_name = "gemini-1.0-pro" # Outdated model reference
    return model_name
"""
        with open(os.path.join(self.test_dir, "main.py"), "w", encoding="utf-8") as f:
            f.write(code_content)
            
        # Create core folder but NOT missing_file.py
        os.makedirs(os.path.join(self.test_dir, "core"), exist_ok=True)
        
    def tearDown(self):
        # Clean up temporary test directory
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass
        # Clean up database entries
        try:
            import sqlite3
            from backend.memory_sqlite import DB_FILE
            conn = sqlite3.connect(str(DB_FILE))
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tracked_projects WHERE project_id LIKE 'test_%'")
            cursor.execute("DELETE FROM project_files WHERE project_id LIKE 'test_%'")
            cursor.execute("DELETE FROM project_scan_history WHERE project_id LIKE 'test_%'")
            conn.commit()
            conn.close()
        except Exception:
            pass

    def test_database_migrations_and_project_fields(self):
        """Verify new columns are persisted and retrieved successfully in SQLite."""
        project_id = "test_proj_db_123"
        name = "TestProjectDB"
        path = self.test_dir
        
        # Save project with all fields
        goals = ["Implement authentication", "Optimize database indexing"]
        completed = ["Initialize repo", "Set up backend skeleton"]
        pending = ["Deploy to AWS", "Add unit tests"]
        bugs = ["Fix memory leak in STT module"]
        history = ["Initial commit on main", "Added memory manager"]
        
        success = save_project(
            project_id=project_id,
            name=name,
            path=path,
            purpose="Test purpose",
            architecture="MVC",
            technologies="['Python']",
            goals=json.dumps(goals),
            completed_modules=json.dumps(completed),
            pending_modules=json.dumps(pending),
            known_bugs=json.dumps(bugs),
            development_history=json.dumps(history)
        )
        
        self.assertTrue(success, "Failed to save project with new fields")
        
        # Retrieve project and verify fields
        proj = get_project(project_id)
        self.assertIsNotNone(proj, "Project not found in DB")
        self.assertEqual(proj["name"], name)
        self.assertEqual(proj["purpose"], "Test purpose")
        
        retrieved_goals = json.loads(proj["goals"])
        self.assertEqual(retrieved_goals, goals)
        
        retrieved_bugs = json.loads(proj["known_bugs"])
        self.assertEqual(retrieved_bugs, bugs)
        
        # Update a single field and verify
        new_goals = ["Updated goal 1"]
        update_success = update_project_field(project_id, "goals", json.dumps(new_goals))
        self.assertTrue(update_success, "Failed to update project field")
        
        proj = get_project(project_id)
        self.assertEqual(json.loads(proj["goals"]), new_goals)

    def test_blocker_detection(self):
        """Verify blocker engine flags empty stubs, outdated APIs, and missing dependencies."""
        blockers = detect_project_blockers(self.test_dir)
        
        # Verify blockers categories and details
        categories = [b["category"] for b in blockers]
        messages = [b["message"] for b in blockers]
        
        # 1. Missing dependency: nonexistent_lib
        self.assertIn("Missing Dependency", categories)
        self.assertTrue(any("nonexistent_lib" in msg for msg in messages))
        
        # 2. Broken local import: core.missing_file
        self.assertIn("Broken Import", categories)
        self.assertTrue(any("core.missing_file" in msg for msg in messages))
        
        # 3. Empty stub functions
        self.assertIn("Missing Implementation", categories)
        self.assertTrue(any("empty_stub" in msg for msg in messages))
        self.assertTrue(any("not_implemented_stub" in msg for msg in messages))
        
        # 4. Outdated Gemini API reference
        self.assertIn("Outdated API Reference", categories)
        self.assertTrue(any("gemini-1.0" in msg for msg in messages))

    def test_workspace_state(self):
        """Verify workspace state correctly resolves active branch and modified files."""
        state = get_workspace_state(self.test_dir)
        
        self.assertEqual(state["active_project_folder"], self.test_dir)
        self.assertIn("current_git_branch", state)
        self.assertIn("vscode_workspace", state)
        self.assertIn("recently_modified_files", state)

    def test_rag_context_enrichment(self):
        """Verify build_context_prompt injects project context when keywords are present."""
        client = OllamaClient()
        
        # 1. Test when project keyword is queried but database is empty
        # First let's query the prompt without any active project in the DB
        # To make sure we test fallback safety, let's remove any projects
        import sqlite3
        from backend.memory_sqlite import DB_FILE
        conn = sqlite3.connect(str(DB_FILE))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tracked_projects")
        conn.commit()
        conn.close()
        
        prompt_no_project = client.build_context_prompt("which files handle authentication")
        self.assertIn("No active project is currently scanned or tracked.", prompt_no_project)
        self.assertIn("you MUST say exactly: 'I do not have enough project data to determine that.'", prompt_no_project)
        
        # 2. Test when project is tracked and active
        project_id = "test_active_proj_99"
        save_project(
            project_id=project_id,
            name="ActiveTestProj",
            path=self.test_dir,
            purpose="Enrichment verification",
            architecture="Microservices",
            technologies="['Python', 'FASTAPI']",
            features_completed="['User Login']",
            features_planned="['OAuth Integration']",
            blockers="['Pending AWS setup']"
        )
        
        # We verify that it resolves as active project because it's the only one scanned
        prompt_with_project = client.build_context_prompt("what is the project completion percentage?")
        self.assertIn("[ACTIVE PROJECT INTELLIGENCE]", prompt_with_project)
        self.assertIn("Project Name: ActiveTestProj", prompt_with_project)
        self.assertIn("Purpose: Enrichment verification", prompt_with_project)
        self.assertIn("Safety Rules for Project Q&A:", prompt_with_project)


if __name__ == "__main__":
    unittest.main()
