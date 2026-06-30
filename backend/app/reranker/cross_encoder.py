"""
reranker/cross_encoder.py — BGE-Reranker-Large cross-encoder integration.

Takes a query and a list of candidate chunks, scores each (query, chunk) pair,
and returns the top-K most relevant chunks. Greatly improves precision over
standard dense retrieval.
"""

from __future__ import annotations

import threading
from typing import Optional

from loguru import logger

from app.core.config import get_settings

settings = get_settings()

_lock = threading.Lock()
_model = None
_loaded = False


def _load_model():
    """Load the BGE-Reranker model (lazy, thread-safe)."""
    global _model, _loaded
    with _lock:
        if _loaded:
            return
        try:
            logger.info(f"Loading reranker model: {settings.reranker_model_name}")

            # Use sentence-transformers CrossEncoder
            import torch
            from sentence_transformers import CrossEncoder

            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using reranker on device: {device}")

            try:
                # Try offline mode first to prevent DNS timeouts if already downloaded
                _model = CrossEncoder(
                    settings.reranker_model_name,
                    device=device,
                    max_length=512,
                    local_files_only=True,
                )
            except Exception:
                if settings.offline_mode:
                    raise  # Don't try online download in offline mode
                logger.info("Reranker model not found locally, attempting to download from HuggingFace...")
                # Fallback to online mode for first-time downloads
                _model = CrossEncoder(
                    settings.reranker_model_name,
                    device=device,
                    max_length=512,
                    local_files_only=False,
                )
            
            _loaded = True
            logger.info("Reranker loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load reranker model: {e}")
            _loaded = True  # prevent retry loops


def get_model():
    """Get the loaded reranker model."""
    if not _loaded:
        _load_model()
    return _model


class RerankerEngine:
    """
    Cross-encoder reranking for the Industrial Manual Chatbot.
    """

    def __init__(self):
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = get_model()
        return self._model

    def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int = settings.reranker_top_k,
    ) -> list[dict]:
        """
        Rerank a list of candidate chunks against a query.

        Args:
            query: The user's search query.
            candidates: List of chunk dicts (e.g., from hybrid_search).
            top_k: Number of top results to return.

        Returns:
            List of chunk dicts sorted by reranker score, truncated to top_k.
        """
        if not candidates or not settings.reranker_enabled:
            return candidates[:top_k]

        model = self.model
        if model is None:
            logger.warning("Reranker model not loaded, skipping reranking")
            return candidates[:top_k]

        # Prepare sentence pairs: (query, document)
        sentence_pairs = [[query, chunk["text"]] for chunk in candidates]

        # Compute scores
        # BGE-Reranker outputs logits, higher is more similar
        try:
            scores = model.predict(sentence_pairs, batch_size=16)
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return candidates[:top_k]

        # Attach scores and sort
        for item, score in zip(candidates, scores):
            item["reranker_score"] = float(score)

        # Sort by reranker score (descending)
        reranked = sorted(candidates, key=lambda x: x["reranker_score"], reverse=True)

        return reranked[:top_k]


# ── Singleton ────────────────────────────────────────────────────────────────

_reranker: Optional[RerankerEngine] = None


def get_reranker() -> RerankerEngine:
    """Get the global RerankerEngine singleton."""
    global _reranker
    if _reranker is None:
        _reranker = RerankerEngine()
    return _reranker
