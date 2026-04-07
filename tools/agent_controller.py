"""
VOID Agent Controller
Parses LLM responses to detect tool actions.
"""

import re
from typing import Optional, Dict, Any


def parse_action(response: str) -> Optional[Dict[str, Any]]:
    """
    Parse LLM response for ACTION/ARGS format.
    
    Expected formats:
    ACTION: open_app
    ARGS: chrome
    
    or
    
    ACTION: open_url
    ARGS: youtube.com
    
    Returns:
        dict: {"action": "tool_name", "args": {"param": "value"}} or None
    """
    if not response:
        return None
    
    response = response.strip()
    
    # Try ACTION: xxx / ARGS: yyy format
    action_match = re.search(r'ACTION:\s*(\w+)', response, re.IGNORECASE)
    args_match = re.search(r'ARGS:\s*(.+)', response, re.IGNORECASE)
    
    if action_match:
        action = action_match.group(1).strip().lower()
        args_text = args_match.group(1).strip() if args_match else ""
        
        # Build args dict
        args = {}
        if args_text:
            args["value"] = args_text  # Pass as single value argument
        
        return {"action": action, "args": args}
    
    # Try JSON format: {"type": "tool", "tool": "xxx", "args": {"url": "yyy"}}
    import json
    json_match = re.search(r'\{[^{}]+\}', response)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            if data.get("type") == "tool":
                return {
                    "action": data.get("tool", "").lower(),
                    "args": data.get("args", {})
                }
        except (json.JSONDecodeError, AttributeError):
            pass
    
    # Try simple keyword matching
    response_lower = response.lower()
    
    if "open" in response_lower and "youtube" in response_lower:
        return {"action": "open_url", "args": {"url": "https://youtube.com"}}
    
    if "open" in response_lower and "chrome" in response_lower:
        return {"action": "open_app", "args": {"app": "chrome"}}
    
    if "open" in response_lower and "notepad" in response_lower:
        return {"action": "open_app", "args": {"app": "notepad"}}
    
    if "system info" in response_lower:
        return {"action": "system_info", "args": {}}
    
    if "time" in response_lower:
        return {"action": "time", "args": {}}
    
    return None


def should_respond_with_action(user_message: str) -> bool:
    """
    Determine if user message likely needs an action.
    Used to help LLM decide when to use tools.
    """
    action_keywords = [
        "open", "start", "launch", "run",
        "search", "google", "find",
        "youtube", "watch", "play",
        "close", "quit", "exit",
        "shutdown", "restart", "lock",
        "time", "what time",
        "system info", "cpu", "memory", "ram",
    ]
    
    msg_lower = user_message.lower()
    return any(kw in msg_lower for kw in action_keywords)

