"""
database/qdrant_store.py — Qdrant vector database integration.

Provides:
  - Embedded or Docker Qdrant connection
  - Collection creation with proper vector configuration
  - Batch upsert with metadata payloads
  - Dense vector search with metadata filtering
  - Manual deletion (by manual_id filter)
  - Thread-safe singleton access
"""

from __future__ import annotations

import uuid
from typing import Optional

from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class QdrantStore:
    """
    Manages a Qdrant collection for the Industrial Manual Chatbot.

    Supports two deployment modes:
      1. Embedded (in-process, no Docker) — for development
      2. Docker/external Qdrant server — for production

    Vector config:
      - Dense vectors: 1024 dimensions (BGE-M3), cosine distance
      - Metadata payload: manual_id, filename, chapter, section, page, etc.
    """

    def __init__(self):
        self._client = None
        self._collection_name = settings.qdrant_collection
        self._images_collection_name = f"{settings.qdrant_collection}_images"

    @property
    def client(self):
        """Lazy-initialize the Qdrant client."""
        if self._client is None:
            self._connect()
        return self._client

    def _connect(self):
        """Establish connection to Qdrant (embedded or remote) with retry logic."""
        import time
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        max_retries = 5
        retry_delay = 2  # seconds between retries

        for attempt in range(1, max_retries + 1):
            try:
                if settings.qdrant_use_embedded:
                    logger.info(
                        f"Connecting to embedded Qdrant at: {settings.resolved_qdrant_path}"
                    )
                    self._client = QdrantClient(path=str(settings.resolved_qdrant_path))
                else:
                    logger.info(
                        f"Connecting to Qdrant at: "
                        f"{settings.qdrant_host}:{settings.qdrant_port}"
                    )
                    self._client = QdrantClient(
                        host=settings.qdrant_host,
                        port=settings.qdrant_port,
                    )

                # Create collection if it doesn't exist
                collections = [c.name for c in self._client.get_collections().collections]

                if self._collection_name not in collections:
                    self._client.create_collection(
                        collection_name=self._collection_name,
                        vectors_config=VectorParams(
                            size=settings.embedding_dimension,
                            distance=Distance.COSINE,
                        ),
                    )
                    logger.info(
                        f"Created Qdrant collection '{self._collection_name}' "
                        f"(dim={settings.embedding_dimension}, distance=cosine)"
                    )
                else:
                    info = self._client.get_collection(self._collection_name)
                    logger.info(
                        f"Using existing Qdrant collection '{self._collection_name}' "
                        f"({info.points_count} points)"
                    )

                # Create images collection if it doesn't exist
                if self._images_collection_name not in collections:
                    self._client.create_collection(
                        collection_name=self._images_collection_name,
                        vectors_config=VectorParams(
                            size=settings.embedding_dimension,
                            distance=Distance.COSINE,
                        ),
                    )
                    logger.info(
                        f"Created Qdrant collection '{self._images_collection_name}' "
                        f"(dim={settings.embedding_dimension}, distance=cosine)"
                    )
                else:
                    info_img = self._client.get_collection(self._images_collection_name)
                    logger.info(
                        f"Using existing Qdrant collection '{self._images_collection_name}' "
                        f"({info_img.points_count} points)"
                    )

                return  # ✅ Connected successfully

            except Exception as e:
                self._client = None
                is_lock_error = "already accessed" in str(e) or "AlreadyLocked" in str(type(e).__name__)
                if is_lock_error and attempt < max_retries:
                    logger.warning(
                        f"Qdrant storage locked (attempt {attempt}/{max_retries}). "
                        f"Waiting {retry_delay}s for previous process to release... "
                        f"(Tip: run 'pkill -f uvicorn' if this persists)"
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # exponential backoff
                else:
                    logger.error(f"Qdrant connection failed: {e}")
                    raise


    def upsert_chunks(
        self,
        chunks: list[dict],
        embeddings,
    ):
        """
        Batch upsert chunks with their embeddings into Qdrant.

        Args:
            chunks: List of chunk dicts with metadata.
            embeddings: NumPy array of shape (len(chunks), dimension).
        """
        from qdrant_client.models import PointStruct

        if len(chunks) == 0:
            return

        points = []
        for i, chunk in enumerate(chunks):
            point_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    chunk.get("chunk_id", f"chunk_{i}"),
                )
            )

            payload = {
                "chunk_id": chunk.get("chunk_id", ""),
                "manual_id": chunk.get("manual_id", ""),
                "manual_name": chunk.get("manual_name", ""),
                "filename": chunk.get("filename", ""),
                "chapter": chunk.get("chapter", ""),
                "section": chunk.get("section", ""),
                "page": chunk.get("page", 0),
                "chunk_index": chunk.get("chunk_index", 0),
                "text": chunk.get("text", ""),
                "content_type": chunk.get("content_type", "text"),
                "hierarchy_path": chunk.get("hierarchy_path", ""),
                "has_tables": chunk.get("has_tables", False),
            }

            points.append(
                PointStruct(
                    id=point_id,
                    vector=embeddings[i].tolist(),
                    payload=payload,
                )
            )

        # Batch upsert (Qdrant handles batching internally)
        batch_size = 100
        for start in range(0, len(points), batch_size):
            batch = points[start : start + batch_size]
            self.client.upsert(
                collection_name=self._collection_name,
                points=batch,
            )

        logger.info(f"Upserted {len(points)} vectors to Qdrant")

    def search(
        self,
        query_vector,
        top_k: int = 20,
        manual_ids: Optional[list[str]] = None,
        score_threshold: Optional[float] = None,
    ) -> list[dict]:
        """
        Search for similar vectors in Qdrant.

        Args:
            query_vector: Query embedding (1D array or list).
            top_k: Number of results to return.
            manual_ids: Optional filter by manual IDs.
            score_threshold: Minimum similarity score.

        Returns:
            List of result dicts with payload + relevance_score.
        """
        from qdrant_client.models import FieldCondition, Filter, MatchAny

        # Build filter
        query_filter = None
        if manual_ids:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="manual_id",
                        match=MatchAny(any=manual_ids),
                    )
                ]
            )

        results_response = self.client.query_points(
            collection_name=self._collection_name,
            query=(
                query_vector.tolist()
                if hasattr(query_vector, "tolist")
                else query_vector
            ),
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
            score_threshold=score_threshold,
        )

        output = []
        for point in results_response.points:
            item = dict(point.payload)
            item["relevance_score"] = point.score
            output.append(item)

        return output

    def upsert_images(self, images_metadata: list[dict], embeddings):
        """
        Batch upsert individual images with their CLIP embeddings into Qdrant.
        """
        from qdrant_client.models import PointStruct

        if len(images_metadata) == 0:
            return

        points = []
        for i, meta in enumerate(images_metadata):
            point_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    f"{meta.get('manual_id', '')}_{meta.get('page', 0)}_{i}",
                )
            )

            payload = {
                "manual_id": meta.get("manual_id", ""),
                "manual_name": meta.get("manual_name", ""),
                "filename": meta.get("filename", ""),
                "page": meta.get("page", 0),
                "image_path": meta.get("image_path", ""),
                "hierarchy_path": meta.get("hierarchy_path", ""),
            }

            points.append(
                PointStruct(
                    id=point_id,
                    vector=embeddings[i].tolist(),
                    payload=payload,
                )
            )

        batch_size = 100
        for start in range(0, len(points), batch_size):
            batch = points[start : start + batch_size]
            self.client.upsert(
                collection_name=self._images_collection_name,
                points=batch,
            )

        logger.info(f"Upserted {len(points)} images to Qdrant")

    def search_images(
        self,
        query_vector,
        top_k: int = 5,
        manual_ids: Optional[list[str]] = None,
        score_threshold: Optional[float] = None,
    ) -> list[dict]:
        """
        Search for images in the images collection using a CLIP text embedding.
        """
        from qdrant_client.models import FieldCondition, Filter, MatchAny

        query_filter = None
        if manual_ids:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="manual_id",
                        match=MatchAny(any=manual_ids),
                    )
                ]
            )

        results_response = self.client.query_points(
            collection_name=self._images_collection_name,
            query=(
                query_vector.tolist()
                if hasattr(query_vector, "tolist")
                else query_vector
            ),
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
            score_threshold=score_threshold,
        )

        output = []
        for point in results_response.points:
            item = dict(point.payload)
            item["relevance_score"] = point.score
            output.append(item)

        return output

    def delete_manual(self, manual_id: str):
        """Delete all vectors for a specific manual."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        manual_filter = Filter(
            must=[
                FieldCondition(
                    key="manual_id",
                    match=MatchValue(value=manual_id),
                )
            ]
        )

        try:
            # Newer qdrant-client (>=1.9) uses FilterSelector
            from qdrant_client.models import FilterSelector

            self.client.delete(
                collection_name=self._collection_name,
                points_selector=FilterSelector(filter=manual_filter),
            )
            # Delete from images collection as well
            self.client.delete(
                collection_name=self._images_collection_name,
                points_selector=FilterSelector(filter=manual_filter),
            )
        except (ImportError, TypeError):
            # Older qdrant-client accepts Filter directly
            self.client.delete(
                collection_name=self._collection_name,
                points_selector=manual_filter,
            )
            self.client.delete(
                collection_name=self._images_collection_name,
                points_selector=manual_filter,
            )
        logger.info(f"Deleted vectors for manual {manual_id}")

    def get_all_payloads(
        self,
        manual_ids: Optional[list[str]] = None,
        limit: int = 10000,
    ) -> list[dict]:
        """
        Retrieve all chunk payloads (for BM25 index rebuilding, etc.).

        Args:
            manual_ids: Optional filter.
            limit: Max number of points to retrieve.

        Returns:
            List of payload dicts.
        """
        from qdrant_client.models import FieldCondition, Filter, MatchAny

        query_filter = None
        if manual_ids:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="manual_id",
                        match=MatchAny(any=manual_ids),
                    )
                ]
            )

        # Scroll through all points
        payloads = []
        offset = None

        while True:
            results, next_offset = self.client.scroll(
                collection_name=self._collection_name,
                scroll_filter=query_filter,
                limit=min(100, limit - len(payloads)),
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            for point in results:
                payloads.append(dict(point.payload))

            if next_offset is None or len(payloads) >= limit:
                break
            offset = next_offset

        return payloads

    @property
    def total_points(self) -> int:
        """Get total number of vectors in the collection."""
        try:
            info = self.client.get_collection(self._collection_name)
            return info.points_count or 0
        except Exception:
            return 0

    @property
    def indexed_manual_ids(self) -> set[str]:
        """Get the set of all manual_ids currently indexed."""
        payloads = self.get_all_payloads(limit=50000)
        return {p.get("manual_id", "") for p in payloads if p.get("manual_id")}


# ── Singleton ────────────────────────────────────────────────────────────────

_store: Optional[QdrantStore] = None


def get_qdrant_store() -> QdrantStore:
    """Get the global QdrantStore singleton."""
    global _store
    if _store is None:
        _store = QdrantStore()
    return _store
