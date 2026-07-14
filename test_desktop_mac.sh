#!/bin/bash
echo "========================================================"
echo "Testing Isra Chatbot (Desktop Mode) on macOS"
echo "========================================================"

# ── STEP 0: Kill any stale backend processes first ────────────────────────────
echo "0. Cleaning up any existing backend processes..."
pkill -9 -f "uvicorn main:app" 2>/dev/null || true
pkill -9 -f "python main.py" 2>/dev/null || true
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
sleep 1
echo "   ✅ Port 8000 is free"

echo ""
echo "1. Building React Frontend..."
cd frontend
npm install
npm run build
cd ..

echo ""
echo "2. Starting Backend and Desktop Window..."
cd backend
if [ ! -f "venv/bin/activate" ]; then
    echo "Virtual environment not found. Creating one now..."
    python3 -m venv venv || python -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt

echo ""
echo "3. Creating Desktop Shortcut for Mac..."
cat << EOF > "$HOME/Desktop/Isra Chatbot.command"
#!/bin/bash
cd "$PWD"
cd ..
bash test_desktop_mac.sh
EOF
chmod +x "$HOME/Desktop/Isra Chatbot.command"
echo "A shortcut 'Isra Chatbot.command' has been created on your Mac Desktop!"
echo ""

echo "4. Launching App..."
python3 main.py || python main.py
