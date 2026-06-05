"""Concrete :class:`app.interfaces.IncidentStore` backed by the Phase-1 Postgres data layer.

Every write also appends to ``audit_log`` (via :mod:`app.persistence`) — the governance trail.
Heavy ``lib.db`` import is module-level (only the running agent loads this module).
"""

from __future__ import annotations

from typing import Any

from app.persistence import persist_incident
from lib.db import append_audit, get_incident, upsert_incident


class DbIncidentStore:
    def persist(self, brief: dict[str, Any], status: str, trace_id: str | None) -> str:
        return persist_incident(brief, status=status, trace_id=trace_id)

    def get(self, incident_id: str) -> dict[str, Any] | None:
        return get_incident(incident_id)

    def update_status(self, incident_id: str, status: str, **fields: Any) -> None:
        # upsert_incident filters to known columns; unknown keys (e.g. internal flags) are ignored.
        upsert_incident({"incident_id": incident_id, "status": status, **fields})
        append_audit(
            actor="agent",
            action=f"transition:{status}",
            incident_id=incident_id,
            details={k: v for k, v in fields.items()},
        )
