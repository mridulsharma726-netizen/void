"""
VOID Unified Memory Manager Module (SQLite Migrated)
===================================================

Provides structural state persistence using high-performance SQLite vector storage
with complete backward-compatibility for uvicorn routers, decision engines, and planners.
"""

import re
import os
import logging
from typing import Dict, Any, Optional, List

# Import SQLite Vector Engine functions
from backend.memory_sqlite import (
    init_db,
    add_fact,
    remove_fact,
    set_preference,
    get_preference,
    add_history,
    get_all_facts,
    get_all_preferences,
    get_recent_history,
    purge_all,
    query_semantic_facts
)

logger = logging.getLogger("void.memory_manager")

def load_memory() -> Dict[str, Any]:
    """
    Constructs a backward-compatible dictionary representation on the fly from SQLite.
    """
    init_db()
    prefs = get_all_preferences()
    
    # Separate core user details
    user_keys = ["name", "age", "location", "occupation"]
    user_data = {}
    other_prefs = {}
    
    for k, v in prefs.items():
        if k.lower() in user_keys:
            user_data[k.lower()] = v
        else:
            other_prefs[k] = v
            
    return {
        "user": user_data,
        "preferences": other_prefs,
        "facts": get_all_facts(),
        "history": get_recent_history()
    }

def save_memory(memory: Dict[str, Any]) -> bool:
    """
    Saves state dictionary elements back into SQLite database.
    """
    try:
        # Save user fields
        for k, v in memory.get("user", {}).items():
            set_preference(k, str(v))
        # Save preference fields
        for k, v in memory.get("preferences", {}).items():
            set_preference(k, str(v))
        # Save facts
        current_facts = get_all_facts()
        for fact in memory.get("facts", []):
            if fact not in current_facts:
                add_fact(fact)
        # Save history turns
        for turn in memory.get("history", []):
            role = turn.get("role", "user")
            content = turn.get("content", turn.get("entry", ""))
            if content:
                add_history(role, content)
        return True
    except Exception as e:
        logger.error(f"Error in legacy save_memory wrapper: {e}")
        return False

def remember(key: str, value: str) -> str:
    """Stores a piece of user preference or user attribute."""
    if set_preference(key, value):
        return f"Remembered: {key} = {value}"
    return "Failed to save memory."

def remember_fact(fact: str) -> bool:
    """Remember a general fact about the user via SQLite vector storage."""
    return add_fact(fact)

def recall(key: str) -> Optional[str]:
    """Recall a specific preference or key."""
    return get_preference(key)

def get_all_memory() -> Dict[str, Any]:
    """Retrieve full backward-compatible memory dictionary."""
    return load_memory()

def get_user_info() -> Dict[str, str]:
    """Get just user information."""
    return load_memory().get("user", {})

def get_preferences() -> Dict[str, Any]:
    """Get all preferences."""
    return get_all_preferences()

def get_facts() -> List[str]:
    """Get all stored facts."""
    return get_all_facts()

def forget(key: str) -> bool:
    """Remove a piece of information from memory preference banks."""
    init_db()
    import sqlite3
    from backend.memory_sqlite import DB_FILE
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM preferences WHERE key = ? OR key = ?", (key, key.lower()))
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        return False
    finally:
        conn.close()

def forget_fact(fact: str) -> bool:
    """Remove fact from memory."""
    return remove_fact(fact)

def clear_memory() -> bool:
    """Purge all memory tables."""
    return purge_all()

def add_to_history(entry: str) -> bool:
    """Adds a conversation entry to history."""
    return add_history("user", entry)

def get_memory_context() -> str:
    """
    Get formatted memory context for LLM prompts.
    Formats user detail key preferences and facts.
    """
    memory = load_memory()
    context_parts = []
    
    user = memory.get("user", {})
    if user:
        user_info = ", ".join([f"{k}: {v}" for k, v in user.items()])
        context_parts.append(f"User: {user_info}")
        
    facts = memory.get("facts", [])
    if facts:
        facts_text = "; ".join(facts)
        context_parts.append(f"Facts: {facts_text}")
        
    prefs = memory.get("preferences", {})
    if prefs:
        prefs_text = ", ".join([f"{k}: {v}" for k, v in prefs.items()])
        context_parts.append(f"Preferences: {prefs_text}")
        
    if context_parts:
        return " | ".join(context_parts)
    return "No stored memory yet."

def get_memory_for_planner() -> str:
    """Get memory context formatted for planner use."""
    memory = load_memory()
    parts = []
    
    if memory.get("user", {}).get("name"):
        parts.append(f"User's name: {memory['user']['name']}")
        
    prefs = memory.get("preferences", {})
    if prefs:
        relevant = list(prefs.items())[:5]
        for k, v in relevant:
            parts.append(f"{k}: {v}")
            
    if parts:
        return " | ".join(parts)
    return ""

def extract_and_remember(prompt: str) -> Optional[str]:
    """
    Extract memory commands from prompt and execute.
    """
    prompt_lower = prompt.lower().strip()
    
    m = re.search(r"remember\s+(?:my\s+)?(.+?)\s+is\s+(.+)", prompt_lower)
    if m:
        key = m.group(1).strip()
        value = m.group(2).strip()
        return remember(key, value)
        
    m = re.search(r"my\s+name\s+is\s+([A-Za-z][A-Za-z0-9\s]{0,30})", prompt, re.IGNORECASE)
    if m:
        name = m.group(1).strip()
        remember("name", name)
        return f"Remembered your name is {name}"
        
    m = re.search(r"I\s+am\s+(\d+)\s+years\s+old", prompt, re.IGNORECASE)
    if m:
        age = m.group(1)
        remember("age", age)
        return f"Remembered your age is {age}"
        
    m = re.search(r"I\s+live\s+in\s+([A-Za-z][A-Za-z0-9\s]{0,30})", prompt, re.IGNORECASE)
    if m:
        location = m.group(1).strip()
        remember("location", location)
        return f"Remembered you live in {location}"
        
    m = re.search(r"(?:I\s+)?work\s+(?:as|as a)\s+([A-Za-z][A-Za-z0-9\s]{0,30})", prompt, re.IGNORECASE)
    if m:
        job = m.group(1).strip()
        remember("occupation", job)
        return f"Remembered your occupation is {job}"
        
    return None

class MemoryManager:
    """
    Class-based interface to VOID Memory system.
    Supports SQLite database vector-similarity querying with full backward compatibility.
    """
    def __init__(self, data_dir):
        self.data_dir = data_dir
        init_db()
        
    @property
    def short_term(self) -> List[Dict[str, str]]:
        """Get recent conversation history turns."""
        return get_recent_history(50)
        
    def remember_turn(self, role: str, content: str) -> bool:
        """Remember a conversation turn (role and content)."""
        role_map = {"user": "user", "assistant": "assistant", "void": "assistant"}
        normalized_role = role_map.get(role.lower(), role)
        return add_history(normalized_role, content)
        
    def list_facts(self) -> List[str]:
        """List all remembered facts."""
        return get_all_facts()
        
    def add_fact(self, fact: str) -> bool:
        """Add a general fact."""
        return add_fact(fact)
        
    def clear(self) -> bool:
        """Purge memory banks."""
        return purge_all()
        
    def get_summary(self) -> str:
        """Return memory banks overview summary."""
        facts_count = len(get_all_facts())
        history_count = len(get_recent_history(50))
        user_name = get_preference("name") or "Sir"
        return f"Memory context loaded for {user_name}. Stored facts: {facts_count}. Conversation turns: {history_count}."

    def query_relevant(self, query: str, limit: int = 3) -> List[str]:
        """Query relevant facts using SQLite vector similarity search."""
        return query_semantic_facts(query, limit=limit)

