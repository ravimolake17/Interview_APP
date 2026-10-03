"""Background worker pool for Agent 1 screening jobs."""

from __future__ import annotations

import asyncio
import logging

from core.database import AsyncSessionLocal
from repositories.screening_job_repository import ScreeningJobRepository
from agents.screening_agent.config import settings
from agents.screening_agent.services.screening_job_runner import execute_screening_job
from agents.screening_agent.services.groq_queue import GroqRateLimitError
from services.screening_integration_service import CandidateAlreadyScreenedElsewhereError

logger = logging.getLogger(__name__)


class ScreeningWorkerPool:
    """Process queued screening jobs with bounded concurrency."""

    def __init__(
        self,
        *,
        max_workers: int | None = None,
        poll_seconds: float | None = None,
    ) -> None:
        self.max_workers = max_workers or settings.MAX_CONCURRENT_SCREENING_JOBS
        self.poll_seconds = poll_seconds or settings.SCREENING_WORKER_POLL_SECONDS
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._tasks = [
            asyncio.create_task(self._worker_loop(worker_id), name=f"screening-worker-{worker_id}")
            for worker_id in range(self.max_workers)
        ]
        logger.info(
            "Screening worker pool started (%d workers, poll=%.1fs)",
            self.max_workers,
            self.poll_seconds,
        )

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("Screening worker pool stopped")

    async def _worker_loop(self, worker_id: int) -> None:
        while self._running:
            try:
                async with AsyncSessionLocal() as db:
                    repo = ScreeningJobRepository(db)
                    job = await repo.claim_next_job()
                    if not job:
                        await asyncio.sleep(self.poll_seconds)
                        continue

                    try:
                        result_json = await execute_screening_job(db, job)
                        await repo.mark_completed(job, result_json)
                    except CandidateAlreadyScreenedElsewhereError as exc:
                        logger.warning("Screening job %s blocked: %s", job.id, exc)
                        await repo.mark_failed(job, str(exc))
                    except GroqRateLimitError as exc:
                        logger.warning(
                            "Screening job %s not saved; Groq stayed busy: %s",
                            job.id,
                            exc,
                        )
                        await repo.mark_failed(job, str(exc))
                    except Exception as exc:
                        logger.exception(
                            "Screening job %s failed on worker %d", job.id, worker_id
                        )
                        await repo.mark_failed(job, str(exc))
                    await db.commit()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Screening worker %d loop error", worker_id)
                await asyncio.sleep(self.poll_seconds)


_worker_pool: ScreeningWorkerPool | None = None


def get_worker_pool() -> ScreeningWorkerPool:
    global _worker_pool
    if _worker_pool is None:
        _worker_pool = ScreeningWorkerPool()
    return _worker_pool
