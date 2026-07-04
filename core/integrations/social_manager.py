import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from tools.academic_progress import get_connection

class SocialManager:
    def __init__(self):
        self.init_social_db()

    def init_social_db(self):
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS social_queue (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        platform TEXT NOT NULL,
                        content TEXT NOT NULL,
                        scheduled_time TEXT NOT NULL,
                        status TEXT DEFAULT 'pending'
                    )
                """)
                conn.commit()
        except Exception:
            pass

    def schedule_post(self, platform: str, content: str, scheduled_time: str = None) -> Dict[str, Any]:
        """
        Add a post draft to the social media scheduler queue.
        """
        if not scheduled_time:
            scheduled_time = datetime.now().isoformat()
            
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO social_queue (platform, content, scheduled_time, status) VALUES (?, ?, ?, 'pending')",
                    (platform, content, scheduled_time)
                )
                conn.commit()
            return {"status": "ok", "message": f"Successfully saved draft for {platform}."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_queued_posts(self) -> Dict[str, Any]:
        """
        List all pending and executed scheduled posts.
        """
        try:
            with get_connection() as conn:
                cursor = conn.execute("SELECT id, platform, content, scheduled_time, status FROM social_queue ORDER BY id DESC")
                posts = [
                    {
                        "id": r[0],
                        "platform": r[1],
                        "content": r[2],
                        "scheduled_time": r[3],
                        "status": r[4]
                    }
                    for r in cursor.fetchall()
                ]
            return {"status": "ok", "posts": posts}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def execute_post(self, post_id: int) -> Dict[str, Any]:
        """
        Simulate/Trigger execution of a scheduled post.
        """
        try:
            with get_connection() as conn:
                conn.execute("UPDATE social_queue SET status = 'posted' WHERE id = ?", (post_id,))
                conn.commit()
            return {"status": "ok", "message": f"Post {post_id} draft marked as posted in your queue."}
        except Exception as e:
            return {"status": "error", "message": str(e)}
