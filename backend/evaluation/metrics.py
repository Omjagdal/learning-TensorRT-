"""
evaluation/metrics.py — Information Retrieval and LLM evaluation metrics.
"""

from __future__ import annotations


def hit_rate(retrieved_chunk_ids: list[str], ground_truth_chunk_id: str) -> float:
    """Returns 1.0 if the ground truth chunk is in the retrieved chunks, else 0.0."""
    return 1.0 if ground_truth_chunk_id in retrieved_chunk_ids else 0.0


def mrr(retrieved_chunk_ids: list[str], ground_truth_chunk_id: str) -> float:
    """Mean Reciprocal Rank. 1/rank if found, else 0."""
    try:
        rank = retrieved_chunk_ids.index(ground_truth_chunk_id) + 1
        return 1.0 / rank
    except ValueError:
        return 0.0


def precision_at_k(retrieved_chunk_ids: list[str], relevant_chunk_ids: set[str], k: int) -> float:
    """Precision@K: Proportion of retrieved chunks in top-K that are relevant."""
    if not retrieved_chunk_ids or k <= 0:
        return 0.0
    
    top_k = retrieved_chunk_ids[:k]
    relevant_retrieved = sum(1 for chunk_id in top_k if chunk_id in relevant_chunk_ids)
    return relevant_retrieved / len(top_k)


def recall_at_k(retrieved_chunk_ids: list[str], relevant_chunk_ids: set[str], k: int) -> float:
    """Recall@K: Proportion of total relevant chunks that are in top-K."""
    if not relevant_chunk_ids or k <= 0:
        return 0.0
        
    top_k = retrieved_chunk_ids[:k]
    relevant_retrieved = sum(1 for chunk_id in top_k if chunk_id in relevant_chunk_ids)
    return relevant_retrieved / len(relevant_chunk_ids)
