"""
rag/pipeline.py — Orchestrates retrieval + generation via Self-RAG.

Delegates to self_rag.py for the full 5-stage pipeline.
Kept as the public API entry point for backward compatibility.
"""

from __future__ import annotations

from typing import Generator, Optional

from app.rag.self_rag import run_self_rag_pipeline, stream_self_rag_pipeline
from app.schemas import ChatResponse


def run_rag_pipeline(
    question: str,
    manual_ids: Optional[list[str]] = None,
    top_k: Optional[int] = None,
    image_b64: Optional[str] = None,
) -> ChatResponse:
    """
    Full Self-RAG pipeline (synchronous):
      1. Classify query
      2. Retrieve top-k relevant chunks from FAISS
      3. Generate answer via Qwen3
      4. Validate answer grounding
      5. Fallback to extractive answer if needed
    """
    return run_self_rag_pipeline(
        question=question,
        manual_ids=manual_ids,
        top_k=top_k,
        image_b64=image_b64,
    )


def stream_rag_pipeline(
    question: str,
    manual_ids: Optional[list[str]] = None,
    top_k: Optional[int] = None,
    image_b64: Optional[str] = None,
) -> Generator[dict, None, None]:
    """
    Self-RAG pipeline with SSE streaming.
    Yields event dicts for real-time frontend updates.
    """
    yield from stream_self_rag_pipeline(
        question=question,
        manual_ids=manual_ids,
        top_k=top_k,
        image_b64=image_b64,
    )
