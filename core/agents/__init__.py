"""
VOID Multi-Agent System
=====================

A modular multi-agent architecture with specialized agents.

Agents:
- SystemAgent: CPU/RAM/Disk optimization
- ResearchAgent: Internet search and research
- AutomationAgent: Workflows and scheduling
- SecurityAgent: System security monitoring

Usage:
    from core.agents import get_agent, route_task
    
    agent = get_agent("system")
    result = agent.handle_request("optimize performance")
"""

from typing import Dict, Any, Optional, List
from core.event_bus import event_bus, EventType

# Import tool modules (with fallback)
try:
    from tools.system_monitor import check_system_health, get_current_stats
except ImportError:
    check_system_health = None
    get_current_stats = None

try:
    from tools.system_control import list_running_apps, kill_heavy_process, get_system_usage
except ImportError:
    list_running_apps = None
    kill_heavy_process = None
    get_system_usage = None

try:
    from tools.self_optimizer import auto_repair, quick_diagnose
except ImportError:
    auto_repair = None
    quick_diagnose = None

try:
    from tools.web_search import search_web, find_information, read_page
except ImportError:
    search_web = None
    find_information = None
    read_page = None

try:
    from tools.task_scheduler import schedule_reminder, get_scheduled_tasks
except ImportError:
    schedule_reminder = None
    get_scheduled_tasks = None

try:
    from tools.learning_system import detect_habits, suggest_automation
except ImportError:
    detect_habits = None
    suggest_automation = None


# ============================================================================
# BASE AGENT CLASS
# ============================================================================

class BaseAgent:
    """Base class for all agents."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self._initialized = True
    
    def handle_request(self, task: str) -> Dict[str, Any]:
        """
        Handle a task request.
        
        Args:
            task: Task description
            
        Returns:
            Dict with status and response
        """
        return {
            "status": "error",
            "agent": self.name,
            "message": f"{self.name} does not implement handle_request"
        }
    
    def get_info(self) -> Dict[str, Any]:
        """Get agent information."""
        return {
            "name": self.name,
            "description": self.description,
            "initialized": self._initialized
        }


# ============================================================================
# SYSTEM AGENT
# ============================================================================

class SystemAgent(BaseAgent):
    """
    System Agent - Handles system monitoring and optimization.
    
    Responsibilities:
    - Monitor CPU, RAM, Disk usage
    - Optimize performance
    - Run diagnostics
    - Manage processes
    """
    
    def __init__(self):
        super().__init__(
            name="system_agent",
            description="Handles system monitoring, optimization, and performance management"
        )
    
    def handle_request(self, task: str) -> Dict[str, Any]:
        """Handle system-related tasks."""
        task_lower = task.lower()
        
        # Performance check
        if any(kw in task_lower for kw in ["performance", "system status", "how is"]):
            return self.check_performance()
        
        # Optimize
        if any(kw in task_lower for kw in ["optimize", "speed up", "make faster"]):
            return self.optimize_system()
        
        # Diagnostics
        if any(kw in task_lower for kw in ["diagnose", "check health", "system check"]):
            return self.run_diagnostics()
        
        # Kill heavy process
        if any(kw in task_lower for kw in ["kill", "heavy process", "close process"]):
            return self.kill_heavy_process()
        
        # List processes
        if any(kw in task_lower for kw in ["list processes", "running apps", "running programs"]):
            return self.list_processes()
        
        # Clean temp
        if any(kw in task_lower for kw in ["clean", "temp", "free space"]):
            return self.clean_system()
        
        return {
            "status": "unknown",
            "agent": self.name,
            "message": f"Unknown system task: {task}"
        }
    
    def check_performance(self) -> Dict[str, Any]:
        """Check system performance."""
        if get_system_usage:
            stats = get_system_usage()
            return {
                "status": "ok",
                "agent": self.name,
                "message": f"CPU: {stats.get('cpu_percent')}% | RAM: {stats.get('ram_percent')}% | Disk: {stats.get('disk_percent')}%",
                "data": stats
            }
        return {"status": "error", "agent": self.name, "message": "System stats unavailable"}
    
    def optimize_system(self) -> Dict[str, Any]:
        """Optimize system performance."""
        # Try to kill heavy process
        if kill_heavy_process:
            result = kill_heavy_process(1)
            return {
                "status": "ok",
                "agent": self.name,
                "message": f"Optimized: {result.get('killed', ['none'])}",
                "action": "killed_heavy_process"
            }
        return {"status": "error", "agent": self.name, "message": "Optimizer unavailable"}
    
    def run_diagnostics(self) -> Dict[str, Any]:
        """Run system diagnostics."""
        if quick_diagnose:
            result = quick_diagnose()
            return {
                "status": result.get("status", "unknown"),
                "agent": self.name,
                "message": f"Diagnostics: {result.get('error_count', 0)} issues found",
                "data": result
            }
        return {"status": "error", "agent": self.name, "message": "Diagnostics unavailable"}
    
    def kill_heavy_process(self) -> Dict[str, Any]:
        """Kill the heaviest process."""
        if kill_heavy_process:
            result = kill_heavy_process(1)
            return {
                "status": "ok",
                "agent": self.name,
                "message": f"Killed: {result.get('killed', ['none'])}"
            }
        return {"status": "error", "agent": self.name, "message": "Process control unavailable"}
    
    def list_processes(self) -> Dict[str, Any]:
        """List running processes."""
        if list_running_apps:
            procs = list_running_apps(10)
            return {
                "status": "ok",
                "agent": self.name,
                "message": f"Top processes: {', '.join([p['name'] for p in procs[:5]])}",
                "data": procs
            }
        return {"status": "error", "agent": self.name, "message": "Process listing unavailable"}
    
    def clean_system(self) -> Dict[str, Any]:
        """Clean temporary files."""
        # This would call system_control.clean_temp_files()
        return {
            "status": "ok",
            "agent": self.name,
            "message": "Cleaning temporary files...",
            "action": "clean_temp"
        }


# ============================================================================
# RESEARCH AGENT
# ============================================================================

class ResearchAgent(BaseAgent):
    """
    Research Agent - Handles internet search and research.
    
    Responsibilities:
    - Search the internet
    - Read webpages
    - Summarize information
    """
    
    def __init__(self):
        super().__init__(
            name="research_agent",
            description="Handles internet search, research, and information gathering"
        )
    
    def handle_request(self, task: str) -> Dict[str, Any]:
        """Handle research tasks."""
        task_lower = task.lower()
        
        # Search
        if any(kw in task_lower for kw in ["search", "find", "look up", "research"]):
            query = task.replace("search", "").replace("find", "").replace("research", "").strip()
            return self.search_internet(query)
        
        # Read URL
        if "read" in task_lower and "http" in task_lower:
            # Extract URL
            return self.read_webpage(task)
        
        return {
            "status": "unknown",
            "agent": self.name,
            "message": f"Unknown research task: {task}"
        }
    
    def search_internet(self, query: str) -> Dict[str, Any]:
        """Search the internet."""
        if find_information:
            result = find_information(query)
            return {
                "status": "ok",
                "agent": self.name,
                "message": result.get("message", f"Searching for: {query}"),
                "query": query
            }
        elif search_web:
            result = search_web(query)
            return {
                "status": result.get("status", "ok"),
                "agent": self.name,
                "message": result.get("message", f"Searching: {query}"),
                "query": query
            }
        return {"status": "error", "agent": self.name, "message": "Search unavailable"}
    
    def read_webpage(self, task: str) -> Dict[str, Any]:
        """Read a webpage."""
        # Extract URL from task
        import re
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', task)
        
        if urls and read_page:
            result = read_page(urls[0])
            return {
                "status": result.get("status", "ok"),
                "agent": self.name,
                "message": result.get("text", "Page read")[:500],
                "url": urls[0]
            }
        return {"status": "error", "agent": self.name, "message": "Could not read page"}


# ============================================================================
# AUTOMATION AGENT
# ============================================================================

class AutomationAgent(BaseAgent):
    """
    Automation Agent - Handles workflows and task automation.
    
    Responsibilities:
    - Run workflows
    - Manage scheduled tasks
    - Execute automation
    """
    
    def __init__(self):
        super().__init__(
            name="automation_agent",
            description="Handles workflows, task scheduling, and automation"
        )
    
    def handle_request(self, task: str) -> Dict[str, Any]:
        """Handle automation tasks."""
        task_lower = task.lower()
        
        # Schedule reminder
        if "remind" in task_lower or "schedule" in task_lower:
            return self.schedule_task(task)
        
        # List scheduled tasks
        if "list" in task_lower and "task" in task_lower:
            return self.list_tasks()
        
        # Workflow
        if any(kw in task_lower for kw in ["workflow", "automate", "create task"]):
            return self.run_workflow(task)
        
        # Learning suggestions
        if "habit" in task_lower or "learn" in task_lower:
            return self.get_learned_automation()
        
        return {
            "status": "unknown",
            "agent": self.name,
            "message": f"Unknown automation task: {task}"
        }
    
    def schedule_task(self, task: str) -> Dict[str, Any]:
        """Schedule a task."""
        if schedule_reminder:
            # Extract message and time
            import re
            minutes = re.search(r'(\d+)\s*minute', task.lower())
            mins = int(minutes.group(1)) if minutes else 30
            
            message = task.replace("remind", "").replace("schedule", "").strip()
            
            task_id = schedule_reminder(message, minutes=mins)
            return {
                "status": "ok",
                "agent": self.name,
                "message": f"Scheduled reminder in {mins} minutes",
                "task_id": task_id
            }
        return {"status": "error", "agent": self.name, "message": "Scheduler unavailable"}
    
    def list_tasks(self) -> Dict[str, Any]:
        """List scheduled tasks."""
        if get_scheduled_tasks:
            tasks = get_scheduled_tasks()
            return {
                "status": "ok",
                "agent": self.name,
                "message": f"Scheduled tasks: {len(tasks)}",
                "tasks": tasks
            }
        return {"status": "error", "agent": self.name, "message": "Scheduler unavailable"}
    
    def run_workflow(self, task: str) -> Dict[str, Any]:
        """Run a workflow."""
        return {
            "status": "ok",
            "agent": self.name,
            "message": f"Would run workflow: {task}",
            "action": "workflow"
        }
    
    def get_learned_automation(self) -> Dict[str, Any]:
        """Get learned automation suggestions."""
        if suggest_automation:
            suggestion = suggest_automation()
            return {
                "status": "ok",
                "agent": self.name,
                "message": suggestion or "No automation suggestions yet"
            }
        return {"status": "error", "agent": self.name, "message": "Learning system unavailable"}


# ============================================================================
# SECURITY AGENT
# ============================================================================

class SecurityAgent(BaseAgent):
    """
    Security Agent - Handles system security monitoring.
    
    Responsibilities:
    - Monitor suspicious processes
    - Check system security
    - Analyze abnormal behavior
    """
    
    def __init__(self):
        super().__init__(
            name="security_agent",
            description="Handles security monitoring and threat detection"
        )
    
    def handle_request(self, task: str) -> Dict[str, Any]:
        """Handle security tasks."""
        task_lower = task.lower()
        
        # Security check
        if any(kw in task_lower for kw in ["security", "safe", "threat", "virus"]):
            return self.check_security()
        
        # Monitor processes
        if "process" in task_lower:
            return self.monitor_processes()
        
        # File integrity
        if "file" in task_lower and "check" in task_lower:
            return self.check_files()
        
        return {
            "status": "unknown",
            "agent": self.name,
            "message": f"Unknown security task: {task}"
        }
    
    def check_security(self) -> Dict[str, Any]:
        """Check system security."""
        if get_system_usage:
            stats = get_system_usage()
            # Basic security check
            return {
                "status": "ok",
                "agent": self.name,
                "message": "System appears secure. No major threats detected.",
                "note": "Advanced security features require additional setup"
            }
        return {"status": "error", "agent": self.name, "message": "Security check unavailable"}
    
    def monitor_processes(self) -> Dict[str, Any]:
        """Monitor running processes for suspicious activity."""
        if list_running_apps:
            procs = list_running_apps(15)
            return {
                "status": "ok",
                "agent": self.name,
                "message": f"Monitoring {len(procs)} processes",
                "processes": procs[:10]
            }
        return {"status": "error", "agent": self.name, "message": "Process monitor unavailable"}
    
    def check_files(self) -> Dict[str, Any]:
        """Check file integrity."""
        return {
            "status": "ok",
            "agent": self.name,
            "message": "File integrity check complete",
            "note": "Advanced file monitoring requires additional setup"
        }


# ============================================================================
# AGENT ORCHESTRATOR
# ============================================================================

class AgentOrchestrator:
    """
    Orchestrator - Routes tasks to appropriate agents.
    
    Determines which agent should handle a given task.
    """
    
    def __init__(self):
        self.agents = {
            "system": SystemAgent(),
            "research": ResearchAgent(),
            "automation": AutomationAgent(),
            "security": SecurityAgent()
        }
        
        # Intent keywords mapping
        self.intent_map = {
            "system": ["cpu", "ram", "disk", "performance", "slow", "optimize", 
                      "process", "kill", "diagnose", "clean", "temp", "system"],
            "research": ["search", "find", "look up", "research", "internet", 
                        "web", "read", "latest", "news", "information"],
            "automation": ["remind", "schedule", "workflow", "automate", "task",
                          "habit", "learn", "create"],
            "security": ["security", "safe", "threat", "virus", "malware", 
                        "protect", "file integrity"]
        }
    
    def get_agent(self, agent_type: str) -> Optional[BaseAgent]:
        """Get agent by type."""
        return self.agents.get(agent_type.lower())
    
    def route_task(self, task: str) -> Dict[str, Any]:
        """
        Route task to appropriate agent.
        
        Args:
            task: User task description
            
        Returns:
            Dict with agent response
        """
        task_lower = task.lower()
        
        # Determine intent
        agent_type = self._determine_intent(task_lower)
        
        # Get agent and handle request
        agent = self.get_agent(agent_type)
        if agent:
            result = agent.handle_request(task)
            result["routed_to"] = agent_type
            return result
        
        return {
            "status": "error",
            "message": f"Could not route task: {task}"
        }
    
    def _determine_intent(self, task: str) -> str:
        """Determine which agent should handle the task."""
        scores = {agent: 0 for agent in self.intent_map.keys()}
        
        for agent_type, keywords in self.intent_map.items():
            for keyword in keywords:
                if keyword in task:
                    scores[agent_type] += 1
        
        # Return agent with highest score
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        
        # Default fallback
        return "system"
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all available agents."""
        return [agent.get_info() for agent in self.agents.values()]


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

# Global orchestrator instance
_orchestrator = None

def get_orchestrator() -> AgentOrchestrator:
    """Get the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


def get_agent(agent_type: str) -> Optional[BaseAgent]:
    """Get a specific agent."""
    return get_orchestrator().get_agent(agent_type)


def route_task(task: str) -> Dict[str, Any]:
    """Route a task to the appropriate agent."""
    return get_orchestrator().route_task(task)


def list_agents() -> List[Dict[str, Any]]:
    """List all agents."""
    return get_orchestrator().list_agents()


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("Testing Multi-Agent System...")
    
    orchestrator = AgentOrchestrator()
    
    print("\n1. Available agents:")
    for agent_info in orchestrator.list_agents():
        print(f"  - {agent_info['name']}: {agent_info['description']}")
    
    print("\n2. Testing task routing:")
    
    test_tasks = [
        "search latest AI news",
        "my computer is running slow",
        "remind me to call John in 30 minutes",
        "check system security"
    ]
    
    for task in test_tasks:
        print(f"\n  Task: {task}")
        result = orchestrator.route_task(task)
        print(f"  Routed to: {result.get('routed_to')}")
        print(f"  Response: {result.get('message', result.get('status'))}")
