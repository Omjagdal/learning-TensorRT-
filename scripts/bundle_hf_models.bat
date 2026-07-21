@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo ISRA Chatbot - HuggingFace Models Offline Bundler
echo ========================================================
echo.

set BUILD_DIR=..\backend\dist\IsraChatbot
set HF_DEST=%BUILD_DIR%\hf_cache

if not exist "%BUILD_DIR%" (
    echo [ERROR] Backend build directory not found! Run PyInstaller first.
    exit /b 1
)

echo [1/2] Creating directory structure...
mkdir "%HF_DEST%" 2>nul

echo [2/2] Copying HuggingFace Cache...
set HF_SRC=%USERPROFILE%\.cache\huggingface\hub
if not exist "%HF_SRC%" (
    echo [WARNING] Default HuggingFace cache folder not found at %HF_SRC%
    echo Attempting to check HF_HOME env var...
    if "%HF_HOME%"=="" (
        echo [ERROR] Could not find HF cache folder.
        exit /b 1
    ) else (
        set HF_SRC=%HF_HOME%\hub
    )
)

:: Only copy the reranker model (BAAI/bge-reranker-large) to save space
:: We assume it's already downloaded on the build machine
xcopy /E /I /Y "%HF_SRC%\models--BAAI--bge-reranker-large" "%HF_DEST%\models--BAAI--bge-reranker-large"

echo.
echo ========================================================
echo DONE! HuggingFace cache bundled into:
echo %HF_DEST%
echo Note: Set HF_HOME=%%cd%%\hf_cache when running the app.
echo ========================================================
