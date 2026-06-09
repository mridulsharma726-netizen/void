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
                      file_batch: str, todos: List[Dict]) -> Dict[str, Any]:
    """Use the local LLM to analyze the project and extract structured data."""
    try:
        from server.backend.llm_client import OllamaClient
        client = OllamaClient()

        todos_text = ""
        if todos:
            todos_text = "\n\nTODO Comments found:\n"
            for t in todos[:20]:
                todos_text += f"- [{t['file']}:{t['line']}] {t['text']}\n"

        system_prompt = """You are a project analysis expert. Analyze the provided project files and return a JSON object with these keys:
- "purpose": A 1-2 sentence description of the project's purpose.
- "architecture": The tech stack / architecture pattern (e.g., "FastAPI backend + React frontend + SQLite").
- "technologies": A JSON array of technologies used (e.g., ["Python", "FastAPI", "SQLite", "JavaScript"]).
- "features_completed": A JSON array of features that appear fully implemented.
- "features_progress": A JSON array of features that appear to be in progress or partially done.
- "features_planned": A JSON array of features that appear planned but not yet started (from TODOs, comments, etc.).
- "blockers": A JSON array of potential blockers or issues found.
Return ONLY valid JSON."""

        prompt = f"""Project: {project_name}

Folder Structure:
{folder_structure}

Source Files:
{file_batch}
{todos_text}"""

        response = client.generate(prompt=prompt, system_prompt=system_prompt, format="json")

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
    if not path:
        return {"status": "error", "message": "Project path is required."}

    path = os.path.abspath(path)
    if not os.path.isdir(path):
        return {"status": "error", "message": f"Directory not found: {path}"}

    project_name = os.path.basename(path)
    project_id = f"proj_{hashlib.md5(path.encode()).hexdigest()[:10]}"

    logger.info(f"[PROJECT INTELLIGENCE] Registering project: {project_name} at {path}")

    # 1. Scan directory
    scan_result = _scan_directory(path)
    files = scan_result["files"]
    file_contents = scan_result["file_contents"]
    folder_tree = scan_result["folder_tree"]

    # 2. Extract TODOs from source code
    todos = _extract_todos(file_contents)

    # 3. Build folder structure string
    folder_str = _format_folder_tree(folder_tree)

    # 4. Analyze with LLM
    file_batch = _build_file_summary_batch(file_contents)
    analysis = _analyze_with_llm(project_name, folder_str, file_batch, todos)

    # 5. Save project profile to DB
    memory_sqlite.save_project(
        project_id=project_id,
        name=project_name,
        path=path,
        purpose=analysis.get("purpose", ""),
        architecture=analysis.get("architecture", ""),
        technologies=json.dumps(analysis.get("technologies", [])),
        features_completed=json.dumps(analysis.get("features_completed", [])),
        features_progress=json.dumps(analysis.get("features_progress", [])),
        features_planned=json.dumps(analysis.get("features_planned", [])),
        blockers=json.dumps(analysis.get("blockers", [])),
        folder_structure=folder_str,
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

    # Search for linked meetings
    meetings = memory_sqlite.search_meetings(project_name, limit=3)

    # Get pending action items
    all_items = memory_sqlite.get_pending_action_items()

    status_report = f"## Project: {project['name']}\n\n"
    status_report += f"**Path:** {project['path']}\n"
    status_report += f"**Purpose:** {project.get('purpose', 'Unknown')}\n"
    status_report += f"**Architecture:** {project.get('architecture', 'Unknown')}\n"
    status_report += f"**Technologies:** {', '.join(technologies) if technologies else 'Unknown'}\n"
    status_report += f"**Last Scanned:** {project.get('last_scan_date', 'Never')}\n\n"

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
