"""Shared httpx clients for Azure OpenAI / Speech (connection reuse)."""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_clients: dict[str, Any] = {}


def _max_connections() -> int:
    try:
        from core.config import get_settings

        return max(4, int(getattr(get_settings(), "azure_http_max_connections", 32) or 32))
    except Exception:
        return 32


def get_azure_http_client(name: str = "default"):
    """Return a process-wide sync httpx.Client with connection pooling."""
    import httpx

    with _lock:
        client = _clients.get(name)
        if client is not None:
            return client
        limits = httpx.Limits(
            max_connections=_max_connections(),
            max_keepalive_connections=max(2, _max_connections() // 2),
            keepalive_expiry=30.0,
        )
        client = httpx.Client(limits=limits, timeout=90.0)
        _clients[name] = client
        logger.info("Azure httpx client ready (name=%s, max_connections=%s)", name, _max_connections())
        return client


def close_azure_http_clients() -> None:
    with _lock:
        for name, client in list(_clients.items()):
            try:
                client.close()
            except Exception:
                logger.debug("Azure httpx client close failed (%s)", name, exc_info=True)
        _clients.clear()
