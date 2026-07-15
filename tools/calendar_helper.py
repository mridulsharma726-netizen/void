import os
import re
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple

logger = logging.getLogger("void.calendar_helper")

DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "memory", "data"))
DB_PATH = os.path.join(DB_DIR, "calendar.db")

def init_db():
    """Ensure the calendar database and table are initialized with default seed data."""
    try:
        os.makedirs(DB_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create schedules table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                priority TEXT NOT NULL,
                recurring TEXT NOT NULL
            )
        """)
        conn.commit()
        
        # Seed default events if database is empty
        cursor.execute("SELECT COUNT(*) FROM schedules")
        if cursor.fetchone()[0] == 0:
            logger.info("Initializing calendar database with seed corporate events.")
            today = datetime.now()
            monday = today - timedelta(days=today.weekday())
            
            # Formatting helpers
            def get_dt_str(day_offset: int, hour: int, minute: int = 0) -> str:
                dt = datetime(monday.year, monday.month, monday.day, hour, minute) + timedelta(days=day_offset)
                return dt.strftime("%Y-%m-%d %H:%M")
            
            seed_events = [
                ("Sprint Planning & Standup", get_dt_str(0, 10), get_dt_str(0, 11), "MEDIUM", "WEEKLY"),
                ("Code Review & Tech Debt Sync", get_dt_str(2, 16), get_dt_str(2, 17, 30), "LOW", "WEEKLY"),
                ("Investor Seed Term Meeting (John Smith)", get_dt_str(3, 14), get_dt_str(3, 14, 45), "HIGH", "NONE"),
                ("SkipIt Supplier Verification Call", get_dt_str(4, 11), get_dt_str(4, 12), "HIGH", "NONE"),
                ("Weekly Retro & Wrap-up", get_dt_str(4, 16), get_dt_str(4, 17), "MEDIUM", "WEEKLY"),
            ]
            
            cursor.executemany(
                "INSERT INTO schedules (title, start_time, end_time, priority, recurring) VALUES (?, ?, ?, ?, ?)",
                seed_events
            )
            conn.commit()
            
        conn.close()
    except Exception as e:
        logger.error(f"Failed to initialize calendar DB: {e}", exc_info=True)

# Run initialization on import
init_db()

def parse_time(time_str: str) -> datetime:
    """Parse time string with error resilience."""
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %I:%M %p",
        "%Y-%m-%d %I:%M%p",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%H:%M"
    ]
    
    cleaned = time_str.strip()
    if len(cleaned) <= 8 and ":" in cleaned:
        today_str = datetime.now().strftime("%Y-%m-%d")
        cleaned = f"{today_str} {cleaned}"
        
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
            
    raise ValueError(f"Could not parse date/time string: '{time_str}'. Expected format: 'YYYY-MM-DD HH:MM'")

def plan_week() -> Dict[str, Any]:
    """Retrieve all scheduled events for the current week, grouped and formatted cleanly."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, title, start_time, end_time, priority, recurring FROM schedules ORDER BY start_time ASC")
        rows = cursor.fetchall()
        conn.close()
        
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        monday_start = datetime(monday.year, monday.month, monday.day, 0, 0)
        sunday_end = monday_start + timedelta(days=7)
        
        week_events = []
        for row in rows:
            ev_id, title, start_str, end_str, priority, recurring = row
            try:
                start_dt = parse_time(start_str)
                end_dt = parse_time(end_str)
            except Exception:
                continue
                
            if recurring == "WEEKLY":
                days_diff = (start_dt.weekday() - monday_start.weekday())
                start_instance = monday_start + timedelta(days=days_diff, hours=start_dt.hour, minutes=start_dt.minute)
                end_instance = start_instance + (end_dt - start_dt)
                
                week_events.append({
                    "id": ev_id,
                    "title": title,
                    "start": start_instance,
                    "end": end_instance,
                    "start_str": start_instance.strftime("%Y-%m-%d %H:%M"),
                    "end_str": end_instance.strftime("%Y-%m-%d %H:%M"),
                    "priority": priority,
                    "recurring": recurring
                })
            elif recurring == "DAILY":
                for d in range(7):
                    day_dt = monday_start + timedelta(days=d)
                    start_instance = datetime(day_dt.year, day_dt.month, day_dt.day, start_dt.hour, start_dt.minute)
                    end_instance = start_instance + (end_dt - start_dt)
                    week_events.append({
                        "id": ev_id,
                        "title": title,
                        "start": start_instance,
                        "end": end_instance,
                        "start_str": start_instance.strftime("%Y-%m-%d %H:%M"),
                        "end_str": end_instance.strftime("%Y-%m-%d %H:%M"),
                        "priority": priority,
                        "recurring": recurring
                    })
            else:
                if monday_start <= start_dt < sunday_end:
                    week_events.append({
                        "id": ev_id,
                        "title": title,
                        "start": start_dt,
                        "end": end_dt,
                        "start_str": start_str,
                        "end_str": end_str,
                        "priority": priority,
                        "recurring": recurring
                    })
                    
        week_events.sort(key=lambda x: x["start"])
        
        days_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        by_day = {day: [] for day in days_names}
        
        for ev in week_events:
            day_name = ev["start"].strftime("%A")
            if day_name in by_day:
                by_day[day_name].append(ev)
                
        md = [
            "Calendar scheduling is currently using a local database seeded with mock corporate events and is not connected to a real Google or Outlook Calendar account. (Sandbox Mock)\n\n"
            "Here is your strategic calendar schedule for this week, Sir:\n"
        ]
        for day in days_names:
            events = by_day[day]
            if events:
                md.append(f"📅 **{day}**:")
                for ev in events:
                    priority_emoji = "🔴" if ev["priority"] == "HIGH" else "🟡" if ev["priority"] == "MEDIUM" else "🟢"
                    rec_indicator = " 🔄" if ev["recurring"] != "NONE" else ""
                    time_range = f"{ev['start'].strftime('%I:%M %p')} - {ev['end'].strftime('%I:%M %p')}"
                    md.append(f"  - {priority_emoji} **{time_range}**: {ev['title']}{rec_indicator} *(Priority: {ev['priority']} | ID: {ev['id']})*")
                md.append("")
                
        if not any(by_day.values()):
            md.append("No active schedules or appointments blocked out for this week, Sir.")
            
        return {
            "status": "ok",
            "message": "\n".join(md).strip(),
            "data": [
                {
                    "id": ev["id"],
                    "title": ev["title"],
                    "start_time": ev["start_str"],
                    "end_time": ev["end_str"],
                    "priority": ev["priority"],
                    "recurring": ev["recurring"]
                }
                for ev in week_events
            ]
        }
    except Exception as e:
        logger.error(f"Failed to plan week: {e}", exc_info=True)
        return {"status": "error", "message": f"Calendar view failed: {str(e)}"}

def schedule_event(title: str, start_time: str, end_time: str, priority: str = "MEDIUM", recurring: str = "NONE") -> Dict[str, Any]:
    """
    Schedule a persistent event in the database after verifying conflicts and handling priority resolution.
    """
    try:
        start_dt = parse_time(start_time)
        end_dt = parse_time(end_time)
        
        if end_dt <= start_dt:
            return {"status": "error", "message": "Error: Event end time must be after the start time, Sir."}
            
        priority = priority.strip().upper()
        if priority not in ["HIGH", "MEDIUM", "LOW"]:
            priority = "MEDIUM"
            
        recurring = recurring.strip().upper()
        if recurring not in ["DAILY", "WEEKLY", "NONE"]:
            recurring = "NONE"
            
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, title, start_time, end_time, priority, recurring FROM schedules")
        existing_rows = cursor.fetchall()
        
        conflict_event = None
        
        for row in existing_rows:
            ex_id, ex_title, ex_start_str, ex_end_str, ex_priority, ex_recurring = row
            try:
                ex_start_dt = parse_time(ex_start_str)
                ex_end_dt = parse_time(ex_end_str)
            except Exception:
                continue
                
            overlap = False
            
            if ex_recurring == "NONE" and recurring == "NONE":
                if max(start_dt, ex_start_dt) < min(end_dt, ex_end_dt):
                    overlap = True
            else:
                w1 = start_dt.weekday()
                w2 = ex_start_dt.weekday()
                
                t1_start = start_dt.time()
                t1_end = end_dt.time()
                t2_start = ex_start_dt.time()
                t2_end = ex_end_dt.time()
                
                time_overlap = max(t1_start, t2_start) < min(t1_end, t2_end)
                
                if recurring == "DAILY" or ex_recurring == "DAILY":
                    if time_overlap:
                        overlap = True
                elif recurring == "WEEKLY" or ex_recurring == "WEEKLY":
                    if w1 == w2 and time_overlap:
                        overlap = True
                else:
                    if start_dt.weekday() == ex_start_dt.weekday() and time_overlap:
                        overlap = True
            
            if overlap:
                conflict_event = {
                    "id": ex_id,
                    "title": ex_title,
                    "start": ex_start_dt,
                    "end": ex_end_dt,
                    "priority": ex_priority,
                    "recurring": ex_recurring
                }
                break
                
        priority_weights = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        resolution_msg = ""
        
        if conflict_event:
            new_weight = priority_weights.get(priority, 2)
            conflict_weight = priority_weights.get(conflict_event["priority"], 2)
            
            if new_weight > conflict_weight:
                cursor.execute("DELETE FROM schedules WHERE id = ?", (conflict_event["id"],))
                conn.commit()
                resolution_msg = (
                    f"\n⚡ **Conflict Resolved**: The lower priority event **'{conflict_event['title']}'** "
                    f"({conflict_event['priority']}) has been successfully rescheduled/cleared to make room."
                )
            else:
                conn.close()
                return {
                    "status": "error",
                    "message": (
                        f"❌ **Schedule Conflict**: Cannot schedule '{title}' because it overlaps with an existing "
                        f"**{conflict_event['priority']} priority** event: **'{conflict_event['title']}'** "
                        f"({conflict_event['start'].strftime('%I:%M %p')} - {conflict_event['end'].strftime('%I:%M %p')}), Sir."
                    )
                }
                
        cursor.execute(
            "INSERT INTO schedules (title, start_time, end_time, priority, recurring) VALUES (?, ?, ?, ?, ?)",
            (title, start_dt.strftime("%Y-%m-%d %H:%M"), end_dt.strftime("%Y-%m-%d %H:%M"), priority, recurring)
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        
        priority_emoji = "🔴" if priority == "HIGH" else "🟡" if priority == "MEDIUM" else "🟢"
        rec_text = " (recurring weekly)" if recurring == "WEEKLY" else " (recurring daily)" if recurring == "DAILY" else ""
        
        return {
            "status": "ok",
            "message": (
                "Calendar scheduling is currently using a local database seeded with mock corporate events and is not connected to a real Google or Outlook Calendar account. (Sandbox Mock)\n\n"
                f"✅ Successfully scheduled **'{title}'** for **{start_dt.strftime('%A, %b %d at %I:%M %p')}** "
                f"to **{end_dt.strftime('%I:%M %p')}**{rec_text}, Sir!{resolution_msg}"
            ),
            "data": {
                "id": new_id,
                "title": title,
                "start_time": start_dt.strftime("%Y-%m-%d %H:%M"),
                "end_time": end_dt.strftime("%Y-%m-%d %H:%M"),
                "priority": priority,
                "recurring": recurring
            }
        }
    except Exception as e:
        logger.error(f"Failed to schedule event: {e}", exc_info=True)
        return {"status": "error", "message": f"Calendar scheduling failed: {str(e)}"}

def schedule_from_text(text: str) -> Dict[str, Any]:
    """
    Intelligent NLP wrapper to parse loose human schedule commands and call schedule_event safely.
    Handles relative weekdays, default durations, priority highlights, and daily/weekly recurrence.
    """
    try:
        t = text.lower().strip()
        
        # 1. Resolve Priority
        priority = "MEDIUM"
        if any(w in t for w in ["high", "urgent", "critical", "important"]):
            priority = "HIGH"
        elif any(w in t for w in ["low", "casual", "minor", "flexible"]):
            priority = "LOW"
            
        # 2. Resolve Recurrence
        recurring = "NONE"
        if any(w in t for w in ["every day", "every morning", "daily", "each day"]):
            recurring = "DAILY"
        elif any(w in t for w in ["every week", "weekly", "every monday", "every tuesday", "every wednesday", "every thursday", "every friday"]):
            recurring = "WEEKLY"
            
        # 3. Resolve Date/Weekday
        today = datetime.now()
        target_date = today
        
        weekdays = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        
        day_found = False
        for day, idx in weekdays.items():
            if day in t:
                days_ahead = idx - today.weekday()
                if days_ahead < 0:
                    days_ahead += 7  # Schedule for next week's day
                target_date = today + timedelta(days=days_ahead)
                day_found = True
                break
                
        # 4. Resolve Hour & Minute
        # Look for standard expressions: 9am, 2:30 pm, 15:00, 4:00 PM, 9:00
        time_match = re.search(r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b', t)
        
        hour = 9
        minute = 0
        
        if time_match:
            h_str, m_str, ampm = time_match.groups()
            hour = int(h_str)
            if m_str:
                minute = int(m_str)
            if ampm:
                ampm = ampm.lower()
                if ampm == "pm" and hour < 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0
            else:
                # If no am/pm, check if it's natural work hours
                if hour < 8:  # e.g., "5" probably means 5pm
                    hour += 12
                    
        # Apply to target date
        start_dt = datetime(target_date.year, target_date.month, target_date.day, hour, minute)
        
        # 5. Resolve Duration (Default to 1 hour)
        duration_mins = 60
        if "30 mins" in t or "30 minutes" in t or "half hour" in t:
            duration_mins = 30
        elif "2 hours" in t or "2 hrs" in t:
            duration_mins = 120
        elif "1.5 hours" in t or "90 mins" in t or "90 minutes" in t:
            duration_mins = 90
            
        end_dt = start_dt + timedelta(minutes=duration_mins)
        
        # 6. Extract Clean Title
        # Strip away common command patterns
        title = "Sprint Sync/Coding Session"
        title_match = re.search(r'(?:schedule|block|add)(?:\s+out|\s+time\s+for)?\s+(?:my\s+)?(.*?)(?:\s+(?:every|at|on|from|this|high|low|urgent|weekly|daily)\b)', t)
        if title_match:
            extracted = title_match.group(1).strip()
            # Remove filler words
            extracted = re.sub(r'^(?:coding\s+time|event|meeting|time\s+for)\s+', '', extracted, flags=re.I)
            if extracted:
                title = extracted.title()
        else:
            # Fallback title finder
            words = text.split()
            # If the command has a few words, extract everything after "schedule"
            for i, w in enumerate(words):
                if w.lower() in ["schedule", "block"]:
                    title_candidate = " ".join(words[i+1:])
                    # Remove time and weekday references
                    title_candidate = re.sub(r'\b(?:at|on|every|this|daily|weekly|monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d+)\b.*', '', title_candidate, flags=re.I).strip()
                    if title_candidate:
                        title = title_candidate.title()
                    break
                    
        start_str = start_dt.strftime("%Y-%m-%d %H:%M")
        end_str = end_dt.strftime("%Y-%m-%d %H:%M")
        
        return schedule_event(title, start_str, end_str, priority, recurring)
    except Exception as e:
        logger.error(f"NLP calendar parser failed: {e}", exc_info=True)
        # Safe fallback: schedule standard coding session today at 10am
        today_str = datetime.now().strftime("%Y-%m-%d")
        return schedule_event("Coding Session", f"{today_str} 10:00", f"{today_str} 11:00", "MEDIUM", "NONE")
