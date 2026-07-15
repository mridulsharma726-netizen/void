"""VOID Observability - Enhanced Logging Utilities

This module is intentionally dependency-free (stdlib only).
It provides:
- JSON structured logging formatter
- Request/trace id propagation via contextvars
- Timed sections via a context manager
- Basic secret redaction
- Convenience get_logger() and timed_section()

Drop-in usage examples:

    from VOID.tools.observability_logger_enhanced import get_logger, timed_section, set_request_id

    set_request_id("req-123")
    log = get_logger(__name__)
    log.info("hello", extra={"component": "demo"})

    with timed_section(log, "db.query"):
        ...

"""

from __future__ import annotations

import contextlib
import contextvars
import datetime as _dt
import hashlib
import json
import logging
import os
import re
import sys
import threading
import time
from typing import Any, Dict, Iterator, Optional


# -----------------------------
# Context / correlation ids
# -----------------------------

_request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "void_request_id", default=None
)

_trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "void_trace_id", default=None
)

_span_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "void_span_id", default=None
)


def set_request_id(value: Optional[str]) -> None:
    """Set the request id for the current context."""
    _request_id_var.set(value)


def get_request_id() -> Optional[str]:
    """Get the request id for the current context."""
    return _request_id_var.get()


def set_trace_id(value: Optional[str]) -> None:
    """Set the trace id for the current context."""
    _trace_id_var.set(value)


def get_trace_id() -> Optional[str]:
    """Get the trace id for the current context."""
    return _trace_id_var.get()


def set_span_id(value: Optional[str]) -> None:
    """Set the span id for the current context."""
    _span_id_var.set(value)


def get_span_id() -> Optional[str]:
    """Get the span id for the current context."""
    return _span_id_var.get()\\\


# -----------------------------
# Secret redaction
# -----------------------------

_SECRET_PATTERNS = [
    # Common token/header formats
    re.compile(r"(?i)(authorization)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)(api[-_]?key)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)(access[_-]?token)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)(bearer)\s+[^\s]+"),
    # Key=... pairs
    re.compile(r"(?i)\b(secret|token|password)\b\s*[:=]\s*[^\s,;]+"),
]


def _redact_value(s: str) -> str:
    out = s
    for pat in _SECRET_PATTERNS:
        out = pat.sub(lambda m: f"{m.group(1)}:***REDACTED***" if m.lastindex else "***REDACTED***", out)
    return out


def redact(obj: Any) -> Any:
    """Recursively redact sensitive values in common structures."""
    if obj is None:
        return None
    if isinstance(obj, (int, float, bool)):
        return obj
    if isinstance(obj, str):
        return _redact_value(obj)
    if isinstance(obj, bytes):
        try:
            return _redact_value(obj.decode("utf-8", errors="ignore"))
        except Exception:
            return "***REDACTED_BYTES***"
    if isinstance(obj, dict):
        return {str(k): redact(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        t = [redact(v) for v in obj]
        return t if not isinstance(obj, set) else list(t)
    # fallback
    try:
        return _redact_value(str(obj))
    except Exception:
        return "***UNREDACTABLE***"


# -----------------------------
# JSON formatter
# -----------------------------


def _utc_iso() -> str:
    return _dt.datetime.utcnow().replace(tzinfo=_dt.timezone.utc).isoformat()


def _hash_short(s: str, length: int = 10) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:length]


class JsonLogFormatter(logging.Formatter):
    """Format standard LogRecord into a JSON string."""

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        # Base message
        msg = record.getMessage()

        # Merge any record extras
        extra: Dict[str, Any] = {}
        # Only include keys not part of standard LogRecord
        standard = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "asctime",
        }

        for k, v in record.__dict__.items():
            if k not in standard:
                extra[k] = v

        # Correlation ids
        request_id = get_request_id()
        trace_id = get_trace_id()
        span_id = get_span_id()

        # Host/runtime context
        host = os.environ.get("HOSTNAME") or os.environ.get("COMPUTERNAME")
        pid = record.process
        tid = getattr(record, "thread", None)

        payload = {
            "ts": _utc_iso(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(msg),
            "request_id": request_id,
            "trace_id": trace_id,
            "span_id": span_id,
            "component": extra.get("component"),
            "event": extra.get("event"),
            "thread": record.threadName,
            "pid": pid,
            "host": host,
            "source": {
                "file": record.filename,
                "line": record.lineno,
                "func": record.funcName,
            },
            "extra": redact(extra),
        }

        # Include exception info when present
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


# -----------------------------
# Logger factory
# -----------------------------


_LOGGER_CREATED_LOCK = threading.Lock()
_CREATED_HANDLERS: Dict[str, logging.Handler] = {}


def get_logger(name: str = "void") -> logging.Logger:
    """Get a JSON logger with request/trace context.

    This configures a StreamHandler once per logger name.
    """
    logger = logging.getLogger(name)

    # Configure default level: INFO
    if logger.level == logging.NOTSET:
        logger.setLevel(os.environ.get("VOID_LOG_LEVEL", "INFO"))

    with _LOGGER_CREATED_LOCK:
        if name not in _CREATED_HANDLERS:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(JsonLogFormatter())
            handler.setLevel(logger.level)
            logger.addHandler(handler)
            logger.propagate = False
            _CREATED_HANDLERS[name] = handler

    return logger


# -----------------------------
# Timed sections
# -----------------------------


@contextlib.contextmanager
def timed_section(
    logger: logging.Logger,
    section_name: str,
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> Iterator[None]:
    """Measure duration of a code block and log it.

    Emits two log lines:
    - event=start (with monotonic ms)
    - event=end (with duration_ms)

    """
    extra = extra or {}
    start = time.perf_counter()
    logger.info(
        "section_start",
        extra={"event": "section_start", "component": extra.get("component"), "section": section_name, **extra},
    )
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000.0
        logger.info(
            "section_end",
            extra={
                "event": "section_end",
                "component": extra.get("component"),
                "section": section_name,
                "duration_ms": round(duration_ms, 3),
                **extra,
            },
        )


# -----------------------------
# Lightweight span id helpers
# -----------------------------


def make_span_id(seed: Optional[str] = None) -> str:
    """Create a short deterministic-ish span id."""
    base = seed or f"{time.time_ns()}-{threading.get_ident()}"
    return _hash_short(base)


@contextlib.contextmanager
def span(logger: logging.Logger, name: str, *, extra: Optional[Dict[str, Any]] = None) -> Iterator[None]:
    """Convenience context manager to set span_id for the duration."""
    extra = extra or {}
    prev = get_span_id()
    sid = make_span_id(f"{name}-{prev}-{time.time_ns()}")
    set_span_id(sid)
    logger.info(
        "span_start",
        extra={"event": "span_start", "span_name": name, "span_id": sid, **extra},
    )
    try:
        yield
    finally:
        logger.info(
            "span_end",
            extra={"event": "span_end", "span_name": name, "span_id": sid, **extra},
        )
        set_span_id(prev)


# -----------------------------
# Minimal self-test
# -----------------------------


def _self_test() -> None:
    log = get_logger("void.observability")

    # Demonstrate correlation ids
    set_request_id("req-demo")
    set_trace_id("trace-demo")
    set_span_id(None)

    log.info(
        "test_event",
        extra={"component": "self_test", "event": "hello", "token": "Bearer SECRET_TOKEN_123"},
    )

    with timed_section(log, "demo_sleep", extra={"component": "self_test"}):
        time.sleep(0.05)

    with span(log, "outer"):
        with timed_section(log, "inner", extra={"component": "self_test"}):
            time.sleep(0.02)

    log.info(
        "done",
        extra={"component": "self_test", "event": "complete"},
    )


if __name__ == "__main__":
    _self_test()

