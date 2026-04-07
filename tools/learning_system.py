"""
VOID Learning System Module
====================

Long-term learning and habit detection for personalized automation.

Functions:
- record_action(action) -> None
- load_habits() -> dict
- save_habits(data) -> None
- detect_habits() -> list
- suggest_automation() -> str
- learn_from_command(command) -> None
"""

import json
import os
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

# Configure logging
logger = logging.getLogger("VOID-Learning")

# Data directory
DATA_DIR = "data"
HABITS_FILE = os.path.join(DATA_DIR, "habits.json")
PATTERNS_FILE = os.path.join(DATA_DIR, "patterns.json")
PREFERENCES_FILE = os.path.join(DATA_DIR, "preferences.json")

# Thresholds
MIN_HABIT_COUNT = 3  # Minimum times action must occur to be considered habit
PATTERN_WINDOW = 300  # Seconds to consider actions as related (5 minutes)
SUGGESTION_THRESHOLD = 5  # Actions before suggesting automation


# ============================================================================
# HABIT MANAGEMENT
# ============================================================================

def ensure_data_dir():
    """Ensure data directory exists."""
    os.makedirs(DATA_DIR, exist_ok=True)


def load_habits() -> Dict[str, Any]:
    """Load habits from file."""
    ensure_data_dir()
    
    if not os.path.exists(HABITS_FILE):
        return {}
    
    try:
        with open(HABITS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_habits(data: Dict[str, Any]) -> None:
    """Save habits to file."""
    ensure_data_dir()
    
    try:
        with open(HABITS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Failed to save habits: {e}")


def record_action(action: str, metadata: Dict[str, Any] = None) -> None:
    """
    Record a user action for learning.
    
    Args:
        action: Action name (e.g., "open_chrome", "search_python")
        metadata: Optional metadata about the action
    """
    ensure_data_dir()
    
    habits = load_habits()
    
    timestamp = time.time()
    
    if action not in habits:
        habits[action] = {
            "count": 1,
            "first_seen": timestamp,
            "last_seen": timestamp,
            "metadata": metadata or {}
        }
    else:
        habits[action]["count"] += 1
        habits[action]["last_seen"] = timestamp
        # Update metadata
        if metadata:
            habits[action]["metadata"].update(metadata)
    
    save_habits(habits)
    logger.info(f"[LEARNING] Recorded action: {action} (total: {habits[action]['count']})")


def get_habit_count(action: str) -> int:
    """Get count for a specific action."""
    habits = load_habits()
    return habits.get(action, {}).get("count", 0)


def is_habit(action: str) -> bool:
    """Check if an action is considered a habit."""
    return get_habit_count(action) >= MIN_HABIT_COUNT


# ============================================================================
# PATTERN DETECTION
# ============================================================================

def load_patterns() -> Dict[str, Any]:
    """Load patterns from file."""
    ensure_data_dir()
    
    if not os.path.exists(PATTERNS_FILE):
        return {"sequences": [], "workspaces": {}}
    
    try:
        with open(PATTERNS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"sequences": [], "workspaces": {}}


def save_patterns(data: Dict[str, Any]) -> None:
    """Save patterns to file."""
    ensure_data_dir()
    
    try:
        with open(PATTERNS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Failed to save patterns: {e}")


def record_action_sequence(actions: List[str], name: str = None) -> None:
    """
    Record a sequence of actions as a pattern.
    
    Args:
        actions: List of action names
        name: Optional name for the pattern
    """
    patterns = load_patterns()
    
    # Create pattern key from actions
    pattern_key = " -> ".join(actions)
    
    if pattern_key not in patterns["sequences"]:
        patterns["sequences"].append({
            "key": pattern_key,
            "actions": actions,
            "name": name,
            "count": 1,
            "first_seen": time.time(),
            "last_seen": time.time()
        })
    else:
        # Find and update
        for p in patterns["sequences"]:
            if p["key"] == pattern_key:
                p["count"] += 1
                p["last_seen"] = time.time()
                if name:
                    p["name"] = name
                break
    
    save_patterns(patterns)
    logger.info(f"[LEARNING] Recorded pattern: {pattern_key}")


def detect_habits(min_count: int = MIN_HABIT_COUNT) -> List[Dict[str, Any]]:
    """
    Detect actions that have become habits.
    
    Returns:
        List of habit dicts sorted by frequency
    """
    habits = load_habits()
    
    # Filter to habits and sort
    habit_list = [
        {
            "action": action,
            "count": data["count"],
            "first_seen": data.get("first_seen"),
            "last_seen": data.get("last_seen")
        }
        for action, data in habits.items()
        if data["count"] >= min_count
    ]
    
    # Sort by count descending
    habit_list.sort(key=lambda x: x["count"], reverse=True)
    
    return habit_list


def detect_patterns() -> List[Dict[str, Any]]:
    """
    Detect common action patterns.
    
    Returns:
        List of pattern dicts
    """
    patterns = load_patterns()
    
    # Sort by count descending
    pattern_list = sorted(
        patterns.get("sequences", []),
        key=lambda x: x.get("count", 0),
        reverse=True
    )
    
    return pattern_list[:10]  # Top 10


# ============================================================================
# PREFERENCES LEARNING
# ============================================================================

def load_preferences() -> Dict[str, Any]:
    """Load user preferences."""
    ensure_data_dir()
    
    if not os.path.exists(PREFERENCES_FILE):
        return {"app_preferences": {}, "time_preferences": {}, "custom_commands": {}}
    
    try:
        with open(PREFERENCES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"app_preferences": {}, "time_preferences": {}, "custom_commands": {}}


def save_preferences(data: Dict[str, Any]) -> None:
    """Save user preferences."""
    ensure_data_dir()
    
    try:
        with open(PREFERENCES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Failed to save preferences: {e}")


def learn_preference(category: str, key: str, value: Any) -> None:
    """
    Learn a user preference.
    
    Args:
        category: Preference category (e.g., "app_preferences")
        key: Preference key (e.g., "favorite_browser")
        value: Preference value
    """
    prefs = load_preferences()
    
    if category not in prefs:
        prefs[category] = {}
    
    prefs[category][key] = {
        "value": value,
        "learned_at": time.time()
    }
    
    save_preferences(prefs)
    logger.info(f"[LEARNING] Learned preference: {category}.{key} = {value}")


def get_preference(category: str, key: str, default: Any = None) -> Any:
    """Get a learned preference."""
    prefs = load_preferences()
    return prefs.get(category, {}).get(key, {}).get("value", default)


# ============================================================================
# AUTOMATION SUGGESTIONS
# ============================================================================

def suggest_automation() -> Optional[str]:
    """
    Analyze habits and suggest automation.
    
    Returns:
        Suggestion string or None
    """
    habits = detect_habits()
    patterns = detect_patterns()
    
    # Check if any action is frequent enough
    frequent_actions = [h for h in habits if h["count"] >= SUGGESTION_THRESHOLD]
    
    if not frequent_actions:
        return None
    
    # Analyze app preferences
    app_habits = [h for h in frequent_actions if h["action"].startswith("open_")]
    
    if len(app_habits) >= 2:
        # Suggest workspace
        apps = [h["action"].replace("open_", "") for h in app_habits[:3]]
        
        return (
            f"I've noticed you often open {', '.join(apps)}. "
            f"Would you like me to create a workspace command for this? "
            f"Just say 'create workspace [name]' and I'll remember."
        )
    
    # Check for search patterns
    search_habits = [h for h in frequent_actions if "search" in h["action"]]
    
    if len(search_habits) >= 3:
        return (
            "I see you search for similar topics often. "
            "Would you like me to remember your common searches?"
        )
    
    return None


def create_workspace(name: str, actions: List[str]) -> Dict[str, Any]:
    """
    Create a custom workspace from learned actions.
    
    Args:
        name: Workspace name
        actions: List of actions in the workspace
        
    Returns:
        Dict with creation status
    """
    patterns = load_patterns()
    
    patterns["workspaces"][name] = {
        "actions": actions,
        "created_at": time.time(),
        "usage_count": 0
    }
    
    save_patterns(patterns)
    logger.info(f"[LEARNING] Created workspace: {name}")
    
    return {
        "status": "ok",
        "workspace": name,
        "actions": actions,
        "message": f"Workspace '{name}' created with {len(actions)} actions"
    }


def get_workspace(name: str) -> Optional[List[str]]:
    """Get actions for a workspace."""
    patterns = load_patterns()
    workspace = patterns.get("workspaces", {}).get(name)
    
    if workspace:
        # Increment usage
        workspace["usage_count"] = workspace.get("usage_count", 0) + 1
        save_patterns(patterns)
        
        return workspace.get("actions", [])
    
    return None


# ============================================================================
# COMMAND LEARNING
# ============================================================================

def learn_command(command: str, action: str) -> None:
    """
    Learn a custom command mapping.
    
    Args:
        command: User's command phrase
        action: Action to execute
    """
    prefs = load_preferences()
    
    if "custom_commands" not in prefs:
        prefs["custom_commands"] = {}
    
    prefs["custom_commands"][command.lower()] = {
        "action": action,
        "learned_at": time.time(),
        "use_count": 0
    }
    
    save_preferences(prefs)
    logger.info(f"[LEARNING] Learned command: '{command}' -> {action}")


def get_custom_command(command: str) -> Optional[str]:
    """Get action for a custom command."""
    prefs = load_preferences()
    cmd_data = prefs.get("custom_commands", {}).get(command.lower())
    
    if cmd_data:
        # Increment use count
        cmd_data["use_count"] = cmd_data.get("use_count", 0) + 1
        save_preferences(prefs)
        
        return cmd_data.get("action")
    
    return None


def get_learned_commands() -> Dict[str, Any]:
    """Get all learned commands."""
    prefs = load_preferences()
    return prefs.get("custom_commands", {})


# ============================================================================
# INTEGRATION WITH TOOLS
# ============================================================================

def learn_from_tool_execution(tool_name: str, args: Any = None) -> None:
    """
    Learn from tool execution.
    Call this after any tool is executed.
    
    Args:
        tool_name: Name of the executed tool
        args: Tool arguments
    """
    # Create action name
    if args:
        action = f"{tool_name}_{args}"
    else:
        action = tool_name
    
    # Record action
    record_action(action, {"source": "tool_execution"})


# ============================================================================
# STATISTICS
# ============================================================================

def get_learning_stats() -> Dict[str, Any]:
    """Get learning system statistics."""
    habits = load_habits()
    patterns = load_patterns()
    prefs = load_preferences()
    
    habit_count = len([h for h in habits.values() if h.get("count", 0) >= MIN_HABIT_COUNT])
    pattern_count = len(patterns.get("sequences", []))
    workspace_count = len(patterns.get("workspaces", {}))
    command_count = len(prefs.get("custom_commands", {}))
    
    return {
        "total_actions": sum(h.get("count", 0) for h in habits.values()),
        "unique_actions": len(habits),
        "habits_detected": habit_count,
        "patterns_detected": pattern_count,
        "workspaces_created": workspace_count,
        "custom_commands": command_count
    }


def reset_learning() -> None:
    """Reset all learning data (for testing)."""
    ensure_data_dir()
    
    if os.path.exists(HABITS_FILE):
        os.remove(HABITS_FILE)
    if os.path.exists(PATTERNS_FILE):
        os.remove(PATTERNS_FILE)
    if os.path.exists(PREFERENCES_FILE):
        os.remove(PREFERENCES_FILE)
    
    logger.info("[LEARNING] Learning data reset")


# ============================================================================
# QUICK FUNCTIONS
# ============================================================================

def quick_record(action: str) -> str:
    """Quick action recording with status."""
    record_action(action)
    count = get_habit_count(action)
    
    if is_habit(action):
        return f"✅ '{action}' is now a habit! ({count} times)"
    else:
        return f"📝 Recorded: {action} ({count}/{MIN_HABIT_COUNT} to become habit)"


if __name__ == "__main__":
    # Test learning system
    print("Testing learning system...")
    
    # Record some actions
    print("\n1. Recording actions:")
    quick_record("open_chrome")
    quick_record("open_chrome")
    quick_record("open_chrome")
    quick_record("open_vscode")
    quick_record("open_vscode")
    quick_record("open_terminal")
    
    # Detect habits
    print("\n2. Detected habits:")
    habits = detect_habits()
    for h in habits:
        print(f"  {h['action']}: {h['count']} times")
    
    # Get stats
    print("\n3. Learning stats:")
    stats = get_learning_stats()
    print(f"  {stats}")
    
    # Suggest automation
    print("\n4. Automation suggestion:")
    suggestion = suggest_automation()
    print(f"  {suggestion or 'No suggestions yet'}")

