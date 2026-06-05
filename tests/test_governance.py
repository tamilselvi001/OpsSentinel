"""Tests for the deterministic governance step that runs after the ADK agent (Phase 6, Task 4).

Replaces the old test_graph orchestration test: the LLM/MCP reasoning now lives in ADK; the
deterministic autonomy + Policy Engine + brief composition is what we unit-test here.
"""

import pathlib
import sys
from types import SimpleNamespace

_AGENT = pathlib.Path(__file__).resolve().parent.parent / "services" / "agent"
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from app.governance import apply_governance  # noqa: E402
from app.models import AgentProposal  # noqa: E402


def _context():
    return SimpleNamespace(
        environment="production",
        service="payment-service",
        size=50,
        event_ids=[f"e{i}" for i in range(50)],
        correlation_key="abc123",
    )


def _proposal(**overrides):
    base = dict(
        category="Database Connection Pool",
        severity="P2",
        remediation_team="sre-oncall",
        confidence=0.88,
        root_cause="connection pool exhausted after deploy",
        summary="restart pool and raise limit",
        steps=["restart the connection pool"],
        commands=["kubectl rollout restart deploy/payment-service"],
        risk_level="medium",
        based_on_runbook_id="rb-db-conn-limit",
        historical_match_ids=["rb-db-conn-limit"],
        category_accuracy=0.91,
        calibration_error=0.01,
        is_novel=False,
    )
    base.update(overrides)
    return AgentProposal(**base)


def test_db_pool_proposal_high_autonomy_and_policy_floor():
    gov = apply_governance("inc-1", _context(), _proposal())
    assert gov.autonomy.tier == "high"  # 91% + well-calibrated
    assert gov.policy.final_severity == "P1"  # production + payment floor
    assert gov.brief["historical_match"]["id"] == "rb-db-conn-limit"
    assert gov.brief["incident_id"] == "inc-1"


def test_high_risk_forces_approval_gate():
    gov = apply_governance("inc-2", _context(), _proposal(risk_level="high"))
    assert gov.policy.approval_required is True
    assert "high_risk_requires_approval" in gov.policy.gates
    assert gov.brief["approval_required"] is True


def test_degraded_accuracy_lowers_autonomy():
    gov = apply_governance("inc-3", _context(), _proposal(category_accuracy=0.55))
    assert gov.autonomy.tier == "low"


def test_novel_category_lowers_autonomy():
    gov = apply_governance("inc-4", _context(), _proposal(is_novel=True))
    assert gov.autonomy.tier == "low"
