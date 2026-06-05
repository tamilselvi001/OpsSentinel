"""Agent entrypoint: enable tracing, start the execution consumer, run alert intake → the graph.

The alert consumer (node 1/2) runs in the main thread; the approval-execution consumer (node 9)
runs in a daemon thread. A correlated incident is driven through the reasoning graph to
``awaiting_approval``; an approval published to ``opssentinel-actions`` drives the execution path.
"""

from __future__ import annotations

import threading

from app.consumer import run
from app.correlation import IncidentContext
from app.execution_consumer import run as run_execution_consumer
from app.graph import run_graph
from app.health import start_health_server
from app.runtime import build_deps, enable_tracing
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
    deps = build_deps()
    threading.Thread(target=_start_execution_consumer, daemon=True).start()

    def on_incident(ctx: IncidentContext) -> None:
        try:
            result = run_graph(ctx, deps)
            logger.info(
                "incident processed",
                extra={
                    "incident_id": result.incident_id,
                    "status": result.status,
                    "trace_id": result.trace_id,
                },
            )
        except Exception:
            logger.exception("graph failed", extra={"correlation_key": ctx.correlation_key})

    run(on_incident=on_incident)


if __name__ == "__main__":
    main()
