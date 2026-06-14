import unittest
import os
import sqlite3
from pathlib import Path
from datetime import date, timedelta

# Mock the database filepath in memory_sqlite
import server.backend.memory_sqlite as mem_db

TEST_DB_FILE = Path(__file__).parent / "memory" / "data" / "test_memory.db"

class TestGamification(unittest.TestCase):
    def setUp(self):
        # Point memory_sqlite to test DB
        self.original_db = mem_db.DB_FILE
        mem_db.DB_FILE = TEST_DB_FILE
        
        # Ensure test DB directory exists and clean test DB if exists
        TEST_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        if TEST_DB_FILE.exists():
            try:
                TEST_DB_FILE.unlink()
            except Exception:
                pass
                
        # Initialize tables
        mem_db._DB_INITIALIZED = False
        mem_db.init_db()

    def tearDown(self):
        # Restore original DB path
        mem_db.DB_FILE = self.original_db
        if TEST_DB_FILE.exists():
            try:
                TEST_DB_FILE.unlink()
            except Exception:
                pass

    def test_xp_accumulation(self):
        # Default XP and level
        xp_info = mem_db.get_xp()
        self.assertEqual(xp_info["points"], 0)
        self.assertEqual(xp_info["level"], 1)
        
        # Add 50 XP
        res = mem_db.add_xp(50)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["points"], 50)
        self.assertEqual(res["level"], 1)
        self.assertFalse(res["leveled_up"])
        
        # Add another 60 XP -> total 110 XP (Level 2)
        res = mem_db.add_xp(60)
        self.assertEqual(res["points"], 110)
        self.assertEqual(res["level"], 2)
        self.assertTrue(res["leveled_up"])
        
        # Fetch again
        xp_info = mem_db.get_xp()
        self.assertEqual(xp_info["points"], 110)
        self.assertEqual(xp_info["level"], 2)

    def test_achievements(self):
        # Check no achievements at start
        achievements = mem_db.get_achievements()
        self.assertEqual(len(achievements), 0)
        
        # Award achievement
        success = mem_db.add_achievement("first_bug", "Squashed First Bug")
        self.assertTrue(success)
        
        # Verify
        achievements = mem_db.get_achievements()
        self.assertEqual(len(achievements), 1)
        self.assertEqual(achievements[0]["badge_id"], "first_bug")
        self.assertEqual(achievements[0]["title"], "Squashed First Bug")

    def test_learning_streaks(self):
        subject = "python_ast"
        
        # Start streak
        res = mem_db.update_streak(subject)
        self.assertEqual(res["streak_count"], 1)
        self.assertEqual(res["status"], "started")
        
        # Same day update should not change count
        res = mem_db.update_streak(subject)
        self.assertEqual(res["streak_count"], 1)
        self.assertEqual(res["status"], "active")
        
        # We need to test continuation and decay cooling bounds.
        # Let's check with direct database update to simulate yesterday and older date.
        conn = sqlite3.connect(str(TEST_DB_FILE))
        cursor = conn.cursor()
        
        # Simulate yesterday
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        cursor.execute("UPDATE learning_streaks SET last_active_date = ? WHERE subject_id = ?", (yesterday_str, subject))
        conn.commit()
        conn.close()
        
        # Update streak again
        res = mem_db.update_streak(subject)
        self.assertEqual(res["streak_count"], 2)
        self.assertEqual(res["status"], "incremented")
        
        # Simulate 3 days ago (decayed/expired streak)
        three_days_ago_str = (date.today() - timedelta(days=3)).isoformat()
        conn = sqlite3.connect(str(TEST_DB_FILE))
        cursor = conn.cursor()
        cursor.execute("UPDATE learning_streaks SET last_active_date = ? WHERE subject_id = ?", (three_days_ago_str, subject))
        conn.commit()
        conn.close()
        
        # Update streak again -> should reset count to 1
        res = mem_db.update_streak(subject)
        self.assertEqual(res["streak_count"], 1)
        self.assertEqual(res["status"], "reset")

if __name__ == "__main__":
    unittest.main()
