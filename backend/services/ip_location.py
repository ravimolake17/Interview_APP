"""Resolve coarse city/region labels for audit-log IPs."""

from __future__ import annotations

import ipaddress
import json
import logging
import threading
import urllib.error
import urllib.request
from collections import OrderedDict

logger = logging.getLogger(__name__)

_CACHE_MAX = 512
_cache: OrderedDict[str, str | None] = OrderedDict()
_cache_lock = threading.Lock()


def normalize_client_ip(ip_address: str | None) -> str | None:
    """Strip ports / brackets. Azure AGW often sends ``client_ip:port``."""
    if not ip_address:
        return None
    value = str(ip_address).strip().strip('"').strip("'")
    if not value or value.lower() in {"unknown", "null", "-"}:
        return None

    # [IPv6]:port
    if value.startswith("[") and "]" in value:
        value = value[1 : value.index("]")]
    # IPv4:port (exactly one colon)
    elif value.count(":") == 1:
        host, maybe_port = value.rsplit(":", 1)
        if maybe_port.isdigit():
            value = host

    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return value[:64] or None


def _is_private_or_local(ip: str) -> str | None:
    if ip in {"127.0.0.1", "::1"} or ip.startswith("127."):
        return "Localhost"
    try:
        parsed = ipaddress.ip_address(ip)
    except ValueError:
        return None
    if parsed.is_private or parsed.is_loopback or parsed.is_link_local:
        return "Private network"
    if parsed.is_reserved or parsed.is_multicast:
        return "Reserved network"
    return None


def _cache_get(ip: str) -> tuple[bool, str | None]:
    with _cache_lock:
        if ip not in _cache:
            return False, None
        _cache.move_to_end(ip)
        return True, _cache[ip]


def _cache_set(ip: str, label: str | None) -> None:
    with _cache_lock:
        _cache[ip] = label
        _cache.move_to_end(ip)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)


def _lookup_public_ip(ip: str) -> str | None:
    """Best-effort HTTPS geo lookup (no API key). Fail soft on any error."""
    url = f"https://ipwho.is/{ip}"
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "InterviewAgenticAI-Audit/1.0", "Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=1.5) as response:
            raw = response.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError) as exc:
        logger.debug("IP geo lookup failed for %s: %s", ip, exc)
        return None

    if not isinstance(data, dict) or not data.get("success", True):
        return None

    parts = [
        str(data.get("city") or "").strip(),
        str(data.get("region") or data.get("regionName") or "").strip(),
        str(data.get("country") or "").strip(),
    ]
    label = ", ".join(part for part in parts if part)
    return label[:255] or None


def resolve_location_label(ip_address: str | None) -> str | None:
    """Return a human location label for an audit IP, or None if unknown."""
    ip = normalize_client_ip(ip_address)
    if not ip:
        return None

    local = _is_private_or_local(ip)
    if local:
        return local

    hit, cached = _cache_get(ip)
    if hit:
        return cached

    label = _lookup_public_ip(ip)
    _cache_set(ip, label)
    return label
