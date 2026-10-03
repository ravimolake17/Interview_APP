"""Repository for Agent 6 interview evaluations."""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.interview_evaluation import InterviewEvaluation


class InterviewEvaluationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        candidate_id: str,
        question_id: str | None,
        question_text: str,
        answer_text: str,
        score: float,
        verdict: str,
        evaluation_json: dict[str, Any],
        model: str | None = None,
        company_id: int,
    ) -> InterviewEvaluation:
        row = InterviewEvaluation(
            candidate_id=candidate_id,
            company_id=company_id,
            question_id=question_id,
            question_text=question_text,
            answer_text=answer_text,
            score=score,
            verdict=verdict,
            evaluation_json=evaluation_json,
            model=model,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def list_for_candidate(
        self, candidate_id: str, *, limit: int = 50
    ) -> Sequence[InterviewEvaluation]:
        result = await self.db.execute(
            select(InterviewEvaluation)
            .where(InterviewEvaluation.candidate_id == candidate_id)
            .order_by(InterviewEvaluation.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
