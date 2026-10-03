"""Process-wide Groq queue for resume extraction.

Groq TPM/RPM is shared. Bursting resume parses causes 429s; treating that as a
parse failure used to save candidates from the weak fallback. This queue:

1. Allows one resume Groq call at a time.
2. Waits and retries on 429 instead of falling back.
3. Raises GroqRateLimitError if Groq stays busy past the wait budget so the
   extract job fails and the candidate is not saved.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import TypeVar

from agents.screening_agent.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class GroqRateLimitError(RuntimeError):
    """Groq is busy. Do not use fallback parse or persist the candidate."""


def is_rate_limited(exc: BaseException) -> bool:
    text = str(exc).casefold()
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status == 429:
        return True
    return any(
        token in text
        for token in ("429", "rate limit", "tokens per minute", "tpm", "too many requests")
    )


def retry_after_seconds(exc: BaseException, *, attempt: int) -> float:
    headers = getattr(exc, "headers", None) or {}
    if isinstance(headers, dict):
        raw = headers.get("Retry-After") or headers.get("retry-after")
        if raw:
            try:
                return min(90.0, max(1.0, float(raw)))
            except (TypeError, ValueError):
                pass
    return min(60.0, 2.0 * (2 ** min(attempt, 5)))


class GroqResumeQueue:
    """Single-flight resume parse queue with cooldown after 429."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cooldown_until = 0.0

    def call(self, fn: Callable[[], T]) -> T:
        deadline = time.monotonic() + settings.GROQ_RATE_LIMIT_WAIT_SECONDS
        with self._lock:
            attempt = 0
            while True:
                cooldown = self._cooldown_until - time.monotonic()
                if cooldown > 0:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise GroqRateLimitError(
                            "Groq rate limit persisted; resume was not parsed or saved."
                        )
                    time.sleep(min(cooldown, remaining))

                try:
                    result = fn()
                    self._cooldown_until = 0.0
                    return result
                except GroqRateLimitError:
                    raise
                except Exception as exc:
                    if not is_rate_limited(exc):
                        raise
                    attempt += 1
                    delay = retry_after_seconds(exc, attempt=attempt)
                    self._cooldown_until = time.monotonic() + delay
                    remaining = deadline - time.monotonic()
                    if remaining <= delay:
                        raise GroqRateLimitError(
                            "Groq rate limit persisted; resume was not parsed or saved."
                        ) from exc
                    logger.info(
                        "Groq busy for resume parse; queued retry in %.1fs (attempt %s)",
                        delay,
                        attempt,
                    )


_queue: GroqResumeQueue | None = None
_queue_lock = threading.Lock()


def get_groq_resume_queue() -> GroqResumeQueue:
    global _queue
    if _queue is None:
        with _queue_lock:
            if _queue is None:
                _queue = GroqResumeQueue()
    return _queue
