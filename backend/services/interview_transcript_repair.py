"""Re-transcribe saved oral answer audio when the stored text looks truncated."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models.candidate import Candidate
from repositories.interview_evaluation_repository import InterviewEvaluationRepository
from services.interview_oral_store import (
    ORAL_KEY,
    oral_turns,
    resolve_answer_audio,
    upsert_oral_turn,
)

logger = logging.getLogger(__name__)

# Spoken English is typically ~2–3 words/sec. Far below that on a long clip
# usually means Azure/Whisper cut the transcript while audio kept going.
_MIN_DURATION_FOR_REPAIR = 20.0
_MIN_WORDS_PER_SECOND = 1.15


def _audio_duration_seconds(path: Path) -> float | None:
    suffix = path.suffix.lower()
    try:
        if suffix == ".wav":
            import wave

            with wave.open(str(path), "rb") as handle:
                rate = handle.getframerate() or 0
                frames = handle.getnframes() or 0
                if rate > 0 and frames > 0:
                    return float(frames) / float(rate)
        # Rough estimate for compressed formats (~16 kbps Opus-ish).
        size = path.stat().st_size
        if size > 0:
            return max(1.0, size / 2000.0)
    except Exception:
        return None
    return None


def looks_truncated(answer_text: str, duration_seconds: float | None) -> bool:
    text = (answer_text or "").strip()
    if not text or duration_seconds is None or duration_seconds < _MIN_DURATION_FOR_REPAIR:
        return False
    words = len(text.split())
    return words < duration_seconds * _MIN_WORDS_PER_SECOND


async def repair_truncated_oral_transcripts(
    db: AsyncSession,
    candidate: Candidate,
    *,
    limit: int = 8,
) -> int:
    """Re-run STT on saved clips when stored text is much shorter than the audio.

    Updates oral snapshot + matching evaluation rows. Safe to call on Agent 6 load.
    """
    from agents.interview_agent.stt_service import transcribe_audio_bytes

    repaired = 0
    turns = oral_turns(candidate)
    for turn in turns:
        if repaired >= limit:
            break
        if turn.get("transcript_repaired"):
            continue
        answer = str(turn.get("answer_text") or "").strip()
        audio_rel = str(turn.get("audio_path") or "").strip()
        path = resolve_answer_audio(audio_rel)
        if path is None:
            continue
        duration = _audio_duration_seconds(path)
        if not looks_truncated(answer, duration):
            continue
        try:
            content = path.read_bytes()
            result = transcribe_audio_bytes(
                content,
                filename=path.name,
                language="en-IN",
            )
            new_text = str(getattr(result, "text", "") or "").strip()
        except Exception:
            logger.exception(
                "Transcript repair failed for candidate=%s question=%s",
                candidate.candidate_id,
                turn.get("question_id"),
            )
            continue
        if not new_text or len(new_text) <= len(answer) + 8:
            # Mark checked so we do not keep retrying the same clip.
            upsert_oral_turn(
                candidate,
                {
                    "question_id": turn.get("question_id"),
                    "question_text": turn.get("question_text"),
                    "answer_text": answer,
                    "audio_path": audio_rel,
                    "transcript_repaired": True,
                },
            )
            continue

        qid = str(turn.get("question_id") or "").strip()
        upsert_oral_turn(
            candidate,
            {
                "question_id": qid,
                "question_text": turn.get("question_text"),
                "answer_text": new_text,
                "audio_path": audio_rel,
                "transcript_repaired": True,
            },
        )
        if qid:
            rows = await InterviewEvaluationRepository(db).list_for_candidate(
                candidate.candidate_id, limit=100
            )
            for row in rows:
                if str(row.question_id or "").strip() != qid:
                    continue
                if len(str(row.answer_text or "").strip()) >= len(new_text):
                    continue
                row.answer_text = new_text
                payload = dict(row.evaluation_json or {}) if isinstance(row.evaluation_json, dict) else {}
                payload["answer_text"] = new_text
                payload["transcript_repaired"] = True
                row.evaluation_json = payload
                flag_modified(row, "evaluation_json")
        repaired += 1
        logger.info(
            "Repaired truncated transcript for %s / %s (%s → %s chars)",
            candidate.candidate_id,
            qid or "?",
            len(answer),
            len(new_text),
        )

    if repaired:
        # Ensure snapshot write is visible to callers reading oral_turns next.
        snap = dict(candidate.evaluation_snapshot or {})
        oral = dict(snap.get(ORAL_KEY) or {})
        snap[ORAL_KEY] = oral
        candidate.evaluation_snapshot = snap
        flag_modified(candidate, "evaluation_snapshot")
        await db.flush()
    return repaired
