"""Agent Pub/Sub consumer — bounded, back-pressured intake feeding the correlation front.

Reuses the Phase-1 :class:`lib.pubsub.AlertSubscriber` (bounded concurrency = back-pressure,
ack/nack, DLQ). Each event is folded into the :class:`StreamingCorrelator` under a lock and acked
immediately — the slow ADK reasoning must never block the ack. A background flush thread
periodically dispatches incidents idle past the correlation window to ``on_incident``, so a storm's
incident is emitted without needing extra traffic to trigger it. The heavy Pub/Sub
import is lazy so this module imports without the SDK.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from app.config import AgentConfig, load_config
from app.correlation import IncidentContext, StreamingCorrelator
from lib.events import AlertEvent
from lib.logging import get_logger

logger = get_logger("opssentinel.agent.consumer")

IncidentHandler = Callable[[IncidentContext], None]


def run(on_incident: IncidentHandler, config: AgentConfig | None = None) -> None:
    """Start the consumer and block until shutdown, draining open incidents on the way out."""
    config = config or load_config()
    correlator = StreamingCorrelator(window_seconds=config.correlation_window_seconds)
    lock = threading.Lock()
    stop = threading.Event()

    def dispatch_ready() -> None:
        with lock:
            ready = correlator.pop_ready()
        for ctx in ready:
            logger.info(
                "incident ready",
                extra={"correlation_key": ctx.correlation_key, "events": ctx.size},
            )
            on_incident(ctx)

    def handle(event: AlertEvent) -> None:
        # Add + ack fast; the slow reasoning runs in the flush thread, not the message callback.
        with lock:
            ctx = correlator.add(event)
        logger.info(
            "event correlated",
            extra={
                "event_id": event.event_id,
                "correlation_key": event.correlation_key,
                "incident_size": ctx.size,
            },
        )

    def flush_loop() -> None:
        interval = max(1, min(config.correlation_window_seconds, 5))
        while not stop.wait(interval):
            try:
                dispatch_ready()
            except Exception:
                logger.exception("flush dispatch failed")

    threading.Thread(target=flush_loop, daemon=True, name="correlator-flush").start()

    from lib.pubsub import AlertSubscriber  # lazy: needs google-cloud-pubsub

    subscriber = AlertSubscriber(
        handler=handle,
        subscription=config.subscription,
        max_messages=config.max_in_flight,
    )
    logger.info("agent consumer starting", extra={"subscription": config.subscription})
    try:
        subscriber.run_forever()
    finally:
        stop.set()
        with lock:
            drained = correlator.drain()
        for ctx in drained:
            on_incident(ctx)
