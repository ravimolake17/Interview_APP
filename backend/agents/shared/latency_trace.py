"""Production interview-turn latency instrumentation (measure only).

Uses monotonic clocks (time.perf_counter) for durations. Never logs API keys,
candidate PII, transcript text, or raw audio. Optional fields that cannot be
observed on the current non-streaming path are recorded as null with
``unavailable_metrics``.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

logger = logging.getLogger("interview.latency")

HEADER_TURN_ID = "X-Interview-Turn-Id"
HEADER_LATENCY = "X-Interview-Latency"

# Metrics that the current architecture cannot observe (non-streaming LLM/TTS).
ALWAYS_UNAVAILABLE = (
    "llm_time_to_first_token_ms",  # chat completions are non-streaming
    "tts_time_to_first_audio_ms",  # Azure TTS REST returns full body
)

_current: ContextVar["LatencyTurn | None"] = ContextVar("interview_latency_turn", default=None)


def new_turn_id() -> str:
    return uuid.uuid4().hex


def get_current_turn() -> "LatencyTurn | None":
    return _current.get()


def bind_turn(turn: "LatencyTurn | None"):
    """Bind turn into the current context; returns token for reset."""
    return _current.set(turn)


def reset_turn(token) -> None:
    _current.reset(token)


class LatencyTurn:
    """Accumulates monotonic spans and scalar metrics for one oral turn."""

    def __init__(
        self,
        *,
        turn_id: str | None = None,
        session_id: str | None = None,
        phase: str | None = None,
    ) -> None:
        self.turn_id = (turn_id or "").strip() or new_turn_id()
        self.session_id = (session_id or "").strip() or None
        self.phase = phase
        self._t0 = time.perf_counter()
        self._marks: dict[str, float] = {"turn_start": self._t0}
        self.metrics: dict[str, Any] = {}
        self.unavailable: list[str] = list(ALWAYS_UNAVAILABLE)
        self.events: list[str] = []
        self.errors: list[str] = []

    def mark(self, name: str) -> float:
        now = time.perf_counter()
        self._marks[name] = now
        self.events.append(name)
        return now

    def since(self, mark_name: str) -> float | None:
        start = self._marks.get(mark_name)
        if start is None:
            return None
        return round((time.perf_counter() - start) * 1000.0, 3)

    def set_ms(self, key: str, value_ms: float | None) -> None:
        if value_ms is None:
            self.mark_unavailable(key)
            return
        self.metrics[key] = round(float(value_ms), 3)

    def set_value(self, key: str, value: Any) -> None:
        if value is None:
            self.mark_unavailable(key)
            return
        self.metrics[key] = value

    def mark_unavailable(self, key: str) -> None:
        if key not in self.unavailable:
            self.unavailable.append(key)
        # Explicit null so dashboards can distinguish missing vs zero.
        if key not in self.metrics:
            self.metrics[key] = None

    def note_error(self, code: str) -> None:
        if code and code not in self.errors:
            self.errors.append(code[:120])

    @contextmanager
    def span(self, metric_key: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.set_ms(metric_key, (time.perf_counter() - start) * 1000.0)

    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self._t0) * 1000.0, 3)

    def merge_client_spans(self, spans: dict[str, Any] | None) -> None:
        """Accept client-measured ms values (already monotonic on the browser)."""
        if not isinstance(spans, dict):
            return
        for key, value in spans.items():
            if value is None:
                self.mark_unavailable(str(key))
                continue
            try:
                self.metrics[str(key)] = round(float(value), 3)
            except (TypeError, ValueError):
                continue

    def payload(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "event": "interview_latency",
            "turn_id": self.turn_id,
            "session_id": self.session_id,
            "phase": self.phase,
            "elapsed_ms": self.elapsed_ms(),
            "metrics": dict(self.metrics),
            "unavailable_metrics": list(self.unavailable),
            "events": list(self.events),
        }
        if self.errors:
            body["errors"] = list(self.errors)
        return body

    def emit(self, *, level: int = logging.INFO) -> None:
        logger.log(level, "%s", json.dumps(self.payload(), separators=(",", ":"), default=str))

    def response_headers(self) -> dict[str, str]:
        compact = {
            "turn_id": self.turn_id,
            "phase": self.phase,
            "metrics": self.metrics,
            "unavailable_metrics": self.unavailable,
        }
        return {
            HEADER_TURN_ID: self.turn_id,
            HEADER_LATENCY: json.dumps(compact, separators=(",", ":"), default=str),
        }


@contextmanager
def latency_turn(
    *,
    turn_id: str | None = None,
    session_id: str | None = None,
    phase: str | None = None,
    emit_on_exit: bool = True,
) -> Iterator[LatencyTurn]:
    turn = LatencyTurn(turn_id=turn_id, session_id=session_id, phase=phase)
    token = bind_turn(turn)
    try:
        yield turn
    except Exception as exc:
        turn.note_error(type(exc).__name__)
        raise
    finally:
        if emit_on_exit:
            try:
                turn.emit()
            except Exception:
                logger.exception("Failed to emit interview latency log")
        reset_turn(token)


def record_ms(key: str, value_ms: float | None) -> None:
    turn = get_current_turn()
    if turn is not None:
        turn.set_ms(key, value_ms)


def record_value(key: str, value: Any) -> None:
    turn = get_current_turn()
    if turn is not None:
        turn.set_value(key, value)


def record_unavailable(key: str) -> None:
    turn = get_current_turn()
    if turn is not None:
        turn.mark_unavailable(key)


def record_event(name: str) -> None:
    turn = get_current_turn()
    if turn is not None:
        turn.mark(name)


@contextmanager
def record_span(metric_key: str) -> Iterator[None]:
    turn = get_current_turn()
    if turn is None:
        yield
        return
    with turn.span(metric_key):
        yield
