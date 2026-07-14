#!/bin/bash
# =============================================================================
# ISRA Chatbot — Full Offline Mac Desktop App Builder
# =============================================================================
# Produces: dist/IsraChatbot.dmg
#
# Requirements (all free):
#   - Python 3.11+   (brew install python@3.11)
#   - Node.js 20+    (brew install node)
#   - create-dmg     (brew install create-dmg)
#   - Homebrew       (https://brew.sh)
#
# Run this on your Mac. The output .dmg can be distributed offline.
# =============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RESET="\033[0m"

step() { echo -e "\n${BOLD}[$1/8] $2...${RESET}"; }
ok()   { echo -e "${GREEN}[OK]${RESET} $1"; }
warn() { echo -e "${YELLOW}[WARN]${RESET} $1"; }

echo -e "${BOLD}"
echo "================================================================"
echo "  ISRA Vision Chatbot | Full Offline Mac Desktop App Builder"
echo "  Produces: dist/IsraChatbot.dmg"
echo "================================================================"
echo -e "${RESET}"

# ── Step 1: Check prerequisites ───────────────────────────────────────────────
step 1 "Checking prerequisites"
command -v node  >/dev/null 2>&1 || { echo "[ERROR] Node.js not found. Run: brew install node"; exit 1; }
command -v npm   >/dev/null 2>&1 || { echo "[ERROR] npm not found. Run: brew install node"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "[ERROR] Python 3 not found. Run: brew install python@3.11"; exit 1; }
ok "Prerequisites found"

# ── Step 2: Build React Frontend ─────────────────────────────────────────────
step 2 "Building React Frontend"
cd "$ROOT/frontend"
npm install --silent
npm run build
[[ -f "$ROOT/frontend/dist/index.html" ]] || { echo "[ERROR] Frontend build failed!"; exit 1; }
cd "$ROOT"
ok "Frontend built: frontend/dist/"

# ── Step 3: Set up Python virtual environment ─────────────────────────────────
step 3 "Setting up Python build environment"
BUILD_VENV="$ROOT/backend/build_venv"
if [[ ! -f "$BUILD_VENV/bin/activate" ]]; then
    python3 -m venv "$BUILD_VENV"
fi
source "$BUILD_VENV/bin/activate"

# CPU-only PyTorch (avoids 4 GB CUDA download)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu -q
# All project dependencies
pip install -r "$ROOT/backend/requirements.txt" -q
# Build tools
pip install pyinstaller pywebview platformdirs create-dmg -q 2>/dev/null || true
ok "Python environment ready"

# ── Step 4: Download Ollama binary ────────────────────────────────────────────
step 4 "Preparing bundled Ollama binary"
OLLAMA_DIR="$ROOT/bundle_assets/ollama"
mkdir -p "$OLLAMA_DIR"

ARCH="$(uname -m)"
if [[ "$ARCH" == "arm64" ]]; then
    OLLAMA_URL="https://github.com/ollama/ollama/releases/latest/download/ollama-darwin-arm64"
else
    OLLAMA_URL="https://github.com/ollama/ollama/releases/latest/download/ollama-darwin-amd64"
fi

if [[ ! -f "$OLLAMA_DIR/ollama" ]]; then
    echo "Downloading Ollama for macOS ($ARCH)..."
    curl -fsSL "$OLLAMA_URL" -o "$OLLAMA_DIR/ollama"
    chmod +x "$OLLAMA_DIR/ollama"
    ok "Ollama binary downloaded"
else
    ok "Ollama binary already present, skipping download"
fi

# ── Step 5: Pre-pull AI models into bundle_assets ────────────────────────────
step 5 "Bundling AI models (first run downloads ~7 GB)"
MODELS_DIR="$ROOT/bundle_assets/ollama_models"
mkdir -p "$MODELS_DIR"

export OLLAMA_MODELS="$MODELS_DIR"
"$OLLAMA_DIR/ollama" serve &>/dev/null &
OLLAMA_PID=$!
echo "Waiting for Ollama to start..."
sleep 8

# Pull qwen3:8b (5.2 GB LLM)
if ! "$OLLAMA_DIR/ollama" list 2>/dev/null | grep -q "qwen3:8b"; then
    echo "Pulling qwen3:8b (~5.2 GB)..."
    "$OLLAMA_DIR/ollama" pull qwen3:8b
else
    ok "qwen3:8b already cached"
fi

# Pull bge-m3 (2.1 GB embedding model)
if ! "$OLLAMA_DIR/ollama" list 2>/dev/null | grep -q "bge-m3"; then
    echo "Pulling bge-m3 (~2.1 GB)..."
    "$OLLAMA_DIR/ollama" pull bge-m3
else
    ok "bge-m3 already cached"
fi

kill $OLLAMA_PID 2>/dev/null || true
ok "Ollama models ready in: bundle_assets/ollama_models"

# ── Step 6: Pre-cache HuggingFace models ─────────────────────────────────────
step 6 "Pre-caching HuggingFace models (reranker, marker)"
HF_CACHE="$ROOT/bundle_assets/hf_cache"
mkdir -p "$HF_CACHE"
export HF_HOME="$HF_CACHE"
export TRANSFORMERS_CACHE="$HF_CACHE/hub"

python3 -c "
from sentence_transformers import CrossEncoder
print('Downloading bge-reranker-large...')
CrossEncoder('BAAI/bge-reranker-large')
print('Done.')
"

# Pre-cache Marker OCR models
python3 -c "
import tempfile, os
from pathlib import Path
pdf_bytes = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n200\n%%EOF'
tmp = Path(tempfile.gettempdir()) / 'dummy.pdf'
tmp.write_bytes(pdf_bytes)
os.system(f'marker_single {tmp} {tempfile.gettempdir()}/marker_out 2>/dev/null || true')
print('Marker models cached.')
"
ok "HuggingFace models cached in: bundle_assets/hf_cache"

# ── Step 7: Run PyInstaller ──────────────────────────────────────────────────
step 7 "Building standalone .app bundle with PyInstaller"
pyinstaller --clean -y isra_chatbot.spec
[[ -d "$ROOT/dist/IsraChatbot" ]] || { echo "[ERROR] PyInstaller failed!"; exit 1; }
ok "PyInstaller build complete: dist/IsraChatbot/"

# ── Step 8: Create .dmg installer ───────────────────────────────────────────
step 8 "Creating .dmg installer"
mkdir -p "$ROOT/dist/installer"

if command -v create-dmg >/dev/null 2>&1; then
    create-dmg \
        --volname "ISRA Vision Chatbot" \
        --volicon "$ROOT/icon.icns" \
        --window-pos 200 200 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "IsraChatbot.app" 175 190 \
        --hide-extension "IsraChatbot.app" \
        --app-drop-link 425 185 \
        "$ROOT/dist/installer/MachineAI_Chatbot_Setup.dmg" \
        "$ROOT/dist/IsraChatbot.app"
    ok "DMG created: dist/installer/MachineAI_Chatbot_Setup.dmg"
else
    warn "create-dmg not found. Run: brew install create-dmg"
    warn "The app bundle is still available at: dist/IsraChatbot.app"
    # Simple hdiutil-based DMG as fallback
    hdiutil create -volname "ISRA Vision Chatbot" \
        -srcfolder "$ROOT/dist/IsraChatbot.app" \
        -ov -format UDZO \
        "$ROOT/dist/installer/MachineAI_Chatbot_Setup.dmg"
    ok "Basic DMG created: dist/installer/MachineAI_Chatbot_Setup.dmg"
fi

echo ""
echo -e "${BOLD}================================================================"
echo "  BUILD COMPLETE!"
echo -e "================================================================${RESET}"
echo ""
echo "  App bundle : dist/IsraChatbot.app"
echo "  DMG file   : dist/installer/MachineAI_Chatbot_Setup.dmg"
echo ""
echo "  Distribute the .dmg file. Users:"
echo "    1. Open the .dmg"
echo "    2. Drag 'ISRA Vision Chatbot' to Applications"
echo "    3. Launch from Applications — no internet needed!"
echo ""
