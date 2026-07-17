"""
core/config.py — Application configuration via pydantic-settings.
All values can be overridden through environment variables or the .env file.

Supports the full Industrial Manual Chatbot stack:
  - Qdrant vector database
  - BGE-M3 embeddings
  - BGE-Reranker-Large cross-encoder
  - Hybrid search (Vector + BM25)
  - Qwen3 8B via Ollama
  - Hierarchical PageIndex RAG
"""

import sys
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = "Industrial Manual Chatbot"
    app_version: str = "2.0.0"
    debug: bool = False

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000

    # ── Storage Paths ─────────────────────────────────────────────────────────
    upload_dir: Path = Path("./data/manuals")

    # ── Chunking ──────────────────────────────────────────────────────────────
    chunk_size: int = 900
    chunk_overlap: int = 120

    # ── Retrieval ─────────────────────────────────────────────────────────────
    top_k_results: int = 5
    retrieval_top_k: int = 20       # Candidates before reranking
    reranker_top_k: int = 5         # Results after reranking

    # ── Self-RAG Pipeline ─────────────────────────────────────────────────────
    relevance_threshold: float = 0.3
    validation_enabled: bool = True
    max_retries: int = 1
    classify_enabled: bool = True

    # ── Qdrant Vector Database ────────────────────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "industrial_manuals"
    qdrant_use_embedded: bool = True
    qdrant_embedded_path: Path = Path("./data/qdrant_storage")

    # ── Embeddings (BGE-M3) ───────────────────────────────────────────────────
    embedding_model_name: str = "BAAI/bge-m3"
    embedding_dimension: int = 1024
    embedding_batch_size: int = 32
    embedding_provider: str = "local"  # "local" (FlagEmbedding) or "ollama"

    # ── Reranker (BGE-Reranker-Large) ─────────────────────────────────────────
    reranker_model_name: str = "BAAI/bge-reranker-large"
    reranker_enabled: bool = True

    # ── Hybrid Search ─────────────────────────────────────────────────────────
    hybrid_search_alpha: float = 0.6    # Weight for vector search (1-alpha for BM25)
    bm25_enabled: bool = True

    # ── LLM (Qwen3 8B via Ollama) ─────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_vlm_model: str = "qwen3-vl:8b"
    llm_max_new_tokens: int = 1024
    llm_temperature: float = 0.1

    # ── LLM Fallback (HuggingFace Transformers) ──────────────────────────────
    llm_fallback_enabled: bool = False  # Disabled: avoids loading a 8B HF model on startup when Ollama is the primary LLM
    llm_hf_model_name: str = "Qwen/Qwen3-8B"

    # ── Offline Mode ─────────────────────────────────────────────────────────
    offline_mode: bool = True

    # ── CORS ──────────────────────────────────────────────────────────────────
    allowed_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:8000"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    def ensure_dirs(self):
        """Create all required data directories on startup."""
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        if self.qdrant_use_embedded:
            self.qdrant_embedded_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    import json
    
    s = Settings()
    
    # ── Load config.json overrides (DPR Section 11) ──────────────────────────
    # Look for config.json relative to the backend package root or the executable root
    _bundle_root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parents[2]
    config_paths = [
        _bundle_root / "config" / "config.json",
        Path("backend/config/config.json").resolve(),
    ]
    
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    overrides = json.load(f)
                    
                # Map JSON keys to Pydantic attributes
                key_mapping = {
                    "app_name": "app_name",
                    "debug": "debug",
                    "offline_mode": "offline_mode",
                    "qdrant_collection_name": "qdrant_collection",
                    "bge_model_name": "embedding_model_name",
                    "reranker_model_name": "reranker_model_name",
                    "ollama_host": "ollama_base_url",
                    "ollama_model": "ollama_model",
                    "top_k_retrieve": "retrieval_top_k",
                    "top_k_rerank": "reranker_top_k",
                }
                
                for json_key, attr_name in key_mapping.items():
                    if json_key in overrides and hasattr(s, attr_name):
                        setattr(s, attr_name, overrides[json_key])
                        
                break # Loaded successfully, no need to check other paths
            except Exception as e:
                # Can't use loguru yet because logger might not be initialized
                print(f"Failed to load {config_path}: {e}")

    s.ensure_dirs()
    return s
