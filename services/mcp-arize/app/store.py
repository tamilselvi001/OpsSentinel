"""Persistence for the Arize MCP tools — the queryable projection of trace/eval outcomes.

Backed by the ``agent_outcomes`` table (Phase-2 migration ``0002``), reusing the Phase-1
SQLAlchemy engine. In production these rows are the projection of Phoenix's LLM-as-a-judge
evaluations; ``log_outcome`` appends one, enriching it with the incident's stated confidence and
category when the incident exists. The metric math lives in :mod:`app.metrics`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.metrics import accuracy, calibration_error, is_novel
from lib.db import transaction

WINDOW_DEFAULT_DAYS = 30


def _fetch(category: str, window_days: int) -> list[dict[str, Any]]:
    sql = text(
        "SELECT category, approved, successful, stated_confidence "
        "FROM agent_outcomes "
        "WHERE category = :category "
        "AND created_at >= now() - make_interval(days => :window) "
    )
    with transaction() as conn:
        rows = conn.execute(sql, {"category": category, "window": window_days}).mappings().all()
    return [dict(r) for r in rows]


def get_category_accuracy(category: str, window: int = WINDOW_DEFAULT_DAYS) -> float:
    return accuracy(_fetch(category, window))


def get_calibration(category: str, window: int = WINDOW_DEFAULT_DAYS) -> float:
    return calibration_error(_fetch(category, window))


def is_novel_category(category: str, window: int = 365) -> bool:
    return is_novel(_fetch(category, window))


def log_outcome(trace_id: str, incident_id: str, approved: bool, successful: bool) -> str:
    """Append an outcome, enriching category + stated_confidence from the incident if present."""
    enrich = text("SELECT category, confidence FROM incidents WHERE incident_id = :id")
    insert = text(
        "INSERT INTO agent_outcomes "
        "(trace_id, incident_id, category, approved, successful, stated_confidence) "
        "VALUES (:trace_id, :incident_id, :category, :approved, :successful, :stated_confidence) "
        "RETURNING outcome_id"
    )
    with transaction() as conn:
        incident = conn.execute(enrich, {"id": incident_id}).mappings().first()
        params = {
            "trace_id": trace_id,
            "incident_id": incident_id,
            "category": incident["category"] if incident else None,
            "approved": approved,
            "successful": successful,
            "stated_confidence": incident["confidence"] if incident else None,
        }
        return str(conn.execute(insert, params).scalar_one())
