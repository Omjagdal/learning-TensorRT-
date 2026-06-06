# Industrial Manual Chatbot

A production-ready Retrieval-Augmented Generation (RAG) system specialized for querying industrial machinery manuals (PDFs). Built with FastAPI, Qdrant, Ollama, BGE-M3, and React.

## Key Features
- **Hierarchical PageIndex**: Preserves Manual → Chapter → Section → Page hierarchy.
- **Hybrid Search**: Combines Qdrant Dense Vector Search (BGE-M3) with Sparse Keyword Search (BM25).
- **Cross-Encoder Reranking**: Uses BGE-Reranker-Large to massively improve retrieval precision.
- **Ollama Integration**: Runs Qwen3 locally with HTTP API streaming, with HuggingFace pipeline fallback.
- **Citation Engine**: Every answer includes precise citations linking to the source manual, chapter, and page number.
- **Self-RAG Pipeline**: 6-stage pipeline (Classify → Retrieve → Rerank → Generate → Validate → Fallback).

## Getting Started

### 1. Prerequisites
- Docker (for Qdrant vector database)
- Ollama (for LLM inference)
- Node.js 18+ (for Frontend)
- Python 3.12 (for Backend)

### 2. Start Services
**Qdrant Vector Database:**
```bash
docker run -d -p 6333:6333 -p 6334:6334 \
    -v $(pwd)/qdrant_storage:/qdrant/storage \
    qdrant/qdrant
```

**Ollama (LLM):**
```bash
ollama run qwen3:8b
```

### 3. Start Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start FastAPI server
uvicorn main:app --reload --port 8000
```

### 4. Start Frontend
```bash
cd frontend
npm install
npm run dev
```

## Configuration
Edit `backend/.env` to configure models, ports, and feature toggles.
