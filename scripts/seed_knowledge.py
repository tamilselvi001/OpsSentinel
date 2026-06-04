"""Seed the Elastic knowledge base with embedded runbooks. Idempotent. Run via `make seed`."""
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
from app.elastic_client import KNOWLEDGE_INDEX
from app.embeddings import encode
from lib.secrets import get_secret

_EMBED_FIELDS = ("title", "summary", "root_cause", "resolution_steps")


def _client() -> Elasticsearch:
    return Elasticsearch(
        get_secret("elastic-url"),
        api_key=get_secret("elastic-api-key", default=None) or None,
    )


def main() -> None:
    ensure_indices()
    client = _client()
    for doc in seed_data.knowledge_documents():
        doc_id = doc.pop("id")
        doc["embedding"] = encode(" ".join(str(doc.get(f, "")) for f in _EMBED_FIELDS))
        client.index(index=KNOWLEDGE_INDEX, id=doc_id, document=doc, refresh=True)
        print(f"indexed runbook {doc_id}")
    print(f"seeded {len(seed_data.KNOWLEDGE_RUNBOOKS)} runbooks")


if __name__ == "__main__":
    main()
