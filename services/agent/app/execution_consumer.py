"""Approval-execution consumer (node 9 driver) — consumes ``opssentinel-actions`` and executes.

A separate consumer from the alert intake: it pulls approval/rejection messages (published by the
Phase-5 Slack bot, or by the ``make approve`` test shim) and runs the deterministic execution path.
The mocked infrastructure is process-local. Heavy imports are deferred so this module loads cheaply.
"""

from __future__ import annotations

import json
import os

from app.config import load_config
from app.executor import execute_approval
from app.incident_store import DbIncidentStore
from app.mcp_clients import ArizeMcpEvaluationClient, ElasticMcpKnowledgeClient
from app.mock_infra import MockInfrastructure
from lib.logging import get_logger

logger = get_logger("opssentinel.agent.execution")

PROJECT_ID = (
    os.environ.get("PUBSUB_PROJECT_ID")
    or os.environ.get("GOOGLE_CLOUD_PROJECT")
    or "opssentinel-mvp"
)


def run() -> None:
    from google.api_core.exceptions import AlreadyExists
    from google.cloud import pubsub_v1

    config = load_config()
    store = DbIncidentStore()
    knowledge = ElasticMcpKnowledgeClient(config.mcp_elastic_url)
    evaluation = ArizeMcpEvaluationClient(config.mcp_arize_url)
    infra = MockInfrastructure()

    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()
    topic_path = publisher.topic_path(PROJECT_ID, config.actions_topic)
    sub_path = subscriber.subscription_path(PROJECT_ID, f"{config.actions_topic}-agent-sub")
    try:  # ensure the subscription exists (idempotent; harmless on the emulator)
        subscriber.create_subscription(name=sub_path, topic=topic_path)
    except AlreadyExists:
        pass

    def callback(message: pubsub_v1.subscriber.message.Message) -> None:
        try:
            decision = json.loads(message.data.decode("utf-8"))
            result = execute_approval(
                decision, store=store, knowledge=knowledge, evaluation=evaluation, infra=infra
            )
            logger.info(
                "approval executed",
                extra={"incident_id": result.incident_id, "status": result.status},
            )
            message.ack()
        except Exception:
            logger.exception("approval execution failed; nacking")
            message.nack()

    logger.info("execution consumer started", extra={"subscription": sub_path})
    future = subscriber.subscribe(sub_path, callback=callback)
    future.result()


if __name__ == "__main__":
    run()
