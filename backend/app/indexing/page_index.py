"""
indexing/page_index.py — Hierarchical PageIndex for structured manual access.

Provides an in-memory index that maps:
  Manual → Chapter → Section → Page → Chunk

Used for:
  - Building hierarchy from ingested chunks
  - Querying chunks by chapter/section/page
  - Providing hierarchy trees for UI display
  - Persisting hierarchy to JSON for fast reload
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

from loguru import logger

from app.core.config import get_settings

settings = get_settings()

# Persist hierarchy alongside manual metadata
HIERARCHY_DIR = settings.resolved_upload_dir


class HierarchicalPageIndex:
    """
    In-memory index organizing chunks into:
      manual_id → chapter → section → page → [chunk_ids]

    Supports:
      - Build from a flat list of chunk dicts
      - Query by any level of the hierarchy
      - Serialize/deserialize for persistence
      - Provide hierarchy tree for UI
    """

    def __init__(self):
        # manual_id → { chapter → { section → { page → [chunk_dict] } } }
        self._index: dict[str, dict] = {}

    def add_manual(self, manual_id: str, chunks: list[dict]):
        """
        Build hierarchical index from a flat list of chunks.

        Each chunk must have: manual_id, chapter, section, page, chunk_id, text
        """
        tree: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

        for chunk in chunks:
            chapter = chunk.get("chapter", "Unknown Chapter")
            section = chunk.get("section", "General")
            page = chunk.get("page", 0)
            tree[chapter][section][page].append(chunk)

        self._index[manual_id] = dict(tree)
        logger.info(
            f"PageIndex: added manual '{manual_id}' — "
            f"{len(tree)} chapters, {len(chunks)} chunks"
        )

    def remove_manual(self, manual_id: str):
        """Remove a manual from the index."""
        self._index.pop(manual_id, None)

    def get_hierarchy(self, manual_id: str) -> Optional[dict]:
        """
        Get the hierarchy tree for UI display.

        Returns:
            {
                "chapters": [
                    {
                        "title": "Chapter 3: Safety",
                        "sections": [
                            {
                                "title": "3.1 Emergency Stop",
                                "pages": [12, 13, 14],
                                "chunk_count": 8
                            }
                        ]
                    }
                ]
            }
        """
        if manual_id not in self._index:
            return None

        chapters = []
        for ch_title, sections in self._index[manual_id].items():
            ch_sections = []
            for sec_title, pages in sections.items():
                all_pages = sorted(pages.keys())
                chunk_count = sum(len(chunks) for chunks in pages.values())
                ch_sections.append(
                    {
                        "title": sec_title,
                        "pages": all_pages,
                        "chunk_count": chunk_count,
                    }
                )
            chapters.append(
                {
                    "title": ch_title,
                    "sections": ch_sections,
                }
            )

        return {"chapters": chapters}

    def get_chunks_by_chapter(self, manual_id: str, chapter: str) -> list[dict]:
        """Get all chunks in a specific chapter."""
        if manual_id not in self._index:
            return []
        chapter_data = self._index[manual_id].get(chapter, {})
        chunks = []
        for sections in chapter_data.values():
            for page_chunks in sections.values():
                chunks.extend(page_chunks)
        return chunks

    def get_chunks_by_section(
        self, manual_id: str, chapter: str, section: str
    ) -> list[dict]:
        """Get all chunks in a specific section."""
        if manual_id not in self._index:
            return []
        chapter_data = self._index[manual_id].get(chapter, {})
        section_data = chapter_data.get(section, {})
        chunks = []
        for page_chunks in section_data.values():
            chunks.extend(page_chunks)
        return chunks

    def get_chunks_by_page(self, manual_id: str, page: int) -> list[dict]:
        """Get all chunks from a specific page across all chapters/sections."""
        if manual_id not in self._index:
            return []
        chunks = []
        for chapter_data in self._index[manual_id].values():
            for section_data in chapter_data.values():
                if page in section_data:
                    chunks.extend(section_data[page])
        return chunks

    def save(self, manual_id: str):
        """Persist hierarchy index to JSON."""
        if manual_id not in self._index:
            return

        path = HIERARCHY_DIR / f"{manual_id}_hierarchy.json"
        data = self.get_hierarchy(manual_id)
        path.write_text(json.dumps(data, indent=2))
        logger.debug(f"Saved hierarchy for {manual_id}")

    def load(self, manual_id: str, chunks: list[dict]) -> bool:
        """Load hierarchy from chunks (rebuild from flat data)."""
        if chunks:
            self.add_manual(manual_id, chunks)
            return True
        return False

    @property
    def manual_ids(self) -> set[str]:
        return set(self._index.keys())


# ── Singleton ────────────────────────────────────────────────────────────────

_page_index: Optional[HierarchicalPageIndex] = None


def get_page_index() -> HierarchicalPageIndex:
    """Get the global HierarchicalPageIndex singleton."""
    global _page_index
    if _page_index is None:
        _page_index = HierarchicalPageIndex()
    return _page_index
