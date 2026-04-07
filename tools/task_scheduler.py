"""
VOID Task Scheduler Module
====================

Schedule tasks to run in the future.
Examples:
- Remind me at 7pm
- Open chrome in 10 minutes
- Shutdown at midnight

Functions:
- add_task(run_time, action, data) -> str
- schedule_reminder(time_str, message) -> str
- schedule_delay(delay_seconds, action, data) -> str
- scheduler_loop()
- cancel_task(task_id) -> bool
- get_scheduled_tasks() -> List[dict]
"""

import time
import threading
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass

# Configure logging
logger = logging.getLogger("VOID-TaskScheduler")

# Task storage
_scheduled_tasks: List[Dict[str, Any]] = []
_task_id_counter = 0
_scheduler_running = False

# Callback for task execution
_task_executor: Optional[Callable[[Dict], None]] = None


def set_task_executor(callback: Callable[[Dict], None]):
    """Set the function to execute tasks."""
    global _task_executor
    _task_executor = callback


def _generate_task_id() -> str:
    """Generate unique task ID."""
    global _task_id_counter
    _task_id_counter += 1
    return f"task_{int(time.time())}_{_task_id_counter}"


def add_task(run_time: datetime, action: str, data: Any = None, 
            description: str = "") -> str:
    """
    Add a task to the scheduler.
    
    Args:
        run_time: When to execute (datetime)
        action: Action type (reminder, open_app, shutdown, etc.)
        data: Data for the action (message, app name, etc.)
        description: Human-readable description
        
    Returns:
        Task ID
    """
    global _scheduled_tasks
    
    task_id = _generate_task_id()
    
    task = {
        "id": task_id,
        "time": run_time,
        "action": action,
        "data": data,
        "description": description or f"{action}: {data}",
        "created": datetime.now(),
        "status": "pending"
    }
    
    _scheduled_tasks.append(task)
    _scheduled_tasks.sort(key=lambda t: t["time"])  # Sort by time
    
    logger.info(f"[SCHEDULER] Task scheduled: {task['description']} at {run_time.strftime('%H:%M')}")
    
    return task_id


def add_task_seconds(delay_seconds: int, action: str, data: Any = None,
                    description: str = "") -> str:
    """
    Add a task to run after a delay.
    
    Args:
        delay_seconds: Seconds to wait
        action: Action type
        data: Data for action
        description: Description
        
    Returns:
        Task ID
    """
    run_time = datetime.now() + timedelta(seconds=delay_seconds)
    return add_task(run_time, action, data, description)


def cancel_task(task_id: str) -> bool:
    """Cancel a scheduled task."""
    global _scheduled_tasks
    
    for task in _scheduled_tasks:
        if task["id"] == task_id:
            _scheduled_tasks.remove(task)
            logger.info(f"[SCHEDULER] Task cancelled: {task_id}")
            return True
    
    return False


def get_scheduled_tasks() -> List[Dict[str, Any]]:
    """Get all scheduled tasks."""
    return [
        {
            "id": t["id"],
            "time": t["time"].isoformat(),
            "action": t["action"],
            "data": t["data"],
            "description": t["description"],
            "status": t["status"]
        }
        for t in _scheduled_tasks
    ]


def clear_completed_tasks():
    """Remove completed tasks."""
    global _scheduled_tasks
    _scheduled_tasks = [t for t in _scheduled_tasks if t["status"] == "pending"]


def _execute_task(task: Dict[str, Any]):
    """Execute a scheduled task."""
    logger.info(f"[SCHEDULER] Executing: {task['description']}")
    
    task["status"] = "running"
    
    try:
        action = task["action"]
        data = task["data"]
        
        if action == "reminder":
            # Speak the reminder
            try:
                from tools.voice_tts import speak
                speak(str(data))
            except Exception as e:
                logger.error(f"Reminder TTS error: {e}")
        
        elif action == "open_app":
            # Open an application
            try:
                from tools.pc_control import open_app
                open_app(str(data))
            except Exception as e:
                logger.error(f"Open app error: {e}")
        
        elif action == "open_url":
            try:
                from tools.pc_control import open_url
                open_url(str(data))
            except Exception as e:
                logger.error(f"Open URL error: {e}")
        
        elif action == "search":
            try:
                from tools.pc_control import search_web
                search_web(str(data))
            except Exception as e:
                logger.error(f"Search error: {e}")
        
        elif action == "shutdown":
            # Schedule shutdown (requires confirmation in production)
            logger.warning(f"[SCHEDULER] Shutdown requested: {data}")
            # import os
            # os.system("shutdown /s /t 60")  # 60 second warning
        
        elif action == "custom":
            # Custom action via callback
            if _task_executor:
                _task_executor(task)
        
        task["status"] = "completed"
        logger.info(f"[SCHEDULER] Task completed: {task['id']}")
        
    except Exception as e:
        logger.error(f"[SCHEDULER] Task error: {e}")
        task["status"] = "failed"


def scheduler_loop(interval: int = 5):
    """
    Main scheduler loop - runs in background.
    
    Args:
        interval: Seconds between checks
    """
    global _scheduler_running
    
    _scheduler_running = True
    logger.info("[SCHEDULER] Started")
    
    while _scheduler_running:
        try:
            now = datetime.now()
            
            # Check each pending task
            for task in _scheduled_tasks[:]:  # Copy list to allow modification
                if task["status"] != "pending":
                    continue
                
                if now >= task["time"]:
                    # Time to execute
                    _execute_task(task)
                    
                    # Remove completed tasks
                    if task["status"] in ["completed", "failed"]:
                        try:
                            _scheduled_tasks.remove(task)
                        except ValueError:
                            pass
            
            # Clean up old completed tasks
            clear_completed_tasks()
            
            # Sleep
            time.sleep(interval)
            
        except Exception as e:
            logger.error(f"[SCHEDULER] Loop error: {e}")
            time.sleep(interval)
    
    logger.info("[SCHEDULER] Stopped")


def stop_scheduler():
    """Stop the scheduler loop."""
    global _scheduler_running
    _scheduler_running = False


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def schedule_reminder(message: str, time_str: str = None, minutes: int = None) -> str:
    """
    Schedule a reminder.
    
    Args:
        message: What to remind
        time_str: Time like "7pm", "14:30" (optional if minutes provided)
        minutes: Minutes from now (alternative to time_str)
        
    Returns:
        Task ID
    """
    if minutes is not None:
        # Relative time
        run_time = datetime.now() + timedelta(minutes=minutes)
        desc = f"Reminder in {minutes} min: {message}"
    elif time_str:
        # Parse time string
        now = datetime.now()
        run_time = _parse_time_string(time_str, now)
        if not run_time:
            return ""
        # If time is in past, schedule for tomorrow
        if run_time < now:
            run_time += timedelta(days=1)
        desc = f"Reminder at {time_str}: {message}"
    else:
        return ""
    
    return add_task(run_time, "reminder", message, desc)


def schedule_app_open(app_name: str, minutes: int = 0, time_str: str = None) -> str:
    """Schedule an app to open."""
    if minutes > 0:
        run_time = datetime.now() + timedelta(minutes=minutes)
    elif time_str:
        now = datetime.now()
        run_time = _parse_time_string(time_str, now)
        if not run_time:
            return ""
        if run_time < now:
            run_time += timedelta(days=1)
    else:
        run_time = datetime.now()
    
    return add_task(run_time, "open_app", app_name, f"Open {app_name}")


def _parse_time_string(time_str: str, base_time: datetime) -> Optional[datetime]:
    """Parse time string like '7pm', '14:30', '3:00am'."""
    time_str = time_str.lower().strip()
    
    # Try "7pm", "7am"
    m = re.match(r"(\d{1,2})(am|pm)", time_str)
    if m:
        hour = int(m.group(1))
        period = m.group(2)
        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        return base_time.replace(hour=hour, minute=0, second=0, microsecond=0)
    
    # Try "14:30" or "3:00"
    m = re.match(r"(\d{1,2}):(\d{2})", time_str)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    return None


# ============================================================================
# NATURAL LANGUAGE PARSING
# ============================================================================

def parse_scheduling_request(prompt: str) -> Optional[str]:
    """
    Parse natural language scheduling requests.
    
    Handles:
    - "remind me to X in Y minutes"
    - "remind me at 7pm to X"
    - "open chrome in 10 minutes"
    - "remind me tomorrow at 9am"
    
    Returns:
        Task ID or None
    """
    prompt = prompt.lower().strip()
    
    # Pattern: "remind me to [message] in [N] minutes"
    m = re.search(r"remind\s+me\s+to\s+(.+?)\s+in\s+(\d+)\s+minute", prompt)
    if m:
        message = m.group(1).strip()
        minutes = int(m.group(2))
        return schedule_reminder(message, minutes=minutes)
    
    # Pattern: "remind me to [message] at [time]"
    m = re.search(r"remind\s+me\s+to\s+(.+?)\s+(?:at|at\s+)([\d:]+(?:am|pm)?)", prompt)
    if m:
        message = m.group(1).strip()
        time_str = m.group(2).strip()
        return schedule_reminder(message, time_str=time_str)
    
    # Pattern: "open [app] in [N] minutes"
    m = re.search(r"open\s+(\w+)\s+in\s+(\d+)\s+minute", prompt)
    if m:
        app = m.group(1).strip()
        minutes = int(m.group(2))
        return schedule_app_open(app, minutes=minutes)
    
    # Pattern: "in [N] minutes, [action]"
    m = re.search(r"in\s+(\d+)\s+minute[,\s]+(.+)", prompt)
    if m:
        minutes = int(m.group(1))
        action = m.group(2).strip()
        
        # Determine action type
        if action.startswith("open "):
            app = action[5:].strip()
            return schedule_app_open(app, minutes=minutes)
        elif "remind" in action:
            return schedule_reminder(action, minutes=minutes)
    
    return None


if __name__ == "__main__":
    # Test scheduler
    print("Testing task scheduler...")
    
    # Schedule a reminder in 10 seconds
    task_id = schedule_reminder("Test reminder - this should appear in 10 seconds", minutes=0)
    print(f"Scheduled: {task_id}")
    
    # List tasks
    tasks = get_scheduled_tasks()
    print(f"Scheduled tasks: {tasks}")
    
    # Run scheduler briefly
    print("Running scheduler for 15 seconds...")
    start = time.time()
    while time.time() - start < 15:
        scheduler_loop(interval=1)
        time.sleep(1)
    
    print("Done")

