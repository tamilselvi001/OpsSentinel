"""Deterministic source-payload → ``AlertEvent`` mappers (no LLM, no correlation).

Each mapper extracts the normalized fields from a source's webhook body with tolerant
fallbacks, derives ``correlation_key`` from ``service + environment + infrastructure scope``,
and stashes the untouched original under ``raw.original``. The mapping is pure and stable: the
same input always yields the same normalized event.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from lib.events import AlertEvent, AlertSource, SeverityHint, derive_correlation_key

# Map common source severity vocabularies onto the normalized severity hint.
_SEVERITY_ALIASES: dict[str, SeverityHint] = {
    "critical": SeverityHint.P1,
    "fatal": SeverityHint.P1,
    "p1": SeverityHint.P1,
    "sev1": SeverityHint.P1,
    "error": SeverityHint.P2,
    "high": SeverityHint.P2,
    "p2": SeverityHint.P2,
    "sev2": SeverityHint.P2,
    "warning": SeverityHint.P3,
    "warn": SeverityHint.P3,
    "p3": SeverityHint.P3,
    "info": SeverityHint.P4,
    "low": SeverityHint.P4,
    "p4": SeverityHint.P4,
}


def _severity(value: Any) -> SeverityHint:
    if value is None:
        return SeverityHint.unknown
    return _SEVERITY_ALIASES.get(str(value).strip().lower(), SeverityHint.unknown)


def _dig(payload: Any, path: str, default: Any = None) -> Any:
    """Safely read a dotted path out of nested dicts."""
    cur = payload
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def _infra_scope(labels: dict[str, Any]) -> str:
    """Smallest failure-domain boundary: k8s namespace, else region, else 'unknown'."""
    return str(
        labels.get("k8s_namespace") or labels.get("namespace") or labels.get("region") or "unknown"
    )


def _stringify_labels(labels: dict[str, Any]) -> dict[str, str]:
    return {str(k): str(v) for k, v in labels.items()}


def _build(
    source: AlertSource,
    *,
    service: str,
    environment: str,
    severity: SeverityHint,
    message: str,
    labels: dict[str, Any],
    original: Any,
    error_code: str | None = None,
    http_status: int | None = None,
    deployment_id: str | None = None,
) -> AlertEvent:
    svc = service or "unknown"
    env = environment or "production"
    scope = _infra_scope(labels)
    return AlertEvent(
        source=source,
        received_at=datetime.now(UTC),
        service=svc,
        environment=env,
        severity_hint=severity,
        error_code=error_code,
        http_status=http_status,
        deployment_id=deployment_id,
        correlation_key=derive_correlation_key(svc, env, scope),
        message=message or f"{source} alert",
        labels=_stringify_labels(labels),
        raw={"original": original},
    )


def normalize_pagerduty(payload: dict[str, Any]) -> AlertEvent:
    data = _dig(payload, "event.data", payload) or {}
    custom = _dig(data, "custom_details", {}) or {}
    labels = {**custom}
    service = (
        _dig(data, "service.summary")
        or custom.get("service")
        or payload.get("service")
        or "unknown"
    )
    environment = custom.get("environment") or custom.get("env") or "production"
    return _build(
        AlertSource.pagerduty,
        service=str(service),
        environment=str(environment),
        severity=_severity(data.get("severity") or data.get("urgency")),
        message=str(data.get("title") or data.get("summary") or "pagerduty incident"),
        labels=labels,
        original=payload,
        error_code=custom.get("error_code"),
        http_status=custom.get("http_status"),
        deployment_id=custom.get("deployment_id"),
    )


def normalize_grafana(payload: dict[str, Any]) -> AlertEvent:
    labels = dict(payload.get("commonLabels") or payload.get("labels") or {})
    annotations = dict(payload.get("commonAnnotations") or {})
    service = labels.get("service") or labels.get("job") or payload.get("service") or "unknown"
    environment = labels.get("environment") or labels.get("env") or "production"
    message = (
        payload.get("message")
        or annotations.get("summary")
        or payload.get("title")
        or "grafana alert"
    )
    return _build(
        AlertSource.grafana,
        service=str(service),
        environment=str(environment),
        severity=_severity(labels.get("severity") or payload.get("severity")),
        message=str(message),
        labels=labels,
        original=payload,
        error_code=labels.get("alertname"),
        deployment_id=labels.get("deployment_id"),
    )


def normalize_elastic(payload: dict[str, Any]) -> AlertEvent:
    labels = dict(_dig(payload, "kubernetes.labels", {}) or payload.get("labels") or {})
    if "k8s_namespace" not in labels:
        namespace = _dig(payload, "kubernetes.namespace")
        if namespace:
            labels["k8s_namespace"] = namespace
    service = (
        _dig(payload, "service.name")
        or labels.get("service")
        or payload.get("service")
        or "unknown"
    )
    environment = _dig(payload, "service.environment") or labels.get("environment") or "production"
    message = (
        payload.get("message")
        or _dig(payload, "error.message")
        or payload.get("reason")
        or "elastic alert"
    )
    return _build(
        AlertSource.elastic,
        service=str(service),
        environment=str(environment),
        severity=_severity(payload.get("severity") or _dig(payload, "event.severity")),
        message=str(message),
        labels=labels,
        original=payload,
        error_code=_dig(payload, "error.code") or payload.get("error_code"),
        http_status=_dig(payload, "http.response.status_code") or payload.get("http_status"),
        deployment_id=_dig(payload, "deployment.id") or payload.get("deployment_id"),
    )


NORMALIZERS = {
    "pagerduty": normalize_pagerduty,
    "grafana": normalize_grafana,
    "elastic": normalize_elastic,
}
