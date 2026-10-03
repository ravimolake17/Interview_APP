"""Agent 5 voice verification STT via Agent 4 Groq Whisper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents.interview_agent.stt_service import transcribe_audio_bytes


@dataclass(frozen=True)
class VoiceTranscriptionResult:
    text: str
    recognition_available: bool
    recognition_error: str | None
    provider: str | None = None
    model: str | None = None
    language: str | None = None
    duration_seconds: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "recognition_available": self.recognition_available,
            "recognition_error": self.recognition_error,
            "provider": self.provider,
            "model": self.model,
            "language": self.language,
            "duration_seconds": self.duration_seconds,
        }


def transcribe_verification_sentence(
    audio_bytes: bytes,
    *,
    filename: str,
    sentence_text: str,
) -> VoiceTranscriptionResult:
    """Transcribe a verification sentence with Whisper, biased by the expected text."""
    if not audio_bytes:
        return VoiceTranscriptionResult(
            text="",
            recognition_available=False,
            recognition_error="empty_audio_payload",
        )

    prompt = sentence_text.strip()
    try:
        result = transcribe_audio_bytes(
            audio_bytes,
            filename=filename,
            language="en",
            whisper_prompt=prompt or None,
        )
    except RuntimeError as exc:
        return VoiceTranscriptionResult(
            text="",
            recognition_available=False,
            recognition_error=str(exc),
        )
    except ValueError as exc:
        return VoiceTranscriptionResult(
            text="",
            recognition_available=False,
            recognition_error=str(exc),
        )
    except Exception as exc:
        return VoiceTranscriptionResult(
            text="",
            recognition_available=False,
            recognition_error=f"{type(exc).__name__}: {exc}",
        )

    text = (result.text or "").strip()
    if not text:
        return VoiceTranscriptionResult(
            text="",
            recognition_available=False,
            recognition_error="whisper_returned_empty_transcript",
            provider=result.provider,
            model=result.model,
            language=result.language,
            duration_seconds=result.duration_seconds,
        )

    return VoiceTranscriptionResult(
        text=text,
        recognition_available=True,
        recognition_error=None,
        provider=result.provider,
        model=result.model,
        language=result.language,
        duration_seconds=result.duration_seconds,
    )
