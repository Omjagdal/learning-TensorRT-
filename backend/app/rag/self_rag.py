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
from typing import Generator, Optional

from loguru import logger

from app.core.config import get_settings
from app.database.qdrant_store import get_qdrant_store
from app.embeddings.bge_m3 import get_embedder as get_bge_embedder
from app.llm.qwen_service import (classify_query, generate_answer,
                                  generate_direct_answer, generate_stream,
                                  is_llm_loaded, validate_answer,
                                  generate_caption_for_base64_image,
                                  )

from app.services.pdf_service import get_image_path
import base64
from app.reranker.cross_encoder import get_reranker
from app.retrieval.hybrid_search import perform_hybrid_search
from app.schemas import ChatResponse, ImageSource, PipelineStep, Source, AdjacentImage

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
    sources = []
    for c in chunks:
        page = c.get("page")
        manual_id = c["manual_id"]
        
        has_images = c.get("has_images", False)
        images_referenced = c.get("images_referenced", [])
        
        image_url = None
        if has_images and images_referenced:
            img_name = images_referenced[0]
            image_path = f"{manual_id}_images/{img_name}"
            image_url = f"/api/v1/images/{image_path}"

        sources.append(
            Source(
                manual_id=manual_id,
                filename=c["filename"],
                chapter=c.get("chapter", "Unknown"),
                section=c.get("section", "General"),
                hierarchy_path=c.get("hierarchy_path", ""),
                page=page,
                chunk_index=c["chunk_index"],
                relevance_score=round(c.get("relevance_score", 0), 4),
                reranker_score=(
                    round(c.get("reranker_score", 0), 4)
                    if "reranker_score" in c
                    else None
                ),
                excerpt=c["text"][:300] + ("…" if len(c["text"]) > 300 else ""),
                has_images=has_images,
                image_url=image_url,
            )
        )
    return sources


def _get_base64_from_image_sources(image_sources: list[ImageSource]) -> list[str]:
    b64_images = []
    for img in image_sources:
        try:
            abs_path = get_image_path(img.image_path)
            if abs_path and abs_path.exists():
                with open(abs_path, "rb") as f:
                    b64_images.append(base64.b64encode(f.read()).decode("utf-8"))
        except Exception as e:
            logger.warning(f"Could not load image {img.image_path}: {e}")
    return b64_images
def _get_adjacent_images(
    manual_id: str,
    base_page: int,
    filename: str,
    hierarchy_path: str
) -> list[AdjacentImage]:
    try:
        images_dir = settings.upload_dir / f"{manual_id}_images"
        if not images_dir.exists():
            return []
            
        all_images = list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg"))
        if len(all_images) <= 50:
            return []
            
        adjacent = []
        start_page = max(0, base_page - 5)
        for p in range(start_page, base_page + 5):
            if p == base_page:
                continue
                
            matching = [img for img in all_images if img.stem == f"page_{p}" or img.stem.startswith(f"page_{p}_")]
            for img in matching:
                image_path = f"{manual_id}_images/{img.name}"
                adjacent.append(
                    AdjacentImage(
                        page=p,
                        image_url=f"/api/v1/images/{image_path}",
                        hierarchy_path=hierarchy_path,
                    )
                )
        return adjacent
    except Exception as e:
        logger.warning(f"Failed to fetch adjacent images: {e}")
        return []


def _retrieve_images(
    query: str, manual_ids: Optional[list[str]] = None, top_k: int = 4
) -> list[ImageSource]:
    """Retrieve semantically relevant images using BGE-M3 search on captions."""
    try:
        qdrant = get_qdrant_store()

        # Check if images collection has any points before searching
        try:
            img_collection = qdrant.client.get_collection(
                f"{qdrant._collection_name}_images"
            )
            if (img_collection.points_count or 0) == 0:
                return []
        except Exception:
            return []

        bge = get_bge_embedder()
        query_vec = bge.embed_query(query)

        results = qdrant.search_images(
            query_vector=query_vec,
            top_k=top_k,
            manual_ids=manual_ids,
            score_threshold=0.15, # Lower threshold to return images more frequently
        )

        images = []
        seen_paths = set()
        for r in results:
            image_path = r.get("image_path", "")
            if not image_path or image_path in seen_paths:
                continue
                
            manual_id = r.get("manual_id", "")
            page = r.get("page", 0)
            filename = r.get("filename", "")
            hierarchy_path = r.get("hierarchy_path", "")
            
            main_img = ImageSource(
                manual_id=manual_id,
                filename=filename,
                page=page,
                image_path=image_path,
                image_url=f"/api/v1/images/{image_path}" if image_path else "",
                hierarchy_path=hierarchy_path,
                relevance_score=round(r.get("relevance_score", 0), 4),
            )
            
            # Fetch adjacent images if manual > 50 images
            adj_images = _get_adjacent_images(
                manual_id=manual_id,
                base_page=page,
                filename=filename,
                hierarchy_path=hierarchy_path
            )
            main_img.adjacent_images = adj_images
            
            images.append(main_img)
            seen_paths.add(image_path)
            
        return images
    except Exception as e:
        logger.error(f"Failed to retrieve images: {e}")
        return []


# ── Self-RAG pipeline ────────────────────────────────────────────────────────


def run_self_rag_pipeline(
    question: str,
    manual_ids: Optional[list[str]] = None,
    top_k: Optional[int] = None,
    image_b64: Optional[str] = None,
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

    # ── Step 0: MULTIMODAL CAPTIONING ──────────────────────────────────────
    if image_b64:
        caption = generate_caption_for_base64_image(image_b64)
        if caption:
            question = f"User uploaded an image showing: {caption}\n\nQuestion: {question}"

    # ── Step 1: CLASSIFY ──────────────────────────────────────────────────
    if settings.classify_enabled and is_llm_loaded():
        classification, cls_ms = _timed(classify_query, question)
        steps.append(
            PipelineStep(
                name="classify",
                status="completed",
                duration_ms=cls_ms,
                detail=classification,
            )
        )
        logger.info(f"[Self-RAG] Classify: {classification} ({cls_ms:.0f}ms)")

        if classification == "DIRECT":

            # DIRECT text answer — but ALWAYS try to retrieve manual context first
            # This is the safety net: even if classified as DIRECT, check if the
            # manual has relevant content and use it if so.
            image_sources = []

            # Attempt retrieval — if the manual has relevant chunks, use them
            direct_chunks = []
            try:
                direct_chunks = perform_hybrid_search(
                    question, top_k=retrieval_k, manual_ids=manual_ids
                )
            except Exception as e:
                logger.warning(f"[Self-RAG] DIRECT path retrieval failed: {e}")

            if direct_chunks:
                # Manual has relevant context — use it for a grounded answer
                logger.info(
                    f"[Self-RAG] DIRECT query has {len(direct_chunks)} manual chunks — "
                    f"answering from manual context instead of direct generation"
                )
                answer, gen_ms = _timed(generate_answer, question, direct_chunks[:final_k])
                final_sources = _build_sources(direct_chunks[:final_k])
                answer_mode = "generated"
            else:
                # Truly no manual content — pure greeting/small-talk
                answer, gen_ms = _timed(generate_direct_answer, question)
                final_sources = []
                answer_mode = "direct"

            steps.append(
                PipelineStep(
                    name="generate",
                    status="completed",
                    duration_ms=gen_ms,
                    detail=answer_mode,
                )
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            return ChatResponse(
                answer=answer,
                sources=final_sources,
                images=image_sources,
                question=question,
                processing_time_ms=round(elapsed_ms, 1),
                answer_mode=answer_mode,
                is_validated=False,
                pipeline_steps=steps,
            )

    else:
        steps.append(
            PipelineStep(name="classify", status="skipped", detail="LLM not loaded")
        )

    # ── Step 2: RETRIEVE (Hybrid) ──────────────────────────────────────────
    retrieve_start = time.perf_counter()
    chunks = perform_hybrid_search(question, top_k=retrieval_k, manual_ids=manual_ids)
    retrieve_ms = round((time.perf_counter() - retrieve_start) * 1000, 1)

    steps.append(
        PipelineStep(
            name="retrieve",
            status="completed",
            duration_ms=retrieve_ms,
            detail=f"{len(chunks)} chunks (Hybrid)",
        )
    )
    logger.info(f"[Self-RAG] Retrieve: {len(chunks)} chunks ({retrieve_ms:.0f}ms)")

    if not chunks:
        steps.append(
            PipelineStep(name="generate", status="skipped", detail="No chunks")
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        return ChatResponse(
            answer="No relevant information found in the indexed manuals for your query.",
            sources=[],
            images=[],
            question=question,
            processing_time_ms=round(elapsed_ms, 1),
            answer_mode="extractive_fallback",
            is_validated=False,
            pipeline_steps=steps,
        )

    # ── Step 2.5: RETRIEVE IMAGES (CLIP) ──────────────────────────────────
    image_sources = _retrieve_images(question, manual_ids=manual_ids)

    # ── Step 3: RERANK ────────────────────────────────────────────────────
    if settings.reranker_enabled:
        reranker = get_reranker()
        reranked_chunks, rerank_ms = _timed(
            reranker.rerank, question, chunks, top_k=final_k
        )
        use_chunks = reranked_chunks

        steps.append(
            PipelineStep(
                name="rerank",
                status="completed",
                duration_ms=rerank_ms,
                detail=f"top {final_k} from {len(chunks)}",
            )
        )
        logger.info(f"[Self-RAG] Rerank: {len(use_chunks)} chunks ({rerank_ms:.0f}ms)")
    else:
        use_chunks = chunks[:final_k]
        steps.append(PipelineStep(name="rerank", status="skipped", detail="Disabled"))

    # ── Step 4: GENERATE ──────────────────────────────────────────────────
    answer, gen_ms = _timed(generate_answer, question, use_chunks, bool(image_sources))
        
    steps.append(
        PipelineStep(
            name="generate",
            status="completed",
            duration_ms=gen_ms,
            detail=f"{len(answer)} chars",
        )
    )
    logger.info(f"[Self-RAG] Generate: {len(answer)} chars ({gen_ms:.0f}ms)")

    # ── Step 5: VALIDATE ──────────────────────────────────────────────────
    is_validated = False
    answer_mode = "generated"

    if settings.validation_enabled and is_llm_loaded():
        validation, val_ms = _timed(validate_answer, question, use_chunks, answer)
        steps.append(
            PipelineStep(
                name="validate",
                status="completed",
                duration_ms=val_ms,
                detail=validation,
            )
        )
        logger.info(f"[Self-RAG] Validate: {validation} ({val_ms:.0f}ms)")

        if validation in ("PASS", "PARTIAL"):
            is_validated = True
        elif validation == "FAIL":
            # ── Step 6: FALLBACK ──────────────────────────────────────────
            logger.info("[Self-RAG] Validation failed → extractive fallback")
            answer = _extractive_fallback(question, use_chunks)
            answer_mode = "extractive_fallback"
            steps.append(
                PipelineStep(
                    name="fallback", status="completed", detail="Validation failed"
                )
            )
    else:
        steps.append(PipelineStep(name="validate", status="skipped", detail="Disabled"))

    # ── Build response ────────────────────────────────────────────────────
    final_sources = _build_sources(use_chunks)
    final_answer = answer
    elapsed_ms = (time.perf_counter() - start) * 1000

    return ChatResponse(
        answer=final_answer,
        sources=final_sources,
        images=image_sources,
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
    image_b64: Optional[str] = None,
) -> Generator[dict, None, None]:
    """Self-RAG pipeline with SSE streaming (yields event dicts)."""
    start = time.perf_counter()
    retrieval_k = settings.retrieval_top_k
    final_k = top_k or settings.reranker_top_k

    # ── Step 0: MULTIMODAL CAPTIONING ──────────────────────────────────────
    if image_b64:
        yield {"event": "stage", "data": {"stage": "analyze_image", "status": "running"}}
        caption = generate_caption_for_base64_image(image_b64)
        if caption:
            question = f"User uploaded an image showing: {caption}\n\nQuestion: {question}"
        yield {"event": "stage", "data": {"stage": "analyze_image", "status": "completed"}}

    # ── Step 1: CLASSIFY ──────────────────────────────────────────────────
    yield {"event": "stage", "data": {"stage": "classify", "status": "running"}}

    if settings.classify_enabled and is_llm_loaded():
        classification, cls_ms = _timed(classify_query, question)
        yield {
            "event": "stage",
            "data": {
                "stage": "classify",
                "status": "completed",
                "result": classification,
                "duration_ms": cls_ms,
            },
        }

        if classification == "DIRECT":

            # DIRECT text answer — ALWAYS try to retrieve manual context first (safety net)
            image_sources = []
            yield {"event": "images", "data": []}

            # Attempt retrieval — if manual has relevant chunks, use them
            direct_chunks = []
            try:
                yield {"event": "stage", "data": {"stage": "retrieve", "status": "running"}}
                direct_chunks = perform_hybrid_search(
                    question, top_k=retrieval_k, manual_ids=manual_ids
                )
                yield {
                    "event": "stage",
                    "data": {
                        "stage": "retrieve",
                        "status": "completed",
                        "chunk_count": len(direct_chunks),
                    },
                }
            except Exception as e:
                logger.warning(f"[Self-RAG] Streaming DIRECT path retrieval failed: {e}")
                yield {"event": "stage", "data": {"stage": "retrieve", "status": "skipped"}}

            yield {"event": "stage", "data": {"stage": "generate", "status": "running"}}

            if direct_chunks:
                # Manual has relevant context — stream answer from manual
                logger.info(
                    f"[Self-RAG] Streaming DIRECT query has {len(direct_chunks)} manual chunks "
                    f"— streaming from manual context"
                )
                gen_start = time.perf_counter()
                full_answer = ""
                for token in generate_stream(question, direct_chunks[:final_k]):
                    full_answer += token
                    yield {"event": "token", "data": {"text": token}}
                gen_ms = round((time.perf_counter() - gen_start) * 1000, 1)
                answer_mode = "generated"
                final_sources = _build_sources(direct_chunks[:final_k])
            else:
                # Truly a greeting — no manual content needed
                answer, gen_ms = _timed(generate_direct_answer, question)
                yield {"event": "token", "data": {"text": answer}}
                answer_mode = "direct"
                final_sources = []

            yield {
                "event": "stage",
                "data": {"stage": "generate", "status": "completed", "duration_ms": gen_ms},
            }
            elapsed_ms = (time.perf_counter() - start) * 1000
            yield {
                "event": "done",
                "data": {
                    "answer_mode": answer_mode,
                    "is_validated": False,
                    "sources": [s.model_dump() for s in final_sources],
                    "images": [img.model_dump() for img in image_sources],
                    "processing_time_ms": round(elapsed_ms, 1),
                },
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
        "data": {
            "stage": "retrieve",
            "status": "completed",
            "duration_ms": retrieve_ms,
            "chunk_count": len(chunks),
        },
    }

    if not chunks:
        yield {
            "event": "token",
            "data": {
                "text": "No relevant information found in the indexed manuals for your query."
            },
        }
        elapsed_ms = (time.perf_counter() - start) * 1000
        yield {
            "event": "done",
            "data": {
                "answer_mode": "extractive_fallback",
                "is_validated": False,
                "sources": [],
                "processing_time_ms": round(elapsed_ms, 1),
            },
        }
        return

    # ── Step 3: RERANK ────────────────────────────────────────────────────
    
    # ── Step 3.5: RETRIEVE IMAGES ─────────────────────────────────────────
    image_sources = _retrieve_images(question, manual_ids=manual_ids)
    
    yield {"event": "images", "data": [img.model_dump() for img in image_sources]}

    if settings.reranker_enabled:
        yield {"event": "stage", "data": {"stage": "rerank", "status": "running"}}
        reranker = get_reranker()
        use_chunks, rerank_ms = _timed(reranker.rerank, question, chunks, top_k=final_k)
        yield {
            "event": "stage",
            "data": {
                "stage": "rerank",
                "status": "completed",
                "duration_ms": rerank_ms,
                "chunk_count": len(use_chunks),
            },
        }
    else:
        use_chunks = chunks[:final_k]
        yield {"event": "stage", "data": {"stage": "rerank", "status": "skipped"}}

    # ── Step 4: GENERATE (streaming) ──────────────────────────────────────
    yield {"event": "stage", "data": {"stage": "generate", "status": "running"}}

    gen_start = time.perf_counter()
    full_answer = ""
    for token in generate_stream(question, use_chunks, has_images=bool(image_sources)):
        full_answer += token
        yield {"event": "token", "data": {"text": token}}

    gen_ms = round((time.perf_counter() - gen_start) * 1000, 1)
    yield {
        "event": "stage",
        "data": {"stage": "generate", "status": "completed", "duration_ms": gen_ms},
    }

    # ── Step 5: VALIDATE ──────────────────────────────────────────────────
    is_validated = False
    answer_mode = "generated"

    if settings.validation_enabled and is_llm_loaded():
        yield {"event": "stage", "data": {"stage": "validate", "status": "running"}}
        validation, val_ms = _timed(validate_answer, question, use_chunks, full_answer)
        yield {
            "event": "stage",
            "data": {
                "stage": "validate",
                "status": "completed",
                "result": validation,
                "duration_ms": val_ms,
            },
        }

        if validation in ("PASS", "PARTIAL"):
            is_validated = True
        elif validation == "FAIL":
            yield {"event": "stage", "data": {"stage": "fallback", "status": "running"}}
            full_answer = _extractive_fallback(question, use_chunks)
            answer_mode = "extractive_fallback"
            yield {"event": "token", "data": {"text": full_answer, "replace": True}}
            yield {
                "event": "stage",
                "data": {"stage": "fallback", "status": "completed"},
            }
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
            "images": [img.model_dump() for img in image_sources],
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
