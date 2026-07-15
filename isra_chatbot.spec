# -*- mode: python ; coding: utf-8 -*-
# =============================================================================
# isra_chatbot.spec — PyInstaller build spec for the ISRA Chatbot desktop app
# =============================================================================
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
project_root  = Path(SPECPATH)
backend_dir   = project_root / "backend"
frontend_dist = project_root / "frontend" / "dist"

# ── Data files to bundle ──────────────────────────────────────────────────────
datas = [
    (str(frontend_dist),         "frontend/dist"),
    (str(backend_dir / ".env"),  "."),
]

# Add bundled Ollama binary
_ollama_win = project_root / "bundle_assets" / "ollama" / "ollama.exe"
_ollama_mac = project_root / "bundle_assets" / "ollama" / "ollama"
if _ollama_win.exists():
    datas.append((str(_ollama_win.parent), "ollama"))
elif _ollama_mac.exists():
    datas.append((str(_ollama_mac.parent), "ollama"))

# Add pre-cached HuggingFace models
_hf_cache = project_root / "bundle_assets" / "hf_cache"
if _hf_cache.exists():
    datas.append((str(_hf_cache), "hf_cache"))

# Add pre-pulled Ollama model store
_ollama_models = project_root / "bundle_assets" / "ollama_models"
if _ollama_models.exists():
    datas.append((str(_ollama_models), "ollama_models"))

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
    # PyWebView — Windows uses WinForms (.NET/pythonnet)
    "webview", "webview.platforms.winforms", "webview.platforms.cocoa",
    "webview.platforms.gtk", "webview.platforms.qt",
    "clr", "clr_loader",          # pythonnet runtime (Windows WinForms)
    # Pydantic
    "pydantic", "pydantic_settings", "pydantic.v1",
    # Qdrant vector DB
    "qdrant_client", "qdrant_client.http", "qdrant_client.models",
    "qdrant_client.http.models", "qdrant_client.http.api",
    # ML / embeddings
    "sentence_transformers", "sentence_transformers.models",
    "FlagEmbedding", "FlagEmbedding.BGE_M3",
    "torch", "torch.nn", "torch.nn.functional", "torchvision",
    "transformers", "transformers.models.auto",
    # PDF processing
    "marker", "marker.converters", "marker.models",
    "surya", "paddleocr", "paddlepaddle",
    "fitz", "pymupdf", "cv2", "PIL", "PIL.Image",
    # Utilities
    "loguru", "aiofiles", "numpy", "tqdm",
    "rank_bm25", "tiktoken", "yaml", "requests", "httpx",
    "langchain", "langchain.text_splitter",
    "langchain_community", "langchain_core",
    "platformdirs",
    "multiprocessing", "multiprocessing.freeze_support",
    "email.mime.text", "email.mime.multipart",  # needed by some httpx internals
    "charset_normalizer",  # needed by requests on some Windows builds
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
        # CUDA not needed — CPU-only build
        "torch.cuda", "torch.cuda.amp", "torchvision.io",
        # Test frameworks
        "pytest", "unittest", "hypothesis",
        # Notebooks / dev tools
        "jupyter", "ipython", "ipykernel",
        # Plotting (not used in app)
        "matplotlib", "seaborn",
        # Linux-only display backends
        "tkinter", "_tkinter",
        # Heavy OCR / PDF processing deps not needed at runtime
        # (PDFs are processed via marker API calls, not direct imports)
        "paddlepaddle", "paddle", "paddleocr",
        "surya",
        # Unused torch sub-packages that are large
        "torch.distributed", "torch.multiprocessing",
        "torch.testing", "torch._dynamo",
        # Unused transformers backends
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
    name="IsraChatbot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,           # No black terminal window on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,        # Build for current arch (x64 on Windows runner)
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "icon.ico") if (project_root / "icon.ico").exists() else None,
    version=None,            # Can add version_info file here if needed
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="IsraChatbot",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name='IsraChatbot.app',
        icon=str(project_root / "icon.png") if (project_root / "icon.png").exists() else None,
        bundle_identifier=None,
        info_plist={
            'NSHighResolutionCapable': 'True',
            'LSBackgroundOnly': 'False',
        },
    )
