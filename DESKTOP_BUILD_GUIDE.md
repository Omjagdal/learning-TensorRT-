# 🖥️ ISRA Chatbot — Desktop App Build Guide

This guide explains how to build **self-contained, fully offline desktop applications** from this project.

The end-user gets **one file** to install. After installation:
- A **"ISRA Vision Chatbot"** shortcut appears on the Desktop
- User double-clicks → app opens in a native window
- **No browser. No terminal. No Python. No internet. No Ollama manual setup.**

---

## 📦 What the Installer Contains

| Component | Size | Notes |
|-----------|------|-------|
| React Frontend (UI) | ~5 MB | Pre-built, served by FastAPI |
| Python backend + libraries | ~3–5 GB | CPU-only PyTorch |
| Ollama binary | ~50 MB | Starts/stops automatically |
| qwen3:8b LLM model | ~5.2 GB | Main language model |
| bge-m3 embedding model | ~2.1 GB | For semantic search |
| bge-reranker-large | ~1.1 GB | For result reranking |
| Marker OCR models | ~500 MB | For PDF processing |
| **Total** | **~12–15 GB** | |

> ⚠️ **Distribute via USB drive or cloud file share (OneDrive, Google Drive)**.

---

## 🚀 Method 1: GitHub Actions (Recommended — No Windows needed)

### Steps

1. **Push to GitHub:**
   ```bash
   git add -A
   git commit -m "Add desktop app build pipeline"
   git push --set-upstream origin main
   ```

2. Go to **[github.com/Omjagdal/learning-TensorRT-/actions](https://github.com/Omjagdal/learning-TensorRT-/actions)**

3. Two workflows will run automatically:
   - `Build Windows Desktop Installer` → `MachineAI_Chatbot_Setup.exe`
   - `Build Mac Desktop App` → `MachineAI_Chatbot_Setup.dmg`

4. Wait ~60–120 minutes (first run downloads ~7 GB of models, cached for later)

5. Click the completed workflow → **Artifacts** section → download your installer

---

## 🪟 Method 2: Build Windows Installer Locally

Run on a **Windows 10/11 machine**.

### Prerequisites

| Tool | Download |
|------|----------|
| Python 3.11 | https://www.python.org/downloads/ |
| Node.js 20+ | https://nodejs.org/ |
| Inno Setup 6 | https://jrsoftware.org/isdl.php |

### Steps

1. Copy the project to the Windows machine
2. Double-click **`build_windows_exe.bat`**
3. Output: `dist\installer\MachineAI_Chatbot_Setup.exe`

---

## 🍎 Method 3: Build Mac App Locally (on this Mac)

```bash
# Install prerequisites (if not already installed)
brew install node create-dmg

# Run the build script
./build_mac_app.sh
```

Output: `dist/installer/MachineAI_Chatbot_Setup.dmg`

---

## 📲 End-User Install Instructions

### Windows
1. Double-click `MachineAI_Chatbot_Setup.exe`
2. Click **Next → Install** → wait 2–5 min → **Finish**
3. Double-click the **"ISRA Vision Chatbot"** desktop icon

### Mac
1. Open `MachineAI_Chatbot_Setup.dmg`
2. Drag **ISRA Vision Chatbot** into **Applications**
3. Open from Launchpad (first time: right-click → Open)

---

## ❓ Troubleshooting

| Problem | Solution |
|---------|---------|
| App opens but LLM doesn't respond | Ollama failed to start. Check `%APPDATA%\ISRAVision\ISRAChatbot\` |
| Very slow responses | Normal without GPU. Consider qwen3:1.7b for faster responses |
| "Windows protected your PC" | Click "More info" → "Run anyway" (app is not code-signed) |
| Mac: "developer unverified" | Right-click → Open → Open |
