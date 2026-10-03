from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.job_posting import JobPosting, JobPostingStatus


class JobPostingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def count(
        self,
        *,
        company_id: int | None = None,
        status: JobPostingStatus | None = None,
    ) -> int:
        query = select(func.count()).select_from(JobPosting)
        if company_id is not None:
            query = query.where(JobPosting.company_id == company_id)
        if status is not None:
            query = query.where(JobPosting.status == status)
        result = await self.db.execute(query)
        return int(result.scalar_one() or 0)

    async def list_all(self, *, company_id: int | None = None) -> list[JobPosting]:
        query = select(JobPosting).order_by(JobPosting.created_at.desc(), JobPosting.id.desc())
        if company_id is not None:
            query = query.where(JobPosting.company_id == company_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, job_id: int) -> JobPosting | None:
        result = await self.db.execute(select(JobPosting).where(JobPosting.id == job_id))
        return result.scalar_one_or_none()

    async def get_by_title(self, title: str, *, company_id: int | None = None) -> JobPosting | None:
        query = select(JobPosting).where(func.lower(JobPosting.title) == title.strip().lower())
        if company_id is not None:
            query = query.where(JobPosting.company_id == company_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_jd_file_url(
        self, jd_file_url: str, *, company_id: int | None = None
    ) -> JobPosting | None:
        query = select(JobPosting).where(JobPosting.jd_file_url == jd_file_url)
        if company_id is not None:
            query = query.where(JobPosting.company_id == company_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> JobPosting:
        job = JobPosting(**kwargs)
        self.db.add(job)
        await self.db.flush()
        return job

    async def delete(self, job: JobPosting) -> None:
        await self.db.delete(job)
        await self.db.flush()
