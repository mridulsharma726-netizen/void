"""
VOID Goal Planner Module
========================

Generates executable plans from high-level user goals.
Uses deterministic pattern matching to create multi-step action sequences.

Functions:
- generate_plan(goal: str) -> List[str]
- execute_plan(plan: List[str], tool_executor: callable) -> List[dict]
"""

from typing import List, Dict, Any, Callable


def generate_plan(goal: str) -> List[str]:
    """
    Generate a list of executable steps from a user goal.
    
    Args:
        goal: The user's high-level goal statement
        
    Returns:
        List of action strings to execute
    """
    goal_lower = goal.lower().strip()
    
    # Workspace setup
    if "workspace" in goal_lower or "setup my desk" in goal_lower:
        return [
            "open chrome",
            "open notepad",
            "open downloads"
        ]
    
    # Coding environment
    if "coding" in goal_lower or "code" in goal_lower:
        return [
            "open vscode",
            "open chrome",
            "open terminal"
        ]
    
    # Productivity setup
    if "productivity" in goal_lower or "productive" in goal_lower:
        return [
            "open chrome",
            "open notepad",
            "open calculator"
        ]
    
    # Music/Entertainment setup
    if "music" in goal_lower or "entertainment" in goal_lower or "spotify" in goal_lower:
        return [
            "open chrome",
            "play youtube lofi"
        ]
    
    # Research setup
    if "research" in goal_lower or "study" in goal_lower:
        return [
            "open chrome",
            "open notepad",
            "open downloads"
        ]
    
    # Communication setup
    if "communication" in goal_lower or "chat" in goal_lower:
        return [
            "open chrome",
            "open notepad"
        ]
    
    # Morning routine
    if "morning" in goal_lower or "start my day" in goal_lower:
        return [
            "open chrome",
            "open notepad",
            "open calculator"
        ]
    
    # Design work
    if "design" in goal_lower or "creative" in goal_lower:
        return [
            "open chrome",
            "open notepad"
        ]
    
    # Download management
    if "download" in goal_lower or "downloads" in goal_lower:
        return [
            "open downloads"
        ]
    
    # Browser + Notepad combo (default productivity)
    if "prepare" in goal_lower or "setup" in goal_lower:
        return [
            "open chrome",
            "open notepad"
        ]
    
    # Initialize system
    if "initialize" in goal_lower or "start my" in goal_lower:
        return [
            "open chrome",
            "open notepad"
        ]
    
    # Organize workspace
    if "organize" in goal_lower or "clean" in goal_lower:
        return [
            "open chrome",
            "open notepad"
        ]
    
    # Default: empty plan
    return []


def execute_plan(plan: List[str], tool_executor: Callable[[str], Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Execute a plan by running each step through the tool executor.
    
    Args:
        plan: List of action strings to execute
        tool_executor: Function that takes an action string and returns a result dict
        
    Returns:
        List of result dictionaries from each step
    """
    results = []
    
    for step in plan:
        try:
            result = tool_executor(step)
            results.append({
                "step": step,
                "status": "success" if result.get("status") == "ok" else "error",
                "result": result
            })
        except Exception as e:
            results.append({
                "step": step,
                "status": "error",
                "result": {"status": "error", "message": str(e)}
            })
    
    return results


def format_plan_response(plan: List[str], results: List[Dict[str, Any]]) -> str:
    """
    Format the plan execution results into a user-friendly message.
    
    Args:
        plan: The original plan that was executed
        results: Results from executing each step
        
    Returns:
        Formatted response string
    """
    if not plan:
        return "No plan generated for this request."
    
    # Count successes
    success_count = sum(1 for r in results if r.get("status") == "success")
    
    # Build response
    plan_steps = "\n".join([f"{i+1}. {step}" for i, step in enumerate(plan)])
    
    response = f"Plan executed: {success_count}/{len(plan)} steps completed\n\n"
    response += f"Steps:\n{plan_steps}"
    
    return response


# Convenience function for direct import
def plan_and_execute(goal: str, tool_executor: Callable[[str], Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate and execute a plan in one call.
    
    Args:
        goal: User's high-level goal
        tool_executor: Function to execute each step
        
    Returns:
        Dict with plan, results, and formatted response
    """
    plan = generate_plan(goal)
    
    if not plan:
        return {
            "plan": [],
            "results": [],
            "response": "I couldn't generate a plan for that request."
        }
    
    results = execute_plan(plan, tool_executor)
    response = format_plan_response(plan, results)
    
    return {
        "plan": plan,
        "results": results,
        "response": response
    }


if __name__ == "__main__":
    # Test the planner
    test_goals = [
        "setup my workspace",
        "prepare my coding environment",
        "start my productivity morning",
        "organize my downloads"
    ]
    
    # Mock tool executor for testing
    def mock_executor(action: str) -> Dict[str, Any]:
        return {"status": "ok", "message": f"Executed: {action}"}
    
    for goal in test_goals:
        print(f"\n=== Goal: {goal} ===")
        result = plan_and_execute(goal, mock_executor)
        print(result["response"])

