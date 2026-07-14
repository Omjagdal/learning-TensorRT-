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
echo [OK] Frontend built.
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
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu --no-cache-dir --no-compile --quiet
pip install -r "%ROOT%backend\requirements.txt" --no-cache-dir --no-compile --quiet
:: pythonnet is required by pywebview on Windows (WinForms backend)
pip install pyinstaller pywebview pythonnet platformdirs --no-cache-dir --no-compile --quiet
echo [OK] Python environment ready.
echo.

:: ── Step 3: Download Ollama binary ───────────────────────────────────────────
echo [3/7] Preparing Ollama binary for bundling...
set "OLLAMA_DIR=%ROOT%bundle_assets\ollama"
mkdir "%OLLAMA_DIR%" 2>nul
if not exist "%OLLAMA_DIR%\ollama.exe" (
    echo Downloading Ollama for Windows...
    curl -L "https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip" ^
         -o "%TEMP%\ollama-windows.zip"
    powershell -Command "Expand-Archive -Force '%TEMP%\ollama-windows.zip' '%OLLAMA_DIR%'"
    echo [OK] Ollama binary downloaded.
) else (
    echo [OK] Ollama binary already present, skipping download.
)
echo.

:: ── Step 4: Pre-pull AI models ───────────────────────────────────────────────
echo [4/7] Bundling AI models (this may take a while on first run)...
set "MODELS_DIR=%ROOT%bundle_assets\ollama_models"
mkdir "%MODELS_DIR%" 2>nul
set OLLAMA_MODELS=%MODELS_DIR%
start /B "" "%OLLAMA_DIR%\ollama.exe" serve
timeout /t 8 /nobreak >nul

echo Checking qwen3:8b model...
"%OLLAMA_DIR%\ollama.exe" list 2>nul | findstr "qwen3:8b" >nul
if errorlevel 1 (
    echo Pulling qwen3:8b (~5.2 GB)...
    "%OLLAMA_DIR%\ollama.exe" pull qwen3:8b
) else (
    echo [OK] qwen3:8b already cached.
)

echo Checking bge-m3 model...
"%OLLAMA_DIR%\ollama.exe" list 2>nul | findstr "bge-m3" >nul
if errorlevel 1 (
    echo Pulling bge-m3 (~2.1 GB)...
    "%OLLAMA_DIR%\ollama.exe" pull bge-m3
) else (
    echo [OK] bge-m3 already cached.
)

taskkill /F /IM ollama.exe /T >nul 2>&1
echo [OK] Ollama models ready.
echo.

:: ── Step 5: Pre-cache HuggingFace models ─────────────────────────────────────
echo [5/7] Pre-caching HuggingFace models...
set "HF_CACHE=%ROOT%bundle_assets\hf_cache"
mkdir "%HF_CACHE%" 2>nul
set HF_HOME=%HF_CACHE%
set TRANSFORMERS_CACHE=%HF_CACHE%\hub
python -c "from sentence_transformers import CrossEncoder; CrossEncoder('BAAI/bge-reranker-large'); print('Done.')"
echo [OK] HuggingFace models cached.
echo.

:: ── Step 6: Run PyInstaller ──────────────────────────────────────────────────
echo [6/7] Building standalone executable with PyInstaller...
cd /d "%ROOT%"
pyinstaller --clean -y isra_chatbot.spec
if not exist "%ROOT%dist\IsraChatbot\IsraChatbot.exe" (
    echo [ERROR] PyInstaller failed!
    pause & exit /b 1
)
echo [OK] PyInstaller build complete.
echo.

:: ── Step 7: Create Windows Installer ─────────────────────────────────────────
echo [7/7] Building Windows Installer...
mkdir "%ROOT%dist\installer" 2>nul

set "ISCC="
for %%p in (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    "C:\Program Files\Inno Setup 6\ISCC.exe"
) do (
    if exist "%%~p" set "ISCC=%%~p"
)

if defined ISCC (
    "%ISCC%" "%ROOT%installer\windows_setup.iss"
    echo [OK] Installer built: dist\installer\MachineAI_Chatbot_Setup.exe
) else (
    echo [INFO] Inno Setup not found. Raw app folder is at: dist\IsraChatbot\
    echo        Install Inno Setup 6 from https://jrsoftware.org/isdl.php
    echo        Then run: iscc installer\windows_setup.iss
)

echo.
echo ================================================================
echo   BUILD COMPLETE!
echo   App folder  : dist\IsraChatbot\
if exist "%ROOT%dist\installer\MachineAI_Chatbot_Setup.exe" (
echo   Installer   : dist\installer\MachineAI_Chatbot_Setup.exe
)
echo ================================================================
echo.
pause
