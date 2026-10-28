"""Shared Redis client with in-process memory fallback when Redis is down."""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

_client = None
_client_lock = threading.Lock()
_memory: dict[str, tuple[str, float | None]] = {}
_memory_lock = threading.Lock()
_using_memory = False


def _settings_url() -> str:
    try:
        from core.config import get_settings

        return str(getattr(get_settings(), "redis_url", "") or "").strip()
    except Exception:
        return ""


def redis_enabled() -> bool:
    return bool(_settings_url())


def get_redis():
    """Return a redis client, or None when using memory fallback."""
    global _client, _using_memory
    url = _settings_url()
    if not url:
        _using_memory = True
        return None
    with _client_lock:
        if _client is not None:
            return _client
        try:
            import redis

            client = redis.Redis.from_url(url, decode_responses=False)
            client.ping()
            _client = client
            _using_memory = False
            logger.info("Redis connected (%s)", url.split("@")[-1])
            return _client
        except Exception:
            logger.warning("Redis unavailable — using in-process memory cache/queue", exc_info=True)
            _using_memory = True
            _client = None
            return None


def using_memory_fallback() -> bool:
    get_redis()
    return _using_memory


def _mem_get(key: str) -> bytes | None:
    with _memory_lock:
        item = _memory.get(key)
        if not item:
            return None
        value, expires = item
        if expires is not None and time.time() >= expires:
            _memory.pop(key, None)
            return None
        return value.encode("utf-8") if isinstance(value, str) else value


def _mem_set(key: str, value: bytes | str, ttl_seconds: int | None = None) -> None:
    raw = value.decode("utf-8") if isinstance(value, bytes) else str(value)
    expires = time.time() + ttl_seconds if ttl_seconds else None
    with _memory_lock:
        _memory[key] = (raw, expires)


def _mem_delete(key: str) -> None:
    with _memory_lock:
        _memory.pop(key, None)


def cache_set(key: str, value: Any, *, ttl_seconds: int = 86_400) -> None:
    payload = value if isinstance(value, (bytes, bytearray)) else json.dumps(value, default=str).encode("utf-8")
    client = get_redis()
    if client is None:
        _mem_set(key, bytes(payload), ttl_seconds)
        return
    try:
        client.setex(key, int(ttl_seconds), bytes(payload))
    except Exception:
        logger.debug("Redis SET failed for %s; memory fallback", key, exc_info=True)
        _mem_set(key, bytes(payload), ttl_seconds)


def cache_get_bytes(key: str) -> bytes | None:
    client = get_redis()
    if client is None:
        return _mem_get(key)
    try:
        raw = client.get(key)
        return raw if isinstance(raw, (bytes, bytearray)) else None
    except Exception:
        return _mem_get(key)


def cache_get_json(key: str) -> Any | None:
    raw = cache_get_bytes(key)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def cache_delete(key: str) -> None:
    client = get_redis()
    if client is None:
        _mem_delete(key)
        return
    try:
        client.delete(key)
    except Exception:
        _mem_delete(key)


def queue_push(queue_key: str, value: Any) -> None:
    payload = json.dumps(value, default=str).encode("utf-8")
    client = get_redis()
    if client is None:
        # Memory list stored as JSON array under queue_key
        items = cache_get_json(queue_key) or []
        if not isinstance(items, list):
            items = []
        items.append(json.loads(payload.decode("utf-8")))
        cache_set(queue_key, items, ttl_seconds=86_400)
        return
    try:
        client.rpush(queue_key, payload)
    except Exception:
        logger.debug("Redis RPUSH failed; memory fallback", exc_info=True)
        items = cache_get_json(queue_key) or []
        if not isinstance(items, list):
            items = []
        items.append(json.loads(payload.decode("utf-8")))
        cache_set(queue_key, items, ttl_seconds=86_400)


def queue_pop(queue_key: str, *, timeout_seconds: int = 1) -> Any | None:
    client = get_redis()
    if client is None:
        items = cache_get_json(queue_key) or []
        if not isinstance(items, list) or not items:
            return None
        item = items.pop(0)
        cache_set(queue_key, items, ttl_seconds=86_400)
        return item
    try:
        raw = client.blpop(queue_key, timeout=max(1, int(timeout_seconds)))
        if not raw:
            return None
        _key, payload = raw
        return json.loads(payload.decode("utf-8"))
    except Exception:
        items = cache_get_json(queue_key) or []
        if not isinstance(items, list) or not items:
            return None
        item = items.pop(0)
        cache_set(queue_key, items, ttl_seconds=86_400)
        return item


def queue_pop_nowait(queue_key: str) -> Any | None:
    client = get_redis()
    if client is None:
        items = cache_get_json(queue_key) or []
        if not isinstance(items, list) or not items:
            return None
        item = items.pop(0)
        cache_set(queue_key, items, ttl_seconds=86_400)
        return item
    try:
        payload = client.lpop(queue_key)
        if not payload:
            return None
        return json.loads(payload.decode("utf-8"))
    except Exception:
        return None
