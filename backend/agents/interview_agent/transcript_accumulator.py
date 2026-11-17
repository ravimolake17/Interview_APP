"""Ordered final-segment transcript accumulator for streaming STT.

Partials stay separate from finals. Finals are ordered, de-duplicated against
the previous segment, and never persist empty/NoMatch text as answers.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def _normalize_for_dedupe(text: str) -> str:
    return " ".join((text or "").lower().split())


@dataclass
class TranscriptAccumulator:
    """Collect Azure continuous-recognition finals without mixing in partials."""

    _segments: list[str] = field(default_factory=list)
    _partial: str = ""
    _first_final_ms: float | None = None
    _t0_monotonic: float | None = None

    def set_clock_origin(self, t0: float) -> None:
        self._t0_monotonic = t0

    def set_partial(self, text: str) -> None:
        cleaned = " ".join((text or "").split()).strip()
        self._partial = cleaned

    def clear_partial(self) -> None:
        self._partial = ""

    def add_final_segment(self, text: str, *, now_monotonic: float | None = None) -> bool:
        """Append a finalized phrase. Returns True when accepted."""
        cleaned = " ".join((text or "").split()).strip()
        if not cleaned:
            return False
        if self._segments:
            prev = self._segments[-1]
            if prev == cleaned or _normalize_for_dedupe(prev) == _normalize_for_dedupe(cleaned):
                self._partial = ""
                return False
            # Drop exact overlap when Azure re-emits trailing words of the prior phrase.
            prev_tokens = prev.split()
            next_tokens = cleaned.split()
            max_overlap = min(8, len(prev_tokens), len(next_tokens))
            for size in range(max_overlap, 2, -1):
                if prev_tokens[-size:] == next_tokens[:size]:
                    cleaned = " ".join(next_tokens[size:]).strip()
                    break
            if not cleaned:
                self._partial = ""
                return False
        self._segments.append(cleaned)
        self._partial = ""
        if self._first_final_ms is None and now_monotonic is not None and self._t0_monotonic is not None:
            self._first_final_ms = max(0.0, (now_monotonic - self._t0_monotonic) * 1000.0)
        return True

    @property
    def partial(self) -> str:
        return self._partial

    @property
    def segments(self) -> list[str]:
        return list(self._segments)

    @property
    def segment_count(self) -> int:
        return len(self._segments)

    @property
    def first_final_ms(self) -> float | None:
        return self._first_final_ms

    def display_text(self) -> str:
        """UI preview: finals + current partial (partial never treated as answer)."""
        parts = list(self._segments)
        if self._partial:
            parts.append(self._partial)
        return " ".join(parts).strip()

    def finalized_text(self, *, include_trailing_partial_if_empty: bool = True) -> str:
        """Authoritative answer text — finals only unless nothing finalized yet."""
        joined = " ".join(self._segments).strip()
        if joined:
            return joined
        if include_trailing_partial_if_empty and self._partial:
            return self._partial
        return ""
