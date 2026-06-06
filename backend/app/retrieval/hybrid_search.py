"""
retrieval/hybrid_search.py — Combines Vector (Qdrant) and Keyword (BM25) search.

Uses Reciprocal Rank Fusion (RRF) or normalized score combination
to merge results from both dense and sparse retrieval methods.
"""

from __future__ import annotations
from typing import Optional

from loguru import logger

from app.core.config import get_settings
from app.database.qdrant_store import get_qdrant_store
from app.embeddings.bge_m3 import get_embedder
from app.retrieval.bm25 import get_bm25_index

settings = get_settings()


def _normalize_scores(results: list[dict], score_key: str = "relevance_score") -> list[dict]:
    """Min-max normalize scores to [0, 1] range."""
    if not results:
        return results

    scores = [r[score_key] for r in results]
    min_score = min(scores)
    max_score = max(scores)

    if max_score == min_score:
        for r in results:
            r["normalized_score"] = 1.0
        return results

    for r in results:
        r["normalized_score"] = (r[score_key] - min_score) / (max_score - min_score)

    return results


def _rrf_fusion(vector_results: list[dict], bm25_results: list[dict], k: int = 60) -> list[dict]:
    """
    Reciprocal Rank Fusion (RRF).
    RRF_score = 1 / (k + rank)
    """
    fused_scores: dict[str, float] = {}
    items: dict[str, dict] = {}

    # Rank vector results
    for rank, item in enumerate(vector_results, start=1):
        chunk_id = item["chunk_id"]
        items[chunk_id] = item
        fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + (1.0 / (k + rank))

    # Rank BM25 results
    for rank, item in enumerate(bm25_results, start=1):
        chunk_id = item["chunk_id"]
        if chunk_id not in items:
            items[chunk_id] = item
        fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + (1.0 / (k + rank))

    # Reconstruct list and sort by fused score
    fused_list = []
    for chunk_id, score in fused_scores.items():
        item = dict(items[chunk_id])
        item["relevance_score"] = score  # overwrite with RRF score
        item["search_type"] = "hybrid_rrf"
        fused_list.append(item)

    fused_list.sort(key=lambda x: x["relevance_score"], reverse=True)
    return fused_list


def _linear_fusion(
    vector_results: list[dict],
    bm25_results: list[dict],
    alpha: float = settings.hybrid_search_alpha,
) -> list[dict]:
    """
    Linear combination of normalized scores.
    Final = alpha * vector_norm + (1-alpha) * bm25_norm
    """
    v_norm = _normalize_scores(vector_results)
    b_norm = _normalize_scores(bm25_results)

    fused_scores: dict[str, float] = {}
    items: dict[str, dict] = {}

    for item in v_norm:
        chunk_id = item["chunk_id"]
        items[chunk_id] = item
        fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + (alpha * item["normalized_score"])

    for item in b_norm:
        chunk_id = item["chunk_id"]
        if chunk_id not in items:
            items[chunk_id] = item
        fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + ((1.0 - alpha) * item["normalized_score"])

    # Reconstruct list and sort by fused score
    fused_list = []
    for chunk_id, score in fused_scores.items():
        item = dict(items[chunk_id])
        item["relevance_score"] = score
        item["search_type"] = "hybrid_linear"
        item.pop("normalized_score", None)
        fused_list.append(item)

    fused_list.sort(key=lambda x: x["relevance_score"], reverse=True)
    return fused_list


class HybridSearchEngine:
    """Executes Vector, BM25, or Hybrid search."""

    def __init__(self):
        self.qdrant = get_qdrant_store()
        self.embedder = get_embedder()
        self.bm25 = get_bm25_index()

    def search(
        self,
        query: str,
        top_k: int = settings.retrieval_top_k,
        manual_ids: Optional[list[str]] = None,
        method: str = "hybrid",  # "vector", "bm25", "hybrid"
    ) -> list[dict]:
        """
        Perform a search query.

        Args:
            query: The search text.
            top_k: Number of results to return.
            manual_ids: Filter by manual IDs.
            method: 'vector', 'bm25', or 'hybrid'.
        """
        # 1. Vector Search
        vector_results = []
        if method in ("vector", "hybrid"):
            query_vec = self.embedder.embed_query(query)
            # Fetch more for fusion
            fetch_k = top_k * 2 if method == "hybrid" else top_k
            vector_results = self.qdrant.search(
                query_vector=query_vec,
                top_k=fetch_k,
                manual_ids=manual_ids,
            )
            for r in vector_results:
                r["search_type"] = "vector"

        # 2. BM25 Search
        bm25_results = []
        if method in ("bm25", "hybrid") and settings.bm25_enabled:
            fetch_k = top_k * 2 if method == "hybrid" else top_k
            bm25_results = self.bm25.search(
                query=query,
                top_k=fetch_k,
                manual_ids=manual_ids,
            )
            for r in bm25_results:
                r["search_type"] = "bm25"

        # 3. Fusion
        if method == "hybrid" and vector_results and bm25_results:
            # We use RRF by default as it's more robust without precise tuning
            results = _rrf_fusion(vector_results, bm25_results)
            logger.debug(
                f"Hybrid fusion: {len(vector_results)} vector + {len(bm25_results)} BM25 "
                f"→ {len(results)} total"
            )
        elif method == "hybrid" and vector_results:
            results = vector_results
        elif method == "hybrid" and bm25_results:
            results = bm25_results
        elif method == "vector":
            results = vector_results
        elif method == "bm25":
            results = bm25_results
        else:
            results = []

        return results[:top_k]


def perform_hybrid_search(
    query: str,
    top_k: int = settings.retrieval_top_k,
    manual_ids: Optional[list[str]] = None,
) -> list[dict]:
    """Convenience function for hybrid search."""
    engine = HybridSearchEngine()
    method = "hybrid" if settings.bm25_enabled else "vector"
    return engine.search(query, top_k=top_k, manual_ids=manual_ids, method=method)
