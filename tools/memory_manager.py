"""
VOID Memory Manager Module
=======================

Purpose:
Store and retrieve user information for personalized conversations and planning.

Functions:
- load_memory() -> dict
- save_memory(memory: dict) 
- remember(key: str, value: str) -> str
- recall(key: str) -> str
- get_all_memory() -> dict
- forget(key: str) -> bool
- update_memory(updates: dict) -> bool
- get_memory_context() -> str (for LLM prompts)
"""

import json
import os
import re
from typing import Dict, Any, Optional

# Memory file path
MEMORY_DIR = "data"
MEMORY_FILE = os.path.join(MEMORY_DIR, "memory.json")


def _ensure_memory_dir():
    """Ensure the memory directory exists."""
    os.makedirs(MEMORY_DIR, exist_ok=True)


def load_memory() -> Dict[str, Any]:
    """
    Load memory from file.
    
    Returns:
        Dict with user information (name, preferences, facts, etc.)
    """
    _ensure_memory_dir()
    
    if not os.path.exists(MEMORY_FILE):
        return {
            "user": {},
            "preferences": {},
            "facts": [],
            "history": []
        }
    
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Ensure all required keys exist
            if not isinstance(data, dict):
                return {"user": {}, "preferences": {}, "facts": [], "history": []}
            return {
                "user": data.get("user", {}),
                "preferences": data.get("preferences", {}),
                "facts": data.get("facts", []),
                "history": data.get("history", [])
            }
    except json.JSONDecodeError:
        # Corrupted file - reset
        return {"user": {}, "preferences": {}, "facts": [], "history": []}
    except Exception:
        return {"user": {}, "preferences": {}, "facts": [], "history": []}


def save_memory(memory: Dict[str, Any]) -> bool:
    """
    Save memory to file.
    
    Args:
        memory: Dict with user, preferences, facts, history
        
    Returns:
        True if saved successfully
    """
    _ensure_memory_dir()
    
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def remember(key: str, value: str) -> str:
    """
    Store a piece of user information.
    
    Args:
        key: What to remember (e.g., "name", "favorite_app")
        value: The value (e.g., "Mridul", "chrome")
        
    Returns:
        Confirmation message
    """
    memory = load_memory()
    
    # Store in appropriate section
    key_lower = key.lower().strip()
    
    if key_lower in ["name", "age", "location", "occupation"]:
        # User info
        memory["user"][key_lower] = value
    else:
        # Preferences or facts
        memory["preferences"][key] = value
    
    if save_memory(memory):
        return f"Remembered: {key} = {value}"
    else:
        return "Failed to save memory."


def remember_fact(fact: str) -> bool:
    """
    Remember a general fact about the user.
    
    Args:
        fact: Fact string to remember
        
    Returns:
        True if saved (or already exists)
    """
    memory = load_memory()
    facts = memory.get("facts", [])
    
    # Check if already exists
    for existing_fact in facts:
        if existing_fact.lower() == fact.lower():
            return False  # Already remembered
    
    facts.append(fact)
    memory["facts"] = facts
    
    return save_memory(memory)


def recall(key: str) -> Optional[str]:
    """
    Recall a specific piece of information.
    
    Args:
        key: The key to look up
        
    Returns:
        The value or None if not found
    """
    memory = load_memory()
    
    key_lower = key.lower().strip()
    
    # Check user info
    if key_lower in memory.get("user", {}):
        return memory["user"][key_lower]
    
    # Check preferences
    if key in memory.get("preferences", {}):
        return memory["preferences"][key]
    
    return None


def get_all_memory() -> Dict[str, Any]:
    """
    Get all stored memory.
    
    Returns:
        Full memory dict
    """
    return load_memory()


def get_user_info() -> Dict[str, str]:
    """Get just user information."""
    memory = load_memory()
    return memory.get("user", {})


def get_preferences() -> Dict[str, Any]:
    """Get user preferences."""
    memory = load_memory()
    return memory.get("preferences", {})


def get_facts() -> list:
    """Get stored facts."""
    memory = load_memory()
    return memory.get("facts", [])


def forget(key: str) -> bool:
    """
    Remove a piece of information from memory.
    
    Args:
        key: Key to remove
        
    Returns:
        True if removed
    """
    memory = load_memory()
    key_lower = key.lower().strip()
    
    removed = False
    
    # Try user info
    if key_lower in memory.get("user", {}):
        del memory["user"][key_lower]
        removed = True
    
    # Try preferences
    if key in memory.get("preferences", {}):
        del memory["preferences"][key]
        removed = True
    
    if removed:
        return save_memory(memory)
    
    return False


def forget_fact(fact: str) -> bool:
    """Remove a fact from memory."""
    memory = load_memory()
    facts = memory.get("facts", [])
    
    original_count = len(facts)
    facts = [f for f in facts if f.lower() != fact.lower()]
    
    if len(facts) < original_count:
        memory["facts"] = facts
        return save_memory(memory)
    
    return False


def clear_memory() -> bool:
    """Clear all memory."""
    return save_memory({
        "user": {},
        "preferences": {},
        "facts": [],
        "history": []
    })


def add_to_history(entry: str) -> bool:
    """Add an entry to conversation history."""
    memory = load_memory()
    history = memory.get("history", [])
    
    history.append({
        "entry": entry,
        "timestamp": None  # Could add timestamp if needed
    })
    
    # Keep only last 50 entries
    if len(history) > 50:
        history = history[-50:]
    
    memory["history"] = history
    return save_memory(memory)


def get_memory_context() -> str:
    """
    Get formatted memory context for LLM prompts.
    
    Returns:
        String with user info and facts formatted for LLM
    """
    memory = load_memory()
    
    context_parts = []
    
    # User information
    user = memory.get("user", {})
    if user:
        user_info = ", ".join([f"{k}: {v}" for k, v in user.items()])
        context_parts.append(f"User: {user_info}")
    
    # Facts
    facts = memory.get("facts", [])
    if facts:
        facts_text = "; ".join(facts)
        context_parts.append(f"Facts: {facts_text}")
    
    # Preferences
    prefs = memory.get("preferences", {})
    if prefs:
        prefs_text = ", ".join([f"{k}: {v}" for k, v in prefs.items()])
        context_parts.append(f"Preferences: {prefs_text}")
    
    if context_parts:
        return " | ".join(context_parts)
    
    return "No stored memory yet."


def get_memory_for_planner() -> str:
    """
    Get memory context formatted for planner use.
    
    Returns:
        String with relevant info for planning
    """
    memory = load_memory()
    
    parts = []
    
    # Name for personalization
    if memory.get("user", {}).get("name"):
        parts.append(f"User's name: {memory['user']['name']}")
    
    # Key preferences that affect planning
    prefs = memory.get("preferences", {})
    if prefs:
        # Get first few preferences
        relevant = list(prefs.items())[:5]
        for k, v in relevant:
            parts.append(f"{k}: {v}")
    
    if parts:
        return " | ".join(parts)
    
    return ""


# Convenience function for main.py integration
def extract_and_remember(prompt: str) -> Optional[str]:
    """
    Extract memory commands from prompt and execute.
    
    Handles patterns like:
    - "remember my name is X"
    - "my name is X"
    - "I am X years old"
    
    Args:
        prompt: User message
        
    Returns:
        Confirmation message if memory was stored, None otherwise
    """
    prompt_lower = prompt.lower().strip()
    
    # Pattern: "remember my name is X"
    m = re.search(r"remember\s+(?:my\s+)?(.+?)\s+is\s+(.+)", prompt_lower)
    if m:
        key = m.group(1).strip()
        value = m.group(2).strip()
        return remember(key, value)
    
    # Pattern: "my name is X" (without "remember")
    m = re.search(r"my\s+name\s+is\s+([A-Za-z][A-Za-z0-9\s]{0,30})", prompt, re.IGNORECASE)
    if m:
        name = m.group(1).strip()
        remember("name", name)
        return f"Remembered your name is {name}"
    
    # Pattern: "I am X years old"
    m = re.search(r"I\s+am\s+(\d+)\s+years\s+old", prompt, re.IGNORECASE)
    if m:
        age = m.group(1)
        remember("age", age)
        return f"Remembered your age is {age}"
    
    # Pattern: "I live in X"
    m = re.search(r"I\s+live\s+in\s+([A-Za-z][A-Za-z0-9\s]{0,30})", prompt, re.IGNORECASE)
    if m:
        location = m.group(1).strip()
        remember("location", location)
        return f"Remembered you live in {location}"
    
    # Pattern: "I work as X"
    m = re.search(r"(?:I\s+)?work\s+(?:as|as a)\s+([A-Za-z][A-Za-z0-9\s]{0,30})", prompt, re.IGNORECASE)
    if m:
        job = m.group(1).strip()
        remember("occupation", job)
        return f"Remembered your occupation is {job}"
    
    return None


if __name__ == "__main__":
    # Test
    print("Testing memory manager...")
    
    # Remember something
    print(remember("name", "Mridul"))
    
    # Get context
    print(f"Context: {get_memory_context()}")
    
    # Recall
    print(f"Recalled: {recall('name')}")

