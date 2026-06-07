"""
VOID Simple Intent Detector
Deterministic intent detection without LLM dependency.
"""

import re


def detect_intent(message: str) -> dict:
    """
    Detect user intent from message.
    
    Args:
        message: User message
        
    Returns:
        dict: {"intent": "intent_name", "params": {...}}
    """
    msg = message.lower().strip()
    
    # Common websites definitions
    common_sites = {
        "youtube": "https://www.youtube.com",
        "google": "https://www.google.com",
        "github": "https://github.com",
        "reddit": "https://www.reddit.com",
        "twitter": "https://twitter.com",
        "x": "https://x.com",
        "x.com": "https://x.com",
        "facebook": "https://www.facebook.com",
        "instagram": "https://www.instagram.com",
        "bing": "https://www.bing.com",
    }
    
    # REPAIR & DIAGNOSTICS INTENT (PRIORITY HIGH)
    repair_keywords = ["repair", "fix", "diagnostics", "diagnose", "scan system", "system health", "check system"]
    if any(kw in msg for kw in repair_keywords):
        return {"intent": "repair_diagnostics", "params": {"action": "diagnostics"}}
    
    # Check for "open" command
    if msg.startswith("open "):
        target = message[5:].strip()  # Get text after "open "
        
        # Check common sites first
        for site, url in common_sites.items():
            if site in target:
                return {"intent": "open_url", "params": {"url": url}}
        
        # Check if it's a URL
        if "://" in target or ".com" in target or ".org" in target or ".net" in target:
            url = target if "://" in target else "https://" + target
            return {"intent": "open_url", "params": {"url": url}}
        
        # Check if it's a folder
        folder_keywords = ["downloads", "documents", "desktop", "pictures", "music", "videos", "folder"]
        if any(kw in target.lower() for kw in folder_keywords):
            return {"intent": "open_folder", "params": {"folder": target}}
        
        # Otherwise, it's an app
        return {"intent": "open_app", "params": {"app": target}}
    
    # Check for URL patterns
    if "http://" in msg or "https://" in msg:
        # Extract URL
        url_match = re.search(r'(https?://[^\s]+)', message)
        if url_match:
            return {"intent": "open_url", "params": {"url": url_match.group(1)}}
    
    # Check for common websites anywhere in message
    for site, url in common_sites.items():
        if site in msg:
            return {"intent": "open_url", "params": {"url": url}}
    
    # Check for YouTube search
    if "youtube" in msg and ("search" in msg or "play" in msg):
        query = msg.replace("youtube", "").replace("search", "").replace("play", "").strip()
        if query:
            return {"intent": "play_youtube", "params": {"query": query}}
    
    # Check for search
    if msg.startswith("search ") or msg.startswith("google "):
        query = msg.replace("search ", "").replace("google ", "").strip()
        return {"intent": "search_web", "params": {"query": query}}
    
    # Check for system info
    if "system info" in msg or "system information" in msg:
        return {"intent": "system_info", "params": {}}
    
    # Check for time
    time_keywords = ["time", "what time", "tell time", "clock", "current time", "what time is it", "whats the time", "time now", "what's the time", "clock now"]
    if any(kw in msg for kw in time_keywords):
        return {"intent": "time", "params": {}}
    
    # Check for folder commands
    folder_cmds = ["open folder", "show folder", "go to folder"]
    for cmd in folder_cmds:
        if msg.startswith(cmd):
            folder = msg[len(cmd):].strip()
            return {"intent": "open_folder", "params": {"folder": folder}}
    
    # Network / Scapy intents
    scapy_keywords = {
        "scapy_ping": ["ping", "check connection", "test connectivity"],
        "scapy_scan": ["scan ports", "port scan", "check ports"],
        "scapy_sniff": ["sniff network", "capture packets", "network traffic"],
        "scapy_traceroute": ["traceroute", "trace route", "network path"],
        "scapy_dns": ["dns lookup", "resolve domain", "what ip"]
    }
    
    for intent, keywords in scapy_keywords.items():
        if any(kw in msg for kw in keywords):
            # Extract host/param
            host_match = re.search(r'(?:to|for|on)?\s*([a-z0-9.-]+(?:\.[a-z]{2,})?)', msg)
            host = host_match.group(1) if host_match else ""
            ports_match = re.search(r'ports?\s*([0-9, -]+)', msg)
            ports = ports_match.group(1) if ports_match else ""
            count_match = re.search(r'(\d+)', msg)
            count = int(count_match.group(1)) if count_match else ""
            return {"intent": intent, "params": {"host": host, "ports": ports, "count": count}}
    
    # No intent detected
    return {"intent": None, "params": {}}

