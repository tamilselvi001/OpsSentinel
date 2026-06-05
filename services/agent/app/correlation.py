"""Time-windowed spatial correlation (deterministic, pre-LLM) — node 2 of the ADK graph.

Folds related/duplicate signals that share a ``correlation_key`` and arrive within a time window
into a SINGLE incident context, *before* any LLM call. This is the storm-deduplication engine and
the defense against alert-correlation failure: a 50-signal storm becomes one incident, not 50
parallel reasoning threads. Pure logic — no Pub/Sub, no LLM — so it is fully unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from lib.events import AlertEvent

DEFAULT_WINDOW_SECONDS = 120


@dataclass
class IncidentContext:
    """One correlated incident: all the signals sharing a key within the window."""

    correlation_key: str
    service: str
    environment: str
    events: list[AlertEvent] = field(default_factory=list)

    def add(self, event: AlertEvent) -> None:
        self.events.append(event)

    @property
    def size(self) -> int:
        return len(self.events)

    @property
    def first_seen(self) -> datetime:
        return min(e.received_at for e in self.events)

    @property
    def last_seen(self) -> datetime:
        return max(e.received_at for e in self.events)

    @property
    def event_ids(self) -> list[str]:
        return [e.event_id for e in self.events]

    @property
    def representative(self) -> AlertEvent:
        """The earliest signal — used as the canonical event for downstream reasoning."""
        return min(self.events, key=lambda e: e.received_at)


def group_by_correlation(
    events: list[AlertEvent], window_seconds: int = DEFAULT_WINDOW_SECONDS
) -> list[IncidentContext]:
    """Batch grouping: signals sharing a correlation_key within ``window_seconds`` of the group's
    first signal fold into one IncidentContext. Returns one context per (key, window)."""
    window = timedelta(seconds=window_seconds)
    contexts: list[IncidentContext] = []
    open_by_key: dict[str, IncidentContext] = {}
    for event in sorted(events, key=lambda e: e.received_at):
        ctx = open_by_key.get(event.correlation_key)
        if ctx is not None and event.received_at - ctx.first_seen <= window:
            ctx.add(event)
        else:
            ctx = IncidentContext(event.correlation_key, event.service, event.environment, [event])
            open_by_key[event.correlation_key] = ctx
            contexts.append(ctx)
    return contexts


class StreamingCorrelator:
    """Stateful streaming counterpart of :func:`group_by_correlation` for the live consumer.

    ``add`` folds an arriving event into the open incident for its key (opening a new one if none
    is open or the window has elapsed). ``pop_ready`` returns and clears incidents that have gone
    idle for longer than the window — those are ready to enter the reasoning graph.
    """

    def __init__(self, window_seconds: int = DEFAULT_WINDOW_SECONDS) -> None:
        self._window = timedelta(seconds=window_seconds)
        self._open: dict[str, IncidentContext] = {}

    def add(self, event: AlertEvent) -> IncidentContext:
        ctx = self._open.get(event.correlation_key)
        if ctx is None or event.received_at - ctx.first_seen > self._window:
            ctx = IncidentContext(event.correlation_key, event.service, event.environment, [event])
            self._open[event.correlation_key] = ctx
        else:
            ctx.add(event)
        return ctx

    def pop_ready(self, now: datetime | None = None) -> list[IncidentContext]:
        now = now or datetime.now(UTC)
        ready = [ctx for ctx in self._open.values() if now - ctx.last_seen > self._window]
        for ctx in ready:
            del self._open[ctx.correlation_key]
        return ready

    def drain(self) -> list[IncidentContext]:
        """Flush every open incident (e.g. on graceful shutdown)."""
        contexts = list(self._open.values())
        self._open.clear()
        return contexts
