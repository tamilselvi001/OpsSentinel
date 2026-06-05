"""The ADK 2.0 graph orchestrator (nodes 3–8) with deterministic edges + conditional branches.

Deterministic nodes (correlate, policy gate, brief) stay off the LLM; Gemini is invoked only for
classification (node 3) and the RAG-bound recommendation (node 5). A tracing/eval hiccup never
crashes incident handling — node 6 degrades to a safe lower autonomy tier. The reasoning + MCP +
store + tracer are injected (see :mod:`app.interfaces`), so this orchestration is unit-testable.

Node 1 (ingest/parse) and node 2 (correlate) happen upstream in the consumer; node 9 (execute on
approval) is the separate :mod:`app.executor` path. ``run_graph`` covers nodes 3–8 and ends at
``awaiting_approval`` (the MVP is human-in-the-loop: every remediation awaits approval).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from policy import engine as policy_engine

from app.autonomy import AutonomyDecision, decide_autonomy, degraded_fallback
from app.brief import build_execution_brief
from app.correlation import IncidentContext
from app.interfaces import (
    EvaluationClient,
    IncidentStore,
    KnowledgeClient,
    Notifier,
    Reasoner,
    Tracer,
)
from app.models import Classification
from lib.logging import get_logger

logger = get_logger("opssentinel.agent.graph")

AWAITING_APPROVAL = "awaiting_approval"


@dataclass
class GraphDeps:
    reasoner: Reasoner
    knowledge: KnowledgeClient
    evaluation: EvaluationClient
    store: IncidentStore
    tracer: Tracer
    log_fetch_minutes: int = 30
    runbook_top_k: int = 3
    notifier: Notifier | None = None  # Phase-5 Slack delivery (optional; no-op when unset)


@dataclass
class GraphResult:
    incident_id: str
    status: str
    brief: dict
    autonomy_tier: str
    risk_level: str
    trace_id: str
    path: list[str] = field(default_factory=list)


def _retrieval_query(context: IncidentContext, classification: Classification) -> str:
    rep = context.representative
    return " ".join(part for part in (classification.category, rep.error_code, rep.message) if part)


def _bind_to_retrieved(recommendation, runbooks: list[dict]) -> object:
    """RAG grounding: the recommendation must reference a retrieved runbook, not invent one."""
    if runbooks:
        ids = {rb.get("id") for rb in runbooks}
        if recommendation.based_on_runbook_id not in ids:
            recommendation.based_on_runbook_id = runbooks[0].get("id")
    return recommendation


def _self_evaluate(
    evaluation: EvaluationClient, classification: Classification
) -> AutonomyDecision:
    """Node 6: query Arize; degrade to a safe low tier if the MCP server is unreachable."""
    try:
        is_novel = evaluation.is_novel_category(classification.category)
        accuracy = evaluation.get_category_accuracy(classification.category)
        calibration = evaluation.get_calibration(classification.category)
    except Exception as exc:  # a tracing/eval hiccup must never crash incident handling
        logger.warning("self-evaluation unavailable; degrading autonomy", extra={"error": str(exc)})
        return degraded_fallback(str(exc))
    return decide_autonomy(
        accuracy=accuracy,
        calibration_error=calibration,
        is_novel=is_novel,
        intent_confidence=classification.confidence,
    )


def run_graph(
    context: IncidentContext, deps: GraphDeps, incident_id: str | None = None
) -> GraphResult:
    """Drive one correlated incident through nodes 3–8 to ``awaiting_approval``."""
    incident_id = incident_id or str(uuid4())
    path: list[str] = []

    with deps.tracer.run_span("incident") as trace_id:
        # Node 3 — Reason (Gemini): classify type/severity/team, root cause, calibrated confidence.
        path.append("reason")
        classification = deps.reasoner.classify(context)

        # Node 4 — Retrieve context (Elastic MCP): last 30m logs + closest historical runbooks.
        path.append("retrieve")
        logs = deps.knowledge.fetch_recent_logs(context.service, deps.log_fetch_minutes)
        runbooks = deps.knowledge.search_runbooks(
            _retrieval_query(context, classification), deps.runbook_top_k
        )

        # Node 5 — Synthesize recommendation (Gemini, RAG-bound to the retrieved runbooks).
        path.append("synthesize")
        recommendation = deps.reasoner.synthesize(context, classification, logs, runbooks)
        recommendation = _bind_to_retrieved(recommendation, runbooks)

        # Node 6 — Self-evaluate / adaptive autonomy (Arize MCP), degrading safely.
        path.append("self_evaluate")
        autonomy = _self_evaluate(deps.evaluation, classification)

        # Node 7 — Policy gate (deterministic; the LLM cannot bypass it).
        path.append("policy")
        policy_decision = policy_engine.evaluate(
            policy_engine.PolicyInput(
                severity=classification.severity,
                environment=context.environment,
                service=context.service,
                risk_level=recommendation.risk_level,
                autonomy_tier=autonomy.tier,
                recommended_steps=recommendation.steps,
                recommended_commands=recommendation.commands,
            )
        )

        # Conditional branch: low-confidence/novel OR a fired policy gate → human-review branch.
        path.append(
            "human_review"
            if (autonomy.requires_human or policy_decision.approval_required)
            else "autonomous_eligible"
        )

        # Node 8 — Brief + persist as awaiting_approval (+ audit, inside the store).
        path.append("brief")
        brief = build_execution_brief(
            incident_id=incident_id,
            context=context,
            classification=classification,
            recommendation=recommendation,
            historical_matches=runbooks,
            autonomy=autonomy,
            policy=policy_decision,
        )
        deps.store.persist(brief, AWAITING_APPROVAL, trace_id)

        # Node 8 (Phase-5 wiring) — deliver the brief to the human via Slack. A delivery failure
        # must not crash incident handling; the brief is already persisted for the dashboard.
        if deps.notifier is not None:
            try:
                deps.notifier.notify(incident_id)
            except Exception as exc:
                logger.warning(
                    "slack notify failed", extra={"incident_id": incident_id, "error": str(exc)}
                )

    logger.info(
        "incident briefed",
        extra={
            "incident_id": incident_id,
            "severity": policy_decision.final_severity,
            "autonomy_tier": autonomy.tier,
            "risk_level": recommendation.risk_level,
            "approval_required": policy_decision.approval_required,
            "trace_id": trace_id,
        },
    )
    return GraphResult(
        incident_id=incident_id,
        status=AWAITING_APPROVAL,
        brief=brief,
        autonomy_tier=autonomy.tier,
        risk_level=recommendation.risk_level,
        trace_id=trace_id,
        path=path,
    )
