"""
VOID Core Intent Router Module
===============================

Provides detect_intent_and_params() function for the workflow engine.
Bridges to the existing server/backend/intent_router.py IntentRouter class.

Used by: workflows/workflow_engine.py
"""

import re
import sys
import os
from typing import Dict, Any, Optional
from pathlib import Path

# Ensure server path is available
ROOT_DIR = Path(__file__).parent.parent
SERVER_DIR = ROOT_DIR / "server"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))


# Intent patterns for synchronous detection (no LLM needed)
INTENT_PATTERNS = {
    "open_app": [
        r"^open\s+(.+)$",
        r"^start\s+(.+)$",
        r"^launch\s+(.+)$",
        r"^run\s+(.+)$",
    ],
    "close_app": [
        r"^close\s+(.+)$",
        r"^kill\s+(.+)$",
        r"^stop\s+(.+)$",
        r"^exit\s+(.+)$",
    ],
    "search_web": [
        r"^search\s+(?:for\s+)?(.+)$",
        r"^google\s+(.+)$",
        r"^look\s+up\s+(.+)$",
    ],
    "open_url": [
        r"^(?:open\s+)?(?:url\s+)?(https?://\S+)$",
        r"^go\s+to\s+(https?://\S+)$",
        r"^(?:open\s+)?(www\.\S+)$",
        r"^(?:open\s+)?(\S+\.com\S*)$",
        r"^(?:open\s+)?(\S+\.org\S*)$",
        r"^(?:open\s+)?(\S+\.io\S*)$",
    ],
    "play_youtube": [
        r"^(?:play|youtube)\s+(.+)$",
        r"^play\s+on\s+youtube\s+(.+)$",
    ],
    "time": [
        r"^(?:what\s+)?time$",
        r"^what\s+(?:is\s+)?(?:the\s+)?time$",
        r"^current\s+time$",
    ],
    "system_info": [
        r"^system\s+info(?:rmation)?$",
        r"^(?:show\s+)?(?:system\s+)?stats$",
        r"^cpu\s+usage$",
        r"^ram\s+usage$",
        r"^memory\s+usage$",
    ],
    "screenshot": [
        r"^(?:take\s+)?(?:a\s+)?screenshot$",
        r"^capture\s+screen$",
        r"^screen\s+capture$",
    ],
    "remember": [
        r"^remember\s+(.+)$",
        r"^save\s+note\s+(.+)$",
    ],
    "recall": [
        r"^recall\s+(.+)$",
        r"^show\s+memory$",
        r"^what\s+do\s+you\s+remember$",
    ],
    "wait": [
        r"^wait\s+(\d+)\s*(?:seconds?|s)?$",
        r"^pause\s+(\d+)\s*(?:seconds?|s)?$",
    ],
}

# Parameter extraction mapping
PARAM_KEYS = {
    "open_app": "app_name",
    "close_app": "app_name",
    "search_web": "query",
    "open_url": "url",
    "play_youtube": "query",
    "screenshot": None,
    "time": None,
    "system_info": None,
    "remember": "content",
    "recall": "query",
    "wait": "seconds",
}


def detect_intent_and_params(text: str) -> Dict[str, Any]:
    """
    Detect intent and extract parameters from user text.
    
    Bridges dynamically to the main FastAPI rule-based intent router
    to avoid duplication of regex patterns and parameter maps.
    
    Args:
        text: User input text
        
    Returns:
        Dict with 'intent' and 'parameters' keys:
        {
            "intent": "open_app",
            "parameters": {"app_name": "chrome"}
        }
    """
    text_clean = text.strip().lower()
    
    if not text_clean:
        return {"intent": "unknown", "parameters": {}}
    
    try:
        from backend.intent_router import IntentRouter
        router = IntentRouter(use_llm_fallback=False)
        res = router._classify_rules(text_clean, text)
        
        if res and res.intent in ["command", "system", "academic"]:
            # Retrieve intent and action details
            action = res.action
            if not action and res.intent == "academic":
                action = "academic"
            
            # Map legacy names if they differ
            if action == "repair":
                action = "repair_self"
                
            params = dict(res.params) if res.params else {}
            
            # Compatibility mapping for parameter keys (e.g. app -> app_name)
            if "app" in params:
                params["app_name"] = params["app"]
                
            return {
                "intent": action,
                "parameters": params
            }
        elif res and res.intent == "chat":
            return {"intent": "chat", "parameters": {}}
            
    except Exception as e:
        # Fallback to local legacy matching if imports fail
        pass
    
    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            match = re.match(pattern, text_clean, re.IGNORECASE)
            if match:
                params = {}
                param_key = PARAM_KEYS.get(intent)
                
                if param_key and match.groups():
                    params[param_key] = match.group(1).strip()
                
                return {
                    "intent": intent,
                    "parameters": params
                }
    
    # Fallback: check for simple keywords
    keyword_intents = {
        "time": ["time", "clock"],
        "system_info": ["system info", "stats", "cpu", "ram"],
        "screenshot": ["screenshot", "screen capture"],
    }
    
    for intent, keywords in keyword_intents.items():
        for keyword in keywords:
            if keyword in text_clean:
                return {"intent": intent, "parameters": {}}
    
    # No match — return unknown
    return {"intent": "unknown", "parameters": {}}
