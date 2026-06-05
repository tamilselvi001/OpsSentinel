"""OpenInference instrumentation: export ADK spans to Arize Phoenix (applied by the Phase-3 agent).

Phoenix is an *active* component of the cognitive loop, not a passive dashboard: with this
applied, every tool call, context retrieval, and generated token becomes a discrete trace span in
Phoenix, feeding the LLM-as-a-judge evaluations and the adaptive-autonomy loop.

The heavy OpenTelemetry / OpenInference imports are deferred into :func:`configure_tracing` so this
module imports cheaply (the Phase-2 acceptance is that the helper "imports cleanly"); only the agent
process, which has those deps installed, calls it.
"""

from __future__ import annotations

import os

from lib.logging import get_logger
from lib.secrets import get_secret

logger = get_logger("opssentinel.observability")

DEFAULT_COLLECTOR = "http://localhost:6006"


def configure_tracing(service_name: str = "opssentinel-agent"):
    """Wire ADK → OpenInference → Phoenix. Call once at agent startup. Returns the TracerProvider.

    Reads ``phoenix-collector-endpoint`` and ``phoenix-api-key`` via the Phase-1 secrets accessor.
    """
    endpoint = get_secret(
        "phoenix-collector-endpoint",
        default=os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", DEFAULT_COLLECTOR),
    )
    api_key = get_secret("phoenix-api-key", default="")

    # Lazy imports — only the agent image carries these.
    from openinference.instrumentation.google_adk import GoogleADKInstrumentor
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    headers = {"api_key": api_key} if api_key else {}
    exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces", headers=headers)
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Set the GLOBAL provider so manually-created spans (the agent's "incident" span) also record a
    # real trace id — not just the ADK auto-instrumented spans.
    trace.set_tracer_provider(provider)
    GoogleADKInstrumentor().instrument(tracer_provider=provider)
    logger.info("tracing configured", extra={"collector": endpoint, "service_name": service_name})
    return provider
