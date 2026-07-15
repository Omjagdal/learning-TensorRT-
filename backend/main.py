"""
main.py — FastAPI application entry point.
Supports three run modes:
  1. Development  — plain `python main.py` with system Ollama
  2. Docker       — headless, DOCKER_ENV=true, Ollama is external
  3. Desktop .exe — PyInstaller frozen, OllamaManager starts bundled Ollama
"""

import sys
import os
import traceback
from pathlib import Path

def _write_crash_log(e):
    try:
        desktop = Path.home() / "Desktop" / "isra_crash.txt"
        with open(desktop, "w") as f:
            f.write("ISRA Chatbot Crash Log\n")
            f.write("========================\n")
            f.write(traceback.format_exc())
    except:
        pass

try:
    # ── PyInstaller / Frozen-app path setup ──────────────────────────────────────
    # CRITICAL: Must happen BEFORE importing ANYTHING from app.* so env vars are in place
    # before pydantic-settings reads them or before module-level code runs mkdir().
    _IS_FROZEN = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")

if _IS_FROZEN:
    _bundle_root = Path(sys.executable).parent
    import platformdirs

    # ── PORTABLE MODE: check for models/ folder next to the .exe ──────────────
    _portable_models = _bundle_root / "models"
    _portable_ollama  = _portable_models / "ollama_models"
    _portable_hf      = _portable_models / "hf_cache"
    _is_portable_mode = _portable_models.exists()

    # ── INSTALLED MODE: use AppData\Local\ISRAVision\ISRAChatbot ──────────────
    _user_data = Path(platformdirs.user_data_dir("ISRAChatbot", "ISRAVision"))
    _user_data.mkdir(parents=True, exist_ok=True)

    if _is_portable_mode and _portable_hf.exists():
        _hf_cache = _portable_hf
    else:
        _hf_cache = _user_data / "hf_cache"
        _hf_cache.mkdir(parents=True, exist_ok=True)

    if _is_portable_mode and _portable_ollama.exists():
        _ollama_models_dir = _portable_ollama
    else:
        _ollama_models_dir = _user_data / "ollama_models"
        _ollama_models_dir.mkdir(parents=True, exist_ok=True)

    os.environ["HF_HOME"] = str(_hf_cache)
    os.environ["TRANSFORMERS_CACHE"] = str(_hf_cache / "hub")
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(_hf_cache / "sentence_transformers")
    os.environ.setdefault("OLLAMA_MODELS", str(_ollama_models_dir))

    os.environ.setdefault("QDRANT_EMBEDDED_PATH", str(_user_data / "qdrant_storage"))
    os.environ.setdefault("UPLOAD_DIR", str(_user_data / "manuals"))
    os.environ["MARKER_TELEMETRY"] = "false"
    os.environ["PADDLE_OCR_DOWNLOAD"] = "false"

    _hf_models_ready = (_hf_cache / "hub" / "models--BAAI--bge-reranker-large").exists()
    if _hf_models_ready:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_DATASETS_OFFLINE"] = "1"

# Now we can safely import our app modules, because os.environ is fully populated.
from contextlib import asynccontextmanager
import threading
import logging as builtin_logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.api.manuals import router as manuals_router
from app.api.chat import router as chat_router
from app.api.stream import router as stream_router
from app.api.sources import router as sources_router
from app.api.images import router as images_router
from app.api.info import router as info_router
from app.database.qdrant_store import get_qdrant_store
from app.retrieval.bm25 import get_bm25_index
from app.indexing.page_index import get_page_index
from app.llm.qwen_service import _load_hf_pipeline, is_llm_loaded
from app.embeddings.bge_m3 import _load_model as load_embedding_model
from app.reranker.cross_encoder import _load_model as load_reranker_model
from app.services.pdf_service import list_manuals, get_chunks_for_manual
from app.schemas import HealthResponse

settings = get_settings()

if settings.offline_mode and not _IS_FROZEN:
    # Development offline mode — same guards, but paths already correct
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    os.environ["MARKER_TELEMETRY"] = "false"
    os.environ["PADDLE_OCR_DOWNLOAD"] = "false"


class InterceptHandler(builtin_logging.Handler):
    """Route standard logging to loguru, filtering noisy health checks."""
    def emit(self, record):
        # Suppress repetitive health check access logs
        msg = record.getMessage()
        if "/api/v1/health" in msg:
            return
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
    
    # Suppress verbose HuggingFace logs
    builtin_logging.getLogger("sentence_transformers").setLevel(builtin_logging.WARNING)
    builtin_logging.getLogger("transformers").setLevel(builtin_logging.WARNING)
    
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

    # 4. Eagerly import heavy ML libraries on main thread
    try:
        import torch
        import transformers
        import sentence_transformers
    except ImportError:
        pass

    # 5. Background model loading
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

# CORS — include self-hosted origin for desktop mode
all_origins = settings.origins_list
self_origin = f"http://127.0.0.1:{settings.port}"
if self_origin not in all_origins:
    all_origins.append(self_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=all_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(manuals_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(stream_router, prefix="/api/v1")
app.include_router(sources_router, prefix="/api/v1")
app.include_router(images_router, prefix="/api/v1")
app.include_router(info_router, prefix="/api/v1")


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
        offline_mode=settings.offline_mode,
    )


if _IS_FROZEN:
    # PyInstaller --onedir: frontend/dist is bundled alongside the .exe
    frontend_dist = Path(sys.executable).parent / "frontend" / "dist"
else:
    # Development: standard relative path from the backend folder
    frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"

if frontend_dist.exists():
    # Serve all static assets from the dist folder (JS, CSS, images, logo.png)
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    # Serve any file directly from dist root (e.g. logo.png, favicon.ico)
    @app.get("/{filename}.{ext}", tags=["Frontend"])
    async def serve_static_file(filename: str, ext: str):
        file_path = frontend_dist / f"{filename}.{ext}"
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(frontend_dist / "index.html"))

    @app.get("/{catchall:path}", tags=["Frontend"])
    async def serve_frontend(catchall: str):
        if catchall.startswith("api/"):
            return {"detail": "Not Found"}
        index_path = frontend_dist / "index.html"
        if not index_path.exists():
            return {"message": "Frontend not built. Run 'npm run build' in frontend dir."}
        return FileResponse(str(index_path))
else:
    @app.get("/", tags=["Root"])
    async def root():
        return {"message": f"Welcome to {settings.app_name}. Frontend not built.", "docs": "/docs"}


if __name__ == "__main__":
    import multiprocessing
    import time
    import requests
    import uvicorn

    # ── PyInstaller freeze support (must be first) ─────────────────────────────
    multiprocessing.freeze_support()

    # ── Detect Docker headless mode ───────────────────────────────────────────
    is_docker = os.environ.get("DOCKER_ENV") == "true"

    # ── Desktop mode: start Ollama via OllamaManager ──────────────────────────
    if not is_docker:
        from app.core.ollama_manager import start_ollama, stop_ollama
        import webview

        logger.info("Desktop mode — initializing Ollama manager...")
        ollama_ok = start_ollama()
        if not ollama_ok:
            logger.warning(
                "Ollama could not be started. The LLM will be unavailable. "
                "Check that the bundled Ollama binary and models are present."
            )

    # ── Server runner ─────────────────────────────────────────────────────────
    def run_server():
        """Start the FastAPI/Uvicorn server."""
        logger.info("Starting FastAPI server via Uvicorn...")
        host = "0.0.0.0" if is_docker else "127.0.0.1"
        uvicorn.run(
            app,
            host=host,
            port=settings.port,
            workers=1,
            log_config=None,
        )

    if is_docker:
        # Docker: run blocking on the main thread
        run_server()
    else:
        # Desktop: run server in background thread, open native window
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        # ── Wait for server to become healthy ─────────────────────────────────
        server_url = f"http://127.0.0.1:{settings.port}"
        logger.info(f"Waiting for server at {server_url}...")
        for _ in range(60):
            try:
                if requests.get(server_url + "/api/v1/health", timeout=1).status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(0.5)

        # ── Open native desktop window ─────────────────────────────────────────
        logger.info("Opening native desktop window...")
        window = webview.create_window(
            settings.app_name,
            server_url,
            width=1400,
            height=860,
            min_size=(900, 600),
            resizable=True,
        )

        def on_window_closed():
            """Called by pywebview when the user closes the window."""
            logger.info("Window closed — shutting down...")
            stop_ollama()

        window.events.closed += on_window_closed

        # Start the webview event loop (blocks until window is closed)
        webview.start(
            private_mode=False,
            debug=settings.debug,
        )

        # Clean shutdown after window closes
        logger.info("Application exiting.")

except Exception as e:
    _write_crash_log(e)
    # Re-raise so the app actually closes
    raise
