@echo off
setlocal enabledelayedexpansion

:: =============================================================================
:: ISRA Chatbot — Complete Offline Windows Desktop Builder
:: =============================================================================
:: OUTPUT (choose what you need):
::   dist\installer\MachineAI_Chatbot_Setup.exe   <- Installer (with .bin files)
::   dist\ISRA_Vision_Chatbot_Portable.zip        <- Single ZIP (portable)
::
:: Everything is included: app + qwen3:8b + bge-m3 + bge-reranker-large
:: Total size after build: ~10 GB
::
:: Requirements (all free):
::   Python 3.11 (64-bit)    https://www.python.org/downloads/
::   Node.js 20+             https://nodejs.org/
::   Inno Setup 6            https://jrsoftware.org/isdl.php  (for installer)
::   Git                     https://git-scm.com/
::
:: Run from an internet-connected Windows 10/11 machine (first time only).
:: Once built, distribute via USB or file share — fully offline.
:: =============================================================================

title ISRA Chatbot — Complete Offline Windows Builder
color 0A
echo.
echo ================================================================
echo   ISRA Vision Chatbot ^| Complete Offline Windows Builder
echo   Includes: App + All AI Models (qwen3:8b, bge-m3, reranker)
echo   Total output size: ~10 GB
echo ================================================================
echo.

set "ROOT=%~dp0"
cd /d "%ROOT%"

:: Check prerequisites
echo Checking prerequisites...
python --version >nul 2>&1 || (echo [ERROR] Python not found. Install Python 3.11 from https://www.python.org/ & pause & exit /b 1)
node --version >nul 2>&1   || (echo [ERROR] Node.js not found. Install from https://nodejs.org/ & pause & exit /b 1)
echo [OK] Prerequisites OK
echo.

:: ─────────────────────────────────────────────────────────────────────────────
echo [1/8] Building React Frontend...
:: ─────────────────────────────────────────────────────────────────────────────
cd "%ROOT%frontend"
call npm install --silent
call npm run build
if not exist "%ROOT%frontend\dist\index.html" (
    echo [ERROR] Frontend build failed!
    pause & exit /b 1
)
cd "%ROOT%"
echo [OK] Frontend built.
echo.

:: ─────────────────────────────────────────────────────────────────────────────
echo [2/8] Setting up Python environment...
:: ─────────────────────────────────────────────────────────────────────────────
if not exist "%ROOT%backend\build_venv\Scripts\activate.bat" (
    python -m venv "%ROOT%backend\build_venv"
    if errorlevel 1 (
        echo [ERROR] Failed to create venv. Is Python 3.11 (64-bit) installed?
        pause & exit /b 1
    )
)
call "%ROOT%backend\build_venv\Scripts\activate.bat"
python -m pip install --upgrade pip "packaging>=24.2" --quiet --no-cache-dir
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu --no-cache-dir --no-compile --quiet
pip install "numpy<2.0.0" --no-cache-dir --no-compile --quiet
pip install -r "%ROOT%backend\requirements.txt" --no-cache-dir --no-compile --quiet
pip install pyinstaller pywebview pythonnet platformdirs --no-cache-dir --no-compile --quiet
echo [OK] Python environment ready.
echo.

:: ─────────────────────────────────────────────────────────────────────────────
echo [3/8] Downloading Ollama binary...
:: ─────────────────────────────────────────────────────────────────────────────
set "OLLAMA_DIR=%ROOT%bundle_assets\ollama"
mkdir "%OLLAMA_DIR%" 2>nul
if not exist "%OLLAMA_DIR%\ollama.exe" (
    echo Downloading Ollama for Windows...
    curl -L "https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip" -o "%TEMP%\ollama-windows.zip" --progress-bar
    powershell -Command "Expand-Archive -Force '%TEMP%\ollama-windows.zip' '%OLLAMA_DIR%'"
    echo [OK] Ollama downloaded.
) else (
    echo [OK] Ollama already present.
)
echo.

:: ─────────────────────────────────────────────────────────────────────────────
echo [4/8] Pulling Ollama AI models (qwen3:8b + bge-m3)...
echo       This downloads ~7.3 GB on first run — skipped if already cached.
:: ─────────────────────────────────────────────────────────────────────────────
set "MODELS_DIR=%ROOT%bundle_assets\ollama_models"
mkdir "%MODELS_DIR%" 2>nul
set OLLAMA_MODELS=%MODELS_DIR%
set OLLAMA_HOST=127.0.0.1:11435

:: Start Ollama on non-default port to avoid conflict with system Ollama
start /B "" "%OLLAMA_DIR%\ollama.exe" serve
timeout /t 10 /nobreak >nul

"%OLLAMA_DIR%\ollama.exe" list 2>nul | findstr "qwen3:8b" >nul
if errorlevel 1 (
    echo Pulling qwen3:8b model (~5.2 GB)...
    "%OLLAMA_DIR%\ollama.exe" pull qwen3:8b
) else (
    echo [OK] qwen3:8b already cached.
)

"%OLLAMA_DIR%\ollama.exe" list 2>nul | findstr "bge-m3" >nul
if errorlevel 1 (
    echo Pulling bge-m3 model (~2.1 GB)...
    "%OLLAMA_DIR%\ollama.exe" pull bge-m3
) else (
    echo [OK] bge-m3 already cached.
)

taskkill /F /IM ollama.exe /T >nul 2>&1
echo [OK] Ollama models ready.
echo.

:: ─────────────────────────────────────────────────────────────────────────────
echo [5/8] Downloading HuggingFace model (bge-reranker-large ~1.3 GB)...
:: ─────────────────────────────────────────────────────────────────────────────
set "HF_CACHE=%ROOT%bundle_assets\hf_cache"
mkdir "%HF_CACHE%" 2>nul
set HF_HOME=%HF_CACHE%
set TRANSFORMERS_CACHE=%HF_CACHE%\hub
if not exist "%HF_CACHE%\hub\models--BAAI--bge-reranker-large" (
    echo Downloading bge-reranker-large...
    python -c "from sentence_transformers import CrossEncoder; CrossEncoder('BAAI/bge-reranker-large'); print('Done.')"
    echo [OK] bge-reranker-large downloaded.
) else (
    echo [OK] bge-reranker-large already cached.
)
echo.

:: ─────────────────────────────────────────────────────────────────────────────
echo [6/8] Building standalone .exe with PyInstaller...
:: ─────────────────────────────────────────────────────────────────────────────
cd /d "%ROOT%"
pyinstaller --clean -y isra_chatbot.spec
if not exist "%ROOT%dist\IsraChatbot\IsraChatbot.exe" (
    echo [ERROR] PyInstaller failed!
    pause & exit /b 1
)
echo [OK] PyInstaller build complete.
echo.

:: ─────────────────────────────────────────────────────────────────────────────
echo [7/8] Creating Windows Installer (multi-part for large size)...
:: ─────────────────────────────────────────────────────────────────────────────
mkdir "%ROOT%dist\installer" 2>nul
del /Q "%ROOT%dist\installer\*.exe" 2>nul
del /Q "%ROOT%dist\installer\*.bin" 2>nul

set "ISCC="
for %%p in (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    "C:\Program Files\Inno Setup 6\ISCC.exe"
) do (
    if exist "%%~p" set "ISCC=%%~p"
)

if defined ISCC (
    "%ISCC%" "%ROOT%installer\windows_setup.iss"
    if exist "%ROOT%dist\installer\MachineAI_Chatbot_Setup.exe" (
        echo [OK] Installer files created in dist\installer\
        echo      Copy ALL files in dist\installer\ to USB together.
    ) else (
        echo [WARN] Inno Setup did not produce output. Check errors above.
    )
) else (
    echo [INFO] Inno Setup not found — skipping installer creation.
    echo        Install from: https://jrsoftware.org/isdl.php
)
echo.

:: ─────────────────────────────────────────────────────────────────────────────
echo [8/8] Creating Portable ZIP (alternative to installer)...
:: ─────────────────────────────────────────────────────────────────────────────
where 7z >nul 2>&1
if not errorlevel 1 (
    echo Zipping with 7-Zip...
    7z a -mx=5 "%ROOT%dist\ISRA_Vision_Chatbot_Portable.zip" "%ROOT%dist\IsraChatbot\*"
    echo [OK] Portable zip: dist\ISRA_Vision_Chatbot_Portable.zip
) else (
    powershell -Command "Compress-Archive -Force -Path '%ROOT%dist\IsraChatbot\*' -DestinationPath '%ROOT%dist\ISRA_Vision_Chatbot_Portable.zip'"
    echo [OK] Portable zip: dist\ISRA_Vision_Chatbot_Portable.zip
)
echo.

:: ─────────────────────────────────────────────────────────────────────────────
echo ================================================================
echo   BUILD COMPLETE!
echo.
echo   OPTION 1 — Installer (copy ALL these files to USB together):
if exist "%ROOT%dist\installer\MachineAI_Chatbot_Setup.exe" (
    dir /b "%ROOT%dist\installer\"
)
echo.
echo   OPTION 2 — Portable ZIP (extract and run IsraChatbot.exe):
echo   dist\ISRA_Vision_Chatbot_Portable.zip
echo.
echo   On target PC: install/extract, launch IsraChatbot.exe
echo   First launch: FULLY OFFLINE — all models are included!
echo ================================================================
echo.
pause
