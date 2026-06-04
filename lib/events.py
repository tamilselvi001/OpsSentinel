"""Normalized alert event model — the contract published to ``opssentinel-alerts``.

This is the single source of truth for the shape every inbound monitoring signal is
normalized into before it enters the Queue Layer (see the Phase-1 prompt, Section 3).
The Input Layer (webhook receiver, Task 5.3) maps each source payload into this shape;
the Agent Layer (Phase 3) consumes it.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AlertSource(StrEnum):
    """Where the signal originated. Superset of the Phase-1 webhook sources, kept in
    sync with the cross-service contract so later phases never have to fork it."""

    elastic = "elastic"
    pagerduty = "pagerduty"
    grafana = "grafana"
    servicenow = "servicenow"
    simulator = "simulator"


class SeverityHint(StrEnum):
    """Source-provided severity hint. The Agent Layer assigns the final severity."""

    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    unknown = "unknown"


def derive_correlation_key(service: str, environment: str, infra_scope: str) -> str:
    """Deterministic, stable hash of ``{service + environment + infrastructure scope}``.

    The Agent Layer (Phase 3) uses this for *time-windowed spatial correlation* — folding
    an alert storm into one incident **before** any LLM call. Phase 1 only needs to populate
    it deterministically; the correlation logic itself is Phase 3.

    ``infra_scope`` is the smallest infrastructure boundary that defines "the same failure
    domain". For the MVP's Kubernetes focus that is the k8s namespace, falling back to region
    when the namespace is unknown — the caller (the webhook receiver) assembles it.
    """
    normalized = "|".join(part.strip().lower() for part in (service, environment, infra_scope))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


class AlertEvent(BaseModel):
    """The normalized event published to the ``opssentinel-alerts`` topic."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    source: AlertSource
    received_at: datetime
    service: str
    environment: str
    severity_hint: SeverityHint = SeverityHint.unknown
    error_code: str | None = None
    http_status: int | None = None
    deployment_id: str | None = None
    correlation_key: str
    message: str
    labels: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)

    @field_validator("http_status")
    @classmethod
    def _valid_http_status(cls, value: int | None) -> int | None:
        if value is not None and not (100 <= value <= 599):
            raise ValueError("http_status must be a valid HTTP status code (100-599)")
        return value

    @field_validator("service", "environment", "message")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must be a non-empty string")
        return value
