"""
VOID Architecture Explainer
============================

Provides real architecture descriptions based on actual project structure
instead of hallucinating components.

Features:
- Scans actual project directories
- Builds architecture description from real files
- Intercepts architecture-related prompts
"""

import os
import json
from typing import Dict, List, Any

# Project root
VOID_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Architecture trigger phrases
ARCHITECTURE_TRIGGERS = [
    "explain your system architecture",
    "describe your architecture",
    "how are you built",
    "analyze your system",
    "what is your architecture",
    "tell me about your architecture",
    "how do you work",
    "what components do you have",
    "describe your system",
    "explain your design",
    "what makes up your system",
    "your architecture",
]


def is_architecture_query(text: str) -> bool:
    """
    Check if the user query is about system architecture.
    
    Args:
        text: User input text
        
    Returns:
        True if this is an architecture query
    """
    text_lower = text.lower().strip()
    
    for trigger in ARCHITECTURE_TRIGGERS:
        if trigger in text_lower:
            return True
    
    return False


def scan_project_structure() -> Dict[str, Any]:
    """
    Scan the actual project structure.
    
    Returns:
        Dictionary with project structure info
    """
    structure = {
        "directories": {},
        "files": {},
        "total_files": 0,
    }
    
    # Key directories to scan
    scan_dirs = ["core", "tools", "ui", "workflows", "agent", "desktop", "data", "logs"]
    
    for dir_name in scan_dirs:
        dir_path = os.path.join(VOID_ROOT, dir_name)
        
        if os.path.isdir(dir_path):
            file_count = 0
            files = []
            
            for root, dirs, files_list in os.walk(dir_path):
                # Skip __pycache__
                if "__pycache__" in root:
                    continue
                    
                for f in files_list:
                    if not f.startswith("."):
                        file_count += 1
                        rel_path = os.path.relpath(os.path.join(root, f), VOID_ROOT)
                        files.append(rel_path)
            
            structure["directories"][dir_name] = {
                "count": file_count,
                "files": files[:10]  # Limit to first 10 for display
            }
            structure["total_files"] += file_count
    
    # Main files
    main_files = ["main.py", "server.py", "package.json", "requirements.txt"]
    for mf in main_files:
        mf_path = os.path.join(VOID_ROOT, mf)
        if os.path.exists(mf_path):
            structure["files"][mf] = True
    
    return structure


def get_module_description(module_name: str) -> str:
    """
    Get a brief description of a module based on its name and content.
    
    Args:
        module_name: Name of the module
        
    Returns:
        Brief description string
    """
    descriptions = {
        "brain": "AI brain - processes queries using Ollama LLM",
        "memory": "Memory system - stores and retrieves conversations",
        "router": "Command router - routes user commands to appropriate handlers",
        "agent": "Agent system - manages AI agent workflows",
        "logger": "Logging system - records system events",
        "event_bus": "Event bus - handles inter-component events",
        "intent_router": "Intent detection - understands user intent",
        "command_interpreter": "Command interpreter - parses user commands",
        "voice_tts": "Text-to-speech - converts text to audio output",
        "voice_stt": "Speech-to-text - converts audio input to text",
        "system_tools": "System tools - system information and control",
        "code_tools": "Code tools - file operations for self-modification",
        "self_modifier": "Self-modifier - allows VOID to rewrite its own code",
        "code_editor_agent": "Code editor agent - AI-powered code improvement",
        "workflow_engine": "Workflow engine - executes automated workflows",
    }
    
    return descriptions.get(module_name.lower(), f"{module_name} module")


def build_architecture_description() -> str:
    """
    Build a real architecture description from scanned project structure.
    
    Returns:
        Formatted architecture description
    """
    structure = scan_project_structure()
    
    # Build the description
    description = """# VOID Architecture

Based on actual project structure scan:

## User Interface
"""
    
    # Check for Electron UI
    if "desktop" in structure["directories"]:
        description += "- Electron desktop UI (desktop/main.js)\n"
    if "ui" in structure["directories"]:
        description += f"- Web UI (ui/) - {structure['directories']['ui']['count']} files\n"
    
    description += """
## Backend
"""
    
    # Backend files
    if "main.py" in structure["files"]:
        description += "- Python FastAPI server (main.py)\n"
    if "server.py" in structure["files"]:
        description += "- Alternative server (server.py)\n"
    
    description += """
## AI Model
"""
    
    description += "- Local Ollama model (llama3.2:3b)\n"
    description += "- No external cloud services required\n"
    
    description += """
## Core System
"""
    
    # Core modules
    core_modules = []
    if "core" in structure["directories"]:
        for f in structure["directories"]["core"]["files"]:
            if f.endswith(".py"):
                module = f.replace(".py", "").replace("core/", "")
                core_modules.append(module)
    
    for mod in core_modules[:8]:
        desc = get_module_description(mod)
        description += f"- {mod}: {desc}\n"
    
    description += """
## Tools
"""
    
    # Tools modules
    if "tools" in structure["directories"]:
        tool_count = structure["directories"]["tools"]["count"]
        description += f"- tools/ directory - {tool_count} tool modules\n"
        
        # List some key tools
        for f in structure["directories"]["tools"]["files"][:5]:
            if f.endswith(".py"):
                tool = f.replace(".py", "").replace("tools/", "")
                desc = get_module_description(tool)
                description += f"  - {tool}: {desc}\n"
    
    description += """
## Agent System
"""
    
    if "agent" in structure["directories"]:
        agent_count = structure["directories"]["agent"]["count"]
        description += f"- agent/ directory - {agent_count} agent modules\n"
    
    description += """
## Workflows
"""
    
    if "workflows" in structure["directories"]:
        wf_count = structure["directories"]["workflows"]["count"]
        description += f"- workflows/ directory - {wf_count} workflow modules\n"
    
    description += f"""
## Data & Storage
"""
    
    if "data" in structure["directories"]:
        description += "- data/ directory - memory and configuration storage\n"
    if "logs" in structure["directories"]:
        description += "- logs/ directory - system logs\n"
    
    description += f"""
## Statistics
- Total project files: {structure['total_files']}
- Directories: {len(structure['directories'])}

## Key Features
- Self-modification: VOID can analyze and improve its own code
- Voice I/O: Speech-to-text and text-to-speech
- Local AI: Runs entirely offline with Ollama
- Tool system: Extensible tool framework
- Workflow automation: Automated task execution
"""
    
    return description


def explain_architecture() -> str:
    """
    Main function to explain VOID's architecture.
    
    Returns:
        Architecture description string
    """
    return build_architecture_description()


# Test
if __name__ == "__main__":
    print("Testing architecture explainer...")
    print()
    
    # Test trigger detection
    test_queries = [
        "explain your system architecture",
        "how are you built",
        "what is the weather today",
        "describe your architecture",
    ]
    
    for q in test_queries:
        result = is_architecture_query(q)
        print(f"Query: '{q}' -> is_architecture: {result}")
    
    print()
    print("=" * 60)
    print("ARCHITECTURE DESCRIPTION:")
    print("=" * 60)
    print(explain_architecture())
