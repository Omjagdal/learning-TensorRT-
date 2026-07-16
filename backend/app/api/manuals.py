"""
api/manuals.py — Endpoints for PDF upload, listing, and deletion.
"""

from __future__ import annotations

import tempfile
import json
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas import ManualListResponse, ManualMetadata
from app.services.pdf_service import ingest_pdf, list_manuals, delete_manual, ingest_pdf_generator

router = APIRouter(prefix="/manuals", tags=["Manuals"])


@router.post("/upload")
async def upload_manual(
    file: UploadFile = File(...),
    include_images: bool = Form(True)
):
    """Upload a PDF manual for ingestion, returning SSE progress."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")
        
    if file.content_type not in ["application/pdf", "application/x-pdf"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Expected application/pdf.")

    # Save uploaded file to a temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    def event_generator():
        try:
            for event in ingest_pdf_generator(tmp_path, file.filename, include_images=include_images):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'stage': 'Error', 'error': str(e)})}\n\n"
        finally:
            tmp_path.unlink(missing_ok=True)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/", response_model=ManualListResponse)
async def list_all_manuals():
    manuals = list_manuals()
    return ManualListResponse(
        manuals=[ManualMetadata(**m) for m in manuals],
        total=len(manuals),
    )


@router.delete("/{manual_id}")
async def delete_manual_endpoint(manual_id: str):
    """Delete a manual and all its associated data."""
    result = delete_manual(manual_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Manual {manual_id} not found.")
    return {"status": "deleted", "manual_id": manual_id}
