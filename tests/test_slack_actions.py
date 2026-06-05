"""Tests for the Slack Approve/Reject routing (Phase 5, Task A)."""

import importlib.util
import pathlib

import pytest

_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "services" / "slack-bot" / "app" / "actions.py"
)
_spec = importlib.util.spec_from_file_location("slack_actions", _PATH)
actions = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(actions)


class FakePublisher:
    def __init__(self):
        self.published = []

    def publish_action(self, decision):
        self.published.append(decision)


class FakeUpdater:
    def __init__(self):
        self.rejected = []
        self.audits = []

    def set_rejected(self, incident_id, approver):
        self.rejected.append((incident_id, approver))

    def audit(self, incident_id, actor, action, details):
        self.audits.append((incident_id, actor, action))


def test_approve_publishes_action_and_audits():
    pub, upd = FakePublisher(), FakeUpdater()
    result = actions.handle_decision("approve_incident", "i1", "alice", publisher=pub, updater=upd)
    assert result == "approved"
    assert pub.published == [{"incident_id": "i1", "decision": "approve", "approver": "alice"}]
    assert upd.rejected == []  # approve does not reject
    assert upd.audits[0][2] == "slack_approved"


def test_reject_sets_rejected_and_audits_without_publishing():
    pub, upd = FakePublisher(), FakeUpdater()
    result = actions.handle_decision("reject_incident", "i2", "bob", publisher=pub, updater=upd)
    assert result == "rejected"
    assert pub.published == []  # reject never triggers the executor
    assert upd.rejected == [("i2", "bob")]
    assert upd.audits[0][2] == "slack_rejected"


def test_unknown_action_raises():
    with pytest.raises(ValueError):
        actions.handle_decision(
            "nope", "i3", "carol", publisher=FakePublisher(), updater=FakeUpdater()
        )
