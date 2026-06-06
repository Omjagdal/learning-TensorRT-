"""
main.py — FastAPI application entry point.
"""

from contextlib import asynccontextmanager
import threading
import logging as builtin_logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.api.manuals import router as manuals_router
from app.api.chat import router as chat_router
from app.api.stream import router as stream_router
from app.api.sources import router as sources_router
from app.database.qdrant_store import get_qdrant_store
from app.retrieval.bm25 import get_bm25_index
from app.indexing.page_index import get_page_index
from app.llm.qwen_service import _load_hf_pipeline, is_llm_loaded
from app.embeddings.bge_m3 import _load_model as load_embedding_model
from app.reranker.cross_encoder import _load_model as load_reranker_model
from app.services.pdf_service import list_manuals, get_chunks_for_manual
from app.schemas import HealthResponse

settings = get_settings()


class InterceptHandler(builtin_logging.Handler):
    """Route standard logging to loguru."""
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = builtin_logging.currentframe(), 2
        while frame.f_code.co_filename == builtin_logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup logging
    setup_logging(settings.debug)
    builtin_logging.basicConfig(handlers=[InterceptHandler()], level=0)
    
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    # 1. Initialize Vector Store (Qdrant)
    store = get_qdrant_store()
    logger.info(f"Connected to Qdrant. Total points: {store.total_points}")
    
    # 2. Rebuild BM25 Index
    bm25 = get_bm25_index()
    
    # 3. Load Hierarchical PageIndex
    page_index = get_page_index()
    manuals = list_manuals()
    for m in manuals:
        mid = m["manual_id"]
        chunks = get_chunks_for_manual(mid)
        if chunks:
            page_index.load(mid, chunks)

    # 4. Background model loading
    # Load ML models in background so server starts instantly
    threading.Thread(target=load_embedding_model, daemon=True).start()
    
    if settings.reranker_enabled:
        threading.Thread(target=load_reranker_model, daemon=True).start()
        
    if settings.llm_fallback_enabled:
        threading.Thread(target=_load_hf_pipeline, daemon=True).start()

    yield

    logger.info("Shutting down …")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Hierarchical PageIndex RAG chatbot for industrial machine manuals",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(manuals_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(stream_router, prefix="/api/v1")
app.include_router(sources_router, prefix="/api/v1")


@app.get("/api/v1/health", response_model=HealthResponse, tags=["Health"])
async def health():
    store = get_qdrant_store()
    manuals = list_manuals()
    
    try:
        qdrant_online = store.client is not None
    except Exception:
        qdrant_online = False
        
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        indexed_manuals=len(manuals),
        llm_loaded=is_llm_loaded(),
        qdrant_online=qdrant_online,
    )


@app.get("/", tags=["Root"])
async def root():
    return {"message": f"Welcome to {settings.app_name}", "docs": "/docs"}
