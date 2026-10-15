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


# Azure short-audio REST rejects / truncates clips near ~60s. Stay under that.
_AZURE_CHUNK_SECONDS = 45.0
_AZURE_CHUNK_OVERLAP = 1.0
_AZURE_CHUNK_THRESHOLD = 48.0


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
                timeout=60,
                check=False,
            )
            if converted.returncode == 0 and target.exists() and target.stat().st_size > 44:
                return target.read_bytes(), wav_type
            err = (converted.stderr or b"").decode("utf-8", errors="ignore")[-200:]
            logger.warning("ffmpeg could not convert %s for Azure STT: %s", suffix, err)

    return content, _AZURE_CONTENT_TYPES.get(suffix, "audio/webm; codecs=opus")


def _wav_duration_seconds(wav_bytes: bytes) -> float | None:
    """Return PCM WAV duration when headers are readable."""
    import wave

    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as handle:
            rate = handle.getframerate() or 0
            frames = handle.getnframes() or 0
            if rate <= 0 or frames <= 0:
                return None
            return float(frames) / float(rate)
    except Exception:
        return None


def _split_pcm_wav(wav_bytes: bytes, *, chunk_seconds: float, overlap_seconds: float) -> list[bytes]:
    """Split 16-bit PCM WAV into overlapping chunks for Azure short-audio STT."""
    import wave

    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as handle:
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            rate = handle.getframerate()
            frames = handle.readframes(handle.getnframes())
    except Exception:
        return [wav_bytes]

    if rate <= 0 or sample_width <= 0 or channels <= 0 or not frames:
        return [wav_bytes]

    frame_bytes = sample_width * channels
    total_frames = len(frames) // frame_bytes
    chunk_frames = max(1, int(chunk_seconds * rate))
    overlap_frames = max(0, int(overlap_seconds * rate))
    if total_frames <= chunk_frames:
        return [wav_bytes]

    parts: list[bytes] = []
    start = 0
    while start < total_frames:
        end = min(total_frames, start + chunk_frames)
        slice_frames = frames[start * frame_bytes : end * frame_bytes]
        buf = io.BytesIO()
        with wave.open(buf, "wb") as out:
            out.setnchannels(channels)
            out.setsampwidth(sample_width)
            out.setframerate(rate)
            out.writeframes(slice_frames)
        parts.append(buf.getvalue())
        if end >= total_frames:
            break
        start = max(start + 1, end - overlap_frames)
    return parts or [wav_bytes]


def _join_transcript_chunks(parts: list[str]) -> str:
    """Concatenate chunk transcripts and drop obvious overlap repeats."""
    joined = ""
    for raw in parts:
        part = " ".join((raw or "").split()).strip()
        if not part:
            continue
        if not joined:
            joined = part
            continue
        left = joined.lower().split()
        right = part.lower().split()
        max_overlap = min(12, len(left), len(right))
        overlap = 0
        for size in range(max_overlap, 2, -1):
            if left[-size:] == right[:size]:
                overlap = size
                break
        remainder = part.split()[overlap:]
        if remainder:
            joined = f"{joined} {' '.join(remainder)}".strip()
    return joined


def _azure_recognize_once(
    *,
    url: str,
    key: str,
    locale: str,
    payload: bytes,
    content_type: str,
) -> tuple[str, float | None]:
    import httpx

    response = httpx.post(
        url,
        params={"language": locale, "format": "detailed"},
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": content_type,
            "Accept": "application/json",
        },
        content=payload,
        timeout=90,
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
        status = str(body.get("RecognitionStatus") or "").strip()
        if status and status.lower() not in {"success", "successwithpartialresult"}:
            raise RuntimeError(f"Azure Speech returned no transcript ({status}).")
        raise RuntimeError("Azure Speech returned an empty transcript.")
    duration_ticks = body.get("Duration")
    duration = None
    if duration_ticks is not None:
        try:
            duration = float(duration_ticks) / 10_000_000
        except (TypeError, ValueError):
            duration = None
    return text, duration


def _transcribe_azure_speech(
    entry: AICatalogEntry,
    content: bytes,
    *,
    suffix: str,
    language: str | None,
) -> tuple[str, float | None, str | None, str, str]:
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
    wav_type = "audio/wav; codecs=audio/pcm; samplerate=16000"
    duration = _wav_duration_seconds(payload) if content_type.startswith("audio/wav") else None

    # Long answers: Azure short-audio truncates near ~60s — chunk and stitch.
    if (
        content_type.startswith("audio/wav")
        and duration is not None
        and duration > _AZURE_CHUNK_THRESHOLD
    ):
        chunks = _split_pcm_wav(
            payload,
            chunk_seconds=_AZURE_CHUNK_SECONDS,
            overlap_seconds=_AZURE_CHUNK_OVERLAP,
        )
        logger.info(
            "Azure STT chunking %.1fs audio into %s parts for complete transcript",
            duration,
            len(chunks),
        )
        texts: list[str] = []
        for index, chunk in enumerate(chunks):
            try:
                piece, _ = _azure_recognize_once(
                    url=url,
                    key=key,
                    locale=locale,
                    payload=chunk,
                    content_type=wav_type,
                )
                texts.append(piece)
            except Exception:
                logger.exception("Azure STT chunk %s/%s failed", index + 1, len(chunks))
        text = _join_transcript_chunks(texts)
        if not text:
            raise RuntimeError("Azure Speech returned an empty transcript.")
        return text, duration, language or "en-IN", "azure_speech", entry.model_id or "azure-speech"

    text, recognized_duration = _azure_recognize_once(
        url=url,
        key=key,
        locale=locale,
        payload=payload,
        content_type=content_type,
    )
    return (
        text,
        duration if duration is not None else recognized_duration,
        language or "en-IN",
        "azure_speech",
        entry.model_id or "azure-speech",
    )
