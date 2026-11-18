"""Azure Speech SDK streaming TTS (MP3 chunks via AudioDataStream).

Uses SpeechSynthesizer.synthesizing / AudioDataStream so the first playable
bytes can leave the server before synthesis completes. Batch /ai/speak remains
the fallback when streaming is disabled or the SDK/key is unavailable.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

logger = logging.getLogger(__name__)

STREAM_FORMAT = "audio/mpeg"
CHUNK_SIZE = 4096


def streaming_tts_available() -> bool:
    try:
        import azure.cognitiveservices.speech  # noqa: F401
    except ImportError:
        return False
    from agents.screening_agent.config import settings

    return bool(getattr(settings, "AZURE_SPEECH_KEY", None))


def _azure_voice(voice: str | None, entry=None, language: str | None = None) -> str:
    from agents.interview_agent.tts_service import _neural_for_entry, _normalize_voice

    return _neural_for_entry(entry, _normalize_voice(voice), language=language)


def synthesize_azure_mp3_stream(
    text: str,
    *,
    voice: str | None = "female",
    language: str | None = None,
) -> Iterator[bytes]:
    """Yield MP3 chunks as Azure produces them (or as soon as the stream is readable)."""
    import azure.cognitiveservices.speech as speechsdk

    from agents.interview_agent.interview_language import tts_voice_and_xml_lang
    from agents.interview_agent.tts_service import _humanize_script
    from agents.screening_agent.config import settings
    from agents.shared.azure_concurrency import azure_slot
    from agents.shared.latency_trace import record_ms, record_unavailable, record_value
    from agents.shared.model_catalog import ordered_targets

    cleaned = _humanize_script(text)
    if not cleaned:
        raise ValueError("Empty text for TTS.")

    key = getattr(settings, "AZURE_SPEECH_KEY", None)
    if not key:
        raise RuntimeError("Azure Speech key is not configured.")

    region = (getattr(settings, "AZURE_SPEECH_REGION", None) or "eastus2").strip()
    endpoint = (getattr(settings, "AZURE_SPEECH_TTS_ENDPOINT", None) or "").strip().rstrip("/")
    entry = None
    for item in ordered_targets("tts", language=language) or []:
        if getattr(item, "provider", "") == "azure":
            entry = item
            region = (item.region or region).strip()
            if item.endpoint:
                endpoint = str(item.endpoint).rstrip("/")
            break

    with azure_slot("tts"):
        if endpoint:
            speech_config = speechsdk.SpeechConfig(subscription=key, endpoint=endpoint)
        else:
            speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio24Khz160KBitRateMonoMp3
        )
        neural = _azure_voice(voice, entry, language=language)
        xml_lang = tts_voice_and_xml_lang(language, voice)[1]
        from agents.interview_agent.tts_service import build_interview_ssml

        ssml = build_interview_ssml(cleaned, voice_name=neural, xml_lang=xml_lang)

        # audio_config=None → result stream only (no local speaker device).
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
        first_chunk_ms: float | None = None
        t0 = time.perf_counter()
        result = synthesizer.start_speaking_ssml_async(ssml).get()
        if result.reason == speechsdk.ResultReason.Canceled:
            details = speechsdk.SpeechSynthesisCancellationDetails.from_result(result)
            raise RuntimeError(f"Azure TTS canceled: {details.reason} {details.error_details}")

        stream = speechsdk.AudioDataStream(result)
        # Wait until stream is readable (synthesis may still be running).
        deadline = time.time() + 60
        while stream.status == speechsdk.StreamStatus.NoData and time.time() < deadline:
            time.sleep(0.01)
        if stream.status not in {
            speechsdk.StreamStatus.AllData,
            speechsdk.StreamStatus.PartialData,
        } and stream.status != speechsdk.StreamStatus.NoData:
            # Some SDK builds expose status differently — continue to read_data anyway.
            pass

        total = 0
        while True:
            # The SDK fills the buffer in place and rejects bytearray; allocate per read.
            buf = bytes(CHUNK_SIZE)
            filled = int(stream.read_data(buf) or 0)
            if not filled:
                if stream.status == speechsdk.StreamStatus.AllData:
                    break
                if stream.status == speechsdk.StreamStatus.Canceled:
                    raise RuntimeError("Azure TTS stream canceled while reading")
                time.sleep(0.02)
                buf = bytes(CHUNK_SIZE)
                filled = int(stream.read_data(buf) or 0)
                if not filled:
                    if stream.status in {speechsdk.StreamStatus.AllData, speechsdk.StreamStatus.NoData}:
                        break
                    if time.perf_counter() - t0 > 60:
                        break
                    continue
            chunk = bytes(buf[:filled])
            total += filled
            if first_chunk_ms is None:
                first_chunk_ms = (time.perf_counter() - t0) * 1000.0
                record_ms("tts_time_to_first_audio_ms", first_chunk_ms)
            yield chunk

        elapsed = (time.perf_counter() - t0) * 1000.0
        record_ms("tts_synthesis_ms", elapsed)
        record_value("tts_audio_bytes", total)
        record_value("tts_provider", "azure_speech_tts_stream")
        record_value("tts_cache_hit", False)
        if first_chunk_ms is None:
            record_unavailable("tts_time_to_first_audio_ms")
        logger.info(
            "TTS stream done voice=%s bytes=%s ttfa_ms=%s total_ms=%.0f",
            neural,
            total,
            None if first_chunk_ms is None else round(first_chunk_ms, 1),
            elapsed,
        )


def stream_metrics_headers(extra: dict[str, Any] | None = None) -> dict[str, str]:
    headers = {
        "Content-Type": STREAM_FORMAT,
        "X-TTS-Stream": "1",
        "X-TTS-Format": "mp3",
        "Cache-Control": "no-store",
    }
    if extra:
        for key, value in extra.items():
            if value is None:
                continue
            headers[str(key)] = str(value)
    return headers
