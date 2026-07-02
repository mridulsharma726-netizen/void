import uuid
import time
import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional

logger = logging.getLogger("void.task_planner")

ACTIVE_TASKS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "memory", "data", "active_tasks.json"
)

class Task:
    def __init__(self, description: str, tool_name: Optional[str] = None, payload: Optional[Dict[str, Any]] = None, max_retries: int = 3):
        self.id = str(uuid.uuid4())[:8]
        self.description = description
        self.tool_name = tool_name
        self.payload = payload or {}
        self.status = "Planning"  # Planning, Running, Waiting, Retrying, Completed, Failed
        self.progress = 0
        self.retry_count = 0
        self.max_retries = max_retries
        self.execution_time = 0.0
        self.logs: List[str] = []
        self.error_reason: Optional[str] = None
        self.subtasks: List['Task'] = []

    def add_log(self, msg: str):
        timestamp = time.strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {msg}")
        logger.info(f"[Task {self.id}] {msg}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "tool_name": self.tool_name,
            "payload": self.payload,
            "status": self.status,
            "progress": self.progress,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "execution_time": round(self.execution_time, 2),
            "logs": self.logs,
            "error_reason": self.error_reason,
            "subtasks": [st.to_dict() for st in self.subtasks]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        task = cls(
            description=data.get("description", ""),
            tool_name=data.get("tool_name"),
            payload=data.get("payload"),
            max_retries=data.get("max_retries", 3)
        )
        task.id = data.get("id", task.id)
        task.status = data.get("status", "Planning")
        task.progress = data.get("progress", 0)
        task.retry_count = data.get("retry_count", 0)
        task.execution_time = data.get("execution_time", 0.0)
        task.logs = data.get("logs", [])
        task.error_reason = data.get("error_reason")
        task.subtasks = [cls.from_dict(st) for st in data.get("subtasks", [])]
        return task

class TaskPlanner:
    def __init__(self):
        self.active_tasks: Dict[str, Task] = {}
        self.load_tasks()

    def load_tasks(self):
        if os.path.exists(ACTIVE_TASKS_FILE):
            try:
                with open(ACTIVE_TASKS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.active_tasks = {k: Task.from_dict(v) for k, v in data.items()}
            except Exception as e:
                logger.error(f"Failed to load active tasks: {e}")
                self.active_tasks = {}

    def save_tasks(self):
        os.makedirs(os.path.dirname(ACTIVE_TASKS_FILE), exist_ok=True)
        try:
            with open(ACTIVE_TASKS_FILE, "w", encoding="utf-8") as f:
                data = {k: v.to_dict() for k, v in self.active_tasks.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save active tasks: {e}")

    def create_task_graph(self, goal: str) -> Task:
        # Create root task
        root_task = Task(description=f"Goal: {goal}")
        
        # Rule-based workflow detection for the phase 2 success criteria
        goal_lower = goal.lower()
        if "open vs code" in goal_lower or "vscode" in goal_lower or "scan" in goal_lower:
            # Generate the success criteria task list
            root_task.subtasks = [
                Task("Open Visual Studio Code", "open_app", {"app": "vscode"}),
                Task("Register VOID Project Path", "register_project", {"path": os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))}),
                Task("Scan current codebase structure", "agent_scan", {}),
                Task("Summarize project architecture", "agent_explain", {}),
                Task("Identify highest-priority TODO action items", "get_action_items", {}),
                Task("Run test suite", "agent_run_tests", {}),
            ]
        elif "automation" in goal_lower or "screenshot" in goal_lower:
            root_task.subtasks = [
                Task("Capture Screen State", "screenshot", {}),
                Task("Read Active Title", "read_active_window", {}),
            ]
        else:
            # Simple fallback task
            root_task.subtasks = [
                Task("Analyze intent and respond", "chat", {"text": goal})
            ]

        self.active_tasks[root_task.id] = root_task
        self.save_tasks()
        return root_task

    async def execute_task_graph(self, task_id: str, tool_manager: Any) -> Dict[str, Any]:
        root_task = self.active_tasks.get(task_id)
        if not root_task:
            return {"status": "error", "message": "Task not found."}

        root_task.status = "Running"
        root_task.progress = 10
        root_task.add_log("Starting task graph execution...")
        self.save_tasks()

        start_time = time.perf_counter()
        total_subtasks = len(root_task.subtasks)
        
        for idx, subtask in enumerate(root_task.subtasks):
            subtask.status = "Running"
            subtask.progress = 20
            subtask.add_log(f"Starting subtask: {subtask.description}")
            self.save_tasks()

            sub_start = time.perf_counter()
            success = False

            while subtask.retry_count <= subtask.max_retries and not success:
                if subtask.retry_count > 0:
                    subtask.status = "Retrying"
                    subtask.add_log(f"Retrying execution (Attempt {subtask.retry_count}/{subtask.max_retries})...")
                    self.save_tasks()

                try:
                    # Execute tool call
                    subtask.add_log(f"Calling tool: {subtask.tool_name} with payload {subtask.payload}")
                    res = await tool_manager.execute(subtask.tool_name, subtask.payload)
                    
                    # Verify execution result
                    from core.autonomous_agent.self_verifier import SelfVerifier
                    verifier = SelfVerifier()
                    verification_res = await verifier.verify(subtask.tool_name, subtask.payload, res)
                    
                    if verification_res.get("status") == "ok":
                        subtask.status = "Completed"
                        subtask.progress = 100
                        subtask.add_log(f"Verification successful: {verification_res.get('message')}")
                        success = True
                    else:
                        subtask.retry_count += 1
                        subtask.error_reason = verification_res.get("message", "Verification failed.")
                        subtask.add_log(f"Verification failed: {subtask.error_reason}")
                except Exception as e:
                    subtask.retry_count += 1
                    subtask.error_reason = str(e)
                    subtask.add_log(f"Execution error: {str(e)}")

            subtask.execution_time = time.perf_counter() - sub_start
            if not success:
                subtask.status = "Failed"
                root_task.status = "Failed"
                root_task.progress = 100
                root_task.add_log(f"Subtask failed after {subtask.retry_count} retries. Reason: {subtask.error_reason}")
                self.save_tasks()
                return {"status": "failed", "failed_step": subtask.description, "reason": subtask.error_reason}

            # Update overall progress
            root_task.progress = int(10 + (idx + 1) / total_subtasks * 90)
            self.save_tasks()

        root_task.status = "Completed"
        root_task.progress = 100
        root_task.execution_time = time.perf_counter() - start_time
        root_task.add_log("All subtasks completed successfully!")
        self.save_tasks()
        return root_task.to_dict()

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.active_tasks.get(task_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        self.load_tasks()
        return [v.to_dict() for v in self.active_tasks.values()]

    def clear_tasks(self):
        self.active_tasks = {}
        if os.path.exists(ACTIVE_TASKS_FILE):
            try:
                os.remove(ACTIVE_TASKS_FILE)
            except Exception:
                pass
        self.save_tasks()
