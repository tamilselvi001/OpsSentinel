"""Elasticsearch access for the Elastic MCP tools (hybrid search, log fetch, closure write).

Credentials resolve only through the Phase-1 secrets accessor. ``search_runbooks`` runs a KNN
query over the 384-dim ``embedding`` field AND a full-text ``multi_match``, then fuses the two
rankings with RRF (in :mod:`app.retrieval`) — KNN + full-text via RRF, exactly as specified.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from elasticsearch import Elasticsearch

from app.embeddings import encode
from app.retrieval import rrf_fuse, shape_runbook
from lib.secrets import get_secret

KNOWLEDGE_INDEX = "opssentinel-knowledge"
LOGS_INDEX = "opssentinel-logs"


class ElasticKnowledge:
    """Thin wrapper over the Elasticsearch client implementing the three Elastic MCP tools."""

    def __init__(self, client: Elasticsearch | None = None) -> None:
        self._client = client or Elasticsearch(
            get_secret("elastic-url"),
            api_key=get_secret("elastic-api-key", default=None) or None,
        )

    def search_runbooks(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """KNN + full-text retrieval fused with RRF; returns the documented top-k shape."""
        query_vector = encode(query)
        pool = max(top_k * 5, 10)

        knn_hits = self._client.search(
            index=KNOWLEDGE_INDEX,
            knn={
                "field": "embedding",
                "query_vector": query_vector,
                "k": pool,
                "num_candidates": max(pool * 2, 100),
            },
            size=pool,
            _source=False,
        )["hits"]["hits"]

        text_hits = self._client.search(
            index=KNOWLEDGE_INDEX,
            query={
                "multi_match": {
                    "query": query,
                    "fields": ["title^2", "summary", "root_cause", "resolution_steps", "tags"],
                }
            },
            size=pool,
            _source=False,
        )["hits"]["hits"]

        fused = rrf_fuse([[h["_id"] for h in knn_hits], [h["_id"] for h in text_hits]])[:top_k]
        if not fused:
            return []

        docs = self._client.mget(index=KNOWLEDGE_INDEX, ids=[doc_id for doc_id, _ in fused])["docs"]
        sources = {d["_id"]: d.get("_source", {}) for d in docs if d.get("found")}
        return [
            shape_runbook(doc_id, sources.get(doc_id, {}), score)
            for doc_id, score in fused
            if doc_id in sources
        ]

    def fetch_recent_logs(self, service: str, minutes: int = 30) -> list[dict[str, Any]]:
        """Return recent application/APM log lines for a service (last ``minutes``)."""
        since = (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()
        hits = self._client.search(
            index=LOGS_INDEX,
            query={
                "bool": {
                    "filter": [
                        {"term": {"service": service}},
                        {"range": {"timestamp": {"gte": since}}},
                    ]
                }
            },
            sort=[{"timestamp": "desc"}],
            size=200,
        )["hits"]["hits"]
        return [h["_source"] for h in hits]

    def write_closure_summary(
        self, incident_id: str, summary: str, tags: list[str]
    ) -> dict[str, Any]:
        """Embed and index the resolved incident as a new, immediately-retrievable document."""
        doc = {
            "title": f"Closure: {incident_id}",
            "summary": summary,
            "root_cause": summary,
            "resolution_steps": summary,
            "tags": tags,
            "category": "closure",
            "resolved_at": datetime.now(UTC).isoformat(),
            "embedding": encode(summary),
        }
        result = self._client.index(
            index=KNOWLEDGE_INDEX, id=incident_id, document=doc, refresh=True
        )
        return {"indexed_id": result["_id"], "result": result["result"]}
