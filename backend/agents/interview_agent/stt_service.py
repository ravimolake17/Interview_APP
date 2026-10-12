"""Speech-to-text for Agent 4 (Groq Whisper and/or Azure Speech)."""

from __future__ import annotations

import io
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from agents.interview_agent.schemas import TranscribeResponse, TranscriptCorrection
from agents.screening_agent.config import settings
from agents.shared.model_catalog import describe_target, ordered_targets, should_fallback
from schemas.settings import AICatalogEntry

logger = logging.getLogger(__name__)

WHISPER_MODEL = "whisper-large-v3"
ALLOWED_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".webm", ".ogg", ".flac", ".mpeg", ".mpga"}
_AZURE_CONTENT_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".mpeg": "audio/mpeg",
    ".mpga": "audio/mpeg",
    ".ogg": "audio/ogg; codecs=opus",
    ".webm": "audio/webm; codecs=opus",
    ".m4a": "audio/mp4",
    ".flac": "audio/flac",
}


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

    targets = ordered_targets("stt")
    if not targets:
        groq_entry = AICatalogEntry(
            id="groq-whisper",
            name="Groq Whisper",
            kind="stt",
            provider="groq",
            model_id=WHISPER_MODEL,
        )
        azure_entry = AICatalogEntry(
            id="azure-speech-stt",
            name="Azure Speech STT",
            kind="stt",
            provider="azure",
            model_id="azure-speech",
        )
        preferred = str(getattr(settings, "STT_PROVIDER", "groq") or "groq").strip().lower()
        targets = [azure_entry, groq_entry] if preferred == "azure" else [groq_entry, azure_entry]

    last_error: Exception | None = None
    text = ""
    duration = None
    lang = language or "en"
    provider = "groq_whisper"
    model_name = WHISPER_MODEL
    for index, entry in enumerate(targets):
        try:
            text, duration, lang, provider, model_name = _transcribe_with_entry(
                entry,
                content,
                filename=filename,
                suffix=suffix,
                language=language,
                whisper_prompt=whisper_prompt,
                prior_text=prior_text,
                partial=partial,
            )
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            if index < len(targets) - 1 and should_fallback(exc):
                nxt = targets[index + 1]
                logger.warning(
                    "STT %s failed (%s); falling back to %s",
                    describe_target(entry),
                    exc,
                    describe_target(nxt),
                )
                continue
            raise
    if last_error:
        raise last_error

    from agents.interview_agent.stt_corrector import (
        correct_transcript_with_resume,
        strip_whisper_artifacts,
    )

    raw_text = strip_whisper_artifacts((text or "").strip())
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
        provider=provider,
        model=model_name,
        resume_corrected=resume_corrected,
        partial=partial,
        corrections=corrections,
    )


def transcribe_for_entry(
    entry: AICatalogEntry,
    content: bytes,
    *,
    filename: str = "audio.webm",
) -> TranscribeResponse:
    """Transcribe with one catalog STT row only (SuperAdmin test). No fallback."""
    if not content:
        raise ValueError("Empty audio payload.")
    suffix = Path(filename).suffix.lower() or ".webm"
    if suffix not in ALLOWED_AUDIO_SUFFIXES:
        raise ValueError(
            f"Unsupported audio type '{suffix}'. Use: {', '.join(sorted(ALLOWED_AUDIO_SUFFIXES))}"
        )
    text, duration, lang, provider, model_name = _transcribe_with_entry(
        entry,
        content,
        filename=filename,
        suffix=suffix,
        language="en-IN",
        whisper_prompt=None,
        prior_text=None,
        partial=False,
    )
    return TranscribeResponse(
        text=(text or "").strip(),
        language=lang,
        duration_seconds=float(duration) if duration is not None else None,
        provider=provider,
        model=model_name,
    )


def _transcribe_with_entry(
    entry: AICatalogEntry,
    content: bytes,
    *,
    filename: str,
    suffix: str,
    language: str | None,
    whisper_prompt: str | None,
    prior_text: str | None,
    partial: bool,
) -> tuple[str, float | None, str | None, str, str]:
    if entry.provider == "azure":
        return _transcribe_azure_speech(entry, content, suffix=suffix, language=language)
    return _transcribe_groq_whisper(
        content,
        filename=filename,
        suffix=suffix,
        language=language,
        whisper_prompt=whisper_prompt,
        prior_text=prior_text,
        partial=partial,
        model_id=entry.model_id or WHISPER_MODEL,
    )


def _transcribe_groq_whisper(
    content: bytes,
    *,
    filename: str,
    suffix: str,
    language: str | None,
    whisper_prompt: str | None,
    prior_text: str | None,
    partial: bool,
    model_id: str,
) -> tuple[str, float | None, str | None, str, str]:
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
                "model": model_id or WHISPER_MODEL,
                "response_format": "verbose_json",
            }
            kwargs["language"] = language or "en"
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
        return str(text or ""), duration, lang, "groq_whisper", model_id or WHISPER_MODEL
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            logger.debug("Could not delete temp audio file %s", tmp_path)


def _azure_locale(language: str | None) -> str:
    raw = str(language or "en-IN").strip() or "en-IN"
    lowered = raw.replace("_", "-").casefold()
    if lowered in {"en", "eng", "english"}:
        return "en-IN"
    if "-" not in raw and len(raw) == 2:
        return "en-IN" if lowered == "en" else f"{raw.lower()}-IN"
    return raw


def _ffmpeg_exe() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).is_file():
            return bundled
    except Exception:
        return None
    return None


def _to_azure_wav(content: bytes, suffix: str) -> tuple[bytes, str]:
    """Azure short-audio REST is most reliable with 16 kHz PCM WAV."""
    wav_type = "audio/wav; codecs=audio/pcm; samplerate=16000"
    if suffix == ".wav":
        return content, wav_type
    try:
        import miniaudio
        import numpy as np
        import soundfile as sf

        decoded = miniaudio.decode(
            content,
            nchannels=1,
            sample_rate=16000,
            output_format=miniaudio.SampleFormat.FLOAT32,
        )
        audio = np.frombuffer(decoded.samples, dtype=np.float32)
        if decoded.nchannels > 1:
            audio = audio.reshape(-1, decoded.nchannels).mean(axis=1)
        buf = io.BytesIO()
        sf.write(buf, audio, 16000, format="WAV", subtype="PCM_16")
        return buf.getvalue(), wav_type
    except Exception as exc:
        logger.debug("miniaudio could not decode %s for Azure STT: %s", suffix, exc)

    ffmpeg = _ffmpeg_exe()
    if ffmpeg:
        with tempfile.TemporaryDirectory(prefix="azure_stt_") as temp:
            source = Path(temp) / f"clip{suffix or '.webm'}"
            target = Path(temp) / "clip.wav"
            source.write_bytes(content)
            converted = subprocess.run(
                [ffmpeg, "-y", "-i", str(source), "-ac", "1", "-ar", "16000", "-f", "wav", str(target)],
                capture_output=True,
                timeout=30,
                check=False,
            )
            if converted.returncode == 0 and target.exists() and target.stat().st_size > 44:
                return target.read_bytes(), wav_type
            err = (converted.stderr or b"").decode("utf-8", errors="ignore")[-200:]
            logger.warning("ffmpeg could not convert %s for Azure STT: %s", suffix, err)

    return content, _AZURE_CONTENT_TYPES.get(suffix, "audio/webm; codecs=opus")


def _transcribe_azure_speech(
    entry: AICatalogEntry,
    content: bytes,
    *,
    suffix: str,
    language: str | None,
) -> tuple[str, float | None, str | None, str, str]:
    import httpx

    key = getattr(settings, "AZURE_SPEECH_KEY", None)
    region = (entry.region or getattr(settings, "AZURE_SPEECH_REGION", "") or "eastus2").strip()
    endpoint = (
        entry.endpoint
        or getattr(settings, "AZURE_SPEECH_STT_ENDPOINT", "")
        or f"https://{region}.stt.speech.microsoft.com"
    ).rstrip("/")
    if not key:
        raise RuntimeError("Azure Speech key is not configured in SuperAdmin → API & Integration.")
    payload, content_type = _to_azure_wav(content, suffix)
    locale = _azure_locale(language)
    url = f"{endpoint}/speech/recognition/conversation/cognitiveservices/v1"
    response = httpx.post(
        url,
        params={"language": locale, "format": "simple"},
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": content_type,
            "Accept": "application/json",
        },
        content=payload,
        timeout=60,
    )
    if response.status_code >= 400:
        detail = (response.text or response.reason_phrase or "").strip()[:180]
        raise RuntimeError(
            "Azure Speech STT rejected this clip. Record a few seconds of speech and try again. "
            f"({response.status_code}: {detail or 'bad audio or language'})"
        )
    body = response.json() if response.content else {}
    text = str(body.get("DisplayText") or body.get("Text") or "").strip()
    if not text:
        nbest = body.get("NBest") or []
        if nbest and isinstance(nbest[0], dict):
            text = str(nbest[0].get("Display") or nbest[0].get("Lexical") or "").strip()
    if not text:
        raise RuntimeError("Azure Speech returned an empty transcript.")
    duration_ticks = body.get("Duration")
    duration = None
    if duration_ticks is not None:
        try:
            duration = float(duration_ticks) / 10_000_000
        except (TypeError, ValueError):
            duration = None
    return text, duration, language or "en-IN", "azure_speech", entry.model_id or "azure-speech"
