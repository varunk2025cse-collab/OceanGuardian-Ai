"""
Centralized logging configuration for OceanGuardian AI.

Provides structured JSON logging and lightweight request/correlation id helpers.
Falls back to simple console logging when JSON formatting is not needed.
"""
import logging
import sys
import json
from datetime import datetime
import uuid
import contextvars
from typing import Optional
from app.config import settings

# Context variables for per-request identifiers
_correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("correlation_id", default=None)
_trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("trace_id", default=None)


class JSONFormatter(logging.Formatter):
    """Minimal JSON formatter for structured logs without external deps."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Attach correlation/trace ids from contextvars if available
        try:
            corr = _correlation_id_var.get()
            if corr:
                payload["correlation_id"] = corr
        except LookupError:
            pass

        try:
            tr = _trace_id_var.get()
            if tr:
                payload["trace_id"] = tr
        except LookupError:
            pass

        # Include any extra fields passed in the LogRecord
        extras = {k: v for k, v in record.__dict__.items() if k not in (
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process"
        )}
        if extras:
            payload["extra"] = extras

        try:
            return json.dumps(payload, default=str, ensure_ascii=False)
        except Exception:
            # Fallback to plain message if JSON serialization fails
            return f"{record.levelname}: {record.getMessage()}"


def set_correlation_id(val: Optional[str] = None) -> str:
    """Set correlation id for current context, returning the value used."""
    if not val:
        val = str(uuid.uuid4())
    _correlation_id_var.set(val)
    return val


def get_correlation_id() -> Optional[str]:
    try:
        return _correlation_id_var.get()
    except LookupError:
        return None


def clear_correlation_id() -> None:
    _correlation_id_var.set(None)


def set_trace_id(val: Optional[str] = None) -> str:
    if not val:
        val = str(uuid.uuid4())
    _trace_id_var.set(val)
    return val


def get_trace_id() -> Optional[str]:
    try:
        return _trace_id_var.get()
    except LookupError:
        return None


def setup_logging() -> logging.Logger:
    """Configure application-wide logging with JSON formatter."""
    log_level = logging.DEBUG if settings.environment == "development" else logging.INFO

    root = logging.getLogger()
    root.setLevel(log_level)

    # Remove default handlers to ensure deterministic formatting
    for h in list(root.handlers):
        root.removeHandler(h)

    stream = logging.StreamHandler(sys.stdout)
    stream.setLevel(log_level)
    stream.setFormatter(JSONFormatter())

    root.addHandler(stream)

    # Specific logger levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("app").setLevel(log_level)

    return logging.getLogger("app")


# Initialize logger
logger = setup_logging()
