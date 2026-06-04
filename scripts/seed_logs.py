"""Seed recent log/APM lines into opssentinel-logs (backs fetch_recent_logs)."""
# ruff: noqa: E402, I001  (sys.path bootstrap must precede first-party / cross-service imports)

from __future__ import annotations

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "services" / "mcp-elastic"))

import seed_data
from elasticsearch import Elasticsearch

from app.bootstrap import ensure_indices
from app.elastic_client import LOGS_INDEX
from lib.secrets import get_secret


def main() -> None:
    ensure_indices()
    client = Elasticsearch(
        get_secret("elastic-url"),
        api_key=get_secret("elastic-api-key", default=None) or None,
    )
    docs = seed_data.log_documents()
    for i, doc in enumerate(docs):
        client.index(index=LOGS_INDEX, id=f"log-{i}", document=doc, refresh=True)
    print(f"seeded {len(docs)} log lines")


if __name__ == "__main__":
    main()
