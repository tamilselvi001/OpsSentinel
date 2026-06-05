"""Format the persisted incident into a Slack plain-text decision brief + Approve/Reject buttons.

Pure logic — unit-testable. The brief is reconstructed from the incident-store row the agent
persisted (no new schema). Buttons carry the ``incident_id`` in their ``value`` per the contract.
"""

from __future__ import annotations

from typing import Any

APPROVE_ACTION = "approve_incident"
REJECT_ACTION = "reject_incident"


def brief_from_incident(row: dict[str, Any]) -> dict[str, Any]:
    """Adapt an ``incidents`` row into the brief shape this formatter expects."""
    action = row.get("recommended_action") or {}
    matches = row.get("historical_match_ids") or []
    return {
        "incident_id": str(row.get("incident_id")),
        "title": row.get("title") or row.get("category") or "Incident",
        "root_cause": row.get("root_cause"),
        "risk_level": row.get("risk_level"),
        "autonomy_tier": row.get("autonomy_tier"),
        "historical_match_id": matches[0] if matches else None,
        "proposed_fix_steps": action.get("steps", []),
    }


def format_brief_text(brief: dict[str, Any]) -> str:
    lines = [
        f"*{brief.get('title', 'Incident')}*",
        f"*Root cause:* {brief.get('root_cause') or '—'}",
        f"*Risk level:* {brief.get('risk_level') or '—'}",
        f"*Autonomy:* {brief.get('autonomy_tier') or '—'}",
        f"*Historical precedent:* {brief.get('historical_match_id') or '—'}",
        "*Proposed fix:*",
    ]
    steps = brief.get("proposed_fix_steps") or []
    lines.extend(f"  {i + 1}. {step}" for i, step in enumerate(steps))
    if not steps:
        lines.append("  (no steps proposed)")
    return "\n".join(lines)


def build_message(brief: dict[str, Any], *, dashboard_url: str | None = None) -> dict[str, Any]:
    """Block Kit message: plain-text brief + binary Approve/Reject buttons (value = incident_id)."""
    incident_id = brief["incident_id"]
    blocks: list[dict[str, Any]] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": format_brief_text(brief)}},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "style": "primary",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "action_id": APPROVE_ACTION,
                    "value": incident_id,
                },
                {
                    "type": "button",
                    "style": "danger",
                    "text": {"type": "plain_text", "text": "Reject"},
                    "action_id": REJECT_ACTION,
                    "value": incident_id,
                },
            ],
        },
    ]
    if dashboard_url:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"<{dashboard_url}|See full reasoning>"},
            }
        )
    return {"text": f"Incident {incident_id} awaiting approval", "blocks": blocks}
