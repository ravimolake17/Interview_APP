"""Data access for async screening jobs."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.screening_job import ScreeningJob, ScreeningJobStatus
from agents.screening_agent.config import settings

EXTRACT_KIND_MARKER = '"kind": "extract"'


def payload_is_extract(payload_json: str | None) -> bool:
    return bool(payload_json) and EXTRACT_KIND_MARKER in payload_json


class ScreeningJobRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, job_id: str, payload_json: str, *, company_id: int | None = None) -> ScreeningJob:
        job = ScreeningJob(
            id=job_id,
            company_id=company_id,
            status=ScreeningJobStatus.PENDING.value,
            payload_json=payload_json,
        )
        self.db.add(job)
        await self.db.flush()
        return job

    async def get_by_id(self, job_id: str) -> ScreeningJob | None:
        result = await self.db.execute(select(ScreeningJob).where(ScreeningJob.id == job_id))
        return result.scalar_one_or_none()

    async def _processing_extract_count(self) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(ScreeningJob)
            .where(
                ScreeningJob.status == ScreeningJobStatus.PROCESSING.value,
                ScreeningJob.payload_json.contains(EXTRACT_KIND_MARKER),
            )
        )
        return int(result.scalar_one() or 0)

    async def claim_next_job(self) -> ScreeningJob | None:
        """Claim the oldest ready job. Only one extract job may process at a time."""
        allow_extract = (
            await self._processing_extract_count() < settings.MAX_CONCURRENT_EXTRACT_JOBS
        )
        conditions = [ScreeningJob.status == ScreeningJobStatus.PENDING.value]
        if not allow_extract:
            conditions.append(~ScreeningJob.payload_json.contains(EXTRACT_KIND_MARKER))

        result = await self.db.execute(
            select(ScreeningJob)
            .where(*conditions)
            .order_by(ScreeningJob.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = result.scalar_one_or_none()
        if not job:
            return None
        job.status = ScreeningJobStatus.PROCESSING.value
        job.started_at = datetime.now(timezone.utc)
        await self.db.flush()

        if (
            payload_is_extract(job.payload_json)
            and await self._processing_extract_count() > settings.MAX_CONCURRENT_EXTRACT_JOBS
        ):
            job.status = ScreeningJobStatus.PENDING.value
            job.started_at = None
            await self.db.flush()
            return await self._claim_scoring_job()
        return job

    async def _claim_scoring_job(self) -> ScreeningJob | None:
        result = await self.db.execute(
            select(ScreeningJob)
            .where(
                ScreeningJob.status == ScreeningJobStatus.PENDING.value,
                ~ScreeningJob.payload_json.contains(EXTRACT_KIND_MARKER),
            )
            .order_by(ScreeningJob.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = result.scalar_one_or_none()
        if not job:
            return None
        job.status = ScreeningJobStatus.PROCESSING.value
        job.started_at = datetime.now(timezone.utc)
        await self.db.flush()
        return job

    async def mark_completed(self, job: ScreeningJob, result_json: str) -> ScreeningJob:
        job.status = ScreeningJobStatus.COMPLETED.value
        job.result_json = result_json
        job.error_message = None
        job.completed_at = datetime.now(timezone.utc)
        await self.db.flush()
        return job

    async def mark_failed(self, job: ScreeningJob, error_message: str) -> ScreeningJob:
        job.status = ScreeningJobStatus.FAILED.value
        job.error_message = error_message[:4000]
        job.completed_at = datetime.now(timezone.utc)
        await self.db.flush()
        return job

    async def count_by_status(self) -> dict[str, int]:
        result = await self.db.execute(
            select(ScreeningJob.status, func.count())
            .group_by(ScreeningJob.status)
        )
        return {status: count for status, count in result.all()}
