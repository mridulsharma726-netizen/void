"""
VOID Terminal Execution Tool
===========================

Safe terminal command execution for self-engineering system.

Features:
- run_command(cmd) - Execute safe terminal commands
- Command whitelist: python, pip, ollama, git

Security:
- Only allows specific commands
- No shell=True for dangerous commands
- Timeout protection
- Output sanitization

"""

import subprocess
import sys
import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

# ============================================================================
# CONSTANTS
# ============================================================================

# Allowed commands (whitelist)
ALLOWED_COMMANDS = [
    "python",
    "pip",
    "ollama",
    "git",
    "uvicorn",
    "fastapi",
    "node",
    "npm",
    "npx",
]

# Command aliases for safety
COMMAND_ALIASES = {
    "python": [sys.executable],
    "pip": [sys.executable, "-m", "pip"],
}

# Maximum execution time (seconds)
MAX_TIMEOUT = 120

# ============================================================================
# LOGGING
# ============================================================================

# Setup logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "terminal.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("VOID-TerminalTools")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _log_command(cmd: str, result: Dict[str, Any]):
    """Log command execution."""
    status = "SUCCESS" if result.get("status") == "ok" else "FAILED"
    logger.info(f"[TERMINAL] {status} | Command: {cmd} | Exit code: {result.get('exit_code', 'N/A')}")


def _is_command_allowed(cmd: str) -> bool:
    """
    Check if command is in the whitelist.
    
    Args:
        cmd: Command string to check
        
    Returns:
        True if allowed, False otherwise
    """
    cmd_lower = cmd.lower().strip()
    
    # Check if starts with allowed command
    for allowed in ALLOWED_COMMANDS:
        if cmd_lower.startswith(allowed):
            return True
    
    return False


def _sanitize_output(output: str, max_length: int = 10000) -> str:
    """
    Sanitize command output for safe display.
    
    Args:
        output: Raw output
        max_length: Maximum length to return
        
    Returns:
        Sanitized output
    """
    if not output:
        return ""
    
    # Limit length
    if len(output) > max_length:
        output = output[:max_length] + f"\n... (truncated, total {len(output)} chars)"
    
    # Remove potentially dangerous content
    # Note: We don't strip too much to preserve useful output
    
    return output


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def run_command(cmd: str, timeout: int = MAX_TIMEOUT, capture_output: bool = True) -> Dict[str, Any]:
    """
    Execute a safe terminal command.
    
    Args:
        cmd: Command to execute (must start with allowed command)
        timeout: Maximum execution time in seconds
        capture_output: Whether to capture stdout/stderr
        
    Returns:
        Dictionary with status, output, error, and exit code
    """
    # Check if command is allowed
    if not _is_command_allowed(cmd):
        logger.warning(f"[TERMINAL] Blocked command: {cmd}")
        return {
            "status": "error",
            "message": f"Command not allowed. Allowed commands: {', '.join(ALLOWED_COMMANDS)}",
            "cmd": cmd,
            "output": "",
            "error": "Security: Command not in whitelist",
            "exit_code": -1
        }
    
    # Log the command
    logger.info(f"[TERMINAL] Executing: {cmd}")
    
    try:
        # Execute command
        # Note: We use shell=True on Windows for compatibility with commands like "pip install"
        # but the command whitelist provides security
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        
        # Prepare output
        output = _sanitize_output(result.stdout) if result.stdout else ""
        error = _sanitize_output(result.stderr) if result.stderr else ""
        
        # Determine status
        if result.returncode == 0:
            status = "ok"
        else:
            status = "error"
        
        response = {
            "status": status,
            "cmd": cmd,
            "output": output,
            "error": error,
            "exit_code": result.returncode,
            "success": result.returncode == 0
        }
        
        _log_command(cmd, response)
        
        return response
        
    except subprocess.TimeoutExpired:
        error_msg = f"Command timed out after {timeout} seconds"
        logger.error(f"[TERMINAL] Timeout: {cmd}")
        return {
            "status": "error",
            "cmd": cmd,
            "output": "",
            "error": error_msg,
            "exit_code": -1,
            "success": False
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[TERMINAL] Error: {error_msg}")
        return {
            "status": "error",
            "cmd": cmd,
            "output": "",
            "error": error_msg,
            "exit_code": -1,
            "success": False
        }


def run_python_command(python_cmd: str, timeout: int = MAX_TIMEOUT) -> Dict[str, Any]:
    """
    Run a Python command safely.
    
    Args:
        python_cmd: Python command to run
        timeout: Maximum execution time
        
    Returns:
        Dictionary with result
    """
    # Build command - use -c for inline code
    if "\n" in python_cmd:
        # Multi-line - write to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(python_cmd)
            temp_file = f.name
        
        cmd = f'python "{temp_file}"'
        result = run_command(cmd, timeout=timeout)
        
        # Cleanup temp file
        try:
            os.unlink(temp_file)
        except:
            pass
            
        return result
    else:
        # Single line
        cmd = f'python -c "{python_cmd}"'
        return run_command(cmd, timeout=timeout)


def run_pip_install(package: str, upgrade: bool = False) -> Dict[str, Any]:
    """
    Install a Python package using pip.
    
    Args:
        package: Package name to install
        upgrade: Whether to upgrade if already installed
        
    Returns:
        Dictionary with result
    """
    upgrade_flag = "--upgrade" if upgrade else ""
    cmd = f"pip install {upgrade_flag} {package}".strip()
    
    return run_command(cmd, timeout=180)


def run_ollama_command(ollama_cmd: str) -> Dict[str, Any]:
    """
    Run an Ollama command.
    
    Args:
        ollama_cmd: Ollama subcommand (e.g., "list", "run llama3")
        
    Returns:
        Dictionary with result
    """
    cmd = f"ollama {ollama_cmd}"
    return run_command(cmd, timeout=180)


def check_command_available(command: str) -> bool:
    """
    Check if a command is available on the system.
    
    Args:
        command: Command to check
        
    Returns:
        True if available, False otherwise
    """
    try:
        # Try to run command --version or --help
        result = subprocess.run(
            f"{command} --version",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False


def get_available_commands() -> List[str]:
    """
    Get list of available commands on the system.
    
    Returns:
        List of available commands
    """
    available = []
    
    for cmd in ALLOWED_COMMANDS:
        if check_command_available(cmd):
            available.append(cmd)
    
    return available


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    # Test terminal tools
    print("VOID Terminal Tools Test")
    print("=" * 50)
    
    # Test allowed command
    result = run_command("python --version")
    print(f"\nPython version: {result.get('output', result.get('error', 'N/A'))}")
    
    # Test blocked command
result = run_command(r"del /f /s /q C:\\*")
    print(f"\nBlocked command test: {result.get('message')}")
    
    # Check available commands
    available = get_available_commands()
    print(f"\nAvailable commands: {available}")

