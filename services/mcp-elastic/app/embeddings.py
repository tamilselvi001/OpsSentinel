"""Embedding helper — loads ``all-MiniLM-L6-v2`` once and caches it.

384-dimensional space, ~100 ms encode — the spec's chosen intersection of latency and precision
for operational logs (and the mitigation for the context-retrieval-latency risk against the 30s
MTTD target). Not substituted for a larger/slower model. Heavy import is lazy so the rest of the
package imports cheaply.
"""

from __future__ import annotations

from functools import lru_cache

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMS = 384


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def encode(text: str) -> list[float]:
    """Encode text into a normalized 384-dim vector (cosine-ready)."""
    vector = _model().encode(text, normalize_embeddings=True)
    return vector.tolist()
