"""
embeddings/bge_m3.py — BGE-M3 embedding pipeline.

Provides:
  - Dense embeddings (1024 dimensions) for vector search
  - Sparse token weights for BM25-style keyword matching
  - Batch processing with configurable batch size
  - GPU/CPU auto-detection with graceful fallback
  - Thread-safe singleton access
"""

from __future__ import annotations
import threading
from typing import Optional

import numpy as np
from loguru import logger

from app.core.config import get_settings

settings = get_settings()

_lock = threading.Lock()
_model = None
_loaded = False


def _load_model():
    """Load the BGE-M3 model (lazy, thread-safe)."""
    global _model, _loaded
    with _lock:
        if _loaded:
            return
        try:
            logger.info(f"Loading embedding model: {settings.embedding_model_name}")

            # Try FlagEmbedding first (official BGE-M3 implementation)
            try:
                from FlagEmbedding import BGEM3FlagModel
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
                logger.info(f"Using FlagEmbedding on device: {device}")

                _model = BGEM3FlagModel(
                    settings.embedding_model_name,
                    use_fp16=(device == "cuda"),
                )
                _loaded = True
                logger.info("BGE-M3 loaded via FlagEmbedding")
                return

            except ImportError:
                logger.info("FlagEmbedding not available, trying sentence-transformers")

            # Fallback: sentence-transformers
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(settings.embedding_model_name)
            _loaded = True
            logger.info("BGE-M3 loaded via sentence-transformers")

        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            _loaded = True  # prevent retry loops


def get_model():
    """Get the loaded embedding model."""
    if not _loaded:
        _load_model()
    return _model


def is_flag_model() -> bool:
    """Check if the loaded model is a FlagEmbedding BGEM3FlagModel."""
    model = get_model()
    if model is None:
        return False
    return type(model).__name__ == "BGEM3FlagModel"


class BGEM3Embedder:
    """
    BGE-M3 embedding pipeline for the Industrial Manual Chatbot.

    Supports two modes:
      1. FlagEmbedding BGEM3FlagModel — produces dense + sparse embeddings
      2. sentence-transformers SentenceTransformer — produces dense only

    Usage:
        embedder = BGEM3Embedder()
        dense_vecs = embedder.embed_documents(["text1", "text2"])
        query_vec = embedder.embed_query("search query")
    """

    def __init__(self):
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = get_model()
        return self._model

    @property
    def dimension(self) -> int:
        """Return the dense embedding dimension."""
        return settings.embedding_dimension

    def embed_documents(
        self,
        texts: list[str],
        batch_size: int = settings.embedding_batch_size,
    ) -> np.ndarray:
        """
        Embed a list of document texts.

        Args:
            texts: List of text strings to embed.
            batch_size: Batch size for processing.

        Returns:
            NumPy array of shape (len(texts), dimension).
        """
        if not texts:
            return np.array([])

        model = self.model
        if model is None:
            raise RuntimeError("Embedding model not loaded")

        if is_flag_model():
            # FlagEmbedding: returns dict with 'dense_vecs'
            output = model.encode(
                texts,
                batch_size=batch_size,
                max_length=512,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            embeddings = output["dense_vecs"]
        else:
            # sentence-transformers
            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
            )

        return np.array(embeddings, dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        """
        Embed a single query text.

        Returns:
            1D NumPy array of shape (dimension,).
        """
        model = self.model
        if model is None:
            raise RuntimeError("Embedding model not loaded")

        if is_flag_model():
            output = model.encode(
                [text],
                batch_size=1,
                max_length=512,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            return np.array(output["dense_vecs"][0], dtype=np.float32)
        else:
            embedding = model.encode(
                [text],
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            return np.array(embedding[0], dtype=np.float32)

    def embed_with_sparse(
        self,
        texts: list[str],
        batch_size: int = settings.embedding_batch_size,
    ) -> dict:
        """
        Embed texts and return both dense and sparse representations.

        Only available with FlagEmbedding backend.

        Returns:
            {
                "dense": np.ndarray (N x dimension),
                "sparse": list[dict] (token → weight mappings)
            }
        """
        model = self.model
        if model is None:
            raise RuntimeError("Embedding model not loaded")

        if is_flag_model():
            output = model.encode(
                texts,
                batch_size=batch_size,
                max_length=512,
                return_dense=True,
                return_sparse=True,
                return_colbert_vecs=False,
            )
            return {
                "dense": np.array(output["dense_vecs"], dtype=np.float32),
                "sparse": output.get("lexical_weights", []),
            }
        else:
            # Fallback: dense only
            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            return {
                "dense": np.array(embeddings, dtype=np.float32),
                "sparse": [],
            }


# ── Singleton ────────────────────────────────────────────────────────────────

_embedder: Optional[BGEM3Embedder] = None


def get_embedder() -> BGEM3Embedder:
    """Get the global BGEM3Embedder singleton."""
    global _embedder
    if _embedder is None:
        _embedder = BGEM3Embedder()
    return _embedder
