"""
VOID Self-Modifier Module
=======================

LLM-powered self-repair and improvement workflow.

Features:
- scan_project() - Scan project for issues and regenerate codebase map
- analyze_code() - Send code to LLM for analysis
- generate_fix() - Generate improved code from LLM
- safe_write() - Safely overwrite with backup
- rewrite_module() - Rewrite a module using the codebase map

Workflow:
1. Scan project directory
2. Regenerate codebase map
3. Resolve module path using map
4. Read relevant files
5. Send code to LLM for analysis
6. Generate improved code
7. Create backup and overwrite

Security:
- Only modifies allowed directories
- Protected directories cannot be modified
- Always creates backups before changes
- Requires developer_mode for modifications
"""

import os
import sys
import json
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime

# Import dependencies
from tools.code_tools import read_file, write_file, list_project_files, get_file_diff
from tools.error_interpreter import translate_exception, format_diagnostics_error

# Import codebase map functions
try:
    from core.codebase_map import (
        generate_codebase_map,
        load_codebase_map,
        get_module_path,
        resolve_module_path,
        is_protected_path,
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
    MAP_FILE = None

# Import logger for logging rewrite operations
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

# Ollama settings
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_TIMEOUT = 90

try:
    from server.backend.llm_client import OllamaClient
    _client = OllamaClient()
    OLLAMA_MODEL = _client.model
except Exception:
    OLLAMA_MODEL = "llama3.2:3b"

# Project root
VOID_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences from LLM output."""
    if not text:
        return text
    lines = text.strip().splitlines()
    # Remove opening fence (```python, ```py, ```)
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    # Remove closing fence
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


def _call_llm(prompt: str, system_prompt: str = None) -> Optional[str]:
    """
    Call Ollama LLM for code analysis/improvement.
    
    Args:
        prompt: User prompt
        system_prompt: Optional system prompt
        
    Returns:
        LLM response or None on error
    """
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
                return _strip_code_fences(message.get("content", "").strip())
        
        return None
        
    except Exception as e:
        print(f"[LLM CALL ERROR] {e}")
        return None


def check_ollama() -> bool:
    """Check if Ollama is running."""
    try:
        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False


# ============================================================================
# SELF-MODIFICATION FUNCTIONS
# ============================================================================

def scan_project() -> Dict[str, Any]:
    """
    Scan the project directory for files and potential issues.
    
    Returns:
        Dictionary with scan results
    """
    try:
        # Scan allowed directories
        directories = ["tools", "core", "ui", "workflows", "agent"]
        all_files = []
        
        for directory in directories:
            result = list_project_files(directory, recursive=True)
            if result["status"] == "ok":
                all_files.extend(result.get("files", []))
        
        # Categorize by extension
        by_extension = {}
        for file_info in all_files:
            ext = os.path.splitext(file_info["path"])[1]
            if ext not in by_extension:
                by_extension[ext] = []
            by_extension[ext].append(file_info)
        
        return {
            "status": "ok",
            "total_files": len(all_files),
            "by_extension": by_extension,
            "directories": directories,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Scan failed: {str(e)}"
        }


def analyze_file(file_path: str) -> Dict[str, Any]:
    """
    Read and analyze a file for potential issues.
    
    Args:
        file_path: Path to file to analyze
        
    Returns:
        Dictionary with analysis results
    """
    # Read file
    result = read_file(file_path)
    
    if result["status"] != "ok":
        return result
    
    content = result["content"]
    file_info = result["file_info"]
    
    # Basic analysis
    analysis = {
        "lines": len(content.splitlines()),
        "characters": len(content),
        "has_imports": "import " in content or "from " in content,
        "has_functions": "def " in content,
        "has_classes": "class " in content,
    }
    
    # Check for common issues
    issues = []
    
    # Check for TODO/FIXME
    if "TODO" in content or "FIXME" in content:
        issues.append("Contains TODO or FIXME comments")
    
    # Check for print statements (debug)
    if content.count("print(") > 5:
        issues.append("Contains many print statements (possible debug code)")
    
    # Check for bare except
    if "except:" in content:
        issues.append("Contains bare except clause")
    
    # Check for hardcoded values
    if len([line for line in content.splitlines() if "=" in line and '"' in line]) > 10:
        issues.append("May contain hardcoded values")
    
    return {
        "status": "ok",
        "file_info": file_info,
        "analysis": analysis,
        "issues": issues,
        "content_preview": content[:500] + "..." if len(content) > 500 else content
    }


def send_to_llm_for_improvement(file_path: str, instructions: str = "Improve this code") -> Dict[str, Any]:
    """
    Send file content to LLM for improvement.
    
    Args:
        file_path: Path to file to improve
        instructions: Instructions for improvement
        
    Returns:
        Dictionary with LLM response
    """
    # Check Ollama
    if not check_ollama():
        return {
            "status": "error",
            "message": "Ollama is not running. Cannot use AI improvement features."
        }
    
    # Read file
    result = read_file(file_path)
    
    if result["status"] != "ok":
        return result
    
    content = result["content"]
    file_info = result["file_info"]
    
    # Create prompt for LLM
    prompt = f"""Please analyze and improve the following code from {file_path}.

Current file info:
- Lines: {file_info.get('lines', 'unknown')}
- Size: {file_info.get('size', 'unknown')} bytes

Instructions: {instructions}

CODE:
```{content}
```

Provide improved code with your fixes and improvements applied. Only output the code, no explanations unless there are important notes."""

    # Call LLM
    improved_code = _call_llm(prompt)
    
    if improved_code is not None:
        improved_code = _strip_code_fences(improved_code)
    
    if improved_code is None:
        return {
            "status": "error",
            "message": "Failed to get response from LLM"
        }
    
    return {
        "status": "ok",
        "original_path": file_path,
        "improved_code": improved_code,
        "original_lines": file_info.get("lines", 0),
        "improved_lines": len(improved_code.splitlines())
    }


def apply_improvement(file_path: str, improved_code: str, create_backup: bool = True) -> Dict[str, Any]:
    """
    Apply improved code to a file.
    
    Args:
        file_path: Path to file to update
        improved_code: New code content
        create_backup: Whether to create backup first
        
    Returns:
        Dictionary with result
    """
    # Enforce strict location locks to prevent overwriting core system files
    if is_protected_path and is_protected_path(file_path):
        return {
            "status": "error",
            "message": f"Security violation: Overwriting protected path '{file_path}' is strictly blocked.",
            "error_type": "protected"
        }

    # Get diff first
    diff_result = get_file_diff(file_path, improved_code)
    
    if diff_result["status"] != "ok":
        return diff_result
    
    if not diff_result["diff"]["has_changes"]:
        return {
            "status": "warning",
            "message": "No changes to apply - code is identical"
        }
    
    # Write the improved code (safe write with syntax validation)
    from tools.code_tools import safe_write_file
    result = safe_write_file(file_path, improved_code, create_backup=create_backup)
    
    if result["status"] == "ok":
        return {
            "status": "ok",
            "message": f"Successfully updated {file_path}",
            "backup": result.get("backup"),
            "diff": diff_result["diff"]
        }
    
    return result


def rewrite_module(module_name: str, instructions: str = "Improve this module") -> Dict[str, Any]:
    """
    Complete workflow to rewrite a module.
    
    Uses the codebase map to resolve module names to file paths.
    
    Args:
        module_name: Name of the module to rewrite (e.g., "voice_tts")
        instructions: Instructions for the LLM
        
    Returns:
        Dictionary with complete result
    """
    # Step 0: Check if protected directory
    if is_protected_path and is_protected_path(module_name):
        return {
            "status": "error",
            "message": "This location is protected and cannot be modified.",
            "error_type": "protected"
        }
    
    # Step 1: Try to resolve the module path using codebase map
    resolved_path = None
    
    if resolve_module_path:
        resolved_path = resolve_module_path(module_name)
    
    # If not found, try direct path
    if not resolved_path:
        if os.path.exists(module_name):
            resolved_path = module_name
        elif os.path.exists(f"tools/{module_name}.py"):
            resolved_path = f"tools/{module_name}.py"
        elif os.path.exists(f"core/{module_name}.py"):
            resolved_path = f"core/{module_name}.py"
    
    # If still not found, return error with helpful message
    if not resolved_path:
        # Try to get list of available modules
        available = []
        if load_codebase_map:
            module_map = load_codebase_map()
            available = sorted(module_map.keys())[:10]  # Show first 10
        
        available_msg = ""
        if available:
            available_msg = f"\n\nAvailable modules: {', '.join(available)}"
        
        return {
            "status": "error",
            "message": f"Module '{module_name}' could not be located in the project.{available_msg}\n\nSuggestion: Run 'scan project' to refresh the codebase map.",
            "error_type": "not_found",
            "suggestion": "Run 'scan project' to refresh the codebase map."
        }
    
    # Log the rewrite operation
    if LOGGING_AVAILABLE:
        log_file_modification(resolved_path, "rewrite_start", f"Starting rewrite for {module_name}")
    
    # Step 2: Analyze file
    analyze_result = analyze_file(resolved_path)
    
    if analyze_result["status"] != "ok":
        return {
            "status": "error",
            "message": f"Could not read module: {analyze_result.get('message', 'Unknown error')}",
            "resolved_path": resolved_path
        }
    
    # Step 3: Get LLM improvement
    improve_result = send_to_llm_for_improvement(resolved_path, instructions)
    
    if improve_result["status"] != "ok":
        return {
            "status": "error",
            "message": f"LLM improvement failed: {improve_result.get('message', 'Unknown error')}",
            "resolved_path": resolved_path
        }
    
    # Step 4: Apply improvement
    apply_result = apply_improvement(resolved_path, improve_result["improved_code"])
    
    # Log the result
    if LOGGING_AVAILABLE:
        log_result = "success" if apply_result.get("status") == "ok" else "failed"
        log_file_modification(resolved_path, f"rewrite_{log_result}", f"Rewrite complete: {apply_result.get('message', '')}")
    
    return {
        "status": apply_result.get("status", "unknown"),
        "module": module_name,
        "resolved_path": resolved_path,
        "analysis": analyze_result.get("analysis"),
        "issues_found": analyze_result.get("issues", []),
        "improvement": {
            "original_lines": improve_result.get("original_lines"),
            "improved_lines": improve_result.get("improved_lines")
        },
        "result": apply_result
    }


def improve_system() -> Dict[str, Any]:
    """
    Run system-wide improvement scan.
    
    Returns:
        Dictionary with improvement results
    """
    # Check Ollama
    if not check_ollama():
        return {
            "status": "error",
            "message": "Ollama is not running. Cannot use AI improvement features."
        }
    
    # Scan project
    scan_result = scan_project()
    
    if scan_result["status"] != "ok":
        return scan_result
    
    # Get list of Python files
    python_files = []
    by_ext = scan_result.get("by_extension", {})
    if ".py" in by_ext:
        python_files = by_ext[".py"]
    
    # Analyze each file (top 10 by size)
    python_files.sort(key=lambda x: x.get("size", 0), reverse=True)
    top_files = python_files[:10]
    
    analyses = []
    for file_info in top_files:
        analysis = analyze_file(file_info["path"])
        if analysis["status"] == "ok" and analysis.get("issues"):
            analyses.append({
                "file": file_info["path"],
                "issues": analysis["issues"]
            })
    
    return {
        "status": "ok",
        "scan": scan_result,
        "files_analyzed": len(top_files),
        "files_with_issues": len(analyses),
        "issues_by_file": analyses,
        "recommendation": f"Found {len(analyses)} files with potential issues. Use 'rewrite module [path]' to improve specific files."
    }


# ============================================================================
# SELF-REPAIR WORKFLOW
# ============================================================================

def self_repair_workflow() -> Dict[str, Any]:
    """
    Complete self-repair workflow.
    
    Steps:
    1. Run diagnostics
    2. Identify issues
    3. Attempt fixes
    4. Report results
    
    Returns:
        Dictionary with repair results
    """
    # Import diagnostics
    try:
        from tools.diagnostics import run_full_diagnostics
        from tools.self_repair import repair_system
    except ImportError as e:
        return {
            "status": "error",
            "message": f"Cannot import repair modules: {str(e)}"
        }
    
    # Run diagnostics
    diag_result = run_full_diagnostics()
    
    if diag_result.get("overall_status") == "ok":
        return {
            "status": "ok",
            "message": "System is healthy - no repairs needed",
            "diagnostics": diag_result
        }
    
    # Attempt repair
    repair_result = repair_system()
    
    # Translate errors to human-readable format
    translated_issues = []
    for issue in repair_result.get("remaining_issues", []):
        translated = format_diagnostics_error("system", issue)
        translated_issues.append(translated)
    
    return {
        "status": repair_result.get("status", "unknown"),
        "message": f"Repaired {len(repair_result.get('actions_taken', []))} items",
        "actions_taken": repair_result.get("actions_taken", []),
        "remaining_issues": translated_issues,
        "diagnostics": diag_result
    }


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

def handle_repair_command() -> Dict[str, Any]:
    """Handle 'repair yourself' command."""
    return self_repair_workflow()


def handle_scan_command(target: str = None) -> Dict[str, Any]:
    """Handle 'scan project' command."""
    if target:
        # Scan specific file or directory
        return analyze_file(target) if os.path.splitext(target)[1] else list_project_files(target)
    else:
        # Scan entire project
        return scan_project()


def handle_rewrite_command(module_path: str, instructions: str = "Improve and fix any issues") -> Dict[str, Any]:
    """Handle 'rewrite module' command."""
    return rewrite_module(module_path, instructions)


def handle_improve_command() -> Dict[str, Any]:
    """Handle 'improve system' command."""
    return improve_system()


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    # Test self-modifier
    import json
    
    print("VOID Self-Modifier Test")
    print("=" * 50)
    
    # Test scan
    result = scan_project()
    print(f"\nScan project: {result.get('status')}")
    print(f"Total files: {result.get('total_files', 0)}")

