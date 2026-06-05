"""Apply a Slack Approve/Reject interaction. Pure orchestration over injected ports — unit-testable.

Approve → publish to ``opssentinel-actions`` (the Phase-3 executor consumes it) + audit.
Reject  → set ``status = rejected`` + audit. No new topics/schemas.
"""

from __future__ import annotations

from typing import Any, Protocol

# Mirrors the shared Slack contract (and app.brief_format); kept local so this module has no
# intra-package import and stays trivially testable in isolation.
APPROVE_ACTION = "approve_incident"
REJECT_ACTION = "reject_incident"


class ActionPublisher(Protocol):
    def publish_action(self, decision: dict[str, Any]) -> None: ...


class IncidentUpdater(Protocol):
    def set_rejected(self, incident_id: str, approver: str) -> None: ...
    def audit(self, incident_id: str, actor: str, action: str, details: dict[str, Any]) -> None: ...


def handle_decision(
    action_id: str,
    incident_id: str,
    approver: str,
    *,
    publisher: ActionPublisher,
    updater: IncidentUpdater,
) -> str:
    """Route an Approve/Reject button click. Returns the resulting decision string."""
    if action_id == APPROVE_ACTION:
        publisher.publish_action(
            {"incident_id": incident_id, "decision": "approve", "approver": approver}
        )
        updater.audit(incident_id, approver, "slack_approved", {"channel": "slack"})
        return "approved"
    if action_id == REJECT_ACTION:
        updater.set_rejected(incident_id, approver)
        updater.audit(incident_id, approver, "slack_rejected", {"channel": "slack"})
        return "rejected"
    raise ValueError(f"unknown action_id: {action_id}")
