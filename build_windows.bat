@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo ISRA Chatbot - Master Build Script (Windows)
echo ========================================================
echo.

:: 1. Build React Frontend
echo [1/5] Building React Frontend...
cd frontend
call npm install
call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] Frontend build failed!
    exit /b %errorlevel%
)
cd ..

:: 2. Build PyInstaller Backend
echo.
echo [2/5] Building PyInstaller Backend...
cd backend
call pyinstaller isra_chatbot.spec --clean -y
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed!
    exit /b %errorlevel%
)
cd ..

:: 3. Copy Backend to Tauri Binaries
echo.
echo [3/4] Preparing Tauri Sidecar...
set TAURI_BIN_DIR=frontend\src-tauri\binaries
mkdir "%TAURI_BIN_DIR%" 2>nul
:: Note: Tauri expects the sidecar directory to be in a specific format if it's not a single exe.
:: Since our PyInstaller output is a directory, we copy the whole directory
:: into a place where the Tauri app can find it at runtime.
set TARGET_DIR=%TAURI_BIN_DIR%\IsraChatbot
mkdir "%TARGET_DIR%" 2>nul
xcopy /E /I /Y "backend\dist\IsraChatbot" "%TARGET_DIR%"

:: 4. Build Tauri App
echo.
echo [4/4] Building Tauri App (Setup .exe)...
cd frontend
call npm run tauri build
if %errorlevel% neq 0 (
    echo [ERROR] Tauri build failed!
    exit /b %errorlevel%
)
cd ..

echo.
echo ========================================================
echo BUILD SUCCESSFUL!
echo Installer is located at: frontend\src-tauri\target\release\bundle\nsis\
echo ========================================================
