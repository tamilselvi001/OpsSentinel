"""Deterministic governance — the off-LLM nodes that run after the ADK reasoner produces a proposal.

This is the spec's "bypass the LLM for deterministic tasks": the autonomy tier and the Policy Engine
gate are computed in plain Python from the metrics the agent gathered — the LLM cannot bypass them.
Pure logic, fully unit-testable; reuses the Phase-3 deterministic modules unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from policy import engine as policy_engine

from app.autonomy import AutonomyDecision, decide_autonomy
from app.brief import build_execution_brief
from app.models import AgentProposal, Classification, Recommendation


@dataclass
class Governance:
    autonomy: AutonomyDecision
    policy: Any  # policy.engine.PolicyDecision
    brief: dict[str, Any]


def apply_governance(incident_id: str, context: Any, proposal: AgentProposal) -> Governance:
    """Map the proposal + Arize metrics to an autonomy tier, policy decision, and brief."""
    autonomy = decide_autonomy(
        accuracy=proposal.category_accuracy,
        calibration_error=proposal.calibration_error,
        is_novel=proposal.is_novel,
        intent_confidence=proposal.confidence,
    )

    classification = Classification(
        category=proposal.category,
        severity=proposal.severity,
        remediation_team=proposal.remediation_team,
        confidence=proposal.confidence,
        root_cause=proposal.root_cause,
    )
    recommendation = Recommendation(
        summary=proposal.summary,
        steps=proposal.steps,
        commands=proposal.commands,
        risk_level=proposal.risk_level,
        based_on_runbook_id=proposal.based_on_runbook_id,
    )

    policy = policy_engine.evaluate(
        policy_engine.PolicyInput(
            severity=proposal.severity,
            environment=context.environment,
            service=context.service,
            risk_level=proposal.risk_level,
            autonomy_tier=autonomy.tier,
            recommended_steps=proposal.steps,
            recommended_commands=proposal.commands,
        )
    )

    historical_matches = [{"id": match_id} for match_id in proposal.historical_match_ids]
    brief = build_execution_brief(
        incident_id=incident_id,
        context=context,
        classification=classification,
        recommendation=recommendation,
        historical_matches=historical_matches,
        autonomy=autonomy,
        policy=policy,
    )
    return Governance(autonomy=autonomy, policy=policy, brief=brief)
