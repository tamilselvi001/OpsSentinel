"""Tests for structured JSON logging (Phase 1, Task 5.9 — secret-safe logging)."""

import json
import logging

from lib.logging import JsonFormatter


def _record(**extra):
    record = logging.LogRecord(
        name="opssentinel.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_emits_expected_fields():
    out = JsonFormatter().format(_record(incident_id="inc-1"))
    data = json.loads(out)
    assert data["message"] == "hello world"
    assert data["severity"] == "INFO"
    assert data["logger"] == "opssentinel.test"
    assert data["incident_id"] == "inc-1"
    assert "timestamp" in data


def test_secret_like_fields_are_redacted():
    out = JsonFormatter().format(_record(slack_bot_token="xoxb-supersecret", api_key="abc123"))
    data = json.loads(out)
    assert data["slack_bot_token"] == "***REDACTED***"
    assert data["api_key"] == "***REDACTED***"
    assert "xoxb-supersecret" not in out
