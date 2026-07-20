"""
schemas/ — Pydantic request/response models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# ── Document / Manual schemas ────────────────────────────────────────────────


class ManualMetadata(BaseModel):
    manual_id: str
    filename: str
    manual_name: Optional[str] = None
    page_count: int
    chunk_count: int
    uploaded_at: datetime
    size_bytes: int


class ManualListResponse(BaseModel):
    manuals: list[ManualMetadata]
    total: int


# ── Self-RAG Pipeline schemas ────────────────────────────────────────────────


class PipelineStep(BaseModel):
    """Tracks a single stage in the Self-RAG pipeline."""

    name: str  # classify, retrieve, rerank, generate, validate, fallback
    status: Literal["completed", "skipped", "failed", "running"] = "completed"
    duration_ms: float = 0.0
    detail: Optional[str] = None


# ── Chat / Query schemas ──────────────────────────────────────────────────────


class Source(BaseModel):
    manual_id: str
    filename: str
    chapter: str
    section: str
    hierarchy_path: str
    page: Optional[int] = None
    chunk_index: int
    relevance_score: float = Field(..., ge=0.0)
    reranker_score: Optional[float] = None
    excerpt: str
    has_images: bool = False
    image_url: Optional[str] = None


class AdjacentImage(BaseModel):
    page: int
    image_url: str
    hierarchy_path: str


class ImageSource(BaseModel):
    manual_id: str
    filename: str
    page: int
    image_path: str
    image_url: str
    hierarchy_path: str
    relevance_score: float = Field(..., ge=0.0)
    adjacent_images: list[AdjacentImage] = []


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=5000)
    manual_ids: Optional[list[str]] = Field(
        default=None,
        description="Filter to specific manuals. None = search all.",
    )
    top_k: Optional[int] = Field(default=None, ge=1, le=50)
    image_b64: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    images: list[ImageSource] = []
    question: str
    processing_time_ms: float
    answer_mode: Literal["generated", "extractive_fallback", "direct"] = "generated"
    is_validated: bool = False
    pipeline_steps: list[PipelineStep] = []


# ── Source retrieval schemas ─────────────────────────────────────────────────


class PageContentResponse(BaseModel):
    manual_id: str
    page: int
    text: str
    hierarchy_path: str


class HierarchyResponse(BaseModel):
    manual_id: str
    hierarchy: dict


# ── SSE streaming event ──────────────────────────────────────────────────────


class StreamEvent(BaseModel):
    """Single SSE event sent during streaming."""

    event: str  # "stage", "token", "sources", "done", "error"
    data: dict = {}


# ── Health schema ─────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    version: str
    indexed_manuals: int
    llm_loaded: bool
    qdrant_online: bool
    offline_mode: bool = False


# ── Knowledge Base Info schemas ──────────────────────────────────────────────


class ModelInfo(BaseModel):
    """Information about a single AI model in the pipeline."""

    model_config = {"protected_namespaces": ()}

    name: str
    provider: str  # "local", "ollama", "huggingface"
    model_type: str  # "embedding", "llm", "reranker"
    status: str  # "loaded", "loading", "unavailable"
    details: Optional[str] = None


class PipelineConfig(BaseModel):
    """RAG pipeline configuration details."""

    chunk_size: int
    chunk_overlap: int
    retrieval_top_k: int
    reranker_top_k: int
    hybrid_search_alpha: float
    bm25_enabled: bool
    reranker_enabled: bool
    validation_enabled: bool
    classify_enabled: bool
    relevance_threshold: float


class IndexedManualInfo(BaseModel):
    """Summary of an indexed manual in the knowledge base."""

    manual_id: str
    filename: str
    manual_name: Optional[str] = None
    page_count: int
    chunk_count: int
    uploaded_at: datetime
    size_bytes: int
    size_mb: float = 0.0


class KnowledgeBaseInfo(BaseModel):
    """Complete knowledge base metadata response."""

    # System info
    offline_mode: bool
    app_name: str
    app_version: str

    # Indexed documents
    manuals: list[IndexedManualInfo]
    total_manuals: int
    total_chunks: int
    total_vectors: int

    # AI models
    models: list[ModelInfo]

    # Pipeline configuration
    pipeline: PipelineConfig

    # System details
    vector_db: str  # "qdrant-embedded" or "qdrant-remote"
    embedding_dimension: int
    search_method: str  # "hybrid", "vector", "bm25"
