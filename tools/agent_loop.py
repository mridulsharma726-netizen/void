"""
VOID Agent Loop Module
=====================

Executes plans step-by-step and evaluates results with reflection.

Functions:
- run_agent_loop(steps, tool_executor) -> List[dict]
- reflect_on_results(results) -> List[str]
- format_execution_summary(plan, results) -> str
"""

from typing import List, Dict, Any, Callable
import time


def run_agent_loop(steps: List[str], tool_executor: Callable[[str], Dict[str, Any]], 
                   delay_between: float = 0.5) -> List[Dict[str, Any]]:
    """
    Execute a plan step-by-step and collect results.
    
    Args:
        steps: List of action strings to execute
        tool_executor: Function that takes an action string and returns a result dict
        delay_between: Seconds to wait between steps (default 0.5)
        
    Returns:
        List of result dictionaries with step, result, and status
    """
    results = []
    
    for i, step in enumerate(steps):
        print(f"[AGENT LOOP] Step {i+1}/{len(steps)}: {step}")
        
        step_result = {
            "step": step,
            "step_number": i + 1,
            "total_steps": len(steps),
            "timestamp": time.time()
        }
        
        try:
            # Execute the step
            result = tool_executor(step)
            
            # Determine status based on result
            if isinstance(result, dict):
                status = result.get("status", "unknown")
                if status in ["ok", "success"]:
                    step_result["status"] = "success"
                elif status in ["error", "failed"]:
                    step_result["status"] = "failed"
                else:
                    step_result["status"] = "unknown"
                step_result["result"] = result
            else:
                step_result["status"] = "success"
                step_result["result"] = {"status": "ok", "message": str(result)}
                
        except Exception as e:
            step_result["status"] = "failed"
            step_result["result"] = {"status": "error", "message": str(e)}
            print(f"[AGENT LOOP] Step {i+1} failed: {e}")
        
        results.append(step_result)
        
        # Small delay between steps
        if delay_between > 0 and i < len(steps) - 1:
            time.sleep(delay_between)
    
    return results


def reflect_on_results(results: List[Dict[str, Any]]) -> List[str]:
    """
    Generate a human-readable summary of execution results.
    
    Args:
        results: List of result dictionaries from run_agent_loop
        
    Returns:
        List of summary strings for each step
    """
    summary = []
    
    for r in results:
        step = r.get("step", "unknown step")
        status = r.get("status", "unknown")
        
        if status == "success":
            summary.append(f"✓ {step} - completed")
        elif status == "failed":
            result = r.get("result", {})
            error_msg = result.get("message", "Unknown error") if isinstance(result, dict) else str(result)
            summary.append(f"✗ {step} - failed: {error_msg}")
        else:
            summary.append(f"? {step} - {status}")
    
    return summary


def get_execution_stats(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Get statistics about the execution.
    
    Args:
        results: List of result dictionaries
        
    Returns:
        Dict with success/failure counts
    """
    total = len(results)
    success = sum(1 for r in results if r.get("status") == "success")
    failed = sum(1 for r in results if r.get("status") == "failed")
    unknown = total - success - failed
    
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "unknown": unknown,
        "success_rate": (success / total * 100) if total > 0 else 0
    }


def format_execution_summary(plan: List[str], results: List[Dict[str, Any]]) -> str:
    """
    Format a complete execution summary.
    
    Args:
        plan: The original plan steps
        results: Results from run_agent_loop
        
    Returns:
        Formatted string summary
    """
    if not plan:
        return "No plan to execute."
    
    stats = get_execution_stats(results)
    summary_lines = reflect_on_results(results)
    
    # Build response
    response = f"Execution: {stats['success']}/{stats['total']} steps completed"
    
    if stats['failed'] > 0:
        response += f" ({stats['failed']} failed)"
    
    response += "\n\n"
    response += "Results:\n"
    response += "\n".join([f"  {line}" for line in summary_lines])
    
    return response


def retry_failed_steps(results: List[Dict[str, Any]], tool_executor: Callable[[str], Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Retry any failed steps in a result set.
    
    Args:
        results: Original results from run_agent_loop
        tool_executor: Function to execute steps
        
    Returns:
        Updated results with retries
    """
    updated_results = []
    
    for r in results:
        if r.get("status") == "failed":
            # Retry the step
            step = r.get("step")
            print(f"[AGENT LOOP] Retrying failed step: {step}")
            
            try:
                result = tool_executor(step)
                r["result"] = result
                r["status"] = "success" if result.get("status") in ["ok", "success"] else "failed"
                r["retried"] = True
            except Exception as e:
                r["result"] = {"status": "error", "message": str(e)}
                r["status"] = "failed"
                r["retried"] = True
        
        updated_results.append(r)
    
    return updated_results


# Convenience function for simple execution
def execute_with_reflection(steps: List[str], tool_executor: Callable[[str], Dict[str, Any]]) -> Dict[str, Any]:
    """
    Execute steps and return results with reflection summary.
    
    Args:
        steps: List of action strings
        tool_executor: Function to execute each step
        
    Returns:
        Dict with plan, results, summary, and stats
    """
    results = run_agent_loop(steps, tool_executor)
    summary = reflect_on_results(results)
    stats = get_execution_stats(results)
    
    return {
        "plan": steps,
        "results": results,
        "summary": summary,
        "stats": stats,
        "formatted": format_execution_summary(steps, results)
    }


if __name__ == "__main__":
    # Test the agent loop
    def mock_executor(action: str):
        return {"status": "ok", "message": f"Executed: {action}"}
    
    test_steps = ["open chrome", "open notepad", "open downloads"]
    results = run_agent_loop(test_steps, mock_executor)
    
    print("Results:", results)
    print("\nSummary:", reflect_on_results(results))
    print("\nFormatted:", format_execution_summary(test_steps, results))

