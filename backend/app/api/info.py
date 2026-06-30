"""
api/info.py — Knowledge base information endpoint.

Exposes metadata about the system's knowledge sources, AI models,
and pipeline configuration so users can understand what powers their answers.
"""

from fastapi import APIRouter

from app.core.config import get_settings
from app.database.qdrant_store import get_qdrant_store
from app.embeddings.bge_m3 import get_embedding_provider_info
from app.llm.qwen_service import is_llm_loaded
from app.reranker.cross_encoder import _loaded as reranker_loaded
from app.schemas import (IndexedManualInfo, KnowledgeBaseInfo, ModelInfo,
                         PipelineConfig)
from app.services.pdf_service import list_manuals

router = APIRouter(prefix="/info", tags=["Info"])

settings = get_settings()


@router.get("/knowledge-base", response_model=KnowledgeBaseInfo)
async def get_knowledge_base_info():
    """
    Get complete knowledge base information.

    Returns metadata about:
    - Indexed manuals (documents the LLM can reference)
    - AI models powering the system
    - RAG pipeline configuration
    - System architecture details
    """
    # ── Indexed manuals ──────────────────────────────────────────────────
    raw_manuals = list_manuals()
    manuals = [
        IndexedManualInfo(
            **m,
            size_mb=round(m.get("size_bytes", 0) / (1024 * 1024), 2),
        )
        for m in raw_manuals
    ]

    total_chunks = sum(m.chunk_count for m in manuals)

    # ── Vector DB stats ──────────────────────────────────────────────────
    try:
        qdrant = get_qdrant_store()
        total_vectors = qdrant.total_points
    except Exception:
        total_vectors = 0

    # ── AI Models ────────────────────────────────────────────────────────
    embed_info = get_embedding_provider_info()
    llm_loaded = is_llm_loaded()

    models = [
        ModelInfo(
            name=settings.embedding_model_name,
            provider=embed_info["provider"],
            model_type="embedding",
            status=(
                "loaded"
                if embed_info["loaded"] and embed_info["local_model_available"]
                else ("loaded" if embed_info["loaded"] else "loading")
            ),
            details=f"{embed_info['mode']} · {settings.embedding_dimension}d vectors",
        ),
        ModelInfo(
            name=settings.ollama_model,
            provider="ollama",
            model_type="llm",
            status="loaded" if llm_loaded else "unavailable",
            details=f"Temperature: {settings.llm_temperature} · Max tokens: {settings.llm_max_new_tokens}",
        ),
    ]

    if settings.reranker_enabled:
        models.append(
            ModelInfo(
                name=settings.reranker_model_name,
                provider="local",
                model_type="reranker",
                status="loaded" if reranker_loaded else "loading",
                details="Cross-encoder reranking for precision",
            )
        )

    # ── Pipeline config ──────────────────────────────────────────────────
    pipeline = PipelineConfig(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        retrieval_top_k=settings.retrieval_top_k,
        reranker_top_k=settings.reranker_top_k,
        hybrid_search_alpha=settings.hybrid_search_alpha,
        bm25_enabled=settings.bm25_enabled,
        reranker_enabled=settings.reranker_enabled,
        validation_enabled=settings.validation_enabled,
        classify_enabled=settings.classify_enabled,
        relevance_threshold=settings.relevance_threshold,
    )

    # ── System details ───────────────────────────────────────────────────
    vector_db = "qdrant-embedded" if settings.qdrant_use_embedded else "qdrant-remote"
    search_method = "hybrid" if settings.bm25_enabled else "vector"

    return KnowledgeBaseInfo(
        offline_mode=settings.offline_mode,
        app_name=settings.app_name,
        app_version=settings.app_version,
        manuals=manuals,
        total_manuals=len(manuals),
        total_chunks=total_chunks,
        total_vectors=total_vectors,
        models=models,
        pipeline=pipeline,
        vector_db=vector_db,
        embedding_dimension=settings.embedding_dimension,
        search_method=search_method,
    )
