"""Publish a sample normalized event and read it back — the Queue Layer round-trip smoke test.

Targets the local Pub/Sub emulator (set ``PUBSUB_EMULATOR_HOST=localhost:8085``). Creates the
topic + subscription if absent, publishes via ``lib.pubsub.publish_alert``, then pulls one
message back and verifies it matches. Run via ``make publish-test``.
"""

# ruff: noqa: E402, I001  (sys.path bootstrap must precede first-party imports)

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import os
from datetime import UTC, datetime

from google.api_core.exceptions import AlreadyExists
from google.cloud import pubsub_v1

from lib.events import AlertEvent, AlertSource, SeverityHint, derive_correlation_key
from lib.pubsub import ALERTS_SUB, ALERTS_TOPIC, PROJECT_ID, publish_alert


def _ensure_topology() -> None:
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()
    topic_path = publisher.topic_path(PROJECT_ID, ALERTS_TOPIC)
    sub_path = subscriber.subscription_path(PROJECT_ID, ALERTS_SUB)
    try:
        publisher.create_topic(name=topic_path)
    except AlreadyExists:
        pass
    try:
        subscriber.create_subscription(name=sub_path, topic=topic_path)
    except AlreadyExists:
        pass


def _sample_event() -> AlertEvent:
    return AlertEvent(
        source=AlertSource.simulator,
        received_at=datetime.now(UTC),
        service="payment-service",
        environment="production",
        severity_hint=SeverityHint.P1,
        error_code="ERR_DB_CONN_TIMEOUT",
        http_status=503,
        correlation_key=derive_correlation_key("payment-service", "production", "payments-ns"),
        message="Database connection timeout on primary pool",
        labels={"k8s_namespace": "payments-ns", "pod": "payment-7c9"},
        raw={"original": {"demo": True}},
    )


def main() -> None:
    if not os.environ.get("PUBSUB_EMULATOR_HOST"):
        print("WARNING: PUBSUB_EMULATOR_HOST not set; this targets real Pub/Sub.")
    _ensure_topology()

    event = _sample_event()
    message_id = publish_alert(event)
    print(f"published  event_id={event.event_id} message_id={message_id}")

    subscriber = pubsub_v1.SubscriberClient()
    sub_path = subscriber.subscription_path(PROJECT_ID, ALERTS_SUB)
    response = subscriber.pull(subscription=sub_path, max_messages=1, timeout=10)
    if not response.received_messages:
        raise SystemExit("no message pulled back — check the emulator is running")

    received = response.received_messages[0]
    pulled = AlertEvent.model_validate_json(received.message.data.decode("utf-8"))
    subscriber.acknowledge(subscription=sub_path, ack_ids=[received.ack_id])
    print(f"pulled     event_id={pulled.event_id} service={pulled.service}")

    assert pulled.event_id == event.event_id, "round-trip mismatch"
    print("round-trip OK")


if __name__ == "__main__":
    main()
