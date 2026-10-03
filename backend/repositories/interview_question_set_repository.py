"""Repository for Agent 4 question sets."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.interview_question_set import InterviewQuestionSet


class InterviewQuestionSetRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_latest(self, candidate_id: str) -> InterviewQuestionSet | None:
        result = await self.db.execute(
            select(InterviewQuestionSet)
            .where(InterviewQuestionSet.candidate_id == candidate_id)
            .order_by(InterviewQuestionSet.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, question_set_id: int) -> InterviewQuestionSet | None:
        result = await self.db.execute(
            select(InterviewQuestionSet).where(InterviewQuestionSet.id == question_set_id)
        )
        return result.scalar_one_or_none()

    async def update_status(self, question_set_id: int, status: str) -> None:
        row = await self.get_by_id(question_set_id)
        if row:
            row.status = status
            await self.db.flush()

    async def create(
        self,
        *,
        candidate_id: str,
        blueprint_id: int | None,
        status: str,
        candidate_level: str | None,
        total_questions: int,
        total_duration_minutes: int | None,
        questions_json: list[dict[str, Any]],
        company_id: int,
    ) -> InterviewQuestionSet:
        row = InterviewQuestionSet(
            candidate_id=candidate_id,
            company_id=company_id,
            blueprint_id=blueprint_id,
            status=status,
            candidate_level=candidate_level,
            total_questions=total_questions,
            total_duration_minutes=total_duration_minutes,
            questions_json=questions_json,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def replace_questions(
        self,
        question_set_id: int,
        *,
        questions_json: list[dict[str, Any]],
        total_questions: int,
        total_duration_minutes: int | None = None,
        status: str | None = None,
    ) -> InterviewQuestionSet | None:
        row = await self.get_by_id(question_set_id)
        if not row:
            return None
        row.questions_json = list(questions_json)
        row.total_questions = total_questions
        if total_duration_minutes is not None:
            row.total_duration_minutes = total_duration_minutes
        if status:
            row.status = status
        await self.db.flush()
        await self.db.refresh(row)
        return row
