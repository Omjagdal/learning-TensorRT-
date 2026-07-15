# ISRA Vision Chatbot — Desktop Build & Deployment Guide

## Quick Summary

| Method | Internet Required | Time | Best For |
|--------|------------------|------|----------|
| [Option A](#option-a-copy-paste-models-usb) | ❌ Never | 5 min setup | Offline/enterprise machines |
| [Option B](#option-b-auto-download-on-first-launch) | ✅ First launch only | 30 min first launch | Single machine setup |
| [Option C](#option-c-build-the-installer-via-github) | ✅ To build | 45 min build | Creating distributable installer |

---

## Option A: Copy-Paste Models (USB / Fully Offline) ✅ RECOMMENDED

Use this when deploying to machines **with no internet**. Copy models from one machine to a USB drive and deploy to all others.

### Step 1 — Install the app
Run `MachineAI_Chatbot_Setup.exe` on the target machine. This installs in ~1 minute.

### Step 2 — Create the models folder

After install, create this folder structure next to `IsraChatbot.exe`:

```
C:\Program Files\ISRA Vision Chatbot\
├── IsraChatbot.exe
├── _internal\
└── models\                        ← CREATE THIS FOLDER
    ├── ollama_models\             ← Copy from source machine
    │   ├── manifests\
    │   └── blobs\
    └── hf_cache\                  ← Copy from source machine
        └── hub\
            └── models--BAAI--bge-reranker-large\
```

### Step 3 — Where to find models on the SOURCE machine

Copy these folders FROM a machine that already has the app running:

| What | Source Path (copy FROM here) | Destination (paste HERE) |
|------|-------------------------------|--------------------------|
| **Ollama models** | `C:\Users\<name>\AppData\Local\ISRAVision\ISRAChatbot\ollama_models\` | `<app_dir>\models\ollama_models\` |
| **HuggingFace models** | `C:\Users\<name>\AppData\Local\ISRAVision\ISRAChatbot\hf_cache\` | `<app_dir>\models\hf_cache\` |

> **Tip:** You can also find Ollama models at `C:\Users\<name>\.ollama\models\` if Ollama was installed separately on the source machine.

### Step 4 — Launch the app
Double-click the desktop icon. The app detects the `models/` folder automatically and starts **100% offline, instantly**.

---

## Option B: Auto-Download on First Launch

If the target machine has internet access **at least once**:

1. Install `MachineAI_Chatbot_Setup.exe`
2. Launch the app — it will automatically download:
   - `qwen3:8b` (~5.2 GB) — the main AI model
   - `bge-m3` (~2.1 GB) — the embedding model
   - `bge-reranker-large` (~1.3 GB) — the reranker model
3. Wait ~20-45 minutes for downloads to complete
4. After that: **fully offline forever** — no internet needed again

Models are saved to:
```
C:\Users\<name>\AppData\Local\ISRAVision\ISRAChatbot\
```

---

## Option C: Build the Installer via GitHub

1. Push code to `main` branch on GitHub
2. Go to → **Actions** → **Build Windows Desktop Installer**
3. Wait ~45 minutes for the build
4. Download **`MachineAI_Chatbot_Setup.exe`** from the Artifacts section

---

## 🍎 Build Mac App Locally

```bash
# Prerequisites (one-time)
brew install node create-dmg

# Build
./build_mac_app.sh

# Output
dist/installer/MachineAI_Chatbot_Setup.dmg
```

---

## 🪟 Build Windows Installer Locally (on Windows)

### Prerequisites

| Tool | Download |
|------|----------|
| Python 3.11 (64-bit) | https://www.python.org/downloads/ |
| Node.js 20+ | https://nodejs.org/ |
| Inno Setup 6 | https://jrsoftware.org/isdl.php |
| Git | https://git-scm.com/ |

### Steps

```cmd
:: Clone the project
git clone https://github.com/Omjagdal/learning-TensorRT-.git
cd learning-TensorRT-

:: Run the build (takes ~30-60 min first time)
build_windows_exe.bat

:: Output
dist\installer\MachineAI_Chatbot_Setup.exe
```

---

## System Requirements

| Component | Minimum |
|-----------|---------|
| OS | Windows 10 (64-bit, any build) or Windows 11 |
| RAM | 8 GB (16 GB recommended) |
| Storage | 15 GB free (for models + app) |
| CPU | x64, supports AVX instructions (any modern CPU) |
| Internet | Only needed on first launch (if not using Option A) |
