"""
VOID LLM Planner Module
=====================

Uses LLM to generate dynamic task plans from user goals.
Complements the rule-based goal_planner.py with AI-generated planning.

Functions:
- generate_llm_plan(goal) -> str (LLM response with plan)
- parse_plan(plan_text) -> List[str] (parse steps from LLM response)
- execute_plan(steps, tool_executor) -> List[dict] (execute each step)
- plan_and_execute(goal, tool_executor, llm_callable) -> dict
"""

from typing import List, Dict, Any, Callable
import re


LLM_PLANNER_PROMPT = """You are VOID, an AI desktop assistant.

Your job is to create a simple action plan using available tools.

Available actions:
- open chrome (browser)
- open notepad (text editor)
- open downloads (folder)
- open documents (folder)
- open calculator
- open vscode (code editor)
- open terminal
- play youtube <query>
- search google <query>
- open <app_name>

Rules:
1. Keep plan simple (1-5 steps maximum)
2. Use only available actions
3. Be practical for the goal

Respond ONLY in this format:

PLAN
1. [action]
2. [action]
3. [action]

User Goal: {goal}

PLAN"""



def generate_llm_plan(goal: str) -> str:
    """
    Generate a plan prompt to send to LLM.
    
    Args:
        goal: User's high-level goal
        
    Returns:
        Prompt string for LLM
    """
    return LLM_PLANNER_PROMPT.format(goal=goal)


def parse_plan(plan_text: str) -> List[str]:
    """
    Parse the plan steps from LLM response text.
    
    Args:
        plan_text: Raw text from LLM containing the plan
        
    Returns:
        List of action strings
    """
    if not plan_text:
        return []
    
    lines = plan_text.splitlines()
    steps = []
    
    for line in lines:
        line = line.strip()
        
        # Match patterns like "1. open chrome" or "1 open chrome"
        if line and (line[0].isdigit() or line.startswith(('- ', '* '))):
            # Remove the number/prefix
            cleaned = re.sub(r'^[\d\.\-\*\s]+', '', line).strip()
            if cleaned:
                steps.append(cleaned)
    
    return steps


def execute_plan(steps: List[str], tool_executor: Callable[[str], Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Execute a plan by running each step through the tool executor.
    
    Args:
        steps: List of action strings to execute
        tool_executor: Function that takes an action string and returns a result dict
        
    Returns:
        List of result dictionaries from each step
    """
    results = []
    
    for step in steps:
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
        return "No plan generated."
    
    # Count successes
    success_count = sum(1 for r in results if r.get("status") == "success")
    
    # Build response
    plan_steps = "\n".join([f"{i+1}. {step}" for i, step in enumerate(plan)])
    
    response = f"Plan executed: {success_count}/{len(plan)} steps completed\n\n"
    response += f"Steps:\n{plan_steps}"
    
    return response


def plan_and_execute(goal: str, tool_executor: Callable[[str], Dict[str, Any]], llm_callable: Callable[[str], str]) -> Dict[str, Any]:
    """
    Generate a plan using LLM, parse it, and execute.
    
    Args:
        goal: User's high-level goal
        tool_executor: Function to execute each step
        llm_callable: Function to call LLM (takes prompt, returns text)
        
    Returns:
        Dict with plan, results, and formatted response
    """
    # Generate plan using LLM
    prompt = generate_llm_plan(goal)
    plan_text = llm_callable(prompt)
    
    # Parse the plan
    plan = parse_plan(plan_text)
    
    if not plan:
        return {
            "plan": [],
            "results": [],
            "response": "I couldn't generate a plan for that request.",
            "raw_plan": plan_text
        }
    
    # Execute the plan
    results = execute_plan(plan, tool_executor)
    response = format_plan_response(plan, results)
    
    return {
        "plan": plan,
        "results": results,
        "response": response,
        "raw_plan": plan_text
    }


# Convenience function that extracts plan from LLM response
def create_llm_planner_response_handler(ollama_url: str, model: str):
    """
    Create a handler function that can be used with the /chat endpoint.
    
    Args:
        ollama_url: URL of Ollama API
        model: Model name to use
        
    Returns:
        Callable that takes goal string and returns plan text
    """
    import requests
    
    def llm_callable(prompt: str) -> str:
        try:
            messages = [{"role": "user", "content": prompt}]
            payload = {"model": model, "messages": messages, "stream": False}
            r = requests.post(ollama_url, json=payload, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict):
                    msg = data.get("message", {})
                    if isinstance(msg, dict):
                        return msg.get("content", "")
            return ""
        except Exception as e:
            print(f"[LLM PLANNER] Error: {e}")
            return ""
    
    return llm_callable


if __name__ == "__main__":
    # Test the parser
    test_plan = """PLAN
1. open chrome
2. open notepad
3. open downloads"""
    
    steps = parse_plan(test_plan)
    print("Parsed steps:", steps)
    
    # Test executor with mock
    def mock_executor(action: str):
        return {"status": "ok", "message": f"Executed: {action}"}
    
    results = execute_plan(steps, mock_executor)
    print("Results:", results)

