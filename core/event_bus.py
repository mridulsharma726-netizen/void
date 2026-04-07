"""
VOID Event Bus Module
====================

Central event system for inter-module communication.

Features:
- Publish/Subscribe pattern
- Event filtering
- Async event handling
- Event history logging
- Priority subscribers

Event Types:
- VOICE_COMMAND: User spoke a command
- SYSTEM_ALERT: System monitoring alert
- TASK_SCHEDULED: New task scheduled
- TASK_TRIGGERED: Scheduled task executed
- WORKFLOW_STARTED: Workflow began
- WORKFLOW_COMPLETED: Workflow finished
- MEMORY_UPDATED: Memory changed
- TOOL_EXECUTED: Tool was run
- ERROR_OCCURRED: Error occurred
- USER_CONNECTED: User interaction started
- USER_IDLE: User became idle
"""

import logging
import time
import threading
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
from enum import Enum

# Configure logging
logger = logging.getLogger("VOID-EventBus")

# Event Types as constants
class EventType(Enum):
    """Pre-defined event types."""
    VOICE_COMMAND = "VOICE_COMMAND"
    SYSTEM_ALERT = "SYSTEM_ALERT"
    TASK_SCHEDULED = "TASK_SCHEDULED"
    TASK_TRIGGERED = "TASK_TRIGGERED"
    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    WORKFLOW_STEP = "WORKFLOW_STEP"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    MEMORY_UPDATED = "MEMORY_UPDATED"
    TOOL_EXECUTED = "TOOL_EXECUTED"
    ERROR_OCCURRED = "ERROR_OCCURRED"
    USER_CONNECTED = "USER_CONNECTED"
    USER_IDLE = "USER_IDLE"
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_THINKING = "AGENT_THINKING"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    DIAGNOSTICS_RUN = "DIAGNOSTICS_RUN"
    REPAIR_COMPLETED = "REPAIR_COMPLETED"


@dataclass
class Event:
    """Event data structure."""
    type: str
    data: Any = None
    timestamp: float = field(default_factory=time.time)
    source: str = "unknown"
    priority: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp,
            "source": self.source,
            "priority": self.priority,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat()
        }


class EventBus:
    """
    Central event bus for VOID module communication.
    
    Usage:
        # Subscribe to events
        event_bus.subscribe(EventType.VOICE_COMMAND, handle_voice)
        
        # Publish events
        event_bus.publish(EventType.VOICE_COMMAND, {"text": "hello"})
        
        # Unsubscribe
        event_bus.unsubscribe(EventType.VOICE_COMMAND, handle_voice)
    """
    
    def __init__(self, enable_logging: bool = True):
        """
        Initialize the event bus.
        
        Args:
            enable_logging: Whether to log events
        """
        self._listeners: Dict[str, List[Callable]] = defaultdict(list)
        self._priority_listeners: Dict[str, List[tuple]] = defaultdict(list)
        self._event_history: List[Event] = []
        self._max_history = 100
        self._enable_logging = enable_logging
        self._lock = threading.RLock()
        
        logger.info("[EVENT BUS] Initialized")
    
    def subscribe(self, 
                 event_type: str, 
                 callback: Callable[[Event], None],
                 priority: int = 0) -> None:
        """
        Subscribe to an event type.
        
        Args:
            event_type: Event type string or EventType enum
            callback: Function to call when event fires
            priority: Higher priority callbacks fire first (default 0)
        """
        event_type = str(event_type)
        
        with self._lock:
            if priority != 0:
                self._priority_listeners[event_type].append((priority, callback))
                self._priority_listeners[event_type].sort(key=lambda x: -x[0])
            else:
                self._listeners[event_type].append(callback)
        
        if self._enable_logging:
            logger.info(f"[EVENT BUS] Subscribed to {event_type} (priority: {priority})")
    
    def unsubscribe(self, event_type: str, callback: Callable) -> bool:
        """
        Unsubscribe from an event type.
        
        Args:
            event_type: Event type
            callback: Callback to remove
            
        Returns:
            True if callback was found and removed
        """
        event_type = str(event_type)
        
        with self._lock:
            # Check regular listeners
            if callback in self._listeners[event_type]:
                self._listeners[event_type].remove(callback)
                if self._enable_logging:
                    logger.info(f"[EVENT BUS] Unsubscribed from {event_type}")
                return True
            
            # Check priority listeners
            for priority, cb in self._priority_listeners[event_type]:
                if cb == callback:
                    self._priority_listeners[event_type].remove((priority, cb))
                    if self._enable_logging:
                        logger.info(f"[EVENT BUS] Unsubscribed from {event_type}")
                    return True
        
        return False
    
    def publish(self, 
                event_type: str, 
                data: Any = None,
                source: str = "unknown",
                priority: int = 0) -> int:
        """
        Publish an event to all subscribers.
        
        Args:
            event_type: Event type or EventType enum
            data: Event data payload
            source: Source module name
            priority: Event priority
            
        Returns:
            Number of subscribers notified
        """
        event_type = str(event_type)
        
        # Create event
        event = Event(
            type=event_type,
            data=data,
            source=source,
            priority=priority
        )
        
        # Add to history
        with self._lock:
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history.pop(0)
        
        if self._enable_logging:
            logger.info(f"[EVENT BUS] Published {event_type} from {source}")
        
        # Notify subscribers
        notified = 0
        
        with self._lock:
            # Priority listeners first
            for _, callback in self._priority_listeners.get(event_type, []):
                try:
                    callback(event)
                    notified += 1
                except Exception as e:
                    logger.error(f"[EVENT BUS] Callback error: {e}")
            
            # Regular listeners
            for callback in self._listeners.get(event_type, []):
                try:
                    callback(event)
                    notified += 1
                except Exception as e:
                    logger.error(f"[EVENT BUS] Callback error: {e}")
        
        return notified
    
    def publish_async(self, 
                     event_type: str, 
                     data: Any = None,
                     source: str = "unknown") -> None:
        """Publish event in background thread."""
        thread = threading.Thread(
            target=self.publish,
            args=(event_type, data, source),
            daemon=True
        )
        thread.start()
    
    def get_history(self, 
                   event_type: Optional[str] = None, 
                   limit: int = 10) -> List[Dict]:
        """
        Get event history.
        
        Args:
            event_type: Filter by event type (optional)
            limit: Maximum events to return
            
        Returns:
            List of event dictionaries
        """
        with self._lock:
            history = self._event_history
            
            if event_type:
                history = [e for e in history if e.type == event_type]
            
            return [e.to_dict() for e in history[-limit:]]
    
    def clear_history(self) -> None:
        """Clear event history."""
        with self._lock:
            self._event_history.clear()
        logger.info("[EVENT BUS] History cleared")
    
    def get_subscribers(self, event_type: str) -> int:
        """Get count of subscribers for an event type."""
        with self._lock:
            regular = len(self._listeners.get(event_type, []))
            priority = len(self._priority_listeners.get(event_type, []))
            return regular + priority
    
    def get_all_event_types(self) -> List[str]:
        """Get list of all event types with subscribers."""
        with self._lock:
            types = set(self._listeners.keys()) | set(self._priority_listeners.keys())
            return sorted(list(types))
    
    def debug_info(self) -> Dict:
        """Get debug information about the event bus."""
        with self._lock:
            return {
                "total_events": len(self._event_history),
                "event_types": self.get_all_event_types(),
                "subscribers": {
                    et: self.get_subscribers(et) 
                    for et in self.get_all_event_types()
                }
            }


# ============================================================================
# GLOBAL EVENT BUS INSTANCE
# ============================================================================

# Create singleton instance
event_bus = EventBus()


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def publish_voice_command(text: str, source: str = "voice_system") -> int:
    """Publish a voice command event."""
    return event_bus.publish(EventType.VOICE_COMMAND, {"text": text}, source)


def publish_system_alert(alert: Dict, source: str = "system_monitor") -> int:
    """Publish a system alert event."""
    return event_bus.publish(EventType.SYSTEM_ALERT, alert, source)


def publish_task_scheduled(task: Dict, source: str = "task_scheduler") -> int:
    """Publish a task scheduled event."""
    return event_bus.publish(EventType.TASK_SCHEDULED, task, source)


def publish_task_triggered(task: Dict, source: str = "task_scheduler") -> int:
    """Publish a task triggered event."""
    return event_bus.publish(EventType.TASK_TRIGGERED, task, source)


def publish_workflow_started(workflow: Dict, source: str = "workflow_engine") -> int:
    """Publish a workflow started event."""
    return event_bus.publish(EventType.WORKFLOW_STARTED, workflow, source)


def publish_workflow_completed(workflow: Dict, source: str = "workflow_engine") -> int:
    """Publish a workflow completed event."""
    return event_bus.publish(EventType.WORKFLOW_COMPLETED, workflow, source)


def publish_tool_executed(tool: str, args: Any, result: Dict, source: str = "agent") -> int:
    """Publish a tool executed event."""
    return event_bus.publish(
        EventType.TOOL_EXECUTED, 
        {"tool": tool, "args": args, "result": result}, 
        source
    )


def publish_error(error: Exception, context: str, source: str = "unknown") -> int:
    """Publish an error event."""
    return event_bus.publish(
        EventType.ERROR_OCCURRED,
        {"error": str(error), "context": context},
        source
    )


# ============================================================================
# DECORATOR FOR SUBSCRIPTIONS
# ============================================================================

def on_event(event_type: str, priority: int = 0):
    """
    Decorator for subscribing to events.
    
    Usage:
        @on_event(EventType.VOICE_COMMAND)
        def handle_voice(event):
            print(f"User said: {event.data['text']}")
    """
    def decorator(func: Callable) -> Callable:
        event_bus.subscribe(event_type, func, priority)
        return func
    return decorator


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("Testing Event Bus...")
    
    # Simple handler
    def handle_voice(event):
        print(f"🎤 Voice command: {event.data}")
    
    def handle_alert(event):
        print(f"⚠️ System alert: {event.data}")
    
    # Subscribe
    event_bus.subscribe(EventType.VOICE_COMMAND, handle_voice, priority=10)
    event_bus.subscribe(EventType.SYSTEM_ALERT, handle_alert)
    
    # Publish events
    print("\n1. Publishing voice command:")
    event_bus.publish(EventType.VOICE_COMMAND, {"text": "hello void"}, "test")
    
    print("\n2. Publishing system alert:")
    event_bus.publish(EventType.SYSTEM_ALERT, {"cpu": 95}, "monitor")
    
    # Get history
    print("\n3. Event history:")
    history = event_bus.get_history(limit=5)
    for h in history:
        print(f"  {h['type']} at {h['datetime']}")
    
    # Debug info
    print("\n4. Debug info:")
    print(event_bus.debug_info())

