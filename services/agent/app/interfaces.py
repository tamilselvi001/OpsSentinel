"""Dependency interfaces (Protocols) the graph orchestrates against.

The graph depends on these abstractions, not concretions — so the deterministic orchestration is
unit-testable with fakes, while the real run wires the Gemini reasoner, the MCP SSE clients, the
Postgres-backed store, and the OpenTelemetry tracer. (Dependency inversion.)
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Protocol

from app.models import Classification, Recommendation


class KnowledgeClient(Protocol):
    """Elastic MCP tools (semantic memory + logs + closure write)."""

    def fetch_recent_logs(self, service: str, minutes: int = 30) -> list[dict[str, Any]]: ...
    def search_runbooks(self, query: str, top_k: int = 3) -> list[dict[str, Any]]: ...
    def write_closure_summary(
        self, incident_id: str, summary: str, tags: list[str]
    ) -> dict[str, Any]: ...


class EvaluationClient(Protocol):
    """Arize Phoenix MCP tools (self-evaluation). May raise — the graph degrades safely."""

    def get_category_accuracy(self, category: str, window: int = 30) -> float: ...
    def get_calibration(self, category: str) -> float: ...
    def is_novel_category(self, category: str) -> bool: ...
    def log_outcome(
        self, trace_id: str, incident_id: str, approved: bool, successful: bool
    ) -> dict[str, Any]: ...


class Reasoner(Protocol):
    """Gemini reasoning nodes (the only LLM steps)."""

    def classify(self, context: Any) -> Classification: ...
    def synthesize(
        self,
        context: Any,
        classification: Classification,
        logs: list[dict[str, Any]],
        runbooks: list[dict[str, Any]],
    ) -> Recommendation: ...


class IncidentStore(Protocol):
    """Persistence for the incident lifecycle + audit trail."""

    def persist(self, brief: dict[str, Any], status: str, trace_id: str | None) -> str: ...
    def update_status(self, incident_id: str, status: str, **fields: Any) -> None: ...
    def get(self, incident_id: str) -> dict[str, Any] | None: ...


class Tracer(Protocol):
    """Wraps a run in an OpenInference span; the context manager yields the trace id."""

    def run_span(self, name: str) -> AbstractContextManager[str]: ...


class Notifier(Protocol):
    """Delivers an awaiting-approval incident for human review (Phase-5 Slack /notify)."""

    def notify(self, incident_id: str) -> None: ...
