"""Tests for the deterministic execution path on approval (Phase 3, Task 6.9)."""

import pathlib
import sys

_AGENT = pathlib.Path(__file__).resolve().parent.parent / "services" / "agent"
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from app.executor import execute_approval  # noqa: E402
from app.mock_infra import MockInfrastructure  # noqa: E402


class FakeStore:
    def __init__(self, incidents):
        self.incidents = incidents
        self.updates = []

    def get(self, incident_id):
        return self.incidents.get(incident_id)

    def update_status(self, incident_id, status, **fields):
        self.incidents.setdefault(incident_id, {})["status"] = status
        self.updates.append((incident_id, status, fields))

    def persist(self, brief, status, trace_id):  # unused here
        return brief["incident_id"]


class FakeKnowledge:
    def __init__(self):
        self.closures = []

    def fetch_recent_logs(self, service, minutes=30):
        return []

    def search_runbooks(self, query, top_k=3):
        return []

    def write_closure_summary(self, incident_id, summary, tags):
        self.closures.append((incident_id, summary, tags))
        return {"indexed_id": incident_id}


class FakeEvaluation:
    def __init__(self):
        self.outcomes = []

    def get_category_accuracy(self, category, window=30):
        return 0.9

    def get_calibration(self, category):
        return 0.0

    def is_novel_category(self, category):
        return False

    def log_outcome(self, trace_id, incident_id, approved, successful):
        self.outcomes.append((trace_id, incident_id, approved, successful))
        return {"outcome_id": "o1"}


def _incident():
    return {
        "status": "awaiting_approval",
        "category": "Database Connection Pool",
        "severity": "P1",
        "title": "[P1] Database Connection Pool on payment-service",
        "root_cause": "pool exhausted after deploy",
        "recommended_action": {
            "steps": ["restart the connection pool"],
            "commands": ["kubectl rollout restart deploy/payment-service"],
        },
        "trace_id": "trace-1",
    }


def test_approval_runs_full_execution_path():
    store = FakeStore({"inc-1": _incident()})
    knowledge, evaluation, infra = FakeKnowledge(), FakeEvaluation(), MockInfrastructure()

    result = execute_approval(
        {"incident_id": "inc-1", "decision": "approve"},
        store=store,
        knowledge=knowledge,
        evaluation=evaluation,
        infra=infra,
    )

    assert result.status == "resolved"
    assert result.successful is True
    assert store.incidents["inc-1"]["status"] == "resolved"
    assert len(knowledge.closures) == 1  # closure written to Elastic
    assert evaluation.outcomes == [("trace-1", "inc-1", True, True)]  # outcome logged to Arize
    assert infra.ticket_status("inc-1") == "resolved"
    assert infra.pool_restarts["payment-service"] == 1


def test_rejection_sets_status_rejected_without_executing():
    store = FakeStore({"inc-1": _incident()})
    knowledge, evaluation, infra = FakeKnowledge(), FakeEvaluation(), MockInfrastructure()

    result = execute_approval(
        {"incident_id": "inc-1", "decision": "reject"},
        store=store,
        knowledge=knowledge,
        evaluation=evaluation,
        infra=infra,
    )

    assert result.status == "rejected"
    assert knowledge.closures == []
    assert evaluation.outcomes == []


def test_reapproval_is_idempotent():
    incident = _incident()
    incident["status"] = "resolved"
    store = FakeStore({"inc-1": incident})
    knowledge, evaluation, infra = FakeKnowledge(), FakeEvaluation(), MockInfrastructure()

    result = execute_approval(
        {"incident_id": "inc-1", "decision": "approve"},
        store=store,
        knowledge=knowledge,
        evaluation=evaluation,
        infra=infra,
    )

    assert result.status == "resolved"
    assert knowledge.closures == []  # already resolved -> no double execution
