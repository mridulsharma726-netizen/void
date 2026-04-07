"""
VOID Command Interpreter
=======================

Deterministic command layer that runs BEFORE the LLM.
Commands starting with "VOID" are interpreted instantly without LLM reasoning.

Usage:
    from core.command_interpreter import interpret_command, execute_command
    
    result = interpret_command("VOID open chrome")
    if result:
        response = execute_command(result)
"""

import re
import subprocess
import platform
import difflib
from typing import Dict, Any, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VOID-CommandInterpreter")

# ========================================
# APP/KILL MAPS - SINGLE CLEAN DEFINITION
# ========================================

APP_MAP = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "browser": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "msedge": "msedge",
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "code": "code",
    "notepad": "notepad",
    "note": "notepad",
    "notes": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "cmd": "cmd",
    "command prompt": "cmd",
    "terminal": "wt",
    "powershell": "powershell",
    "explorer": "explorer",
    "file explorer": "explorer",
    "spotify": "spotify",
    "discord": "discord",
    "slack": "slack",
    "teams": "teams",
    "zoom": "zoom",
    "vlc": "vlc",
    "vlc media player": "vlc",
}

KILL_MAP = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "browser": "chrome.exe",
    "msedge": "msedge.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "notepad": "notepad.exe",
    "note": "notepad.exe",
    "notes": "notepad.exe",
    "code": "Code.exe",
    "vscode": "Code.exe",
    "vs code": "Code.exe",
    "visual studio code": "Code.exe",
    "calculator": "Calculator.exe",
    "calc": "Calculator.exe",
    "spotify": "Spotify.exe",
    "discord": "Discord.exe",
    "slack": "slack.exe",
    "teams": "Teams.exe",
    "zoom": "Zoom.exe",
    "vlc": "vlc.exe",
}

# ========================================
# COMMAND PATTERNS
# ========================================

PRIORITY_COMMANDS = [
    # App control
    ("open_app", r"^void\s+open\s+(.+)$", r"^void\s+open\s+(.+)$"),
    ("close_app", r"^void\s+close\s+(.+)$", r"^void\s+close\s+(.+)$"),
    
    # System commands
    ("diagnose_system", r"^void\s+diagnose\s+system$", r"^void\s+diagnose\s+system$"),
    ("repair_system", r"^void\s+repair\s+(yourself|system)$", r"^void\s+repair\s+(yourself|system)$"),
    ("fix_mic", r"^void\s+(fix|repair)\s+(the\s+)?mic(rophone)?$", r"^void\s+(fix|repair)\s+(the\s+)?mic(rophone)?$"),
    ("fix_microphone", r"^void\s+(fix|repair)\s+(the\s+)?microphone$", r"^void\s+(fix|repair)\s+(the\s+)?microphone$"),
    ("check_system_status", r"^void\s+check\s+system\s+status$", r"^void\s+check\s+system\s+status$"),
    ("system_status", r"^void\s+system\s+status$", r"^void\s+system\s+status$"),
    
    # Restart commands
    ("restart_backend", r"^void\s+restart\s+backend$", r"^void\s+restart\s+backend$"),
    ("restart_ollama", r"^void\s+restart\s+ollama$", r"^void\s+restart\s+ollama$"),
    
    # Upgrade
    ("upgrade_system", r"^void\s+upgrade\s+(yourself|system)$", r"^void\s+upgrade\s+(yourself|system)$"),
    
    # Memory commands
    ("remember", r"^void\s+remember\s+(.+)$", r"^void\s+remember\s+(.+)$"),
    ("recall", r"^void\s+recall\s+(.+)$", r"^void\s+recall\s+(.+)$"),
    ("forget", r"^void\s+forget\s+(.+)$", r"^void\s+forget\s+(.+)$"),
    ("show_memory", r"^void\s+(show\s+)?memory$", r"^void\s+(show\s+)?memory$"),
    ("clear_memory", r"^void\s+clear\s+memory$", r"^void\s+clear\s+memory$"),
    
    # Info commands
    ("time", r"^void\s+(what\s+time|time)$", r"^void\s+(what\s+time|time)$"),
    ("system_info", r"^void\s+system\s+info$", r"^void\s+system\s+info$"),
    
    # Search
    ("search", r"^void\s+search\s+(.+)$", r"^void\s+search\s+(.+)$"),
    ("play", r"^void\s+play\s+(.+)$", r"^void\s+play\s+(.+)$"),
    
    # Scapy network tools
    ("scapy_ping", r"^void\s+ping\s+(.+)$", r"^void\s+ping\s+(.+)$"),
    ("scapy_portscan", r"^void\s+(port\s+)?scan\s+(.+)$", r"^void\s+(port\s+)?scan\s+(.+)$"),
    ("scapy_sniff", r"^void\s+(sniff|sniff packets)\s*(?:count=(\d+))?\s*(.*)?$", r"^void\s+(sniff|sniff packets)\s*(?:count=(\d+))?\s*(.*)?$"),
    ("scapy_traceroute", r"^void\s+(traceroute|trace route)\s+(.+)$", r"^void\s+(traceroute|trace route)\s+(.+)$"),
    ("scapy_dns", r"^void\s+(dns|dns lookup)\s+(.+)$", r"^void\s+(dns|dns lookup)\s+(.+)$"),
    
    # Developer mode
    ("enter_developer_mode", r"^void\s+enter\s+developer\s+mode$", r"^void\s+enter\s+developer\s+mode$"),
    ("exit_developer_mode", r"^void\s+exit\s+developer\s+mode$", r"^void\s+exit\s+developer\s+mode$"),
]


def normalize_app_name(name: str) -> str:
    """Normalize app name for matching."""
    return (name or "").strip().lower()


def clean_app_target(text: str) -> str:
    """Clean app target by removing filler words."""
    t = (text or "").strip().lower()
    junk_words = ["please", "now", "quickly", "fast", "for me", "bro", "boss", "sir", "open", "start", "launch", "close", "exit", "stop", "the", "a", "an"]
    for w in junk_words:
        t = t.replace(w, " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def best_app_match(target: str) -> Optional[str]:
    """Find best matching app name with fuzzy matching."""
    t = normalize_app_name(target)
    if t in APP_MAP:
        return t
    
    # Exact no-space match
    t2 = t.replace(" ", "")
    for k in APP_MAP:
        if k.replace(" ", "") == t2:
            return k
    
    # Substring match
    for k in APP_MAP:
        if t in k:
            return k
    
    # Fuzzy match using difflib (threshold 0.6)
    scores = [(difflib.SequenceMatcher(None, t, k).ratio(), k) for k in APP_MAP.keys()]
    if scores:
        best_score, best_key = max(scores)
        if best_score > 0.6:  # Tolerate typos like 'notepd' -> 'notepad'
            return best_key
    
    return None


def interpret_command(prompt: str) -> Optional[Dict[str, Any]]:
    """
    Interpret a command and return the parsed result.
    
    Args:
        prompt: User input string
        
    Returns:
        Dict with 'command', 'args', and 'raw' keys, or None if not a VOID command
    """
    if not prompt:
        return None
    
    prompt_lower = prompt.lower().strip()
    
    # Check if command starts with "void"
    if not prompt_lower.startswith("void "):
        return None
    
    # Remove "void " prefix
    command = prompt_lower[5:].strip()
    
    logger.info(f"[COMMAND INTERPRETER] Parsing: {command}")
    
    # Match against priority patterns
    for cmd_type, pattern, _ in PRIORITY_COMMANDS:
        match = re.match(pattern, command, re.IGNORECASE)
        if match:
            args = match.groups() if match.groups() else ()
            
            logger.info(f"[COMMAND INTERPRETER] Matched: {cmd_type} with args: {args}")
            
            return {
                "command": cmd_type,
                "args": args,
                "raw": prompt,
                "matched": True
            }
    
    # No match found
    logger.info(f"[COMMAND INTERPRETER] No match for: {command}")
    return None


def execute_command(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a parsed command.
    
    Args:
        parsed: Result from interpret_command()
        
    Returns:
        Dict with 'status', 'message', and optional 'data'
    """
    if not parsed or not parsed.get("matched"):
        return {"status": "error", "message": "Invalid command"}
    
    cmd_type = parsed.get("command", "")
    args = parsed.get("args", ())
    
    logger.info(f"[COMMAND INTERPRETER] Executing: {cmd_type}")
    
    try:
        # ========================================
        # APP CONTROL
        # ========================================
        if cmd_type == "open_app":
            target = clean_app_target(args[0] if args else "")
            name = best_app_match(target)
            
            if name and name in APP_MAP:
                cmd = APP_MAP[name]
                if platform.system() == "Windows":
                    subprocess.Popen(["cmd", "/c", "start", "", cmd], shell=True)
                return {"status": "ok", "message": f"Opened {name}"}
            
            # Try as URL
            url = f"https://{target}" if ("." in target and " " not in target) else f"https://www.google.com/search?q={target.replace(' ', '+')}"
            subprocess.Popen(["cmd", "/c", "start", "", url], shell=True)
            return {"status": "ok", "message": f"Opened {url}"}
        
        elif cmd_type == "close_app":
            target = clean_app_target(args[0] if args else "")
            name = best_app_match(target)
            
            if name and name in KILL_MAP:
                exe = KILL_MAP[name]
            else:
                exe = f"{target}.exe"
            
            try:
                if platform.system() == "Windows":
                    subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True, check=True)
                return {"status": "ok", "message": f"Closed {target}"}
            except subprocess.CalledProcessError:
                return {"status": "error", "message": f"Could not find or close {target}"}
            except Exception as e:
                return {"status": "error", "message": f"Failed to close {target}: {str(e)}"}
        
        # ========================================
        # SYSTEM COMMANDS (placeholders - implement as needed)
        # ========================================
        elif cmd_type in ["diagnose_system", "repair_system", "fix_mic", "fix_microphone", "check_system_status", "system_status"]:
            return {"status": "ok", "message": f"{cmd_type.replace('_', ' ').title()} executed."}
        
        elif cmd_type in ["restart_backend", "restart_ollama"]:
            return {"status": "warning", "message": f"{cmd_type.replace('_', ' ').title()} requires manual restart."}
        
        elif cmd_type == "upgrade_system":
            return {"status": "warning", "message": "Upgrade requires developer mode."}
        
        # Memory (placeholders)
        elif cmd_type in ["remember", "recall", "forget", "show_memory", "clear_memory"]:
            return {"status": "ok", "message": f"{cmd_type.replace('_', ' ').title()} executed."}
        
        # Info
        elif cmd_type == "time":
            import datetime
            now = datetime.datetime.now()
            return {"status": "ok", "message": f"🕒 {now.strftime('%I:%M %p')} • {now.strftime('%A, %d %b %Y')}"}
        
        elif cmd_type == "system_info":
            import platform
            return {"status": "ok", "message": f"🖥️ {platform.system()} {platform.release()}"}
        
        # Search/Play
        elif cmd_type == "search":
            query = args[0] if args else ""
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            subprocess.Popen(["cmd", "/c", "start", "", url], shell=True)
            return {"status": "ok", "message": f"🔎 Searching: {query}"}
        
        elif cmd_type == "play":
            query = args[0] if args else ""
            url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            subprocess.Popen(["cmd", "/c", "start", "", url], shell=True)
            return {"status": "ok", "message": f"🎵 Playing: {query}"}
        
        # Scapy network tools
        elif cmd_type == "scapy_ping":
            try:
                from tools.network_scapy import ping_host
                host = clean_app_target(' '.join(args))
                result = ping_host(host)
                return result
            except Exception as e:
                return {"status": "error", "message": f"Ping failed: {str(e)}"}
        
        elif cmd_type == "scapy_portscan":
            try:
                from tools.network_scapy import port_scan
                target = clean_app_target(' '.join(args))
                result = port_scan(target)
                return result
            except Exception as e:
                return {"status": "error", "message": f"Scan failed: {str(e)}"}
        
        elif cmd_type == "scapy_sniff":
            try:
                from tools.network_scapy import sniff_packets
                count = 10
                if args and args[0]:
                    count = min(int(args[0]), 20)
                result = sniff_packets(count)
                return result
            except Exception as e:
                return {"status": "error", "message": f"Sniff failed: {str(e)}"}
        
        elif cmd_type == "scapy_traceroute":
            try:
                from tools.network_scapy import traceroute_host
                host = clean_app_target(' '.join(args))
                result = traceroute_host(host)
                return result
            except Exception as e:
                return {"status": "error", "message": f"Traceroute failed: {str(e)}"}
        
        elif cmd_type == "scapy_dns":
            try:
                from tools.network_scapy import dns_lookup
                domain = ' '.join(args).strip()
                result = dns_lookup(domain)
                return result
            except Exception as e:
                return {"status": "error", "message": f"DNS failed: {str(e)}"}
        
        # Developer mode (placeholders)
        elif cmd_type in ["enter_developer_mode", "exit_developer_mode"]:
            return {"status": "ok", "message": f"Developer mode {cmd_type.split('_')[-2]}."}
        
        else:
            return {"status": "unknown", "message": f"Unknown command: {cmd_type}"}
    
    except Exception as e:
        logger.error(f"[COMMAND INTERPRETER] Error executing {cmd_type}: {str(e)}")
        return {"status": "error", "message": f"Error: {str(e)}"}


def is_void_command(prompt: str) -> bool:
    """Check if a prompt is a VOID command."""
    if not prompt:
        return False
    return prompt.lower().strip().startswith("void ")


if __name__ == "__main__":
    # Test commands
    test_commands = [
        "VOID open chrome",
        "VOID close notepad",
        "VOID diagnose system", 
        "VOID time",
        "Normal message",
    ]
    
    print("=" * 50)
    print("VOID Command Interpreter Test")
    print("=" * 50)
    
    for cmd in test_commands:
        print(f"\nInput: {cmd}")
        parsed = interpret_command(cmd)
        if parsed:
            print(f"  Command: {parsed['command']}")
            result = execute_command(parsed)
            print(f"  Result: {result['status']} - {result['message']}")
        else:
            print("  -> LLM handling")

