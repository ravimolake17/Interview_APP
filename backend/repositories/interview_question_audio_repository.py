"""Repository for pre-generated interview question TTS audio."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.interview_question_audio import InterviewQuestionAudio


class InterviewQuestionAudioRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_set(self, question_set_id: int) -> Sequence[InterviewQuestionAudio]:
        result = await self.db.execute(
            select(InterviewQuestionAudio).where(
                InterviewQuestionAudio.question_set_id == question_set_id
            )
        )
        return result.scalars().all()

    async def get_for_question(
        self, *, question_set_id: int, question_id: str
    ) -> InterviewQuestionAudio | None:
        result = await self.db.execute(
            select(InterviewQuestionAudio).where(
                InterviewQuestionAudio.question_set_id == question_set_id,
                InterviewQuestionAudio.question_id == question_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_ready_for_candidate_question(
        self, *, candidate_id: str, question_id: str
    ) -> InterviewQuestionAudio | None:
        result = await self.db.execute(
            select(InterviewQuestionAudio)
            .where(
                InterviewQuestionAudio.candidate_id == candidate_id,
                InterviewQuestionAudio.question_id == question_id,
                InterviewQuestionAudio.status == "READY",
            )
            .order_by(InterviewQuestionAudio.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def delete_for_set(self, question_set_id: int) -> None:
        await self.db.execute(
            delete(InterviewQuestionAudio).where(
                InterviewQuestionAudio.question_set_id == question_set_id
            )
        )

    async def upsert_ready(
        self,
        *,
        candidate_id: str,
        question_set_id: int,
        question_id: str,
        question_text: str,
        text_hash: str,
        file_path: str,
        content_type: str,
        provider: str,
        model: str,
        voice: str,
        byte_size: int,
    ) -> InterviewQuestionAudio:
        existing = await self.get_for_question(
            question_set_id=question_set_id, question_id=question_id
        )
        if existing:
            existing.question_text = question_text
            existing.text_hash = text_hash
            existing.file_path = file_path
            existing.content_type = content_type
            existing.provider = provider
            existing.model = model
            existing.voice = voice
            existing.byte_size = byte_size
            existing.status = "READY"
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        row = InterviewQuestionAudio(
            candidate_id=candidate_id,
            question_set_id=question_set_id,
            question_id=question_id,
            question_text=question_text,
            text_hash=text_hash,
            file_path=file_path,
            content_type=content_type,
            provider=provider,
            model=model,
            voice=voice,
            byte_size=byte_size,
            status="READY",
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row
