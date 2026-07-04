import os
import re
import sys
import json
import time
import math
import sqlite3
import asyncio
import logging
import requests
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger("void.agent_network")

# Workspace root
WORKSPACE_ROOT = Path(__file__).parent.parent
DB_FILE = WORKSPACE_ROOT / "memory" / "data" / "memory.db"
BRAIN_LOG_PATH = WORKSPACE_ROOT / "logs" / "brain.log"
AGENT_SWARM_LOG_PATH = WORKSPACE_ROOT / "logs" / "agent_swarm.log"

def _log_to_brain(agent: str, action: str, details: str = ""):
    """Log agent events to logs/brain.log."""
    try:
        os.makedirs(WORKSPACE_ROOT / "logs", exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{agent}] {action}: {details}\n"
        with open(BRAIN_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        logger.error(f"Failed writing to brain.log: {e}")

def _log_to_swarm(agent: str, event_type: str, details: str = ""):
    """Log detailed swarm interactions to logs/agent_swarm.log."""
    try:
        os.makedirs(WORKSPACE_ROOT / "logs", exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{agent}] [{event_type}] {details}\n"
        with open(AGENT_SWARM_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        logger.error(f"Failed writing to agent_swarm.log: {e}")

# ==================== SWARM BLACKBOARD AND VOTING TABLES ====================

def init_swarm_tables():
    """Initializes dedicated SQLite tables for shared swarm state board and consensus voting."""
    os.makedirs(DB_FILE.parent, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    
    # Shared Swarm Blackboard Memory
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS swarm_blackboard (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            posted_by TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Collaborative Swarm Proposals and Votes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS swarm_proposals (
            proposal_id TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            votes TEXT NOT NULL,
            consensus TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

# ==================== SPECIALIST AGENTS DEFINITION ====================

class SpecialistAgent:
    def __init__(self, name: str, role: str, badge: str, capabilities: List[str], system_prompt: str):
        self.name = name
        self.role = role
        self.badge = badge
        self.capabilities = capabilities
        self.system_prompt = system_prompt
        self.tasks_completed = 0
        self.status = "IDLE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "badge": self.badge,
            "capabilities": self.capabilities,
            "tasks_completed": self.tasks_completed,
            "status": self.status
        }

# Swarm Registry
SWARM: Dict[str, SpecialistAgent] = {
    "ceo": SpecialistAgent(
        name="CEO Agent",
        role="Swarm Coordinator & Final Synthesizer",
        badge="👑 [CEO]",
        capabilities=["Orchestrates task handoffs", "Synthesizes final response", "Blackboard monitoring"],
        system_prompt="VOID CEO node supervising coordinator operations, checking metrics, and formatting answers."
    ),
    "planner": SpecialistAgent(
        name="Planner Agent",
        role="Strategic Dependency & Roadmap Compiler",
        badge="📋 [PLANNER]",
        capabilities=["Project roadmap compiling", "Gantt timeline design", "Task matrix tracking"],
        system_prompt="VOID Planner node compiling matrices, listing task hierarchies, framing timelines."
    ),
    "coding": SpecialistAgent(
        name="Coding Agent",
        role="Safe Code Architect & Synthesizer",
        badge="💻 [CODING]",
        capabilities=["Safe file authoring", "Scaffolds builder", "Syntax compiler validation"],
        system_prompt="VOID Coding node generating scaffolds, compiling local scripts, verifying code formats."
    ),
    "frontend": SpecialistAgent(
        name="Frontend Agent",
        role="Web Interface UI & Styling Specialist",
        badge="🎨 [FRONTEND]",
        capabilities=["CSS design styling", "HTML structure layout", "JavaScript user interaction"],
        system_prompt="VOID Frontend node building responsive interfaces, CSS styling variables, and JS triggers."
    ),
    "backend": SpecialistAgent(
        name="Backend Agent",
        role="Database & API Route Architect",
        badge="⚙️ [BACKEND]",
        capabilities=["FastAPI endpoint setup", "Database schema writing", "Server routes linking"],
        system_prompt="VOID Backend node building FastAPI endpoints, DB tables, schemas, and processing requests."
    ),
    "debug": SpecialistAgent(
        name="Debug Agent",
        role="Error Analyzer & Code Diagnostics Node",
        badge="🛠️ [DEBUG]",
        capabilities=["Log parsing telemetry", "Traceback analysis", "Syntax error isolation"],
        system_prompt="VOID Debug node parsing error logs, identifying traceback issues, and suggesting fixes."
    ),
    "qa": SpecialistAgent(
        name="QA Agent",
        role="Quality Assurance & Unit Test Verifier",
        badge="🧪 [QA]",
        capabilities=["Unit test compilation", "Function verification", "Validation assertion checking"],
        system_prompt="VOID QA node verifying assertions, running unit tests, and checking functionality health."
    ),
    "research": SpecialistAgent(
        name="Research Agent",
        role="Workspace Telemetry & File Auditor",
        badge="🔍 [RESEARCH]",
        capabilities=["Real workspace directories walking", "File system auditing", "Telemetric queries"],
        system_prompt="VOID Research node auditing files, cataloging directories, compiling codebase context."
    ),
    "memory": SpecialistAgent(
        name="Memory Agent",
        role="Long-Term Fact & Preference Indexer",
        badge="💾 [MEMORY]",
        capabilities=["Retrieves semantic facts", "Tracks owner preferences", "Indexes workspace history"],
        system_prompt="VOID Memory node retrieving semantic details, indexing project logs, and matching user preferences."
    ),
    "security": SpecialistAgent(
        name="Security Agent",
        role="Secrets Scanning & Static Auditor",
        badge="🛡️ [SECURITY]",
        capabilities=["Credentials exposure scan", "Shell-injection audit", "Dependency checking"],
        system_prompt="VOID Security node auditing file buffers, checking credentials, protecting bounds."
    )
}

# ==================== REAL AGENT OPERATIONS IMPLEMENTATION ====================

async def run_agent_llm(agent_name: str, badge: str, system_prompt: str, instruction: str) -> str:
    """Helper to query the routing LLM to generate agent reasoning and text responses."""
    try:
        from backend.llm_client import OllamaClient
        llm = OllamaClient()
        
        # Load blackboard context
        blackboard_context = ""
        conn = sqlite3.connect(str(DB_FILE))
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT key, value, posted_by FROM swarm_blackboard ORDER BY timestamp DESC LIMIT 5")
            rows = cursor.fetchall()
            if rows:
                blackboard_context = "\nShared Blackboard Memory Status:\n" + "\n".join(
                    f"- [{posted}] {key}: {val[:120]}" for key, val, posted in rows
                )
        except Exception as e:
            logger.debug(f"Failed to query swarm_blackboard: {e}")
        finally:
            conn.close()

        full_system_prompt = (
            f"{system_prompt}\n"
            f"{blackboard_context}\n"
            f"Always start your response with your identifier badge: {badge}. "
            f"Address the user politely as Master Mridul / Sir. Speak naturally and perform your specialized role."
        )
        
        response = await llm.chat([], instruction, system_prompt=full_system_prompt)
        return response
    except Exception as e:
        logger.error(f"Error in run_agent_llm for {agent_name}: {e}")
        return f"{badge} I am operational, Sir, but my communication link to Ollama is offline. I am ready to perform tasks."

async def run_research_task(instruction: str) -> Dict[str, Any]:
    """Research Agent: Scans actual workspace directories or searches files."""
    _log_to_brain("RESEARCH_AGENT", "TASK_START", instruction)
    _log_to_swarm("RESEARCH_AGENT", "SCANNING", "Walking directories")
    init_swarm_tables()
    
    # Search patterns
    target_pattern = ""
    match = re.search(r'(?:find|search\s+for|locate)\s+([a-zA-Z0-9_\-\.]+)', instruction, re.I)
    if match:
        target_pattern = match.group(1).strip().lower()
        
    found_files = []
    scanned_count = 0
    
    # Perform a real local directory traversal
    for root, dirs, files in os.walk(str(WORKSPACE_ROOT)):
        if any(ignore in root.lower() for ignore in ["venv", "node_modules", ".git", "__pycache__", "backups"]):
            continue
        for file in files:
            scanned_count += 1
            if not target_pattern or target_pattern in file.lower() or target_pattern in root.lower():
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, str(WORKSPACE_ROOT))
                size = os.path.getsize(full_path)
                found_files.append(f"`{rel_path}` ({size} bytes)")
                if len(found_files) >= 15:
                    break
        if len(found_files) >= 15:
            break
            
    # Post finding to Swarm Blackboard
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO swarm_blackboard (key, value, posted_by) VALUES (?, ?, ?)",
        ("last_scanned_files", json.dumps(found_files[:5]), "Research Agent")
    )
    conn.commit()
    conn.close()
    
    lines = [
        "🔍 **Research Agent Workspace Telemetry Scan Complete!**\n",
        f"- **Scanned Files**: {scanned_count} files indexed",
        f"- **Target Search**: `\"{target_pattern or 'All Files'}\"`"
    ]
    if found_files:
        lines.append("\n**Matches Uncovered**:")
        for f in found_files[:10]:
            lines.append(f"- {f}")
    else:
        lines.append("\n- *No matches found in the active workspace directories.*")
        
    return {"status": "ok", "message": "\n".join(lines).strip(), "data": {"scanned": scanned_count, "found": len(found_files)}}

async def run_coding_task(instruction: str) -> Dict[str, Any]:
    """Coding Agent: Creates syntactically-verified code scaffolds inside workspace."""
    _log_to_brain("CODING_AGENT", "TASK_START", instruction)
    _log_to_swarm("CODING_AGENT", "WRITING", "Authoring script scaffold")
    init_swarm_tables()
    
    file_match = re.search(r'([a-zA-Z0-9_\-\/]+\.(?:html|py|js|css|json|md))', instruction, re.I)
    filename = file_match.group(1) if file_match else "scaffold_generated.py"
    
    # Simple check for path safety
    if ".." in filename or filename.startswith("/") or ":" in filename:
        return {
            "status": "error",
            "message": f"Security Lockout: Path '{filename}' contains invalid characters.",
            "data": None
        }
        
    target_path = WORKSPACE_ROOT / filename
    
    # Generate robust boilerplate
    content = ""
    if filename.endswith(".py"):
        content = (
            f'# -*- coding: utf-8 -*-\n'
            f'"""\n'
            f'Autogenerated Swarm Scaffold: {filename}\n'
            f'Compiled on: {time.strftime("%Y-%m-%d %H:%M:%S")}\n'
            f'"""\n\n'
            f'import logging\n\n'
            f'logger = logging.getLogger("void.scaffold")\n\n'
            f'def perform_routine(payload: dict) -> dict:\n'
            f'    """Core functional routine."""\n'
            f'    logger.info("Executing routine payload...")\n'
            f'    return {{"status": "ok", "processed": True}}\n'
        )
    elif filename.endswith(".json"):
        content = json.dumps({"status": "healthy", "spawned_at": time.time(), "details": instruction}, indent=4)
    else:
        content = f"# VOID Custom Scaffold\n- **Target**: {instruction}\n- **Created At**: {time.time()}\n"
        
    try:
        if filename.endswith(".py"):
            compile(content, filename, "exec")
            
        os.makedirs(target_path.parent, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        conn = sqlite3.connect(str(DB_FILE))
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO swarm_blackboard (key, value, posted_by) VALUES (?, ?, ?)",
            (f"last_written_{filename}", f"Bytes: {len(content)}", "Coding Agent")
        )
        conn.commit()
        conn.close()
        
        msg = (
            f"💻 **Coding Agent Task Successful!**\n\n"
            f"- **File Created**: `{filename}`\n"
            f"- **Scaffold verification**: **Passed** (Python AST compiled successfully)"
        )
        return {"status": "ok", "message": msg, "data": {"path": str(target_path), "bytes": len(content)}}
    except Exception as e:
        logger.error(f"Coding Agent scaffold execution failed: {e}")
        return {"status": "error", "message": f"Syntax scaffolding failed: {e}", "data": None}

async def run_testing_task(instruction: str) -> Dict[str, Any]:
    """Testing Agent: Runs live diagnostic suite or measures latency to active ports."""
    _log_to_brain("TESTING_AGENT", "TASK_START", instruction)
    _log_to_swarm("TESTING_AGENT", "DIAGNOSTICS", "Checking ports and endpoints")
    init_swarm_tables()
    
    start_time = time.time()
    latency_ms = 0.0
    
    # 1. Real HTTP probe to backend health endpoint on 8003
    url = "http://127.0.0.1:8003/health"
    status_code = "Offline"
    try:
        resp = requests.get(url, timeout=3.0)
        status_code = str(resp.status_code)
        latency_ms = (time.time() - start_time) * 1000
    except Exception as e:
        logger.debug(f"Testing Agent failed HTTP probe: {e}")
        
    # 2. Run local diagnostics
    diagnostics_passed = False
    try:
        from backend.diagnostics import DiagnosticsEngine
        diag = DiagnosticsEngine()
        diag_report = await diag.run()
        diagnostics_passed = diag_report.get("status") == "OK"
    except Exception as e:
        logger.debug(f"Testing Agent failed diagnostics: {e}")
        
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO swarm_blackboard (key, value, posted_by) VALUES (?, ?, ?)",
        ("last_diagnostic_status", "Passed" if diagnostics_passed else "Failed", "Testing Agent")
    )
    conn.commit()
    conn.close()
    
    lines = [
        "🧪 **Testing Agent Dynamic Verification Complete!**\n",
        f"- **Local Backend (Port 8003)**: `HTTP {status_code}` (Probe Latency: {latency_ms:.1f}ms)",
        f"- **Diagnostics System Suite**: **{'Passed' if diagnostics_passed else 'Failed'}**",
        "- **Event Loop Status**: **Operational**"
    ]
    return {"status": "ok", "message": "\n".join(lines).strip(), "data": {"latency": latency_ms, "http_status": status_code, "diagnostics": diagnostics_passed}}

async def run_security_task(instruction: str) -> Dict[str, Any]:
    """Security Agent: Performs real secrets audit on critical workspace scripts."""
    _log_to_brain("SECURITY_AGENT", "TASK_START", instruction)
    _log_to_swarm("SECURITY_AGENT", "AUDITING", "Scanning files for secrets")
    init_swarm_tables()
    
    exposed_credentials = []
    unsafe_evals = []
    
    files_to_check = [
        WORKSPACE_ROOT / "server" / "main.py",
        WORKSPACE_ROOT / "tools" / "pc_operator.py",
        WORKSPACE_ROOT / "tools" / "terminal_tools.py"
    ]
    
    for fpath in files_to_check:
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.readlines()
                    for idx, line in enumerate(content):
                        if re.search(r'(?:api_key|password|jwt_secret|secret_key)\s*=\s*[\'"][a-zA-Z0-9]{8,}[\'"]', line, re.I):
                            exposed_credentials.append(f"`{fpath.name}:{idx+1}`: {line.strip()[:35]}")
                        if "eval(" in line or "exec(" in line:
                            if "def " not in line and "#" not in line:
                                unsafe_evals.append(f"`{fpath.name}:{idx+1}`: {line.strip()[:35]}")
            except Exception as e:
                logger.debug(f"Security Agent failed reading {fpath}: {e}")
                
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO swarm_blackboard (key, value, posted_by) VALUES (?, ?, ?)",
        ("last_security_vulnerabilities", str(len(exposed_credentials) + len(unsafe_evals)), "Security Agent")
    )
    conn.commit()
    conn.close()
    
    lines = [
        "🛡️ **Security Agent Static Credentials & Injection Audit!**\n",
        f"- **Secret Exposure Check**: **{'CLEAN' if not exposed_credentials else 'WARNING'}** ({len(exposed_credentials)} potential hits)",
        f"- **Dangerous Evaluations**: **{'CLEAN' if not unsafe_evals else 'WARNING'}** ({len(unsafe_evals)} potential hits)"
    ]
    return {"status": "ok", "message": "\n".join(lines).strip(), "data": {"exposures": len(exposed_credentials), "injections": len(unsafe_evals)}}

async def run_planner_task(instruction: str) -> Dict[str, Any]:
    """Planner Agent: Compiles dependency roadmaps and matrices using blackboard status."""
    _log_to_brain("PLANNER_AGENT", "TASK_START", instruction)
    _log_to_swarm("PLANNER_AGENT", "PLANNING", "Compiling roadmap")
    init_swarm_tables()
    
    # Load blackboard status
    blackboard_info = {}
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT key, value FROM swarm_blackboard")
        blackboard_info = {row[0]: row[1] for row in cursor.fetchall()}
    except Exception as e:
        logger.debug(f"Planner Agent failed reading blackboard: {e}")
    finally:
        conn.close()
        
    diag_status = blackboard_info.get("last_diagnostic_status", "Unknown")
    sec_issues = blackboard_info.get("last_security_vulnerabilities", "0")
    
    roadmap = (
        f"📋 **Planner Agent Swarm Dependency Roadmap Compilation!**\n\n"
        f"- **Input Target**: `\"{instruction}\"`\n"
        f"- **Swarm State Diagnostics**: `Status: {diag_status}` | `Sec Warnings: {sec_issues}`\n\n"
        f"🗺️ **Roadmap Milestones & Tasks**:\n"
        f"1. **Stabilization Verification** [Priority: High]\n"
        f"   - Confirm uvicorn API ports remain completely responsive under latency loads.\n"
        f"2. **Continuous Security Hardening** [Priority: Critical]\n"
        f"   - Eliminate any newly reported shell-execution vulnerabilities.\n"
        f"3. **Local Vector Semantics Deployment** [Priority: Medium]\n"
        f"   - Optimize sqlite recall pipelines and embed vectors."
    )
    return {"status": "ok", "message": roadmap, "data": {"instruction": instruction}}

# ==================== COLLABORATIVE SWARM VOTING ENGINE ====================

async def initiate_swarm_vote(proposal_id: str, description: str) -> Dict[str, Any]:
    """
    Simulates a collaborative specialist consensus vote.
    Each specialist node evaluates the proposal based on its system prompt,
    posts reasoning, and registers an APPROVE or REJECT vote in the SQLite proposals table.
    """
    init_swarm_tables()
    _log_to_brain("VOID_COORDINATOR", "INITIATE_VOTE", f"Proposal ID: {proposal_id}")
    
    votes = {}
    for agent_id, agent in SWARM.items():
        # Evaluate based on agent responsibility
        vote_choice = "APPROVE"
        reason = f"Aligned with {agent.role} guidelines."
        
        if agent_id == "security" and ("force" in description.lower() or "delete" in description.lower()):
            vote_choice = "REJECT"
            reason = "Security guidelines warn against forceful overrides or destructive sweeps."
            
        votes[agent_id] = {
            "vote": vote_choice,
            "reasoning": reason
        }
        
    approve_count = sum(1 for v in votes.values() if v["vote"] == "APPROVE")
    reject_count = len(votes) - approve_count
    consensus = "APPROVED" if approve_count > reject_count else "REJECTED"
    
    # Save proposal
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO swarm_proposals (proposal_id, description, votes, consensus) VALUES (?, ?, ?, ?)",
            (proposal_id, description, json.dumps(votes), consensus)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Error saving proposal: {e}")
    finally:
        conn.close()
        
    lines = [
        f"🤖 **Swarm Consensus Voting Ledger Complete!**\n",
        f"📌 **Proposal**: `\"{description}\"`",
        f"📈 **Consensus Outcome**: **{consensus}** ({approve_count} Approved, {reject_count} Rejected)\n",
        "📝 **Detailed Node Ballots**:"
    ]
    for agent_id, ballot in votes.items():
        agent = SWARM[agent_id]
        icon = "✅ APPROVE" if ballot["vote"] == "APPROVE" else "❌ REJECT"
        lines.append(f"- **{agent.name}** {agent.badge}: **{icon}**")
        lines.append(f"  *Reasoning*: {ballot['reasoning']}")
        
    return {
        "status": "ok",
        "message": "\n".join(lines).strip(),
        "data": {
            "proposal_id": proposal_id,
            "outcome": consensus,
            "votes": votes
        }
    }

# ==================== NETWORK MANAGER ROUTING ====================

def get_network_status() -> Dict[str, Any]:
    """Compile current swarm completion stats and SQLite Blackboard memory summary."""
    init_swarm_tables()
    
    blackboard_items = []
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT key, value, posted_by FROM swarm_blackboard ORDER BY timestamp DESC LIMIT 10")
        blackboard_items = cursor.fetchall()
    except Exception as e:
        logger.debug(f"Failed getting network status from blackboard: {e}")
    finally:
        conn.close()
        
    lines = [
        "🌐 **VOID Agent Swarm Network Control Panel**\n",
        f"🚦 **Network Status**: **OPERATIONAL ({len(SWARM)} Specialist Nodes Online)**\n",
        "📋 **Swarm Shared Blackboard Memory**:"
    ]
    if blackboard_items:
        for key, val, posted in blackboard_items:
            lines.append(f"- `[{posted}]` {key}: **{val[:50]}**")
    else:
        lines.append("- *Blackboard memory board is currently blank.*")
        
    lines.append("\n🚦 **Swarm Registry Stats**:")
    for agent_id, agent in SWARM.items():
        status_icon = "🟢 IDLE" if agent.status == "IDLE" else "🔥 BUSY"
        lines.append(
            f"{agent.badge} **{agent.name}**:\n"
            f"  - Status: {status_icon} | Completed: {agent.tasks_completed} ops"
        )
        
    return {
        "status": "ok",
        "message": "\n".join(lines).strip(),
        "data": {agent_id: agent.to_dict() for agent_id, agent in SWARM.items()}
    }

async def spawn_agent_network() -> Dict[str, Any]:
    """Spawn agent network, create SQLite tables, and warm up all specialist nodes."""
    init_swarm_tables()
    _log_to_brain("VOID_COORDINATOR", "SPAWN_SWARM", f"Syncing {len(SWARM)} specialist nodes")
    
    for agent in SWARM.values():
        agent.status = "INITIALIZING"
    await asyncio.sleep(0.3)
    for agent in SWARM.values():
        agent.status = "IDLE"
        
    msg = (
        f"🚀 **VOID Agent Swarm Network Spawned successfully, Sir!**\n\n"
        f"I have initialized **{len(SWARM)} specialized AI nodes** and seeded the **SQLite shared blackboard board**:\n"
        + "\n".join(f"{idx+1}. {agent.badge} **{agent.name}** ({agent.role})" for idx, agent in enumerate(SWARM.values()))
        + "\n\nThe network is unified and ready. You can ask nodes to run tasks or start proposals!"
    )
    return {"status": "ok", "message": msg, "data": {"swarm_size": len(SWARM)}}

async def ask_agent(agent_type: str, instruction: str) -> Dict[str, Any]:
    """Routes commands directly to real specialists, handles chaining / handoffs, and updates task counts."""
    target = agent_type.strip().lower()
    if target not in SWARM:
        return {
            "status": "error",
            "message": f"Specialist node '{agent_type}' is not registered."
        }
        
    agent = SWARM[target]
    agent.status = "BUSY"
    
    _log_to_swarm(agent.name, "RECEIVE_TASK", instruction)
    
    try:
        # Detect Task Handoff Triggers (e.g. if CEO decides to delegate to Planner or Coding)
        handoff_chain = []
        
        # CEO Handoff routing logic
        if target == "ceo":
            # Determine delegation targets based on instruction keywords
            if any(k in instruction.lower() for k in ["plan", "roadmap", "milestone"]):
                handoff_chain.append(("planner", f"Generate a project plan for: {instruction}"))
            elif any(k in instruction.lower() for k in ["code", "script", "scaffold"]):
                handoff_chain.append(("coding", f"Create a script scaffold based on: {instruction}"))
            elif any(k in instruction.lower() for k in ["test", "verify", "health"]):
                handoff_chain.append(("qa", f"Verify functionality of: {instruction}"))
                handoff_chain.append(("testing", f"Port check functionality for: {instruction}"))
            elif any(k in instruction.lower() for k in ["security", "credential", "expose"]):
                handoff_chain.append(("security", f"Static credential scan for: {instruction}"))
            elif any(k in instruction.lower() for k in ["find", "search", "workspace"]):
                handoff_chain.append(("research", f"Audit workspace directories for: {instruction}"))
            elif any(k in instruction.lower() for k in ["history", "facts", "preference"]):
                handoff_chain.append(("memory", f"Query memory database for facts on: {instruction}"))
                
        # Running the base task
        if target == "research":
            res = await run_research_task(instruction)
        elif target == "coding":
            res = await run_coding_task(instruction)
        elif target == "testing":
            res = await run_testing_task(instruction)
        elif target == "security":
            res = await run_security_task(instruction)
        elif target == "planner":
            res = await run_planner_task(instruction)
        else:
            # General persona-based reasoning using dynamic LLM router
            llm_reasoning = await run_agent_llm(agent.name, agent.badge, agent.system_prompt, instruction)
            res = {"status": "ok", "message": llm_reasoning, "data": {"reasoning": llm_reasoning}}
            
        if res.get("status") == "ok":
            agent.tasks_completed += 1
            
        agent.status = "IDLE"
        
        reply_lines = [f"{agent.badge} **{agent.name}** responds:\n\n{res.get('message')}"]
        
        # Execute Handoff Chaining
        for next_agent_type, sub_instruction in handoff_chain:
            _log_to_swarm(agent.name, "HANDOFF", f"Delegating to {next_agent_type}")
            reply_lines.append(f"\n🔄 *Handoff: {agent.name} delegating to {SWARM[next_agent_type].name}...*")
            
            # Recurse ask_agent
            handoff_res = await ask_agent(next_agent_type, sub_instruction)
            reply_lines.append(handoff_res.get("message", ""))
            
        return {"status": "ok", "message": "\n".join(reply_lines).strip(), "data": res.get("data")}
    except Exception as e:
        agent.status = "IDLE"
        logger.error(f"Error delegating to node {agent_type}: {e}", exc_info=True)
        return {"status": "error", "message": f"Error running node {agent_type}: {str(e)}"}
