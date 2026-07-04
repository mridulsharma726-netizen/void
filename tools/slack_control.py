import logging
from typing import Dict, Any, List

logger = logging.getLogger("void.slack_control")

# Mock Slack Workspace Channels
MOCK_SLACK_WORKSPACE = {
    "general": [
        {"sender": "jane_admin", "content": "Welcome to the VOID workspace! Let's keep stabilizing, team.", "timestamp": "09:00 AM"}
    ],
    "marketing": [
        {"sender": "dan_marketer", "content": "Working on the newsletter design draft. Should have it ready by Wednesday.", "timestamp": "11:30 AM"}
    ],
    "leads": [
        {"sender": "sales_bot", "content": "New lead captured: pilot store manager from SuperMart Delhi.", "timestamp": "01:45 PM"}
    ]
}

def send_slack_message(channel: str, message: str) -> Dict[str, Any]:
    """
    Simulates sending a Slack message to a channel.
    """
    if not channel or not message:
        return {"status": "error", "message": "Slack channel name and message body are required, Sir."}
        
    clean_chan = channel.lstrip('#').lower().strip()
    try:
        logger.info(f"[SLACK SEND] Channel: #{clean_chan} | Message: {message}")
        
        # Add to mock channels
        if clean_chan not in MOCK_SLACK_WORKSPACE:
            MOCK_SLACK_WORKSPACE[clean_chan] = []
        MOCK_SLACK_WORKSPACE[clean_chan].append({
            "sender": "mridul_sharma (You)",
            "content": message,
            "timestamp": "Just Now"
        })
        
        return {
            "status": "ok",
            "message": f"Successfully posted to Slack channel **#{clean_chan}**:\n\"{message}\""
        }
    except Exception as e:
        logger.error(f"[SLACK SEND] Failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to send Slack message: {str(e)}"}

def read_slack_channel(channel: str) -> Dict[str, Any]:
    """
    Reads unread/recent Slack messages in a channel.
    """
    if not channel:
        return {"status": "error", "message": "Slack channel name is required, Sir."}
        
    clean_chan = channel.lstrip('#').lower().strip()
    try:
        if clean_chan not in MOCK_SLACK_WORKSPACE:
            return {
                "status": "ok",
                "message": f"Slack channel **#{clean_chan}** is inactive. No recent messages found.",
                "data": []
            }
        messages = MOCK_SLACK_WORKSPACE[clean_chan]
        summary_lines = [f"Here are recent messages in **#{clean_chan}**:\n"]
        for m in messages:
            summary_lines.append(f"[{m['timestamp']}] **{m['sender']}**: {m['content']}")
            
        return {
            "status": "ok",
            "message": "\n".join(summary_lines),
            "data": messages
        }
    except Exception as e:
        logger.error(f"[SLACK READ] Failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to read Slack channel: {str(e)}"}
