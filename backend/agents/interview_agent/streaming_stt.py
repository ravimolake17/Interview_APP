"""Azure Speech SDK continuous recognition for interview WebSocket STT.

PushAudioInputStream requires raw PCM (signed 16-bit, mono, 16 kHz).
WebM/Opus from MediaRecorder is NOT accepted here — the browser must send PCM.

One SpeechRecognizer per answer turn (not per frame). Recognition runs while
the candidate speaks; finals are accumulated separately from partials.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any

from agents.interview_agent.transcript_accumulator import TranscriptAccumulator

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
CHANNELS = 1
BITS_PER_SAMPLE = 16

EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


def interview_stt_mode() -> str:
    env = (os.getenv("INTERVIEW_STT_MODE") or "").strip().lower()
    if env in {"batch", "streaming"}:
        return env
    try:
        from core.config import get_settings

        mode = str(getattr(get_settings(), "interview_stt_mode", "batch") or "batch").strip().lower()
        if mode in {"batch", "streaming"}:
            return mode
    except Exception:
        pass
    return "batch"


def _resolve_azure_speech_key() -> str | None:
    """Speech key may live in env or be hydrated from SuperAdmin ai_secrets."""
    import os

    env_key = (os.getenv("AZURE_SPEECH_KEY") or "").strip()
    if env_key:
        return env_key
    try:
        from agents.screening_agent.config import settings

        key = getattr(settings, "AZURE_SPEECH_KEY", None)
        if key:
            return str(key).strip() or None
    except Exception:
        pass
    return None


def streaming_stt_available() -> bool:
    try:
        import azure.cognitiveservices.speech  # noqa: F401
    except ImportError:
        return False
    return bool(_resolve_azure_speech_key())


def _segmentation_silence_ms() -> int:
    try:
        from core.config import get_settings

        value = int(getattr(get_settings(), "stt_stream_segmentation_silence_ms", 1200) or 1200)
    except Exception:
        value = 1200
    return max(100, min(5000, value))


def _initial_silence_ms() -> int:
    try:
        from core.config import get_settings

        value = int(getattr(get_settings(), "stt_stream_initial_silence_ms", 8000) or 8000)
    except Exception:
        value = 8000
    return max(1000, min(30_000, value))


def end_silence_ms() -> int:
    env = (os.getenv("INTERVIEW_STT_END_SILENCE_MS") or "").strip()
    if env.isdigit():
        return max(800, min(10_000, int(env)))
    try:
        from core.config import get_settings

        value = int(getattr(get_settings(), "interview_stt_end_silence_ms", 2500) or 2500)
    except Exception:
        value = 2500
    return max(800, min(10_000, value))


def finalization_timeout_seconds() -> float:
    env = (os.getenv("INTERVIEW_STT_FINALIZATION_TIMEOUT_MS") or "").strip()
    if env.isdigit():
        return max(0.5, min(20.0, int(env) / 1000.0))
    try:
        from core.config import get_settings

        value = int(getattr(get_settings(), "interview_stt_finalization_timeout_ms", 5000) or 5000)
    except Exception:
        value = 5000
    return max(0.5, min(20.0, value / 1000.0))


class StreamingSttSession:
    """One Azure SpeechRecognizer + PushAudioInputStream per interview audio turn."""

    def __init__(
        self,
        *,
        session_id: str,
        candidate_id: str,
        loop: asyncio.AbstractEventLoop,
        on_event: EventCallback,
        language: str = "en-IN",
    ) -> None:
        self.session_id = session_id
        self.candidate_id = candidate_id
        self._loop = loop
        self._on_event = on_event
        self.language = language or "en-IN"
        self._lock = threading.Lock()
        self._closed = False
        self._started = False
        self._stream = None
        self._recognizer = None
        self._accumulator = TranscriptAccumulator()
        self._bytes_written = 0
        self._t0 = time.perf_counter()
        self._accumulator.set_clock_origin(self._t0)
        self._first_partial_ms: float | None = None
        self._first_audio_write_ms: float | None = None
        self._recognition_started_ms: float | None = None
        self._speech_end_ms: float | None = None
        self._final_ready = threading.Event()
        self._stop_requested = False
        self._error: str | None = None
        self._slot_cm = None

    def _emit(self, payload: dict[str, Any]) -> None:
        if self._closed and payload.get("type") not in {"final", "error"}:
            return

        def _run() -> None:
            try:
                result = self._on_event(payload)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception:
                logger.exception("Streaming STT event callback failed (%s)", payload.get("type"))

        self._loop.call_soon_threadsafe(_run)

    def start(self) -> None:
        import azure.cognitiveservices.speech as speechsdk

        from agents.screening_agent.config import settings
        from agents.shared.azure_concurrency import azure_slot
        from agents.shared.model_catalog import ordered_targets

        if self._started:
            return
        key = _resolve_azure_speech_key() or getattr(settings, "AZURE_SPEECH_KEY", None)
        if not key:
            raise RuntimeError("Speech recognition is not configured.")

        region = (getattr(settings, "AZURE_SPEECH_REGION", None) or "eastus2").strip()
        endpoint = (getattr(settings, "AZURE_SPEECH_STT_ENDPOINT", None) or "").strip().rstrip("/")
        targets = ordered_targets("stt")
        for entry in targets:
            if getattr(entry, "provider", "") == "azure":
                region = (entry.region or region).strip()
                if entry.endpoint:
                    endpoint = str(entry.endpoint).rstrip("/")
                break

        # Bound concurrent Azure STT sessions (shared with batch REST).
        self._slot_cm = azure_slot("stt")
        self._slot_cm.__enter__()

        try:
            if endpoint:
                speech_config = speechsdk.SpeechConfig(subscription=key, endpoint=endpoint)
            else:
                speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
            speech_config.speech_recognition_language = self.language

            speech_config.set_property(
                speechsdk.PropertyId.Speech_SegmentationSilenceTimeoutMs,
                str(_segmentation_silence_ms()),
            )
            speech_config.set_property(
                speechsdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs,
                str(_initial_silence_ms()),
            )

            fmt = speechsdk.audio.AudioStreamFormat(
                samples_per_second=SAMPLE_RATE,
                bits_per_sample=BITS_PER_SAMPLE,
                channels=CHANNELS,
            )
            self._stream = speechsdk.audio.PushAudioInputStream(stream_format=fmt)
            audio_config = speechsdk.audio.AudioConfig(stream=self._stream)
            self._recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config,
            )
        except Exception:
            self._release_slot()
            raise

        def recognizing(evt) -> None:
            text = str(getattr(evt.result, "text", "") or "").strip()
            if not text:
                return
            now = time.perf_counter()
            if self._first_partial_ms is None:
                self._first_partial_ms = (now - self._t0) * 1000.0
            self._accumulator.set_partial(text)
            self._emit(
                {
                    "type": "partial",
                    "text": text,
                    "display_text": self._accumulator.display_text(),
                    "partial_latency_ms": round((now - self._t0) * 1000.0, 3),
                }
            )

        def recognized(evt) -> None:
            result = evt.result
            reason = getattr(result, "reason", None)
            import azure.cognitiveservices.speech as speechsdk

            now = time.perf_counter()
            if reason == speechsdk.ResultReason.RecognizedSpeech:
                text = str(getattr(result, "text", "") or "").strip()
                accepted = self._accumulator.add_final_segment(text, now_monotonic=now)
                if accepted:
                    self._emit(
                        {
                            "type": "segment",
                            "text": text,
                            "display_text": self._accumulator.display_text(),
                            "segment_count": self._accumulator.segment_count,
                        }
                    )
            elif reason == speechsdk.ResultReason.NoMatch:
                # Never persist NoMatch as a final answer segment.
                self._accumulator.clear_partial()
                if self._stop_requested:
                    self._final_ready.set()

        def canceled(evt) -> None:
            import azure.cognitiveservices.speech as speechsdk

            details = getattr(evt, "cancellation_details", None) or getattr(evt.result, "cancellation_details", None)
            reason = getattr(details, "reason", None) if details else None
            if reason == speechsdk.CancellationReason.Error:
                err = str(getattr(details, "error_details", "") or "Speech recognition canceled")[:240]
                self._error = err
                logger.warning(
                    "streaming_stt_canceled session=%s candidate=%s reason=%s",
                    self.session_id,
                    self.candidate_id,
                    err[:120],
                )
                self._emit(
                    {
                        "type": "error",
                        "code": "azure_canceled",
                        "message": "Speech recognition was interrupted. We will try again from your recording.",
                    }
                )
            self._final_ready.set()

        def session_stopped(_evt) -> None:
            self._final_ready.set()

        # Service-side VAD: lets the client end the turn on Azure's speech boundary
        # instead of relying only on browser mic levels.
        def speech_start_detected(_evt) -> None:
            self._emit({"type": "vad", "state": "start"})

        def speech_end_detected(_evt) -> None:
            self._emit({"type": "vad", "state": "end"})

        self._recognizer.recognizing.connect(recognizing)
        self._recognizer.recognized.connect(recognized)
        self._recognizer.canceled.connect(canceled)
        self._recognizer.session_stopped.connect(session_stopped)
        self._recognizer.speech_start_detected.connect(speech_start_detected)
        self._recognizer.speech_end_detected.connect(speech_end_detected)
        self._recognizer.start_continuous_recognition()
        self._started = True
        self._recognition_started_ms = (time.perf_counter() - self._t0) * 1000.0
        self._emit(
            {
                "type": "ready",
                "sample_rate": SAMPLE_RATE,
                "channels": CHANNELS,
                "format": "pcm_s16le",
                "segmentation_silence_ms": _segmentation_silence_ms(),
                "end_silence_ms": end_silence_ms(),
                "finalization_timeout_ms": int(finalization_timeout_seconds() * 1000),
            }
        )

    def write(self, pcm: bytes | bytearray | memoryview) -> None:
        if self._closed or not self._stream or not pcm:
            return
        # Azure PushAudioInputStream.write requires strict bytes (not bytearray/memoryview).
        data = pcm if isinstance(pcm, bytes) else bytes(pcm)
        if not data:
            return
        with self._lock:
            if self._closed or not self._stream:
                return
            if self._first_audio_write_ms is None:
                self._first_audio_write_ms = (time.perf_counter() - self._t0) * 1000.0
            try:
                self._stream.write(data)
            except Exception:
                logger.exception(
                    "streaming_stt_write_failed session=%s candidate=%s bytes=%s",
                    self.session_id,
                    self.candidate_id,
                    len(data),
                )
                raise
            self._bytes_written += len(data)

    def mark_speech_end(self) -> None:
        if self._speech_end_ms is None:
            self._speech_end_ms = (time.perf_counter() - self._t0) * 1000.0
            self._emit({"type": "speech_end", "speech_end_ms": round(self._speech_end_ms, 3)})

    def stop(self, *, wait_seconds: float | None = None) -> dict[str, Any]:
        """Close the push stream, stop recognition, return assembled transcript metrics."""
        wait = finalization_timeout_seconds() if wait_seconds is None else max(0.5, wait_seconds)
        self._stop_requested = True
        self.mark_speech_end()
        with self._lock:
            stream = self._stream
            recognizer = self._recognizer
            self._stream = None
        if stream is not None:
            try:
                stream.close()
            except Exception:
                logger.debug("Push stream close failed", exc_info=True)
        if recognizer is not None:
            try:
                recognizer.stop_continuous_recognition()
            except Exception:
                logger.debug("stop_continuous_recognition failed", exc_info=True)
        self._final_ready.wait(timeout=wait)
        raw = self._accumulator.finalized_text(include_trailing_partial_if_empty=True)
        elapsed = (time.perf_counter() - self._t0) * 1000.0
        speech_to_final = None
        if self._speech_end_ms is not None:
            speech_to_final = max(0.0, elapsed - self._speech_end_ms)
        self._closed = True
        self._release_slot()
        return {
            "raw_text": raw,
            "error": self._error,
            "metrics": {
                "stt_stream_ms": round(elapsed, 3),
                "stt_audio_bytes": self._bytes_written,
                "stt_audio_duration_seconds": round(self._bytes_written / (SAMPLE_RATE * 2), 3)
                if self._bytes_written
                else None,
                "partial_first_ms": round(self._first_partial_ms, 3) if self._first_partial_ms is not None else None,
                "first_final_segment_ms": round(self._accumulator.first_final_ms, 3)
                if self._accumulator.first_final_ms is not None
                else None,
                "first_audio_write_ms": round(self._first_audio_write_ms, 3)
                if self._first_audio_write_ms is not None
                else None,
                "recognition_started_ms": round(self._recognition_started_ms, 3)
                if self._recognition_started_ms is not None
                else None,
                "speech_end_to_final_ms": round(speech_to_final, 3) if speech_to_final is not None else None,
                "segment_count": self._accumulator.segment_count,
                "finalization_wait_seconds": wait,
            },
        }

    def _release_slot(self) -> None:
        cm = self._slot_cm
        self._slot_cm = None
        if cm is None:
            return
        try:
            cm.__exit__(None, None, None)
        except Exception:
            logger.debug("Azure STT slot release failed", exc_info=True)

    def close(self) -> None:
        if self._closed and self._stream is None:
            self._release_slot()
            return
        try:
            self.stop(wait_seconds=1.0)
        except Exception:
            logger.debug("Streaming STT close failed", exc_info=True)
            self._release_slot()
        self._closed = True
        self._recognizer = None
