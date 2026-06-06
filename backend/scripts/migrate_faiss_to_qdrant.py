"""
scripts/migrate_faiss_to_qdrant.py — Migrate existing flat FAISS indexes to Qdrant.

Note: This script migrates text chunks and metadata, but they won't have
the new hierarchical metadata (Chapter/Section) since the old system didn't extract it.
For best results, re-ingest PDFs through the UI.
"""

import sys
import json
import uuid
from pathlib import Path

# Add backend to python path
sys.path.append(str(Path(__file__).parent.parent))

from loguru import logger
from app.core.config import get_settings
from app.database.qdrant_store import get_qdrant_store
from app.embeddings.bge_m3 import get_embedder

settings = get_settings()


def migrate():
    logger.info("Starting FAISS to Qdrant migration...")
    
    # Check old storage
    old_db_dir = Path("faiss_db")
    if not old_db_dir.exists():
        logger.error("No 'faiss_db' directory found. Nothing to migrate.")
        return

    # Load old metadata
    meta_file = old_db_dir / "document_metadata.json"
    if not meta_file.exists():
        logger.error("No document_metadata.json found.")
        return
        
    old_meta = json.loads(meta_file.read_text())
    logger.info(f"Found {len(old_meta)} manuals in old metadata.")
    
    # Check old chunks
    chunks_file = old_db_dir / "document_chunks.json"
    if not chunks_file.exists():
        logger.error("No document_chunks.json found.")
        return
        
    old_chunks = json.loads(chunks_file.read_text())
    logger.info(f"Found {len(old_chunks)} chunks in total.")
    
    # We will re-embed using BGE-M3 (the old embeddings were 384d MiniLM)
    embedder = get_embedder()
    qdrant = get_qdrant_store()
    
    for manual_id, manual_info in old_meta.items():
        logger.info(f"Migrating manual: {manual_info.get('filename')} ({manual_id})")
        
        # Filter chunks for this manual
        manual_chunks = [c for c in old_chunks if c.get("manual_id") == manual_id]
        
        if not manual_chunks:
            logger.warning(f"No chunks found for manual {manual_id}")
            continue
            
        # Format chunks to new schema
        new_chunks = []
        for i, c in enumerate(manual_chunks):
            new_chunks.append({
                "chunk_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{manual_id}_{i}")),
                "manual_id": manual_id,
                "manual_name": manual_info.get("filename", "").replace(".pdf", ""),
                "filename": manual_info.get("filename", ""),
                "chapter": "Migrated Data",  # Missing in old schema
                "section": "General",        # Missing in old schema
                "page": c.get("page", 0),
                "chunk_index": i,
                "text": c.get("text", ""),
                "content_type": "text",
                "hierarchy_path": "Migrated Data > General",
                "has_tables": c.get("has_tables", False),
            })
            
        # Embed and Upsert
        logger.info(f"  Embedding {len(new_chunks)} chunks...")
        texts = [c["text"] for c in new_chunks]
        embeddings = embedder.embed_documents(texts)
        
        logger.info(f"  Upserting to Qdrant...")
        qdrant.upsert_chunks(new_chunks, embeddings)
        
        # Save chunks to new storage location
        dest_file = settings.upload_dir / f"{manual_id}_chunks.json"
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        dest_file.write_text(json.dumps(new_chunks, indent=2))
        
    # Copy metadata to new location
    new_meta_file = settings.upload_dir / "metadata.json"
    if not new_meta_file.exists():
        new_meta_file.write_text(json.dumps(old_meta, indent=2))
        
    logger.info("Migration complete! Note: Re-ingesting PDFs is recommended to get hierarchical metadata.")


if __name__ == "__main__":
    migrate()
