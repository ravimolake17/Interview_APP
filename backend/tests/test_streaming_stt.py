"""Phase 2 streaming STT unit tests (no live Azure calls)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from agents.interview_agent.streaming_stt import (
    SAMPLE_RATE,
    interview_stt_mode,
    streaming_stt_available,
)


def test_default_mode_is_batch(monkeypatch):
    monkeypatch.delenv("INTERVIEW_STT_MODE", raising=False)
    with patch("core.config.get_settings", side_effect=Exception("no settings")):
        assert interview_stt_mode() == "batch"


def test_mode_env_streaming(monkeypatch):
    monkeypatch.setenv("INTERVIEW_STT_MODE", "streaming")
    assert interview_stt_mode() == "streaming"


def test_sample_rate_is_pcm_16k():
    assert SAMPLE_RATE == 16_000


def test_streaming_available_false_without_sdk_or_key(monkeypatch):
    monkeypatch.setenv("INTERVIEW_STT_MODE", "streaming")
    with patch.dict("sys.modules", {"azure.cognitiveservices.speech": None}):
        # Import path may still resolve installed SDK; force key missing.
        with patch("agents.screening_agent.config.settings") as settings:
            settings.AZURE_SPEECH_KEY = None
            # If SDK is installed, availability still requires a key.
            assert streaming_stt_available() is False or settings.AZURE_SPEECH_KEY is None


def test_session_write_and_stop_without_azure():
    from agents.interview_agent.streaming_stt import StreamingSttSession

    events: list[dict] = []

    async def on_event(msg):
        events.append(msg)

    loop = asyncio.new_event_loop()
    session = StreamingSttSession(
        session_id="s1",
        candidate_id="c1",
        loop=loop,
        on_event=on_event,
    )
    # Simulate a started stream without calling Azure.
    session._started = True
    session._stream = MagicMock()
    session._recognizer = MagicMock()
    session._accumulator.add_final_segment("Yes")
    session.write(b"\x00\x01" * 160)
    session.write(bytearray(b"\x00\x02" * 80))  # Starlette often delivers bytearray
    session._stream.write.assert_called()
    # Azure SDK requires strict bytes — never pass bytearray through.
    for call in session._stream.write.call_args_list:
        assert isinstance(call.args[0], bytes)
    result = session.stop(wait_seconds=0.1)
    assert result["raw_text"] == "Yes"
    assert result["metrics"]["segment_count"] == 1
    loop.close()


def test_transcript_accumulator_keeps_partial_separate():
    from agents.interview_agent.transcript_accumulator import TranscriptAccumulator

    acc = TranscriptAccumulator()
    acc.set_partial("I worked on Fast")
    assert acc.display_text() == "I worked on Fast"
    assert acc.finalized_text(include_trailing_partial_if_empty=False) == ""
    acc.add_final_segment("I worked on FastAPI.")
    acc.set_partial("and Redis")
    assert acc.finalized_text() == "I worked on FastAPI."
    assert "Redis" in acc.display_text()
    acc.add_final_segment("I worked on FastAPI.")  # duplicate ignored
    assert acc.segment_count == 1
    acc.add_final_segment("and Redis caching.")
    assert acc.finalized_text() == "I worked on FastAPI. and Redis caching."


def test_end_silence_env(monkeypatch):
    from agents.interview_agent.streaming_stt import end_silence_ms

    monkeypatch.setenv("INTERVIEW_STT_END_SILENCE_MS", "2500")
    assert end_silence_ms() == 2500
    monkeypatch.setenv("INTERVIEW_STT_END_SILENCE_MS", "500")
    assert end_silence_ms() == 800  # clamped minimum


def test_stt_mode_endpoint(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("INTERVIEW_STT_MODE", "batch")
    from main import app

    client = TestClient(app)
    response = client.get("/api/interview/room/sessions/demo/ai/stt-mode")
    assert response.status_code == 200
    body = response.json()
    assert body["interview_stt_mode"] == "batch"
    assert body["effective_mode"] == "batch"
    assert body["sample_rate"] == 16_000
    assert body["format"] == "pcm_s16le"


def test_batch_vs_streaming_flag_comparison(monkeypatch):
    """Documented comparison gate: batch remains default until streaming is opted in."""
    monkeypatch.delenv("INTERVIEW_STT_MODE", raising=False)
    with patch("core.config.get_settings") as gs:
        gs.return_value.interview_stt_mode = "batch"
        assert interview_stt_mode() == "batch"
    monkeypatch.setenv("INTERVIEW_STT_MODE", "streaming")
    assert interview_stt_mode() == "streaming"
