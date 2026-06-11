"""
VOID Project Intelligence System
=================================

Autonomous project scanning, understanding, and tracking.
Scans directories, builds project profiles, detects changes,
and extracts TODO/task items from source code.

Functions:
- register_project(path) -> Dict
- scan_project_changes(project_id) -> Dict
- get_project_status(project_name) -> Dict
- get_recent_work(timeframe) -> Dict
"""

import os
import re
import json
import hashlib
import logging
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from server.backend import memory_sqlite

logger = logging.getLogger("void.project_intelligence")

# === CONFIGURATION ===

# File extensions to scan
ALLOWED_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
    ".json", ".yaml", ".yml", ".md", ".txt"
}

# Directories to ignore
IGNORED_DIRS = {
    "node_modules", "venv", ".venv", ".git", "dist", "build",
    "__pycache__", ".cache", ".tox", ".mypy_cache", ".pytest_cache",
    ".next", ".nuxt", "coverage", ".idea", ".vscode", ".qodo",
    ".zencoder", ".zenflow", "env", ".env", "eggs", ".eggs",
    "scratch", "logs"
}

# Max file size to read (100KB)
MAX_FILE_SIZE = 100 * 1024

# Max files to send to LLM in one batch for summarization
LLM_BATCH_SIZE = 15


def _compute_file_hash(filepath: str) -> str:
    """Compute MD5 hash of a file for change detection."""
    try:
        hasher = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""


def _scan_directory(project_path: str, read_contents: bool = True) -> Dict[str, Any]:
    """
    Recursively scan a project directory.
    Returns file list, folder structure, and file contents for analysis.
    """
    project_path = os.path.abspath(project_path)
    files_found = []
    folder_tree = {}
    file_contents = {}

    for root, dirs, files in os.walk(project_path):
        # Prune ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        rel_root = os.path.relpath(root, project_path).replace("\\", "/")
        if rel_root == ".":
            rel_root = ""

        for filename in sorted(files):
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue

            full_path = os.path.join(root, filename)
            rel_path = os.path.join(rel_root, filename).replace("\\", "/") if rel_root else filename
            file_size = 0
            try:
                file_size = os.path.getsize(full_path)
            except OSError:
                continue

            file_hash = _compute_file_hash(full_path)

            files_found.append({
                "path": rel_path,
                "full_path": full_path,
                "ext": ext,
                "size": file_size,
                "hash": file_hash,
            })

            # Read content for analysis (skip large files)
            if read_contents and file_size <= MAX_FILE_SIZE:
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        file_contents[rel_path] = f.read()
                except Exception:
                    pass

        # Build folder tree
        if rel_root:
            parts = rel_root.split("/")
            node = folder_tree
            for part in parts:
                if part not in node:
                    node[part] = {}
                node = node[part]

    return {
        "files": files_found,
        "folder_tree": folder_tree,
        "file_contents": file_contents,
        "total_files": len(files_found),
    }


def _extract_todos(file_contents: Dict[str, str]) -> List[Dict[str, str]]:
    """Extract TODO/FIXME/HACK comments from source files."""
    todos = []
    todo_pattern = re.compile(
        r"(?:#|//|/\*)\s*(?:TODO|FIXME|HACK|XXX|BUG|NOTE)\s*:?\s*(.+)",
        re.IGNORECASE
    )

    for filepath, content in file_contents.items():
        for line_num, line in enumerate(content.splitlines(), 1):
            match = todo_pattern.search(line)
            if match:
                todos.append({
                    "file": filepath,
                    "line": line_num,
                    "text": match.group(1).strip(),
                    "raw": line.strip(),
                })
    return todos


def _build_file_summary_batch(file_contents: Dict[str, str]) -> str:
    """Build a concise batch of file descriptions for LLM context."""
    summaries = []
    for filepath, content in list(file_contents.items())[:LLM_BATCH_SIZE]:
        # Take first 50 lines or less
        lines = content.splitlines()[:50]
        preview = "\n".join(lines)
        summaries.append(f"=== FILE: {filepath} ===\n{preview}\n")
    return "\n".join(summaries)


def _analyze_with_llm(project_name: str, folder_structure: str,
                      file_batch: str, todos: List[Dict],
                      static_tech: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Use the local LLM to analyze the project and extract structured data."""
    try:
        from server.backend.llm_client import OllamaClient
        client = OllamaClient()

        todos_text = ""
        if todos:
            todos_text = "\n\nTODO Comments found:\n"
            for t in todos[:20]:
                todos_text += f"- [{t['file']}:{t['line']}] {t['text']}\n"

        static_tech_text = ""
        if static_tech:
            static_tech_text = f"\nStatically Detected Technologies:\n{json.dumps(static_tech, indent=2)}\n"

        system_prompt = """You are a project analysis expert. Analyze the provided project files and return a JSON object with these keys:
- "purpose": A 1-2 sentence description of the project's purpose.
- "architecture": The tech stack / architecture pattern (e.g., "FastAPI backend + React frontend + SQLite").
- "technologies": A JSON array of technologies used (e.g., ["Python", "FastAPI", "SQLite", "JavaScript"]).
- "features_completed": A JSON array of features that appear fully implemented.
- "features_progress": A JSON array of features that appear to be in progress or partially done.
- "features_planned": A JSON array of features that appear planned but not yet started (from TODOs, comments, etc.).
- "goals": A JSON array of the primary business/technical goals of the project.
- "known_bugs": A JSON array of known bugs or issues found in TODOs/comments/source files.
- "development_history": A JSON array of development history events (e.g., "Initial commit", "Added voice STT").
- "blockers": A JSON array of potential blockers or issues found.
Return ONLY valid JSON."""

        prompt = f"""Project: {project_name}
{static_tech_text}
Folder Structure:
{folder_structure}

Source Files:
{file_batch}
{todos_text}"""

        response = client.generate(prompt=prompt, system_prompt=system_prompt, format="json", timeout=35.0)

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error("LLM returned invalid JSON for project analysis")
            return {}
    except Exception as e:
        logger.error(f"LLM analysis failed: {e}")
        return {}


def _format_folder_tree(tree: Dict, indent: int = 0) -> str:
    """Format folder tree dict into a readable string."""
    lines = []
    prefix = "  " * indent
    for name, subtree in sorted(tree.items()):
        if isinstance(subtree, dict) and subtree:
            lines.append(f"{prefix}📁 {name}/")
            lines.append(_format_folder_tree(subtree, indent + 1))
        else:
            lines.append(f"{prefix}📁 {name}/")
    return "\n".join(lines)


# === PUBLIC API ===

def register_project(path: str = "") -> Dict[str, Any]:
    """
    Register and perform initial deep scan of a project directory.
    Scans files, extracts TODOs, analyzes with LLM, and saves to memory.
    """
    # Path resolution intelligence
    clean_path = path.lower().strip() if path else ""
    if clean_path:
        import re
        # Strip leading and trailing quotes first
        clean_path = clean_path.strip("'\"")
        # Remove leading 'the ', 'this ', 'current ', 'my '
        clean_path = re.sub(r'^(the|this|current|my)\s+', '', clean_path)
        # Remove trailing ' project', ' codebase', ' folder', ' directory' (along with optional trailing dot/s or quotes/spaces)
        clean_path = re.sub(r'\s+(project|codebase|folder|directory)[\s.\'"]*$', '', clean_path)
        # Strip trailing dot, quotes, and whitespace again
        clean_path = clean_path.strip(". '\"")

    default_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if not path or clean_path in [
        "this project", "this codebase", "current project", "current codebase", 
        "void", "current folder", "this folder", "codebase", "project", "."
    ]:
        # Resolve to current workspace directory
        path = default_root
    elif clean_path:
        path = clean_path
    
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        # Fallback for void references if path not found
        if "void" in clean_path:
            path = default_root
            
        if not os.path.isdir(path):
            # Check parent directory (e.g. for sister projects like SkipIt on user's desktop)
            parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            test_path = os.path.join(parent_dir, os.path.basename(path))
            if os.path.isdir(test_path):
                path = test_path
            else:
                return {"status": "error", "message": f"Directory not found: {path}"}

    project_name = os.path.basename(path)
    project_id = f"proj_{hashlib.md5(path.encode()).hexdigest()[:10]}"

    logger.info(f"[PROJECT INTELLIGENCE] Registering project: {project_name} at {path}")

    # 0. Static Technology Detection
    from tools.tech_detector import detect_technologies
    static_tech = detect_technologies(path)

    # 1. Scan directory
    scan_result = _scan_directory(path)
    files = scan_result["files"]
    file_contents = scan_result["file_contents"]
    folder_tree = scan_result["folder_tree"]

    # 2. Extract TODOs from source code
    todos = _extract_todos(file_contents)

    # 3. Build folder structure string
    folder_str = _format_folder_tree(folder_tree)

    # 4. Analyze with LLM (merging static tech detection context)
    file_batch = _build_file_summary_batch(file_contents)
    analysis = _analyze_with_llm(project_name, folder_str, file_batch, todos, static_tech)

    # Merge static tech and LLM analysis technologies
    static_tech_list = []
    if static_tech:
        static_tech_list = static_tech.get("languages", []) + static_tech.get("frameworks", []) + static_tech.get("databases", [])
    llm_tech = analysis.get("technologies", [])
    merged_tech = sorted(list(set(static_tech_list + llm_tech)))

    # Merge static blockers and LLM blockers
    static_blockers = [b["message"] for b in detect_project_blockers(path) if b["severity"] == "High"]
    llm_blockers = analysis.get("blockers", [])
    merged_blockers = sorted(list(set(static_blockers + llm_blockers)))

    # 5. Save project profile to DB
    memory_sqlite.save_project(
        project_id=project_id,
        name=project_name,
        path=path,
        purpose=analysis.get("purpose", ""),
        architecture=analysis.get("architecture", ""),
        technologies=json.dumps(merged_tech),
        features_completed=json.dumps(analysis.get("features_completed", [])),
        features_progress=json.dumps(analysis.get("features_progress", [])),
        features_planned=json.dumps(analysis.get("features_planned", [])),
        blockers=json.dumps(merged_blockers),
        folder_structure=folder_str,
        goals=json.dumps(analysis.get("goals", [])),
        completed_modules=json.dumps(analysis.get("features_completed", [])),
        pending_modules=json.dumps(analysis.get("features_planned", [])),
        known_bugs=json.dumps(analysis.get("known_bugs", [])),
        development_history=json.dumps(analysis.get("development_history", []))
    )

    # 6. Save individual file records for change detection
    for file_info in files:
        file_id = f"{project_id}_{hashlib.md5(file_info['path'].encode()).hexdigest()[:10]}"
        memory_sqlite.save_project_file(
            file_id=file_id,
            project_id=project_id,
            path=file_info["path"],
            file_hash=file_info["hash"],
        )

    # 7. Save TODO items as action items
    for todo in todos:
        memory_sqlite.add_action_item(
            meeting_id="",
            description=f"[TODO] {todo['text']} ({todo['file']}:{todo['line']})",
            owner="",
            deadline="",
        )

    features_done = analysis.get("features_completed", [])
    features_wip = analysis.get("features_progress", [])

    return {
        "status": "ok",
        "message": (
            f"Project '{project_name}' registered successfully.\n"
            f"📁 {scan_result['total_files']} files scanned.\n"
            f"✅ {len(features_done)} completed features found.\n"
            f"🔄 {len(features_wip)} in-progress features found.\n"
            f"📝 {len(todos)} TODO items extracted.\n"
            f"🏗️ Architecture: {analysis.get('architecture', 'Unknown')}"
        ),
        "project_id": project_id,
        "analysis": analysis,
    }


def scan_project_changes(project_id: str = "") -> Dict[str, Any]:
    """
    Re-scan a registered project and detect changes since the last scan.
    Compares file hashes to identify new, modified, and deleted files.
    """
    if not project_id:
        # Try to find the first project
        projects = memory_sqlite.list_tracked_projects()
        if not projects:
            return {"status": "error", "message": "No tracked projects found."}
        project_id = projects[0]["project_id"]

    project = memory_sqlite.get_project(project_id)
    if not project:
        return {"status": "error", "message": f"Project '{project_id}' not found."}

    project_path = project["path"]
    if not os.path.isdir(project_path):
        return {"status": "error", "message": f"Project directory no longer exists: {project_path}"}

    logger.info(f"[PROJECT INTELLIGENCE] Scanning changes for: {project['name']}")

    # Get previous file records
    old_files = memory_sqlite.get_project_files(project_id)
    old_file_map = {f["path"]: f for f in old_files}

    # Perform fresh scan
    scan_result = _scan_directory(project_path, read_contents=False)
    new_file_map = {f["path"]: f for f in scan_result["files"]}

    # Compute deltas
    new_paths = set(new_file_map.keys()) - set(old_file_map.keys())
    deleted_paths = set(old_file_map.keys()) - set(new_file_map.keys())
    common_paths = set(new_file_map.keys()) & set(old_file_map.keys())

    modified_paths = set()
    for p in common_paths:
        if new_file_map[p]["hash"] != old_file_map[p]["file_hash"]:
            modified_paths.add(p)

    # Update file records in DB
    for file_info in scan_result["files"]:
        file_id = f"{project_id}_{hashlib.md5(file_info['path'].encode()).hexdigest()[:10]}"
        memory_sqlite.save_project_file(
            file_id=file_id,
            project_id=project_id,
            path=file_info["path"],
            file_hash=file_info["hash"],
        )

    # Remove deleted file records
    for path in deleted_paths:
        old_record = old_file_map[path]
        memory_sqlite.delete_project_file(old_record["file_id"])

    # Save scan history
    change_summary = (
        f"New: {len(new_paths)}, Modified: {len(modified_paths)}, Deleted: {len(deleted_paths)}"
    )
    memory_sqlite.save_scan_history(
        project_id=project_id,
        new_files=json.dumps(sorted(new_paths)),
        modified_files=json.dumps(sorted(modified_paths)),
        deleted_files=json.dumps(sorted(deleted_paths)),
        summary=change_summary,
    )

    # Update last scan date and recent changes
    memory_sqlite.update_project_field(project_id, "last_scan_date", datetime.datetime.now().isoformat())
    memory_sqlite.update_project_field(project_id, "recent_changes", json.dumps({
        "scan_date": datetime.datetime.now().isoformat(),
        "new": sorted(new_paths),
        "modified": sorted(modified_paths),
        "deleted": sorted(deleted_paths),
    }))

    # Build report
    report = f"**Change Report for '{project['name']}'**\n\n"
    if new_paths:
        report += "**New Files:**\n" + "".join(f"  + {p}\n" for p in sorted(new_paths))
    if modified_paths:
        report += "**Modified Files:**\n" + "".join(f"  ~ {p}\n" for p in sorted(modified_paths))
    if deleted_paths:
        report += "**Deleted Files:**\n" + "".join(f"  - {p}\n" for p in sorted(deleted_paths))
    if not new_paths and not modified_paths and not deleted_paths:
        report += "No changes detected since last scan."

    return {
        "status": "ok",
        "message": report,
        "new": sorted(new_paths),
        "modified": sorted(modified_paths),
        "deleted": sorted(deleted_paths),
    }


def get_project_status(project_name: str = "") -> Dict[str, Any]:
    """
    Retrieve the full status of a tracked project from memory.
    Loads project profile, linked meetings, and pending tasks.
    """
    if not project_name:
        # List all projects
        projects = memory_sqlite.list_tracked_projects()
        if not projects:
            return {"status": "ok", "message": "No tracked projects found. Use 'Track this project' to register one."}
        listing = "**Tracked Projects:**\n"
        for p in projects:
            listing += f"- **{p['name']}** ({p['path']}) — Last scanned: {p['last_scan_date'] or 'never'}\n"
        return {"status": "ok", "message": listing, "projects": projects}

    project = memory_sqlite.get_project_by_name(project_name)
    if not project:
        return {"status": "error", "message": f"No project found with name '{project_name}'."}

    # Parse JSON fields
    try:
        features_done = json.loads(project.get("features_completed", "[]"))
    except Exception:
        features_done = []
    try:
        features_wip = json.loads(project.get("features_progress", "[]"))
    except Exception:
        features_wip = []
    try:
        features_planned = json.loads(project.get("features_planned", "[]"))
    except Exception:
        features_planned = []
    try:
        blockers = json.loads(project.get("blockers", "[]"))
    except Exception:
        blockers = []
    try:
        technologies = json.loads(project.get("technologies", "[]"))
    except Exception:
        technologies = []

    # Get pending action items
    all_items = memory_sqlite.get_pending_action_items()

    # Calculate completion percentage
    total_features = len(features_done) + len(features_wip) + len(features_planned)
    completion_pct = 0
    if total_features > 0:
        completion_pct = round((len(features_done) / total_features) * 100)
    else:
        # Fallback to code analysis estimation: base 90% minus 3% per pending TODO
        files_count = len(memory_sqlite.get_project_files(project["project_id"]))
        if files_count > 0:
            todos_count = len(all_items)
            completion_pct = max(20, 95 - (todos_count * 3))
            completion_pct = min(95, completion_pct)

    # Search for linked meetings
    meetings = memory_sqlite.search_meetings(project_name, limit=3)

    status_report = f"## Project: {project['name']}\n\n"
    status_report += f"**Path:** {project['path']}\n"
    status_report += f"**Purpose:** {project.get('purpose', 'Unknown')}\n"
    status_report += f"**Architecture:** {project.get('architecture', 'Unknown')}\n"
    status_report += f"**Technologies:** {', '.join(technologies) if technologies else 'Unknown'}\n"
    status_report += f"**Last Scanned:** {project.get('last_scan_date', 'Never')}\n"
    status_report += f"**Estimated Completion:** {completion_pct}%\n\n"
    
    # Progress Bar
    bars = round(completion_pct / 5)
    progress_bar = "█" * bars + "░" * (20 - bars)
    status_report += f"`[{progress_bar}]`\n\n"

    if features_done:
        status_report += "**✅ Completed Features:**\n"
        for f in features_done:
            status_report += f"  - {f}\n"

    if features_wip:
        status_report += "**🔄 In Progress:**\n"
        for f in features_wip:
            status_report += f"  - {f}\n"

    if features_planned:
        status_report += "**📋 Planned:**\n"
        for f in features_planned:
            status_report += f"  - {f}\n"

    if blockers:
        status_report += "**🚫 Blockers:**\n"
        for b in blockers:
            status_report += f"  - {b}\n"

    if meetings:
        status_report += "\n**📅 Related Meetings:**\n"
        for m in meetings:
            status_report += f"  - {m['title']} ({m['date_time']})\n"

    if all_items:
        status_report += "\n**📝 Pending Action Items:**\n"
        for item in all_items[:10]:
            status_report += f"  - {item['description']}\n"

    return {"status": "ok", "message": status_report, "project": project}


def get_recent_work(timeframe: str = "today") -> Dict[str, Any]:
    """
    Analyze what was recently worked on by checking file modification times
    across all tracked projects.
    """
    projects = memory_sqlite.list_tracked_projects()
    if not projects:
        return {"status": "ok", "message": "No tracked projects to analyze."}

    # Determine cutoff time
    now = datetime.datetime.now()
    if timeframe in ("today", ""):
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif timeframe == "yesterday":
        cutoff = (now - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif "week" in timeframe:
        cutoff = now - datetime.timedelta(days=7)
    else:
        cutoff = now - datetime.timedelta(days=1)

    results = []

    for proj in projects:
        project_path = proj["path"]
        if not os.path.isdir(project_path):
            continue

        modified_files = []
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            for filename in files:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    continue
                full_path = os.path.join(root, filename)
                try:
                    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(full_path))
                    if mtime >= cutoff:
                        rel_path = os.path.relpath(full_path, project_path).replace("\\", "/")
                        modified_files.append({
                            "file": rel_path,
                            "modified_at": mtime.isoformat(),
                        })
                except OSError:
                    continue

        if modified_files:
            # Sort by modification time, most recent first
            modified_files.sort(key=lambda x: x["modified_at"], reverse=True)
            results.append({
                "project": proj["name"],
                "files_changed": len(modified_files),
                "files": modified_files[:20],  # Limit display
            })

    if not results:
        return {"status": "ok", "message": f"No changes found for timeframe '{timeframe}'."}

    report = f"**Recent Work ({timeframe}):**\n\n"
    for r in results:
        report += f"**{r['project']}** — {r['files_changed']} files changed\n"
        for f in r["files"][:10]:
            report += f"  ~ {f['file']} (modified {f['modified_at']})\n"
        if r["files_changed"] > 10:
            report += f"  ... and {r['files_changed'] - 10} more\n"
        report += "\n"

    return {"status": "ok", "message": report, "results": results}


def _get_git_branch(project_path: str) -> str:
    """Gets the current active git branch for a project directory."""
    try:
        import subprocess
        res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], 
                             cwd=project_path, capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return "main"


def continue_where_left_off(project_id: str = "") -> Dict[str, Any]:
    """
    Find recently worked on files and recommend next actions/TODOs.
    """
    if not project_id:
        # Get first tracked project
        projects = memory_sqlite.list_tracked_projects()
        if not projects:
            return {"status": "error", "message": "No tracked projects found."}
        project_id = projects[0]["project_id"]

    project = memory_sqlite.get_project(project_id)
    if not project:
        return {"status": "error", "message": f"Project '{project_id}' not found."}

    # Get recent work
    recent = get_recent_work("today")
    files_changed = []
    if recent and "results" in recent:
        for r in recent["results"]:
            if r["project"] == project["name"]:
                files_changed = [f["file"] for f in r["files"]]
                break

    # If no work today, try "week"
    if not files_changed:
        recent = get_recent_work("week")
        if recent and "results" in recent:
            for r in recent["results"]:
                if r["project"] == project["name"]:
                    files_changed = [f["file"] for f in r["files"]]
                    break

    # Find TODOs in the project
    project_path = project["path"]
    scan_result = _scan_directory(project_path, read_contents=True)
    file_contents = scan_result.get("file_contents", {})
    all_todos = _extract_todos(file_contents)

    # Filter TODOs related to files changed or show top 5
    relevant_todos = [t for t in all_todos if t["file"] in files_changed][:5]
    if not relevant_todos:
        relevant_todos = all_todos[:5]

    git_branch = _get_git_branch(project_path)

    # Build response message
    msg = f"### Continue Where You Left Off ({project['name']})\n\n"
    msg += f"**Current Branch:** `{git_branch}`\n\n"
    
    if files_changed:
        msg += "**Recent Files Worked On:**\n"
        for f in files_changed[:5]:
            msg += f"- `{f}`\n"
    else:
        msg += "*No files recently modified in this project, Sir.*\n"
        
    msg += "\n**Suggested Next Actions:**\n"
    if relevant_todos:
        for idx, t in enumerate(relevant_todos, 1):
            msg += f"{idx}. Fix TODO in `{t['file']}:{t['line']}`: *\"{t['text']}\"*\n"
    else:
        msg += "1. No pending TODO comments found in recently modified files. You can start a new feature or inspect project blockers, Sir.\n"

    return {
        "status": "ok",
        "message": msg,
        "git_branch": git_branch,
        "files_changed": files_changed,
        "relevant_todos": relevant_todos
    }


def generate_architecture_map(project_id: str = "") -> str:
    """
    Generate plain English architecture explanation and a Mermaid graph.
    """
    if not project_id:
        projects = memory_sqlite.list_tracked_projects()
        if not projects:
            return "No tracked projects found, Sir."
        project_id = projects[0]["project_id"]

    project = memory_sqlite.get_project(project_id)
    if not project:
        return f"Project '{project_id}' not found."

    project_path = project["path"]
    
    # 1. Parse tech stack and purpose
    techs = []
    try:
        techs = json.loads(project.get("technologies", "[]"))
    except:
        pass
    
    purpose = project.get("purpose", "Unknown purpose")
    architecture = project.get("architecture", "Unknown architecture")

    # 2. Extract imports to build Mermaid dependency map
    scan_result = _scan_directory(project_path, read_contents=True)
    file_contents = scan_result.get("file_contents", {})

    dependencies = {} # key: folder/module, value: set of imported folders/modules
    
    # Identify key high-level directories (e.g. backend, server, tools, core, workflows)
    root_dirs = set()
    for filepath in file_contents.keys():
        parts = filepath.split('/')
        if len(parts) > 1:
            root_dirs.add(parts[0])

    for filepath, content in file_contents.items():
        parts = filepath.split('/')
        if len(parts) <= 1:
            current_module = "root"
        else:
            current_module = parts[0]
            
        if current_module not in dependencies:
            dependencies[current_module] = set()
            
        # Parse imports
        for line in content.splitlines():
            line = line.strip()
            # Match python imports: from x import y, import x
            py_from_match = re.match(r'^from\s+([a-zA-Z0-9_\.]+)\s+import', line)
            py_import_match = re.match(r'^import\s+([a-zA-Z0-9_\.]+)', line)
            
            # Match javascript/typescript imports: import x from 'y', require('y')
            js_import_match = re.match(r'^import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]', line)
            js_require_match = re.match(r'.*require\([\'"]([^\'"]+)[\'"]\)', line)
            
            imported_module = None
            if py_from_match:
                imported_module = py_from_match.group(1).split('.')[0]
            elif py_import_match:
                imported_module = py_import_match.group(1).split('.')[0]
            elif js_import_match:
                imp_path = js_import_match.group(1)
                # handle relative path
                if imp_path.startswith('.'):
                    imported_module = "local_ref"
                else:
                    imported_module = imp_path.split('/')[0]
            elif js_require_match:
                imp_path = js_require_match.group(1)
                if imp_path.startswith('.'):
                    imported_module = "local_ref"
                else:
                    imported_module = imp_path.split('/')[0]
                    
            if imported_module and imported_module in root_dirs and imported_module != current_module:
                dependencies[current_module].add(imported_module)

    # Build Mermaid graph
    mermaid = "```mermaid\ngraph TD\n"
    edges_found = False
    for mod, imports in sorted(dependencies.items()):
        # Exclude common builtins or root folder
        if mod == "root" or mod in IGNORED_DIRS:
            continue
        for imp in sorted(list(imports)):
            if imp != "root" and imp not in IGNORED_DIRS:
                mermaid += f"  {mod} --> {imp}\n"
                edges_found = True
                
    if not edges_found:
        # Fallback edges if no internal imports mapped
        mermaid += "  Client[Desktop Application] --> Server[FastAPI Backend]\n"
        mermaid += "  Server --> Memory[SQLite Database]\n"
        mermaid += "  Server --> LLM[Ollama Client]\n"
        
    mermaid += "```"

    # Build report
    report = f"## Architecture Report: {project['name']}\n\n"
    report += f"**Purpose:** {purpose}\n"
    report += f"**Architecture Design:** {architecture}\n"
    report += f"**Technologies Used:** {', '.join(techs) if techs else 'None detected'}\n\n"
    report += "### Component Dependency Map\n"
    report += mermaid + "\n\n"
    report += "### Plain English Explanation\n"
    report += f"The project '{project['name']}' follows a modular structure where components represent functional divisions:\n"
    for mod, imports in sorted(dependencies.items()):
        if mod == "root" or mod in IGNORED_DIRS:
            continue
        dep_str = f"imports modules from: {', '.join(imports)}" if imports else "has no internal dependencies"
        report += f"- **{mod}**: This module handles logical operations for `{mod}` components and {dep_str}.\n"
        
    return report


def detect_project_blockers(project_path: str) -> List[Dict[str, Any]]:
    """
    Scans the project to proactively identify blockers (broken imports, missing configs, TODOs, outdated APIs, empty stubs).
    """
    blockers = []
    
    # 1. Check for missing environment config
    if os.path.exists(os.path.join(project_path, ".env.example")) and not os.path.exists(os.path.join(project_path, ".env")):
        blockers.append({
            "category": "Configuration",
            "severity": "High",
            "message": "Missing local environment configuration: '.env.example' exists but '.env' is missing.",
            "file": ".env",
            "line": 1
        })
        
    # 2. Scan directory
    scan_result = _scan_directory(project_path, read_contents=True)
    file_contents = scan_result.get("file_contents", {})
    
    # Find all top-level folders
    top_folders = {d for d in os.listdir(project_path) if os.path.isdir(os.path.join(project_path, d)) and d not in IGNORED_DIRS}
    
    # 3. Check for broken imports
    broken_imports_count = 0
    for filepath, content in file_contents.items():
        if not filepath.endswith(".py"):
            continue
        for line_num, line in enumerate(content.splitlines(), 1):
            line = line.strip()
            # Match: from tools.abc import xyz
            m_from = re.match(r'^from\s+([a-zA-Z0-9_]+)(?:\.([a-zA-Z0-9_]+))?\s+import', line)
            # Match: import tools.abc
            m_import = re.match(r'^import\s+([a-zA-Z0-9_]+)(?:\.([a-zA-Z0-9_]+))?', line)
            
            top_mod = None
            sub_mod = None
            if m_from:
                top_mod = m_from.group(1)
                sub_mod = m_from.group(2)
            elif m_import:
                top_mod = m_import.group(1)
                sub_mod = m_import.group(2)
                
            if top_mod and top_mod in top_folders:
                # Local module check
                if sub_mod:
                    sub_file = os.path.join(project_path, top_mod, f"{sub_mod}.py")
                    sub_dir = os.path.join(project_path, top_mod, sub_mod)
                    if not os.path.exists(sub_file) and not os.path.isdir(sub_dir):
                        blockers.append({
                            "category": "Broken Import",
                            "severity": "High",
                            "message": f"Broken local reference: Import of '{top_mod}.{sub_mod}' refers to a missing file.",
                            "file": filepath,
                            "line": line_num
                        })
                        broken_imports_count += 1
                else:
                    mod_dir = os.path.join(project_path, top_mod)
                    if not os.path.isdir(mod_dir):
                        blockers.append({
                            "category": "Broken Import",
                            "severity": "High",
                            "message": f"Broken local reference: Import of '{top_mod}' refers to a missing directory.",
                            "file": filepath,
                            "line": line_num
                        })
                        broken_imports_count += 1
                        
            if broken_imports_count >= 5:  # Cap broken imports to avoid spam
                break

    # 4. Check for outdated Gemini references (e.g. gemini-1.0)
    for filepath, content in file_contents.items():
        if "gemini-1.0" in content.lower():
            for line_num, line in enumerate(content.splitlines(), 1):
                if "gemini-1.0" in line.lower():
                    blockers.append({
                        "category": "Outdated API Reference",
                        "severity": "High",
                        "message": "Outdated Gemini model reference: found 'gemini-1.0' which is deprecated.",
                        "file": filepath,
                        "line": line_num
                    })

    # 5. Check for empty function/class stubs (pass or NotImplementedError)
    import ast
    for filepath, content in file_contents.items():
        if not filepath.endswith(".py"):
            continue
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    body = node.body
                    is_empty = False
                    if len(body) == 1:
                        stmt = body[0]
                        if isinstance(stmt, ast.Pass):
                            is_empty = True
                        elif isinstance(stmt, ast.Raise) and isinstance(stmt.exc, ast.Name) and stmt.exc.id == "NotImplementedError":
                            is_empty = True
                    elif len(body) == 2 and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                        stmt = body[1]
                        if isinstance(stmt, ast.Pass):
                            is_empty = True
                        elif isinstance(stmt, ast.Raise) and isinstance(stmt.exc, ast.Name) and stmt.exc.id == "NotImplementedError":
                            is_empty = True
                            
                    if is_empty:
                        blockers.append({
                            "category": "Missing Implementation",
                            "severity": "Medium",
                            "message": f"Empty implementation: function '{node.name}' contains no active statements.",
                            "file": filepath,
                            "line": node.lineno
                        })
        except Exception:
            pass

    # 6. Check for missing package dependencies
    STD_LIBS = {
        "os", "sys", "re", "json", "hashlib", "logging", "datetime", "sqlite3", "time", "math",
        "subprocess", "ctypes", "socket", "asyncio", "threading", "pathlib", "typing", "collections",
        "functools", "itertools", "urllib", "uuid", "shutil", "platform", "select", "struct", "array",
        "binascii", "base64", "csv", "xml", "html", "pickle", "copy", "tempfile", "traceback", "weakref",
        "io", "gc", "sysconfig", "inspect", "ast", "importlib", "contextlib", "abc", "argparse",
        "enum", "glob", "fnmatch", "random", "secrets", "string", "textwrap", "getpass", "errno", "signal",
        "xmlrpc", "unittest", "timeit", "pdb", "pprint", "warnings", "ctypes", "distutils"
    }
    LIB_MAP = {
        "sklearn": "scikit-learn",
        "yaml": "pyyaml",
        "PIL": "pillow",
        "bs4": "beautifulsoup4",
        "pg": "psycopg2",
        "psycopg2_binary": "psycopg2"
    }
    
    declared = set()
    req_path = os.path.join(project_path, "requirements.txt")
    if os.path.exists(req_path):
        try:
            with open(req_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        lib_name = re.split(r"==|>=|<=|>|<|~=", line)[0].strip().lower().replace("-", "_")
                        declared.add(lib_name)
        except Exception:
            pass
            
    pkg_path = os.path.join(project_path, "package.json")
    if os.path.exists(pkg_path):
        try:
            with open(pkg_path, "r", encoding="utf-8") as f:
                pkg_data = json.load(f)
                for dep_type in ["dependencies", "devDependencies"]:
                    if dep_type in pkg_data:
                        for dep in pkg_data[dep_type].keys():
                            declared.add(dep.lower().replace("-", "_").replace("@", ""))
        except Exception:
            pass

    for filepath, content in file_contents.items():
        if not filepath.endswith(".py"):
            continue
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                imported_modules = []
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_modules.append(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.level == 0 and node.module:
                        imported_modules.append(node.module.split('.')[0])
                        
                for mod in imported_modules:
                    mod_lower = mod.lower()
                    declared_name = LIB_MAP.get(mod, mod_lower)
                    
                    if (mod not in STD_LIBS and 
                        mod_lower not in STD_LIBS and
                        mod not in top_folders and 
                        declared_name not in declared and 
                        mod_lower not in declared):
                        
                        blockers.append({
                            "category": "Missing Dependency",
                            "severity": "Medium",
                            "message": f"Missing package dependency: Module '{mod}' is imported but not declared in requirements.txt or package.json.",
                            "file": filepath,
                            "line": node.lineno
                        })
        except Exception:
            pass

    # 7. Gather TODO items
    todos = _extract_todos(file_contents)
    for todo in todos[:10]:
        blockers.append({
            "category": "Technical Debt",
            "severity": "Low",
            "message": f"Pending TODO: {todo['text']}",
            "file": todo["file"],
            "line": todo["line"]
        })
        
    return blockers


def get_workspace_state(project_path: str = "") -> Dict[str, Any]:
    """
    Retrieves the current working environment parameters (Workspace Awareness).
    """
    if not project_path:
        from server.backend.memory_sqlite import get_active_project
        active_proj = get_active_project()
        if active_proj:
            project_path = active_proj["path"]
        else:
            # Fallback to local VOID directory
            project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            
    project_path = os.path.abspath(project_path)
    project_name = os.path.basename(project_path)
    
    # 1. VS Code workspace window title detection
    vscode_workspace = "Unknown Workspace"
    try:
        from server.backend.screen_monitor import get_monitor_instance
        monitor = get_monitor_instance()
        win_title = monitor.get_foreground_window_title()
        if win_title and any(k in win_title.lower() for k in ["visual studio code", "vscode", "code"]):
            vscode_workspace = win_title
    except Exception:
        pass
        
    # 2. Current Git branch
    git_branch = _get_git_branch(project_path)
    
    # 3. Recently modified files (last 24 hours)
    modified_files = []
    try:
        recent = get_recent_work("today")
        if recent and "results" in recent:
            for r in recent["results"]:
                if r["project"] == project_name:
                    modified_files = [f["file"] for f in r["files"]]
                    break
    except Exception:
        pass
                
    # 4. Recent build alerts/failures from CVCS Monitor
    recent_alerts = []
    try:
        from server.backend.screen_monitor import get_monitor_instance
        monitor = get_monitor_instance()
        unread = monitor.get_unread_notifications()
        for n in unread:
            if n.get("category") == "build":
                recent_alerts.append(n.get("message"))
    except Exception:
        pass
            
    return {
        "active_project_folder": project_path,
        "vscode_workspace": vscode_workspace,
        "current_git_branch": git_branch,
        "recently_modified_files": modified_files,
        "recent_build_alerts": recent_alerts
    }


def generate_project_report(report_type: str, project_id: str = "") -> str:
    """
    Generates structured markdown reports (daily, weekly, architecture, progress, technical_debt).
    """
    if not project_id:
        projects = memory_sqlite.list_tracked_projects()
        if not projects:
            return "No tracked projects found, Sir."
        project_id = projects[0]["project_id"]

    project = memory_sqlite.get_project(project_id)
    if not project:
        return f"Project '{project_id}' not found."

    project_path = project["path"]
    report_type = report_type.lower().strip()

    # Retrieve all elements
    scan_result = _scan_directory(project_path, read_contents=True)
    file_contents = scan_result.get("file_contents", {})
    todos = _extract_todos(file_contents)
    blockers = detect_project_blockers(project_path)

    # Tech stack
    techs = []
    try:
        techs = json.loads(project.get("technologies", "[]"))
    except:
        pass

    # Features
    try:
        features_done = json.loads(project.get("features_completed", "[]"))
    except:
        features_done = []
    try:
        features_wip = json.loads(project.get("features_progress", "[]"))
    except:
        features_wip = []
    try:
        features_planned = json.loads(project.get("features_planned", "[]"))
    except:
        features_planned = []

    # Completion calculation
    total_features = len(features_done) + len(features_wip) + len(features_planned)
    completion_pct = 0
    if total_features > 0:
        completion_pct = round((len(features_done) / total_features) * 100)
    else:
        # Fallback to code analysis estimation
        all_items = memory_sqlite.get_pending_action_items()
        files_count = len(memory_sqlite.get_project_files(project_id))
        if files_count > 0:
            todos_count = len(all_items)
            completion_pct = max(20, 95 - (todos_count * 3))
            completion_pct = min(95, completion_pct)

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    if report_type == "daily":
        report = f"# Daily Status Report: {project['name']}\n"
        report += f"Generated: {now_str}\n\n"
        report += f"### Summary\n- **Project Name:** {project['name']}\n- **Git Branch:** `{_get_git_branch(project_path)}`\n- **Completion:** {completion_pct}%\n\n"
        
        # Recent modifications
        recent = get_recent_work("today")
        report += "### Today's Modifications\n"
        files_modified = False
        if recent and "results" in recent:
            for r in recent["results"]:
                if r["project"] == project["name"]:
                    for f in r["files"][:10]:
                        report += f"- `~ {f['file']}` (modified {f['modified_at']})\n"
                    files_modified = True
                    break
        if not files_modified:
            report += "- No files modified today, Sir.\n"

        # Blockers
        report += "\n### Current Blockers\n"
        active_blockers = [b for b in blockers if b["severity"] == "High"]
        if active_blockers:
            for b in active_blockers:
                report += f"- **[{b['category']}]** {b['message']} (`{b['file']}`)\n"
        else:
            report += "- No High-priority blockers detected, Sir!\n"

    elif report_type == "weekly":
        report = f"# Weekly Progress Report: {project['name']}\n"
        report += f"Generated: {now_str}\n\n"
        report += f"### Project Metrics\n- **Completion Percent:** {completion_pct}%\n- **Active Branch:** `{_get_git_branch(project_path)}`\n\n"
        
        recent = get_recent_work("week")
        report += "### Weekly Modifications\n"
        files_modified = False
        if recent and "results" in recent:
            for r in recent["results"]:
                if r["project"] == project["name"]:
                    report += f"- Total files changed this week: {r['files_changed']}\n"
                    for f in r["files"][:10]:
                        report += f"  - `{f['file']}`\n"
                    files_modified = True
                    break
        if not files_modified:
            report += "- No modifications detected this week, Sir.\n"

        report += "\n### Task Tracking\n"
        report += f"- **Completed Features:** {len(features_done)}\n"
        report += f"- **In-Progress Features:** {len(features_wip)}\n"
        report += f"- **Planned Features:** {len(features_planned)}\n"

    elif report_type == "architecture":
        report = generate_architecture_map(project_id)

    elif report_type == "progress":
        report = f"# Progress Report: {project['name']}\n"
        report += f"Generated: {now_str}\n\n"
        report += f"## Project Completion: **{completion_pct}%**\n\n"
        
        # ProgressBar
        bars = round(completion_pct / 5)
        progress_bar = "█" * bars + "░" * (20 - bars)
        report += f"`[{progress_bar}]`\n\n"

        report += "### Completed Features\n"
        if features_done:
            for f in features_done:
                report += f"- [x] {f}\n"
        else:
            report += "- None recorded.\n"

        report += "\n### In-Progress Features\n"
        if features_wip:
            for f in features_wip:
                report += f"- [/] {f}\n"
        else:
            report += "- None recorded.\n"

        report += "\n### Planned Features\n"
        if features_planned:
            for f in features_planned:
                report += f"- [ ] {f}\n"
        else:
            report += "- None recorded.\n"

    elif report_type == "technical_debt":
        report = f"# Technical Debt Audit: {project['name']}\n"
        report += f"Generated: {now_str}\n\n"
        
        # Blockers density
        high_debt = [b for b in blockers if b["severity"] == "High"]
        med_debt = [b for b in blockers if b["severity"] == "Medium"]
        
        report += f"### Debt Summary\n- **High Severity Issues:** {len(high_debt)}\n- **Medium Severity Issues:** {len(med_debt)}\n- **Unresolved TODOs:** {len(todos)}\n\n"
        
        if high_debt:
            report += "### High Severity Config & Code Errors\n"
            for b in high_debt:
                report += f"- **[{b['category']}]** {b['message']} (`{b['file']}`)\n"
                
        if med_debt:
            report += "\n### Medium Severity Stubs & Dependencies\n"
            for b in med_debt:
                report += f"- **[{b['category']}]** {b['message']} (`{b['file']}:{b['line']}`)\n"
                
        report += "\n### Active TODO & HACK Markers\n"
        if todos:
            for t in todos[:20]:
                report += f"- `{t['file']}:{t['line']}`: *\"{t['text']}\"*\n"
        else:
            report += "- No pending TODO markers found, Sir.\n"
            
    else:
        report = f"Unknown report type: {report_type}. Available types: daily, weekly, architecture, progress, technical_debt."

    return report
