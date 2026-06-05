"""Agent entrypoint: tracing + health + execution consumer, then alert intake → the ADK agent.

The alert consumer (node 1/2) runs in the main thread and feeds each correlated incident to the
ADK agent (:func:`app.adk_app.run_incident`); the approval-execution consumer (node 9) runs in a
daemon thread.
"""

from __future__ import annotations

import threading

from app.adk_app import run_incident
from app.consumer import run
from app.correlation import IncidentContext
from app.execution_consumer import run as run_execution_consumer
from app.health import start_health_server
from app.runtime import build_notifier, build_store, enable_tracing
from lib.logging import get_logger

logger = get_logger("opssentinel.agent")


def _start_execution_consumer() -> None:
    try:
        run_execution_consumer()
    except Exception:
        logger.exception("execution consumer crashed")


def main() -> None:
    start_health_server()  # Cloud Run liveness (the agent is otherwise a background pull worker)
    enable_tracing()
    store = build_store()
    notifier = build_notifier()
    threading.Thread(target=_start_execution_consumer, daemon=True).start()

    def on_incident(ctx: IncidentContext) -> None:
        try:
            result = run_incident(ctx, store=store, notifier=notifier)
            logger.info(
                "incident processed",
                extra={
                    "incident_id": result.incident_id,
                    "status": result.status,
                    "trace_id": result.trace_id,
                },
            )
        except Exception:
            logger.exception("agent failed", extra={"correlation_key": ctx.correlation_key})

    run(on_incident=on_incident)


if __name__ == "__main__":
    main()
