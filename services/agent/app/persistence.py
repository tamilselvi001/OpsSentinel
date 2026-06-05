"""Incident persistence + governance audit trail (node 8 side-effects). Uses Phase-1 lib.db.

Every state change and AI decision is written to ``audit_log`` (append-only) alongside the
``incidents`` upsert — the governance-grade trail. Heavy DB import is module-level (this module is
only loaded by the running agent, not by the pure unit tests).
"""

from __future__ import annotations

from typing import Any

from lib.db import append_audit, upsert_incident


def incident_row_from_brief(
    brief: dict[str, Any], *, status: str, trace_id: str | None
) -> dict[str, Any]:
    """Map an execution brief to an ``incidents`` row (Phase-1 schema columns)."""
    evidence = brief.get("correlated_evidence", {})
    match = brief.get("historical_match") or {}
    return {
        "incident_id": brief["incident_id"],
        "status": status,
        "severity": brief.get("severity"),
        "category": brief.get("category"),
        "title": brief.get("title"),
        "root_cause": brief.get("root_cause"),
        "confidence": brief.get("confidence"),
        "risk_level": brief.get("risk_level"),
        "correlated_event_ids": evidence.get("event_ids", []),
        "recommended_action": {
            "steps": brief.get("proposed_fix_steps", []),
            "commands": brief.get("commands", []),
        },
        "historical_match_ids": [match["id"]] if match.get("id") else [],
        "autonomy_tier": brief.get("autonomy_tier"),
        "trace_id": trace_id,
    }


def persist_incident(
    brief: dict[str, Any],
    *,
    status: str,
    trace_id: str | None,
    actor: str = "agent",
) -> str:
    """Upsert the incident and append a governance audit entry. Returns the incident id."""
    row = incident_row_from_brief(brief, status=status, trace_id=trace_id)
    incident_id = upsert_incident(row)
    append_audit(
        actor=actor,
        action=f"transition:{status}",
        incident_id=incident_id,
        details={
            "severity": row["severity"],
            "autonomy_tier": row["autonomy_tier"],
            "risk_level": row["risk_level"],
            "policy_gates": brief.get("policy_gates", []),
            "approval_required": brief.get("approval_required"),
        },
    )
    return incident_id
