from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from .ai.audio import SpeakerEngine
from .ai.attention import AttentionTemporalTracker
from .ai.face import AntiSpoofEngine, FaceEngine, HeadPoseGazeEngine


@dataclass
class SignalState:
    first_seen: float
    last_seen: float
    count: int


class ConfirmationTracker:
    """Process-local temporal confirmer. The resulting events are persisted in the DB."""

    def __init__(self) -> None:
        self._states: dict[tuple[str, str], SignalState] = {}
        self._lock = threading.Lock()

    def update(
        self,
        session_id: str,
        signal: str,
        active: bool,
        *,
        required_seconds: float,
        required_count: int = 2,
        observed_ms: int | None = None,
    ) -> tuple[bool, int]:
        """Confirm a sustained signal using media time when available.

        Browser/media timestamps are authoritative for detector duration because
        CPU queueing or inference latency must not make a short event look long,
        or a sustained event look short. ``time.monotonic`` remains the fallback
        for callers/tests that do not have a capture timestamp.
        """
        now = float(observed_ms) / 1000.0 if observed_ms is not None else time.monotonic()
        key = (session_id, signal)
        with self._lock:
            if not active:
                self._states.pop(key, None)
                return False, 0
            state = self._states.get(key)
            reset_gap = max(required_seconds * 2, 4.0)
            # Out-of-order capture timestamps must never extend a confirmation
            # window. Start a fresh window instead.
            if state is None or now < state.last_seen or now - state.last_seen > reset_gap:
                state = SignalState(now, now, 1)
            else:
                state.last_seen = now
                state.count += 1
            self._states[key] = state
            elapsed_seconds = max(0.0, state.last_seen - state.first_seen)
            elapsed_ms = int(elapsed_seconds * 1000)
            confirmed = state.count >= required_count and elapsed_seconds >= required_seconds
            if confirmed:
                self._states.pop(key, None)
            return confirmed, elapsed_ms

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            for key in [k for k in self._states if k[0] == session_id]:
                self._states.pop(key, None)


face_engine = FaceEngine()
pose_gaze_engine = HeadPoseGazeEngine()
anti_spoof_engine = AntiSpoofEngine()
speaker_engine = SpeakerEngine()
confirmation_tracker = ConfirmationTracker()
attention_tracker = AttentionTemporalTracker()
