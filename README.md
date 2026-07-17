# ISRA Vision Industrial AI Assistant

A production-ready, **100% offline** Retrieval-Augmented Generation (RAG) system specialized for querying industrial machinery manuals, SOPs, and technical PDFs. 

Built using a modern desktop architecture: **Tauri (Rust) + React + Python (FastAPI)**.

## Key Features
- **Fully Offline Desktop App**: Runs securely with zero internet connection via a native Tauri window.
- **Hierarchical PageIndex**: Preserves Manual → Chapter → Section → Page hierarchy.
- **Hybrid Search**: Combines Dense Vector Search (BGE-M3) with Sparse Keyword Search (BM25).
- **Cross-Encoder Reranking**: Uses BGE-Reranker-Large to massively improve retrieval precision.
- **Local LLM Integration**: Uses Qwen3 via Ollama for entirely private inference.
- **Citation Engine**: Every answer includes precise citations linking to the source manual and page number.
- **Structured Logging**: Maintains detailed `application.log`, `backend.log`, `rag.log`, `error.log`, and `performance.log`.

## Architecture (DPR Compliant)
```text
Chatbot.exe (Tauri Rust Shell)
│
├── Spawns → backend_server.exe (Python PyInstaller Sidecar)
│               ├── FastAPI Server (127.0.0.1:8765)
│               ├── Qdrant Vector DB
│               ├── PDF Parser (Marker)
│               ├── BGE-M3 + Reranker
│               └── Ollama (Qwen3)
│
└── Opens WebView2 Window → Native Desktop UI
```

## Getting Started

### 1. Prerequisites (Development)
- **Rust**: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
- **Node.js**: v22+
- **Python**: 3.10+
- **Ollama**: Installed locally

### 2. Development Run
You can run the application locally without compiling it to an `.exe`:
```bash
# Terminal 1: Start the backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py

# Terminal 2: Start the frontend
cd frontend
npm install
npm run dev
```

### 3. Building for Production (Windows)
The CI pipeline handles this automatically, but to build manually on Windows:
```cmd
# 1. Build the Python backend sidecar
cd backend
pip install pyinstaller
pyinstaller --clean -y ../isra_chatbot.spec

# 2. Build the Tauri frontend shell
cd ../src-tauri
cargo tauri build --target x86_64-pc-windows-msvc
```
This produces three artifacts in `src-tauri/target/.../bundle/`:
- NSIS Installer (`.exe` setup)
- MSI Installer
- Portable Executable

## Configuration
Users can modify the application behavior by editing `config/config.json`.
There is no need to recompile the application to change models, vector databases, or retrieval limits.

*Note: GPU usage is currently disabled by user request to ensure maximum compatibility across all machines.*
