"""
api/manuals.py — Endpoints for PDF upload, listing, and deletion.
"""

from __future__ import annotations
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks
from loguru import logger

from app.schemas import UploadResponse, ManualListResponse, ManualMetadata, DeleteResponse
from app.services.pdf_service import ingest_pdf, list_manuals, delete_manual, get_chunks_for_manual
from app.database.qdrant_store import get_qdrant_store
from app.embeddings.bge_m3 import get_embedder
from app.retrieval.bm25 import rebuild_bm25_index

router = APIRouter(prefix="/manuals", tags=["Manuals"])


@router.post("/upload", response_model=UploadResponse)
async def upload_manual(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    if file.size and file.size > 200 * 1024 * 1024:  # 200 MB limit
        raise HTTPException(status_code=413, detail="File too large (max 200 MB)")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        # Process PDF synchronously (could be async for very large files)
        meta = ingest_pdf(tmp_path, file.filename)
        tmp_path.unlink(missing_ok=True)

        # Index vectors and rebuild BM25 in background
        background_tasks.add_task(_index_manual, meta["manual_id"])

        return UploadResponse(
            message="Manual uploaded and queued for vector indexing",
            manual_id=meta["manual_id"],
            filename=meta["filename"],
            chunk_count=meta["chunk_count"],
        )
    except Exception as e:
        logger.exception(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


def _index_manual(manual_id: str):
    """Background task: compute embeddings, upsert to Qdrant, rebuild BM25."""
    try:
        chunks = get_chunks_for_manual(manual_id)
        if not chunks:
            return

        logger.info(f"Background indexing {len(chunks)} chunks for {manual_id}...")
        
        # 1. Embed dense vectors
        embedder = get_embedder()
        texts = [c["text"] for c in chunks]
        embeddings = embedder.embed_documents(texts)
        
        # 2. Upsert to Qdrant
        qdrant = get_qdrant_store()
        qdrant.upsert_chunks(chunks, embeddings)
        
        # 3. Rebuild BM25 index
        rebuild_bm25_index()
        
        logger.info(f"Successfully indexed manual {manual_id}")
    except Exception as e:
        logger.error(f"Indexing failed for {manual_id}: {e}")


@router.get("/", response_model=ManualListResponse)
async def list_all_manuals():
    manuals = list_manuals()
    return ManualListResponse(
        manuals=[ManualMetadata(**m) for m in manuals],
        total=len(manuals),
    )


@router.delete("/{manual_id}", response_model=DeleteResponse)
async def delete_manual_endpoint(manual_id: str):
    meta = delete_manual(manual_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Manual not found")
    return DeleteResponse(message="Manual deleted successfully", manual_id=manual_id)
