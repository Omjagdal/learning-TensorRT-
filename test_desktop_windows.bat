@echo off
:: Force the script to run in its own directory (fixes issues if run as administrator)
cd /d "%~dp0"

echo ========================================================
echo Testing Isra Chatbot (Desktop Mode) on Windows
echo ========================================================

echo 0. Cleaning up any existing backend processes...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do taskkill /f /pid %%a >nul 2>&1
wmic process where "name='uvicorn.exe'" call terminate >nul 2>&1
wmic process where "name='python.exe' and commandline like '%%main.py%%'" call terminate >nul 2>&1
timeout /t 1 /nobreak >nul
echo    [+] Port 8000 is free

echo.
echo 1. Building React Frontend...
pushd frontend
call npm install
call npm run build
popd

echo.
echo 2. Starting Backend and Desktop Window...
pushd backend

if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found. Creating one now...
    
    :: Try different python commands in case 'python' is not in PATH
    py -m venv venv >nul 2>&1
    if not exist "venv\Scripts\activate.bat" (
        python -m venv venv >nul 2>&1
    )
    if not exist "venv\Scripts\activate.bat" (
        python3 -m venv venv >nul 2>&1
    )
    
    if not exist "venv\Scripts\activate.bat" (
        echo [ERROR] Could not create virtual environment!
        echo Please ensure Python is installed and added to your Windows PATH.
        pause
        exit /b 1
    )
)
call venv\Scripts\activate.bat
pip install -r requirements.txt

echo.
echo 3. Creating Desktop Shortcut for Windows...
set "VBS_SCRIPT=%TEMP%\create_shortcut.vbs"
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%VBS_SCRIPT%"
echo sLinkFile = "%USERPROFILE%\Desktop\Isra Chatbot.lnk" >> "%VBS_SCRIPT%"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%VBS_SCRIPT%"
echo oLink.TargetPath = "%~dp0test_desktop_windows.bat" >> "%VBS_SCRIPT%"
echo oLink.WorkingDirectory = "%~dp0" >> "%VBS_SCRIPT%"
echo oLink.Save >> "%VBS_SCRIPT%"
cscript //nologo "%VBS_SCRIPT%"
del "%VBS_SCRIPT%"
echo A shortcut 'Isra Chatbot' has been created on your Windows Desktop!
echo.

echo 4. Launching App...
python main.py

popd
pause
