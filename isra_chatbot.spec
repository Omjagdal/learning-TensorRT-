# -*- mode: python ; coding: utf-8 -*-
# =============================================================================
# isra_chatbot.spec — PyInstaller build spec for the ISRA Chatbot desktop app
# =============================================================================
#
# This builds a --onedir bundle (a folder, not a single file) because the app
# contains ~5-15 GB of AI models. Extracting a single-file bundle every launch
# would take 5+ minutes. The folder is then wrapped into an installer.
#
# Build command (run from project root, on Windows with venv activated):
#   pyinstaller --clean -y isra_chatbot.spec
#
# Outputs:
#   dist/IsraChatbot/          <-- the application folder
#   dist/IsraChatbot/IsraChatbot.exe (Windows) or IsraChatbot (Mac)
# =============================================================================

import sys
import os
from pathlib import Path

block_cipher = None

# ── Project Paths ─────────────────────────────────────────────────────────────
project_root  = Path(SPECPATH)         # where this .spec file lives
backend_dir   = project_root / "backend"
frontend_dist = project_root / "frontend" / "dist"

# ── Data files to bundle alongside the executable ─────────────────────────────
# Format: (source_path_on_disk, destination_inside_bundle)
datas = [
    # React frontend build output
    (str(frontend_dist),             "frontend/dist"),
    # Backend .env config (will be loaded by pydantic-settings)
    (str(backend_dir / ".env"),      "."),
]

# Add bundled Ollama binary (Windows: ollama.exe, Mac: ollama)
_ollama_win = project_root / "bundle_assets" / "ollama" / "ollama.exe"
_ollama_mac = project_root / "bundle_assets" / "ollama" / "ollama"
if _ollama_win.exists():
    datas.append((str(_ollama_win.parent), "ollama"))
elif _ollama_mac.exists():
    datas.append((str(_ollama_mac.parent), "ollama"))

# Add pre-cached HuggingFace models (bge-m3, bge-reranker-large, marker)
_hf_cache = project_root / "bundle_assets" / "hf_cache"
if _hf_cache.exists():
    datas.append((str(_hf_cache), "hf_cache"))

# Add pre-pulled Ollama model store (qwen3:8b GGUF)
_ollama_models = project_root / "bundle_assets" / "ollama_models"
if _ollama_models.exists():
    datas.append((str(_ollama_models), "ollama_models"))

print(f"[spec] datas = {[d[1] for d in datas]}")

# ── Hidden imports PyInstaller cannot auto-detect ─────────────────────────────
hidden_imports = [
    # Web framework
    "uvicorn", "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan", "uvicorn.lifespan.on",
    "fastapi", "fastapi.middleware.cors",
    "starlette", "starlette.routing", "starlette.staticfiles",
    # Desktop window
    "webview",
    "webview.platforms.winforms",   # Windows WebView2
    "webview.platforms.cocoa",      # macOS WKWebView
    # Pydantic / settings
    "pydantic", "pydantic_settings", "pydantic.v1",
    # Vector DB
    "qdrant_client", "qdrant_client.http", "qdrant_client.models",
    # ML / Embeddings
    "sentence_transformers", "sentence_transformers.models",
    "FlagEmbedding", "FlagEmbedding.BGE_M3",
    # PyTorch (CPU-only)
    "torch", "torch.nn", "torch.nn.functional",
    "torchvision",
    # Transformers
    "transformers", "transformers.models.auto",
    # Marker PDF models
    "marker", "marker.converters", "marker.models",
    "surya",
    # OCR
    "paddleocr", "paddlepaddle",
    # PDF / image
    "fitz", "pymupdf", "cv2", "PIL", "PIL.Image",
    # Utilities
    "loguru", "aiofiles", "numpy", "tqdm",
    "rank_bm25", "tiktoken", "yaml",
    "requests", "httpx",
    # Langchain
    "langchain", "langchain.text_splitter",
    "langchain_community", "langchain_core",
    # Platform
    "platformdirs",
    # Multiprocessing
    "multiprocessing", "multiprocessing.freeze_support",
]

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    [str(backend_dir / "main.py")],
    pathex=[str(backend_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude CUDA — we use CPU-only PyTorch
        "torch.cuda", "torchvision.io",
        # Exclude test frameworks
        "pytest", "unittest", "hypothesis",
        # Exclude Jupyter
        "jupyter", "ipython", "ipykernel",
        # Exclude dev tools
        "matplotlib", "seaborn",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── Executable ────────────────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],                          # No binaries/datas here — they go in COLLECT
    exclude_binaries=True,       # Required for --onedir
    name="IsraChatbot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                   # UPX breaks some DLLs; safer to leave off
    console=False,               # No black console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "icon.ico") if (project_root / "icon.ico").exists() else None,
)

# ── Collection (onedir output folder) ─────────────────────────────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="IsraChatbot",           # Output folder: dist/IsraChatbot/
)
