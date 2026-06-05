"""Agent configuration resolved from the environment (secrets come via lib.secrets)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    subscription: str
    actions_topic: str
    mcp_elastic_url: str
    mcp_arize_url: str
    correlation_window_seconds: int
    max_in_flight: int
    gemini_model: str
    slack_notify_url: str


def load_config() -> AgentConfig:
    """Build config from env. MCP URLs default to the Phase-2 in-cluster SSE endpoints."""
    return AgentConfig(
        subscription=os.environ.get("OPSSENTINEL_ALERTS_SUB", "opssentinel-alerts-sub"),
        actions_topic=os.environ.get("OPSSENTINEL_ACTIONS_TOPIC", "opssentinel-actions"),
        mcp_elastic_url=os.environ.get("MCP_ELASTIC_URL", "http://mcp-elastic:8080/sse"),
        mcp_arize_url=os.environ.get("MCP_ARIZE_URL", "http://mcp-arize:8081/sse"),
        correlation_window_seconds=int(os.environ.get("CORRELATION_WINDOW_SECONDS", "120")),
        max_in_flight=int(os.environ.get("AGENT_MAX_IN_FLIGHT", "4")),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
        slack_notify_url=os.environ.get("SLACK_NOTIFY_URL", "http://slack-bot:8080/notify"),
    )
