"""
VOID Code Editor Agent
======================

Allows VOID to rewrite its own modules using LLM.

Features:
- rewrite_module() - Rewrite a module using codebase map
- get_available_modules() - List all available modules
- validate_module() - Check if module exists and is editable
- analyze_module() - Analyze a module for potential improvements

Dependencies:
- core.codebase_map - Module path resolution
- tools.code_tools - File operations
- core.logger - Action logging
"""

import os
import json
from typing import Dict, Any, List, Optional

# Import dependencies
try:
    from core.codebase_map import (
        generate_codebase_map,
        load_codebase_map,
        get_module_path,
        resolve_module_path,
        is_protected_path,
        get_all_modules,
        MAP_FILE
    )
    CODEBASE_MAP_AVAILABLE = True
except ImportError:
    CODEBASE_MAP_AVAILABLE = False
    generate_codebase_map = None
    load_codebase_map = None
    get_module_path = None
    resolve_module_path = None
    is_protected_path = None
    get_all_modules = None
    MAP_FILE = None

try:
    from tools.code_tools import read_file, write_file, list_project_files, safe_write_file
    CODE_TOOLS_AVAILABLE = True
except ImportError:
    CODE_TOOLS_AVAILABLE = False
    read_file = None
    write_file = None
    list_project_files = None
    safe_write_file = None

try:
    from core.logger import log_file_modification, log_event
    LOGGING_AVAILABLE = True
except ImportError:
    LOGGING_AVAILABLE = False
    def log_file_modification(*args, **kwargs): pass
    def log_event(*args, **kwargs): pass

# ============================================================================
# CONSTANTS
# ============================================================================

VOID_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "llama3.2:3b"
OLLAMA_TIMEOUT = 90


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _call_llm(prompt: str, system_prompt: str = None) -> Optional[str]:
    """
    Call Ollama LLM for code analysis/improvement.
    
    Args:
        prompt: User prompt
        system_prompt: Optional system prompt
        
    Returns:
        LLM response or None on error
    """
    import requests
    
    if system_prompt is None:
        system_prompt = """You are a helpful code improvement assistant.
Analyze the provided code and suggest improvements.
When asked to fix or improve code, provide the complete improved code.
Only output the code, no explanations unless asked."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        if isinstance(data, dict):
            message = data.get("message", {})
            if isinstance(message, dict):
                return message.get("content", "").strip()
        
        return None
        
    except Exception as e:
        print(f"[LLM CALL ERROR] {e}")
        return None


def check_ollama() -> bool:
    """Check if Ollama is running."""
    import requests
    try:
        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False


# ============================================================================
# MAIN FUNCTIONS
# ============================================================================

def validate_module(module_name: str) -> Dict[str, Any]:
    """
    Validate if a module exists and is editable.
    
    Args:
        module_name: Name of the module to validate
        
    Returns:
        Dictionary with validation result
    """
    if not CODEBASE_MAP_AVAILABLE:
        return {
            "valid": False,
            "message": "Codebase map not available"
        }
    
    # Check protected paths
    if is_protected_path and is_protected_path(module_name):
        return {
            "valid": False,
            "message": "This location is protected and cannot be modified"
        }
    
    # Try to resolve module path
    resolved_path = None
    if resolve_module_path:
        resolved_path = resolve_module_path(module_name)
    
    if not resolved_path:
        return {
            "valid": False,
            "message": f"Module '{module_name}' not found in codebase"
        }
    
    # Check if resolved path is protected
    if is_protected_path and is_protected_path(resolved_path):
        return {
            "valid": False,
            "message": "This location is protected and cannot be modified"
        }
    
    # Verify file exists
    full_path = os.path.join(VOID_ROOT, resolved_path)
    if not os.path.exists(full_path):
        return {
            "valid": False,
            "message": f"Module file not found: {resolved_path}"
        }
    
    return {
        "valid": True,
        "module_name": module_name,
        "path": resolved_path,
        "full_path": full_path
    }


def get_available_modules() -> List[str]:
    """
    Get list of all available modules in the codebase.
    
    Returns:
        List of module names
    """
    if not CODEBASE_MAP_AVAILABLE:
        return []
    
    if get_all_modules:
        return get_all_modules()
    
    # Fallback: load directly from map file
    if os.path.exists(MAP_FILE):
        try:
            with open(MAP_FILE, 'r', encoding='utf-8') as f:
                module_map = json.load(f)
            return sorted(module_map.keys())
        except:
            pass
    
    return []


def analyze_module(module_name: str) -> Dict[str, Any]:
    """
    Analyze a module for potential improvements.
    
    Args:
        module_name: Name of the module to analyze
        
    Returns:
        Dictionary with analysis results
    """
    # Validate module
    validation = validate_module(module_name)
    if not validation.get("valid"):
        return {
            "status": "error",
            "message": validation.get("message", "Validation failed")
        }
    
    resolved_path = validation["path"]
    
    # Read file
    if not CODE_TOOLS_AVAILABLE:
        return {
            "status": "error",
            "message": "Code tools not available"
        }
    
    result = read_file(resolved_path)
    
    if result.get("status") != "ok":
        return {
            "status": "error",
            "message": f"Failed to read file: {result.get('message', 'Unknown error')}"
        }
    
    content = result["content"]
    file_info = result.get("file_info", {})
    
    # Basic analysis
    analysis = {
        "path": resolved_path,
        "lines": file_info.get("lines", len(content.splitlines())),
        "size": file_info.get("size", len(content)),
        "has_todos": "TODO" in content or "FIXME" in content,
        "has_debug": "print(" in content,
        "has_bare_except": "except:" in content,
    }
    
    # Check for common issues
    issues = []
    if analysis["has_todos"]:
        issues.append("Contains TODO or FIXME comments")
    if content.count("print(") > 5:
        issues.append("Contains many print statements (possible debug code)")
    if "except:" in content:
        issues.append("Contains bare except clause")
    
    return {
        "status": "ok",
        "module_name": module_name,
        "analysis": analysis,
        "issues": issues,
        "can_improve": len(issues) > 0 or True  # Always can improve
    }


def rewrite_module(module_name: str, instructions: str = "Improve this code") -> Dict[str, Any]:
    """
    Rewrite a module using LLM.
    
    Args:
        module_name: Name of the module to rewrite
        instructions: Instructions for the LLM
        
    Returns:
        Dictionary with rewrite result
    """
    # Log the operation
    if LOGGING_AVAILABLE:
        log_file_modification(module_name, "rewrite_start", f"Starting rewrite for {module_name}")
    
    # Check Ollama
    if not check_ollama():
        if LOGGING_AVAILABLE:
            log_file_modification(module_name, "rewrite_failed", "Ollama not running")
        return {
            "status": "error",
            "message": "Ollama is not running. Cannot use AI improvement features."
        }
    
    # Validate module
    validation = validate_module(module_name)
    if not validation.get("valid"):
        if LOGGING_AVAILABLE:
            log_file_modification(module_name, "rewrite_failed", validation.get("message"))
        return {
            "status": "error",
            "message": validation.get("message", "Validation failed")
        }
    
    resolved_path = validation["path"]
    
    # Read file
    if not CODE_TOOLS_AVAILABLE:
        return {
            "status": "error",
            "message": "Code tools not available"
        }
    
    read_result = read_file(resolved_path)
    
    if read_result.get("status") != "ok":
        if LOGGING_AVAILABLE:
            log_file_modification(resolved_path, "rewrite_failed", "Failed to read file")
        return {
            "status": "error",
            "message": f"Failed to read file: {read_result.get('message', 'Unknown error')}"
        }
    
    content = read_result["content"]
    file_info = read_result.get("file_info", {})
    
    # Create prompt for LLM
    prompt = f"""Please analyze and improve the following code from {resolved_path}.

File info:
- Lines: {file_info.get('lines', 'unknown')}
- Size: {file_info.get('size', 'unknown')} bytes

Instructions: {instructions}

CODE:
```{content}
```

Provide improved code with your fixes and improvements applied. Only output the code, no explanations unless there are important notes."""

    # Call LLM
    improved_code = _call_llm(prompt)
    
    if improved_code is None:
        if LOGGING_AVAILABLE:
            log_file_modification(resolved_path, "rewrite_failed", "LLM call failed")
        return {
            "status": "error",
            "message": "Failed to get response from LLM"
        }
    
    # Write improved code using safe_write (validates syntax first!)
    if safe_write_file:
        write_result = safe_write_file(resolved_path, improved_code, create_backup=True)
    else:
        # Fallback to regular write if safe_write not available
        write_result = write_file(resolved_path, improved_code, create_backup=True)
    
    if write_result.get("status") != "ok":
        if LOGGING_AVAILABLE:
            log_file_modification(resolved_path, "rewrite_failed", "Failed to write file")
        return {
            "status": "error",
            "message": f"Failed to write improved code: {write_result.get('message', 'Unknown error')}"
        }
    
    # Log success
    if LOGGING_AVAILABLE:
        log_file_modification(resolved_path, "rewrite_success", f"Rewrote {module_name}")
        log_event("rewrite_module", f"Successfully rewrote {module_name}", {
            "module": module_name,
            "path": resolved_path,
            "original_lines": file_info.get("lines", 0),
            "improved_lines": len(improved_code.splitlines())
        })
    
    return {
        "status": "ok",
        "message": f"Successfully rewrote module: {module_name}",
        "module": module_name,
        "path": resolved_path,
        "original_lines": file_info.get("lines", 0),
        "improved_lines": len(improved_code.splitlines()),
        "backup": write_result.get("backup")
    }


def scan_project() -> Dict[str, Any]:
    """
    Scan the project and return overview.
    
    Returns:
        Dictionary with project scan results
    """
    # Regenerate codebase map
    if CODEBASE_MAP_AVAILABLE and generate_codebase_map:
        map_result = generate_codebase_map(force_refresh=True)
    else:
        map_result = {"status": "error", "message": "Codebase map not available"}
    
    # Get file counts
    directories = ["tools", "core", "ui", "workflows", "agent"]
    file_counts = {}
    total_files = 0
    
    for directory in directories:
        if CODE_TOOLS_AVAILABLE:
            result = list_project_files(directory, recursive=True)
            if result.get("status") == "ok":
                count = len(result.get("files", []))
                file_counts[directory] = count
                total_files += count
    
    # Get available modules
    modules = get_available_modules()
    
    return {
        "status": "ok",
        "total_files": total_files,
        "files_by_directory": file_counts,
        "available_modules": modules[:20],  # Limit to 20 for display
        "total_modules": len(modules)
    }


def improve_self() -> Dict[str, Any]:
    """
    Self-improvement workflow.
    
    Steps:
    1. Scan project
    2. Identify candidate modules
    3. Rewrite the most important one
    
    Returns:
        Dictionary with improvement results
    """
    # Check Ollama
    if not check_ollama():
        return {
            "status": "error",
            "message": "Ollama is not running. Cannot use AI improvement features."
        }
    
    # Scan project first
    scan_result = scan_project()
    
    if scan_result.get("status") != "ok":
        return scan_result
    
    # Get modules to improve (prioritize core tools)
    priority_modules = ["voice_tts", "voice_stt", "brain", "memory", "router"]
    available = scan_result.get("available_modules", [])
    
    # Find a module to improve
    module_to_improve = None
    for mod in priority_modules:
        if mod in available:
            module_to_improve = mod
            break
    
    if not module_to_improve and available:
        module_to_improve = available[0]
    
    if not module_to_improve:
        return {
            "status": "error",
            "message": "No modules available to improve"
        }
    
    # Rewrite the module
    rewrite_result = rewrite_module(
        module_to_improve, 
        "Improve this code. Fix any bugs, improve performance, and add comments."
    )
    
    return {
        "status": "ok",
        "scan_result": scan_result,
        "module_improved": module_to_improve,
        "rewrite_result": rewrite_result
    }


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

def handle_rewrite_command(module_name: str) -> Dict[str, Any]:
    """
    Handle 'rewrite module' command.
    
    Args:
        module_name: Name of the module to rewrite
        
    Returns:
        Result dictionary
    """
    return rewrite_module(module_name)


def handle_scan_command() -> Dict[str, Any]:
    """
    Handle 'scan project' command.
    
    Returns:
        Scan result dictionary
    """
    return scan_project()


def handle_improve_self_command() -> Dict[str, Any]:
    """
    Handle 'improve yourself' command.
    
    Returns:
        Improvement result dictionary
    """
    return improve_self()


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("VOID Code Editor Agent Test")
    print("=" * 50)
    
    # Test scan
    result = scan_project()
    print(f"\nScan project: {result.get('status')}")
    print(f"Total files: {result.get('total_files', 0)}")
    print(f"Total modules: {result.get('total_modules', 0)}")
    
    # Test available modules
    modules = get_available_modules()
    print(f"\nAvailable modules ({len(modules)}):")
    for m in modules[:10]:
        print(f"  - {m}")

