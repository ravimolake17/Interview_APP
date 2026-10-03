"""Repository for Agent 7 HR recommendation reports."""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.candidate import Candidate
from models.hr_recommendation_report import HrRecommendationReport


class HrRecommendationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        candidate_id: str,
        decision: str,
        overall_score: float,
        screening_score: float,
        interview_score: float,
        stage: str,
        executive_summary: str,
        report_json: dict[str, Any],
        model: str | None = None,
        company_id: int | None = None,
    ) -> HrRecommendationReport:
        row = HrRecommendationReport(
            candidate_id=candidate_id,
            company_id=company_id,
            decision=decision,
            overall_score=overall_score,
            screening_score=screening_score,
            interview_score=interview_score,
            stage=stage,
            executive_summary=executive_summary,
            report_json=report_json,
            model=model,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get_latest(self, candidate_id: str) -> HrRecommendationReport | None:
        result = await self.db.execute(
            select(HrRecommendationReport)
            .where(HrRecommendationReport.candidate_id == candidate_id)
            .order_by(HrRecommendationReport.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_recent(
        self, *, limit: int = 40, company_id: int | None = None
    ) -> Sequence[tuple[HrRecommendationReport, Candidate]]:
        query = (
            select(HrRecommendationReport, Candidate)
            .join(Candidate, Candidate.candidate_id == HrRecommendationReport.candidate_id)
            .order_by(HrRecommendationReport.created_at.desc())
            .limit(limit)
        )
        if company_id is not None:
            query = query.where(HrRecommendationReport.company_id == company_id)
        result = await self.db.execute(query)
        return result.all()

    async def latest_decisions(self, candidate_ids: Sequence[str]) -> dict[str, str]:
        if not candidate_ids:
            return {}
        result = await self.db.execute(
            select(HrRecommendationReport.candidate_id, HrRecommendationReport.decision)
            .where(HrRecommendationReport.candidate_id.in_(list(candidate_ids)))
            .distinct(HrRecommendationReport.candidate_id)
            .order_by(
                HrRecommendationReport.candidate_id,
                HrRecommendationReport.created_at.desc(),
            )
        )
        return {str(candidate_id): str(decision) for candidate_id, decision in result.all() if decision}
