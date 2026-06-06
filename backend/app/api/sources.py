"""
api/sources.py — Endpoints for retrieving document hierarchies and pages.
"""

from fastapi import APIRouter, HTTPException

from app.services.pdf_service import get_hierarchy_for_manual
from app.indexing.page_index import get_page_index
from app.schemas import HierarchyResponse, PageContentResponse

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.get("/{manual_id}/hierarchy", response_model=HierarchyResponse)
async def get_manual_hierarchy(manual_id: str):
    """Get the chapter/section hierarchy for a manual."""
    hierarchy = get_hierarchy_for_manual(manual_id)
    if not hierarchy:
        raise HTTPException(status_code=404, detail="Manual hierarchy not found")
        
    return HierarchyResponse(
        manual_id=manual_id,
        hierarchy=hierarchy,
    )


@router.get("/{manual_id}/pages/{page}", response_model=PageContentResponse)
async def get_page_content(manual_id: str, page: int):
    """Reconstruct the text content of a specific page from its chunks."""
    index = get_page_index()
    chunks = index.get_chunks_by_page(manual_id, page)
    
    if not chunks:
        raise HTTPException(status_code=404, detail=f"Page {page} not found in manual {manual_id}")
        
    # Reconstruct text (might have overlap duplicates, simplified here)
    # Sort by chunk_index to ensure order
    chunks.sort(key=lambda x: x["chunk_index"])
    
    # Just grab the first chunk's path (it's the same for the whole page usually)
    hierarchy_path = chunks[0].get("hierarchy_path", "")
    
    # Simple join (in a real app we'd strip overlaps, but this is for viewing)
    text = "\n\n".join(c["text"] for c in chunks)
    
    return PageContentResponse(
        manual_id=manual_id,
        page=page,
        text=text,
        hierarchy_path=hierarchy_path,
    )
