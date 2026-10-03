"""Data access layer for candidates."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.candidate import Candidate, CandidateStatus


class CandidateRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _scoped(self, query, company_id: int | None):
        if company_id is not None:
            return query.where(Candidate.company_id == company_id)
        return query

    async def get_by_candidate_id(
        self, candidate_id: str, *, company_id: int | None = None
    ) -> Candidate | None:
        query = self._scoped(
            select(Candidate).where(Candidate.candidate_id == candidate_id),
            company_id,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_email(
        self, email: str, *, company_id: int | None = None
    ) -> Candidate | None:
        normalized = email.strip().lower()
        query = self._scoped(
            select(Candidate)
            .where(func.lower(Candidate.email) == normalized)
            .order_by(Candidate.created_at.desc())
            .limit(1),
            company_id,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_by_email(
        self, email: str, *, company_id: int | None = None
    ) -> list[Candidate]:
        normalized = email.strip().lower()
        query = self._scoped(
            select(Candidate)
            .where(func.lower(Candidate.email) == normalized)
            .order_by(Candidate.created_at.desc()),
            company_id,
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_email_outside_company(
        self, email: str, company_id: int
    ) -> Candidate | None:
        """Most recent record with this email that belongs to a different company."""
        normalized = email.strip().lower()
        result = await self.db.execute(
            select(Candidate)
            .where(func.lower(Candidate.email) == normalized)
            .where(Candidate.company_id != company_id)
            .order_by(Candidate.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_resume_file_url(
        self, resume_file_url: str, *, company_id: int | None = None
    ) -> Candidate | None:
        if not resume_file_url:
            return None
        query = self._scoped(
            select(Candidate).where(Candidate.resume_file_url == resume_file_url),
            company_id,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_by_status(
        self,
        status: CandidateStatus | None = None,
        *,
        company_id: int | None = None,
    ) -> list[Candidate]:
        query = self._scoped(select(Candidate).order_by(Candidate.created_at.desc()), company_id)
        if status is not None:
            query = query.where(Candidate.status == status)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_status(self, candidate_id: str, status: CandidateStatus) -> Candidate | None:
        candidate = await self.get_by_candidate_id(candidate_id)
        if candidate:
            candidate.status = status
            await self.db.flush()
        return candidate
