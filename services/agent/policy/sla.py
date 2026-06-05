"""SLA timers (part of the Policy Engine, node 7) — escalate incidents past their response window.

Deadlines come from the Phase-1 ``sla_policies`` seed (P1 respond ≤ 15 min, P2 ≤ 60 min). The
periodic check is driven by the Phase-1 Cloud Scheduler ``opssentinel-sla-check`` job; this module
is the pure decision used by that sweep. Terminal/handled states are never re-escalated.
"""

from __future__ import annotations

from datetime import datetime, timedelta

# Response-window minutes per severity (matches the Phase-1 sla_policies seed).
DEFAULT_SLA_MINUTES = {"P1": 15, "P2": 60, "P3": 240, "P4": 1440}

# States past which an SLA escalation no longer applies.
_TERMINAL_OR_HANDLED = {"approved", "executing", "resolved", "rejected", "escalated"}


def response_breached(
    severity: str,
    created_at: datetime,
    now: datetime,
    sla_minutes: dict[str, int] | None = None,
) -> bool:
    """True if the response window for ``severity`` has elapsed since ``created_at``."""
    minutes = (sla_minutes or DEFAULT_SLA_MINUTES).get(severity)
    if minutes is None:
        return False
    return (now - created_at) > timedelta(minutes=minutes)


def should_escalate(
    status: str,
    severity: str,
    created_at: datetime,
    now: datetime,
    sla_minutes: dict[str, int] | None = None,
) -> bool:
    """True if an un-actioned incident has breached its response SLA and must be escalated."""
    if status in _TERMINAL_OR_HANDLED:
        return False
    return response_breached(severity, created_at, now, sla_minutes)
