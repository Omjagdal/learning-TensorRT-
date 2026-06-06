"""
rag/vector_store.py — FAISS-backed vector store with sentence-transformer embeddings.
"""

from __future__ import annotations
import json
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from loguru import logger

from app.core.config import get_settings

settings = get_settings()

INDEX_FILE = settings.faiss_index_dir / "index.faiss"
CHUNKS_MAP_FILE = settings.faiss_index_dir / "chunks_map.pkl"


class VectorStore:
    """
    Manages a FAISS index alongside a list of chunk metadata dicts.
    Thread-safe for read operations; write operations should be called at startup.
    """

    def __init__(self):
        self._model: Optional[SentenceTransformer] = None
        self._index: Optional[faiss.IndexFlatIP] = None
        self._chunks: list[dict] = []  # parallel to index rows
        self._dim: int = 0

    # ── Lazy model loading ────────────────────────────────────────────────────

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info(f"Loading embedding model: {settings.embedding_model_name}")
            self._model = SentenceTransformer(settings.embedding_model_name)
            self._dim = self._model.get_sentence_embedding_dimension()
            logger.info(f"Embedding dimension: {self._dim}")
        return self._model

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self):
        settings.faiss_index_dir.mkdir(parents=True, exist_ok=True)
        if self._index is not None:
            faiss.write_index(self._index, str(INDEX_FILE))
            with open(CHUNKS_MAP_FILE, "wb") as f:
                pickle.dump(self._chunks, f)
            logger.info(f"Saved FAISS index ({len(self._chunks)} vectors)")

    def load(self) -> bool:
        if INDEX_FILE.exists() and CHUNKS_MAP_FILE.exists():
            self._index = faiss.read_index(str(INDEX_FILE))
            with open(CHUNKS_MAP_FILE, "rb") as f:
                self._chunks = pickle.load(f)
            self._dim = self._index.d
            logger.info(f"Loaded FAISS index ({len(self._chunks)} vectors)")
            return True
        return False

    # ── Indexing ──────────────────────────────────────────────────────────────

    def _embed(self, texts: list[str]) -> np.ndarray:
        embeddings = self.model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,  # cosine similarity via inner product
        )
        return embeddings.astype(np.float32)

    def build_index(self, chunks: list[dict]):
        """Build a fresh FAISS index from all chunks."""
        if not chunks:
            logger.warning("No chunks provided — skipping index build")
            return

        texts = [c["text"] for c in chunks]
        logger.info(f"Embedding {len(texts)} chunks …")
        embeddings = self._embed(texts)

        dim = embeddings.shape[1]
        self._index = faiss.IndexFlatIP(dim)  # Inner-product (cosine with normed vecs)
        self._index.add(embeddings)
        self._chunks = list(chunks)
        self.save()
        logger.info("FAISS index built and saved")

    def add_chunks(self, new_chunks: list[dict]):
        """Incrementally add chunks to an existing index."""
        if not new_chunks:
            return
        texts = [c["text"] for c in new_chunks]
        embeddings = self._embed(texts)

        if self._index is None:
            self._index = faiss.IndexFlatIP(embeddings.shape[1])

        self._index.add(embeddings)
        self._chunks.extend(new_chunks)
        self.save()
        logger.info(f"Added {len(new_chunks)} chunks — total {len(self._chunks)}")

    def remove_manual(self, manual_id: str):
        """
        FAISS flat index doesn't support deletion natively.
        Rebuild the index excluding the given manual_id.
        """
        remaining = [c for c in self._chunks if c["manual_id"] != manual_id]
        logger.info(
            f"Rebuilding index without manual {manual_id} "
            f"({len(self._chunks) - len(remaining)} chunks removed)"
        )
        if remaining:
            self.build_index(remaining)
        else:
            self._index = None
            self._chunks = []
            INDEX_FILE.unlink(missing_ok=True)
            CHUNKS_MAP_FILE.unlink(missing_ok=True)

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = settings.top_k_results,
        manual_ids: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Returns top-k most relevant chunks for the query.
        Optionally filtered to a subset of manuals.
        """
        if self._index is None or self._index.ntotal == 0:
            return []

        query_emb = self._embed([query])
        k = min(top_k * 4, self._index.ntotal)  # over-fetch for post-filter
        scores, indices = self._index.search(query_emb, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            chunk = dict(self._chunks[idx])
            if manual_ids and chunk["manual_id"] not in manual_ids:
                continue
            chunk["relevance_score"] = float(score)
            results.append(chunk)
            if len(results) >= top_k:
                break

        return results

    @property
    def total_chunks(self) -> int:
        return len(self._chunks)

    @property
    def indexed_manual_ids(self) -> set[str]:
        return {c["manual_id"] for c in self._chunks}


# Singleton
_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
        if not _store.load():
            logger.info("No existing FAISS index found — will build on first upload")
    return _store
