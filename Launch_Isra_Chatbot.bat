@echo off
title Isra Chatbot Launcher
color 0B

echo ===================================================
echo             ISRA CHATBOT LAUNCHER
echo ===================================================
echo.
echo Starting the AI Server via Docker...

:: Check if Docker is running
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [INFO] Docker is not running. Starting Docker Desktop in the background...
    :: Programmatically disable the Docker Dashboard popup in settings
    powershell -Command "$p=\"$env:APPDATA\Docker\settings.json\"; if(Test-Path $p){ $j=Get-Content $p -Raw | ConvertFrom-Json; $j.openUIOnStartup=$false; $j | ConvertTo-Json -Depth 10 | Set-Content $p }"
    start /MIN "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo [INFO] Waiting for Docker to start...
:wait_docker
    timeout /t 3 /nobreak >nul
    docker info >nul 2>&1
    if %ERRORLEVEL% neq 0 goto wait_docker
    echo [SUCCESS] Docker is now running!
    echo.
)

:: Check if the container already exists
docker ps -a --format "{{.Names}}" | findstr /I "^isra_bot$" >nul
if %ERRORLEVEL% equ 0 (
    echo [INFO] Resuming existing Chatbot server...
    docker start isra_bot >nul
) else (
    echo [INFO] First time setup: Launching Chatbot...
    docker run -p 8000:8000 -d --name isra_bot -e EMBEDDING_PROVIDER=ollama -v isra_data:/app/backend/data isra-chatbot:latest >nul
)

echo.
echo [INFO] Waiting for the AI brain to initialize...
timeout /t 5 /nobreak >nul

echo.
echo [SUCCESS] Opening Isra Chatbot in your default web browser!
start http://localhost:8000

echo.
echo You can safely close this black window. The server will keep running in Docker!
timeout /t 10 >nul
