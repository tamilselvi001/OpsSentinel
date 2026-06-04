"""Tests for the Alert Simulator's pure signal generation (Phase 2, Task 5.5)."""

import importlib.util
import pathlib

_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "services"
    / "alert-simulator"
    / "app"
    / "generator.py"
)
_spec = importlib.util.spec_from_file_location("generator", _PATH)
generator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generator)

from lib.events import AlertEvent  # noqa: E402


def test_single_signal_is_a_valid_p1_incident():
    event = generator.make_incident_signal()
    assert isinstance(event, AlertEvent)
    assert event.service == "payment-service"
    assert event.severity_hint == "P1"
    assert event.error_code == "ERR_DB_CONN_TIMEOUT"


def test_storm_emits_50_plus_correlated_signals():
    events = generator.make_storm(50)
    assert len(events) == 50
    assert all(isinstance(e, AlertEvent) for e in events)
    keys = {e.correlation_key for e in events}
    assert len(keys) == 1  # every storm signal shares one correlation_key
    # the single reference incident shares that same key (same failure domain)
    assert generator.make_incident_signal().correlation_key == keys.pop()


def test_storm_mixes_sources():
    events = generator.make_storm(9)
    assert len({e.source for e in events}) >= 2  # signals arrive from several tools
