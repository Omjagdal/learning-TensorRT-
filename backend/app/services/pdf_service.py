"""
services/pdf_service.py — PDF ingestion integration.

Delegates extraction and chunking to the new ingestion package,
then handles Qdrant and BM25 index updates.
"""

from __future__ import annotations
import uuid
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from app.core.config import get_settings
from app.ingestion.pdf_extractor import extract_text_from_pdf, get_pdf_metadata
from app.ingestion.metadata_extractor import extract_manual_hierarchy
from app.ingestion.chunker import chunk_pages
from app.indexing.page_index import get_page_index
from app.database.qdrant_store import get_qdrant_store
from app.retrieval.bm25 import rebuild_bm25_index

settings = get_settings()

METADATA_FILE = settings.upload_dir / "metadata.json"


def _load_metadata() -> dict:
    if METADATA_FILE.exists():
        return json.loads(METADATA_FILE.read_text())
    return {}


def _save_metadata(data: dict):
    METADATA_FILE.write_text(json.dumps(data, indent=2, default=str))


def ingest_pdf(file_path: Path, original_filename: str) -> dict:
    """
    Full ingestion pipeline:
      1. Extract text + tables via PyMuPDF
      2. Extract hierarchical structure (TOC/headings)
      3. Chunk pages preserving hierarchy
      4. Store in Qdrant + PageIndex
    """
    manual_id = str(uuid.uuid4())[:8]
    manual_name = original_filename.rsplit(".", 1)[0] if "." in original_filename else original_filename

    dest_path = settings.upload_dir / f"{manual_id}_{original_filename}"
    shutil.copy2(file_path, dest_path)

    logger.info(f"Starting ingestion for {original_filename} (ID: {manual_id})")

    # 1. Base extraction
    pdf_meta = get_pdf_metadata(dest_path)
    pages = extract_text_from_pdf(dest_path)

    # 2. Hierarchy extraction
    hierarchy = extract_manual_hierarchy(dest_path, manual_name)

    # 3. Chunking
    chunks = chunk_pages(pages, manual_id, original_filename, hierarchy=hierarchy)

    # Persist chunks as JSON for backup/inspection
    chunks_file = settings.upload_dir / f"{manual_id}_chunks.json"
    chunks_file.write_text(json.dumps(chunks, indent=2))

    meta = {
        "manual_id": manual_id,
        "filename": original_filename,
        "manual_name": manual_name,
        "page_count": pdf_meta.get("page_count", 0),
        "chunk_count": len(chunks),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "size_bytes": dest_path.stat().st_size,
    }

    all_meta = _load_metadata()
    all_meta[manual_id] = meta
    _save_metadata(all_meta)

    # 4. Update in-memory PageIndex
    page_index = get_page_index()
    page_index.add_manual(manual_id, chunks)
    page_index.save(manual_id)

    return meta


def list_manuals() -> list[dict]:
    return list(_load_metadata().values())


def delete_manual(manual_id: str) -> Optional[dict]:
    """Delete a manual and its associated data from all stores."""
    all_meta = _load_metadata()
    if manual_id not in all_meta:
        return None
    meta = all_meta.pop(manual_id)

    # Remove files
    for f in settings.upload_dir.glob(f"{manual_id}_*"):
        f.unlink(missing_ok=True)

    _save_metadata(all_meta)

    # Remove from stores
    try:
        qdrant = get_qdrant_store()
        qdrant.delete_manual(manual_id)

        page_index = get_page_index()
        page_index.remove_manual(manual_id)

        # Rebuild BM25 index after deletion
        rebuild_bm25_index()

        logger.info(f"Deleted all data for manual {manual_id}")
    except Exception as e:
        logger.warning(f"Cleanup warning for {manual_id}: {e}")

    return meta


def get_chunks_for_manual(manual_id: str) -> list[dict]:
    """Load raw chunk dicts from JSON."""
    chunks_file = settings.upload_dir / f"{manual_id}_chunks.json"
    if not chunks_file.exists():
        return []
    return json.loads(chunks_file.read_text())


def get_hierarchy_for_manual(manual_id: str) -> Optional[dict]:
    """Get the hierarchy tree for a manual."""
    page_index = get_page_index()
    return page_index.get_hierarchy(manual_id)
