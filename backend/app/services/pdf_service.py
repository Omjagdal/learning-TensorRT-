"""
services/pdf_service.py — PDF ingestion integration with Marker.

Pipeline:
  1. Marker converts PDF → Markdown + extracted images
  2. PyMuPDF extracts per-page text for image indexing (page-text mapping)
  3. MarkdownHeaderTextSplitter chunks the Markdown
  4. BGE-M3 embeds text chunks → Qdrant (text collection)
  5. BGE-M3 embeds page-text captions → Qdrant (images collection)
  6. BM25 index is rebuilt for keyword search
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger

from app.core.config import get_settings
from app.database.qdrant_store import get_qdrant_store
from app.embeddings.bge_m3 import get_embedder as get_bge_embedder
from app.indexing.page_index import get_page_index
from app.ingestion.chunker import chunk_pages
from app.ingestion.marker_extractor import extract_with_marker
from app.retrieval.bm25 import rebuild_bm25_index

settings = get_settings()

METADATA_FILE = settings.upload_dir / "metadata.json"


def _load_metadata() -> dict:
    if METADATA_FILE.exists():
        return json.loads(METADATA_FILE.read_text())
    return {}


def _save_metadata(data: dict):
    METADATA_FILE.write_text(json.dumps(data, indent=2, default=str))


def _get_images_dir(manual_id: str) -> Path:
    """Get the directory for extracted images."""
    return settings.upload_dir / f"{manual_id}_images"


def _build_page_text_map(pdf_path: Path) -> dict:
    """
    Extract text from each PDF page using PyMuPDF (instant, no LLM).
    Returns {page_number: text_content}.
    This is the core of Option 1 — Page-Text Mapping.
    """
    try:
        import fitz  # PyMuPDF
        page_texts = {}
        doc = fitz.open(str(pdf_path))
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()
            page_texts[page_num] = text if text else f"Page {page_num} — technical diagram"
        doc.close()
        logger.info(f"Page-text map built: {len(page_texts)} pages extracted via PyMuPDF")
        return page_texts
    except Exception as e:
        logger.warning(f"PyMuPDF page-text extraction failed: {e}")
        return {}


def ingest_pdf_generator(file_path: Path, original_filename: str, include_images: bool = True):
    """
    Generator version of ingest_pdf that yields progress events.
    """
    manual_id = str(uuid.uuid4())[:8]
    manual_name = (
        original_filename.rsplit(".", 1)[0]
        if "." in original_filename
        else original_filename
    )

    dest_path = settings.upload_dir / f"{manual_id}_{original_filename}"
    if file_path.resolve() != dest_path.resolve():
        shutil.copy2(file_path, dest_path)

    logger.info(f"Starting Marker ingestion for {original_filename} (ID: {manual_id})")

    yield {"stage": "Building page-text map", "progress": 10}
    page_text_map = _build_page_text_map(dest_path)

    yield {"stage": "Extracting Markdown & Images (Marker)", "progress": 30}
    md_text, extracted_images = extract_with_marker(dest_path, settings.upload_dir)
    image_filenames = [img.name for img in extracted_images]

    images_dir = _get_images_dir(manual_id)
    images_dir.mkdir(parents=True, exist_ok=True)

    image_paths = []
    for img in extracted_images:
        dest_img = images_dir / img.name
        if img.exists():
            shutil.move(str(img), str(dest_img))
            image_paths.append(dest_img)

    marker_out_dir = settings.upload_dir / f"marker_tmp_{dest_path.stem}"
    shutil.rmtree(marker_out_dir, ignore_errors=True)

    yield {"stage": "Chunking text", "progress": 60}
    chunks = chunk_pages(
        md_text,
        manual_id,
        original_filename,
        manual_name,
        image_filenames=image_filenames,
    )

    chunks_file = settings.upload_dir / f"{manual_id}_chunks.json"
    chunks_file.write_text(json.dumps(chunks, indent=2))

    yield {"stage": "Embedding text chunks", "progress": 70}
    logger.info(f"Embedding {len(chunks)} text chunks with BGE-M3...")
    bge_embedder = get_bge_embedder()
    texts = [c["text"] for c in chunks]
    if texts:
        text_embeddings = bge_embedder.embed_documents(texts)
        qdrant = get_qdrant_store()
        qdrant.upsert_chunks(chunks, text_embeddings)
        logger.info(f"Upserted {len(chunks)} text chunk vectors to Qdrant.")

    if include_images:
        yield {"stage": "Embedding images", "progress": 85}
        embed_marker_images(image_paths, manual_id, manual_name, original_filename, page_text_map=page_text_map)

    yield {"stage": "Rebuilding index", "progress": 95}
    logger.info("Rebuilding BM25 index...")
    rebuild_bm25_index()

    meta = {
        "manual_id": manual_id,
        "filename": original_filename,
        "manual_name": manual_name,
        "page_count": 0,
        "chunk_count": len(chunks),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "size_bytes": dest_path.stat().st_size,
    }

    all_meta = _load_metadata()
    all_meta[manual_id] = meta
    _save_metadata(all_meta)

    page_index = get_page_index()
    page_index.add_manual(manual_id, chunks)
    page_index.save(manual_id)

    logger.info(
        f"✅ Ingestion complete for '{original_filename}': "
        f"{len(chunks)} chunks, {len(image_paths)} images."
    )
    yield {"stage": "Done", "progress": 100, "meta": meta}

def ingest_pdf(file_path: Path, original_filename: str, include_images: bool = True) -> dict:
    """Wrapper around ingest_pdf_generator for synchronous use."""
    meta = None
    for event in ingest_pdf_generator(file_path, original_filename, include_images=include_images):
        if event["stage"] == "Done":
            meta = event["meta"]
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
        if f.is_dir():
            shutil.rmtree(f, ignore_errors=True)
        else:
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


def embed_marker_images(
    image_paths: list[Path],
    manual_id: str,
    manual_name: str,
    original_filename: str,
    page_text_map: dict = None,
) -> int:
    """
    Index extracted images using page-text mapping (Option 1).
    
    Instead of VLM captioning, each image is indexed with the actual text
    content of its corresponding PDF page (extracted via PyMuPDF).
    This is instant, accurate, and requires no LLM.
    """
    if not image_paths:
        return 0

    page_text_map = page_text_map or {}
    images_metadata = []
    captions = []

    try:
        for img_path in image_paths:
            # Parse page number from filename: page_0.png → 0
            page_num = 0
            name = img_path.stem
            if name.startswith("page_"):
                try:
                    page_num = int(name.split("_")[1])
                except (ValueError, IndexError):
                    pass

            # Use real page text as caption (core of page-text mapping)
            page_text = page_text_map.get(page_num, "")
            if page_text and page_text != f"Page {page_num} — technical diagram":
                caption = f"Page {page_num}: {page_text[:600]}"
            else:
                caption = f"Page {page_num} — technical diagram from {manual_name}"

            images_metadata.append({
                "manual_id": manual_id,
                "manual_name": manual_name,
                "filename": original_filename,
                "page": page_num,
                "image_path": str(img_path.relative_to(settings.upload_dir)),
                "hierarchy_path": f"Page {page_num}",
            })
            captions.append(caption)

        logger.info(
            f"Indexing {len(images_metadata)} images using page-text mapping "
            f"(PyMuPDF, no LLM needed)"
        )

        # Embed page-text captions with BGE-M3
        bge_embedder = get_bge_embedder()
        embeddings = bge_embedder.embed_documents(captions)

        # Upsert to Qdrant images collection
        qdrant = get_qdrant_store()
        qdrant.upsert_images(images_metadata, embeddings)

        logger.info(
            f"Successfully indexed {len(images_metadata)} images with page-text captions."
        )

    except Exception as e:
        logger.error(f"Failed to embed images for {manual_id}: {e}")

    return len(image_paths)



def get_image_path(image_rel_path: str) -> Optional[Path]:
    """
    Get the absolute path to an extracted image.
    """
    import os

    safe_path = os.path.normpath(f"/{image_rel_path}").lstrip("/")
    image_path = settings.upload_dir / safe_path
    if image_path.exists():
        return image_path
    return None
