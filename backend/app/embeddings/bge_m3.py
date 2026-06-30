"""
embeddings/bge_m3.py — BGE-M3 embedding pipeline.

Supports two providers:
  1. "local"  — In-process via FlagEmbedding (fully offline, no Ollama needed)
  2. "ollama" — Ollama HTTP API (requires Ollama running with bge-m3 pulled)

Provides:
  - Dense embeddings (1024 dimensions) for vector search
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
_loaded = False
_local_model = None  # FlagEmbedding model instance
_runtime_provider: Optional[str] = None  # Override provider at runtime if local fails


def _load_model():
    """Load the embedding model based on configured provider."""
    global _loaded, _runtime_provider
    with _lock:
        if _loaded:
            return
        provider = settings.embedding_provider.lower()

        if provider == "local":
            _load_local_model()
            # If local model failed, auto-fallback to Ollama
            if _local_model is None:
                logger.warning(
                    "Local embedding model failed to load. "
                    "Falling back to Ollama bge-m3 embeddings."
                )
                _runtime_provider = "ollama"
                _load_ollama_model()
        else:
            _runtime_provider = "ollama"
            _load_ollama_model()

        _loaded = True


def _load_local_model():
    """Load BGE-M3 model locally — sentence-transformers (preferred) or FlagEmbedding."""
    global _local_model

    logger.info(f"Loading local embedding model: {settings.embedding_model_name}")

    # Try sentence-transformers first (more compatible with current transformers versions)
    _load_sentence_transformer()
    if _local_model is not None:
        return

    # Fallback: try FlagEmbedding
    try:
        from FlagEmbedding import BGEM3FlagModel

        _local_model = BGEM3FlagModel(
            settings.embedding_model_name,
            use_fp16=False,  # CPU-safe; set True for GPU
        )
        logger.info("Local embedding model loaded successfully (FlagEmbedding)")
    except ImportError:
        logger.warning("FlagEmbedding not available either — embedding model failed to load")
    except Exception as e:
        logger.warning(f"FlagEmbedding also failed ({e}) — embedding model failed to load")


def _load_sentence_transformer():
    """Load embedding model via sentence-transformers (primary method)."""
    global _local_model
    try:
        from sentence_transformers import SentenceTransformer

        # Try offline first (cached model) to avoid DNS timeouts
        try:
            _local_model = SentenceTransformer(
                settings.embedding_model_name,
                trust_remote_code=False,
                local_files_only=True,
            )
            logger.info(
                "Local embedding model loaded successfully (sentence-transformers, cached)"
            )
            return
        except Exception:
            if settings.offline_mode:
                raise  # Don't try online in offline mode
            logger.info("Model not cached locally, attempting download...")

        # Fallback: download from HuggingFace
        _local_model = SentenceTransformer(
            settings.embedding_model_name,
            trust_remote_code=False,
        )
        logger.info(
            "Local embedding model loaded successfully (sentence-transformers)"
        )
    except TypeError as e:
        # Handle unexpected keyword argument errors (e.g., dtype)
        if "dtype" in str(e) or "unexpected keyword" in str(e):
            logger.warning(
                f"sentence-transformers dtype incompatibility: {e}. "
                "Trying with model_kwargs workaround..."
            )
            try:
                from sentence_transformers import SentenceTransformer
                import torch

                _local_model = SentenceTransformer(
                    settings.embedding_model_name,
                    model_kwargs={"torch_dtype": torch.float32},
                    trust_remote_code=False,
                    local_files_only=True,
                )
                logger.info(
                    "Local embedding model loaded (sentence-transformers with workaround)"
                )
            except Exception as e2:
                logger.error(f"All local embedding attempts failed: {e2}")
                _local_model = None
        else:
            logger.error(f"Failed to load local embedding model: {e}")
            _local_model = None
    except Exception as e:
        logger.error(f"Failed to load local embedding model: {e}")
        _local_model = None


def _wait_for_ollama(max_wait: int = 30) -> bool:
    """Wait for Ollama server to become responsive before testing models."""
    import requests
    import time

    for i in range(max_wait // 2):
        try:
            r = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=3)
            if r.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(2)
    return False


def _load_ollama_model():
    """Verify Ollama embedding model is available (with retry + backoff)."""
    import requests
    import time

    logger.info("Checking Ollama embedding model: bge-m3")

    # Wait for Ollama server to be responsive first
    if not _wait_for_ollama(max_wait=30):
        logger.warning(
            "Ollama server not reachable during startup. "
            "Embeddings will be attempted on first use."
        )
        return

    # Retry the embedding test with exponential backoff
    # First attempt needs extra time — Ollama cold-loads bge-m3 (~2GB) on first call
    max_retries = 3
    timeouts = [90, 60, 60]  # 1st attempt generous for cold load, then shorter
    delay = 5

    # Brief warm-up delay — give Ollama time to finish initializing after /api/tags responds
    time.sleep(3)

    for attempt in range(1, max_retries + 1):
        try:
            attempt_timeout = timeouts[attempt - 1]
            logger.info(
                f"Ollama embedding check attempt {attempt}/{max_retries} "
                f"(timeout={attempt_timeout}s)..."
            )
            res = requests.post(
                f"{settings.ollama_base_url}/api/embed",
                json={"model": "bge-m3", "input": ["test"]},
                timeout=attempt_timeout,
            )
            if res.status_code == 200:
                logger.info("Ollama embedding model 'bge-m3' is ready.")
                return
            else:
                logger.warning(
                    f"Ollama embedding check attempt {attempt}/{max_retries} "
                    f"returned status {res.status_code}: {res.text[:200]}"
                )
        except requests.RequestException as e:
            logger.warning(
                f"Ollama embedding check attempt {attempt}/{max_retries} failed: {e}"
            )

        if attempt < max_retries:
            time.sleep(delay)
            delay *= 2  # exponential backoff

    logger.warning(
        "Ollama embedding model not confirmed during startup. "
        "It will be loaded on first embedding request."
    )


def _get_effective_provider() -> str:
    """Get the effective provider (may differ from config if local failed)."""
    if _runtime_provider:
        return _runtime_provider
    return settings.embedding_provider.lower()


def get_model():
    """Trigger lazy load."""
    if not _loaded:
        _load_model()
    return _local_model or "ollama-bge-m3"


def get_embedding_provider_info() -> dict:
    """Return info about the current embedding provider for the info API."""
    effective = _get_effective_provider()
    return {
        "provider": effective,
        "model_name": settings.embedding_model_name,
        "dimension": settings.embedding_dimension,
        "loaded": _loaded,
        "local_model_available": _local_model is not None,
        "mode": "in-process" if effective == "local" and _local_model is not None else "ollama-http",
    }


class BGEM3Embedder:
    """
    BGE-M3 embedding pipeline — supports local and Ollama backends.

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
        return settings.embedding_dimension

    @property
    def provider(self) -> str:
        return _get_effective_provider()

    def embed_documents(
        self,
        texts: list[str],
        batch_size: int = settings.embedding_batch_size,
    ) -> np.ndarray:
        if not texts:
            return np.array([])

        # Ensure model is loaded
        self.model

        if self.provider == "local" and _local_model is not None:
            return self._embed_local(texts, batch_size)
        else:
            return self._embed_ollama(texts, batch_size)

    def embed_query(self, text: str) -> np.ndarray:
        self.model

        if self.provider == "local" and _local_model is not None:
            return self._query_local(text)
        else:
            return self._query_ollama(text)

    def _embed_local(self, texts: list[str], batch_size: int) -> np.ndarray:
        """Embed via local FlagEmbedding or sentence-transformers model."""
        try:
            from FlagEmbedding import BGEM3FlagModel

            if isinstance(_local_model, BGEM3FlagModel):
                # FlagEmbedding returns dict with 'dense_vecs'
                output = _local_model.encode(
                    texts,
                    batch_size=batch_size,
                    max_length=512,
                )
                if isinstance(output, dict):
                    return np.array(output["dense_vecs"], dtype=np.float32)
                return np.array(output, dtype=np.float32)
        except (ImportError, AttributeError):
            pass

        # sentence-transformers fallback
        try:
            embeddings = _local_model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            return np.array(embeddings, dtype=np.float32)
        except Exception as e:
            logger.error(f"Local embedding failed, falling back to Ollama: {e}")
            # If local embedding fails at runtime, try Ollama as last resort
            return self._embed_ollama(texts, batch_size)

    def _query_local(self, text: str) -> np.ndarray:
        """Embed a single query via local model."""
        result = self._embed_local([text], batch_size=1)
        if len(result) > 0:
            return result[0]
        raise RuntimeError("Local embedding returned empty result")

    def _embed_ollama(self, texts: list[str], batch_size: int) -> np.ndarray:
        """Embed via Ollama HTTP API."""
        import requests

        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                res = requests.post(
                    f"{settings.ollama_base_url}/api/embed",
                    json={"model": "bge-m3", "input": batch},
                    timeout=30,
                )
                res.raise_for_status()
                data = res.json()
                all_embeddings.extend(data.get("embeddings", []))
            except Exception as e:
                logger.error(f"Ollama embedding failed for batch: {e}")
                all_embeddings.extend([[0.0] * self.dimension for _ in batch])

        return np.array(all_embeddings, dtype=np.float32)

    def _query_ollama(self, text: str) -> np.ndarray:
        """Embed a single query via Ollama HTTP API."""
        import requests

        try:
            res = requests.post(
                f"{settings.ollama_base_url}/api/embed",
                json={"model": "bge-m3", "input": [text]},
                timeout=10,
            )
            res.raise_for_status()
            data = res.json()
            embeddings = data.get("embeddings", [])
            if embeddings:
                return np.array(embeddings[0], dtype=np.float32)
        except Exception as e:
            logger.error(f"Ollama embedding query failed: {e}")
            raise RuntimeError(
                "Embedding model not loaded or Ollama is unavailable"
            ) from e

        raise RuntimeError("No embedding returned from Ollama")

    def embed_with_sparse(
        self,
        texts: list[str],
        batch_size: int = settings.embedding_batch_size,
    ) -> dict:
        embeddings = self.embed_documents(texts, batch_size=batch_size)
        return {
            "dense": embeddings,
            "sparse": [],  # Sparse embeddings not used in current pipeline
        }


# ── Singleton ────────────────────────────────────────────────────────────────

_embedder: Optional[BGEM3Embedder] = None


def get_embedder() -> BGEM3Embedder:
    """Get the global BGEM3Embedder singleton."""
    global _embedder
    if _embedder is None:
        _embedder = BGEM3Embedder()
    return _embedder
