"""
evaluation/evaluate.py — Evaluation runner for the retrieval pipeline.
"""

import time
import json
from pathlib import Path
from statistics import mean

from app.retrieval.hybrid_search import perform_hybrid_search
from app.reranker.cross_encoder import get_reranker
from evaluation.metrics import hit_rate, mrr


def run_retrieval_evaluation(test_dataset_path: str):
    """
    Run retrieval evaluation against a dataset.
    
    Dataset format:
    [
      {
        "query": "How to reset the emergency stop?",
        "expected_chunk_id": "manual_1_chunk_42"
      }
    ]
    """
    dataset_file = Path(test_dataset_path)
    if not dataset_file.exists():
        print(f"Dataset not found: {test_dataset_path}")
        return

    dataset = json.loads(dataset_file.read_text())
    print(f"Loaded {len(dataset)} test queries.\n")

    hybrid_hit_rates = []
    hybrid_mrrs = []
    
    rerank_hit_rates = []
    rerank_mrrs = []
    
    reranker = get_reranker()

    for item in dataset:
        query = item["query"]
        expected_id = item["expected_chunk_id"]

        # 1. Base Hybrid Search
        start = time.perf_counter()
        hybrid_results = perform_hybrid_search(query, top_k=20)
        hybrid_ms = (time.perf_counter() - start) * 1000
        
        hybrid_ids = [r["chunk_id"] for r in hybrid_results]
        hybrid_hit_rates.append(hit_rate(hybrid_ids[:5], expected_id))
        hybrid_mrrs.append(mrr(hybrid_ids[:5], expected_id))

        # 2. Reranked Search
        start = time.perf_counter()
        rerank_results = reranker.rerank(query, hybrid_results, top_k=5)
        rerank_ms = (time.perf_counter() - start) * 1000
        
        rerank_ids = [r["chunk_id"] for r in rerank_results]
        rerank_hit_rates.append(hit_rate(rerank_ids, expected_id))
        rerank_mrrs.append(mrr(rerank_ids, expected_id))

    print("=== Evaluation Results ===")
    print(f"Queries evaluated: {len(dataset)}")
    print(f"\n[Hybrid Search (Top-5)]")
    print(f"Hit Rate: {mean(hybrid_hit_rates):.4f}")
    print(f"MRR:      {mean(hybrid_mrrs):.4f}")
    
    print(f"\n[Hybrid + Reranker (Top-5)]")
    print(f"Hit Rate: {mean(rerank_hit_rates):.4f}")
    print(f"MRR:      {mean(rerank_mrrs):.4f}")


if __name__ == "__main__":
    # Example usage:
    # run_retrieval_evaluation("tests/data/eval_set.json")
    print("Evaluation framework ready. Create an eval_set.json to run.")
