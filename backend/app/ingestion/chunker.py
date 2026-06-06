"""
ingestion/chunker.py — Hierarchy-preserving text chunking.

Produces chunks that carry full hierarchical context:
  manual_name → chapter → section → page → chunk

Features:
  - 800–1000 token chunks with 100–150 token overlap
  - Respects chapter/section boundaries when possible
  - Attaches complete metadata to every chunk
  - Classifies chunk content type (text, table, list, heading)
"""

from __future__ import annotations
import re
from typing import Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter
from loguru import logger

from app.core.config import get_settings
from app.ingestion.metadata_extractor import ManualHierarchy

settings = get_settings()


# ── Content type classification ──────────────────────────────────────────────

_SECTION_PATTERNS = [
    r"^\d+\.\d*\s+[A-Z]",           # "3.1 Safety Precautions"
    r"^Chapter\s+\d+",              # "Chapter 5"
    r"^SECTION\s+\d+",              # "SECTION 3"
    r"^[A-Z][A-Z\s]{4,}$",          # "MAINTENANCE PROCEDURES"
    r"^\d+\)\s+[A-Z]",              # "1) Introduction"
]


def _detect_content_type(text: str) -> str:
    """Classify a chunk's primary content type."""
    if "[TABLE]" in text:
        return "table"
    if re.search(r"(?m)^[\s]*[-•●◦]\s", text):
        return "list"
    if re.search(r"(?i)(?:error|fault|alarm)\s*(?:code|#|number)", text):
        return "error_code"
    if re.search(r"(?i)(?:warning|caution|danger)\s*:", text):
        return "safety"
    for pat in _SECTION_PATTERNS:
        if re.search(pat, text, re.MULTILINE):
            return "heading"
    return "text"


# ── Main chunker ─────────────────────────────────────────────────────────────

class HierarchicalChunker:
    """
    Splits page text into overlapping chunks while preserving
    hierarchical metadata (manual → chapter → section → page).
    """

    def __init__(
        self,
        chunk_size: int = settings.chunk_size,
        chunk_overlap: int = settings.chunk_overlap,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Use section-aware separators
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n\n",       # Section breaks
                "\n\n",         # Paragraph breaks
                "\n",           # Line breaks
                ". ",           # Sentence breaks
                "; ",           # Clause breaks
                ", ",           # Comma breaks
                " ",            # Word breaks
                "",             # Character breaks (last resort)
            ],
        )

    def chunk_pages(
        self,
        pages: list[dict],
        manual_id: str,
        filename: str,
        hierarchy: Optional[ManualHierarchy] = None,
    ) -> list[dict]:
        """
        Split page text into chunks with full hierarchical metadata.

        Args:
            pages: List of page dicts from PDFExtractor (must have 'page' and 'text').
            manual_id: Unique identifier for the manual.
            filename: Original filename of the manual.
            hierarchy: Optional ManualHierarchy for chapter/section resolution.

        Returns:
            List of chunk dicts with all metadata fields.
        """
        manual_name = filename.rsplit(".", 1)[0] if "." in filename else filename

        chunks: list[dict] = []
        chunk_idx = 0

        for page_data in pages:
            page_number = page_data["page"]
            text = page_data["text"]

            if not text or not text.strip():
                continue

            # Resolve hierarchy for this page
            if hierarchy:
                location = hierarchy.get_location(page_number)
                chapter = location["chapter"]
                section = location["section"]
            else:
                chapter = "Unknown Chapter"
                section = "General"

            hierarchy_path = f"{manual_name} > {chapter} > {section}"

            # Split text into chunks
            page_chunks = self.splitter.split_text(text)

            for chunk_text in page_chunks:
                chunk_text = chunk_text.strip()
                if not chunk_text:
                    continue

                content_type = _detect_content_type(chunk_text)

                chunks.append({
                    "chunk_id": f"{manual_id}_{chunk_idx}",
                    "manual_id": manual_id,
                    "manual_name": manual_name,
                    "filename": filename,
                    "chapter": chapter,
                    "section": section,
                    "page": page_number,
                    "chunk_index": chunk_idx,
                    "text": chunk_text,
                    "content_type": content_type,
                    "has_tables": page_data.get("has_tables", False),
                    "hierarchy_path": hierarchy_path,
                })
                chunk_idx += 1

        # Log summary
        logger.info(f"Generated {len(chunks)} chunks for '{filename}'")
        type_counts: dict[str, int] = {}
        for c in chunks:
            ct = c["content_type"]
            type_counts[ct] = type_counts.get(ct, 0) + 1
        logger.info(f"  ↳ Chunk types: {type_counts}")

        return chunks


def chunk_pages(
    pages: list[dict],
    manual_id: str,
    filename: str,
    hierarchy: Optional[ManualHierarchy] = None,
    chunk_size: int = settings.chunk_size,
    chunk_overlap: int = settings.chunk_overlap,
) -> list[dict]:
    """
    Convenience function: chunk pages with hierarchical metadata.

    Args:
        pages: Page dicts from extract_text_from_pdf().
        manual_id: Unique manual identifier.
        filename: Original PDF filename.
        hierarchy: Optional ManualHierarchy for chapter/section info.
        chunk_size: Target chunk size in characters.
        chunk_overlap: Overlap between consecutive chunks.

    Returns:
        List of chunk dicts ready for embedding and indexing.
    """
    chunker = HierarchicalChunker(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return chunker.chunk_pages(pages, manual_id, filename, hierarchy)
