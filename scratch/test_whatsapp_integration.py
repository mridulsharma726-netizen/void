import sys
from pathlib import Path
import re

ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))
sys.path.append(str(ROOT_DIR / "server"))

# Let's define the new patterns exactly as we want them in intent_router.py
PREFIX = r"^(?:please\s+|can\s+you\s+|do\s+one\s+thing\s+(?:and\s+)?|go\s+ahead\s+and\s+|void\s+)?"
SUFFIX = r"\s*(?:please|sir)?$"

COMMAND_PATTERNS = {
    "send_whatsapp": [
        PREFIX + r"(?:send|write|type)\s+(?:a\s+)?(?:whatsapp(?:\s+message)?|message)(?:\s+on\s+whatsapp)?\s+(?:to\s+)?([a-zA-Z0-9\s]+)\s+(?:saying|with|text)\s+(.+)" + SUFFIX,
        PREFIX + r"(?:send|write|type)\s+(?:a\s+)?(?:whatsapp(?:\s+message)?|message)(?:\s+on\s+whatsapp)?\s+(?:to\s+)?([a-zA-Z0-9\s]+)\s*:\s*(.+)" + SUFFIX,
        PREFIX + r"(?:whatsapp|message)\s+(?:to\s+)?([a-zA-Z0-9\s]+)\s+(?:saying|with|text)\s+(.+)" + SUFFIX,
    ],
    "read_whatsapp": [
        PREFIX + r"(?:read|check|show|get)\s+(?:my\s+)?(?:unread\s+)?(?:messages|chats|whatsapp)(?:\s+(?:on|in|from)\s+whatsapp)?" + SUFFIX,
        PREFIX + r"(?:read|check|show|get)\s+(?:my\s+)?(?:whatsapp)\s+(?:unread\s+)?(?:messages|chats)" + SUFFIX,
        PREFIX + r"(?:open\s+)?whatsapp\s+(?:and\s+)?(?:read|check|show|get)\s+(?:my\s+)?(?:unread\s+)?(?:messages|chats)" + SUFFIX
    ]
}

def parse_params(action: str, match, raw: str):
    groups = match.groups()
    if action == "send_whatsapp":
        contact_val = groups[0].strip() if groups and groups[0] else ""
        message_val = groups[1].strip() if len(groups) > 1 and groups[1] else ""
        return {"contact": contact_val, "message": message_val}
    return {}

def classify(text: str):
    lower = text.lower().strip()
    for action, patterns in COMMAND_PATTERNS.items():
        for pat in patterns:
            match = re.search(pat, lower)
            if match:
                return action, parse_params(action, match, text)
    return "chat", {}

def main():
    # 1. Test parsing read_whatsapp
    test_reads = [
        "check my whatsapp messages",
        "read my unread messages on whatsapp",
        "open whatsapp and read my unread chats",
        "check my unread messages",
        "get my whatsapp messages",
    ]
    
    print("--- TESTING READ PATTERNS ---")
    for msg in test_reads:
        action, params = classify(msg)
        print(f"Msg: '{msg}' -> Action: {action}, Params: {params}")

    # 2. Test parsing send_whatsapp
    test_sends = [
        "send a whatsapp to Papa saying Hello VOID works",
        "send a message on whatsapp to Mridul Sharma text I am here",
        "send a whatsapp message to John saying let's meet at 5?",
        "write a whatsapp to Alice saying how are you doing today sir?",
        "send a whatsapp to Bob: please call me",
        "whatsapp Charlie saying call me when free",
    ]
    
    print("\n--- TESTING SEND PATTERNS ---")
    for msg in test_sends:
        action, params = classify(msg)
        print(f"Msg: '{msg}' -> Action: {action}, Params: {params}")

if __name__ == "__main__":
    main()
