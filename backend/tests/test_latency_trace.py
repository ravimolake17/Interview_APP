"""Unit tests for interview latency instrumentation helpers."""

from __future__ import annotations

import json
import logging

from agents.shared.latency_trace import (
    HEADER_TURN_ID,
    LatencyTurn,
    get_current_turn,
    latency_turn,
    record_ms,
    record_unavailable,
)


def test_latency_turn_uses_monotonic_spans(caplog):
    with caplog.at_level(logging.INFO, logger="interview.latency"):
        with latency_turn(session_id="sess-1", phase="transcribe") as turn:
            assert get_current_turn() is turn
            with turn.span("stt_ms"):
                pass
            turn.set_ms("audio_upload_ms", 12.5)
            turn.mark_unavailable("llm_time_to_first_token_ms")
            assert turn.metrics["audio_upload_ms"] == 12.5
            assert turn.metrics["stt_ms"] is not None
            assert turn.metrics["stt_ms"] >= 0
            assert "llm_time_to_first_token_ms" in turn.unavailable
            headers = turn.response_headers()
            assert HEADER_TURN_ID in headers
            assert turn.turn_id == headers[HEADER_TURN_ID]

    assert get_current_turn() is None
    assert any("interview_latency" in record.message for record in caplog.records)
    payload = json.loads(next(r.message for r in caplog.records if "interview_latency" in r.message))
    assert payload["event"] == "interview_latency"
    assert payload["session_id"] == "sess-1"
    assert "text" not in payload
    assert "audio" not in payload.get("metrics", {})


def test_record_helpers_noop_without_turn():
    record_ms("stt_ms", 1.0)
    record_unavailable("foo")
    assert get_current_turn() is None


def test_merge_client_spans():
    turn = LatencyTurn(turn_id="abc12345", session_id="s1", phase="client")
    turn.merge_client_spans({"silence_wait_ms": 2401.2, "bad": "x", "audio_upload_ms": None})
    assert turn.metrics["silence_wait_ms"] == 2401.2
    assert turn.metrics["audio_upload_ms"] is None
    assert "bad" not in turn.metrics
