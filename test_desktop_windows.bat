@echo off
echo ========================================================
echo Testing Isra Chatbot (Desktop Mode) on Windows
echo ========================================================

:: ── STEP 0: Kill any stale backend processes first ────────────────────────────
echo 0. Cleaning up any existing backend processes...
taskkill /F /IM "python.exe" /FI "WINDOWTITLE eq uvicorn*" >nul 2>&1
taskkill /F /IM "python.exe" /FI "WINDOWTITLE eq main.py*" >nul 2>&1

:: Check if port 8000 is in use and kill the PID
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8000" ^| find "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul
echo    [OK] Port 8000 is free

echo.
echo 1. Building React Frontend...
cd frontend
call npm install
call npm run build
cd ..

echo.
echo 2. Starting Backend and Desktop Window...
cd backend

:: Ensure venv exists and activate it
if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found! Please create one using "python -m venv venv".
    pause
    exit /b 1
)
call venv\Scripts\activate.bat

:: Install dependencies
pip install -r requirements.txt

echo.
echo 3. Creating Desktop Shortcut for Windows...
set SHORTCUT_PATH=%USERPROFILE%\Desktop\Isra Chatbot.bat
echo @echo off > "%SHORTCUT_PATH%"
echo cd /d "%~dp0" >> "%SHORTCUT_PATH%"
echo call test_desktop_windows.bat >> "%SHORTCUT_PATH%"
echo A shortcut 'Isra Chatbot.bat' has been created on your Windows Desktop!
echo.

echo 4. Launching App...
python main.py
pause
