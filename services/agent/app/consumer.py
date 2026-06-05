"""Agent Pub/Sub consumer — bounded, back-pressured intake feeding the correlation front.

Reuses the Phase-1 :class:`lib.pubsub.AlertSubscriber` (bounded concurrency = back-pressure,
ack/nack, DLQ). Each event is folded into the :class:`StreamingCorrelator`; incidents that go
idle past the correlation window are dispatched to ``on_incident`` (the reasoning graph, wired in
a later checkpoint). The heavy Pub/Sub import is lazy so this module imports without the SDK.
"""

from __future__ import annotations

from collections.abc import Callable

from app.config import AgentConfig, load_config
from app.correlation import IncidentContext, StreamingCorrelator
from lib.events import AlertEvent
from lib.logging import get_logger

logger = get_logger("opssentinel.agent.consumer")

IncidentHandler = Callable[[IncidentContext], None]


def make_event_handler(
    correlator: StreamingCorrelator, on_incident: IncidentHandler
) -> Callable[[AlertEvent], None]:
    """Build the per-event handler: correlate, then dispatch any incidents that are ready."""

    def handle(event: AlertEvent) -> None:
        ctx = correlator.add(event)
        logger.info(
            "event correlated",
            extra={
                "event_id": event.event_id,
                "correlation_key": event.correlation_key,
                "incident_size": ctx.size,
            },
        )
        for ready in correlator.pop_ready():
            logger.info(
                "incident ready",
                extra={"correlation_key": ready.correlation_key, "events": ready.size},
            )
            on_incident(ready)

    return handle


def run(on_incident: IncidentHandler, config: AgentConfig | None = None) -> None:
    """Start the consumer and block until shutdown, draining open incidents on the way out."""
    config = config or load_config()
    correlator = StreamingCorrelator(window_seconds=config.correlation_window_seconds)

    from lib.pubsub import AlertSubscriber  # lazy: needs google-cloud-pubsub

    subscriber = AlertSubscriber(
        handler=make_event_handler(correlator, on_incident),
        subscription=config.subscription,
        max_messages=config.max_in_flight,
    )
    logger.info("agent consumer starting", extra={"subscription": config.subscription})
    try:
        subscriber.run_forever()
    finally:
        for ctx in correlator.drain():
            on_incident(ctx)
