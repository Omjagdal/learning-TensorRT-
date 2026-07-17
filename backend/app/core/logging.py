"""
core/logging.py — Structured multi-file logging as per DPR Section 12.

Log files (all in logs/ directory):
  application.log  — General app events, startup, API requests
  backend.log      — Backend init: GPU, Ollama, Qdrant, model loading
  rag.log          — RAG pipeline: retrieval, reranking, prompt building
  error.log        — Errors and exceptions only (with full tracebacks)
  performance.log  — Latency and timing metrics
"""

import sys
from pathlib import Path
from loguru import logger


def setup_logging(debug: bool = False, logs_dir: Path | None = None):
    """
    Configure loguru with 5 structured log files as specified in the DPR.

    Args:
        debug:    If True, enables DEBUG level on console and application.log.
        logs_dir: Override the logs directory path (used by frozen sidecar to
                  route logs to AppData instead of the bundle dir).
    """
    logger.remove()
    level = "DEBUG" if debug else "INFO"

    # ── Console output (stdout — read by Tauri shell) ─────────────────────────
    logger.add(
        sys.stdout,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        colorize=False,  # No ANSI codes on stdout — Tauri reads this
    )

    # ── Resolve logs directory ────────────────────────────────────────────────
    if logs_dir is None:
        logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    _fmt_full = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} — {message}"
    _fmt_err  = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} — {message}\n{exception}"
    _fmt_perf = "{time:YYYY-MM-DD HH:mm:ss} | {message}"

    # ── application.log — General events (DPR §12) ───────────────────────────
    logger.add(
        str(logs_dir / "application.log"),
        rotation="10 MB",
        retention="7 days",
        level=level,
        compression="zip",
        format=_fmt_full,
        filter=lambda r: "backend_log" not in r["extra"]
                      and "rag_log" not in r["extra"]
                      and "perf_log" not in r["extra"],
    )

    # ── backend.log — GPU, Ollama, Qdrant, model loading (DPR §8) ────────────
    logger.add(
        str(logs_dir / "backend.log"),
        rotation="10 MB",
        retention="14 days",
        level="DEBUG",
        compression="zip",
        format=_fmt_full,
        filter=lambda r: "backend_log" in r["extra"],
    )

    # ── rag.log — Retrieval, reranking, pipeline events (DPR §9) ─────────────
    logger.add(
        str(logs_dir / "rag.log"),
        rotation="50 MB",
        retention="30 days",
        level="INFO",
        format=_fmt_full,
        filter=lambda r: "rag_log" in r["extra"],
    )

    # ── error.log — Errors and exceptions only (DPR §13) ─────────────────────
    logger.add(
        str(logs_dir / "error.log"),
        rotation="10 MB",
        retention="30 days",
        level="ERROR",
        compression="zip",
        format=_fmt_err,
    )

    # ── performance.log — Latency / timing metrics (DPR §4 NFR) ──────────────
    logger.add(
        str(logs_dir / "performance.log"),
        rotation="20 MB",
        retention="14 days",
        level="INFO",
        format=_fmt_perf,
        filter=lambda r: "perf_log" in r["extra"],
    )

    return logger


# ── Specialized loggers ───────────────────────────────────────────────────────

def log_backend(message: str, level: str = "INFO"):
    """Log a backend initialization event to backend.log."""
    getattr(logger.bind(backend_log=True), level.lower())(message)


def log_rag(message: str):
    """Log a RAG pipeline event to rag.log."""
    logger.bind(rag_log=True).info(message)


def log_performance(operation: str, duration_ms: float, **kwargs):
    """Log a timing metric to performance.log."""
    extra = " | ".join(f"{k}={v}" for k, v in kwargs.items())
    msg = f"PERF | {operation} | {duration_ms:.1f}ms"
    if extra:
        msg += f" | {extra}"
    logger.bind(perf_log=True).info(msg)


# ── Legacy helpers (kept for backward compatibility) ──────────────────────────

def log_query(question: str, manual_ids: list[str] | None = None):
    """Log a user query (routes to rag.log)."""
    logger.bind(rag_log=True).info(f'QUERY | q="{question}" | manuals={manual_ids}')


def log_retrieval(question: str, num_results: int, search_type: str, duration_ms: float):
    """Log retrieval results (routes to both rag.log and performance.log)."""
    logger.bind(rag_log=True).info(
        f'RETRIEVAL | q="{question}" | results={num_results} | type={search_type}'
    )
    log_performance("retrieval", duration_ms, results=num_results, type=search_type)
