"""Pre-generate and serve Indic Parler-TTS audio for interview questions."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agents.interview_agent.tts_service import (
    TTS_MODEL,
    TTS_VOICE,
    synthesize_speech,
    tts_available,
)
from agents.interview_agent.tts_storage import (
    delete_candidate_audio,
    read_audio_file,
    text_hash,
    write_audio_file,
)
from repositories.interview_question_audio_repository import InterviewQuestionAudioRepository
from repositories.interview_question_set_repository import InterviewQuestionSetRepository

logger = logging.getLogger(__name__)


class InterviewTTSCacheService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.audio_repo = InterviewQuestionAudioRepository(db)
        self.questions_repo = InterviewQuestionSetRepository(db)

    async def audio_ready_map(self, question_set_id: int) -> dict[str, bool]:
        rows = await self.audio_repo.list_for_set(question_set_id)
        return {row.question_id: row.status == "READY" for row in rows}

    async def tts_status(self, question_set_id: int, total_questions: int) -> dict[str, Any]:
        ready_map = await self.audio_ready_map(question_set_id)
        ready_count = sum(1 for ok in ready_map.values() if ok)
        return {
            "tts_ready": ready_count >= total_questions > 0,
            "tts_ready_count": ready_count,
            "tts_total": total_questions,
            "tts_preparing": total_questions > 0 and ready_count < total_questions,
            "audio_ready_by_question": ready_map,
        }

    async def pregenerate_for_question_set(
        self,
        *,
        candidate_id: str,
        question_set_id: int,
        questions: list[dict[str, Any]],
        commit_each: bool = True,
    ) -> dict[str, Any]:
        """Synthesize Indic Parler-TTS audio for every question and persist to disk + DB.

        When commit_each=True, each finished clip is committed so the UI can
        show live progress (1/16, 2/16, ...).
        """
        import asyncio

        if not tts_available():
            return {"ok": False, "error": "Indic Parler-TTS not installed", "ready": 0}

        total = len(questions)
        ready = 0
        errors: list[str] = []

        row = await self.questions_repo.get_by_id(question_set_id)
        if row:
            row.status = "SPEAK_PREPARING"
            await self.db.flush()
            if commit_each:
                await self.db.commit()

        for item in questions:
            qid = str(item.get("id") or "").strip()
            text = str(item.get("question_text") or "").strip()
            if not qid or not text:
                continue
            try:
                result = await asyncio.to_thread(synthesize_speech, text)
                rel = write_audio_file(candidate_id, qid, result["audio_bytes"])
                await self.audio_repo.upsert_ready(
                    candidate_id=candidate_id,
                    question_set_id=question_set_id,
                    question_id=qid,
                    question_text=text,
                    text_hash=text_hash(text),
                    file_path=rel,
                    content_type=str(result.get("content_type") or "audio/wav"),
                    provider=str(result.get("provider") or "indic_parler_tts"),
                    model=str(result.get("model") or TTS_MODEL),
                    voice=str(result.get("voice") or TTS_VOICE),
                    byte_size=len(result["audio_bytes"]),
                )
                ready += 1
                # Keep set status as preparing until the last clip.
                row = await self.questions_repo.get_by_id(question_set_id)
                if row:
                    row.status = "SPEAK_READY" if ready >= total > 0 else "SPEAK_PREPARING"
                await self.db.flush()
                if commit_each:
                    await self.db.commit()
                logger.info(
                    "TTS progress candidate=%s set=%s %s/%s (%s)",
                    candidate_id,
                    question_set_id,
                    ready,
                    total,
                    qid,
                )
            except Exception as exc:
                logger.exception("TTS pre-generate failed for %s/%s", candidate_id, qid)
                errors.append(f"{qid}: {exc}")
                if commit_each:
                    await self.db.rollback()

        row = await self.questions_repo.get_by_id(question_set_id)
        if row:
            if ready >= total > 0:
                row.status = "SPEAK_READY"
            elif ready > 0:
                row.status = "SPEAK_PARTIAL"
            else:
                row.status = "QUESTIONS_GENERATED"
            await self.db.flush()
            if commit_each:
                await self.db.commit()

        return {"ok": not errors, "ready": ready, "total": total, "errors": errors[:5]}

    async def get_cached_audio(
        self,
        *,
        candidate_id: str,
        question_id: str | None = None,
        text: str | None = None,
    ) -> dict[str, Any] | None:
        """Return cached audio bytes if available for question_id (preferred) or text hash."""
        if question_id:
            row = await self.audio_repo.get_ready_for_candidate_question(
                candidate_id=candidate_id, question_id=question_id
            )
            if row:
                data = read_audio_file(row.file_path)
                if data:
                    return {
                        "audio_bytes": data,
                        "content_type": row.content_type or "audio/wav",
                        "provider": row.provider,
                        "model": row.model,
                        "voice": row.voice,
                        "cached": True,
                        "question_id": row.question_id,
                    }

        # Fallback: live synthesize + optionally cache if we know the question.
        if not text:
            return None
        result = synthesize_speech(text)
        result["cached"] = False
        return result

    async def clear_for_candidate(self, candidate_id: str) -> None:
        delete_candidate_audio(candidate_id)
