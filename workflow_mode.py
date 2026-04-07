import re

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
    Detect if user message is a workflow command.
    """
    if not text:
        return False

    t = text.lower().strip()

    # Contains workflow separators + action verbs
    for w in WORKFLOW_HINT_WORDS:
        if w in t and any(v in t for v in ACTION_VERBS):
            return True

    # Or contains 2+ verbs
    count = sum(1 for v in ACTION_VERBS if v in t)
    return count >= 2


def normalize_step(step: str) -> str:
    """
    If step has no verb, assume OPEN.

    Examples:
      "notepad" -> "open notepad"
      "youtube" -> "open youtube"
    """
    s = (step or "").strip()
    if not s:
        return ""

    low = s.lower().strip()

    for v in ACTION_VERBS:
        if low.startswith(v + " "):
            return s

    return "open " + s


def split_into_steps(text: str) -> list[str]:
    """
    Split user workflow into steps.

    IMPORTANT:
    We do NOT replace generic "and" because it can break song names.
    We only replace:
      - "and then"
      - "after that"
      - "next"
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

    Returns one of:
      {"action":"open_url","url":"..."}
      {"action":"open_app","app":"..."}
      {"action":"close_app","app":"..."}
      {"action":"search_google","query":"..."}
      {"action":"play_youtube","query":"..."}
      {"action":"wait","seconds":2}
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
        target = low.replace("close ", "", 1).strip()
        target = COMMON_APPS.get(target, target)
        return {"action": "close_app", "app": target}

    # SEARCH
    if low.startswith("search "):
        query = low.replace("search ", "", 1).strip()
        return {"action": "search_google", "query": query}

    # PLAY
    if low.startswith("play "):
        query = low.replace("play ", "", 1).strip()
        query = re.sub(r"\bon youtube\b", "", query, flags=re.I).strip()
        return {"action": "play_youtube", "query": query}

    # OPEN
    if low.startswith("open "):
        target = low.replace("open ", "", 1).strip()

        # site shortcut
        if target in COMMON_SITES:
            return {"action": "open_url", "url": COMMON_SITES[target]}

        # looks like domain
        if "." in target and " " not in target:
            if not target.startswith("http"):
                return {"action": "open_url", "url": "https://" + target}
            return {"action": "open_url", "url": target}

        # app
        app = COMMON_APPS.get(target, target)
        return {"action": "open_app", "app": app}

    # fallback: treat as app
    return {"action": "open_app", "app": COMMON_APPS.get(low, low)}


def build_workflow_steps(text: str) -> list[dict]:
    """
    Full pipeline:
      user text -> split -> normalize -> convert to tool steps
    """
    raw_steps = split_into_steps(text)
    tool_steps = [step_to_tool_step(x) for x in raw_steps]
    return tool_steps
