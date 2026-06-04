"""Tests for the webhook receiver's deterministic normalizers (Phase 1, Task 5.3 acceptance).

The normalizers live under services/webhook-receiver/app; we load that module by path so the
test needs neither FastAPI nor Pub/Sub. They depend only on lib.events.
"""

import importlib.util
import pathlib

import pytest

_NORM_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "services"
    / "webhook-receiver"
    / "app"
    / "normalizers.py"
)
_spec = importlib.util.spec_from_file_location("normalizers", _NORM_PATH)
normalizers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(normalizers)

from lib.events import AlertEvent, derive_correlation_key  # noqa: E402


def test_grafana_normalizes_to_valid_event():
    payload = {
        "commonLabels": {
            "service": "payment-service",
            "environment": "production",
            "severity": "critical",
            "k8s_namespace": "payments-ns",
            "alertname": "HighErrorRate",
        },
        "commonAnnotations": {"summary": "DB connection timeout"},
    }
    event = normalizers.normalize_grafana(payload)
    assert isinstance(event, AlertEvent)
    assert event.service == "payment-service"
    assert event.environment == "production"
    assert event.severity_hint == "P1"  # "critical" -> P1
    assert event.message == "DB connection timeout"
    assert event.correlation_key == derive_correlation_key(
        "payment-service", "production", "payments-ns"
    )
    assert event.raw["original"] == payload


def test_pagerduty_nested_payload():
    payload = {
        "event": {
            "data": {
                "title": "Pod CrashLoopBackOff",
                "severity": "warning",
                "service": {"summary": "checkout-service"},
                "custom_details": {"environment": "production", "k8s_namespace": "checkout-ns"},
            }
        }
    }
    event = normalizers.normalize_pagerduty(payload)
    assert event.service == "checkout-service"
    assert event.severity_hint == "P3"  # "warning" -> P3
    assert event.environment == "production"


def test_elastic_ecs_style_payload():
    payload = {
        "service": {"name": "auth-service", "environment": "production"},
        "error": {"code": "ERR_DB_CONN_TIMEOUT", "message": "connection pool exhausted"},
        "http": {"response": {"status_code": 503}},
        "kubernetes": {"namespace": "auth-ns"},
        "severity": "error",
    }
    event = normalizers.normalize_elastic(payload)
    assert event.service == "auth-service"
    assert event.error_code == "ERR_DB_CONN_TIMEOUT"
    assert event.http_status == 503
    assert event.severity_hint == "P2"  # "error" -> P2


def test_unknown_fields_fall_back_safely():
    event = normalizers.normalize_grafana({})
    assert event.service == "unknown"
    assert event.environment == "production"
    assert event.severity_hint == "unknown"


@pytest.mark.parametrize("source", ["pagerduty", "grafana", "elastic"])
def test_registry_exposes_all_sources(source):
    assert source in normalizers.NORMALIZERS
