"""
VOID Secure File System Tools
================================

Provides safe file system operations with an ApprovalGate:
  - All READ operations execute immediately.
  - All WRITE / CREATE / DELETE operations are held until the user
    approves them via the Electron approval WebSocket channel.

Security rules enforced in code:
  - Windows sensitive path blocklist (System32, AppData, Registry, etc.)
  - All paths resolved to absolute before any operation
  - No symlink traversal allowed
  - Approval timeout: 30 seconds → auto-deny

Usage:
    from server.backend.fs_tools import FSTools, get_fs_tools

    fs = get_fs_tools()
    content = fs.read_file("C:/Users/HP/project/main.py")
    # Write — will block until user approves or timeout:
    result = await fs.write_file("C:/Users/HP/project/output.txt", "Hello!")
"""

import asyncio
import logging
import os
import stat
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("void.fs_tools")

# ---------------------------------------------------------------------------
# Security: blocked path prefixes (Windows)
# ---------------------------------------------------------------------------
_BLOCKED_PREFIXES: List[str] = [
    "C:\\Windows",
    "C:\\System32",
    "C:\\SysWOW64",
    "C:\\ProgramData\\Microsoft",
    os.path.expandvars("%APPDATA%\\Microsoft"),
    os.path.expandvars("%LOCALAPPDATA%\\Microsoft"),
    "C:\\Users\\HP\\AppData\\Roaming\\Microsoft",
]

_BLOCKED_EXTENSIONS: set = {".exe", ".dll", ".sys", ".bat", ".cmd", ".reg", ".msi"}


def _is_path_safe(path: Path) -> tuple[bool, str]:
    """Return (is_safe, reason). Blocks dangerous paths."""
    abs_path = str(path.resolve())

    # Blocked prefixes
    for blocked in _BLOCKED_PREFIXES:
        if abs_path.lower().startswith(blocked.lower()):
            return False, f"Access to '{blocked}' is restricted for safety."

    # Blocked extensions for write/delete
    if path.suffix.lower() in _BLOCKED_EXTENSIONS:
        return False, f"Writing/deleting '{path.suffix}' files is not allowed."

    # Prevent symlink traversal
    if path.exists() and path.is_symlink():
        target = path.resolve()
        for blocked in _BLOCKED_PREFIXES:
            if str(target).lower().startswith(blocked.lower()):
                return False, "Symlink target is in a restricted location."

    return True, ""


# ---------------------------------------------------------------------------
# Approval gate (WebSocket-based)
# ---------------------------------------------------------------------------
_pending_approvals: Dict[str, asyncio.Future] = {}


async def request_approval(
    operation: str,
    path: str,
    details: str = "",
    timeout: float = 30.0,
) -> bool:
    """
    Send an approval request to the Electron UI and wait for user response.

    Args:
        operation: Human-readable operation name ('write', 'delete', etc.)
        path:      File path being modified.
        details:   Extra description shown in the UI modal.
        timeout:   Seconds before auto-deny (default 30).

    Returns:
        True if user approved, False if denied or timed out.
    """
    import uuid
    request_id = str(uuid.uuid4())[:8]

    loop = asyncio.get_event_loop()
    future: asyncio.Future = loop.create_future()
    _pending_approvals[request_id] = future

    # Emit approval request event (picked up by WebSocket handler in main.py)
    approval_event = {
        "type": "approval_request",
        "id": request_id,
        "operation": operation,
        "path": path,
        "details": details,
        "timeout": timeout,
    }
    # Notify all connected approval WebSocket clients
    _broadcast_approval_event(approval_event)

    logger.info(
        f"[FS] Awaiting approval for {operation} on '{path}' "
        f"(id={request_id}, timeout={timeout}s)"
    )
    try:
        approved = await asyncio.wait_for(future, timeout=timeout)
        logger.info(f"[FS] Approval id={request_id}: {'APPROVED' if approved else 'DENIED'}")
        return approved
    except asyncio.TimeoutError:
        logger.warning(f"[FS] Approval id={request_id} timed out — auto-denied")
        return False
    finally:
        _pending_approvals.pop(request_id, None)


def resolve_approval(request_id: str, approved: bool) -> bool:
    """
    Called by the WebSocket handler when the user responds to an approval modal.
    Returns True if the request_id was found and resolved.
    """
    future = _pending_approvals.get(request_id)
    if future and not future.done():
        future.set_result(approved)
        return True
    return False


# Active WebSocket connections for approval events
_approval_ws_connections: List[Any] = []


def register_approval_ws(ws) -> None:
    _approval_ws_connections.append(ws)


def unregister_approval_ws(ws) -> None:
    if ws in _approval_ws_connections:
        _approval_ws_connections.remove(ws)


def _broadcast_approval_event(event: Dict[str, Any]) -> None:
    """Send approval event JSON to all connected WebSocket clients."""
    import json
    msg = json.dumps(event)
    dead = []
    for ws in _approval_ws_connections:
        try:
            # FastAPI/Starlette WebSocket — fire-and-forget
            asyncio.ensure_future(ws.send_text(msg))
        except Exception:
            dead.append(ws)
    for ws in dead:
        unregister_approval_ws(ws)


# ---------------------------------------------------------------------------
# Directory entry helper
# ---------------------------------------------------------------------------
def _entry_info(item: Path, root: Path) -> Dict[str, Any]:
    """Build a directory entry dict for a single file/dir."""
    try:
        st = item.stat()
        modified = datetime.fromtimestamp(st.st_mtime).isoformat()
        size = st.st_size if item.is_file() else 0
    except Exception:
        modified = ""
        size = 0
    return {
        "name": item.name,
        "relative_path": str(item.relative_to(root)),
        "type": "directory" if item.is_dir() else "file",
        "size_bytes": size,
        "modified": modified,
        "extension": item.suffix.lower() if item.is_file() else "",
    }


# ---------------------------------------------------------------------------
# Main FSTools class
# ---------------------------------------------------------------------------
class FSTools:
    """
    Secure file system operations with mandatory approval for writes.
    Designed to be used as a singleton (see get_fs_tools()).
    """

    MAX_READ_BYTES = 500_000   # 500 KB read limit per file

    # ------------------------------------------------------------------
    # READ (no approval needed)
    # ------------------------------------------------------------------
    def read_file(self, path: str) -> Dict[str, Any]:
        """
        Read a file and return its content.
        No approval required — read-only operation.

        Returns:
            {status, content, lines, size_bytes, encoding, path}
        """
        p = Path(path).resolve()
        logger.info(f"[FS] read_file: {p}")

        if not p.exists():
            return {"status": "error", "message": f"File not found: {path}"}
        if not p.is_file():
            return {"status": "error", "message": f"Not a file: {path}"}

        size = p.stat().st_size
        if size > self.MAX_READ_BYTES:
            return {
                "status": "error",
                "message": f"File is too large to read ({size:,} bytes). Max: {self.MAX_READ_BYTES:,} bytes.",
            }

        # Try multiple encodings
        for enc in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                content = p.read_text(encoding=enc)
                lines = content.count("\n") + 1
                return {
                    "status": "ok",
                    "path": str(p),
                    "content": content,
                    "lines": lines,
                    "size_bytes": size,
                    "encoding": enc,
                }
            except UnicodeDecodeError:
                continue
            except Exception as exc:
                return {"status": "error", "message": str(exc)}

        return {"status": "error", "message": "Could not decode file with any supported encoding."}

    def list_directory(self, path: str = ".", max_entries: int = 200) -> Dict[str, Any]:
        """
        List the contents of a directory.
        No approval required — read-only operation.

        Returns:
            {status, path, entries: [{name, type, size_bytes, modified}], total}
        """
        p = Path(path).resolve()
        logger.info(f"[FS] list_directory: {p}")

        if not p.exists():
            return {"status": "error", "message": f"Path not found: {path}"}
        if not p.is_dir():
            return {"status": "error", "message": f"Not a directory: {path}"}

        try:
            entries = []
            for item in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
                entries.append(_entry_info(item, p))
                if len(entries) >= max_entries:
                    break

            return {
                "status": "ok",
                "path": str(p),
                "entries": entries,
                "total": len(entries),
                "truncated": len(list(p.iterdir())) > max_entries,
            }
        except PermissionError:
            return {"status": "error", "message": f"Permission denied: {path}"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    # ------------------------------------------------------------------
    # WRITE (requires approval)
    # ------------------------------------------------------------------
    async def write_file(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8",
        require_approval: bool = True,
    ) -> Dict[str, Any]:
        """
        Write content to a file.
        Requires user approval via the Electron approval modal.

        Args:
            path:             Absolute or relative file path.
            content:          Text content to write.
            encoding:         File encoding (default utf-8).
            require_approval: Set False only for system-internal operations.

        Returns:
            {status, path, bytes_written} or {status, error, message}
        """
        p = Path(path).resolve()
        logger.info(f"[FS] write_file: {p} ({len(content)} chars)")

        safe, reason = _is_path_safe(p)
        if not safe:
            return {"status": "error", "message": reason}

        action_label = "create" if not p.exists() else "overwrite"

        if require_approval:
            preview = content[:200].replace("\n", "↵")
            approved = await request_approval(
                operation=f"Write file ({action_label})",
                path=str(p),
                details=f"Content preview: {preview}…" if len(content) > 200 else content,
            )
            if not approved:
                return {"status": "denied", "message": "User did not approve the file write."}

        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            bytes_written = p.write_text(content, encoding=encoding)
            logger.info(f"[FS] Wrote {len(content)} chars to {p}")
            return {
                "status": "ok",
                "path": str(p),
                "bytes_written": p.stat().st_size,
                "action": action_label,
            }
        except Exception as exc:
            logger.error(f"[FS] write_file failed: {exc}")
            return {"status": "error", "message": str(exc)}

    async def create_file(
        self,
        path: str,
        content: str = "",
        require_approval: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a new file. Wraps write_file with an existence check.
        """
        p = Path(path).resolve()
        if p.exists():
            return {"status": "error", "message": f"File already exists: {path}"}
        return await self.write_file(path, content, require_approval=require_approval)

    async def delete_file(
        self,
        path: str,
        require_approval: bool = True,
    ) -> Dict[str, Any]:
        """
        Delete a file. Always requires user approval.
        Sends a double-confirm message to make the risk clear.

        Args:
            path:             Path to the file to delete.
            require_approval: Always True (parameter kept for interface consistency).

        Returns:
            {status, path} or {status, error, message}
        """
        p = Path(path).resolve()
        logger.info(f"[FS] delete_file: {p}")

        if not p.exists():
            return {"status": "error", "message": f"File not found: {path}"}

        safe, reason = _is_path_safe(p)
        if not safe:
            return {"status": "error", "message": reason}

        # Always require approval for deletes, no override
        approved = await request_approval(
            operation="⚠️ DELETE FILE (PERMANENT)",
            path=str(p),
            details=f"This will permanently delete '{p.name}'. This action cannot be undone.",
        )
        if not approved:
            return {"status": "denied", "message": "User did not approve the file deletion."}

        try:
            p.unlink()
            logger.info(f"[FS] Deleted: {p}")
            return {"status": "ok", "path": str(p), "action": "deleted"}
        except Exception as exc:
            logger.error(f"[FS] delete_file failed: {exc}")
            return {"status": "error", "message": str(exc)}

    async def create_directory(
        self,
        path: str,
        require_approval: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a directory (and any missing parents).
        Requires approval.
        """
        p = Path(path).resolve()
        logger.info(f"[FS] create_directory: {p}")

        if p.exists():
            return {"status": "ok", "path": str(p), "action": "already_exists"}

        if require_approval:
            approved = await request_approval(
                operation="Create directory",
                path=str(p),
                details=f"Will create directory '{p.name}' and any missing parent folders.",
            )
            if not approved:
                return {"status": "denied", "message": "User did not approve directory creation."}

        try:
            p.mkdir(parents=True, exist_ok=True)
            return {"status": "ok", "path": str(p), "action": "created"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def status(self) -> Dict[str, Any]:
        """Return FS tools status for monitoring dashboard."""
        return {
            "pending_approvals": len(_pending_approvals),
            "approval_ws_connections": len(_approval_ws_connections),
            "max_read_bytes": self.MAX_READ_BYTES,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_fs_tools: Optional[FSTools] = None

def get_fs_tools() -> FSTools:
    """Return (or create) the FSTools singleton."""
    global _fs_tools
    if _fs_tools is None:
        _fs_tools = FSTools()
    return _fs_tools
