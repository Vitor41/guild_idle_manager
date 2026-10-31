"""Small, user-shareable logs for desktop gameplay actions."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import threading
import traceback

from app.desktop.paths import user_log_directory


_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 2
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|token|secret|authorization|cookie|api[_-]?key)\b(\s*[:=]\s*)[^\s,;]+"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*")
_LOGGERS: dict[str, logging.Logger] = {}
_LOCK = threading.Lock()


def gameplay_log_path() -> Path:
    """Return the persistent per-user log location, outside the app and saves."""
    return user_log_directory() / "gameplay-actions.log"


def _sanitize(value: str) -> str:
    value = _BEARER.sub("Bearer [REDACTED]", value)
    value = _SECRET_ASSIGNMENT.sub(r"\1\2[REDACTED]", value)
    return value[:12_000]


def _logger_for(path: Path) -> logging.Logger:
    key = str(path.resolve())
    with _LOCK:
        logger = _LOGGERS.get(key)
        if logger is None:
            path.parent.mkdir(parents=True, exist_ok=True)
            logger = logging.getLogger(f"gim.gameplay.{len(_LOGGERS)}")
            logger.setLevel(logging.INFO)
            logger.propagate = False
            logger.addHandler(RotatingFileHandler(
                path, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8",
            ))
            _LOGGERS[key] = logger
        return logger


def close_gameplay_logger(path: Path) -> None:
    """Close a test or shutdown log handle without changing its file."""
    key = str(path.resolve())
    with _LOCK:
        logger = _LOGGERS.pop(key, None)
        if logger is None:
            return
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()


def log_gameplay_action(
    *,
    action: str,
    route: str,
    diagnostic_id: str,
    status_code: int,
    outcome: str,
    exception: BaseException | None = None,
    log_path: Path | None = None,
) -> None:
    """Write one bounded, credential-free text record. Request bodies are never logged."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    line = (
        f"{timestamp} action={_sanitize(action)} route={_sanitize(route)} "
        f"ref={_sanitize(diagnostic_id)} status={int(status_code)} outcome={_sanitize(outcome)}"
    )
    if exception is not None:
        stack = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        line += "\n" + _sanitize(stack)
    try:
        _logger_for(log_path or gameplay_log_path()).info("%s", line)
    except OSError:
        # Logging must not prevent the game action or hide its visible response.
        return
