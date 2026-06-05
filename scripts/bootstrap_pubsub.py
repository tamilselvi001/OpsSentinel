"""Create the Pub/Sub topology (topics + subscriptions) on the local emulator. Idempotent.

Local harness only — in the cloud, infra/pubsub (Terraform) provisions these. Run with
PUBSUB_EMULATOR_HOST set (e.g. localhost:8085).
"""
# ruff: noqa: E402, I001  (sys.path bootstrap must precede first-party imports)

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from google.api_core.exceptions import AlreadyExists
from google.cloud import pubsub_v1

from lib.pubsub import PROJECT_ID

TOPICS = ["opssentinel-alerts", "opssentinel-alerts-dlq", "opssentinel-actions"]
SUBSCRIPTIONS = {
    "opssentinel-alerts-sub": "opssentinel-alerts",
    "opssentinel-alerts-dlq-sub": "opssentinel-alerts-dlq",
    "opssentinel-actions-agent-sub": "opssentinel-actions",
}


def main() -> None:
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()

    for topic in TOPICS:
        topic_path = publisher.topic_path(PROJECT_ID, topic)
        try:
            publisher.create_topic(name=topic_path)
            print(f"topic created: {topic}")
        except AlreadyExists:
            print(f"topic exists: {topic}")

    for sub, topic in SUBSCRIPTIONS.items():
        sub_path = subscriber.subscription_path(PROJECT_ID, sub)
        topic_path = publisher.topic_path(PROJECT_ID, topic)
        try:
            subscriber.create_subscription(name=sub_path, topic=topic_path)
            print(f"subscription created: {sub} -> {topic}")
        except AlreadyExists:
            print(f"subscription exists: {sub}")


if __name__ == "__main__":
    main()
