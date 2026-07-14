#!/bin/bash
# =============================================================================
# ISRA Chatbot — Full Offline Mac Desktop App Builder
# Produces: dist/installer/MachineAI_Chatbot_Setup.dmg
# =============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BOLD="\033[1m"; GREEN="\033[0;32m"; YELLOW="\033[0;33m"; RESET="\033[0m"
step() { echo -e "\n${BOLD}[$1/8] $2...${RESET}"; }
ok()   { echo -e "${GREEN}[OK]${RESET} $1"; }
warn() { echo -e "${YELLOW}[WARN]${RESET} $1"; }

echo -e "${BOLD}"
echo "================================================================"
echo "  ISRA Vision Chatbot | Full Offline Mac Desktop App Builder"
echo "  Produces: dist/installer/MachineAI_Chatbot_Setup.dmg"
echo "================================================================"
echo -e "${RESET}"

step 1 "Checking prerequisites"
command -v node    >/dev/null 2>&1 || { echo "[ERROR] Node.js not found. Run: brew install node"; exit 1; }

# Prefer python3.11, fallback to python3 if it's the right version
if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_CMD="python3.11"
elif command -v python3.10 >/dev/null 2>&1; then
    PYTHON_CMD="python3.10"
else
    PYTHON_CMD="python3"
fi
$PYTHON_CMD --version >/dev/null 2>&1 || { echo "[ERROR] Python not found. Run: brew install python@3.11"; exit 1; }
ok "Prerequisites found ($PYTHON_CMD)"

step 2 "Building React Frontend"
cd "$ROOT/frontend"
npm install --silent
npm run build
[[ -f "$ROOT/frontend/dist/index.html" ]] || { echo "[ERROR] Frontend build failed!"; exit 1; }
cd "$ROOT"
ok "Frontend built"

step 3 "Setting up Python build environment"
BUILD_VENV="$ROOT/backend/build_venv"
[[ -f "$BUILD_VENV/bin/activate" ]] || $PYTHON_CMD -m venv "$BUILD_VENV"
source "$BUILD_VENV/bin/activate"
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu --no-cache-dir --no-compile -q
pip install -r "$ROOT/backend/requirements.txt" --no-cache-dir --no-compile -q
pip install pyinstaller pywebview platformdirs --no-cache-dir --no-compile -q
ok "Python environment ready"

step 4 "Preparing bundled Ollama binary"
OLLAMA_DIR="$ROOT/bundle_assets/ollama"
mkdir -p "$OLLAMA_DIR"
OLLAMA_URL="https://github.com/ollama/ollama/releases/latest/download/ollama-darwin.tgz"
if [[ ! -f "$OLLAMA_DIR/ollama" ]]; then
    echo "Downloading Ollama for macOS..."
    curl -fsSL -L "$OLLAMA_URL" -o "$OLLAMA_DIR/ollama-darwin.tgz"
    tar -xzf "$OLLAMA_DIR/ollama-darwin.tgz" -C "$OLLAMA_DIR"
    chmod +x "$OLLAMA_DIR/ollama"
    rm -f "$OLLAMA_DIR/ollama-darwin.tgz"
    ok "Ollama binary downloaded and extracted"
else
    ok "Ollama binary already present"
fi

step 5 "Bundling AI models (first run downloads ~7 GB)"
MODELS_DIR="$ROOT/bundle_assets/ollama_models"
mkdir -p "$MODELS_DIR"
export OLLAMA_MODELS="$MODELS_DIR"
"$OLLAMA_DIR/ollama" serve &>/dev/null &
OLLAMA_PID=$!
echo "Waiting for Ollama to start..."
sleep 8

if ! "$OLLAMA_DIR/ollama" list 2>/dev/null | grep -q "qwen3:8b"; then
    echo "Pulling qwen3:8b (~5.2 GB)..."
    "$OLLAMA_DIR/ollama" pull qwen3:8b
else
    ok "qwen3:8b already cached"
fi

if ! "$OLLAMA_DIR/ollama" list 2>/dev/null | grep -q "bge-m3"; then
    echo "Pulling bge-m3 (~2.1 GB)..."
    "$OLLAMA_DIR/ollama" pull bge-m3
else
    ok "bge-m3 already cached"
fi
kill $OLLAMA_PID 2>/dev/null || true
ok "Ollama models ready"

step 6 "Pre-caching HuggingFace models"
HF_CACHE="$ROOT/bundle_assets/hf_cache"
mkdir -p "$HF_CACHE"
export HF_HOME="$HF_CACHE"
export TRANSFORMERS_CACHE="$HF_CACHE/hub"
python3 -c "
from sentence_transformers import CrossEncoder
CrossEncoder('BAAI/bge-reranker-large')
print('bge-reranker-large ready.')
"
ok "HuggingFace models cached"

step 7 "Building standalone .app bundle with PyInstaller"
pyinstaller --clean -y isra_chatbot.spec
[[ -d "$ROOT/dist/IsraChatbot" ]] || { echo "[ERROR] PyInstaller failed!"; exit 1; }
[[ -d "$ROOT/dist/IsraChatbot.app" ]] || { echo "[ERROR] PyInstaller BUNDLE step failed — no .app created!"; exit 1; }
ok "PyInstaller build complete"

# ── Strip kernel-level xattrs (com.apple.provenance) and re-sign ──────────────
# macOS tracks provenance of files installed via pip. These xattrs block
# codesigning and cause the app to crash instantly when opened from Applications.
# rsync with --no-xattrs copies cleanly into a fresh directory tree.
echo "Stripping extended attributes and signing app bundle..."
CLEAN_APP="$ROOT/dist/IsraChatbot_signed.app"
rm -rf "$CLEAN_APP"
mkdir -p "$CLEAN_APP"
rsync -a --no-xattrs "$ROOT/dist/IsraChatbot.app/" "$CLEAN_APP/"
codesign --force --deep --sign - "$CLEAN_APP" 2>&1 | grep -v 'replacing existing' || true
codesign --verify --deep --strict "$CLEAN_APP" && ok "App signed and verified" || warn "Signing had warnings but proceeding"
rm -rf "$ROOT/dist/IsraChatbot.app"
mv "$CLEAN_APP" "$ROOT/dist/IsraChatbot.app"
ok "App bundle ready: dist/IsraChatbot.app"

step 8 "Creating .dmg installer"
mkdir -p "$ROOT/dist/installer"
rm -f "$ROOT/dist/installer/MachineAI_Chatbot_Setup.dmg"
if command -v create-dmg >/dev/null 2>&1; then
    create-dmg \
        --volname "ISRA Vision Chatbot" \
        --window-pos 200 200 \
        --window-size 600 400 \
        --icon-size 100 \
        --hide-extension "IsraChatbot.app" \
        --app-drop-link 425 185 \
        "$ROOT/dist/installer/MachineAI_Chatbot_Setup.dmg" \
        "$ROOT/dist/IsraChatbot.app" 2>&1 | grep -v 'hdiutil: internet-enable' || \
    hdiutil create -volname "ISRA Vision Chatbot" \
        -srcfolder "$ROOT/dist/IsraChatbot.app" \
        -ov -format UDZO \
        "$ROOT/dist/installer/MachineAI_Chatbot_Setup.dmg"
else
    warn "create-dmg not found. Run: brew install create-dmg"
    hdiutil create -volname "ISRA Vision Chatbot" \
        -srcfolder "$ROOT/dist/IsraChatbot.app" \
        -ov -format UDZO \
        "$ROOT/dist/installer/MachineAI_Chatbot_Setup.dmg"
fi
ok "DMG created"

echo ""
echo -e "${BOLD}================================================================"
echo "  BUILD COMPLETE!"
echo "  App bundle : dist/IsraChatbot.app"
echo "  DMG file   : dist/installer/MachineAI_Chatbot_Setup.dmg"
echo -e "================================================================${RESET}"
