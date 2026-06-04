"""Synthetic telemetry datasets for Phase-2 seeding (pure data — unit-testable, no I/O).

Backs the spec's reference walk-through: a Database-Connection-Pool runbook plus Kubernetes-class
incidents, recent logs, and an Arize history with a ~91% accuracy DB-pool category, a
well-calibrated example, and a degraded + a novel category.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

# ── Knowledge base runbooks (embedded into opssentinel-knowledge at seed time) ───────────────
KNOWLEDGE_RUNBOOKS: list[dict[str, Any]] = [
    {
        "id": "rb-db-conn-limit",
        "title": "Database Connection Limit Reached",
        "summary": "Service exhausts its DB connection pool under load; new queries time out.",
        "root_cause": "Connection pool exhausted: size below peak demand after deploy.",
        "resolution_steps": (
            "1. Restart the connection pool to release leaked connections. "
            "2. Dynamically raise max pool size / DB max_connections. "
            "3. Verify error rate recovers and connections stabilize."
        ),
        "commands": [
            "kubectl rollout restart deploy/payment-service -n payments-ns",
            "psql -c 'ALTER SYSTEM SET max_connections = 400;'",
        ],
        "service": "payment-service",
        "category": "Database Connection Pool",
        "tags": ["database", "connection-pool", "timeout", "ERR_DB_CONN_TIMEOUT"],
        "environment": "production",
        "who_handled": "sre-oncall",
        "time_to_fix": "8m",
        "resolved_at": "2025-11-03T02:55:00Z",
    },
    {
        "id": "rb-pod-crashloop",
        "title": "Pod CrashLoopBackOff after deploy",
        "summary": "A pod repeatedly crashes and restarts immediately after rollout.",
        "root_cause": "Bad config / failing readiness probe causes the container to exit on boot.",
        "resolution_steps": "Roll back the deployment; fix the probe/config; redeploy.",
        "commands": ["kubectl rollout undo deploy/<svc> -n <ns>"],
        "service": "checkout-service",
        "category": "Kubernetes Pod Failure",
        "tags": ["kubernetes", "crashloopbackoff", "rollout"],
        "environment": "production",
        "who_handled": "sre-oncall",
        "time_to_fix": "12m",
        "resolved_at": "2025-12-01T14:10:00Z",
    },
    {
        "id": "rb-oomkill",
        "title": "Container OOMKilled under memory pressure",
        "summary": "Container exceeds its memory limit and is OOMKilled by the kubelet.",
        "root_cause": "Memory limit below working set; a leak or load spike trips it.",
        "resolution_steps": "Raise memory limits/requests; investigate the leak; restart the pod.",
        "commands": ["kubectl set resources deploy/<svc> --limits=memory=1Gi -n <ns>"],
        "service": "auth-service",
        "category": "Kubernetes Resource",
        "tags": ["kubernetes", "oomkill", "memory"],
        "environment": "production",
        "who_handled": "sre-oncall",
        "time_to_fix": "15m",
        "resolved_at": "2025-12-10T09:30:00Z",
    },
    {
        "id": "rb-net-partition",
        "title": "Network partition between service and datastore",
        "summary": "Transient network split isolates a service from its database/region.",
        "root_cause": "Network partition / CNI disruption breaks connectivity to the datastore.",
        "resolution_steps": "Fail over to standby region; verify connectivity; drain node.",
        "commands": ["kubectl drain <node> --ignore-daemonsets"],
        "service": "payment-service",
        "category": "Network Partition",
        "tags": ["kubernetes", "network", "partition"],
        "environment": "production",
        "who_handled": "network-oncall",
        "time_to_fix": "20m",
        "resolved_at": "2026-01-05T22:00:00Z",
    },
    {
        "id": "rb-deploy-regression",
        "title": "Deployment regression — error spike after release",
        "summary": "A new release introduces a regression; error rate spikes after deploy.",
        "root_cause": "Regression shipped in the latest deployment image.",
        "resolution_steps": "Roll back to the last known-good image; open a fix-forward.",
        "commands": ["kubectl rollout undo deploy/<svc> -n <ns>"],
        "service": "checkout-service",
        "category": "Deployment Regression",
        "tags": ["deployment", "regression", "rollback"],
        "environment": "production",
        "who_handled": "release-oncall",
        "time_to_fix": "10m",
        "resolved_at": "2026-02-14T11:45:00Z",
    },
]

# ── Arize history: (category, total outcomes, successful count, stated confidence) ───────────
# DB-pool ~91% accurate & well-calibrated; one degraded (poorly calibrated) and one novel.
ARIZE_CATEGORY_STATS: list[tuple[str, int, int, float]] = [
    ("Database Connection Pool", 100, 91, 0.90),  # 91% accuracy, calibration ≈ 0.01 (<5%)
    ("Kubernetes Pod Failure", 40, 36, 0.88),  # 90% accuracy
    ("Deployment Regression", 20, 11, 0.85),  # 55% accuracy — degraded, calibration ≈ 0.30
    ("DNS Resolution Failure", 2, 1, 0.80),  # < 5 outcomes — novel category
]


def knowledge_documents() -> list[dict[str, Any]]:
    """Runbook documents (without the embedding; the seed script adds it)."""
    return [dict(rb) for rb in KNOWLEDGE_RUNBOOKS]


def log_documents(now: datetime | None = None) -> list[dict[str, Any]]:
    """Recent log/APM lines backing fetch_recent_logs (mostly payment-service timeouts)."""
    now = now or datetime.now(UTC)
    lines = [
        ("payment-service", "ERROR", "ERR_DB_CONN_TIMEOUT: timeout acquiring connection from pool"),
        (
            "payment-service",
            "ERROR",
            "HikariPool-1 - Connection is not available, request timed out",
        ),
        ("payment-service", "WARN", "connection pool at 100% utilization (50/50)"),
        ("payment-service", "ERROR", "503 upstream connect error: database unreachable"),
        ("checkout-service", "WARN", "elevated p99 latency on /checkout"),
        ("auth-service", "INFO", "readiness probe ok"),
    ]
    docs = []
    for i, (service, level, message) in enumerate(lines):
        docs.append(
            {
                "service": service,
                "timestamp": (now - timedelta(minutes=i)).isoformat(),
                "level": level,
                "message": message,
                "labels": {"k8s_namespace": "payments-ns", "region": "us-central1"},
            }
        )
    return docs


def arize_outcomes() -> list[dict[str, Any]]:
    """Expand the category stats into individual outcome rows."""
    outcomes: list[dict[str, Any]] = []
    for category, total, successful, confidence in ARIZE_CATEGORY_STATS:
        for i in range(total):
            outcomes.append(
                {
                    "category": category,
                    "approved": True,
                    "successful": i < successful,
                    "stated_confidence": confidence,
                }
            )
    return outcomes
