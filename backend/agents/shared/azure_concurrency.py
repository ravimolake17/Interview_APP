"""Process-wide Azure capacity gates (STT / TTS / GPT) with bounded wait.

Keeps concurrent Azure calls under deployment quota without uncontrolled
retry storms. Limits are per Uvicorn process — production must stay at
``--workers 1`` so these gates remain coherent.
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_semaphores: dict[str, threading.BoundedSemaphore] = {}
_limits: dict[str, int] = {}
_stats: dict[str, dict[str, int | float]] = {}


def _settings_int(name: str, default: int) -> int:
    try:
        from core.config import get_settings

        return max(1, int(getattr(get_settings(), name, default) or default))
    except Exception:
        return max(1, int(default))


def _limit_for(kind: str) -> int:
    mapping = {
        "llm": ("azure_llm_max_concurrent", 8),
        "stt": ("azure_stt_max_concurrent", 6),
        "tts": ("azure_tts_max_concurrent", 6),
    }
    attr, default = mapping.get(kind, ("azure_llm_max_concurrent", 8))
    return _settings_int(attr, default)


def _wait_seconds(kind: str) -> float:
    try:
        from core.config import get_settings

        attr = {
            "llm": "azure_llm_acquire_timeout_seconds",
            "stt": "azure_stt_acquire_timeout_seconds",
            "tts": "azure_tts_acquire_timeout_seconds",
        }.get(kind, "azure_llm_acquire_timeout_seconds")
        return max(1.0, float(getattr(get_settings(), attr, 30.0) or 30.0))
    except Exception:
        return 30.0


def _get_semaphore(kind: str) -> threading.BoundedSemaphore:
    with _lock:
        limit = _limit_for(kind)
        sem = _semaphores.get(kind)
        if sem is None or _limits.get(kind) != limit:
            sem = threading.BoundedSemaphore(limit)
            _semaphores[kind] = sem
            _limits[kind] = limit
            _stats.setdefault(
                kind,
                {
                    "limit": limit,
                    "acquired": 0,
                    "rejected": 0,
                    "wait_ms_total": 0.0,
                    "in_flight": 0,
                },
            )
            _stats[kind]["limit"] = limit
        return sem


class AzureCapacityError(RuntimeError):
    """Raised when a local concurrency slot cannot be acquired in time."""


@contextmanager
def azure_slot(kind: str) -> Iterator[None]:
    """Acquire a process-local Azure concurrency slot (blocking, timed)."""
    sem = _get_semaphore(kind)
    wait_s = _wait_seconds(kind)
    t0 = time.perf_counter()
    acquired = sem.acquire(timeout=wait_s)
    waited_ms = (time.perf_counter() - t0) * 1000.0
    with _lock:
        bucket = _stats.setdefault(
            kind,
            {
                "limit": _limit_for(kind),
                "acquired": 0,
                "rejected": 0,
                "wait_ms_total": 0.0,
                "in_flight": 0,
            },
        )
        bucket["wait_ms_total"] = float(bucket.get("wait_ms_total") or 0) + waited_ms
        if acquired:
            bucket["acquired"] = int(bucket.get("acquired") or 0) + 1
            bucket["in_flight"] = int(bucket.get("in_flight") or 0) + 1
        else:
            bucket["rejected"] = int(bucket.get("rejected") or 0) + 1
    if not acquired:
        logger.warning(
            "Azure %s capacity exhausted (waited %.0fms, limit=%s)",
            kind,
            waited_ms,
            _limit_for(kind),
        )
        raise AzureCapacityError(
            f"Azure {kind} concurrency limit reached; try again shortly."
        )
    try:
        yield
    finally:
        with _lock:
            bucket = _stats.get(kind) or {}
            bucket["in_flight"] = max(0, int(bucket.get("in_flight") or 0) - 1)
        sem.release()


def azure_concurrency_snapshot() -> dict[str, dict[str, int | float]]:
    with _lock:
        out: dict[str, dict[str, int | float]] = {}
        for kind in ("llm", "stt", "tts"):
            bucket = dict(_stats.get(kind) or {})
            bucket.setdefault("limit", _limit_for(kind))
            bucket.setdefault("acquired", 0)
            bucket.setdefault("rejected", 0)
            bucket.setdefault("wait_ms_total", 0.0)
            bucket.setdefault("in_flight", 0)
            out[kind] = bucket
        return out
