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
    
    # Ensure default row in user_xp
    cursor.execute("SELECT COUNT(*) FROM user_xp")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO user_xp (points, level) VALUES (0, 1)")
        
    conn.commit()
    conn.close()
    logger.info(f"[SQLITE MEMORY] Database initialized at: {DB_FILE}")

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
    """Generates embedding vector from local Ollama endpoint."""
    model = get_ollama_model()
    try:
        # Option 1: Classic embeddings API
        resp = requests.post(OLLAMA_EMBED_URL, json={"model": model, "prompt": text}, timeout=4.0)
        if resp.status_code == 200:
            vector = resp.json().get("embedding", [])
            if vector:
                return vector
    except Exception:
        pass
        
    try:
        # Option 2: Newer embed API
        resp = requests.post(OLLAMA_EMBED_FALLBACK, json={"model": model, "input": [text]}, timeout=4.0)
        if resp.status_code == 200:
            vectors = resp.json().get("embeddings", [])
            if vectors:
                return vectors[0]
    except Exception:
        pass
        
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
        return {
            "status": "ok",
            "points": new_points,
            "level": new_level,
            "leveled_up": leveled_up
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
