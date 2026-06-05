"""Tests for time-windowed spatial correlation (Phase 3, Task 6.4 — storm dedup)."""

import importlib.util
import pathlib
import sys
from datetime import UTC, datetime, timedelta

from lib.events import AlertEvent, derive_correlation_key

_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "services" / "agent" / "app" / "correlation.py"
)
_spec = importlib.util.spec_from_file_location("agent_correlation", _PATH)
correlation = importlib.util.module_from_spec(_spec)
# Register before exec: the module's @dataclass needs sys.modules[__name__] to resolve annotations.
sys.modules["agent_correlation"] = correlation
_spec.loader.exec_module(correlation)

_BASE = datetime(2026, 1, 1, 2, 47, 0, tzinfo=UTC)


def _event(scope: str, offset_seconds: int, service: str = "payment-service") -> AlertEvent:
    return AlertEvent(
        source="elastic",
        received_at=_BASE + timedelta(seconds=offset_seconds),
        service=service,
        environment="production",
        correlation_key=derive_correlation_key(service, "production", scope),
        message="signal",
    )


def test_storm_folds_into_single_incident():
    storm = [_event("payments-ns", i) for i in range(50)]  # all same key, within window
    contexts = correlation.group_by_correlation(storm, window_seconds=120)
    assert len(contexts) == 1
    assert contexts[0].size == 50
    assert contexts[0].correlation_key == storm[0].correlation_key


def test_distinct_correlation_keys_yield_distinct_incidents():
    events = [_event("payments-ns", 0), _event("checkout-ns", 1, service="checkout-service")]
    contexts = correlation.group_by_correlation(events, window_seconds=120)
    assert len(contexts) == 2


def test_same_key_outside_window_opens_new_incident():
    events = [_event("payments-ns", 0), _event("payments-ns", 5), _event("payments-ns", 600)]
    contexts = correlation.group_by_correlation(events, window_seconds=120)
    assert len(contexts) == 2
    assert sorted(c.size for c in contexts) == [1, 2]


def test_streaming_correlator_groups_then_pops_when_idle():
    correlator = correlation.StreamingCorrelator(window_seconds=120)
    for i in range(10):
        correlator.add(_event("payments-ns", i))
    # Nothing idle yet (still within the window of the last event).
    assert correlator.pop_ready(now=_BASE + timedelta(seconds=11)) == []
    # Well past the window -> the single incident becomes ready.
    ready = correlator.pop_ready(now=_BASE + timedelta(seconds=600))
    assert len(ready) == 1
    assert ready[0].size == 10


def test_representative_event_is_earliest():
    storm = [_event("payments-ns", i) for i in range(5)]
    ctx = correlation.group_by_correlation(storm)[0]
    assert ctx.representative.received_at == _BASE
