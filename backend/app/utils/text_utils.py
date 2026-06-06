"""
utils/text_utils.py — Shared text cleaning and processing utilities.

Used across the ingestion pipeline, chunking, and search modules.
"""

from __future__ import annotations
import re
import unicodedata


def clean_text(text: str) -> str:
    """
    Normalize extracted PDF text for better downstream processing.

    Steps:
      1. Fix hyphenation at line breaks
      2. Collapse excessive whitespace
      3. Remove standalone page numbers and copyright lines
      4. Normalize unicode characters
    """
    if not text:
        return ""

    # Normalize unicode (e.g., ligatures → standard characters)
    text = unicodedata.normalize("NFKC", text)

    # Fix hyphenation at line breaks (e.g., "lubri-\ncation" → "lubrication")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # Collapse multiple blank lines into at most two
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Normalize whitespace within lines (but preserve newlines)
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(line)
    text = "\n".join(lines)

    # Remove common page headers/footers
    text = re.sub(r"(?m)^Page\s+\d+\s*(?:of\s+\d+)?\s*$", "", text)
    text = re.sub(r"(?m)^\d+\s*$", "", text)      # standalone page numbers
    text = re.sub(r"(?m)^©.*$", "", text)           # copyright lines
    text = re.sub(r"(?m)^Confidential.*$", "", text) # confidentiality notices

    return text.strip()


def table_to_markdown(table_data: list[list]) -> str:
    """
    Convert a table (list of rows, each a list of cells) to markdown format.

    Args:
        table_data: 2D list where table_data[0] is the header row.

    Returns:
        Markdown-formatted table string.
    """
    if not table_data or not table_data[0]:
        return ""

    # Clean None values and strip whitespace
    cleaned = []
    for row in table_data:
        cleaned.append([str(cell).strip() if cell else "" for cell in row])

    if not cleaned:
        return ""

    # Build markdown table
    header = cleaned[0]
    md_lines = ["| " + " | ".join(header) + " |"]
    md_lines.append("| " + " | ".join(["---"] * len(header)) + " |")

    for row in cleaned[1:]:
        # Pad row if shorter than header
        padded = row + [""] * (len(header) - len(row))
        md_lines.append("| " + " | ".join(padded[: len(header)]) + " |")

    return "\n".join(md_lines)


def normalize_whitespace(text: str) -> str:
    """Collapse all whitespace sequences to single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def count_tokens_approx(text: str) -> int:
    """
    Approximate token count using whitespace splitting.
    Roughly 1 token ≈ 0.75 words for English technical text.
    """
    words = text.split()
    return int(len(words) / 0.75)


def truncate_text(text: str, max_chars: int = 500) -> str:
    """Truncate text to max_chars with ellipsis."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"
