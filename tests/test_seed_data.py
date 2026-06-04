"""Tests for the synthetic telemetry datasets (Phase 2, Task 5.4)."""

import importlib.util
import pathlib

_PATH = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "seed_data.py"
_spec = importlib.util.spec_from_file_location("seed_data", _PATH)
seed_data = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed_data)


def test_knowledge_includes_db_pool_and_kubernetes_runbooks():
    docs = seed_data.knowledge_documents()
    ids = {d["id"] for d in docs}
    assert "rb-db-conn-limit" in ids
    categories = {d["category"] for d in docs}
    assert "Database Connection Pool" in categories
    # Kubernetes-class incidents present (crashloop / oomkill / partition / regression)
    assert {"Kubernetes Pod Failure", "Kubernetes Resource", "Network Partition"} <= categories


def test_db_pool_runbook_has_resolution_and_commands():
    rb = next(d for d in seed_data.knowledge_documents() if d["id"] == "rb-db-conn-limit")
    assert rb["resolution_steps"]
    assert rb["commands"]
    assert "connection-pool" in rb["tags"]


def test_logs_include_payment_service():
    logs = seed_data.log_documents()
    assert any(line["service"] == "payment-service" for line in logs)


def test_arize_outcomes_cover_all_seeded_categories():
    outcomes = seed_data.arize_outcomes()
    categories = {o["category"] for o in outcomes}
    assert "Database Connection Pool" in categories
    assert "DNS Resolution Failure" in categories  # the novel category
    assert len(outcomes) == sum(total for _, total, _, _ in seed_data.ARIZE_CATEGORY_STATS)
