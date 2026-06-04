"""Pure signal generation (no I/O) — unit-testable. The CLI publishes what these return.

Two scenarios: a single realistic incident (the 2:47 AM payment-service DB-connection-pool event)
and an alert storm of 50+ related signals that all share one ``correlation_key`` — the input the
Phase-5 deduplication test folds into a single incident.
"""

from __future__ import annotations

from datetime import UTC, datetime

from lib.events import AlertEvent, AlertSource, SeverityHint, derive_correlation_key

SCENARIO_SERVICE = "payment-service"
SCENARIO_ENVIRONMENT = "production"
SCENARIO_SCOPE = "payments-ns"

# Storm signals arrive from several tools but describe the same failure domain.
_STORM_SOURCES = [AlertSource.elastic, AlertSource.pagerduty, AlertSource.grafana]
_STORM_PODS = ["payment-7c9", "payment-3f2", "payment-a18", "payment-b44"]
_STORM_MESSAGES = [
    "Database connection timeout on primary pool",
    "HikariPool-1 - Connection is not available, request timed out",
    "503 upstream connect error: database unreachable",
    "connection pool at 100% utilization",
]


def _correlation_key() -> str:
    return derive_correlation_key(SCENARIO_SERVICE, SCENARIO_ENVIRONMENT, SCENARIO_SCOPE)


def make_incident_signal(source: AlertSource = AlertSource.elastic) -> AlertEvent:
    """The single reference incident: payment-service DB connection-pool exhaustion at 02:47."""
    return AlertEvent(
        source=source,
        received_at=datetime.now(UTC),
        service=SCENARIO_SERVICE,
        environment=SCENARIO_ENVIRONMENT,
        severity_hint=SeverityHint.P1,
        error_code="ERR_DB_CONN_TIMEOUT",
        http_status=503,
        deployment_id="deploy-2026-01-01-0000",
        correlation_key=_correlation_key(),
        message="Database connection timeout on primary pool (02:47 scenario)",
        labels={"k8s_namespace": SCENARIO_SCOPE, "pod": "payment-7c9", "region": "us-central1"},
        raw={"original": {"simulated": True}},
    )


def make_storm(count: int = 50) -> list[AlertEvent]:
    """``count`` related signals (default 50) that all share one correlation_key."""
    correlation_key = _correlation_key()
    events: list[AlertEvent] = []
    for i in range(count):
        events.append(
            AlertEvent(
                source=_STORM_SOURCES[i % len(_STORM_SOURCES)],
                received_at=datetime.now(UTC),
                service=SCENARIO_SERVICE,
                environment=SCENARIO_ENVIRONMENT,
                severity_hint=SeverityHint.P1,
                error_code="ERR_DB_CONN_TIMEOUT",
                http_status=503,
                deployment_id="deploy-2026-01-01-0000",
                correlation_key=correlation_key,
                message=f"{_STORM_MESSAGES[i % len(_STORM_MESSAGES)]} (#{i + 1})",
                labels={
                    "k8s_namespace": SCENARIO_SCOPE,
                    "pod": _STORM_PODS[i % len(_STORM_PODS)],
                    "region": "us-central1",
                },
                raw={"original": {"simulated": True, "seq": i + 1}},
            )
        )
    return events
