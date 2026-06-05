"""Publish an approval/rejection to opssentinel-actions — the Phase-5 Slack approval shim.

Usage:
    python scripts/approve.py --incident <id>            # approve
    python scripts/approve.py --incident <id> --reject   # reject
Via the harness: `make approve INCIDENT=<id>` / `make reject INCIDENT=<id>`.
"""
# ruff: noqa: E402, I001  (sys.path bootstrap must precede first-party imports)

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from google.api_core.exceptions import AlreadyExists
from google.cloud import pubsub_v1

PROJECT_ID = (
    os.environ.get("PUBSUB_PROJECT_ID")
    or os.environ.get("GOOGLE_CLOUD_PROJECT")
    or "opssentinel-mvp"
)
ACTIONS_TOPIC = os.environ.get("OPSSENTINEL_ACTIONS_TOPIC", "opssentinel-actions")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish an approval decision to the actions topic"
    )
    parser.add_argument("--incident", required=True, help="incident_id to approve/reject")
    parser.add_argument("--reject", action="store_true", help="reject instead of approve")
    parser.add_argument("--approver", default="cli-shim", help="approver identity")
    args = parser.parse_args()

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, ACTIONS_TOPIC)
    try:  # ensure the topic exists on the emulator
        publisher.create_topic(name=topic_path)
    except AlreadyExists:
        pass

    decision = {
        "incident_id": args.incident,
        "decision": "reject" if args.reject else "approve",
        "approver": args.approver,
    }
    future = publisher.publish(topic_path, json.dumps(decision).encode("utf-8"))
    future.result(timeout=30)
    print(f"published {decision['decision']} for incident {args.incident}")


if __name__ == "__main__":
    main()
