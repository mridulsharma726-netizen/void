import threading
import time
import json
import logging
import uuid
import datetime
from typing import Dict, Any, Optional

from tools.voice_listener import listen_for_command
from server.backend.llm_client import OllamaClient
from server.backend import memory_sqlite

logger = logging.getLogger("void.meeting_assistant")

_meeting_active = False
_meeting_thread: Optional[threading.Thread] = None
_meeting_transcript = []
_meeting_start_time = None

def _continuous_listen_loop():
    global _meeting_active, _meeting_transcript
    logger.info("Meeting assistant: Continuous listening started.")
    while _meeting_active:
        try:
            # Listen without wake word, long timeouts since it's continuous
            text = listen_for_command(timeout=10, phrase_time_limit=15)
            if text and _meeting_active:
                logger.info(f"[MEETING TRANSCRIPT] {text}")
                _meeting_transcript.append(text)
        except Exception as e:
            logger.error(f"Meeting listen error: {e}")
            time.sleep(1)
        time.sleep(0.1)

def start_meeting() -> Dict[str, Any]:
    """Starts the meeting continuous listening loop."""
    global _meeting_active, _meeting_thread, _meeting_transcript, _meeting_start_time
    
    if _meeting_active:
        return {"status": "error", "message": "A meeting is already active."}
        
    _meeting_active = True
    _meeting_transcript = []
    _meeting_start_time = datetime.datetime.now()
    
    _meeting_thread = threading.Thread(target=_continuous_listen_loop, daemon=True)
    _meeting_thread.start()
    
    return {"status": "ok", "message": "Meeting started. I am now listening continuously."}

def stop_meeting() -> Dict[str, Any]:
    """Stops the meeting, processes the transcript, and saves to memory."""
    global _meeting_active, _meeting_thread, _meeting_transcript
    
    if not _meeting_active:
        return {"status": "error", "message": "No active meeting to stop."}
        
    _meeting_active = False
    if _meeting_thread:
        _meeting_thread.join(timeout=2)
        
    if not _meeting_transcript:
        return {"status": "ok", "message": "Meeting ended. No speech was detected."}
        
    full_transcript = " ".join(_meeting_transcript)
    logger.info("Meeting ended. Processing transcript...")
    
    # Process transcript with LLM
    try:
        client = OllamaClient()
        system_prompt = """
You are an expert meeting assistant. Your task is to analyze the following meeting transcript and extract structured information.
Please return a JSON object with the following keys:
- "title": A short, descriptive title for the meeting.
- "participants": A list of inferred participants or roles.
- "topics": A list of main topics discussed.
- "decisions": A list of key decisions made.
- "action_items": A list of tasks assigned. Each task should be an object with "description", "owner" (if mentioned, otherwise ""), and "deadline" (if mentioned, otherwise "").
- "summary": A 2-5 sentence summary of the meeting.
Return ONLY valid JSON.
"""
        response = client.generate(
            prompt=full_transcript,
            system_prompt=system_prompt,
            format="json"
        )
        
        try:
            structured_data = json.loads(response)
        except json.JSONDecodeError:
            # Fallback if the LLM didn't return pure JSON
            logger.error("Failed to parse JSON from LLM response.")
            structured_data = {
                "title": "Untitled Meeting",
                "participants": [],
                "topics": [],
                "decisions": [],
                "action_items": [],
                "summary": "Failed to generate structured summary."
            }
            
        meeting_id = f"mtg_{uuid.uuid4().hex[:8]}"
        
        # Save meeting to DB
        memory_sqlite.save_meeting(
            meeting_id=meeting_id,
            title=structured_data.get("title", "Untitled Meeting"),
            participants=json.dumps(structured_data.get("participants", [])),
            transcript=full_transcript,
            structured_notes=json.dumps(structured_data),
            summary=structured_data.get("summary", "")
        )
        
        # Save action items
        action_items = structured_data.get("action_items", [])
        for item in action_items:
            memory_sqlite.add_action_item(
                meeting_id=meeting_id,
                description=item.get("description", ""),
                owner=item.get("owner", ""),
                deadline=item.get("deadline", "")
            )
        
        # Auto-link meeting to tracked projects
        linked_projects = []
        try:
            tracked = memory_sqlite.list_tracked_projects()
            transcript_lower = full_transcript.lower()
            title_lower = structured_data.get("title", "").lower()
            summary_lower = structured_data.get("summary", "").lower()
            search_text = f"{transcript_lower} {title_lower} {summary_lower}"
            
            for proj in tracked:
                proj_name_lower = proj["name"].lower()
                if proj_name_lower in search_text:
                    linked_projects.append(proj["name"])
                    logger.info(f"[MEETING] Auto-linked to project: {proj['name']}")
        except Exception as e:
            logger.warning(f"Project linking skipped: {e}")
        
        linked_msg = ""
        if linked_projects:
            linked_msg = f" Linked to project(s): {', '.join(linked_projects)}."
            
        return {
            "status": "ok", 
            "message": f"Meeting ended and saved as '{structured_data.get('title', 'Untitled Meeting')}'. {len(action_items)} action items recorded.{linked_msg}",
            "data": structured_data,
            "linked_projects": linked_projects
        }
        
    except Exception as e:
        logger.error(f"Error processing meeting: {e}")
        return {"status": "error", "message": f"Meeting ended but processing failed: {str(e)}"}

def recall_meeting(query: str = "") -> Dict[str, Any]:
    """Recalls recent or matching meetings."""
    if query:
        results = memory_sqlite.search_meetings(query)
    else:
        results = memory_sqlite.get_recent_meetings()
        
    if not results:
        return {"status": "ok", "message": "No meetings found matching your query."}
        
    formatted = "Here are the relevant meetings:\n"
    for r in results:
        formatted += f"- **{r['title']}** ({r['date_time']}): {r['summary']}\n"
        
    return {"status": "ok", "message": formatted, "meetings": results}

def get_action_items() -> Dict[str, Any]:
    """Retrieves pending action items."""
    items = memory_sqlite.get_pending_action_items()
    if not items:
        return {"status": "ok", "message": "You have no pending action items."}
        
    formatted = "Here are your pending action items:\n"
    for item in items:
        owner_str = f" [Owner: {item['owner']}]" if item['owner'] else ""
        deadline_str = f" [Due: {item['deadline']}]" if item['deadline'] else ""
        formatted += f"- {item['description']}{owner_str}{deadline_str}\n"
        
    return {"status": "ok", "message": formatted, "action_items": items}
