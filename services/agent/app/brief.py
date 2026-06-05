"""Structured execution brief (node 8) — the human decision document.

Pure builder (inputs are duck-typed, no app/db imports) so it is unit-testable. The brief is
persisted on the incident and is exactly what Phase 5 renders into the Slack Block Kit message:
title, root cause, correlated evidence, confidence, historical match, proposed fix, risk level,
and the autonomy/caution note.
"""

from __future__ import annotations

from typing import Any


def build_execution_brief(
    *,
    incident_id: str,
    context: Any,  # correlation.IncidentContext (duck-typed)
    classification: Any,  # models.Classification
    recommendation: Any,  # models.Recommendation
    historical_matches: list[dict[str, Any]],
    autonomy: Any,  # autonomy.AutonomyDecision
    policy: Any,  # policy.engine.PolicyDecision
) -> dict[str, Any]:
    """Assemble the brief dict persisted on the incident and surfaced to the approver."""
    top_match = historical_matches[0] if historical_matches else None
    return {
        "incident_id": incident_id,
        "title": f"[{policy.final_severity}] {classification.category} on {context.service}",
        "service": context.service,
        "severity": policy.final_severity,
        "category": classification.category,
        "remediation_team": classification.remediation_team,
        "root_cause": classification.root_cause,
        "confidence": round(float(classification.confidence), 3),
        "correlated_evidence": {
            "event_count": context.size,
            "event_ids": context.event_ids,
            "correlation_key": context.correlation_key,
        },
        "historical_match": top_match,
        "proposed_fix_steps": list(recommendation.steps),
        "commands": list(recommendation.commands),
        "risk_level": recommendation.risk_level,
        "autonomy_tier": autonomy.tier,
        "autonomy_note": autonomy.caution_note or autonomy.reason,
        "approval_required": policy.approval_required,
        "policy_gates": policy.gates,
    }
