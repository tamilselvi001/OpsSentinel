"""End-to-end graph orchestration with injected fakes (Phase 3, Tasks 6.3/6.5/6.6/6.7/6.10/6.12).

Drives one correlated incident through nodes 3-8 without a live Gemini / MCP / DB, asserting it
reaches awaiting_approval with an autonomy tier, a risk level, a retrieved runbook, and a trace id;
plus the high-risk and degraded/novel branches.
"""

import contextlib
import pathlib
import sys
from datetime import UTC, datetime

from lib.events import AlertEvent, derive_correlation_key

_AGENT = pathlib.Path(__file__).resolve().parent.parent / "services" / "agent"
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from app.correlation import IncidentContext  # noqa: E402
from app.graph import GraphDeps, run_graph  # noqa: E402
from app.models import Classification, Recommendation  # noqa: E402

_RUNBOOKS = [
    {
        "id": "rb-db-conn-limit",
        "title": "Database Connection Limit Reached",
        "root_cause": "pool exhausted",
        "resolution_steps": "restart pool",
        "similarity_score": 0.91,
    }
]


class FakeReasoner:
    def __init__(self, classification, recommendation):
        self._c, self._r = classification, recommendation

    def classify(self, context):
        return self._c

    def synthesize(self, context, classification, logs, runbooks):
        return self._r


class FakeKnowledge:
    def __init__(self, runbooks):
        self._runbooks = runbooks

    def fetch_recent_logs(self, service, minutes=30):
        return [{"service": service, "message": "timeout"}]

    def search_runbooks(self, query, top_k=3):
        return self._runbooks

    def write_closure_summary(self, incident_id, summary, tags):
        return {}


class FakeEvaluation:
    def __init__(self, accuracy=0.91, calibration=0.01, novel=False, fail=False):
        self._acc, self._cal, self._novel, self._fail = accuracy, calibration, novel, fail

    def get_category_accuracy(self, category, window=30):
        if self._fail:
            raise RuntimeError("arize unreachable")
        return self._acc

    def get_calibration(self, category):
        return self._cal

    def is_novel_category(self, category):
        if self._fail:
            raise RuntimeError("arize unreachable")
        return self._novel

    def log_outcome(self, *a, **k):
        return {}


class FakeStore:
    def __init__(self):
        self.persisted = []

    def persist(self, brief, status, trace_id):
        self.persisted.append((brief, status, trace_id))
        return brief["incident_id"]

    def update_status(self, *a, **k):
        pass

    def get(self, incident_id):
        return None


class FakeTracer:
    @contextlib.contextmanager
    def run_span(self, name):
        yield "trace-test-123"


def _context():
    key = derive_correlation_key("payment-service", "production", "payments-ns")
    events = [
        AlertEvent(
            source="elastic",
            received_at=datetime(2026, 1, 1, 2, 47, i % 60, tzinfo=UTC),
            service="payment-service",
            environment="production",
            error_code="ERR_DB_CONN_TIMEOUT",
            correlation_key=key,
            message="DB connection timeout",
        )
        for i in range(50)
    ]
    return IncidentContext("k", "payment-service", "production", events)


def _deps(reasoner, evaluation):
    return GraphDeps(
        reasoner=reasoner,
        knowledge=FakeKnowledge(_RUNBOOKS),
        evaluation=evaluation,
        store=FakeStore(),
        tracer=FakeTracer(),
    )


def _classification(confidence=0.88):
    return Classification(
        category="Database Connection Pool",
        severity="P2",
        remediation_team="sre-oncall",
        confidence=confidence,
        root_cause="connection pool exhausted after deploy",
    )


def _recommendation(risk="medium", runbook_id="rb-db-conn-limit"):
    return Recommendation(
        summary="restart pool and raise limit",
        steps=["restart the connection pool"],
        commands=["kubectl rollout restart deploy/payment-service"],
        risk_level=risk,
        based_on_runbook_id=runbook_id,
    )


def test_db_pool_incident_reaches_awaiting_approval_high_autonomy():
    deps = _deps(FakeReasoner(_classification(), _recommendation()), FakeEvaluation())
    result = run_graph(_context(), deps, incident_id="inc-1")

    assert result.status == "awaiting_approval"
    assert result.autonomy_tier == "high"  # 91% + well-calibrated
    assert result.risk_level == "medium"
    assert result.trace_id == "trace-test-123"
    assert result.brief["historical_match"]["id"] == "rb-db-conn-limit"  # RAG-grounded
    assert result.brief["severity"] == "P1"  # policy floor: prod + payment -> P1
    assert "autonomous_eligible" in result.path
    assert result.path[:5] == ["reason", "retrieve", "synthesize", "self_evaluate", "policy"]


def test_high_risk_forces_human_review_branch():
    deps = _deps(FakeReasoner(_classification(), _recommendation(risk="high")), FakeEvaluation())
    result = run_graph(_context(), deps)
    assert result.brief["approval_required"] is True
    assert "human_review" in result.path
    assert "high_risk_requires_approval" in result.brief["policy_gates"]


def test_degraded_evaluation_falls_back_to_low_autonomy():
    deps = _deps(FakeReasoner(_classification(), _recommendation()), FakeEvaluation(fail=True))
    result = run_graph(_context(), deps)
    assert result.autonomy_tier == "low"  # safe degradation when Arize is unreachable
    assert "human_review" in result.path


def test_novel_category_lowers_autonomy():
    deps = _deps(FakeReasoner(_classification(), _recommendation()), FakeEvaluation(novel=True))
    result = run_graph(_context(), deps)
    assert result.autonomy_tier == "low"


def test_recommendation_is_rebound_to_a_retrieved_runbook():
    reasoner = FakeReasoner(_classification(), _recommendation(runbook_id="hallucinated-id"))
    run_graph(_context(), _deps(reasoner, FakeEvaluation()))
    # graph rebinds an out-of-corpus runbook id to a retrieved one (anti-hallucination)
    assert reasoner._r.based_on_runbook_id == "rb-db-conn-limit"
