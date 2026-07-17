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
    # config.json must be bundled so get_settings() can load user overrides
    (str(backend_dir / "config" / "config.json"), "config"),
]

# Add bundled Ollama binary ONLY (not models — those download on first launch)
_ollama_win = project_root / "bundle_assets" / "ollama" / "ollama.exe"
_ollama_mac = project_root / "bundle_assets" / "ollama" / "ollama"
if _ollama_win.exists():
    datas.append((str(_ollama_win.parent), "ollama"))
elif _ollama_mac.exists():
    datas.append((str(_ollama_mac.parent), "ollama"))

# Bundle marker-pdf package data (JSON layout/OCR config files)
try:
    import site as _site
    _marker_path = Path(_site.getsitepackages()[0]) / "marker"
    if _marker_path.exists():
        datas.append((str(_marker_path), "marker"))
except Exception:
    pass  # marker not installed — safe to skip

# NOTE: HuggingFace models (hf_cache) and Ollama models (ollama_models) are NOT
# bundled here. They are placed in models/ folder next to the .exe (portable mode)
# or downloaded to AppData on first launch (installed mode).

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
    # Qdrant vector DB — include local/embedded submodules (critical for embedded mode)
    "qdrant_client", "qdrant_client.http", "qdrant_client.models",
    "qdrant_client.http.models", "qdrant_client.http.api",
    "qdrant_client.http.exceptions",
    "qdrant_client.local",               # required for embedded (no-server) mode
    "qdrant_client.local.collection",
    "qdrant_client.conversions",
    "qdrant_client.conversions.common_types",
    # ML / embeddings — tokenizers is dynamically loaded by FlagEmbedding
    "sentence_transformers", "FlagEmbedding",
    "tokenizers", "tokenizers.implementations",
    "transformers.modeling_utils",
    "transformers.tokenization_utils_fast",
    # Utilities
    "loguru", "aiofiles", "numpy", "tqdm",
    "rank_bm25", "tiktoken", "yaml", "requests", "httpx",
    "langchain", "langchain.text_splitter",
    "langchain_community", "langchain_core",
    "platformdirs",
    "multiprocessing", "multiprocessing.freeze_support",
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
        # Unused ML Frameworks
        "tensorflow", "tensorboard", "flax", "keras", "jax", "jaxlib",
        # CUDA not needed — CPU-only build
        "torch.cuda", "torch.cuda.amp", "torchvision.io",
        "triton", "xformers", "nvidia", "vllm", "flash_attn",
        # Test frameworks
        "pytest", "unittest", "hypothesis",
        # Notebooks / dev tools
        "jupyter", "ipython", "ipykernel",
        # Plotting (not used in app)
        "matplotlib", "seaborn",
        # Linux-only display backends
        "tkinter", "_tkinter",
        # Heavy OCR / PDF processing deps not needed at runtime
        "paddlepaddle", "paddle", "paddleocr",
        "surya", "surya_ocr",
        # Unused torch sub-packages that are large
        "torch.distributed", "torch.multiprocessing",
        "torch.testing", "torch._dynamo",
        "torch.onnx", "torch.export", "torch.fx",
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
