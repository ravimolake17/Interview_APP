"""Data access for Agent 3 interview blueprints."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.interview_blueprint import InterviewBlueprint


class BlueprintRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_latest_for_candidate(self, candidate_id: str) -> InterviewBlueprint | None:
        result = await self.db.execute(
            select(InterviewBlueprint)
            .where(InterviewBlueprint.candidate_id == candidate_id)
            .order_by(InterviewBlueprint.created_at.desc(), InterviewBlueprint.id.desc())
        )
        return result.scalars().first()

    async def create(
        self,
        *,
        candidate_id: str,
        blueprint_version: str,
        candidate_level: str,
        total_questions: int,
        job_title: str | None,
        blueprint_json: dict[str, Any],
        company_id: int,
    ) -> InterviewBlueprint:
        row = InterviewBlueprint(
            candidate_id=candidate_id,
            company_id=company_id,
            blueprint_version=blueprint_version,
            candidate_level=candidate_level,
            total_questions=total_questions,
            job_title=job_title,
            blueprint_json=blueprint_json,
        )
        self.db.add(row)
        await self.db.flush()
        return row
