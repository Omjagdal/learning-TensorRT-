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
    "uvicorn", "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan", "uvicorn.lifespan.on",
    "fastapi", "fastapi.middleware.cors",
    "starlette", "starlette.routing", "starlette.staticfiles",
    "webview", "webview.platforms.winforms", "webview.platforms.cocoa",
    "pydantic", "pydantic_settings", "pydantic.v1",
    "qdrant_client", "qdrant_client.http", "qdrant_client.models",
    "sentence_transformers", "sentence_transformers.models",
    "FlagEmbedding", "FlagEmbedding.BGE_M3",
    "torch", "torch.nn", "torch.nn.functional", "torchvision",
    "transformers", "transformers.models.auto",
    "marker", "marker.converters", "marker.models",
    "surya", "paddleocr", "paddlepaddle",
    "fitz", "pymupdf", "cv2", "PIL", "PIL.Image",
    "loguru", "aiofiles", "numpy", "tqdm",
    "rank_bm25", "tiktoken", "yaml", "requests", "httpx",
    "langchain", "langchain.text_splitter",
    "langchain_community", "langchain_core",
    "platformdirs",
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
        "torch.cuda", "torchvision.io",
        "pytest", "unittest", "hypothesis",
        "jupyter", "ipython", "ipykernel",
        "matplotlib", "seaborn",
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "icon.ico") if (project_root / "icon.ico").exists() else None,
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
