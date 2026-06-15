import sys
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "server"))

import tools.meeting_assistant as ma
from server.backend import memory_sqlite

def test_meeting():
    print("Starting meeting...")
    res = ma.start_meeting()
    print("Start status:", res)
    
    # Mock transcript
    ma._meeting_transcript = [
        "We are here to discuss project VOID.",
        "Mridul is the lead engineer and will fix the memory progress bar.",
        "The deadline is tomorrow.",
        "We decided to launch the product by next Monday."
    ]
    
    print("Stopping meeting...")
    res2 = ma.stop_meeting()
    print("Stop status:", res2)
    
    # Verify DB
    meetings = memory_sqlite.get_recent_meetings()
    print("\nRecent meetings in DB:")
    for m in meetings:
        print(f"- Title: {m['title']}, Date: {m['date_time']}")
        print(f"  Summary: {m['summary']}")
        
    items = memory_sqlite.get_pending_action_items()
    print("\nAction items in DB:")
    for item in items:
        print(f"- Task: {item['description']}, Owner: {item['owner']}, Deadline: {item['deadline']}")

if __name__ == "__main__":
    test_meeting()
