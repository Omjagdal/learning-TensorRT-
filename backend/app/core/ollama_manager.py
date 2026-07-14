"""
core/ollama_manager.py — Manages the bundled Ollama subprocess for desktop builds.

When running as a frozen PyInstaller .exe, this module:
  1. Locates the bundled ollama binary (next to the .exe or in _MEIPASS)
  2. Sets OLLAMA_MODELS to point at the bundled model directory
  3. Starts `ollama serve` as a hidden background subprocess
  4. Waits until the Ollama HTTP API is responsive
  5. Verifies required models are loaded from the local model store
  6. Terminates Ollama cleanly when the app exits

In non-frozen (development) mode, it checks if Ollama is already running
externally and leaves it alone — no subprocess management needed.
"""

from __future__ import annotations

import atexit
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import requests
from loguru import logger


# ── Constants ─────────────────────────────────────────────────────────────────

OLLAMA_STARTUP_TIMEOUT = 60       # seconds to wait for ollama serve to be ready
OLLAMA_MODEL_PULL_TIMEOUT = 30    # seconds to wait for model verification
OLLAMA_BASE_URL = "http://127.0.0.1:11434"

# Models that must be available locally (will be verified, NOT downloaded)
REQUIRED_MODELS = ["qwen3:8b", "bge-m3"]


# ── State ─────────────────────────────────────────────────────────────────────

_ollama_process: Optional[subprocess.Popen] = None
_ollama_managed = False   # True only if WE started the process


# ── Path Resolution ───────────────────────────────────────────────────────────

def _get_app_root() -> Path:
    """Get the root directory of the application (works frozen and unfrozen)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller: the .exe is in the dist/<name>/ folder
        # sys.executable = path to IsraChatbot.exe
        return Path(sys.executable).parent
    else:
        # Development: project root is 2 levels above this file
        # (backend/app/core/ollama_manager.py → project root)
        return Path(__file__).parent.parent.parent.parent


def _get_ollama_binary() -> Optional[Path]:
    """Find the Ollama binary, bundled or system-installed."""
    app_root = _get_app_root()
    system = platform.system()

    # 1. Look for bundled binary next to the .exe
    if system == "Windows":
        candidates = [
            app_root / "ollama" / "ollama.exe",
            app_root / "ollama.exe",
        ]
    else:  # macOS / Linux
        candidates = [
            app_root / "ollama" / "ollama",
            app_root / "ollama",
        ]

    for candidate in candidates:
        if candidate.exists():
            logger.info(f"Found bundled Ollama binary: {candidate}")
            return candidate

    # 2. Fall back to system Ollama (development mode)
    system_ollama = "ollama.exe" if system == "Windows" else "ollama"
    try:
        result = subprocess.run(
            ["where" if system == "Windows" else "which", system_ollama],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            path = Path(result.stdout.strip().splitlines()[0])
            logger.info(f"Using system Ollama binary: {path}")
            return path
    except Exception:
        pass

    return None


def _get_models_dir() -> Optional[Path]:
    """Find the bundled models directory."""
    app_root = _get_app_root()

    candidates = [
        app_root / "ollama_models",
        app_root / "models",
    ]
    for candidate in candidates:
        if candidate.exists():
            logger.info(f"Found bundled models directory: {candidate}")
            return candidate

    return None


# ── Ollama Health Check ───────────────────────────────────────────────────────

def _is_ollama_running() -> bool:
    """Check if Ollama HTTP API is responding."""
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False


def _wait_for_ollama(timeout: int = OLLAMA_STARTUP_TIMEOUT) -> bool:
    """
    Poll the Ollama API until it becomes ready or timeout is reached.
    Returns True if ready, False if timed out.
    """
    logger.info(f"Waiting for Ollama to start (timeout={timeout}s)...")
    deadline = time.time() + timeout
    attempt = 0

    while time.time() < deadline:
        attempt += 1
        if _is_ollama_running():
            logger.info(f"Ollama is ready (attempt {attempt})")
            return True
        time.sleep(1)

    logger.error(f"Ollama did not start within {timeout} seconds")
    return False


# ── Model Verification ────────────────────────────────────────────────────────

def _get_available_models() -> list[str]:
    """Return list of model names available in Ollama."""
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if r.status_code == 200:
            return [m.get("name", "") for m in r.json().get("models", [])]
    except requests.RequestException:
        pass
    return []


def _verify_models() -> bool:
    """
    Verify that the required models are available in Ollama.
    In offline mode we do NOT attempt to pull them — they must already
    exist in the bundled OLLAMA_MODELS directory.
    """
    available = _get_available_models()
    logger.info(f"Available Ollama models: {available}")

    missing = []
    for model in REQUIRED_MODELS:
        # Check if model name is a prefix of any available model
        model_base = model.split(":")[0]
        if not any(model_base in avail for avail in available):
            missing.append(model)

    if missing:
        logger.warning(
            f"Required models not found in Ollama: {missing}. "
            "Ensure the bundled model files are present in the 'ollama_models' directory."
        )
        return False

    logger.info("All required models verified ✓")
    return True


# ── Startup ───────────────────────────────────────────────────────────────────

def start_ollama() -> bool:
    """
    Start the Ollama server if not already running.
    
    Returns True if Ollama is ready (either was already running, or we started it).
    Returns False if Ollama could not be started.
    """
    global _ollama_process, _ollama_managed

    # Already running externally — leave it alone
    if _is_ollama_running():
        logger.info("Ollama is already running (external). Skipping managed start.")
        return True

    ollama_bin = _get_ollama_binary()
    if ollama_bin is None:
        logger.error(
            "Ollama binary not found. Cannot start the language model server. "
            "Please install Ollama from https://ollama.com/download"
        )
        return False

    # Set OLLAMA_MODELS to the bundled models directory if available
    models_dir = _get_models_dir()
    env = os.environ.copy()
    if models_dir:
        env["OLLAMA_MODELS"] = str(models_dir)
        logger.info(f"Set OLLAMA_MODELS={models_dir}")
    else:
        logger.warning(
            "Bundled models directory not found. "
            "Ollama will use its default model store (~/.ollama/models). "
            "Models must be pre-installed for offline use."
        )

    # Prevent Ollama from showing its own window
    env.setdefault("OLLAMA_HOST", "127.0.0.1:11434")
    env.setdefault("OLLAMA_NOPRUNE", "1")   # Don't auto-prune models on start

    logger.info(f"Starting bundled Ollama server: {ollama_bin}")

    try:
        system = platform.system()
        if system == "Windows":
            # CREATE_NO_WINDOW hides the console window on Windows
            _ollama_process = subprocess.Popen(
                [str(ollama_bin), "serve"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            _ollama_process = subprocess.Popen(
                [str(ollama_bin), "serve"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        _ollama_managed = True
        logger.info(f"Ollama process started (PID={_ollama_process.pid})")

    except Exception as e:
        logger.error(f"Failed to start Ollama: {e}")
        return False

    # Wait for API to become ready
    ready = _wait_for_ollama()
    if not ready:
        stop_ollama()
        return False

    # Verify models are available
    _verify_models()

    # Register shutdown hook
    atexit.register(stop_ollama)

    return True


# ── Shutdown ──────────────────────────────────────────────────────────────────

def stop_ollama():
    """Terminate the managed Ollama process gracefully."""
    global _ollama_process, _ollama_managed

    if not _ollama_managed or _ollama_process is None:
        return

    logger.info("Stopping managed Ollama server...")
    try:
        _ollama_process.terminate()
        _ollama_process.wait(timeout=10)
        logger.info("Ollama server stopped cleanly.")
    except subprocess.TimeoutExpired:
        logger.warning("Ollama did not stop in time — killing forcefully.")
        _ollama_process.kill()
    except Exception as e:
        logger.warning(f"Error stopping Ollama: {e}")
    finally:
        _ollama_process = None
        _ollama_managed = False


# ── Status ────────────────────────────────────────────────────────────────────

def get_ollama_status() -> dict:
    """Return current Ollama status for the health endpoint."""
    return {
        "running": _is_ollama_running(),
        "managed": _ollama_managed,
        "pid": _ollama_process.pid if _ollama_process else None,
        "models": _get_available_models(),
        "base_url": OLLAMA_BASE_URL,
    }
