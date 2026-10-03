"""Persistent ChromaDB client for interview vector memory.

Postgres remains the system of record. Chroma only stores embeddings so Agents
1, 4, 6, and 7 can retrieve similar past resumes, questions, answers, and HR
outcomes. All operations no-op when Chroma or embeddings are unavailable.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from core.config import get_settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_client: Any = None
_ready: bool = False
_error: str | None = None


def chroma_persist_path() -> Path:
    settings = get_settings()
    raw = (settings.chroma_persist_dir or "storage/chroma").strip()
    path = Path(raw)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    return path


def chroma_enabled() -> bool:
    return bool(get_settings().chroma_enabled)


def chroma_status() -> dict[str, Any]:
    return {
        "enabled": chroma_enabled(),
        "ready": _ready,
        "persist_dir": str(chroma_persist_path()),
        "error": _error,
    }


def get_chroma_client() -> Any | None:
    """Return the process-wide PersistentClient, or None if unavailable."""
    global _client, _ready, _error
    if not chroma_enabled():
        return None
    if _client is not None:
        return _client
    with _lock:
        if _client is not None:
            return _client
        try:
            import chromadb
        except Exception as exc:
            _error = f"chromadb import failed: {exc}"
            logger.warning("ChromaDB is not installed; vector memory disabled (%s)", exc)
            return None
        try:
            path = chroma_persist_path()
            path.mkdir(parents=True, exist_ok=True)
            _client = chromadb.PersistentClient(path=str(path))
            _ready = True
            _error = None
            logger.info("ChromaDB ready at %s", path)
            return _client
        except Exception as exc:
            _error = str(exc)
            logger.warning("ChromaDB client failed to start: %s", exc)
            return None


def init_chroma_runtime() -> dict[str, Any]:
    """Create the client and seed starter examples if needed."""
    if not chroma_enabled():
        logger.info("ChromaDB disabled by settings")
        return chroma_status()
    client = get_chroma_client()
    if client is None:
        return chroma_status()
    if get_settings().chroma_seed_on_startup:
        def _seed() -> None:
            try:
                from core.chroma_store import seed_chroma_memory

                seed_chroma_memory()
            except Exception:
                logger.warning("ChromaDB seed skipped", exc_info=True)

        threading.Thread(target=_seed, daemon=True, name="chroma-seed").start()
    return chroma_status()


def shutdown_chroma_runtime() -> None:
    global _client, _ready
    with _lock:
        _client = None
        _ready = False
