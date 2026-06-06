"""
rag/self_rag.py — Self-Reflective RAG pipeline (v2).

Now a 6-stage pipeline:
  1. CLASSIFY  — Does this query need retrieval?
  2. RETRIEVE  — Hybrid search (Vector + BM25 via Qdrant)
  3. RERANK    — Cross-encoder reranking (BGE-Reranker-Large)
  4. GENERATE  — Answer from context (Ollama Qwen3)
  5. VALIDATE  — Is the answer grounded in context?
  6. FALLBACK  — Extractive answer from chunks
"""

from __future__ import annotations
import time
from typing import Optional, Generator

from loguru import logger

from app.core.config import get_settings
from app.retrieval.hybrid_search import perform_hybrid_search
from app.reranker.cross_encoder import get_reranker
from app.llm.qwen_service import (
    classify_query,
    generate_answer,
    generate_direct_answer,
    validate_answer,
    is_llm_loaded,
    generate_stream,
)
from app.schemas import ChatResponse, Source, PipelineStep

settings = get_settings()


# ── Stage helpers ─────────────────────────────────────────────────────────────

def _timed(fn, *args, **kwargs):
    """Run a function and return (result, elapsed_ms)."""
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = (time.perf_counter() - t0) * 1000
    return result, round(elapsed, 1)


def _build_sources(chunks: list[dict]) -> list[Source]:
    """Convert retrieved chunks to Source schema objects."""
    return [
        Source(
            manual_id=c["manual_id"],
            filename=c["filename"],
            chapter=c.get("chapter", "Unknown"),
            section=c.get("section", "General"),
            hierarchy_path=c.get("hierarchy_path", ""),
            page=c.get("page"),
            chunk_index=c["chunk_index"],
            relevance_score=round(c.get("relevance_score", 0), 4),
            reranker_score=round(c.get("reranker_score", 0), 4) if "reranker_score" in c else None,
            excerpt=c["text"][:300] + ("…" if len(c["text"]) > 300 else ""),
        )
        for c in chunks
    ]


# ── Self-RAG pipeline ────────────────────────────────────────────────────────

def run_self_rag_pipeline(
    question: str,
    manual_ids: Optional[list[str]] = None,
    top_k: Optional[int] = None,
) -> ChatResponse:
    """
    Full Self-RAG pipeline:
      1. Classify query
      2. Retrieve (Hybrid Search)
      3. Rerank (Cross-Encoder)
      4. Generate answer via Qwen3
      5. Validate answer grounding
      6. Fallback to extractive
    """
    start = time.perf_counter()
    retrieval_k = settings.retrieval_top_k
    final_k = top_k or settings.reranker_top_k
    
    steps: list[PipelineStep] = []
    
    # ── Step 1: CLASSIFY ──────────────────────────────────────────────────
    if settings.classify_enabled and is_llm_loaded():
        classification, cls_ms = _timed(classify_query, question)
        steps.append(PipelineStep(
            name="classify",
            status="completed",
            duration_ms=cls_ms,
            detail=classification,
        ))
        logger.info(f"[Self-RAG] Classify: {classification} ({cls_ms:.0f}ms)")

        if classification == "DIRECT":
            answer, gen_ms = _timed(generate_direct_answer, question)
            steps.append(PipelineStep(name="generate", status="completed", duration_ms=gen_ms, detail="direct"))
            elapsed_ms = (time.perf_counter() - start) * 1000
            return ChatResponse(
                answer=answer, sources=[], question=question,
                processing_time_ms=round(elapsed_ms, 1), answer_mode="direct",
                is_validated=False, pipeline_steps=steps,
            )
    else:
        steps.append(PipelineStep(name="classify", status="skipped", detail="LLM not loaded"))

    # ── Step 2: RETRIEVE (Hybrid) ──────────────────────────────────────────
    retrieve_start = time.perf_counter()
    chunks = perform_hybrid_search(question, top_k=retrieval_k, manual_ids=manual_ids)
    retrieve_ms = round((time.perf_counter() - retrieve_start) * 1000, 1)
    
    steps.append(PipelineStep(
        name="retrieve", status="completed", duration_ms=retrieve_ms,
        detail=f"{len(chunks)} chunks (Hybrid)",
    ))
    logger.info(f"[Self-RAG] Retrieve: {len(chunks)} chunks ({retrieve_ms:.0f}ms)")

    if not chunks:
        steps.append(PipelineStep(name="generate", status="skipped", detail="No chunks"))
        elapsed_ms = (time.perf_counter() - start) * 1000
        return ChatResponse(
            answer="No relevant information found in the indexed manuals for your query.",
            sources=[], question=question, processing_time_ms=round(elapsed_ms, 1),
            answer_mode="extractive_fallback", is_validated=False, pipeline_steps=steps,
        )

    # ── Step 3: RERANK ────────────────────────────────────────────────────
    if settings.reranker_enabled:
        reranker = get_reranker()
        reranked_chunks, rerank_ms = _timed(reranker.rerank, question, chunks, top_k=final_k)
        use_chunks = reranked_chunks
        
        steps.append(PipelineStep(
            name="rerank", status="completed", duration_ms=rerank_ms,
            detail=f"top {final_k} from {len(chunks)}",
        ))
        logger.info(f"[Self-RAG] Rerank: {len(use_chunks)} chunks ({rerank_ms:.0f}ms)")
    else:
        use_chunks = chunks[:final_k]
        steps.append(PipelineStep(name="rerank", status="skipped", detail="Disabled"))

    # ── Step 4: GENERATE ──────────────────────────────────────────────────
    answer, gen_ms = _timed(generate_answer, question, use_chunks)
    steps.append(PipelineStep(name="generate", status="completed", duration_ms=gen_ms, detail=f"{len(answer)} chars"))
    logger.info(f"[Self-RAG] Generate: {len(answer)} chars ({gen_ms:.0f}ms)")

    # ── Step 5: VALIDATE ──────────────────────────────────────────────────
    is_validated = False
    answer_mode = "generated"

    if settings.validation_enabled and is_llm_loaded():
        validation, val_ms = _timed(validate_answer, question, use_chunks, answer)
        steps.append(PipelineStep(name="validate", status="completed", duration_ms=val_ms, detail=validation))
        logger.info(f"[Self-RAG] Validate: {validation} ({val_ms:.0f}ms)")

        if validation in ("PASS", "PARTIAL"):
            is_validated = True
        elif validation == "FAIL":
            # ── Step 6: FALLBACK ──────────────────────────────────────────
            logger.info("[Self-RAG] Validation failed → extractive fallback")
            answer = _extractive_fallback(question, use_chunks)
            answer_mode = "extractive_fallback"
            steps.append(PipelineStep(name="fallback", status="completed", detail="Validation failed"))
    else:
        steps.append(PipelineStep(name="validate", status="skipped", detail="Disabled"))

    # ── Build response ────────────────────────────────────────────────────
    sources = _build_sources(use_chunks)
    elapsed_ms = (time.perf_counter() - start) * 1000

    return ChatResponse(
        answer=answer,
        sources=sources,
        question=question,
        processing_time_ms=round(elapsed_ms, 1),
        answer_mode=answer_mode,
        is_validated=is_validated,
        pipeline_steps=steps,
    )


# ── Streaming Self-RAG ───────────────────────────────────────────────────────

def stream_self_rag_pipeline(
    question: str,
    manual_ids: Optional[list[str]] = None,
    top_k: Optional[int] = None,
) -> Generator[dict, None, None]:
    """Self-RAG pipeline with SSE streaming (yields event dicts)."""
    start = time.perf_counter()
    retrieval_k = settings.retrieval_top_k
    final_k = top_k or settings.reranker_top_k

    # ── Step 1: CLASSIFY ──────────────────────────────────────────────────
    yield {"event": "stage", "data": {"stage": "classify", "status": "running"}}

    if settings.classify_enabled and is_llm_loaded():
        classification, cls_ms = _timed(classify_query, question)
        yield {
            "event": "stage",
            "data": {"stage": "classify", "status": "completed", "result": classification, "duration_ms": cls_ms},
        }

        if classification == "DIRECT":
            yield {"event": "stage", "data": {"stage": "generate", "status": "running"}}
            answer, gen_ms = _timed(generate_direct_answer, question)
            yield {"event": "token", "data": {"text": answer}}
            yield {"event": "stage", "data": {"stage": "generate", "status": "completed", "duration_ms": gen_ms}}
            elapsed_ms = (time.perf_counter() - start) * 1000
            yield {
                "event": "done",
                "data": {"answer_mode": "direct", "is_validated": False, "sources": [], "processing_time_ms": round(elapsed_ms, 1)},
            }
            return
    else:
        yield {"event": "stage", "data": {"stage": "classify", "status": "skipped"}}

    # ── Step 2: RETRIEVE (Hybrid) ──────────────────────────────────────────
    yield {"event": "stage", "data": {"stage": "retrieve", "status": "running"}}

    retrieve_start = time.perf_counter()
    chunks = perform_hybrid_search(question, top_k=retrieval_k, manual_ids=manual_ids)
    retrieve_ms = round((time.perf_counter() - retrieve_start) * 1000, 1)

    yield {
        "event": "stage",
        "data": {"stage": "retrieve", "status": "completed", "duration_ms": retrieve_ms, "chunk_count": len(chunks)},
    }

    if not chunks:
        yield {"event": "token", "data": {"text": "No relevant information found in the indexed manuals for your query."}}
        elapsed_ms = (time.perf_counter() - start) * 1000
        yield {
            "event": "done",
            "data": {"answer_mode": "extractive_fallback", "is_validated": False, "sources": [], "processing_time_ms": round(elapsed_ms, 1)},
        }
        return

    # ── Step 3: RERANK ────────────────────────────────────────────────────
    if settings.reranker_enabled:
        yield {"event": "stage", "data": {"stage": "rerank", "status": "running"}}
        reranker = get_reranker()
        use_chunks, rerank_ms = _timed(reranker.rerank, question, chunks, top_k=final_k)
        yield {
            "event": "stage",
            "data": {"stage": "rerank", "status": "completed", "duration_ms": rerank_ms, "chunk_count": len(use_chunks)},
        }
    else:
        use_chunks = chunks[:final_k]
        yield {"event": "stage", "data": {"stage": "rerank", "status": "skipped"}}

    # ── Step 4: GENERATE (streaming) ──────────────────────────────────────
    yield {"event": "stage", "data": {"stage": "generate", "status": "running"}}

    gen_start = time.perf_counter()
    full_answer = ""
    for token in generate_stream(question, use_chunks):
        full_answer += token
        yield {"event": "token", "data": {"text": token}}

    gen_ms = round((time.perf_counter() - gen_start) * 1000, 1)
    yield {"event": "stage", "data": {"stage": "generate", "status": "completed", "duration_ms": gen_ms}}

    # ── Step 5: VALIDATE ──────────────────────────────────────────────────
    is_validated = False
    answer_mode = "generated"

    if settings.validation_enabled and is_llm_loaded():
        yield {"event": "stage", "data": {"stage": "validate", "status": "running"}}
        validation, val_ms = _timed(validate_answer, question, use_chunks, full_answer)
        yield {
            "event": "stage",
            "data": {"stage": "validate", "status": "completed", "result": validation, "duration_ms": val_ms},
        }

        if validation in ("PASS", "PARTIAL"):
            is_validated = True
        elif validation == "FAIL":
            yield {"event": "stage", "data": {"stage": "fallback", "status": "running"}}
            full_answer = _extractive_fallback(question, use_chunks)
            answer_mode = "extractive_fallback"
            yield {"event": "token", "data": {"text": full_answer, "replace": True}}
            yield {"event": "stage", "data": {"stage": "fallback", "status": "completed"}}
    else:
        yield {"event": "stage", "data": {"stage": "validate", "status": "skipped"}}

    # ── Final event ───────────────────────────────────────────────────────
    sources = _build_sources(use_chunks)
    elapsed_ms = (time.perf_counter() - start) * 1000

    yield {
        "event": "done",
        "data": {
            "answer_mode": answer_mode,
            "is_validated": is_validated,
            "sources": [s.model_dump() for s in sources],
            "processing_time_ms": round(elapsed_ms, 1),
        },
    }


def _extractive_fallback(question: str, chunks: list[dict]) -> str:
    """Extractive fallback."""
    if not chunks:
        return "No relevant information found."
    parts = ["Based on the manual excerpts, here is the relevant information:\n"]
    for chunk in chunks[:3]:
        page = chunk.get("page", "?")
        path = chunk.get("hierarchy_path", chunk.get("filename", ""))
        parts.append(f"\n**From [{path}, Page {page}]:**\n{chunk['text'][:500]}…")
    return "\n".join(parts)
