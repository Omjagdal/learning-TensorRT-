# ISRA VISION OMI Assistant

A production-ready Retrieval-Augmented Generation (RAG) system specialized for querying industrial machinery manuals (PDFs). Built with FastAPI, embedded Qdrant, Ollama, BGE-M3, and React. 

**This project runs as a fully offline, native desktop application using PyWebView.**

## Key Features
- **Hierarchical PageIndex**: Preserves Manual → Chapter → Section → Page hierarchy.
- **Hybrid Search**: Combines Qdrant Dense Vector Search (BGE-M3 via Ollama) with Sparse Keyword Search (BM25).
- **Cross-Encoder Reranking**: Uses BGE-Reranker-Large to massively improve retrieval precision.
- **Ollama Integration**: Runs Qwen3 locally with HTTP API streaming.
- **Dynamic Mermaid Diagrams**: Automatically maps out logic, steps, and technical concepts using linear flowcharts directly in the chat UI.
- **Citation Engine**: Every answer includes precise citations linking to the source manual, chapter, and page number, along with image extracts.
- **Self-RAG Pipeline**: 6-stage pipeline (Classify → Retrieve → Rerank → Generate → Validate → Fallback).
- **Fully Offline**: Uses an embedded Qdrant vector database—no Docker required!

## Getting Started

### 1. Prerequisites
- **Ollama**: Must be installed on your system.
- **Python 3.10+** (for the backend environment).
- *(Note: Node.js is only required for frontend development, and Docker is no longer required).*

### 2. Install Required Models
Make sure you have pulled the required models in Ollama:
```bash
ollama pull qwen3:8b
ollama pull bge-m3
```

### 3. Launch the Application

You do not need to start the frontend and backend separately. The project includes automated launch scripts that will start the backend, start Ollama if it's not running, and open the desktop GUI window.

**On macOS / Linux:**
```bash
bash test_desktop_mac.sh
```

**On Windows:**
```cmd
test_desktop_windows.bat
```

*(Note: `build_exe.bat` is also available for bundling the app via PyInstaller).*

## Configuration
Edit `backend/.env` to configure models, chunk sizes, and feature toggles.
