"""Process clock that ignores OS date/time changes after it is anchored.

Interview slots, join windows, and HR edit locks must not follow a laptop
clock. We sync UTC from the internet when possible, then advance with
``time.monotonic()`` so changing Windows date/time has no effect.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_TIME_URLS = (
    "https://www.gstatic.com/generate_204",
    "https://cloudflare.com",
    "https://1.1.1.1",
)

_anchor_utc: datetime | None = None
_anchor_mono: float | None = None
_last_sync_mono: float = 0.0
_SYNC_EVERY_SECONDS = 6 * 3600


def _http_utc() -> datetime | None:
    for url in _TIME_URLS:
        try:
            req = Request(
                url,
                method="HEAD",
                headers={"User-Agent": "InterviewAgenticAI/1.0"},
            )
            with urlopen(req, timeout=2.5) as resp:
                header = resp.headers.get("Date")
            if not header:
                continue
            parsed = parsedate_to_datetime(header)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            logger.debug("Trusted time sync failed for %s", url, exc_info=True)
    return None


def reset_trusted_clock_for_tests() -> None:
    global _anchor_utc, _anchor_mono, _last_sync_mono
    _anchor_utc = None
    _anchor_mono = None
    _last_sync_mono = 0.0


def sync_trusted_clock(*, force: bool = False) -> datetime:
    global _anchor_utc, _anchor_mono, _last_sync_mono
    now_mono = time.monotonic()
    if (
        not force
        and _anchor_utc is not None
        and _anchor_mono is not None
        and (now_mono - _last_sync_mono) < _SYNC_EVERY_SECONDS
    ):
        return trusted_utc_now()

    remote = _http_utc()
    source = remote or datetime.now(timezone.utc)
    _anchor_utc = source
    _anchor_mono = time.monotonic()
    _last_sync_mono = _anchor_mono
    if remote is not None:
        logger.info("Trusted clock synced from internet UTC (%s)", remote.isoformat())
    else:
        logger.warning(
            "Trusted clock using OS UTC at startup; later OS clock changes are still ignored"
        )
    return _anchor_utc


def trusted_utc_now() -> datetime:
    global _anchor_utc, _anchor_mono
    if _anchor_utc is None or _anchor_mono is None:
        sync_trusted_clock(force=True)
    elapsed = time.monotonic() - float(_anchor_mono or 0)
    if elapsed > _SYNC_EVERY_SECONDS:
        try:
            return sync_trusted_clock(force=True)
        except Exception:
            logger.debug("Trusted clock periodic resync failed", exc_info=True)
    return _anchor_utc + timedelta(seconds=elapsed)


def trusted_now(tz_name: str | None = None) -> datetime:
    utc = trusted_utc_now()
    name = (tz_name or "Asia/Kolkata").strip() or "Asia/Kolkata"
    try:
        from zoneinfo import ZoneInfo

        return utc.astimezone(ZoneInfo(name))
    except Exception:
        return utc.astimezone(timezone(timedelta(hours=5, minutes=30)))
