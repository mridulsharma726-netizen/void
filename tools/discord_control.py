import logging
from typing import Dict, Any, List

logger = logging.getLogger("void.discord_control")

# In-memory mock discord state
MOCK_DISCORD_CHANNELS = {
    "development": [
        {"sender": "alex_coder", "content": "Just pushed the new Electron preload updates. Please verify the CORS allowlist, Mridul.", "timestamp": "10:15 AM"},
        {"sender": "bot_linter", "content": "Build passing: 140 tests successful.", "timestamp": "10:18 AM"}
    ],
    "announcements": [
        {"sender": "mridul_sharma", "content": "VOID MK1 is currently in final stabilization review.", "timestamp": "09:00 AM"}
    ],
    "investor-pitch": [
        {"sender": "funding_guru", "content": "John Smith requested a pitch presentation deck about the pilot stores by this afternoon.", "timestamp": "Yesterday"}
    ]
}

def send_discord_message(channel: str, message: str) -> Dict[str, Any]:
    """
    Simulates sending a Discord message to a specific channel.
    """
    if not channel or not message:
        return {"status": "error", "message": "Discord channel name and message body are required, Sir."}
        
    clean_chan = channel.lstrip('#').lower()
    try:
        logger.info(f"[DISCORD SEND] Channel: #{clean_chan} | Message: {message}")
        
        # Add to mock channel history
        if clean_chan not in MOCK_DISCORD_CHANNELS:
            MOCK_DISCORD_CHANNELS[clean_chan] = []
        MOCK_DISCORD_CHANNELS[clean_chan].append({
            "sender": "mridul_sharma (You)",
            "content": message,
            "timestamp": "Just Now"
        })
        
        return {
            "status": "ok",
            "message": f"Successfully posted to Discord channel **#{clean_chan}**:\n\"{message}\""
        }
    except Exception as e:
        logger.error(f"[DISCORD SEND] Failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to send Discord message: {str(e)}"}

def read_discord_channel(channel: str) -> Dict[str, Any]:
    """
    Reads unread/recent messages in a Discord channel.
    """
    if not channel:
        return {"status": "error", "message": "Discord channel name is required, Sir."}
        
    clean_chan = channel.lstrip('#').lower()
    try:
        if clean_chan not in MOCK_DISCORD_CHANNELS:
            return {
                "status": "ok",
                "message": f"Channel **#{clean_chan}** is quiet, Sir. No new messages found.",
                "data": []
            }
            
        messages = MOCK_DISCORD_CHANNELS[clean_chan]
        summary_lines = [f"Here are recent messages in **#{clean_chan}**:\n"]
        for m in messages:
            summary_lines.append(f"[{m['timestamp']}] **{m['sender']}**: {m['content']}")
            
        return {
            "status": "ok",
            "message": "\n".join(summary_lines),
            "data": messages
        }
    except Exception as e:
        logger.error(f"[DISCORD READ] Failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to read Discord channel: {str(e)}"}
