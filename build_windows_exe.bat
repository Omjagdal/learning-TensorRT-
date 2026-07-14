@echo off
setlocal enabledelayedexpansion

:: =============================================================================
:: ISRA Chatbot — Full Offline Windows Desktop App Builder
:: =============================================================================
:: Produces: dist\installer\MachineAI_Chatbot_Setup.exe
::
:: Requirements (all free):
::   - Python 3.11            https://www.python.org/downloads/
::   - Node.js 20+            https://nodejs.org/
::   - Inno Setup 6           https://jrsoftware.org/isdl.php
::   - Git (optional)
::
:: Run this script ONCE from a Windows machine that has internet access.
:: The output installer can then be distributed offline (USB, file share).
:: =============================================================================

title ISRA Chatbot — Windows Desktop Builder
color 0B
echo.
echo ================================================================
echo   ISRA Vision Chatbot ^| Full Offline Desktop App Builder
echo   Produces: MachineAI_Chatbot_Setup.exe
echo ================================================================
echo.

:: ── Locate the script directory ───────────────────────────────────────────────
set "ROOT=%~dp0"
cd /d "%ROOT%"

:: ── Step 1: Build React Frontend ─────────────────────────────────────────────
echo [1/7] Building React Frontend...
cd "%ROOT%frontend"
call npm install --silent
call npm run build
if not exist "%ROOT%frontend\dist\index.html" (
    echo [ERROR] Frontend build failed! Check Node.js and npm are installed.
    pause & exit /b 1
)
cd "%ROOT%"
echo [OK] Frontend built: frontend\dist\
echo.

:: ── Step 2: Set up Python virtual environment ─────────────────────────────────
echo [2/7] Setting up Python environment...
if not exist "%ROOT%backend\build_venv\Scripts\activate.bat" (
    python -m venv "%ROOT%backend\build_venv"
    if errorlevel 1 (
        echo [ERROR] Failed to create Python venv. Is Python 3.11 installed?
        pause & exit /b 1
    )
)
call "%ROOT%backend\build_venv\Scripts\activate.bat"

:: Install CPU-only PyTorch first (prevents 4 GB CUDA download)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu --quiet
:: Install all Python dependencies
pip install -r "%ROOT%backend\requirements.txt" --quiet
:: Install build tools
pip install pyinstaller pywebview platformdirs --quiet
echo [OK] Python environment ready.
echo.

:: ── Step 3: Download and prepare Ollama binary ───────────────────────────────
echo [3/7] Preparing Ollama binary for bundling...
set "OLLAMA_DIR=%ROOT%bundle_assets\ollama"
mkdir "%OLLAMA_DIR%" 2>nul

if not exist "%OLLAMA_DIR%\ollama.exe" (
    echo Downloading Ollama for Windows...
    curl -L "https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip" ^
         -o "%TEMP%\ollama-windows.zip"
    powershell -Command "Expand-Archive -Force '%TEMP%\ollama-windows.zip' '%OLLAMA_DIR%'"
    echo [OK] Ollama binary downloaded and extracted.
) else (
    echo [OK] Ollama binary already present, skipping download.
)
echo.

:: ── Step 4: Pre-pull and bundle AI models ────────────────────────────────────
echo [4/7] Bundling AI models (this may take a while on first run)...

set "MODELS_DIR=%ROOT%bundle_assets\ollama_models"
mkdir "%MODELS_DIR%" 2>nul

:: Start Ollama with a custom models dir to pull models there
set OLLAMA_MODELS=%MODELS_DIR%
start /B "" "%OLLAMA_DIR%\ollama.exe" serve
timeout /t 8 /nobreak >nul

:: Pull qwen3:8b LLM (5.2 GB) — only if not already cached
echo Checking qwen3:8b model...
"%OLLAMA_DIR%\ollama.exe" list 2>nul | findstr "qwen3:8b" >nul
if errorlevel 1 (
    echo Pulling qwen3:8b (~5.2 GB). This will take several minutes...
    "%OLLAMA_DIR%\ollama.exe" pull qwen3:8b
) else (
    echo [OK] qwen3:8b already cached.
)

:: Pull bge-m3 embedding model (2.1 GB) — only if not already cached
echo Checking bge-m3 model...
"%OLLAMA_DIR%\ollama.exe" list 2>nul | findstr "bge-m3" >nul
if errorlevel 1 (
    echo Pulling bge-m3 (~2.1 GB)...
    "%OLLAMA_DIR%\ollama.exe" pull bge-m3
) else (
    echo [OK] bge-m3 already cached.
)

:: Stop the temporary Ollama instance
taskkill /F /IM ollama.exe /T >nul 2>&1
echo [OK] Ollama models ready in: %MODELS_DIR%
echo.

:: ── Step 5: Pre-cache HuggingFace models (bge-reranker-large + marker) ───────
echo [5/7] Pre-caching HuggingFace models (bge-reranker-large, marker)...
set "HF_CACHE=%ROOT%bundle_assets\hf_cache"
mkdir "%HF_CACHE%" 2>nul
set HF_HOME=%HF_CACHE%
set TRANSFORMERS_CACHE=%HF_CACHE%\hub

python -c "
from sentence_transformers import CrossEncoder
print('Downloading bge-reranker-large...')
CrossEncoder('BAAI/bge-reranker-large')
print('Done.')
"

:: Pre-cache Marker/Surya OCR models by running on a tiny dummy PDF
python -c "
import tempfile, os
from pathlib import Path

pdf_bytes = b'%%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n5 0 obj\n<< /Length 44 >>\nstream\nBT\n/F1 24 Tf\n100 700 Td\n(Cache Test) Tj\nET\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f \n0000000009 00000 n \ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n300\n%%%%EOF'
tmp = Path(tempfile.gettempdir()) / 'dummy.pdf'
tmp.write_bytes(pdf_bytes)
os.system(f'marker_single {tmp} {tempfile.gettempdir()}\\\\marker_out')
print('Marker models cached.')
"
echo [OK] HuggingFace models cached in: %HF_CACHE%
echo.

:: ── Step 6: Run PyInstaller ──────────────────────────────────────────────────
echo [6/7] Building standalone executable with PyInstaller...
cd /d "%ROOT%"
pyinstaller --clean -y isra_chatbot.spec
if not exist "%ROOT%dist\IsraChatbot\IsraChatbot.exe" (
    echo [ERROR] PyInstaller failed! Check the output above for errors.
    pause & exit /b 1
)
echo [OK] PyInstaller build complete: dist\IsraChatbot\
echo.

:: ── Step 7: Create Windows Installer with Inno Setup ─────────────────────────
echo [7/7] Building Windows Installer (MachineAI_Chatbot_Setup.exe)...
mkdir "%ROOT%dist\installer" 2>nul

:: Find Inno Setup
set "ISCC="
for %%p in (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    "C:\Program Files\Inno Setup 6\ISCC.exe"
) do (
    if exist "%%~p" set "ISCC=%%~p"
)

if defined ISCC (
    "%ISCC%" "%ROOT%installer\windows_setup.iss"
    if errorlevel 1 (
        echo [WARNING] Inno Setup build failed. The raw app folder is still available at:
        echo           dist\IsraChatbot\
    ) else (
        echo [OK] Installer built: dist\installer\MachineAI_Chatbot_Setup.exe
    )
) else (
    echo [INFO] Inno Setup not found. Skipping installer creation.
    echo        The raw application folder is available at: dist\IsraChatbot\
    echo        To create the installer later, install Inno Setup 6 from:
    echo        https://jrsoftware.org/isdl.php
    echo        Then run: iscc installer\windows_setup.iss
)

echo.
echo ================================================================
echo   BUILD COMPLETE!
echo ================================================================
echo.
echo   App folder  : dist\IsraChatbot\
if exist "%ROOT%dist\installer\MachineAI_Chatbot_Setup.exe" (
echo   Installer   : dist\installer\MachineAI_Chatbot_Setup.exe
echo.
echo   Copy "MachineAI_Chatbot_Setup.exe" to a USB drive or file
echo   share. Users just double-click and install -- no internet needed!
) else (
echo   To create the installer, install Inno Setup 6 and rerun this script.
)
echo.
pause
