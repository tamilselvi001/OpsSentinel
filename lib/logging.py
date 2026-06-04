"""Structured JSON logging for every service — consistent, machine-parseable, secret-safe.

``get_logger(name)`` returns a logger that emits one JSON object per line (Cloud Run /
Cloud Logging friendly). Extra fields passed via ``logger.info(msg, extra={...})`` are
included, except keys that look like credentials, which are redacted as a defense in depth
against accidentally logging a secret value.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

_REDACT_HINTS = ("token", "secret", "password", "api_key", "apikey", "authorization", "credential")
_REDACTED = "***REDACTED***"

# Attributes present on a stock LogRecord — anything else is caller-supplied "extra".
_STANDARD_FIELDS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime", "taskName"}


def _should_redact(key: str) -> bool:
    lowered = key.lower()
    return any(hint in lowered for hint in _REDACT_HINTS)


class JsonFormatter(logging.Formatter):
    """Render a ``LogRecord`` as a single-line JSON document."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key in _STANDARD_FIELDS or key.startswith("_"):
                continue
            payload[key] = _REDACTED if _should_redact(key) else value
        return json.dumps(payload, default=str)


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a process-wide logger that writes structured JSON to stdout."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
    return logger
