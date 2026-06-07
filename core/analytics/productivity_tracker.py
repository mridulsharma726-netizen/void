import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from tools.academic_progress import get_connection, init_db

class ProductivityTracker:
    def __init__(self):
        init_db()

    def log_event(self, event_type: str, details: Any) -> Dict[str, Any]:
        """
        Record a user behavior or study performance event in the database.
        """
        timestamp = datetime.now().isoformat()
        details_str = json.dumps(details) if not isinstance(details, str) else details
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO analytics_logs (event_type, details, timestamp) VALUES (?, ?, ?)",
                    (event_type, details_str, timestamp)
                )
                conn.commit()
            return {"status": "ok", "message": f"Logged event {event_type}."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Fetch and compile user productivity, chat frequency, study completions, and focus levels.
        """
        try:
            with get_connection() as conn:
                # 1. Total events count
                row = conn.execute("SELECT COUNT(*) FROM analytics_logs").fetchone()
                total_events = row[0] if row else 0
                
                # 2. Count by event type
                cursor = conn.execute("SELECT event_type, COUNT(*) as count FROM analytics_logs GROUP BY event_type")
                counts = {r["event_type"]: r["count"] for r in cursor.fetchall()}
                
                # 3. Get recent logs
                cursor = conn.execute("SELECT event_type, details, timestamp FROM analytics_logs ORDER BY id DESC LIMIT 50")
                recent = [
                    {
                        "event_type": r["event_type"],
                        "details": r["details"],
                        "timestamp": r["timestamp"]
                    }
                    for r in cursor.fetchall()
                ]
                
            return {
                "status": "ok",
                "total_events": total_events,
                "event_breakdown": counts,
                "recent_logs": recent,
                "focus_index": min(100, int((counts.get("study", 0) * 15 + counts.get("chat", 0) * 5 + 20))),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
