"""
core/logging.py — Structured logging with loguru.

Provides:
  - Console logging (colorized)
  - File rotation (app.log)
  - Query logging (queries.log)
  - Retrieval logging (retrieval.log)
  - Error logging (errors.log)
"""

import sys
from pathlib import Path

from loguru import logger


def setup_logging(debug: bool = False):
    """Configure loguru with structured, multi-file logging."""
    logger.remove()
    level = "DEBUG" if debug else "INFO"

    # ── Console output ────────────────────────────────────────────────────────
    logger.add(
        sys.stdout,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # ── Main application log ──────────────────────────────────────────────────
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    logger.add(
        str(logs_dir / "app.log"),
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} — {message}",
    )

    # ── Query log (tracks all user queries) ───────────────────────────────────
    logger.add(
        str(logs_dir / "queries.log"),
        rotation="50 MB",
        retention="30 days",
        level="INFO",
        filter=lambda record: "query_log" in record["extra"],
        format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
    )

    # ── Retrieval log (tracks search results) ─────────────────────────────────
    logger.add(
        str(logs_dir / "retrieval.log"),
        rotation="50 MB",
        retention="30 days",
        level="INFO",
        filter=lambda record: "retrieval_log" in record["extra"],
        format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
    )

    # ── Error log (errors only) ───────────────────────────────────────────────
    logger.add(
        str(logs_dir / "errors.log"),
        rotation="10 MB",
        retention="30 days",
        level="ERROR",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} — {message}\n{exception}",
    )

    return logger


# ── Specialized loggers ──────────────────────────────────────────────────────


def log_query(question: str, manual_ids: list[str] | None = None):
    """Log a user query for analytics."""
    logger.bind(query_log=True).info(f'QUERY | q="{question}" | manuals={manual_ids}')


def log_retrieval(
    question: str,
    num_results: int,
    search_type: str,
    duration_ms: float,
):
    """Log retrieval results for analytics."""
    logger.bind(retrieval_log=True).info(
        f'RETRIEVAL | q="{question}" | results={num_results} | '
        f"type={search_type} | duration={duration_ms:.1f}ms"
    )
