"""Whisper STT via Groq (whisper-large-v3) for Agent 4."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from agents.interview_agent.schemas import TranscribeResponse, TranscriptCorrection
from agents.screening_agent.config import settings

logger = logging.getLogger(__name__)

WHISPER_MODEL = "whisper-large-v3"
ALLOWED_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".webm", ".ogg", ".flac", ".mpeg", ".mpga"}


def transcribe_audio_bytes(
    content: bytes,
    *,
    filename: str = "audio.webm",
    language: str | None = None,
    whisper_prompt: str | None = None,
    prior_text: str | None = None,
    partial: bool = False,
    resume_context: dict[str, str] | None = None,
    resume_terms: list[str] | None = None,
    question_text: str | None = None,
    candidate_name: str | None = None,
) -> TranscribeResponse:
    """Transcribe candidate speech with Groq Whisper (+ optional resume correction)."""
    if not content:
        raise ValueError("Empty audio payload.")

    suffix = Path(filename).suffix.lower() or ".webm"
    if suffix not in ALLOWED_AUDIO_SUFFIXES:
        raise ValueError(
            f"Unsupported audio type '{suffix}'. Use: {', '.join(sorted(ALLOWED_AUDIO_SUFFIXES))}"
        )

    if not settings.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not configured. Set it to enable Whisper STT for Agent 4."
        )

    try:
        from groq import Groq
    except ImportError as exc:
        raise RuntimeError("groq package is required for Whisper STT.") from exc

    client = Groq(api_key=settings.GROQ_API_KEY)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        with tmp_path.open("rb") as audio_file:
            kwargs: dict = {
                "file": (filename or tmp_path.name, audio_file.read()),
                "model": WHISPER_MODEL,
                "response_format": "verbose_json",
            }
            if language:
                kwargs["language"] = language
            else:
                # Interview answers are English; pinning language reduces garbled words.
                kwargs["language"] = "en"
            kwargs["temperature"] = 0
            prompt_parts: list[str] = []
            if prior_text and partial:
                prompt_parts.append(prior_text.strip()[-400:])
            if whisper_prompt:
                prompt_parts.append(whisper_prompt.strip())
            if prompt_parts:
                kwargs["prompt"] = " ".join(prompt_parts)[:800]
            result = client.audio.transcriptions.create(**kwargs)

        text = getattr(result, "text", None) or ""
        if isinstance(result, dict):
            text = str(result.get("text") or text)
            duration = result.get("duration")
            lang = result.get("language")
        else:
            duration = getattr(result, "duration", None)
            lang = getattr(result, "language", None) or language or "en"

        from agents.interview_agent.stt_corrector import (
            correct_transcript_with_resume,
            strip_whisper_artifacts,
        )

        raw_text = strip_whisper_artifacts(text.strip())
        final_text = raw_text
        resume_corrected = False
        corrections: list[TranscriptCorrection] = []

        if (
            not partial
            and raw_text
            and (resume_context is not None or resume_terms or candidate_name)
        ):
            fixed = correct_transcript_with_resume(
                raw_text,
                context=resume_context or {},
                resume_terms=resume_terms or [],
                question_text=question_text,
                candidate_name=candidate_name,
            )
            final_text = str(fixed.get("text") or raw_text).strip()
            resume_corrected = bool(fixed.get("resume_corrected"))
            for item in fixed.get("corrections") or []:
                if isinstance(item, dict):
                    try:
                        corrections.append(TranscriptCorrection(**item))
                    except Exception:
                        continue

        return TranscribeResponse(
            text=final_text,
            raw_text=raw_text if resume_corrected else None,
            language=lang,
            duration_seconds=float(duration) if duration is not None else None,
            provider="groq_whisper",
            model=WHISPER_MODEL,
            resume_corrected=resume_corrected,
            partial=partial,
            corrections=corrections,
        )
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            logger.debug("Could not delete temp audio file %s", tmp_path)
