"""Tests for the mocked infrastructure state (Phase 3, Task 6.9)."""

import importlib.util
import pathlib
import sys

_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "services" / "agent" / "app" / "mock_infra.py"
)
_spec = importlib.util.spec_from_file_location("agent_mock_infra", _PATH)
mock_infra = importlib.util.module_from_spec(_spec)
sys.modules["agent_mock_infra"] = mock_infra
_spec.loader.exec_module(mock_infra)


def test_apply_restart_and_scale_and_max_connections():
    infra = mock_infra.MockInfrastructure()
    result = infra.apply(
        "payment-service",
        [
            "kubectl rollout restart deploy/payment-service",
            "kubectl scale deploy/payment-service --replicas=5",
            "psql -c 'ALTER SYSTEM SET max_connections = 400'",
        ],
    )
    assert result["applied"] == [
        "restart_connection_pool",
        "scale_replicas",
        "increase_max_connections",
    ]
    assert infra.pool_restarts["payment-service"] == 1
    assert infra.replicas["payment-service"] == 5
    assert infra.max_connections["payment-service"] == 400


def test_ticket_lifecycle_is_idempotent():
    infra = mock_infra.MockInfrastructure()
    infra.open_ticket("inc-1")
    assert infra.ticket_status("inc-1") == "open"
    infra.resolve_ticket("inc-1")
    infra.resolve_ticket("inc-1")  # idempotent
    assert infra.ticket_status("inc-1") == "resolved"
