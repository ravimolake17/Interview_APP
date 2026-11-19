"""TTS cache fingerprint helpers (text + voice + format invalidation)."""

from __future__ import annotations

import hashlib
import os


DEFAULT_CONTENT_TYPE = "audio/wav"
STREAM_CONTENT_TYPE = "audio/mpeg"


def _voice_style_version() -> str:
    """Changing SSML style/pauses must invalidate previously cached audio."""
    return ",".join(
        [
            "ssml-v2",
            (os.getenv("TTS_STYLE") or "empathetic").strip().lower(),
            (os.getenv("TTS_STYLE_DEGREE") or "1.1").strip(),
            (os.getenv("TTS_SENTENCE_PAUSE_MS") or "320").strip(),
            (os.getenv("TTS_COMMA_PAUSE_MS") or "160").strip(),
        ]
    )


def cache_fingerprint(text: str, *, voice: str, content_type: str) -> str:
    payload = "|".join(
        [
            (text or "").strip(),
            (voice or "female").strip().lower(),
            (content_type or DEFAULT_CONTENT_TYPE).strip().lower(),
            _voice_style_version(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def tts_combine_ack_enabled() -> bool:
    env = (os.getenv("INTERVIEW_TTS_COMBINE_ACK") or "").strip().lower()
    if env in {"0", "false", "no", "off"}:
        return False
    if env in {"1", "true", "yes", "on"}:
        return True
    try:
        from core.config import get_settings

        return bool(getattr(get_settings(), "interview_tts_combine_ack", True))
    except Exception:
        return True


def tts_stream_enabled() -> bool:
    env = (os.getenv("INTERVIEW_TTS_STREAM") or "").strip().lower()
    if env in {"0", "false", "no", "off"}:
        return False
    if env in {"1", "true", "yes", "on"}:
        return True
    try:
        from core.config import get_settings

        return bool(getattr(get_settings(), "interview_tts_stream", True))
    except Exception:
        return True


def build_combined_utterance(ack: str | None, question_text: str | None) -> str:
    parts = [str(ack or "").strip(), str(question_text or "").strip()]
    return " ".join(part for part in parts if part).strip()
