#!/bin/bash
# ==============================================================================
# ISRA Chatbot - Windows ONLINE Package Builder (Run on Mac)
# ==============================================================================
# This script bundles ONLY the source code. Since the IPC has internet,
# we don't need to bundle heavy installers, wheels, or AI models.
# This makes the package extremely small (a few MBs) and instant to copy!
# ==============================================================================

set -e

# Target directory
TARGET_DIR="$HOME/Desktop/ISRA_Windows_Online_Package"
echo "📦 Building lightweight online package at: $TARGET_DIR"

# 1. Setup Directory
mkdir -p "$TARGET_DIR/app"

# 2. Build Frontend (Ensure the latest UI is compiled before copying)
echo "🌐 Building React Frontend on Mac..."
cd frontend
npm install
npm run build
cd ..

# 3. Copy Project Files (exclude heavy node_modules, python cache, etc.)
echo "📂 Copying project source code..."
rsync -av --exclude 'backend/venv' \
          --exclude 'backend/__pycache__' \
          --exclude 'frontend/node_modules' \
          --exclude '.git' \
          --exclude 'data/qdrant_storage' \
          ./ "$TARGET_DIR/app/"

# 4. Generate the Online Installer Script for Windows
echo "📝 Generating SETUP_ONLINE.bat for the IPC..."
cat << 'EOF' > "$TARGET_DIR/SETUP_ONLINE.bat"
@echo off
:: Force correct directory
cd /d "%~dp0"

echo =====================================================
echo   ISRA Vision Chatbot - ONLINE Windows Installer
echo =====================================================
echo This script requires an active internet connection.
echo.

echo [1/2] Checking Dependencies...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.11 from https://www.python.org/downloads/
    pause
    exit /b
)
ollama --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Ollama is not installed or not in PATH!
    echo Please install Ollama from https://ollama.com/download
    pause
)

echo.
echo [2/2] Installing Python Packages (via Internet)...
cd app\backend
if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -r requirements.txt

echo.
echo =====================================================
echo   DONE! You can now run the app via START_CHATBOT.bat
echo   (Or run test_desktop_windows.bat inside the app folder)
echo =====================================================
pause
EOF

# 5. Generate the Windows IPC Launcher Script
echo "📝 Generating START_CHATBOT.bat for the IPC..."
cat << 'EOF' > "$TARGET_DIR/START_CHATBOT.bat"
@echo off
cd /d "%~dp0"
echo Starting ISRA Vision Chatbot...

:: Start Ollama in background
start /B ollama serve
timeout /t 3 /nobreak > nul

:: Run Backend
cd /d "%~dp0app\backend"
call venv\Scripts\activate.bat
python main.py
EOF

# 6. Zip it for instant transfer
echo "🗜️ Zipping the lightweight package for instant USB transfer..."
cd "$(dirname "$TARGET_DIR")"
zip -r -q "ISRA_Windows_Online_Package.zip" "ISRA_Windows_Online_Package"

echo "✅ ALL DONE! The lightweight online package is ready."
echo "📦 ZIP File: $HOME/Desktop/ISRA_Windows_Online_Package.zip"
echo "👉 Copy ONLY the .zip file to your USB drive. It will transfer instantly!"
echo "👉 On the Windows IPC, right-click the zip to 'Extract All', then run SETUP_ONLINE.bat"
