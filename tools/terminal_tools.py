"""
VOID Terminal Execution Tool
===========================

Safe terminal command execution for self-engineering system.

Features:
- run_command(cmd)          - Execute safe terminal commands (sync)
- execute_sandboxed(cmd)    - Approval-gated async execution with streaming
- Command allowlist:        python, pip, ollama, git, npm, npx, node,
                            flutter, yarn, cargo, dotnet, uvicorn, fastapi

Security:
- Only allows allowlisted commands (prefix match)
- Blocklist of destructive patterns (rm -rf, del /f, format, shutdown, etc.)
- User approval required for all sandboxed executions (30s timeout → auto-deny)
- No shell=True for dangerous commands
- Timeout protection (120s default)
- Full execution history logged to logs/terminal_history.log
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

# Allowed commands (allowlist — matched as prefix of the command string)
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
    "flutter",
    "yarn",
    "cargo",
    "dotnet",
    "docker",
    "pytest",
]

# Blocklist: destructive patterns that are NEVER allowed, even if prefix matches
BLOCKED_PATTERNS = [
    "rm -rf",
    "rm -fr",
    "del /f",
    "del /q",
    "format c",
    "format d",
    "shutdown",
    "reg delete",
    "reg add",
    "netsh",
    "net user",
    "sc delete",
    "taskkill /f",
    "rmdir /s",
    "rd /s",
    "cipher /w",
    "diskpart",
    "bcdedit",
    "sfc /scannow",
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
history_log_file = os.path.join(log_dir, "terminal_history.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("VOID-TerminalTools")
_history_logger = logging.getLogger("VOID-TerminalHistory")
_history_handler = logging.FileHandler(history_log_file, encoding='utf-8')
_history_handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s'))
_history_logger.addHandler(_history_logger.handlers[0] if _history_logger.handlers else _history_handler)
if not _history_logger.handlers:
    _history_logger.addHandler(_history_handler)
_history_logger.setLevel(logging.INFO)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _log_command(cmd: str, result: Dict[str, Any]):
    """Log command execution."""
    status = "SUCCESS" if result.get("status") == "ok" else "FAILED"
    logger.info(f"[TERMINAL] {status} | Command: {cmd} | Exit code: {result.get('exit_code', 'N/A')}")


def _is_command_allowed(cmd: str) -> bool:
    """
    Check if command is in the allowlist AND not matching the blocklist.
    
    Args:
        cmd: Command string to check
        
    Returns:
        True if allowed and not destructive, False otherwise
    """
    cmd_lower = cmd.lower().strip()
    
    # Check blocklist first (takes priority)
    for blocked in BLOCKED_PATTERNS:
        if blocked in cmd_lower:
            logger.warning(f"[TERMINAL] Blocked destructive pattern '{blocked}' in: {cmd}")
            return False
    
    # Check if starts with an allowed command
    for allowed in ALLOWED_COMMANDS:
        if cmd_lower.startswith(allowed):
            return True
    
    return False


def _is_destructive(cmd: str) -> bool:
    """Check if command matches any destructive blocked pattern."""
    cmd_lower = cmd.lower().strip()
    return any(p in cmd_lower for p in BLOCKED_PATTERNS)


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
        import shlex
        import shutil
        
        try:
            cmd_args = shlex.split(cmd, posix=False)
        except Exception:
            cmd_args = cmd.split()
            
        if not cmd_args:
            return {
                "status": "error",
                "cmd": cmd,
                "output": "",
                "error": "Empty command string",
                "exit_code": -1,
                "success": False
            }
            
        base_cmd = cmd_args[0]
        base_cmd_lower = base_cmd.lower().strip()
        if base_cmd_lower in COMMAND_ALIASES:
            alias_args = COMMAND_ALIASES[base_cmd_lower]
            cmd_args = alias_args + cmd_args[1:]
        else:
            resolved_exe = shutil.which(base_cmd)
            if resolved_exe:
                cmd_args[0] = resolved_exe

        result = subprocess.run(
            cmd_args,
            shell=False,
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
    import shutil
    try:
        resolved = shutil.which(command) or command
        result = subprocess.run(
            [resolved, "--version"],
            shell=False,
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
# SANDBOXED EXECUTION WITH APPROVAL GATE
# ============================================================================

async def execute_sandboxed(
    command: str,
    cwd: Optional[str] = None,
    timeout: int = MAX_TIMEOUT,
    approval_required: bool = True,
) -> Dict[str, Any]:
    """
    Execute a terminal command with user approval gate.

    All commands go through:
    1. Blocklist check (immediate reject if destructive)
    2. Allowlist check (reject if not in approved list)
    3. User approval via Electron WebSocket modal (30s timeout → auto-deny)
    4. Execution with output captured
    5. Logging to terminal_history.log

    Args:
        command:          The command string to execute.
        cwd:              Working directory (defaults to project root).
        timeout:          Execution timeout in seconds (default 120).
        approval_required: Set False only for trusted internal calls.

    Returns:
        Dict with status, output, error, exit_code, approved fields.
    """
    cmd_clean = command.strip()

    # 1. Blocklist check
    if _is_destructive(cmd_clean):
        logger.warning(f"[TERMINAL-SANDBOX] BLOCKED destructive command: {cmd_clean}")
        _history_logger.info(f"BLOCKED | {cmd_clean}")
        return {
            "status": "blocked",
            "message": "Command matches a destructive pattern and was blocked by VOID's security policy.",
            "cmd": cmd_clean,
            "output": "",
            "error": "Security block",
            "exit_code": -1,
            "approved": False,
        }

    # 2. Allowlist check
    if not _is_command_allowed(cmd_clean):
        logger.warning(f"[TERMINAL-SANDBOX] NOT ALLOWED: {cmd_clean}")
        _history_logger.info(f"DENIED(allowlist) | {cmd_clean}")
        return {
            "status": "error",
            "message": (
                f"Command not allowed. Permitted prefixes: "
                f"{', '.join(ALLOWED_COMMANDS)}"
            ),
            "cmd": cmd_clean,
            "output": "",
            "error": "Command not in allowlist",
            "exit_code": -1,
            "approved": False,
        }

    # 3. User approval
    if approval_required:
        try:
            from server.backend.fs_tools import request_approval
            approved = await request_approval(
                operation="Run Terminal Command",
                path=cwd or os.getcwd(),
                details=f"Command: `{cmd_clean}`",
                timeout=30.0,
            )
        except ImportError:
            # fs_tools not available — default deny
            logger.warning("[TERMINAL-SANDBOX] fs_tools.request_approval unavailable — denying")
            approved = False

        if not approved:
            _history_logger.info(f"DENIED(user) | {cmd_clean}")
            return {
                "status": "denied",
                "message": "User did not approve command execution.",
                "cmd": cmd_clean,
                "output": "",
                "error": "User denied",
                "exit_code": -1,
                "approved": False,
            }

    # 4. Execute
    logger.info(f"[TERMINAL-SANDBOX] Executing: {cmd_clean}")
    _history_logger.info(f"EXEC | {cmd_clean} | cwd={cwd}")
    result = run_command(cmd_clean, timeout=timeout)
    result["approved"] = True

    # 5. Log outcome
    outcome = "SUCCESS" if result.get("status") == "ok" else "FAILED"
    _history_logger.info(f"{outcome} | exit={result.get('exit_code')} | {cmd_clean}")
    return result


# ============================================================================
# STATUS
# ============================================================================

def get_terminal_status() -> Dict[str, Any]:
    """Return terminal tools status for the monitoring dashboard."""
    available = get_available_commands()
    return {
        "allowed_commands": ALLOWED_COMMANDS,
        "available_commands": available,
        "blocked_patterns_count": len(BLOCKED_PATTERNS),
        "history_log": history_log_file,
    }


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

    # Status
    print(f"\nStatus: {get_terminal_status()}")
