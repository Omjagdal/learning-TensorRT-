"""
ingestion/pdf_extractor.py — PyMuPDF-based PDF text extraction.

Extracts text page-by-page with:
  - Layout-aware text extraction
  - Table detection and markdown formatting
  - Multi-column layout handling
  - Image/figure metadata extraction
  - Robust fallback for corrupted pages
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from loguru import logger

from app.utils.text_utils import clean_text, table_to_markdown


class PDFExtractor:
    """
    Extracts structured text content from PDF files using PyMuPDF.

    Each page yields a dict with:
      - page: int (1-indexed page number)
      - text: str (cleaned text content)
      - has_tables: bool
      - tables: list[str] (markdown-formatted tables)
      - images: list[dict] (image metadata)
      - raw_dict: dict (PyMuPDF page dict for further processing)
    """

    def __init__(self, pdf_path: Path | str):
        self.pdf_path = Path(pdf_path)
        self._doc: Optional[fitz.Document] = None

    def __enter__(self):
        self._doc = fitz.open(str(self.pdf_path))
        return self

    def __exit__(self, *args):
        if self._doc:
            self._doc.close()

    @property
    def doc(self) -> fitz.Document:
        if self._doc is None:
            raise RuntimeError("PDFExtractor must be used as a context manager")
        return self._doc

    @property
    def page_count(self) -> int:
        return len(self.doc)

    @property
    def metadata(self) -> dict:
        """Extract document-level metadata."""
        meta = self.doc.metadata or {}
        return {
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "subject": meta.get("subject", ""),
            "creator": meta.get("creator", ""),
            "producer": meta.get("producer", ""),
            "creation_date": meta.get("creationDate", ""),
            "page_count": self.page_count,
        }

    def get_toc(self) -> list[dict]:
        """
        Extract the Table of Contents (outline/bookmarks).

        Returns list of dicts:
          - level: int (hierarchy depth, 1 = top chapter)
          - title: str
          - page: int (1-indexed)
        """
        toc_raw = self.doc.get_toc()
        toc = []
        for level, title, page in toc_raw:
            toc.append({
                "level": level,
                "title": title.strip(),
                "page": page,
            })
        return toc

    def extract_page(self, page_num: int) -> dict:
        """
        Extract text and metadata from a single page.

        Args:
            page_num: 0-indexed page number.

        Returns:
            Dict with page content and metadata.
        """
        page = self.doc[page_num]
        page_number = page_num + 1  # 1-indexed for user display

        try:
            # ── Text extraction with layout preservation ──────────────────
            text = page.get_text("text", sort=True) or ""
            text = clean_text(text)

            # ── Table extraction ──────────────────────────────────────────
            tables_md = []
            has_tables = False
            try:
                tables = page.find_tables()
                if tables and tables.tables:
                    has_tables = True
                    for table in tables.tables:
                        table_data = table.extract()
                        if table_data:
                            md = table_to_markdown(table_data)
                            if md:
                                tables_md.append(md)
            except Exception as e:
                logger.debug(f"Table extraction failed on page {page_number}: {e}")

            # ── Image metadata ────────────────────────────────────────────
            images = []
            try:
                image_list = page.get_images(full=True)
                for img_info in image_list:
                    images.append({
                        "xref": img_info[0],
                        "width": img_info[2],
                        "height": img_info[3],
                    })
            except Exception:
                pass

            # ── Combine text with tables ──────────────────────────────────
            parts = []
            if text:
                parts.append(text)
            for md_table in tables_md:
                parts.append(f"\n[TABLE]\n{md_table}\n[/TABLE]")

            combined = "\n\n".join(parts)

            return {
                "page": page_number,
                "text": combined.strip(),
                "has_tables": has_tables,
                "tables": tables_md,
                "images": images,
                "char_count": len(combined),
            }

        except Exception as e:
            logger.warning(f"Failed to extract page {page_number}: {e}")
            return {
                "page": page_number,
                "text": "",
                "has_tables": False,
                "tables": [],
                "images": [],
                "char_count": 0,
            }

    def extract_all_pages(self) -> list[dict]:
        """
        Extract text from all pages in the PDF.

        Returns:
            List of page dicts, filtered to non-empty pages.
        """
        pages = []
        for i in range(self.page_count):
            page_data = self.extract_page(i)
            if page_data["text"]:
                pages.append(page_data)

        logger.info(
            f"Extracted {len(pages)} non-empty pages "
            f"from {self.pdf_path.name} ({self.page_count} total)"
        )

        table_pages = sum(1 for p in pages if p.get("has_tables"))
        if table_pages:
            logger.info(f"  ↳ {table_pages} pages contain tables")

        image_pages = sum(1 for p in pages if p.get("images"))
        if image_pages:
            logger.info(f"  ↳ {image_pages} pages contain images")

        return pages


def extract_text_from_pdf(pdf_path: Path) -> list[dict]:
    """
    Convenience function: extract all pages from a PDF file.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        List of page dicts with text, tables, and metadata.
    """
    with PDFExtractor(pdf_path) as extractor:
        return extractor.extract_all_pages()


def get_pdf_metadata(pdf_path: Path) -> dict:
    """
    Extract document-level metadata from a PDF.

    Returns dict with title, author, page_count, TOC, etc.
    """
    with PDFExtractor(pdf_path) as extractor:
        meta = extractor.metadata
        meta["toc"] = extractor.get_toc()
        return meta
