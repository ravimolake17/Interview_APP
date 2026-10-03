from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass
class DetectorGate:
    interval_seconds: float
    timeout_seconds: float
    last_run: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    runs: int = 0
    skipped_interval: int = 0
    skipped_inflight: int = 0
    timeouts: int = 0
    errors: int = 0
    last_duration_ms: float = 0.0
    max_duration_ms: float = 0.0

    async def run(self, operation: Callable[[], Awaitable[Any]]) -> Any | None:
        now = time.monotonic()
        if now - self.last_run < self.interval_seconds:
            self.skipped_interval += 1
            return None
        if self.lock.locked():
            self.skipped_inflight += 1
            return None
        async with self.lock:
            self.last_run = time.monotonic()
            started = time.perf_counter()
            try:
                result = await asyncio.wait_for(operation(), timeout=self.timeout_seconds)
                self.runs += 1
                return result
            except TimeoutError:
                self.timeouts += 1
                raise
            except Exception:
                self.errors += 1
                raise
            finally:
                duration = (time.perf_counter() - started) * 1000.0
                self.last_duration_ms = round(duration, 3)
                self.max_duration_ms = round(max(self.max_duration_ms, duration), 3)

    def snapshot(self) -> dict[str, float | int | bool]:
        return {
            "runs": self.runs,
            "skipped_interval": self.skipped_interval,
            "skipped_inflight": self.skipped_inflight,
            "timeouts": self.timeouts,
            "errors": self.errors,
            "last_duration_ms": self.last_duration_ms,
            "max_duration_ms": self.max_duration_ms,
            "in_flight": self.lock.locked(),
        }


class LatestOnlyQueue(Generic[T]):
    """Bounded queue that drops stale work instead of building latency.

    This is suitable for camera frames and analysis windows where a newer item
    supersedes an unprocessed older item. Dropped counts are exposed for admin
    telemetry rather than silently hidden.
    """

    def __init__(self, maxsize: int = 1) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be at least one")
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=maxsize)
        self.dropped = 0

    def put_latest(self, item: T) -> int:
        while self._queue.full():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                self.dropped += 1
            except asyncio.QueueEmpty:
                break
        self._queue.put_nowait(item)
        return self.dropped

    async def get(self) -> T:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()

    @property
    def depth(self) -> int:
        return self._queue.qsize()


class InferenceScheduler:
    def __init__(self) -> None:
        self.gates = {
            "face_detection": DetectorGate(0.75, 5.0),
            "face_verification": DetectorGate(2.0, 8.0),
            "gaze_head": DetectorGate(0.75, 5.0),
            "anti_spoof": DetectorGate(5.0, 8.0),
            "speaker_verification": DetectorGate(3.0, 20.0),
        }
        self.frame_queue: LatestOnlyQueue[Any] = LatestOnlyQueue(maxsize=1)
        self.audio_queue: LatestOnlyQueue[Any] = LatestOnlyQueue(maxsize=2)

    def snapshot(self) -> dict[str, Any]:
        return {
            "gates": {name: gate.snapshot() for name, gate in self.gates.items()},
            "queues": {
                "frames": {"depth": self.frame_queue.depth, "dropped": self.frame_queue.dropped},
                "audio": {"depth": self.audio_queue.depth, "dropped": self.audio_queue.dropped},
            },
        }
