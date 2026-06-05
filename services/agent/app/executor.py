"""Deterministic execution path (node 9) — runs on approval, against the mocked infrastructure.

Idempotent: a re-delivered approval cannot double-apply (an already-resolved incident short-
circuits). On approve: update mocked infra, resolve the mocked ServiceNow ticket, write the closure
back to Elastic, log the outcome to Arize, set ``status = resolved``. On reject: ``status =
rejected``. Pure orchestration over injected clients — unit-testable with fakes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.interfaces import EvaluationClient, IncidentStore, KnowledgeClient
from app.mock_infra import MockInfrastructure


@dataclass
class ExecutionResult:
    incident_id: str
    status: str
    successful: bool


def _service_of(incident: dict[str, Any] | None) -> str:
    title = (incident or {}).get("title") or ""
    return title.split(" on ")[-1].strip() if " on " in title else "unknown"


def _closure_summary(incident: dict[str, Any] | None) -> str:
    incident = incident or {}
    steps = (incident.get("recommended_action") or {}).get("steps", [])
    root_cause = incident.get("root_cause") or "incident resolved"
    return f"{incident.get('category', 'Incident')} resolved. Root cause: {root_cause}. " + (
        f"Applied: {'; '.join(steps)}." if steps else ""
    )


def _closure_tags(incident: dict[str, Any] | None) -> list[str]:
    incident = incident or {}
    return [t for t in [incident.get("category"), incident.get("severity"), "resolved"] if t]


def execute_approval(
    decision: dict[str, Any],
    *,
    store: IncidentStore,
    knowledge: KnowledgeClient,
    evaluation: EvaluationClient,
    infra: MockInfrastructure,
) -> ExecutionResult:
    """Apply an approval/rejection from ``opssentinel-actions``."""
    incident_id = decision["incident_id"]
    verdict = decision.get("decision", "approve")
    incident = store.get(incident_id)

    if verdict == "reject":
        store.update_status(incident_id, "rejected", approval_status="rejected")
        return ExecutionResult(incident_id, "rejected", successful=False)

    if incident and incident.get("status") == "resolved":
        return ExecutionResult(incident_id, "resolved", successful=True)  # idempotent re-delivery

    store.update_status(incident_id, "executing", approval_status="approved")
    infra.open_ticket(incident_id)

    service = _service_of(incident)
    commands = ((incident or {}).get("recommended_action") or {}).get("commands", [])
    infra.apply(service, commands)

    summary = _closure_summary(incident)
    knowledge.write_closure_summary(incident_id, summary, _closure_tags(incident))

    trace_id = (incident or {}).get("trace_id") or ""
    successful = True
    evaluation.log_outcome(trace_id, incident_id, approved=True, successful=successful)

    infra.resolve_ticket(incident_id)
    store.update_status(incident_id, "resolved", resolution_summary=summary)
    return ExecutionResult(incident_id, "resolved", successful=successful)
