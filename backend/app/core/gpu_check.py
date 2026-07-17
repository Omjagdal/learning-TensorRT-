"""
core/gpu_check.py — GPU detection and status reporting (DPR Section 8).

Detects NVIDIA GPU availability, logs to backend.log, and returns a
structured status dict consumed by the /api/v1/health endpoint.
"""

from __future__ import annotations
import os
from typing import TypedDict

from loguru import logger
from .logging import log_backend


class GPUStatus(TypedDict):
    available: bool
    device_name: str | None
    vram_gb: float | None
    cuda_version: str | None
    compute_mode: str   # "cuda" | "cpu" | "mps"


def detect_gpu() -> GPUStatus:
    """
    User explicitly requested 'dont use gpu'.
    Always returns CPU mode.
    """
    status: GPUStatus = {
        "available": False,
        "device_name": None,
        "vram_gb": None,
        "cuda_version": None,
        "compute_mode": "cpu",
    }

    try:
        import platform
        cpu_info = platform.processor() or "Unknown CPU"
        log_backend(
            f"GPU | GPU usage disabled by user request — running on CPU ({cpu_info}).",
            level="INFO",
        )
    except Exception:
        log_backend("GPU | GPU usage disabled by user request — running on CPU.", level="INFO")

    return status


# Module-level singleton — detect once at import time, reuse everywhere
_gpu_status: GPUStatus | None = None


def get_gpu_status() -> GPUStatus:
    """Return cached GPU status (detected once at startup)."""
    global _gpu_status
    if _gpu_status is None:
        _gpu_status = detect_gpu()
    return _gpu_status
