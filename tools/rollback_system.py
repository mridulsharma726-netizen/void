"""
VOID Automated Rollback & Self-Healing System
============================================

Features:
- Scans local backup directories and tracks original filenames and change vectors.
- Restores individual file checkpoints to original locations with safe overwriting.
- Auto-rollback recent changes: Evaluates files changed within a time window and restores them.
- Diagnostics-driven self-healing: Triggers rollback if active health checks/diagnostics fail!
"""

import os
import shutil
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("void.rollback")

# Project directories
ROOT_DIR = Path(__file__).parent.parent
BACKUP_DIR = ROOT_DIR / "backups"

def list_backups() -> List[Dict[str, Any]]:
    """
    Lists all available backups in the backups folder, sorted by timestamp descending.
    """
    backups = []
    if not BACKUP_DIR.exists():
        return []
        
    for file in os.listdir(str(BACKUP_DIR)):
        file_path = BACKUP_DIR / file
        if not file_path.is_file():
            continue
            
        # Parse timestamp from format: YYYYMMDD_HHMMSS_filename.ext
        parts = file.split("_", 2)
        if len(parts) >= 3:
            timestamp_str = f"{parts[0]}_{parts[1]}"
            orig_filename = parts[2]
            try:
                dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            except Exception:
                dt = datetime.fromtimestamp(file_path.stat().st_mtime)
                
            backups.append({
                "backup_path": str(file_path),
                "filename": file,
                "original_filename": orig_filename,
                "timestamp": dt,
                "size_bytes": file_path.stat().st_size
            })
            
    # Sort by timestamp descending (newest first)
    backups.sort(key=lambda x: x["timestamp"], reverse=True)
    return backups

def restore_backup(backup_path: str) -> Dict[str, Any]:
    """
    Restores a single backup file to its original target location inside the project.
    """
    try:
        backup_file = Path(backup_path)
        if not backup_file.exists():
            return {"status": "error", "message": "Backup file does not exist."}
            
        # Extract original filename
        parts = backup_file.name.split("_", 2)
        if len(parts) < 3:
            return {"status": "error", "message": "Malformed backup filename structure."}
            
        orig_filename = parts[2]
        
        # Search for original file in tools/ or core/ or server/ directories
        target_path = None
        for root, dirs, files in os.walk(str(ROOT_DIR)):
            if any(ignore in root.lower() for ignore in ["venv", "node_modules", ".git", "backups", "__pycache__"]):
                continue
            if orig_filename in files:
                target_path = Path(root) / orig_filename
                break
                
        if not target_path:
            # Fallback to direct root or tools directory
            if os.path.exists(ROOT_DIR / "tools" / orig_filename):
                target_path = ROOT_DIR / "tools" / orig_filename
            else:
                target_path = ROOT_DIR / orig_filename
                
        # Copy backup back to original location
        shutil.copy2(str(backup_file), str(target_path))
        logger.info(f"[ROLLBACK] Restored backup '{backup_file.name}' back to '{target_path}'")
        
        return {
            "status": "ok",
            "message": f"Successfully restored {orig_filename} back to its original location.",
            "restored_path": str(target_path)
        }
    except Exception as e:
        logger.error(f"[ROLLBACK ERROR] Failed restoring backup: {e}")
        return {"status": "error", "message": f"Rollback failed: {e}"}

def rollback_latest_for_file(orig_filename: str) -> Dict[str, Any]:
    """
    Finds the latest backup for a specific filename and restores it.
    """
    backups = list_backups()
    target_backup = None
    
    for b in backups:
        if b["original_filename"].lower() == orig_filename.lower():
            target_backup = b
            break
            
    if not target_backup:
        return {"status": "error", "message": f"No backup checkpoints found for file '{orig_filename}'."}
        
    return restore_backup(target_backup["backup_path"])

def rollback_recent_changes(minutes: int = 15) -> Dict[str, Any]:
    """
    Rolls back all files modified within the recent time window.
    """
    backups = list_backups()
    cutoff_time = datetime.now() - timedelta(minutes=minutes)
    
    restored_files = []
    failed_files = []
    
    # Process newest to oldest, keeping track of already restored files to prevent double-restores
    processed_files = set()
    
    for b in backups:
        # Check time bounds
        if b["timestamp"] >= cutoff_time:
            orig = b["original_filename"]
            if orig in processed_files:
                continue
                
            processed_files.add(orig)
            res = restore_backup(b["backup_path"])
            if res["status"] == "ok":
                restored_files.append(orig)
            else:
                failed_files.append(orig)
                
    if not restored_files and not failed_files:
        return {
            "status": "warning",
            "message": "No file backup checkpoints found in the specified recent time window."
        }
        
    status = "ok" if not failed_files else "partial"
    return {
        "status": status,
        "message": f"Rollback complete: {len(restored_files)} files restored, {len(failed_files)} failures.",
        "restored": restored_files,
        "failed": failed_files
    }

async def run_diagnostics_and_rollback_if_failed() -> Dict[str, Any]:
    """
    Core self-healing loop: Runs live diagnostics suite, and if it fails,
    automatically rolls back recent modifications from the last 15 minutes!
    """
    try:
        from server.backend.diagnostics import DiagnosticsEngine
        diag = DiagnosticsEngine()
        report = await diag.run()
        
        if report.get("status") == "OK":
            return {
                "status": "ok",
                "message": "System diagnostics are completely healthy. Self-healing not required.",
                "diagnostics": report
            }
            
        # Diagnostics failed! Trigger self-healing rollback loop
        logger.warning("[SELF-HEALING] Diagnostic issues detected! Triggering automatic rollback of recent edits.")
        rollback_res = rollback_recent_changes(minutes=15)
        
        # Re-run diagnostics to verify recovery
        post_report = await diag.run()
        
        return {
            "status": "self_healed" if post_report.get("status") == "OK" else "healed_partial",
            "message": f"Diagnostics failed, auto-rollback executed: {rollback_res.get('message')}",
            "rollback_results": rollback_res,
            "pre_diagnostics": report,
            "post_diagnostics": post_report
        }
    except Exception as e:
        logger.error(f"[SELF-HEALING ERROR] Diagnostics recovery sequence crashed: {e}")
        return {
            "status": "error",
            "message": f"Self-healing execution failed: {e}"
        }
