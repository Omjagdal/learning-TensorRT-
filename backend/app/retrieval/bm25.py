"""
retrieval/bm25.py — BM25 keyword search implementation.

Uses the rank_bm25 library for exact-keyword and sparse term matching.
Maintains an in-memory index built from chunks retrieved from Qdrant.
"""

from __future__ import annotations
import threading
from typing import Optional

from rank_bm25 import BM25Okapi
from loguru import logger

from app.core.config import get_settings
from app.database.qdrant_store import get_qdrant_store

settings = get_settings()

_lock = threading.Lock()
_bm25_index: Optional['BM25Index'] = None


def tokenize(text: str) -> list[str]:
    """
    Simple tokenizer for BM25.
    Lowercase, remove punctuation, split by whitespace.
    """
    import string
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    return text.split()


class BM25Index:
    """
    In-memory BM25 index for keyword search.

    Built by loading payloads from Qdrant. Rebuilt when manuals are added/removed.
    """

    def __init__(self):
        self.bm25: Optional[BM25Okapi] = None
        self.corpus: list[dict] = []
        self._manual_ids: set[str] = set()

    def build_from_qdrant(self):
        """Fetch all payloads from Qdrant and build the BM25 index."""
        store = get_qdrant_store()
        payloads = store.get_all_payloads()

        if not payloads:
            self.bm25 = None
            self.corpus = []
            self._manual_ids = set()
            logger.info("BM25 Index: No documents to index.")
            return

        self.corpus = payloads
        self._manual_ids = {p["manual_id"] for p in payloads if "manual_id" in p}

        tokenized_corpus = [tokenize(p.get("text", "")) for p in payloads]
        self.bm25 = BM25Okapi(tokenized_corpus)
        logger.info(f"BM25 Index built with {len(self.corpus)} chunks.")

    def search(
        self,
        query: str,
        top_k: int = 20,
        manual_ids: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Search the BM25 index.

        Args:
            query: The search query string.
            top_k: Number of top results to return.
            manual_ids: Optional filter by manual IDs.

        Returns:
            List of result dicts with payload + relevance_score.
        """
        if self.bm25 is None or not self.corpus:
            return []

        tokenized_query = tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-K indices (we fetch more initially if filtering)
        k = len(scores) if manual_ids else top_k
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score <= 0.0:
                continue

            item = dict(self.corpus[idx])

            # Apply manual_id filter
            if manual_ids and item.get("manual_id") not in manual_ids:
                continue

            item["relevance_score"] = score
            results.append(item)

            if len(results) >= top_k:
                break

        return results


def get_bm25_index() -> BM25Index:
    """Get the global BM25Index singleton."""
    global _bm25_index
    with _lock:
        if _bm25_index is None:
            _bm25_index = BM25Index()
            _bm25_index.build_from_qdrant()
        return _bm25_index


def rebuild_bm25_index():
    """Force a rebuild of the BM25 index."""
    global _bm25_index
    with _lock:
        if _bm25_index is None:
            _bm25_index = BM25Index()
        _bm25_index.build_from_qdrant()
