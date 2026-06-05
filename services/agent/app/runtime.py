"""Runtime wiring for the ADK agent: OpenInference tracing + the store/notifier the graph needs.

Only the running agent imports this; the unit tests build the pieces directly.
"""

from __future__ import annotations

import json
import urllib.request

from app.config import AgentConfig, load_config
from app.incident_store import DbIncidentStore
from lib.logging import get_logger
from lib.observability import configure_tracing

logger = get_logger("opssentinel.agent.runtime")


class SlackNotifier:
    """Concrete Notifier — POSTs ``{incident_id}`` to the slack-bot ``/notify`` endpoint."""

    def __init__(self, notify_url: str) -> None:
        self._url = notify_url

    def notify(self, incident_id: str) -> None:
        data = json.dumps({"incident_id": incident_id}).encode("utf-8")
        request = urllib.request.Request(
            self._url, data=data, headers={"content-type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(request, timeout=10).close()  # noqa: S310 (internal URL)


def build_store() -> DbIncidentStore:
    return DbIncidentStore()


def build_notifier(config: AgentConfig | None = None) -> SlackNotifier:
    config = config or load_config()
    return SlackNotifier(config.slack_notify_url)


def enable_tracing() -> None:
    """Apply the OpenInference ADK instrumentor → Phoenix; never fatal if the collector is down.

    Because the agent now actually runs on ADK, this auto-captures every model/tool/token as a span.
    """
    try:
        configure_tracing(service_name="opssentinel-agent")
        logger.info("openinference ADK tracing enabled")
    except Exception as exc:
        logger.warning("tracing not configured; continuing", extra={"error": str(exc)})
