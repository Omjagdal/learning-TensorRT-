"""
api/stream.py — SSE streaming endpoint for Self-RAG pipeline.
"""

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from app.database.qdrant_store import get_qdrant_store
from app.rag.pipeline import stream_rag_pipeline
from app.schemas import ChatRequest

router = APIRouter(prefix="/chat", tags=["Chat"])


def _sse_format(event: str, data: dict) -> str:
    """Format a dict as an SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """SSE streaming endpoint for Self-RAG pipeline."""
    qdrant = get_qdrant_store()
    if qdrant.total_points == 0:
        raise HTTPException(
            status_code=400,
            detail="No manuals have been indexed yet. Please upload a PDF first.",
        )

    if request.manual_ids:
        available = qdrant.indexed_manual_ids
        invalid = set(request.manual_ids) - available
        if invalid:
            raise HTTPException(
                status_code=404,
                detail=f"Manual IDs not found in index: {invalid}",
            )

    def event_generator():
        try:
            for event in stream_rag_pipeline(
                question=request.question,
                manual_ids=request.manual_ids,
                top_k=request.top_k,
                image_b64=request.image_b64,
            ):
                yield _sse_format(event["event"], event.get("data", {}))
        except Exception as e:
            logger.exception(f"SSE streaming error: {e}")
            yield _sse_format("error", {"detail": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
