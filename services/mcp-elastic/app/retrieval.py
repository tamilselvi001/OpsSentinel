"""Pure retrieval logic: Reciprocal Rank Fusion (RRF) + result shaping.

Kept free of any Elasticsearch / model dependency so it is unit-testable in isolation. The
Elastic client runs a KNN query over the dense-vector field AND a full-text query, then fuses
the two rankings here with RRF — so a query worded "connection pool exhausted" still surfaces a
"database connection limit reached" runbook ranked by combined signal.
"""

from __future__ import annotations

from typing import Any

RRF_K = 60  # standard RRF dampening constant


def rrf_fuse(rankings: list[list[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    """Fuse multiple ranked id-lists into one, by Reciprocal Rank Fusion.

    Each input list is ordered best-first. RRF score for a doc = sum over lists of
    ``1 / (k + rank)`` (rank is 1-based). Returns ``(doc_id, score)`` sorted best-first.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


def shape_runbook(doc_id: str, source: dict[str, Any], similarity_score: float) -> dict[str, Any]:
    """Project a knowledge document into the fixed ``search_runbooks`` return shape."""
    return {
        "id": doc_id,
        "title": source.get("title"),
        "root_cause": source.get("root_cause"),
        "resolution_steps": source.get("resolution_steps"),
        "commands": source.get("commands", []),
        "who_handled": source.get("who_handled"),
        "time_to_fix": source.get("time_to_fix"),
        "similarity_score": round(float(similarity_score), 6),
    }
