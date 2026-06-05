"""Tests for the execution-brief builder (Phase 3, Task 6.8)."""

import importlib.util
import pathlib
import sys
from types import SimpleNamespace

_APP = pathlib.Path(__file__).resolve().parent.parent / "services" / "agent" / "app"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _APP / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


brief = _load("agent_brief", "brief.py")
models = _load("agent_models", "models.py")


def _build():
    context = SimpleNamespace(
        size=50,
        event_ids=[f"e{i}" for i in range(50)],
        correlation_key="abc123",
        service="payment-service",
    )
    classification = models.Classification(
        category="Database Connection Pool",
        severity="P1",
        remediation_team="sre-oncall",
        confidence=0.88,
        root_cause="connection pool exhausted after deploy",
    )
    recommendation = models.Recommendation(
        summary="Restart pool and raise limit",
        steps=["restart the connection pool", "raise max pool size"],
        commands=["kubectl rollout restart deploy/payment-service"],
        risk_level="high",
        based_on_runbook_id="rb-db-conn-limit",
    )
    historical = [{"id": "rb-db-conn-limit", "title": "Database Connection Limit Reached"}]
    autonomy = SimpleNamespace(tier="moderate", caution_note="verify before approval", reason="r")
    policy = SimpleNamespace(
        final_severity="P1", approval_required=True, gates=["high_risk_requires_approval"]
    )
    return brief.build_execution_brief(
        incident_id="inc-1",
        context=context,
        classification=classification,
        recommendation=recommendation,
        historical_matches=historical,
        autonomy=autonomy,
        policy=policy,
    )


def test_brief_has_all_decision_sections():
    b = _build()
    assert b["incident_id"] == "inc-1"
    assert b["severity"] == "P1"
    assert b["root_cause"].startswith("connection pool")
    assert b["correlated_evidence"]["event_count"] == 50
    assert b["historical_match"]["id"] == "rb-db-conn-limit"
    assert b["proposed_fix_steps"] == ["restart the connection pool", "raise max pool size"]
    assert b["risk_level"] == "high"
    assert b["autonomy_tier"] == "moderate"
    assert b["approval_required"] is True
    assert "high_risk_requires_approval" in b["policy_gates"]


def test_brief_title_summarizes_severity_and_service():
    b = _build()
    assert b["title"] == "[P1] Database Connection Pool on payment-service"


def test_brief_handles_no_historical_match():
    context = SimpleNamespace(size=1, event_ids=["e0"], correlation_key="k", service="auth-service")
    classification = models.Classification("Kubernetes Pod Failure", "P2", "sre", 0.7, "rc")
    recommendation = models.Recommendation("s", ["step"], [], "low")
    autonomy = SimpleNamespace(tier="high", caution_note=None, reason="accurate")
    policy = SimpleNamespace(final_severity="P2", approval_required=False, gates=[])
    b = brief.build_execution_brief(
        incident_id="inc-2",
        context=context,
        classification=classification,
        recommendation=recommendation,
        historical_matches=[],
        autonomy=autonomy,
        policy=policy,
    )
    assert b["historical_match"] is None
    assert b["autonomy_note"] == "accurate"  # falls back to reason when no caution note
