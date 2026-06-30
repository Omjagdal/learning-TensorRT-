@echo off
echo ========================================================
echo Building Isra Chatbot .exe (Windows)
echo ========================================================

echo.
echo 1. Building React Frontend...
cd frontend
call npm install
call npm run build
cd ..

echo.
echo 2. Setting up Python Environment for Build...
cd backend
if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found! Please create one using "python -m venv venv".
    pause
    exit /b 1
)
call venv\Scripts\activate.bat

echo Installing dependencies and PyInstaller...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo 3. Packaging into .exe with PyInstaller...
:: Remove old build folders if they exist
if exist build rmdir /S /Q build
if exist dist rmdir /S /Q dist

:: Use PyInstaller to build a single-file executable or single-directory. 
:: A single directory (--onedir) is usually more stable for large ML projects than --onefile.
:: We include the frontend dist folder so the server can serve the React UI.
pyinstaller --noconfirm --name "IsraChatbot" ^
    --add-data "../frontend/dist;frontend/dist" ^
    --hidden-import "uvicorn" ^
    --hidden-import "fastapi" ^
    --hidden-import "webview" ^
    --hidden-import "loguru" ^
    --windowed ^
    main.py

echo.
echo ========================================================
echo Build Complete!
echo You can find your packaged application in:
echo backend\dist\IsraChatbot\IsraChatbot.exe
echo ========================================================
pause
