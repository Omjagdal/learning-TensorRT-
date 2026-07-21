@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo ISRA Chatbot - Offline Bundler Script
echo ========================================================
echo.

set BUILD_DIR=..\backend\dist\IsraChatbot
set OLLAMA_DEST=%BUILD_DIR%\ollama
set OLLAMA_MODELS_DEST=%OLLAMA_DEST%\models

if not exist "%BUILD_DIR%" (
    echo [ERROR] Backend build directory not found! Run PyInstaller first.
    exit /b 1
)

echo [1/3] Creating directory structure...
mkdir "%OLLAMA_DEST%" 2>nul
mkdir "%OLLAMA_MODELS_DEST%" 2>nul

echo [2/3] Copying Ollama executable...
:: Try default install locations
set OLLAMA_EXE_SRC=%LOCALAPPDATA%\Programs\Ollama\ollama.exe
if not exist "%OLLAMA_EXE_SRC%" (
    echo [ERROR] Cannot find ollama.exe at %OLLAMA_EXE_SRC%
    echo Please install Ollama first.
    exit /b 1
)
copy /Y "%OLLAMA_EXE_SRC%" "%OLLAMA_DEST%\ollama.exe"

echo [3/3] Copying Ollama models (qwen3:8b, bge-m3, qwen3-vl:8b)...
set OLLAMA_MODELS_SRC=%USERPROFILE%\.ollama\models
if not exist "%OLLAMA_MODELS_SRC%" (
    echo [WARNING] Default Ollama models folder not found at %OLLAMA_MODELS_SRC%
    echo Attempting to check OLLAMA_MODELS env var...
    if "%OLLAMA_MODELS%"=="" (
        echo [ERROR] Could not find models folder.
        exit /b 1
    ) else (
        set OLLAMA_MODELS_SRC=%OLLAMA_MODELS%
    )
)

xcopy /E /I /Y "%OLLAMA_MODELS_SRC%" "%OLLAMA_MODELS_DEST%"

echo.
echo ========================================================
echo DONE! Ollama and models bundled into:
echo %OLLAMA_DEST%
echo ========================================================
