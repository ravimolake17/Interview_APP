"""Enqueue screening jobs for async processing."""

from __future__ import annotations

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.screening_job_repository import ScreeningJobRepository
from agents.screening_agent.config import settings
from agents.screening_agent.schemas.ats import CandidateEvaluateRequest


class ScreeningQueueService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ScreeningJobRepository(db)

    async def enqueue(self, payload: CandidateEvaluateRequest, *, company_id: int | None = None) -> str:
        job_id = str(uuid.uuid4())
        await self.repo.create(
            job_id,
            payload.model_dump_json(),
            company_id=company_id if company_id is not None else payload.company_id,
        )
        return job_id

    async def enqueue_extract(self, payload: dict) -> str:
        job_id = str(uuid.uuid4())
        body = dict(payload)
        body["kind"] = "extract"
        await self.repo.create(job_id, json.dumps(body), company_id=body.get("company_id"))
        return job_id

    async def enqueue_many(self, payloads: list[CandidateEvaluateRequest]) -> list[str]:
        if len(payloads) > settings.SCREENING_BATCH_MAX_SIZE:
            raise ValueError(
                f"Batch size {len(payloads)} exceeds limit of "
                f"{settings.SCREENING_BATCH_MAX_SIZE}."
            )
        job_ids: list[str] = []
        for payload in payloads:
            job_ids.append(await self.enqueue(payload, company_id=payload.company_id))
        return job_ids
