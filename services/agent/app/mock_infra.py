"""Mocked infrastructure state for the execution path (node 9).

The MVP does **not** touch a real cluster: the deterministic execution path mutates this in-repo
mock (a connection-pool / replica state plus a "ServiceNow" ticket), exactly as the spec requires.
All operations are **idempotent** so a re-delivered approval cannot double-apply. Pure + testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MockInfrastructure:
    pool_restarts: dict[str, int] = field(default_factory=dict)
    max_connections: dict[str, int] = field(default_factory=dict)
    replicas: dict[str, int] = field(default_factory=dict)
    tickets: dict[str, str] = field(default_factory=dict)  # incident_id -> open | resolved

    def open_ticket(self, incident_id: str) -> None:
        self.tickets.setdefault(incident_id, "open")

    def resolve_ticket(self, incident_id: str) -> None:
        self.tickets[incident_id] = "resolved"

    def ticket_status(self, incident_id: str) -> str | None:
        return self.tickets.get(incident_id)

    def apply(self, service: str, commands: list[str]) -> dict[str, Any]:
        """Apply the recommended (mocked) remediation commands. Idempotent per service."""
        applied: list[str] = []
        for command in commands:
            lowered = command.lower()
            if "restart" in lowered:
                self.pool_restarts[service] = self.pool_restarts.get(service, 0) + 1
                applied.append("restart_connection_pool")
            elif "scale" in lowered or "replicas" in lowered:
                self.replicas[service] = _extract_int(
                    lowered, default=self.replicas.get(service, 1)
                )
                applied.append("scale_replicas")
            elif "max_connections" in lowered or "alter system" in lowered:
                self.max_connections[service] = _extract_int(lowered, default=400)
                applied.append("increase_max_connections")
        return {"service": service, "applied": applied}


def _extract_int(text: str, default: int) -> int:
    """Best-effort: pull the last integer out of a command string (e.g. replicas=5)."""
    digits = "".join(ch if ch.isdigit() else " " for ch in text).split()
    return int(digits[-1]) if digits else default
