# -*- mode: python ; coding: utf-8 -*-
"""
isra_chatbot.spec — PyInstaller spec file for the ISRA Chatbot Backend
"""
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all implicit ML dependencies
hidden_imports = (
    collect_submodules('transformers') +
    collect_submodules('sentence_transformers') +
    collect_submodules('torch') +
    collect_submodules('qdrant_client') +
    collect_submodules('paddleocr') +
    collect_submodules('paddle') +
    collect_submodules('surya') +
    collect_submodules('marker') +
    [
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'app.api',
        'app.api.chat',
        'app.api.images',
        'app.api.info',
        'app.api.license',
        'app.api.manuals',
        'app.api.sources',
        'app.api.stream',
    ]
)

# Collect required data files (e.g. tokenizer configs, tiktoken files)
datas = [
    ('.env', '.'),
]
datas += collect_data_files('transformers', include_py_files=True)
datas += collect_data_files('tiktoken')
datas += collect_data_files('paddleocr')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pywebview'],  # Explicitly exclude pywebview, we use Tauri now
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
    name='IsraChatbot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False, # Hide the console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='../frontend/src-tauri/icons/icon.ico' # Optional: set an icon for the backend exe too
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='IsraChatbot',
)
