import logging
from typing import Dict, Any, List

logger = logging.getLogger("void.telegram_control")

# Mock Telegram Chats
MOCK_TELEGRAM_CHATS = {
    "mom": [
        {"sender": "mom", "content": "Mridul, did you have lunch yet? Eat on time dear.", "timestamp": "12:30 PM"}
    ],
    "sam_partner": [
        {"sender": "sam_partner", "content": "Hey, the retail sensor specs have been verified. Standard shipment is on schedule.", "timestamp": "02:15 PM"},
        {"sender": "sam_partner", "content": "Let me know when the seed call with John goes through.", "timestamp": "02:17 PM"}
    ]
}

def send_telegram_message(contact: str, message: str) -> Dict[str, Any]:
    """
    Simulates sending a Telegram message to a specific contact.
    """
    if not contact or not message:
        return {"status": "error", "message": "Telegram contact name and message body are required, Sir."}
        
    clean_contact = contact.lower().strip()
    try:
        logger.info(f"[TELEGRAM SEND] Contact: {clean_contact} | Message: {message}")
        
        # Add to mock chats
        if clean_contact not in MOCK_TELEGRAM_CHATS:
            MOCK_TELEGRAM_CHATS[clean_contact] = []
        MOCK_TELEGRAM_CHATS[clean_contact].append({
            "sender": "Mridul (You)",
            "content": message,
            "timestamp": "Just Now"
        })
        
        return {
            "status": "ok",
            "message": f"Telegram messaging isn't connected to a real account or bot yet. (Sandbox Mock: sent Telegram message to **{contact}**:\n\"{message}\")"
        }
    except Exception as e:
        logger.error(f"[TELEGRAM SEND] Failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to send Telegram message: {str(e)}"}

def read_telegram_messages(contact: str = None) -> Dict[str, Any]:
    """
    Reads recent Telegram messages, optionally filtering by contact name.
    """
    try:
        if contact:
            clean_contact = contact.lower().strip()
            if clean_contact not in MOCK_TELEGRAM_CHATS:
                return {
                    "status": "ok",
                    "message": f"Telegram message retrieval isn't connected to a real account or bot yet. (Sandbox Mock: no recent Telegram chats found with **{contact}**, Sir.)",
                    "data": []
                }
            messages = MOCK_TELEGRAM_CHATS[clean_contact]
            summary_lines = [f"Telegram message retrieval isn't connected to a real account or bot yet. (Sandbox Mock: recent Telegram messages from **{contact}**):\n"]
            for m in messages:
                summary_lines.append(f"[{m['timestamp']}] **{m['sender']}**: {m['content']}")
            return {
                "status": "ok",
                "message": "\n".join(summary_lines),
                "data": messages
            }
            
        # If no contact specified, summarize all unread chats
        summary_lines = ["Telegram message retrieval isn't connected to a real account or bot yet. (Sandbox Mock: active Telegram chats, Sir):\n"]
        all_chats = []
        for c, msgs in MOCK_TELEGRAM_CHATS.items():
            if msgs:
                last_msg = msgs[-1]
                summary_lines.append(f"- **{c}** (*{last_msg['sender']}* at {last_msg['timestamp']}):\n  \"{last_msg['content']}\"")
                all_chats.extend(msgs)
        return {
            "status": "ok",
            "message": "\n".join(summary_lines),
            "data": all_chats
        }
    except Exception as e:
        logger.error(f"[TELEGRAM READ] Failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to read Telegram chats: {str(e)}"}
