"""Bounded thread pool for blocking Azure/Groq STT work.

Keeps FastAPI's event loop free while capping concurrent transcriptions.
"""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

import threading

_executor: ThreadPoolExecutor | None = None
_lock = threading.Lock()


def _worker_count() -> int:
    try:
        from core.config import get_settings

        return max(1, min(16, int(getattr(get_settings(), "stt_worker_threads", 4) or 4)))
    except Exception:
        raw = (os.getenv("STT_WORKER_THREADS") or "4").strip()
        try:
            return max(1, min(16, int(raw)))
        except ValueError:
            return 4


def _timeout_seconds() -> float:
    try:
        from core.config import get_settings

        return float(getattr(get_settings(), "stt_timeout_seconds", 90) or 90)
    except Exception:
        raw = (os.getenv("STT_TIMEOUT_SECONDS") or "90").strip()
        try:
            return max(5.0, min(300.0, float(raw)))
        except ValueError:
            return 90.0


def get_stt_executor() -> ThreadPoolExecutor:
    global _executor
    with _lock:
        if _executor is None:
            workers = _worker_count()
            _executor = ThreadPoolExecutor(
                max_workers=workers,
                thread_name_prefix="stt-worker",
            )
            logger.info("STT executor started (max_workers=%s)", workers)
        return _executor


def shutdown_stt_executor() -> None:
    global _executor
    with _lock:
        if _executor is not None:
            _executor.shutdown(wait=False, cancel_futures=False)
            _executor = None


async def run_stt_blocking(fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Run blocking STT/correction work off the event loop with a hard timeout."""
    loop = asyncio.get_running_loop()
    executor = get_stt_executor()
    timeout = _timeout_seconds()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(executor, lambda: fn(*args, **kwargs)),
            timeout=timeout,
        )
    except asyncio.TimeoutError as exc:
        raise TimeoutError(f"Speech transcription timed out after {timeout:.0f}s") from exc
