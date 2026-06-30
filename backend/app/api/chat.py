"""
api/chat.py — Chat / query endpoint.
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.database.qdrant_store import get_qdrant_store
from app.rag.pipeline import run_rag_pipeline
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    qdrant = get_qdrant_store()
    if qdrant.total_points == 0:
        raise HTTPException(
            status_code=400,
            detail="No manuals have been indexed yet. Please upload a PDF first.",
        )

    # Validate requested manual_ids
    if request.manual_ids:
        available = qdrant.indexed_manual_ids
        invalid = set(request.manual_ids) - available
        if invalid:
            raise HTTPException(
                status_code=404,
                detail=f"Manual IDs not found in index: {invalid}",
            )

    try:
        response = run_rag_pipeline(
            question=request.question,
            manual_ids=request.manual_ids,
            top_k=request.top_k,
        )
        return response
    except Exception as e:
        logger.exception(f"RAG pipeline error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Query processing failed: {str(e)}"
        )
