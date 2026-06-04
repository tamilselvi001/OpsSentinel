"""Pub/Sub client helpers for the Queue Layer (AP-tuned: zero alert loss + back-pressure).

``publish_alert`` validates against the normalized :class:`~lib.events.AlertEvent` model
*before* a message ever reaches the topic. :class:`AlertSubscriber` consumes at a controlled,
sustainable rate — bounded concurrency provides back-pressure so an alert storm cannot
overwhelm downstream processing — with ack on success, nack on failure (Pub/Sub redelivers and,
after the topic's configured max attempts, forwards to the dead-letter topic), and graceful
shutdown on SIGTERM (the signal Cloud Run sends on scale-in).
"""

from __future__ import annotations

import os
import signal
import threading
from collections.abc import Callable
from concurrent.futures import TimeoutError as FuturesTimeoutError

from google.cloud import pubsub_v1

from lib.events import AlertEvent
from lib.logging import get_logger

logger = get_logger("opssentinel.pubsub")

PROJECT_ID = (
    os.environ.get("PUBSUB_PROJECT_ID")
    or os.environ.get("GOOGLE_CLOUD_PROJECT")
    or "opssentinel-mvp"
)
ALERTS_TOPIC = os.environ.get("OPSSENTINEL_ALERTS_TOPIC", "opssentinel-alerts")
ALERTS_SUB = os.environ.get("OPSSENTINEL_ALERTS_SUB", "opssentinel-alerts-sub")


def publish_alert(event: AlertEvent | dict, topic: str = ALERTS_TOPIC) -> str:
    """Validate ``event`` against the normalized model, then publish it. Returns the message id.

    ``correlation_key``, ``source`` and ``event_id`` are also attached as message attributes so
    downstream consumers and the DLQ can be inspected without decoding the payload.
    """
    model = event if isinstance(event, AlertEvent) else AlertEvent.model_validate(event)
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, topic)
    future = publisher.publish(
        topic_path,
        model.model_dump_json().encode("utf-8"),
        correlation_key=model.correlation_key,
        source=str(model.source),
        event_id=model.event_id,
    )
    message_id = future.result(timeout=30)
    logger.info(
        "published alert",
        extra={"event_id": model.event_id, "message_id": message_id, "topic": topic},
    )
    return message_id


class AlertSubscriber:
    """Bounded, back-pressured streaming pull subscriber with graceful shutdown.

    ``handler(event)`` is called once per message. Returning normally acks the message;
    raising nacks it (Pub/Sub will redeliver, then dead-letter after the configured attempts).
    ``max_messages`` caps in-flight messages — the controlled, sustainable consume rate.
    """

    def __init__(
        self,
        handler: Callable[[AlertEvent], None],
        subscription: str = ALERTS_SUB,
        max_messages: int = 8,
        project_id: str = PROJECT_ID,
    ) -> None:
        self._handler = handler
        self._subscriber = pubsub_v1.SubscriberClient()
        self._sub_path = self._subscriber.subscription_path(project_id, subscription)
        self._flow_control = pubsub_v1.types.FlowControl(max_messages=max_messages)
        self._stop = threading.Event()

    def _on_message(self, message: pubsub_v1.subscriber.message.Message) -> None:
        try:
            event = AlertEvent.model_validate_json(message.data.decode("utf-8"))
            self._handler(event)
            message.ack()
        except Exception:
            logger.exception("handler failed; nacking for redelivery / dead-letter")
            message.nack()

    def run_forever(self) -> None:
        """Subscribe and block until SIGTERM/SIGINT, then drain and stop cleanly."""
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(sig, lambda *_: self._stop.set())
            except ValueError:
                pass  # signals can only be set from the main thread

        future = self._subscriber.subscribe(
            self._sub_path, callback=self._on_message, flow_control=self._flow_control
        )
        logger.info("subscriber started", extra={"subscription": self._sub_path})
        try:
            while not self._stop.is_set():
                try:
                    future.result(timeout=1)
                except FuturesTimeoutError:
                    continue
        finally:
            future.cancel()
            future.result(timeout=10)
            logger.info("subscriber stopped")
