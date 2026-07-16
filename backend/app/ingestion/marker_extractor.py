"""
ingestion/marker_extractor.py — PDF extraction using VikParuchuri/marker.

Runs `marker_single` CLI to convert complex industrial PDFs to clean Markdown
and extract images/diagrams to disk.

Uses the full path to the current venv's marker_single to avoid PATH conflicts.
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from loguru import logger


def _get_marker_binary() -> str:
    """Get the full path to marker_single in the current venv."""
    venv_bin = Path(sys.executable).parent
    marker_path = venv_bin / "marker_single"
    if marker_path.exists():
        return str(marker_path)
    # Fallback: try PATH
    return "marker_single"


def _get_env() -> dict:
    """Build environment with libmagic paths for macOS Homebrew and strict offline mode."""
    env = os.environ.copy()
    
    # Enforce strict offline mode for Marker to prevent runtime downloads
    env["PADDLE_OCR_DOWNLOAD"] = "false"
    env["MARKER_TELEMETRY"] = "false"
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["HF_DATASETS_OFFLINE"] = "1"
    
    # Ensure Homebrew's lib is on the library search path
    homebrew_lib = "/opt/homebrew/lib"
    if os.path.isdir(homebrew_lib):
        existing = env.get("DYLD_FALLBACK_LIBRARY_PATH", "")
        env["DYLD_FALLBACK_LIBRARY_PATH"] = f"{homebrew_lib}:{existing}" if existing else homebrew_lib
    return env


def extract_with_marker(pdf_path: Path, output_dir: Path) -> tuple[str, list[Path]]:
    """
    Run marker_single CLI to convert PDF to Markdown and extract images.

    Args:
        pdf_path: Path to the input PDF file.
        output_dir: Temporary directory to store Marker outputs.

    Returns:
        Tuple of (markdown_text, list_of_image_paths_extracted)
    """
    pdf_name = pdf_path.stem
    marker_out_dir = output_dir / f"marker_tmp_{pdf_name}"

    marker_bin = _get_marker_binary()

    cmd = [
        marker_bin,
        str(pdf_path),
        str(marker_out_dir),
    ]

    logger.info(f"Running Marker extraction on {pdf_path.name}... This may take a while.")
    logger.debug(f"Marker binary: {marker_bin}")

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            env=_get_env(),
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Marker extraction failed: {e.stderr}")
        raise RuntimeError(f"Marker failed: {e.stderr}")
    except FileNotFoundError:
        logger.error(
            "marker_single not found. Install it with: pip install marker-pdf"
        )
        raise RuntimeError("marker_single binary not found in venv")

    # Marker creates a subdirectory named after the PDF stem inside the output dir
    result_dir = marker_out_dir / pdf_name

    md_file = None
    
    # Check if marker_out_dir is itself the output file (some versions write directly to the target path)
    if marker_out_dir.is_file():
        md_file = marker_out_dir
        result_dir = None  # Marker wrote a single file, no images were extracted
    elif result_dir.exists():
        md_files = list(result_dir.glob("*.md"))
        if md_files:
            md_file = md_files[0]
    else:
        # Some versions of marker put output directly in marker_out_dir
        # Try to find the .md file anywhere in the output tree
        if marker_out_dir.exists() and marker_out_dir.is_dir():
            md_files = list(marker_out_dir.rglob("*.md"))
            if md_files:
                md_file = md_files[0]
                result_dir = md_file.parent

    if not md_file:
        logger.error(f"Marker output not found. Checked {marker_out_dir} and {result_dir}")
        raise FileNotFoundError(
            f"Marker failed to produce expected output"
        )

    md_text = md_file.read_text(encoding="utf-8")

    # Gather extracted images
    images = []
    if result_dir is not None:
        for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
            images.extend(list(result_dir.glob(ext)))

    if not images:
        logger.info("Marker did not extract images. Using PyMuPDF to render full pages as fallback.")
        if result_dir is None:
            result_dir = output_dir / f"{pdf_name}_fallback_images"
            result_dir.mkdir(parents=True, exist_ok=True)
            
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                pix = page.get_pixmap(dpi=150)
                img_name = f"page_{page_idx}.png"
                img_path = result_dir / img_name
                pix.save(str(img_path))
                images.append(img_path)
                md_text += f"\n\n![Page {page_idx}]({img_name})\n"
        except Exception as e:
            logger.error(f"PyMuPDF fallback failed: {e}")

    logger.info(f"Marker extraction complete. Found {len(images)} images.")
    return md_text, images
