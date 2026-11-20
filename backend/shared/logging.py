"""
Structured logging with correlation ID propagation.

Uses stdlib logging throughout so no extra dependencies are required.
JSON output is the default; set LOG_FORMAT=text for local development.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Any

# Fields that belong to LogRecord's own namespace and should not be echoed
_RECORD_BUILTINS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname",
    "filename", "module", "exc_info", "exc_text", "stack_info",
    "lineno", "funcName", "created", "msecs", "relativeCreated",
    "thread", "threadName", "processName", "process", "message",
    "taskName",
})


class JSONFormatter(logging.Formatter):
    """Emit one JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()

        entry: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
            "module": record.module,
            "function": record.funcName,
        }

        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)

        # Merge caller-supplied extras (correlation_id, event_id, …)
        for key, value in record.__dict__.items():
            if key not in _RECORD_BUILTINS and not key.startswith("_"):
                entry[key] = value

        return json.dumps(entry, default=str)


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Configure the root logger.  Call once at application startup."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)

    if fmt == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )

    root.handlers.clear()
    root.addHandler(handler)

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger under the 'aegis.' prefix."""
    return logging.getLogger(f"aegis.{name}")
