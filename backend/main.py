"""
main.py — FastAPI application entry point.
"""

from contextlib import asynccontextmanager
import sys
import threading
import logging as builtin_logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
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
from app.api.license import router as license_router
from app.core.license import (
    validate_license, set_current_license, get_current_license, LicenseError
)
from app.database.qdrant_store import get_qdrant_store
from app.retrieval.bm25 import get_bm25_index
from app.indexing.page_index import get_page_index
from app.llm.qwen_service import _load_hf_pipeline, is_llm_loaded
from app.embeddings.bge_m3 import _load_model as load_embedding_model
from app.reranker.cross_encoder import _load_model as load_reranker_model
from app.services.pdf_service import list_manuals, get_chunks_for_manual
from app.schemas import HealthResponse

settings = get_settings()

import os
if settings.offline_mode:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["MARKER_TELEMETRY"] = "false"
    # Prevent PaddleOCR from downloading models at runtime
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

    # 0. Validate License
    try:
        info = validate_license()
        set_current_license(info)
        logger.info(f"License OK — {info.customer}, expires {info.expiry_date}")
    except LicenseError as e:
        logger.warning(f"License validation failed: {e}")
        # App still starts but API calls will be blocked by middleware

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
    # Prevents multithreading import race conditions (e.g., torch RpcBackendOptions error)
    # when background threads try to import them simultaneously.
    try:
        import torch
        import transformers
        import sentence_transformers
    except ImportError:
        pass

    # 5. Background model loading
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

# ── License Middleware ────────────────────────────────────────────────────────
# Blocks all API requests (except license + health + frontend) if no valid license
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class LicenseMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        # Always allow: license endpoints, health check, frontend assets
        if (
            path.startswith("/api/v1/license")
            or path == "/api/v1/health"
            or not path.startswith("/api/")
        ):
            return await call_next(request)
        
        # Check if we have a valid license
        current = get_current_license()
        if current is None:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "No valid license. Please activate your license.",
                    "license_status": "not_activated",
                },
            )
        if current.is_expired:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": f"License expired on {current.expiry_date}. Please renew.",
                    "license_status": "expired",
                },
            )
        return await call_next(request)

app.add_middleware(LicenseMiddleware)

# Routers
app.include_router(license_router, prefix="/api/v1")
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


# Resolve frontend dist — works in both dev and PyInstaller frozen mode
if getattr(sys, 'frozen', False):
    frontend_dist = Path(sys._MEIPASS) / "frontend" / "dist"
else:
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
        # Fallback to index.html (SPA routing)
        return FileResponse(str(frontend_dist / "index.html"))

    @app.get("/{catchall:path}", tags=["Frontend"])
    async def serve_frontend(catchall: str):
        if catchall.startswith("api/"):
            return {"detail": "Not Found"}
        # Serve index.html for all other routes to support React Router
        index_path = frontend_dist / "index.html"
        if not index_path.exists():
            return {"message": "Frontend not built. Run 'npm run build' in frontend dir."}
        return FileResponse(str(index_path))
else:
    @app.get("/", tags=["Root"])
    async def root():
        return {"message": f"Welcome to {settings.app_name}. Frontend not built. Run 'npm run build' in frontend dir.", "docs": "/docs"}


if __name__ == "__main__":
    import multiprocessing
    import platform
    import socket
    import subprocess
    import sys
    import time
    import uvicorn

    # Freeze support for PyInstaller
    multiprocessing.freeze_support()

    # Determine base path (PyInstaller bundle or dev)
    if getattr(sys, 'frozen', False):
        BASE_DIR = Path(sys._MEIPASS)
    else:
        BASE_DIR = Path(__file__).parent

    # ── Find a random free port ──────────────────────────────────────────────
    def get_free_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]

    port = get_free_port()

    # Write port to temp file so Tauri can read it
    import os
    port_file = Path(os.environ.get('TEMP', os.environ.get('TMPDIR', '/tmp'))) / 'isra_port.txt'
    port_file.write_text(str(port))
    logger.info(f"Backend port: {port} (written to {port_file})")

    # ── Start Ollama ─────────────────────────────────────────────────────────
    # Try bundled Ollama first (frozen exe), then system Ollama
    ollama_exe = BASE_DIR / "ollama" / "ollama.exe"
    ollama_models = BASE_DIR / "ollama" / "models"

    if ollama_exe.exists():
        # Use bundled Ollama with bundled models
        os.environ["OLLAMA_MODELS"] = str(ollama_models)
        logger.info(f"Starting bundled Ollama from: {ollama_exe}")
        try:
            if platform.system() == "Windows":
                subprocess.Popen(
                    [str(ollama_exe), "serve"],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                subprocess.Popen(
                    [str(ollama_exe), "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            time.sleep(2)
        except Exception as e:
            logger.error(f"Failed to start bundled Ollama: {e}")
    else:
        # Use system Ollama
        if platform.system() == "Windows":
            try:
                output = subprocess.check_output(
                    'tasklist /FI "IMAGENAME eq ollama.exe"', shell=True
                ).decode()
                if "ollama.exe" not in output:
                    logger.info("Ollama is not running. Starting ollama serve...")
                    subprocess.Popen(
                        ["ollama", "serve"],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                else:
                    logger.info("Ollama is already running.")
            except Exception as e:
                logger.error(f"Failed to check or start Ollama: {e}")
        elif platform.system() == "Darwin":  # macOS
            try:
                result = subprocess.run(
                    ["pgrep", "-x", "ollama"],
                    capture_output=True, text=True,
                )
                if result.returncode != 0:
                    logger.info("Starting ollama serve on macOS...")
                    subprocess.Popen(
                        ["ollama", "serve"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    time.sleep(2)
                else:
                    logger.info("Ollama is already running on macOS.")
            except Exception as e:
                logger.warning(f"Could not check/start Ollama on macOS: {e}")

    # ── Run headless server (Tauri handles the window) ───────────────────────
    logger.info(f"Starting headless server on 127.0.0.1:{port}...")
    uvicorn.run("main:app", host="127.0.0.1", port=port, workers=1)
