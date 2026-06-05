"""Tests for the deterministic Policy Engine + SLA timers (Phase 3, Task 6.6)."""

import importlib.util
import pathlib
import sys
from datetime import UTC, datetime, timedelta

_POLICY_DIR = pathlib.Path(__file__).resolve().parent.parent / "services" / "agent" / "policy"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _POLICY_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


engine = _load("agent_policy_engine", "engine.py")
sla = _load("agent_policy_sla", "sla.py")


def _input(**overrides):
    base = {
        "severity": "P3",
        "environment": "production",
        "service": "payment-service",
        "risk_level": "low",
        "autonomy_tier": "high",
        "recommended_steps": ["restart the connection pool"],
        "recommended_commands": ["kubectl rollout restart deploy/payment-service"],
    }
    base.update(overrides)
    return engine.PolicyInput(**base)


# ── Severity floor ───────────────────────────────────────────────────────────
def test_production_critical_service_floors_at_p1():
    assert engine.enforce_minimum_severity("P3", "production", "payment-service") == "P1"


def test_production_noncritical_service_floors_at_p2():
    assert engine.enforce_minimum_severity("P4", "production", "billing-service") == "P2"


def test_assigned_more_severe_than_floor_is_kept():
    assert engine.enforce_minimum_severity("P1", "production", "billing-service") == "P1"


def test_nonproduction_not_floored():
    assert engine.enforce_minimum_severity("P4", "staging", "payment-service") == "P4"


# ── Governance gates ─────────────────────────────────────────────────────────
def test_high_risk_forces_approval():
    decision = engine.evaluate(_input(risk_level="high"))
    assert decision.approval_required is True
    assert "high_risk_requires_approval" in decision.gates
    assert decision.allowed_autonomous is False


def test_schema_change_requires_dba_approval():
    decision = engine.evaluate(
        _input(recommended_commands=["psql -c 'ALTER TABLE accounts ADD COLUMN x int'"])
    )
    assert "dba_approval_schema_change" in decision.gates
    assert decision.approval_required is True


def test_destructive_unauthorized_is_gated():
    decision = engine.evaluate(
        _input(recommended_commands=["kubectl delete deploy/payment-service"])
    )
    assert "destructive_action_unauthorized" in decision.gates


def test_destructive_authorized_passes_that_gate():
    decision = engine.evaluate(
        _input(
            recommended_commands=["kubectl delete pod/payment-7c9"],
            explicitly_authorized=True,
            risk_level="low",
            autonomy_tier="high",
        )
    )
    assert "destructive_action_unauthorized" not in decision.gates


def test_low_autonomy_requires_human_review():
    decision = engine.evaluate(_input(autonomy_tier="low"))
    assert "low_autonomy_human_review" in decision.gates


def test_clean_low_risk_high_autonomy_allows_autonomous():
    decision = engine.evaluate(
        _input(
            severity="P1",
            risk_level="low",
            autonomy_tier="high",
            recommended_steps=["scale replicas +2"],
            recommended_commands=["kubectl scale deploy/payment-service --replicas=5"],
        )
    )
    assert decision.approval_required is False
    assert decision.allowed_autonomous is True


# ── SLA timers ───────────────────────────────────────────────────────────────
def test_p1_response_breached_after_window():
    created = datetime(2026, 1, 1, 2, 47, tzinfo=UTC)
    assert sla.response_breached("P1", created, created + timedelta(minutes=20)) is True
    assert sla.response_breached("P1", created, created + timedelta(minutes=10)) is False


def test_open_breached_incident_escalates():
    created = datetime(2026, 1, 1, 2, 47, tzinfo=UTC)
    now = created + timedelta(minutes=90)
    assert sla.should_escalate("awaiting_approval", "P2", created, now) is True


def test_resolved_incident_never_escalates():
    created = datetime(2026, 1, 1, 2, 47, tzinfo=UTC)
    now = created + timedelta(hours=5)
    assert sla.should_escalate("resolved", "P1", created, now) is False
