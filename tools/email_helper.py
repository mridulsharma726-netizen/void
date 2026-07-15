import logging
from typing import Dict, Any, List

logger = logging.getLogger("void.email_helper")

# Simulated High-Priority Inbox
MOCK_INBOX = [
    {
        "id": "mail_101",
        "sender": "John Smith <john.invest@venturecapital.com>",
        "subject": "Smart Cart Deck - Introductory Call Request",
        "body": "Hey Mridul, I read the Smart Cart pitch deck and loved your early pilot store performance metrics (35% time reduction is impressive). Are you open for a quick 15-minute introductory call this Thursday at 2:00 PM EST to discuss seed terms?",
        "priority": "HIGH",
        "category": "Investor Inquiry"
    },
    {
        "id": "mail_102",
        "sender": "production@smartcart-verify.cn",
        "subject": "BATCH VERIFICATION: Smart Cart Sensor Arrays Ready",
        "body": "Dear Sharma, we have successfully assembled the hardware sensor arrays for the Smart Cart Pilot Store batch (50 units). Please review the specs and verify the shipment address so we can ship out by this Friday.",
        "priority": "HIGH",
        "category": "Supplier Operations"
    },
    {
        "id": "mail_103",
        "sender": "SkipIt Support <support@skipit.co>",
        "subject": "BUG REPORT: Dark Mode Slider Contrast Glitch",
        "body": "Hi Mridul, a user flagged a visual glitch on the SkipIt rental slider when selecting tools in dark mode. The glassmorphic slider background overrides white text contrast on high-res monitors. Please review.",
        "priority": "MEDIUM",
        "category": "Product Bug"
    },
    {
        "id": "mail_104",
        "sender": "Retail Tech Digest <newsletter@retaildigest.com>",
        "subject": "Top 10 Brick-and-Mortar Retail Trends of 2026",
        "body": "Explore the latest insights on RFID tracking, smart checkouts, and mobile POS systems that are taking over commercial hubs this fiscal year.",
        "priority": "LOW",
        "category": "Newsletter"
    }
]

def summarize_inbox() -> Dict[str, Any]:
    """Retrieve prioritized unread emails from the mock mailbox."""
    try:
        # Group by priority
        high = [m for m in MOCK_INBOX if m["priority"] == "HIGH"]
        med = [m for m in MOCK_INBOX if m["priority"] == "MEDIUM"]
        low = [m for m in MOCK_INBOX if m["priority"] == "LOW"]
        
        summary_lines = [
            "Email management is currently using a mock sandbox inbox with hardcoded developer emails and is not connected to a live mail account. (Sandbox Mock)\n\n"
            "Here is a summary of your priority inbox, Sir:\n"
        ]
        
        if high:
            summary_lines.append("🔴 **HIGH PRIORITY**:")
            for m in high:
                summary_lines.append(f"- **{m['category']}** from *{m['sender']}*:\n  \"{m['subject']}\" → *{m['body'][:120]}...*")
                
        if med:
            summary_lines.append("\n🟡 **MEDIUM PRIORITY**:")
            for m in med:
                summary_lines.append(f"- **{m['category']}** from *{m['sender']}*:\n  \"{m['subject']}\" → *{m['body'][:120]}...*")
                
        if low:
            summary_lines.append("\n🟢 **LOW PRIORITY**:")
            for m in low:
                summary_lines.append(f"- **{m['category']}** from *{m['sender']}*:\n  \"{m['subject']}\"")
                
        return {
            "status": "ok",
            "message": "\n".join(summary_lines),
            "data": MOCK_INBOX
        }
    except Exception as e:
        logger.error(f"Inbox summarization failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Inbox summary failed: {str(e)}"}

def draft_reply(email_id: str, instructions: str) -> Dict[str, Any]:
    """Draft a highly professional response to a specific sandbox email based on instructions."""
    try:
        target_mail = None
        for m in MOCK_INBOX:
            if m["id"] == email_id:
                target_mail = m
                break
                
        if not target_mail:
            return {"status": "error", "message": f"Could not find email ID '{email_id}', Sir."}
            
        # Standard professional response template generator
        draft = ""
        if email_id == "mail_101": # John Smith (Investor)
            draft = (
                f"Subject: Re: {target_mail['subject']}\n\n"
                f"Hi John,\n\n"
                f"Thanks for reaching out and for your kind words regarding the Smart Cart deck and our pilot metrics. "
                f"I would be delighted to connect. Thursday at 2:00 PM EST works perfectly for me. "
                f"Please let me know if you would like me to set up a calendar link or send over a meeting invite.\n\n"
                f"Looking forward to our conversation.\n\n"
                f"Best regards,\n"
                f"Mridul Sharma"
            )
        elif email_id == "mail_102": # China Supplier
            draft = (
                f"Subject: Re: {target_mail['subject']}\n\n"
                f"Dear Operations Team,\n\n"
                f"Thank you for the update. I have reviewed the batch specifications for the 50 sensor arrays and everything looks excellent. "
                f"Please ship the batch to the following address:\n"
                f"VOID Technology Labs, Mridul Sharma, 12 Corporate Hub, New Delhi, India.\n\n"
                f"Please send over the tracking number once the container is shipped.\n\n"
                f"Best regards,\n"
                f"Mridul Sharma"
            )
        else: # Default draft
            draft = (
                f"Subject: Re: {target_mail['subject']}\n\n"
                f"Hi there,\n\n"
                f"Thank you for reaching out. I have received your message regarding: '{instructions}'. "
                f"I will look into this immediately and get back to you shortly.\n\n"
                f"Best,\n"
                f"Mridul Sharma"
            )
            
        return {
            "status": "ok",
            "message": f"Email management is currently using a mock sandbox inbox with hardcoded developer emails and is not connected to a live mail account. (Sandbox Mock)\n\nDraft compiled successfully, Sir. Here is the drafted response to **{target_mail['sender']}**:\n\n```text\n{draft}\n```",
            "data": {"draft": draft, "to": target_mail["sender"]}
        }
    except Exception as e:
        logger.error(f"Email draft failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to draft email: {str(e)}"}
