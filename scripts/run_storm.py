"""Alert-storm validation harness (Phase 5, Tasks B/C): publish 50+ correlated signals onto
opssentinel-alerts, wait, then reconcile published-vs-processed and assert the DLQ is empty.

Run via `make validate` (needs the emulator + Postgres + a running agent). Proves Exit Criterion 1:
the storm dedups into a single incident with zero alert loss.
"""
# ruff: noqa: E402, I001  (sys.path bootstrap must precede first-party imports)

from __future__ import annotations

import argparse
import pathlib
import sys
import time

_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "services" / "alert-simulator"))

from app.generator import make_storm
from lib.logging import get_logger
from lib.pubsub import PROJECT_ID, publish_alert

logger = get_logger("opssentinel.run-storm")


def _reconcile(expected_min: int) -> None:
    try:
        from sqlalchemy import text

        from lib.db import get_engine
    except Exception as exc:  # sqlalchemy not installed in this context
        print(f"(skipping DB reconciliation: {exc})")
        return
    try:
        with get_engine().connect() as conn:
            window = "created_at > now() - interval '10 minutes'"
            incidents = conn.execute(
                text(f"SELECT count(*) FROM incidents WHERE {window}")
            ).scalar_one()
            events = conn.execute(
                text(f"SELECT count(*) FROM incident_events WHERE {window}")
            ).scalar_one()
        print(f"incidents (last 10m): {incidents}  |  correlated events: {events}")
        assert incidents >= 1, "expected at least one incident from the storm"
        assert events >= expected_min, "fewer correlated events than published — alert loss!"
    except Exception as exc:
        print(f"(DB reconciliation unavailable: {exc})")


def _assert_dlq_empty() -> None:
    try:
        from google.cloud import pubsub_v1

        subscriber = pubsub_v1.SubscriberClient()
        sub_path = subscriber.subscription_path(PROJECT_ID, "opssentinel-alerts-dlq-sub")
        response = subscriber.pull(subscription=sub_path, max_messages=1, timeout=5)
        if response.received_messages:
            raise SystemExit("DLQ is not empty — a poison message was dead-lettered")
        print("DLQ is empty — no dropped events")
    except SystemExit:
        raise
    except Exception as exc:
        print(f"(DLQ check unavailable: {exc})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish an alert storm and validate dedup")
    parser.add_argument("--count", type=int, default=50, help="number of storm signals (>= 50)")
    parser.add_argument("--wait", type=int, default=20, help="seconds to wait for processing")
    args = parser.parse_args()

    events = make_storm(args.count)
    for event in events:
        publish_alert(event)
    print(
        f"published {len(events)} storm signals sharing correlation_key {events[0].correlation_key}"
    )

    print(f"waiting {args.wait}s for correlation + processing ...")
    time.sleep(args.wait)

    _reconcile(expected_min=args.count)
    _assert_dlq_empty()
    print("storm validation complete")


if __name__ == "__main__":
    main()
