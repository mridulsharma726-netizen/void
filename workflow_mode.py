import re
import time
from typing import Dict, Any, List

# Words that usually mean multi-step command
WORKFLOW_HINT_WORDS = [
    "then",
    "after that",
    "and then",
    "next",
    ",",
]

# Supported verbs
ACTION_VERBS = [
    "open",
    "start",
    "launch",
    "play",
    "search",
    "close",
    "run",
    "wait",
    "remember",
    "recall",
    "screenshot",
    "system",
    "send",
    "write",
    "type",
    "read",
    "check",
    "get",
    "create",
    "make",
    "delete",
    "remove",
    "clean",
    "find",
    "move",
    "arrange",
    "split",
    "tile",
    "cascade",
    "maximize",
    "minimize",
    "whatsapp",
    "download",
    "research",
    "investigate",
    "analyze",
    "spawn",
    "ask",
    "tell",
    "repair",
    "diagnose",
    "reply",
    "draft",
    "block",
    "schedule",
    "add",
    "plan",
    "view",
    "show",
]

# Quick URLs
COMMON_SITES = {
    "youtube": "https://youtube.com",
    "google": "https://google.com",
    "gmail": "https://mail.google.com",
    "instagram": "https://instagram.com",
    "facebook": "https://facebook.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "chatgpt": "https://chat.openai.com",
}

# App aliases
COMMON_APPS = {
    "notepad": "notepad",
    "notepad.exe": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "calc.exe": "calc",
    "paint": "mspaint",
    "cmd": "cmd",
    "terminal": "wt",
    "powershell": "powershell",
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
    "code": "code",
    "code.exe": "code",
}


def is_workflow_command(text: str) -> bool:
    """
    Detect if user message is a multi-step workflow command.
    Must have explicit workflow separators AND action verbs at clause boundaries.
    Avoids false positives on conversational text.
    """
    if not text:
        return False

    t = text.lower().strip()
    
    # Too short or too long for a workflow command
    if len(t) < 8 or len(t) > 300:
        return False
    
    # Conversational indicators — if present, it's probably NOT a command
    conversational_markers = [
        "?",  # Questions are never workflows
        "i think", "i feel", "i like", "i want to know",
        "can you tell", "what is", "what are", "why ",
        "how does", "how is", "who is", "who are",
        "please explain", "tell me about",
        "i was", "i am", "i have been", "we were",
    ]
    for marker in conversational_markers:
        if marker in t:
            return False

    # Must contain an explicit multi-step separator
    has_separator = any(sep in t for sep in [" then ", " and then ", " after that "])
    if not has_separator:
        # No separator: check if it has 2+ verbs at START of comma-separated clauses
        if "," not in t:
            return False
        clauses = [c.strip() for c in t.split(",") if c.strip()]
        verb_clauses = sum(1 for c in clauses if any(c.startswith(v + " ") or c == v for v in ACTION_VERBS))
        return verb_clauses >= 2
    
    # Has separator: verify at least one clause starts with an action verb
    parts = re.split(r'\bthen\b|\bafter that\b', t, flags=re.I)
    verb_parts = sum(1 for p in parts if any(p.strip().startswith(v + " ") or p.strip() == v for v in ACTION_VERBS))
    return verb_parts >= 1


def normalize_step(step: str) -> str:
    """
    If step has no verb, assume OPEN.
    """
    s = (step or "").strip()
    if not s:
        return ""

    low = s.lower().strip()

    for v in ACTION_VERBS:
        if low.startswith(v + " ") or low == v:
            return s

    return "open " + s


def split_into_steps(text: str) -> list[str]:
    """
    Split user workflow into steps.
    """
    t = (text or "").strip()
    if not t:
        return []

    # Normalize separators into "then"
    t = re.sub(r"\band then\b", " then ", t, flags=re.I)
    t = re.sub(r"\bafter that\b", " then ", t, flags=re.I)
    t = re.sub(r"\bnext\b", " then ", t, flags=re.I)

    # Split by then or commas
    if re.search(r"\bthen\b", t, flags=re.I):
        parts = re.split(r"\bthen\b", t, flags=re.I)
    else:
        parts = t.split(",")

    steps = []
    for p in parts:
        s = normalize_step(p.strip())
        if s:
            steps.append(s)

    return steps


def step_to_tool_step(step: str) -> dict:
    """
    Converts a text step into a workflow tool dict.
    """
    s = (step or "").strip()
    low = s.lower().strip()

    # WAIT
    if low.startswith("wait"):
        m = re.search(r"wait(\s+for)?\s+(\d+(\.\d+)?)", low)
        seconds = 1.0
        if m:
            seconds = float(m.group(2))
        return {"action": "wait", "seconds": seconds}

    # CLOSE
    if low.startswith("close "):
        target = s[6:].strip()
        target = COMMON_APPS.get(target.lower(), target)
        return {"action": "close_app", "app_name": target}

    # SEARCH
    if low.startswith("search "):
        query = s[7:].strip()
        return {"action": "search_web", "query": query}

    # PLAY
    if low.startswith("play "):
        query = s[5:].strip()
        query = re.sub(r"\bon youtube\b", "", query, flags=re.I).strip()
        return {"action": "play_youtube", "query": query}

    # SCREENSHOT
    if "screenshot" in low or "capture screen" in low:
        return {"action": "screenshot"}

    # SYSTEM INFO
    if "system info" in low or "system stats" in low or "cpu usage" in low:
        return {"action": "system_info"}

    # REMEMBER
    if low.startswith("remember "):
        content = s[9:].strip()
        return {"action": "remember", "content": content}

    # RECALL
    if low.startswith("recall "):
        query = s[7:].strip()
        return {"action": "recall", "query": query}

    # OPEN
    if low.startswith("open "):
        target = s[5:].strip()

        # site shortcut
        if target.lower() in COMMON_SITES:
            return {"action": "open_url", "url": COMMON_SITES[target.lower()]}

        # looks like domain
        if "." in target and " " not in target:
            if not target.lower().startswith("http"):
                return {"action": "open_url", "url": "https://" + target}
            return {"action": "open_url", "url": target}

        # app
        app = COMMON_APPS.get(target.lower(), target)
        return {"action": "open_app", "app_name": app}

    # fallback: treat as app
    return {"action": "open_app", "app_name": COMMON_APPS.get(low, s)}


def build_workflow_steps(text: str) -> list[dict]:
    """
    Full pipeline:
      user text -> split -> normalize -> convert to tool steps
    """
    raw_steps = split_into_steps(text)
    tool_steps = [step_to_tool_step(x) for x in raw_steps]
    return tool_steps


def execute_workflow_text(text: str, tools: dict) -> dict:
    """
    Parse a multi-step text command and execute it through the WorkflowEngine.
    
    Args:
        text: Multi-step command like "open chrome then search cats"
        tools: Dict of tool functions for the engine
        
    Returns:
        Workflow execution result dict
    """
    if not is_workflow_command(text):
        return {"ok": False, "error": "Not a workflow command"}
    
    steps = split_into_steps(text)
    if not steps:
        return {"ok": False, "error": "No steps found"}
    
    from workflows.workflow_engine import WorkflowEngine
    engine = WorkflowEngine(tools)
    
    workflow_id = f"text_workflow_{int(time.time())}"
    return engine.run_workflow(workflow_id, steps)
