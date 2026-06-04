"""Phase-2 validation: semantic search robustness, logs, Arize signals, and MCP /health.

Run against the seeded local harness via `make validate-phase2` (needs Elasticsearch + Postgres +
both MCP servers up and `make seed` applied). Exits non-zero on the first failed assertion.
"""
# ruff: noqa: E402, I001  (sys.path bootstrap must precede first-party / cross-service imports)

from __future__ import annotations

import os
import pathlib
import sys
import urllib.request

_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "services" / "mcp-elastic"))

from sqlalchemy import text

from app.elastic_client import ElasticKnowledge
from lib.db import transaction

MCP_ELASTIC_URL = os.environ.get("MCP_ELASTIC_URL", "http://localhost:8080")
MCP_ARIZE_URL = os.environ.get("MCP_ARIZE_URL", "http://localhost:8081")


def check_semantic_search() -> None:
    kb = ElasticKnowledge()
    # Different wording than the runbook title ("Database Connection Limit Reached").
    results = kb.search_runbooks("connection pool exhausted", top_k=3)
    assert results, "search_runbooks returned nothing"
    top_ids = [r["id"] for r in results]
    assert "rb-db-conn-limit" in top_ids, f"DB-pool runbook not retrieved (got {top_ids})"
    assert top_ids[0] == "rb-db-conn-limit", f"RRF ranking unexpected: {top_ids}"
    print(f"OK  semantic search: '{results[0]['title']}' ranked #1 via RRF")


def check_logs() -> None:
    kb = ElasticKnowledge()
    logs = kb.fetch_recent_logs("payment-service", minutes=120)
    assert logs, "fetch_recent_logs returned nothing"
    print(f"OK  fetch_recent_logs: {len(logs)} lines for payment-service")


def check_arize() -> None:
    with transaction() as conn:
        acc = conn.execute(
            text(
                "SELECT count(*) FILTER (WHERE successful)::float / NULLIF(count(*), 0) "
                "FROM agent_outcomes WHERE category = :c"
            ),
            {"c": "Database Connection Pool"},
        ).scalar_one()
        novel_count = conn.execute(
            text("SELECT count(*) FROM agent_outcomes WHERE category = :c"),
            {"c": "DNS Resolution Failure"},
        ).scalar_one()
    assert acc is not None and 0.89 <= acc <= 0.93, f"DB-pool accuracy off target: {acc}"
    assert novel_count < 5, f"expected a novel category, found {novel_count} outcomes"
    print(f"OK  arize: DB-pool accuracy={acc:.2f}; novel category has {novel_count} outcomes")


def check_health() -> None:
    for name, base in (("mcp-elastic", MCP_ELASTIC_URL), ("mcp-arize", MCP_ARIZE_URL)):
        with urllib.request.urlopen(f"{base}/health", timeout=5) as resp:  # noqa: S310
            assert resp.status == 200, f"{name} /health returned {resp.status}"
        print(f"OK  {name} /health reachable")


def main() -> None:
    check_health()
    check_semantic_search()
    check_logs()
    check_arize()
    print("\nPhase-2 validation passed.")


if __name__ == "__main__":
    main()
