"""Bounded exponential backoff for Azure 429 / transient failures.

Never loops unboundedly. Honors Retry-After when present and sane.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _settings_int(name: str, default: int) -> int:
    try:
        from core.config import get_settings

        return max(0, int(getattr(get_settings(), name, default) or default))
    except Exception:
        return max(0, int(default))


def max_azure_retries() -> int:
    # Default 2 retries → 3 total attempts. Cap hard at 4.
    return min(4, _settings_int("azure_retry_max_attempts", 2))


def is_retryable_status(status: int | None) -> bool:
    return status in {408, 429, 500, 502, 503, 504}


def parse_retry_after_seconds(headers: dict | None, *, attempt: int) -> float:
    """Return sleep seconds from Retry-After or exponential backoff + jitter."""
    base = min(8.0, 0.5 * (2 ** max(0, attempt)))
    if headers:
        raw = headers.get("Retry-After") or headers.get("retry-after")
        if raw is not None:
            try:
                return min(30.0, max(0.25, float(raw)))
            except (TypeError, ValueError):
                pass
    return min(30.0, base + random.uniform(0.0, 0.35))


def call_with_azure_retries(
    label: str,
    fn: Callable[[], T],
    *,
    status_of: Callable[[BaseException], int | None] | None = None,
) -> T:
    """Invoke ``fn`` with a hard cap on retries for transient Azure errors."""
    attempts = max_azure_retries() + 1
    last_exc: BaseException | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except BaseException as exc:
            last_exc = exc
            status = status_of(exc) if status_of else _guess_status(exc)
            retryable = is_retryable_status(status) or _guess_retryable_text(exc)
            if attempt >= attempts - 1 or not retryable:
                raise
            headers = getattr(exc, "headers", None)
            if not isinstance(headers, dict):
                response = getattr(exc, "response", None)
                headers = getattr(response, "headers", None) if response is not None else None
            delay = parse_retry_after_seconds(
                dict(headers) if headers else None,
                attempt=attempt,
            )
            logger.warning(
                "Azure %s transient failure (attempt %s/%s, status=%s); backoff %.2fs",
                label,
                attempt + 1,
                attempts,
                status,
                delay,
            )
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc


def _guess_status(exc: BaseException) -> int | None:
    for attr in ("status_code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    if response is not None:
        code = getattr(response, "status_code", None)
        if isinstance(code, int):
            return code
    text = str(exc)
    for code in (429, 503, 502, 504, 500, 408):
        if str(code) in text:
            return code
    return None


def _guess_retryable_text(exc: BaseException) -> bool:
    text = str(exc).casefold()
    markers = (
        "429",
        "rate limit",
        "too many requests",
        "tpm",
        "throttl",
        "temporar",
        "unavailable",
        "overloaded",
        "timeout",
        "timed out",
        "503",
        "502",
        "504",
    )
    return any(m in text for m in markers)
