"""PostgreSQL incident store — ACID-safe connection pool + minimal data-access layer.

Tuned for **Consistency + Partition tolerance (CP)**: every write goes through a single
transaction (``BEGIN ... COMMIT``), and ``upsert_incident`` is atomic via ``INSERT ... ON
CONFLICT`` — so concurrent updates can never produce a duplicate or lost write (the guard
against double remediation). ``pool_pre_ping`` lets a pooled connection survive Cloud SQL's
Active-Passive failover. The Agent Layer (Phase 3) imports these helpers; it does not re-open
the database directly.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from lib.secrets import get_secret

_engine: Engine | None = None

# Columns that carry JSON documents (bound as text, cast to jsonb in SQL).
_JSONB_COLUMNS = {"correlated_event_ids", "recommended_action", "historical_match_ids"}

# Allowlist of writable incident columns (fixes the SQL surface — values are always bound).
_INCIDENT_COLUMNS = (
    "incident_id",
    "status",
    "severity",
    "category",
    "title",
    "root_cause",
    "confidence",
    "risk_level",
    "correlated_event_ids",
    "recommended_action",
    "historical_match_ids",
    "autonomy_tier",
    "trace_id",
    "approver_subject",
    "approval_status",
    "approved_at",
    "resolution_summary",
)


def get_engine() -> Engine:
    """Return a lazily-initialized, pooled SQLAlchemy engine (psycopg3 driver)."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_secret("database-url"),
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # survive Active-Passive failover / dropped connections
            pool_recycle=1800,
            future=True,
        )
    return _engine


@contextmanager
def transaction() -> Iterator[Connection]:
    """Yield a connection inside one ACID transaction (commit on success, rollback on error)."""
    with get_engine().begin() as conn:
        yield conn


def _bind_value(column: str, value: Any) -> Any:
    if column in _JSONB_COLUMNS and not isinstance(value, str):
        return json.dumps(value)
    return value


def upsert_incident(incident: dict[str, Any]) -> str:
    """Insert or update an incident by primary key. Atomic via ``INSERT ... ON CONFLICT``."""
    if "incident_id" not in incident:
        raise ValueError("incident_id is required")
    data = {k: v for k, v in incident.items() if k in _INCIDENT_COLUMNS}
    columns = list(data)

    def placeholder(col: str) -> str:
        return f"CAST(:{col} AS jsonb)" if col in _JSONB_COLUMNS else f":{col}"

    insert_cols = ", ".join(columns)
    insert_vals = ", ".join(placeholder(c) for c in columns)
    updates = [f"{c} = EXCLUDED.{c}" for c in columns if c != "incident_id"]
    updates.append("updated_at = now()")
    sql = text(
        f"INSERT INTO incidents ({insert_cols}) VALUES ({insert_vals}) "
        f"ON CONFLICT (incident_id) DO UPDATE SET {', '.join(updates)} "
        f"RETURNING incident_id"
    )
    params = {c: _bind_value(c, data[c]) for c in columns}
    with transaction() as conn:
        return str(conn.execute(sql, params).scalar_one())


def get_incident(incident_id: str) -> dict[str, Any] | None:
    """Fetch a single incident as a dict, or ``None`` if it does not exist."""
    sql = text("SELECT * FROM incidents WHERE incident_id = :id")
    with transaction() as conn:
        row = conn.execute(sql, {"id": incident_id}).mappings().first()
        return dict(row) if row else None


def add_event(incident_id: str, event: dict[str, Any], correlation_key: str | None = None) -> str:
    """Attach a raw correlated event to an incident. Returns the event row id."""
    sql = text(
        "INSERT INTO incident_events (incident_id, correlation_key, event) "
        "VALUES (:incident_id, :correlation_key, CAST(:event AS jsonb)) "
        "RETURNING event_pk"
    )
    params = {
        "incident_id": incident_id,
        "correlation_key": correlation_key,
        "event": json.dumps(event),
    }
    with transaction() as conn:
        return str(conn.execute(sql, params).scalar_one())


def append_audit(
    actor: str,
    action: str,
    incident_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> str:
    """Append an immutable audit record (every AI decision and human action). Returns its id."""
    sql = text(
        "INSERT INTO audit_log (incident_id, actor, action, details) "
        "VALUES (:incident_id, :actor, :action, CAST(:details AS jsonb)) "
        "RETURNING audit_id"
    )
    params = {
        "incident_id": incident_id,
        "actor": actor,
        "action": action,
        "details": json.dumps(details or {}),
    }
    with transaction() as conn:
        return str(conn.execute(sql, params).scalar_one())
