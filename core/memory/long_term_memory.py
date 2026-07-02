import os
import sqlite3
import logging
from typing import Dict, Any, List, Optional
from server.backend.memory_sqlite import DB_FILE, init_db

logger = logging.getLogger("void.long_term_memory")

class LongTermMemory:
    def __init__(self):
        init_db()
        self._init_ltm_table()

    def _init_ltm_table(self):
        try:
            conn = sqlite3.connect(str(DB_FILE))
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS long_term_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    val TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(category, key)
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize long term memory table: {e}")

    def store(self, category: str, key: str, value: str) -> bool:
        """Store or insert a long-term memory fact."""
        try:
            conn = sqlite3.connect(str(DB_FILE))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO long_term_memories (category, key, val)
                VALUES (?, ?, ?)
                ON CONFLICT(category, key) DO UPDATE SET val=excluded.val, timestamp=CURRENT_TIMESTAMP
            """, (category.lower().strip(), key.lower().strip(), value.strip()))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Store memory failed: {e}")
            return False

    def retrieve(self, category: str, key: str) -> Optional[str]:
        """Retrieve a specific long-term memory value."""
        try:
            conn = sqlite3.connect(str(DB_FILE))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT val FROM long_term_memories 
                WHERE category = ? AND key = ?
            """, (category.lower().strip(), key.lower().strip()))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception as e:
            logger.error(f"Retrieve memory failed: {e}")
            return None

    def update(self, category: str, key: str, value: str) -> bool:
        """Update an existing long-term memory."""
        return self.store(category, key, value)

    def forget(self, category: str, key: str) -> bool:
        """Remove a long-term memory."""
        try:
            conn = sqlite3.connect(str(DB_FILE))
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM long_term_memories 
                WHERE category = ? AND key = ?
            """, (category.lower().strip(), key.lower().strip()))
            rows_deleted = cursor.rowcount
            conn.commit()
            conn.close()
            return rows_deleted > 0
        except Exception as e:
            logger.error(f"Forget memory failed: {e}")
            return False

    def search(self, category: str, query: str) -> List[Dict[str, Any]]:
        """Search long-term memories in a category matching a query."""
        try:
            conn = sqlite3.connect(str(DB_FILE))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT key, val, timestamp FROM long_term_memories 
                WHERE category = ? AND (key LIKE ? OR val LIKE ?)
            """, (category.lower().strip(), f"%{query}%", f"%{query}%"))
            rows = cursor.fetchall()
            conn.close()
            return [{"key": r[0], "val": r[1], "timestamp": r[2]} for r in rows]
        except Exception as e:
            logger.error(f"Search memory failed: {e}")
            return []

    def summarize(self, category: str) -> str:
        """Generate a summary string of all memories within a category."""
        try:
            conn = sqlite3.connect(str(DB_FILE))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT key, val FROM long_term_memories WHERE category = ?
            """, (category.lower().strip(),))
            rows = cursor.fetchall()
            conn.close()
            if not rows:
                return f"No memories registered under category '{category}', Sir."
            items = [f"- {r[0]}: {r[1]}" for r in rows]
            return f"Memory Bank [{category.upper()}], Sir:\n" + "\n".join(items)
        except Exception as e:
            return f"Failed to summarize memory: {e}"
