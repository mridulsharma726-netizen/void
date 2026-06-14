"""
VOID SQLite Vector & Semantic Memory Database Backend
====================================================

Features:
- Structured SQLite database persisting facts, preferences, and conversations.
- On-the-fly local semantic retrieval using Ollama's embeddings.
- Cosine similarity ranking merged with recency decay and importance weights.
"""

import os
import json
import time
import math
import sqlite3
import logging
import requests
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("void.memory_sqlite")

DB_DIR = Path(__file__).parent.parent.parent / "memory" / "data"
DB_FILE = DB_DIR / "memory.db"

OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"
OLLAMA_EMBED_FALLBACK = "http://127.0.0.1:11434/api/embed"

_DB_INITIALIZED = False
_EMBEDDING_CACHE = {}

def get_ollama_model() -> str:
    """Helper to detect currently active Ollama model or default to llama3.2:3b."""
    try:
        from server.backend.llm_client import OllamaClient
        client = OllamaClient()
        return client.model
    except Exception:
        return "llama3.2:3b"

def init_db():
    """Create structural SQLite database tables for persistence."""
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    
    # 1. Facts table (with embeddings and importance)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact TEXT NOT NULL UNIQUE,
            importance INTEGER DEFAULT 5,
            embedding TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 2. Preferences table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS preferences (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 3. Conversation history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 4. Personal Profile schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profile_data (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 5. Achievements table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            badge_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            earned_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 6. User XP table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_xp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            points INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1
        )
    """)
    
    # 7. Learning Streaks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_streaks (
            subject_id TEXT PRIMARY KEY,
            streak_count INTEGER DEFAULT 0,
            last_active_date TEXT
        )
    """)
    
    # 8. Meetings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            meeting_id TEXT PRIMARY KEY,
            title TEXT,
            date_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            participants TEXT,
            transcript TEXT,
            structured_notes TEXT,
            summary TEXT
        )
    """)
    
    # 9. Action Items table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS action_items (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id TEXT,
            description TEXT NOT NULL,
            owner TEXT,
            deadline TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY(meeting_id) REFERENCES meetings(meeting_id)
        )
    """)
    
    # 10. Tracked Projects table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracked_projects (
            project_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_scan_date DATETIME,
            purpose TEXT,
            architecture TEXT,
            technologies TEXT,
            features_completed TEXT DEFAULT '[]',
            features_progress TEXT DEFAULT '[]',
            features_planned TEXT DEFAULT '[]',
            blockers TEXT DEFAULT '[]',
            recent_changes TEXT DEFAULT '[]',
            folder_structure TEXT,
            goals TEXT DEFAULT '',
            completed_modules TEXT DEFAULT '',
            pending_modules TEXT DEFAULT '',
            known_bugs TEXT DEFAULT '',
            development_history TEXT DEFAULT ''
        )
    """)
    
    # 11. Project Files table (for change detection)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_files (
            file_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            path TEXT NOT NULL,
            file_hash TEXT,
            summary TEXT,
            last_scanned DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES tracked_projects(project_id)
        )
    """)
    
    # 12. Project Scan History table (for change reports)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_scan_history (
            scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            scan_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            new_files TEXT DEFAULT '[]',
            modified_files TEXT DEFAULT '[]',
            deleted_files TEXT DEFAULT '[]',
            summary TEXT,
            FOREIGN KEY(project_id) REFERENCES tracked_projects(project_id)
        )
    """)
    
    # Migrate action_items: add project_id, source, priority columns if missing
    try:
        cursor.execute("PRAGMA table_info(action_items)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if "project_id" not in existing_cols:
            cursor.execute("ALTER TABLE action_items ADD COLUMN project_id TEXT DEFAULT ''")
        if "source" not in existing_cols:
            cursor.execute("ALTER TABLE action_items ADD COLUMN source TEXT DEFAULT 'meeting'")
        if "priority" not in existing_cols:
            cursor.execute("ALTER TABLE action_items ADD COLUMN priority TEXT DEFAULT 'normal'")
    except Exception as e:
        logger.warning(f"[SQLITE MEMORY] action_items migration note: {e}")

    # Migrate tracked_projects: add goals, completed_modules, pending_modules, known_bugs, development_history columns if missing
    try:
        cursor.execute("PRAGMA table_info(tracked_projects)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        for col in ["goals", "completed_modules", "pending_modules", "known_bugs", "development_history"]:
            if col not in existing_cols:
                cursor.execute(f"ALTER TABLE tracked_projects ADD COLUMN {col} TEXT DEFAULT ''")
    except Exception as e:
        logger.warning(f"[SQLITE MEMORY] tracked_projects migration note: {e}")
    
    # ----------------------------------------------------------------
    # REAL-TIME INTELLIGENCE UPGRADE — new tables (Phase 9)
    # ----------------------------------------------------------------

    # 13. Search History table — tracks every web/news search
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            query       TEXT    NOT NULL,
            intent      TEXT    DEFAULT 'web_search',
            source      TEXT    DEFAULT 'duckduckgo',
            result_count INTEGER DEFAULT 0,
            web_used    INTEGER DEFAULT 0,
            news_used   INTEGER DEFAULT 0,
            latency_ms  REAL    DEFAULT 0.0,
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 14. Build Decisions table — logs architecture/code-gen choices
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS build_decisions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project     TEXT    NOT NULL,
            decision    TEXT    NOT NULL,
            rationale   TEXT    DEFAULT '',
            tech_stack  TEXT    DEFAULT '',
            approved    INTEGER DEFAULT 0,
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 15. User Patterns table — aggregated intent analytics
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_patterns (
            intent      TEXT    PRIMARY KEY,
            count       INTEGER DEFAULT 1,
            last_used   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migrate: add search_history / build_decisions columns if DB existed before upgrade
    for table, col, col_def in [
        ("search_history", "latency_ms", "REAL DEFAULT 0.0"),
        ("build_decisions", "approved",  "INTEGER DEFAULT 0"),
    ]:
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            existing = {row[1] for row in cursor.fetchall()}
            if col not in existing:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
        except Exception as e:
            logger.warning(f"[SQLITE MEMORY] {table} migration note: {e}")

    # Ensure default row in user_xp
    cursor.execute("SELECT COUNT(*) FROM user_xp")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO user_xp (points, level) VALUES (0, 1)")
        
    conn.commit()
    conn.close()
    _DB_INITIALIZED = True
    logger.info(f"[SQLITE MEMORY] Database initialized at: {DB_FILE}")


# ---------------------------------------------------------------------------
# REAL-TIME INTELLIGENCE UPGRADE — helper functions (Phase 9)
# ---------------------------------------------------------------------------

def store_search(
    query: str,
    intent: str = "web_search",
    source: str = "duckduckgo",
    result_count: int = 0,
    web_used: bool = False,
    news_used: bool = False,
    latency_ms: float = 0.0,
) -> bool:
    """
    Log a web/news search to the search_history table.

    Args:
        query:        The search query text.
        intent:       The detected intent (e.g. 'web_search', 'news_query').
        source:       The search provider used ('duckduckgo', 'rss', 'both').
        result_count: Number of results returned.
        web_used:     Whether DuckDuckGo web search was used.
        news_used:    Whether RSS/DDG news was used.
        latency_ms:   Total fusion latency in milliseconds.

    Returns:
        True on success, False on error.
    """
    init_db()
    try:
        conn = sqlite3.connect(str(DB_FILE))
        conn.execute(
            """
            INSERT INTO search_history
                (query, intent, source, result_count, web_used, news_used, latency_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (query, intent, source, result_count,
             1 if web_used else 0,
             1 if news_used else 0,
             latency_ms),
        )
        conn.commit()
        conn.close()
        # Also update user_patterns
        _increment_user_pattern(intent)
        return True
    except Exception as e:
        logger.warning(f"[SQLITE MEMORY] store_search error: {e}")
        return False


def store_build_decision(
    project: str,
    decision: str,
    rationale: str = "",
    tech_stack: str = "",
    approved: bool = False,
) -> bool:
    """
    Log an architecture or code-generation decision to build_decisions.

    Args:
        project:    Project name or path.
        decision:   The decision made (e.g. 'Use FastAPI over Flask').
        rationale:  Why this decision was made.
        tech_stack: Comma-separated tech stack string.
        approved:   Whether the user approved this decision.

    Returns:
        True on success, False on error.
    """
    init_db()
    try:
        conn = sqlite3.connect(str(DB_FILE))
        conn.execute(
            """
            INSERT INTO build_decisions (project, decision, rationale, tech_stack, approved)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project, decision, rationale, tech_stack, 1 if approved else 0),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"[SQLITE MEMORY] store_build_decision error: {e}")
        return False


def get_user_patterns(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Return the most frequently used intents for personalisation.

    Returns:
        List of {intent, count, last_used} dicts ordered by frequency.
    """
    init_db()
    try:
        conn = sqlite3.connect(str(DB_FILE))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT intent, count, last_used FROM user_patterns "
            "ORDER BY count DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"[SQLITE MEMORY] get_user_patterns error: {e}")
        return []


def get_recent_searches(limit: int = 10) -> List[Dict[str, Any]]:
    """Return the most recent search history entries."""
    init_db()
    try:
        conn = sqlite3.connect(str(DB_FILE))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM search_history ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"[SQLITE MEMORY] get_recent_searches error: {e}")
        return []


def _increment_user_pattern(intent: str) -> None:
    """Internal helper: upsert intent frequency counter."""
    try:
        conn = sqlite3.connect(str(DB_FILE))
        conn.execute(
            """
            INSERT INTO user_patterns (intent, count, last_used) VALUES (?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(intent) DO UPDATE SET
                count    = count + 1,
                last_used = CURRENT_TIMESTAMP
            """,
            (intent,),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def set_profile_value(key: str, value: str) -> bool:

    """Store or update user profile details (goals, projects, skills)."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO profile_data (key, value, timestamp) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key, value)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"[SQLITE MEMORY ERROR] Failed storing profile key {key}: {e}")
        return False
    finally:
        conn.close()

def get_profile_value(key: str) -> Optional[str]:
    """Retrieve value of profile key."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT value FROM profile_data WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception:
        return None
    finally:
        conn.close()

def get_embedding(text: str) -> List[float]:
    """Generates embedding vector from local Ollama endpoint, with in-memory caching."""
    text_key = text.strip().lower() if text else ""
    if not text_key:
        return [0.0] * 128
    if text_key in _EMBEDDING_CACHE:
        return _EMBEDDING_CACHE[text_key]
        
    model = get_ollama_model()
    vector = None
    try:
        # Option 1: Classic embeddings API
        resp = requests.post(OLLAMA_EMBED_URL, json={"model": model, "prompt": text}, timeout=4.0)
        if resp.status_code == 200:
            vector = resp.json().get("embedding", [])
    except Exception:
        pass
        
    if not vector:
        try:
            # Option 2: Newer embed API
            resp = requests.post(OLLAMA_EMBED_FALLBACK, json={"model": model, "input": [text]}, timeout=4.0)
            if resp.status_code == 200:
                vectors = resp.json().get("embeddings", [])
                if vectors:
                    vector = vectors[0]
        except Exception:
            pass
            
    if vector:
        _EMBEDDING_CACHE[text_key] = vector
        return vector
        
    # Return placeholder small vector on failures
    return [0.0] * 128

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculates cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)

def add_fact(fact: str, importance: int = 5) -> bool:
    """Computes embedding and inserts a new fact into sqlite."""
    init_db()
    embedding_vector = get_embedding(fact)
    embedding_json = json.dumps(embedding_vector)
    
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO facts (fact, importance, embedding, timestamp) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (fact, importance, embedding_json)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"[SQLITE MEMORY ERROR] Failed storing fact: {e}")
        return False
    finally:
        conn.close()

def remove_fact(fact: str) -> bool:
    """Remove a fact by exact or substring match."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM facts WHERE fact LIKE ?", (fact,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        return False
    finally:
        conn.close()

def set_preference(key: str, value: str) -> bool:
    """Store or update user preference."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO preferences (key, value, timestamp) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key, value)
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def get_preference(key: str) -> Optional[str]:
    """Retrieve value of preference key."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT value FROM preferences WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception:
        return None
    finally:
        conn.close()

def add_history(role: str, content: str) -> bool:
    """Inserts a conversation turn."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO history (role, content, timestamp) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (role, content)
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def get_all_facts() -> List[str]:
    """Return all facts list."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT fact FROM facts ORDER BY timestamp DESC")
        return [row[0] for row in cursor.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()

def get_all_preferences() -> Dict[str, Any]:
    """Return all preferences."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT key, value FROM preferences")
        return {row[0]: row[1] for row in cursor.fetchall()}
    except Exception:
        return {}
    finally:
        conn.close()

def get_recent_history(limit: int = 50) -> List[Dict[str, str]]:
    """Retrieves recent conversation history."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT role, content FROM history ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        # Return in correct chronological order
        return [{"role": row[0], "content": row[1]} for row in reversed(rows)]
    except Exception:
        return []
    finally:
        conn.close()

def purge_all() -> bool:
    """Wipes all sqlite memory tables."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM facts")
        cursor.execute("DELETE FROM preferences")
        cursor.execute("DELETE FROM history")
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def query_semantic_facts(query: str, limit: int = 5) -> List[str]:
    """
    Core local Vector semantic search loop.
    Returns facts prioritized by: Cosine Similarity, Recency Decay, Importance Weights.
    """
    init_db()
    query_vector = get_embedding(query)
    if not query_vector:
        return get_all_facts()[:limit]
        
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    
    results = []
    try:
        cursor.execute("SELECT fact, importance, embedding, timestamp FROM facts")
        rows = cursor.fetchall()
        
        now = datetime.utcnow()
        
        for fact, importance, embedding_json, timestamp_str in rows:
            if not embedding_json:
                continue
                
            embedding_vector = json.loads(embedding_json)
            # 1. Cosine similarity
            sim = cosine_similarity(query_vector, embedding_vector)
            
            # 2. Recency Decay calculation (exponential decay over time)
            try:
                # Convert timestamps to float age
                dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                age_seconds = max(1.0, (now - dt).total_seconds())
            except Exception:
                age_seconds = 1.0
            # Lambda decay constant (decay slowly over days)
            lambda_decay = 1e-6
            decay = math.exp(-lambda_decay * age_seconds)
            
            # 3. Importance Weight (normalized 0.1 to 1.0)
            imp_weight = importance / 10.0
            
            # Hybrid Score formula: 0.5 * Similarity + 0.3 * Decay + 0.2 * Importance
            hybrid_score = (0.5 * sim) + (0.3 * decay) + (0.2 * imp_weight)
            
            results.append((fact, hybrid_score))
            
        # Sort results by hybrid score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in results[:limit]]
        
    except Exception as e:
        logger.error(f"[SQLITE SEMANTIC QUERY ERROR] {e}")
        return get_all_facts()[:limit]
    finally:
        conn.close()

# === GAMIFICATION HELPER FUNCTIONS ===

def add_xp(points: int) -> Dict[str, Any]:
    """Adds XP points, updates level, and returns the result."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        # Get current points & level
        cursor.execute("SELECT points, level FROM user_xp LIMIT 1")
        row = cursor.fetchone()
        if not row:
            # Fallback insertion
            cursor.execute("INSERT INTO user_xp (points, level) VALUES (0, 1)")
            current_points, current_level = 0, 1
        else:
            current_points, current_level = row[0], row[1]
            
        new_points = current_points + points
        # Every 100 XP is a level
        new_level = (new_points // 100) + 1
        leveled_up = new_level > current_level
        
        cursor.execute(
            "UPDATE user_xp SET points = ?, level = ? WHERE id = (SELECT id FROM user_xp LIMIT 1)",
            (new_points, new_level)
        )
        conn.commit()
        
        unlocked_roles = []
        if leveled_up:
            # Grant level-up achievements based on milestones
            milestones = {
                2: ("unlock_teacher", "Unlocked Personality: Teacher"),
                3: ("unlock_researcher", "Unlocked Personality: Researcher"),
                4: ("unlock_developer", "Unlocked Personality: Developer"),
                5: ("unlock_founder", "Unlocked Personality: Founder"),
                6: ("unlock_motivator", "Unlocked Personality: Motivator")
            }
            # We unlock all milestones that were passed
            for lvl in range(current_level + 1, new_level + 1):
                if lvl in milestones:
                    badge_id, title = milestones[lvl]
                    add_achievement(badge_id, title)
                    unlocked_roles.append(title)

        return {
            "status": "ok",
            "points": new_points,
            "level": new_level,
            "leveled_up": leveled_up,
            "unlocked": unlocked_roles
        }
    except Exception as e:
        logger.error(f"Failed to add XP: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

def get_xp() -> Dict[str, int]:
    """Retrieves current points and level."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT points, level FROM user_xp LIMIT 1")
        row = cursor.fetchone()
        if row:
            return {"points": row[0], "level": row[1]}
        return {"points": 0, "level": 1}
    except Exception:
        return {"points": 0, "level": 1}
    finally:
        conn.close()

def add_achievement(badge_id: str, title: str) -> bool:
    """Awards an achievement badge to the user."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO achievements (badge_id, title) VALUES (?, ?)",
            (badge_id, title)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to add achievement: {e}")
        return False
    finally:
        conn.close()

def get_achievements() -> List[Dict[str, Any]]:
    """Returns list of earned achievements."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT badge_id, title, earned_at FROM achievements ORDER BY earned_at DESC")
        return [{"badge_id": r[0], "title": r[1], "earned_at": r[2]} for r in cursor.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()

def update_streak(subject_id: str) -> Dict[str, Any]:
    """Updates active learning streak count based on last active date."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    current_date = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    try:
        cursor.execute("SELECT streak_count, last_active_date FROM learning_streaks WHERE subject_id = ?", (subject_id,))
        row = cursor.fetchone()
        
        if not row:
            # Create new streak
            cursor.execute(
                "INSERT INTO learning_streaks (subject_id, streak_count, last_active_date) VALUES (?, 1, ?)",
                (subject_id, current_date)
            )
            conn.commit()
            return {"subject_id": subject_id, "streak_count": 1, "status": "started"}
            
        streak_count, last_active = row[0], row[1]
        
        if last_active == current_date:
            # Already active today, no change
            return {"subject_id": subject_id, "streak_count": streak_count, "status": "active"}
        elif last_active == yesterday:
            # Continued streak
            new_streak = streak_count + 1
            cursor.execute(
                "UPDATE learning_streaks SET streak_count = ?, last_active_date = ? WHERE subject_id = ?",
                (new_streak, current_date, subject_id)
            )
            conn.commit()
            return {"subject_id": subject_id, "streak_count": new_streak, "status": "incremented"}
        else:
            # Streak broke, reset
            cursor.execute(
                "UPDATE learning_streaks SET streak_count = 1, last_active_date = ? WHERE subject_id = ?",
                (current_date, subject_id)
            )
            conn.commit()
            return {"subject_id": subject_id, "streak_count": 1, "status": "reset"}
            
    except Exception as e:
        logger.error(f"Failed to update streak: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

def get_streaks() -> List[Dict[str, Any]]:
    """Returns list of learning streaks."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT subject_id, streak_count, last_active_date FROM learning_streaks")
        return [{"subject_id": r[0], "streak_count": r[1], "last_active_date": r[2]} for r in cursor.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()

# === MEETING INTELLIGENCE ===

def save_meeting(meeting_id: str, title: str, participants: str, transcript: str, structured_notes: str, summary: str) -> bool:
    """Saves a meeting and its structured notes to the database."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO meetings (meeting_id, title, participants, transcript, structured_notes, summary) VALUES (?, ?, ?, ?, ?, ?)",
            (meeting_id, title, participants, transcript, structured_notes, summary)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to save meeting: {e}")
        return False
    finally:
        conn.close()

def get_meeting(meeting_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a specific meeting by ID."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT title, date_time, participants, transcript, structured_notes, summary FROM meetings WHERE meeting_id = ?", (meeting_id,))
        row = cursor.fetchone()
        if row:
            return {
                "title": row[0],
                "date_time": row[1],
                "participants": row[2],
                "transcript": row[3],
                "structured_notes": row[4],
                "summary": row[5]
            }
        return None
    except Exception as e:
        logger.error(f"Failed to get meeting {meeting_id}: {e}")
        return None
    finally:
        conn.close()

def search_meetings(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Searches meetings for a query in title, notes or transcript."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT meeting_id, title, date_time, summary FROM meetings WHERE title LIKE ? OR transcript LIKE ? OR summary LIKE ? ORDER BY date_time DESC LIMIT ?",
            (f"%{query}%", f"%{query}%", f"%{query}%", limit)
        )
        return [{"meeting_id": r[0], "title": r[1], "date_time": r[2], "summary": r[3]} for r in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to search meetings: {e}")
        return []
    finally:
        conn.close()

def get_recent_meetings(limit: int = 5) -> List[Dict[str, Any]]:
    """Retrieves the most recent meetings."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT meeting_id, title, date_time, summary FROM meetings ORDER BY date_time DESC LIMIT ?",
            (limit,)
        )
        return [{"meeting_id": r[0], "title": r[1], "date_time": r[2], "summary": r[3]} for r in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get recent meetings: {e}")
        return []
    finally:
        conn.close()

def add_action_item(meeting_id: str, description: str, owner: str = "", deadline: str = "") -> bool:
    """Adds a new action item to the database."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO action_items (meeting_id, description, owner, deadline) VALUES (?, ?, ?, ?)",
            (meeting_id, description, owner, deadline)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to add action item: {e}")
        return False
    finally:
        conn.close()

def get_pending_action_items() -> List[Dict[str, Any]]:
    """Retrieves all pending action items."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT task_id, meeting_id, description, owner, deadline FROM action_items WHERE status = 'pending' ORDER BY deadline ASC"
        )
        return [
            {
                "task_id": r[0],
                "meeting_id": r[1],
                "description": r[2],
                "owner": r[3],
                "deadline": r[4]
            } for r in cursor.fetchall()
        ]
    except Exception as e:
        logger.error(f"Failed to get pending action items: {e}")
        return []
    finally:
        conn.close()

def update_action_item_status(task_id: int, status: str) -> bool:
    """Updates the status of an action item."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE action_items SET status = ? WHERE task_id = ?", (status, task_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to update action item {task_id}: {e}")
        return False
    finally:
        conn.close()

# === PROJECT INTELLIGENCE ===

def save_project(project_id: str, name: str, path: str, purpose: str = "",
                 architecture: str = "", technologies: str = "",
                 features_completed: str = "[]", features_progress: str = "[]",
                 features_planned: str = "[]", blockers: str = "[]",
                 folder_structure: str = "", goals: str = "",
                 completed_modules: str = "", pending_modules: str = "",
                 known_bugs: str = "", development_history: str = "") -> bool:
    """Saves or updates a tracked project profile."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT OR REPLACE INTO tracked_projects
               (project_id, name, path, last_scan_date, purpose, architecture,
                technologies, features_completed, features_progress, features_planned,
                blockers, folder_structure, goals, completed_modules, pending_modules,
                known_bugs, development_history)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (project_id, name, path, purpose, architecture, technologies,
             features_completed, features_progress, features_planned,
             blockers, folder_structure, goals, completed_modules, pending_modules,
             known_bugs, development_history)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to save project {project_id}: {e}")
        return False
    finally:
        conn.close()

def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a tracked project by ID."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT project_id, name, path, created_at, last_scan_date, purpose, architecture, 
                      technologies, features_completed, features_progress, features_planned, 
                      blockers, recent_changes, folder_structure, goals, completed_modules, 
                      pending_modules, known_bugs, development_history 
               FROM tracked_projects WHERE project_id = ?""",
            (project_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "project_id": row[0], "name": row[1], "path": row[2],
                "created_at": row[3], "last_scan_date": row[4],
                "purpose": row[5], "architecture": row[6], "technologies": row[7],
                "features_completed": row[8], "features_progress": row[9],
                "features_planned": row[10], "blockers": row[11],
                "recent_changes": row[12], "folder_structure": row[13],
                "goals": row[14], "completed_modules": row[15],
                "pending_modules": row[16], "known_bugs": row[17],
                "development_history": row[18]
            }
        return None
    except Exception as e:
        logger.error(f"Failed to get project {project_id}: {e}")
        return None
    finally:
        conn.close()

def get_project_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Retrieves a tracked project by name (case-insensitive)."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT project_id, name, path, created_at, last_scan_date, purpose, architecture, 
                      technologies, features_completed, features_progress, features_planned, 
                      blockers, recent_changes, folder_structure, goals, completed_modules, 
                      pending_modules, known_bugs, development_history 
               FROM tracked_projects WHERE LOWER(name) = LOWER(?)""",
            (name,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "project_id": row[0], "name": row[1], "path": row[2],
                "created_at": row[3], "last_scan_date": row[4],
                "purpose": row[5], "architecture": row[6], "technologies": row[7],
                "features_completed": row[8], "features_progress": row[9],
                "features_planned": row[10], "blockers": row[11],
                "recent_changes": row[12], "folder_structure": row[13],
                "goals": row[14], "completed_modules": row[15],
                "pending_modules": row[16], "known_bugs": row[17],
                "development_history": row[18]
            }
        return None
    except Exception as e:
        logger.error(f"Failed to get project by name '{name}': {e}")
        return None
    finally:
        conn.close()

def get_active_project() -> Optional[Dict[str, Any]]:
    """
    Attempts to identify the active workspace project folder.
    First tries to inspect active desktop foreground window titles.
    Then falls back to the local workspace root or most recently scanned project.
    """
    init_db()
    
    # 1. Check if there are any tracked projects
    projects = list_tracked_projects()
    if not projects:
        return None
        
    # 2. Try to get foreground window title (from screen_monitor if available)
    try:
        from server.backend.screen_monitor import get_monitor_instance
        monitor = get_monitor_instance()
        title = monitor.get_foreground_window_title().lower()
        if title:
            # Check if any tracked project name or basename is in the title
            for proj in projects:
                if proj["name"].lower() in title:
                    return get_project(proj["project_id"])
    except Exception:
        pass

    # 3. Check if current directory path corresponds to any tracked project path
    import os
    # Default local workspace root of VOID
    default_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    for proj in projects:
        if os.path.abspath(proj["path"]) == default_root:
            return get_project(proj["project_id"])
            
    # 4. Fallback to the most recently scanned project
    return get_project(projects[0]["project_id"])

def list_tracked_projects() -> List[Dict[str, Any]]:
    """Lists all tracked projects."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT project_id, name, path, last_scan_date, purpose FROM tracked_projects ORDER BY last_scan_date DESC")
        return [{"project_id": r[0], "name": r[1], "path": r[2], "last_scan_date": r[3], "purpose": r[4]} for r in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        return []
    finally:
        conn.close()

def save_project_file(file_id: str, project_id: str, path: str, file_hash: str, summary: str = "") -> bool:
    """Saves or updates a project file record for change detection."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO project_files (file_id, project_id, path, file_hash, summary, last_scanned) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (file_id, project_id, path, file_hash, summary)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to save project file: {e}")
        return False
    finally:
        conn.close()

def get_project_files(project_id: str) -> List[Dict[str, Any]]:
    """Retrieves all file records for a project."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT file_id, path, file_hash, summary, last_scanned FROM project_files WHERE project_id = ? ORDER BY path",
            (project_id,)
        )
        return [{"file_id": r[0], "path": r[1], "file_hash": r[2], "summary": r[3], "last_scanned": r[4]} for r in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get project files: {e}")
        return []
    finally:
        conn.close()

def delete_project_file(file_id: str) -> bool:
    """Removes a project file record (for deleted files)."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM project_files WHERE file_id = ?", (file_id,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to delete project file: {e}")
        return False
    finally:
        conn.close()

def delete_project(project_id: str) -> bool:
    """Removes a project and its associated files and scan histories from the database."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM tracked_projects WHERE project_id = ?", (project_id,))
        cursor.execute("DELETE FROM project_files WHERE project_id = ?", (project_id,))
        cursor.execute("DELETE FROM project_scan_history WHERE project_id = ?", (project_id,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to delete project {project_id}: {e}")
        return False
    finally:
        conn.close()

def save_scan_history(project_id: str, new_files: str, modified_files: str, deleted_files: str, summary: str = "") -> bool:
    """Records a project scan result for historical tracking."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO project_scan_history (project_id, new_files, modified_files, deleted_files, summary) VALUES (?, ?, ?, ?, ?)",
            (project_id, new_files, modified_files, deleted_files, summary)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to save scan history: {e}")
        return False
    finally:
        conn.close()

def update_project_field(project_id: str, field: str, value: str) -> bool:
    """Updates a single field on a tracked project."""
    allowed_fields = {
        "purpose", "architecture", "technologies", "features_completed",
        "features_progress", "features_planned", "blockers", "recent_changes",
        "folder_structure", "last_scan_date", "goals", "completed_modules",
        "pending_modules", "known_bugs", "development_history"
    }
    if field not in allowed_fields:
        logger.warning(f"Attempted to update disallowed field: {field}")
        return False
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute(f"UPDATE tracked_projects SET {field} = ? WHERE project_id = ?", (value, project_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to update project field {field}: {e}")
        return False
    finally:
        conn.close()
