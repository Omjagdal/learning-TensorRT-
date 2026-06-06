"""
ingestion/metadata_extractor.py — Hierarchical metadata extraction from PDFs.

Detects and builds a structured hierarchy:
  Manual → Chapter → Section → Page

Uses multiple signals:
  1. PDF Table of Contents (TOC / bookmarks)
  2. Font-size–based heading detection
  3. Regex pattern matching for numbered headings
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

import fitz  # PyMuPDF
from loguru import logger


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class SectionInfo:
    """Represents a section within a chapter."""
    title: str
    level: int                      # Hierarchy depth (1=chapter, 2=section, 3=subsection)
    start_page: int                 # 1-indexed
    end_page: Optional[int] = None  # 1-indexed, filled after parsing

    def __repr__(self):
        return f"Section(L{self.level}: '{self.title}', pp.{self.start_page}-{self.end_page})"


@dataclass
class ChapterInfo:
    """Represents a chapter containing sections."""
    title: str
    start_page: int
    end_page: Optional[int] = None
    sections: list[SectionInfo] = field(default_factory=list)

    def __repr__(self):
        return (
            f"Chapter('{self.title}', pp.{self.start_page}-{self.end_page}, "
            f"{len(self.sections)} sections)"
        )


@dataclass
class ManualHierarchy:
    """Complete hierarchical structure of a manual."""
    manual_name: str
    total_pages: int
    chapters: list[ChapterInfo] = field(default_factory=list)

    def get_location(self, page_number: int) -> dict:
        """
        Get the chapter and section for a given page number.

        Returns:
            Dict with 'chapter' and 'section' strings.
        """
        chapter_name = "Unknown Chapter"
        section_name = "General"

        for chapter in self.chapters:
            c_start = chapter.start_page
            c_end = chapter.end_page or self.total_pages
            if c_start <= page_number <= c_end:
                chapter_name = chapter.title
                for section in chapter.sections:
                    s_start = section.start_page
                    s_end = section.end_page or c_end
                    if s_start <= page_number <= s_end:
                        section_name = section.title
                        break
                break

        return {
            "chapter": chapter_name,
            "section": section_name,
        }

    def to_dict(self) -> dict:
        """Serialize hierarchy to a JSON-serializable dict."""
        return {
            "manual_name": self.manual_name,
            "total_pages": self.total_pages,
            "chapters": [
                {
                    "title": ch.title,
                    "start_page": ch.start_page,
                    "end_page": ch.end_page,
                    "sections": [
                        {
                            "title": sec.title,
                            "level": sec.level,
                            "start_page": sec.start_page,
                            "end_page": sec.end_page,
                        }
                        for sec in ch.sections
                    ],
                }
                for ch in self.chapters
            ],
        }


# ── Heading detection patterns ───────────────────────────────────────────────

# Chapter-level patterns (Level 1)
CHAPTER_PATTERNS = [
    re.compile(r"^Chapter\s+\d+", re.IGNORECASE),
    re.compile(r"^CHAPTER\s+\d+"),
    re.compile(r"^\d+\.\s+[A-Z][A-Za-z\s]{3,}$"),     # "1. Introduction"
    re.compile(r"^SECTION\s+\d+", re.IGNORECASE),
    re.compile(r"^Part\s+[IVXLC]+", re.IGNORECASE),    # "Part III"
]

# Section-level patterns (Level 2)
SECTION_PATTERNS = [
    re.compile(r"^\d+\.\d+\s+[A-Z]"),                  # "3.2 Safety"
    re.compile(r"^\d+\.\d+\.\s+"),                      # "3.2. Safety"
]

# Subsection-level patterns (Level 3)
SUBSECTION_PATTERNS = [
    re.compile(r"^\d+\.\d+\.\d+\s+"),                  # "3.2.1 Procedure"
]


def _classify_heading(text: str) -> Optional[int]:
    """
    Classify a text line as a heading and return its level.

    Returns:
        1 for chapter, 2 for section, 3 for subsection, None if not a heading.
    """
    text = text.strip()
    if not text or len(text) > 200:
        return None

    for pattern in CHAPTER_PATTERNS:
        if pattern.match(text):
            return 1

    for pattern in SECTION_PATTERNS:
        if pattern.match(text):
            return 2

    for pattern in SUBSECTION_PATTERNS:
        if pattern.match(text):
            return 3

    # All-caps lines longer than 4 chars → likely chapter heading
    if text.isupper() and len(text) > 4 and len(text) < 100:
        return 1

    return None


# ── Main extraction ──────────────────────────────────────────────────────────

class MetadataExtractor:
    """
    Extracts hierarchical structure from a PDF document.

    Strategy (in priority order):
      1. Use PDF TOC (bookmarks) if available — most reliable
      2. Fall back to font-size–based heading detection
      3. Fall back to regex pattern matching on text
    """

    def __init__(self, doc: fitz.Document, manual_name: str):
        self.doc = doc
        self.manual_name = manual_name
        self.total_pages = len(doc)

    def extract_hierarchy(self) -> ManualHierarchy:
        """
        Build the full manual hierarchy using the best available method.
        """
        hierarchy = ManualHierarchy(
            manual_name=self.manual_name,
            total_pages=self.total_pages,
        )

        # Strategy 1: Use PDF TOC if available
        toc = self.doc.get_toc()
        if toc and len(toc) >= 3:
            logger.info(f"Using PDF TOC ({len(toc)} entries) for hierarchy")
            hierarchy.chapters = self._hierarchy_from_toc(toc)
        else:
            # Strategy 2: Font-based + regex heading detection
            logger.info("No PDF TOC — detecting headings from text/fonts")
            hierarchy.chapters = self._hierarchy_from_text()

        # Fill in end pages
        self._fill_end_pages(hierarchy)

        # Add a default chapter if none found
        if not hierarchy.chapters:
            hierarchy.chapters = [
                ChapterInfo(
                    title="Document Content",
                    start_page=1,
                    end_page=self.total_pages,
                )
            ]
            logger.info("No chapters detected — using single default chapter")

        logger.info(
            f"Hierarchy: {len(hierarchy.chapters)} chapters, "
            f"{sum(len(c.sections) for c in hierarchy.chapters)} sections"
        )
        return hierarchy

    def _hierarchy_from_toc(self, toc: list) -> list[ChapterInfo]:
        """Build hierarchy from PDF Table of Contents."""
        chapters: list[ChapterInfo] = []
        current_chapter: Optional[ChapterInfo] = None

        for level, title, page in toc:
            title = title.strip()
            if not title:
                continue

            if level == 1:
                # New chapter
                current_chapter = ChapterInfo(
                    title=title,
                    start_page=max(1, page),
                )
                chapters.append(current_chapter)
            elif level >= 2 and current_chapter is not None:
                # Section or subsection
                current_chapter.sections.append(
                    SectionInfo(
                        title=title,
                        level=level,
                        start_page=max(1, page),
                    )
                )
            elif level >= 2 and current_chapter is None:
                # Section before any chapter — create a default chapter
                current_chapter = ChapterInfo(
                    title="Introduction",
                    start_page=1,
                )
                chapters.append(current_chapter)
                current_chapter.sections.append(
                    SectionInfo(
                        title=title,
                        level=level,
                        start_page=max(1, page),
                    )
                )

        return chapters

    def _hierarchy_from_text(self) -> list[ChapterInfo]:
        """Build hierarchy by scanning page text for heading patterns."""
        chapters: list[ChapterInfo] = []
        current_chapter: Optional[ChapterInfo] = None

        for page_idx in range(self.total_pages):
            page = self.doc[page_idx]
            page_num = page_idx + 1

            # Get text blocks with font information
            try:
                blocks = page.get_text("dict", sort=True).get("blocks", [])
            except Exception:
                continue

            for block in blocks:
                if block.get("type") != 0:  # text blocks only
                    continue

                for line in block.get("lines", []):
                    line_text = ""
                    max_font_size = 0.0
                    is_bold = False

                    for span in line.get("spans", []):
                        line_text += span.get("text", "")
                        font_size = span.get("size", 0)
                        if font_size > max_font_size:
                            max_font_size = font_size
                        flags = span.get("flags", 0)
                        if flags & 2 ** 4:  # bold flag
                            is_bold = True

                    line_text = line_text.strip()
                    if not line_text or len(line_text) < 3:
                        continue

                    # Check if this is a heading
                    heading_level = _classify_heading(line_text)

                    # Large font or bold text → likely heading
                    if heading_level is None and max_font_size >= 14 and is_bold:
                        heading_level = 1
                    elif heading_level is None and max_font_size >= 12 and is_bold:
                        heading_level = 2

                    if heading_level == 1:
                        current_chapter = ChapterInfo(
                            title=line_text,
                            start_page=page_num,
                        )
                        chapters.append(current_chapter)
                    elif heading_level in (2, 3) and current_chapter is not None:
                        current_chapter.sections.append(
                            SectionInfo(
                                title=line_text,
                                level=heading_level,
                                start_page=page_num,
                            )
                        )

        return chapters

    def _fill_end_pages(self, hierarchy: ManualHierarchy):
        """Fill end_page for all chapters and sections."""
        chapters = hierarchy.chapters

        for i, chapter in enumerate(chapters):
            # Chapter end = start of next chapter - 1 (or last page)
            if i + 1 < len(chapters):
                chapter.end_page = chapters[i + 1].start_page - 1
            else:
                chapter.end_page = self.total_pages

            # Fill section end pages
            sections = chapter.sections
            for j, section in enumerate(sections):
                if j + 1 < len(sections):
                    section.end_page = sections[j + 1].start_page - 1
                else:
                    section.end_page = chapter.end_page


def extract_manual_hierarchy(
    pdf_path: str | fitz.Document,
    manual_name: str,
) -> ManualHierarchy:
    """
    Convenience function: extract the full hierarchy from a PDF.

    Args:
        pdf_path: Path string or an already-opened fitz.Document.
        manual_name: Display name for the manual.

    Returns:
        ManualHierarchy with chapters and sections.
    """
    if isinstance(pdf_path, fitz.Document):
        extractor = MetadataExtractor(pdf_path, manual_name)
        return extractor.extract_hierarchy()

    with fitz.open(str(pdf_path)) as doc:
        extractor = MetadataExtractor(doc, manual_name)
        return extractor.extract_hierarchy()
