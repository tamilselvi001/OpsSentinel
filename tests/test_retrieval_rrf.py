"""Tests for the pure RRF fusion + result shaping (Phase 2, Task 5.2)."""

import importlib.util
import pathlib

_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "services"
    / "mcp-elastic"
    / "app"
    / "retrieval.py"
)
_spec = importlib.util.spec_from_file_location("retrieval", _PATH)
retrieval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(retrieval)


def test_rrf_rewards_agreement_across_rankings():
    knn = ["a", "b", "c"]
    text = ["b", "a", "d"]
    fused = retrieval.rrf_fuse([knn, text])
    ids = [doc_id for doc_id, _ in fused]
    # 'a' (ranks 1,2) and 'b' (ranks 2,1) appear in both lists and outrank single-list 'c'/'d'.
    assert set(ids[:2]) == {"a", "b"}
    assert ids[2] in {"c", "d"}


def test_rrf_single_list_preserves_order():
    fused = retrieval.rrf_fuse([["x", "y", "z"]])
    assert [doc_id for doc_id, _ in fused] == ["x", "y", "z"]


def test_rrf_scores_descending():
    fused = retrieval.rrf_fuse([["a", "b"], ["a", "c"]])
    scores = [score for _, score in fused]
    assert scores == sorted(scores, reverse=True)
    assert fused[0][0] == "a"  # only id in both lists


def test_shape_runbook_matches_contract():
    source = {
        "title": "Database Connection Limit Reached",
        "category": "Database Connection Pool",
        "root_cause": "pool exhausted",
        "resolution_steps": "restart pool",
        "commands": ["kubectl rollout restart"],
        "who_handled": "sre",
        "time_to_fix": "8m",
    }
    shaped = retrieval.shape_runbook("rb-1", source, 0.1234567)
    assert set(shaped) == {
        "id",
        "title",
        "category",
        "root_cause",
        "resolution_steps",
        "commands",
        "who_handled",
        "time_to_fix",
        "similarity_score",
    }
    assert shaped["id"] == "rb-1"
    # the canonical category is surfaced so the agent can reuse it for the Arize accuracy lookup
    assert shaped["category"] == "Database Connection Pool"
    assert shaped["similarity_score"] == 0.123457  # rounded to 6 dp
