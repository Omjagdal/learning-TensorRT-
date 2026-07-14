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

> ⚠️ **Distribute via USB drive or cloud file share (OneDrive, Google Drive)**. Do NOT email the installer.

---

## 🚀 Method 1: GitHub Actions (Recommended — Easiest)

No local Windows machine needed. GitHub's cloud builds the installer for you.

### Prerequisites
- Push this project to a GitHub repository
- (Free GitHub account)

### Steps

1. **Commit and push** all files to your GitHub repo:
   ```bash
   git add -A
   git commit -m "Add desktop app build pipeline"
   git push
   ```

2. Go to your repository on **GitHub.com** → click the **Actions** tab

3. You'll see two workflows running:
   - `Build Windows Desktop Installer` → produces `MachineAI_Chatbot_Setup.exe`
   - `Build Mac Desktop App` → produces `MachineAI_Chatbot_Setup.dmg`

4. Wait ~60–120 minutes (first run downloads ~7 GB of models, cached for later)

5. Click the completed workflow → **Artifacts** section → download your installer

> 💡 **Tip:** After the first run, model downloads are cached. Subsequent builds take ~15–20 minutes.

---

## 🪟 Method 2: Build Windows Installer Locally

Run this on a **Windows 10/11 machine** with internet access.

### Prerequisites (all free)

| Tool | Download |
|------|----------|
| Python 3.11 | https://www.python.org/downloads/ |
| Node.js 20+ | https://nodejs.org/ |
| Inno Setup 6 | https://jrsoftware.org/isdl.php |
| Git (optional) | https://git-scm.com/ |

### Steps

1. Copy the project folder to the Windows machine (USB, Git clone, etc.)

2. Double-click **`build_windows_exe.bat`**

3. The script will:
   - Build the React frontend
   - Install Python dependencies
   - Download the Ollama binary
   - Pull qwen3:8b and bge-m3 models (~7 GB, first run only)
   - Download bge-reranker-large (~1.1 GB)
   - Run PyInstaller to bundle everything
   - Run Inno Setup to create the installer

4. Output: **`dist\installer\MachineAI_Chatbot_Setup.exe`** (~12–15 GB)

5. Copy `MachineAI_Chatbot_Setup.exe` to a USB drive

---

## 🍎 Method 3: Build Mac App Locally

Run this on the **Mac you are on right now**.

### Prerequisites

```bash
# Install Homebrew if you don't have it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install tools
brew install node python@3.11 create-dmg
```

### Steps

1. Open Terminal in the project folder

2. Run:
   ```bash
   ./build_mac_app.sh
   ```

3. The script will do everything automatically (same steps as Windows)

4. Output: **`dist/installer/MachineAI_Chatbot_Setup.dmg`**

---

## 📲 How to Install (End-User Instructions)

### Windows
1. Copy `MachineAI_Chatbot_Setup.exe` from the USB drive
2. Double-click the file
3. Click **Next → Install**
4. Wait 2–5 minutes
5. Click **Finish**
6. A **"ISRA Vision Chatbot"** icon appears on the Desktop
7. Double-click to launch → the app opens

### Mac
1. Open `MachineAI_Chatbot_Setup.dmg`
2. Drag **ISRA Vision Chatbot** into the **Applications** folder
3. Open **Launchpad** → click **ISRA Vision Chatbot**
4. (First launch only: right-click → Open if macOS blocks it)

---

## 🗂️ Project Files Added

| File | Purpose |
|------|---------|
| `backend/app/core/ollama_manager.py` | Auto-manages the bundled Ollama subprocess |
| `isra_chatbot.spec` | PyInstaller bundle configuration |
| `build_windows_exe.bat` | Full Windows build script |
| `build_mac_app.sh` | Full Mac build script |
| `installer/windows_setup.iss` | Inno Setup installer configuration |
| `.github/workflows/build_windows_exe.yml` | GitHub Actions — Windows cloud build |
| `.github/workflows/build_mac_app.yml` | GitHub Actions — Mac cloud build |

---

## 🔧 How It Works Internally

When the user launches the installed app:

```
IsraChatbot.exe
      │
      ├─ Starts bundled Ollama (ollama.exe serve) as a hidden background process
      │    └─ Points to bundled model directory (qwen3:8b, bge-m3)
      │
      ├─ Starts FastAPI/Uvicorn server on http://127.0.0.1:8000
      │    ├─ Loads bge-reranker-large (from bundled HF cache)
      │    ├─ Loads bge-m3 embedding model (from bundled HF cache)
      │    └─ Serves the React frontend from bundled dist/
      │
      └─ Opens pywebview native desktop window → http://127.0.0.1:8000

[User closes window] → Ollama is terminated → App exits cleanly
```

All AI models, the database engine (Qdrant embedded), and user data (uploaded PDFs, vector DB) are stored in the user's AppData folder — **separate from the install folder** so it persists across app updates.

---

## ❓ Troubleshooting

| Problem | Solution |
|---------|---------|
| App opens but LLM doesn't respond | Ollama failed to start. Check the log file in `%APPDATA%\ISRAVision\ISRAChatbot\` |
| Very slow responses (5–10 min) | Normal on CPUs without GPU. Consider using qwen3:1.7b for faster responses |
| "Windows protected your PC" warning | Click "More info" → "Run anyway". This is because the app is not code-signed |
| Mac: "Cannot open because developer unverified" | Right-click → Open → Open |
| Installation fails on old machine | Ensure Windows 10 (1903+) or macOS 12+. Older systems not supported |
