import logging
from typing import Dict, Any
from tools.email_helper import summarize_inbox, draft_reply

logger = logging.getLogger("void.email_control")

def send_email_message(to: str, body: str) -> Dict[str, Any]:
    """
    Simulates sending an email message to a contact in the sandbox environment.
    """
    if not to or not body:
        return {"status": "error", "message": "Email recipient ('to') and body content are required, Sir."}
        
    try:
        logger.info(f"[EMAIL SEND] Simulating outgoing email to {to}:\nContent: {body}")
        return {
            "status": "ok",
            "message": f"Successfully sent sandbox email to **{to}**:\n\"{body}\""
        }
    except Exception as e:
        logger.error(f"[EMAIL SEND] Failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to send email: {str(e)}"}

def read_email_inbox(sender: str = None) -> Dict[str, Any]:
    """
    Reads prioritize/unread emails in sandbox inbox, optionally filtering by sender name.
    """
    try:
        res = summarize_inbox()
        if res.get("status") == "error":
            return res
            
        posts = res.get("data", [])
        if sender:
            filtered = [p for p in posts if sender.lower() in p["sender"].lower()]
            if not filtered:
                return {
                    "status": "ok",
                    "message": f"You have no unread emails from **{sender}**, Sir.",
                    "data": []
                }
            
            summary_lines = [f"Here is a summary of unread emails from **{sender}**, Sir:\n"]
            for m in filtered:
                summary_lines.append(f"- **{m['category']}**:\n  \"{m['subject']}\" → *{m['body'][:120]}...*")
            return {
                "status": "ok",
                "message": "\n".join(summary_lines),
                "data": filtered
            }
            
        return res
    except Exception as e:
        logger.error(f"[EMAIL READ] Failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to read inbox: {str(e)}"}
