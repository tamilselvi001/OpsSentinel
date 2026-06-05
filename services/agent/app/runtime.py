"""Compose the concrete graph dependencies + apply OpenInference tracing (Tasks 6.10/6.11 runtime).

Only the running agent imports this (it pulls in Gemini / MCP / DB / OTel); the unit tests build
``GraphDeps`` from fakes instead.
"""

from __future__ import annotations

import contextlib
import json
import urllib.request
from collections.abc import Iterator

from app.config import AgentConfig, load_config
from app.graph import GraphDeps
from app.incident_store import DbIncidentStore
from app.mcp_clients import ArizeMcpEvaluationClient, ElasticMcpKnowledgeClient
from app.reasoning import GeminiReasoner
from lib.logging import get_logger
from lib.observability import configure_tracing

logger = get_logger("opssentinel.agent.runtime")


class SlackNotifier:
    """Concrete Notifier — POSTs ``{incident_id}`` to the slack-bot ``/notify`` endpoint."""

    def __init__(self, notify_url: str) -> None:
        self._url = notify_url

    def notify(self, incident_id: str) -> None:
        data = json.dumps({"incident_id": incident_id}).encode("utf-8")
        request = urllib.request.Request(
            self._url, data=data, headers={"content-type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(request, timeout=10).close()  # noqa: S310 (internal URL)


class OtelTracer:
    """Wraps a run in an OpenTelemetry span and yields its trace id (persisted on the incident)."""

    @contextlib.contextmanager
    def run_span(self, name: str) -> Iterator[str]:
        from opentelemetry import trace

        tracer = trace.get_tracer("opssentinel.agent")
        with tracer.start_as_current_span(name) as span:
            yield format(span.get_span_context().trace_id, "032x")


def build_deps(config: AgentConfig | None = None) -> GraphDeps:
    config = config or load_config()
    return GraphDeps(
        reasoner=GeminiReasoner(model=config.gemini_model),
        knowledge=ElasticMcpKnowledgeClient(config.mcp_elastic_url),
        evaluation=ArizeMcpEvaluationClient(config.mcp_arize_url),
        store=DbIncidentStore(),
        tracer=OtelTracer(),
        notifier=SlackNotifier(config.slack_notify_url),
    )


def enable_tracing() -> None:
    """Apply the Phase-2 OpenInference helper; never fatal if the collector is unreachable."""
    try:
        configure_tracing(service_name="opssentinel-agent")
        logger.info("openinference tracing enabled")
    except Exception as exc:
        logger.warning("tracing not configured; continuing", extra={"error": str(exc)})
