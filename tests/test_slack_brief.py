"""Tests for the Slack decision-brief formatting (Phase 5, Task A)."""

import importlib.util
import pathlib

_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "services"
    / "slack-bot"
    / "app"
    / "brief_format.py"
)
_spec = importlib.util.spec_from_file_location("slack_brief", _PATH)
brief_format = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(brief_format)

ROW = {
    "incident_id": "i1",
    "title": "[P1] Database Connection Pool on payment-service",
    "category": "Database Connection Pool",
    "root_cause": "connection pool exhausted after deploy",
    "risk_level": "high",
    "autonomy_tier": "moderate",
    "historical_match_ids": ["rb-db-conn-limit"],
    "recommended_action": {"steps": ["restart the connection pool", "raise max pool size"]},
}


def test_brief_from_incident_maps_row():
    brief = brief_format.brief_from_incident(ROW)
    assert brief["incident_id"] == "i1"
    assert brief["risk_level"] == "high"
    assert brief["historical_match_id"] == "rb-db-conn-limit"
    assert brief["proposed_fix_steps"] == ["restart the connection pool", "raise max pool size"]


def test_message_has_binary_buttons_carrying_incident_id():
    brief = brief_format.brief_from_incident(ROW)
    message = brief_format.build_message(brief, dashboard_url="http://dash/incidents/i1")
    actions = next(b for b in message["blocks"] if b["type"] == "actions")
    by_action = {e["action_id"]: e for e in actions["elements"]}
    assert set(by_action) == {"approve_incident", "reject_incident"}
    assert all(e["value"] == "i1" for e in actions["elements"])


def test_brief_text_includes_root_cause_and_risk():
    text = brief_format.format_brief_text(brief_format.brief_from_incident(ROW))
    assert "connection pool exhausted" in text
    assert "high" in text
    assert "restart the connection pool" in text
