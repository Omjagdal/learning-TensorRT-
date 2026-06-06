"""
schemas/ — Pydantic request/response models.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Literal
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


class UploadResponse(BaseModel):
    message: str
    manual_id: str
    filename: str
    chunk_count: int


class DeleteResponse(BaseModel):
    message: str
    manual_id: str


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


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    manual_ids: Optional[list[str]] = Field(
        default=None,
        description="Filter to specific manuals. None = search all.",
    )
    top_k: Optional[int] = Field(default=None, ge=1, le=50)


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
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
