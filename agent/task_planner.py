"""
VOID Task Planner Module
====================

Converts high-level goals into sequences of tool executions.

Functions:
- create_plan(goal: str) -> List[dict]
- get_available_goals() -> List[str]
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("VOID-TaskPlanner")

# ============================================================================
# WORKSPACE DEFINITIONS
# ============================================================================

WORKSPACES = {
    "coding": {
        "name": "Coding Environment",
        "description": "Development workspace with code editor, browser, and terminal",
        "steps": [
            {"tool": "open_app", "args": "chrome", "description": "Open Chrome browser"},
            {"tool": "open_app", "args": "code", "description": "Open VS Code"},
            {"tool": "open_terminal", "args": None, "description": "Open Terminal"}
        ]
    },
    "study": {
        "name": "Study Environment",
        "description": "Workspace for learning and research",
        "steps": [
            {"tool": "open_app", "args": "chrome", "description": "Open Chrome browser"},
            {"tool": "open_app", "args": "notepad", "description": "Open Notepad for notes"},
            {"tool": "open_app", "args": "calculator", "description": "Open Calculator"}
        ]
    },
    "work": {
        "name": "Work Environment",
        "description": "Professional workspace",
        "steps": [
            {"tool": "open_app", "args": "chrome", "description": "Open Chrome browser"},
            {"tool": "open_app", "args": "outlook", "description": "Open Outlook (if installed)"},
            {"tool": "open_app", "args": "word", "description": "Open Word (if installed)"}
        ]
    },
    "creative": {
        "name": "Creative Environment",
        "description": "For creative work like design or media",
        "steps": [
            {"tool": "open_app", "args": "chrome", "description": "Open Chrome browser"},
            {"tool": "open_app", "args": "photoshop", "description": "Open Photoshop (if installed)"}
        ]
    },
    "gaming": {
        "name": "Gaming Environment",
        "description": "Launch gaming platforms",
        "steps": [
            {"tool": "open_app", "args": "steam", "description": "Open Steam"},
            {"tool": "open_app", "args": "discord", "description": "Open Discord"}
        ]
    },
    "presentation": {
        "name": "Presentation Environment",
        "description": "For giving presentations",
        "steps": [
            {"tool": "open_app", "args": "chrome", "description": "Open browser for slides"},
            {"tool": "open_app", "args": "powerpnt", "description": "Open PowerPoint"},
            {"tool": "open_app", "args": "notes", "description": "Open Notes app"}
        ]
    },
    "music": {
        "name": "Music Production",
        "description": "Audio production workspace",
        "steps": [
            {"tool": "open_app", "args": "chrome", "description": "Open browser for reference"},
            {"tool": "open_app", "args": "spotify", "description": "Open Spotify"}
        ]
    }
}

# ============================================================================
# PROJECT FOLDERS
# ============================================================================

COMMON_FOLDERS = {
    "projects": "C:/Users/HP/Desktop/Projects",
    "desktop": "C:/Users/HP/Desktop",
    "documents": "C:/Users/HP/Documents",
    "downloads": "C:/Users/HP/Downloads"
}


def get_available_goals() -> List[str]:
    """Get list of available workspace goals."""
    return list(WORKSPACES.keys())


def create_plan(goal: str, custom_folders: Dict[str, str] = None) -> List[Dict[str, Any]]:
    """
    Create a plan for the given goal.
    
    Args:
        goal: High-level goal (e.g., "prepare coding environment")
        custom_folders: Optional custom folder paths
        
    Returns:
        List of step dicts with tool, args, description
    """
    goal_lower = goal.lower().strip()
    logger.info(f"[PLANNER] Creating plan for: {goal}")
    
    # Use custom folders if provided
    folders = custom_folders or COMMON_FOLDERS
    
    # Check for workspace keywords
    for workspace_key, workspace in WORKSPACES.items():
        if workspace_key in goal_lower:
            steps = workspace["steps"].copy()
            
            # Check for custom folder in goal
            for folder_key, folder_path in folders.items():
                if folder_key in goal_lower:
                    # Add open_folder step
                    steps.insert(1, {
                        "tool": "open_folder",
                        "args": folder_path,
                        "description": f"Open {folder_key} folder"
                    })
            
            logger.info(f"[PLANNER] Plan created: {len(steps)} steps")
            return steps
    
    # Check for specific action patterns
    if "open" in goal_lower and "chrome" in goal_lower:
        return [{"tool": "open_app", "args": "chrome", "description": "Open Chrome"}]
    
    if "open" in goal_lower and "code" in goal_lower:
        return [{"tool": "open_app", "args": "code", "description": "Open VS Code"}]
    
    if "open" in goal_lower and "terminal" in goal_lower:
        return [{"tool": "open_terminal", "args": None, "description": "Open Terminal"}]
    
    if "open" in goal_lower and "folder" in goal_lower:
        # Try to extract folder name
        for folder_key, folder_path in folders.items():
            if folder_key in goal_lower:
                return [{"tool": "open_folder", "args": folder_path, "description": f"Open {folder_key}"}]
    
    # Check for "search" or "look up" patterns
    if "search" in goal_lower or "look up" in goal_lower:
        # Extract query
        query = goal_lower.replace("search", "").replace("look up", "").strip()
        if query:
            return [{"tool": "search_google", "args": query, "description": f"Search: {query}"}]
    
    # Check for "play" patterns (music/video)
    if "play" in goal_lower:
        query = goal_lower.replace("play", "").strip()
        if query:
            return [{"tool": "play_youtube", "args": query, "description": f"Play: {query}"}]
    
    # No plan found
    logger.info(f"[PLANNER] No plan found for: {goal}")
    return []


def create_llm_plan(goal: str, available_tools: List[str]) -> List[Dict[str, Any]]:
    """
    Create a plan using LLM-style reasoning (simulated).
    For more complex goals that don't match predefined templates.
    
    Args:
        goal: The user's goal
        available_tools: List of available tool names
        
    Returns:
        List of steps
    """
    goal_lower = goal.lower()
    
    # Break down into verbs
    steps = []
    
    # Check for common actions
    if "open" in goal_lower:
        # Extract what's being opened
        for tool in available_tools:
            if tool in goal_lower:
                steps.append({
                    "tool": tool,
                    "args": None,
                    "description": f"Open {tool}"
                })
    
    if "search" in goal_lower:
        query = goal_lower.split("search")[-1].strip()
        if query:
            steps.append({
                "tool": "search_google",
                "args": query,
                "description": f"Search for {query}"
            })
    
    if "play" in goal_lower:
        query = goal_lower.split("play")[-1].strip()
        if query:
            steps.append({
                "tool": "play_youtube", 
                "args": query,
                "description": f"Play {query}"
            })
    
    return steps


# ============================================================================
# NATURAL LANGUAGE GOAL PARSING
# ============================================================================

GOAL_PATTERNS = {
    "prepare": ["prepare", "setup", "start", "launch", "initiate"],
    "coding": ["coding", "development", "dev", "program", "code"],
    "study": ["study", "learning", "research", "homework"],
    "work": ["work", "office", "professional", "business"],
    "creative": ["creative", "design", "art", "media"],
    "gaming": ["gaming", "game", "play games"],
    "presentation": ["presentation", "present", "slides", "pitch"],
    "music": ["music", "audio", "sound", "production"]
}


def parse_goal_intent(prompt: str) -> Optional[Dict[str, Any]]:
    """
    Parse the user's goal from natural language.
    
    Returns:
        Dict with intent, entities, and plan
    """
    prompt_lower = prompt.lower()
    
    # Detect action verb
    action = None
    for key, synonyms in GOAL_PATTERNS.items():
        if key in ["prepare", "setup", "start", "launch"]:
            continue
        for syn in synonyms:
            if syn in prompt_lower:
                action = key
                break
    
    # Detect preparation intent
    is_prepare = any(syn in prompt_lower for syn in GOAL_PATTERNS["prepare"])
    
    if is_prepare and action:
        goal = f"{action} environment"
        plan = create_plan(goal)
        return {
            "intent": "prepare_workspace",
            "action": action,
            "goal": goal,
            "plan": plan
        }
    
    # Direct action
    if action:
        plan = create_plan(f"open {action}")
        return {
            "intent": "open_app",
            "action": action,
            "plan": plan
        }
    
    # Try generic planning
    plan = create_plan(prompt)
    if plan:
        return {
            "intent": "execute_plan",
            "goal": prompt,
            "plan": plan
        }
    
    return None


if __name__ == "__main__":
    # Test planner
    print("Testing task planner...")
    
    # Test predefined workspaces
    for goal_name in get_available_goals():
        plan = create_plan(f"prepare {goal_name} environment")
        print(f"\n{goal_name}: {len(plan)} steps")
        for step in plan:
            print(f"  - {step['description']}")
    
    # Test custom
    print("\n\nCustom: open chrome and code")
    plan = create_plan("open chrome and code")
    print(f"Plan: {plan}")

