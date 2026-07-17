# -*- mode: python ; coding: utf-8 -*-
# =============================================================================
# isra_chatbot.spec — PyInstaller spec for the HEADLESS Python backend sidecar
# =============================================================================
#
# This builds ONLY the Python FastAPI backend as a headless executable.
# The window/UI is managed by the Tauri shell (IsraChatbot.exe).
#
# Build command (run from project root, on Windows with venv activated):
#   pyinstaller --clean -y isra_chatbot.spec
#
# Output:
#   dist/backend_server/backend_server.exe  <-- the sidecar Tauri expects
# =============================================================================

import sys
import os
from pathlib import Path

block_cipher = None

# ── Project Paths ─────────────────────────────────────────────────────────────
project_root  = Path(SPECPATH)
backend_dir   = project_root / "backend"
frontend_dist = project_root / "frontend" / "dist"

# ── Data files to bundle ──────────────────────────────────────────────────────
datas = [
    # The built React frontend — served as static files by FastAPI
    (str(frontend_dist),         "frontend/dist"),
    # .env defaults (overridden at runtime by Tauri env vars)
    (str(backend_dir / ".env"),  "."),
]

# Add bundled Ollama binary
_ollama_win = project_root / "bundle_assets" / "ollama" / "ollama.exe"
_ollama_mac = project_root / "bundle_assets" / "ollama" / "ollama"
if _ollama_win.exists():
    datas.append((str(_ollama_win.parent), "ollama"))
elif _ollama_mac.exists():
    datas.append((str(_ollama_mac.parent), "ollama"))

# NOTE: HuggingFace models (hf_cache) and Ollama models (ollama_models) are NOT
# bundled here. They reside in the models/ folder next to the Tauri app bundle.

# ── Hidden imports ────────────────────────────────────────────────────────────
hidden_imports = [
    # Uvicorn ASGI server
    "uvicorn", "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan", "uvicorn.lifespan.on",
    # FastAPI / Starlette
    "fastapi", "fastapi.middleware.cors",
    "starlette", "starlette.routing", "starlette.staticfiles", "starlette.responses",
    # Pydantic
    "pydantic", "pydantic_settings", "pydantic.v1",
    # Qdrant vector DB
    "qdrant_client", "qdrant_client.http", "qdrant_client.models",
    "qdrant_client.http.models", "qdrant_client.http.api",
    # ML / embeddings
    "sentence_transformers", "FlagEmbedding",
    # Utilities
    "loguru", "aiofiles", "numpy", "tqdm",
    "rank_bm25", "tiktoken", "yaml", "requests", "httpx",
    "langchain", "langchain.text_splitter",
    "langchain_community", "langchain_core",
    "platformdirs",
    "email.mime.text", "email.mime.multipart",
    "charset_normalizer",
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
        # No GUI frameworks needed — window is managed by Tauri
        "webview", "pythonnet", "clr", "clr_loader",
        "tkinter", "_tkinter",
        # Unused ML Frameworks
        "tensorflow", "tensorboard", "flax", "keras", "jax", "jaxlib",
        # CUDA not needed — CPU-only build
        "torch.cuda", "torch.cuda.amp", "torchvision.io",
        "triton", "xformers", "nvidia", "vllm", "flash_attn",
        # Test / dev tools
        "pytest", "unittest", "hypothesis",
        "jupyter", "ipython", "ipykernel",
        # Plotting
        "matplotlib", "seaborn",
        # Heavy OCR deps
        "paddlepaddle", "paddle", "paddleocr",
        "surya", "surya_ocr",
        # Unused torch sub-packages
        "torch.distributed", "torch.multiprocessing",
        "torch.testing", "torch._dynamo",
        "torch.onnx", "torch.export", "torch.fx",
        "transformers.integrations",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="backend_server",        # <-- Tauri sidecar name
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,                 # Keep console=True: Tauri reads stdout for BACKEND_READY
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="backend_server",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name='backend_server.app',
        icon=None,
        bundle_identifier="com.isravision.backend",
        info_plist={
            'LSBackgroundOnly': 'True',  # Headless — no Dock icon on macOS
        },
    )
