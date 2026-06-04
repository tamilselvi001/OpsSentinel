"""Alert Simulator CLI — publish mock signals to opssentinel-alerts via lib.pubsub.

Usage:
    python -m app.main signal            # one realistic incident
    python -m app.main storm --count 50  # 50+ correlated signals (Phase-5 dedup input)
"""
# ruff: noqa: E402, I001  (sys.path bootstrap must precede first-party imports)

from __future__ import annotations

import argparse
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent.parent))  # dir containing the app/ package
for _parent in _HERE.parents:  # repo root (so lib/ resolves locally)
    if (_parent / "pyproject.toml").exists():
        sys.path.insert(0, str(_parent))
        break

from app.generator import make_incident_signal, make_storm
from lib.logging import get_logger
from lib.pubsub import publish_alert

logger = get_logger("opssentinel.alert-simulator")


def main() -> None:
    parser = argparse.ArgumentParser(description="OpsSentinel alert simulator")
    parser.add_argument("mode", choices=["signal", "storm"], help="single signal or alert storm")
    parser.add_argument("--count", type=int, default=50, help="number of storm signals")
    args = parser.parse_args()

    events = [make_incident_signal()] if args.mode == "signal" else make_storm(args.count)
    for event in events:
        publish_alert(event)
    logger.info("published signals", extra={"mode": args.mode, "count": len(events)})
    print(f"published {len(events)} event(s) in {args.mode} mode")


if __name__ == "__main__":
    main()
