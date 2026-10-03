"""Tests for Agent 1 async screening queue."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest

from core.database import AsyncSessionLocal
from repositories.screening_job_repository import ScreeningJobRepository
from agents.screening_agent.config import settings
from agents.screening_agent.schemas.ats import CandidateEvaluateRequest
from agents.screening_agent.services.screening_job_runner import (
    execute_screening_job,
    parse_extract_result,
    parse_job_result,
)
from agents.screening_agent.services.screening_queue_service import ScreeningQueueService

PARSED_RESUME = {
    "sections": [
        {
            "section_id": "contact_information",
            "heading": "Contact Information",
            "heading_source": "inferred",
            "order": 0,
            "content_type": "text",
            "items": [],
            "raw_text": "Asha Patil\nasha@example.com",
        },
        {
            "section_id": "skills",
            "heading": "Technical Skills",
            "heading_source": "original",
            "order": 1,
            "content_type": "list",
            "items": ["Python", "FastAPI", "Postgres"],
            "raw_text": "Python, FastAPI, Postgres",
        },
        {
            "section_id": "experience",
            "heading": "Experience",
            "heading_source": "original",
            "order": 2,
            "content_type": "text",
            "items": [],
            "raw_text": "Backend Developer\nJan 2023 - Present\nBuilt REST APIs.",
        },
    ],
    "extraction_method": "ai",
}

JD_TEXT = (
    "Job Title: Backend Developer\n"
    "Required Skills: Python, FastAPI, PostgreSQL\n"
    "Preferred Skills: Docker\n"
    "Minimum 2 years experience"
)


def _evaluate_payload() -> dict:
    return {"parsed_resume": PARSED_RESUME, "jd_text": JD_TEXT}


class _FakeDb:
    pass


@pytest.mark.asyncio
async def test_enqueue_many_respects_batch_limit():
    payloads = [
        CandidateEvaluateRequest.model_validate(_evaluate_payload())
        for _ in range(settings.SCREENING_BATCH_MAX_SIZE + 1)
    ]
    service = ScreeningQueueService(_FakeDb())  # type: ignore[arg-type]

    async def fake_enqueue(_payload):
        return str(uuid.uuid4())

    service.enqueue = fake_enqueue  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="exceeds limit"):
        await service.enqueue_many(payloads)


@pytest.mark.asyncio
async def test_queue_enqueue_process_complete():
    async with AsyncSessionLocal() as db:
        queue = ScreeningQueueService(db)
        payload = CandidateEvaluateRequest.model_validate(_evaluate_payload())
        job_id = await queue.enqueue(payload)
        await db.commit()

    async with AsyncSessionLocal() as db:
        repo = ScreeningJobRepository(db)
        job = await repo.get_by_id(job_id)
        assert job is not None
        if job.status != "pending":
            pytest.skip("Job already processed by a running screening worker.")
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        result_json = await execute_screening_job(db, job)
        await repo.mark_completed(job, result_json)
        await db.commit()

    async with AsyncSessionLocal() as db:
        job = await ScreeningJobRepository(db).get_by_id(job_id)
        assert job is not None
        assert job.status == "completed"
        assert job.result_json is not None


def test_extract_result_is_not_parsed_as_evaluation():
    payload = {
        "kind": "extract",
        "original_filename": "asha.pdf",
        "stored_file_url": "/screening-files/resumes/a.pdf",
        "pages": 1,
        "scoring_job_id": "score-1",
        "parsed_data": PARSED_RESUME,
        "extraction_warning": "",
    }
    raw = json.dumps(payload)
    assert parse_job_result(raw) is None
    extraction = parse_extract_result(raw)
    assert extraction is not None
    assert extraction.scoring_job_id == "score-1"
    assert extraction.parsed_data is not None


@pytest.mark.asyncio
async def test_execute_extract_job_enqueues_scoring(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from agents.screening_agent.services.screening_job_runner import execute_extract_job

    resume_dir = tmp_path / "resumes"
    resume_dir.mkdir()
    stored_name = "asha.pdf"
    (resume_dir / stored_name).write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(
        "agents.screening_agent.services.screening_job_runner.get_uploads_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "agents.screening_agent.services.screening_job_runner.extract_text_from_pdf",
        lambda _path: {
            "full_text": "Asha Patil\nasha@example.com\nExperience\nBackend Developer Jan 2023 - Present",
            "pages": ["1"],
        },
    )
    monkeypatch.setattr(
        "agents.screening_agent.services.screening_job_runner.extract_resume_data",
        lambda _text: {**PARSED_RESUME, "source_text": "Asha Patil"},
    )

    class FakeQueue:
        def __init__(self, _db):
            self.payload = None

        async def enqueue(self, payload):
            self.payload = payload
            return "score-job-1"

    fake_queue = FakeQueue(None)
    monkeypatch.setattr(
        "agents.screening_agent.services.screening_queue_service.ScreeningQueueService",
        lambda _db: fake_queue,
    )

    result_json = await execute_extract_job(
        None,  # type: ignore[arg-type]
        SimpleNamespace(id="extract-1"),
        {
            "kind": "extract",
            "stored_relative_path": f"resumes/{stored_name}",
            "stored_url": f"/screening-files/resumes/{stored_name}",
            "original_filename": "Asha.pdf",
            "jd_text": JD_TEXT,
            "audit_context": {"user_id": 1, "user_email": "admin@example.com"},
        },
    )
    extraction = parse_extract_result(result_json)
    assert extraction is not None
    assert extraction.scoring_job_id == "score-job-1"
    assert extraction.original_filename == "Asha.pdf"
    assert parse_job_result(result_json) is None
    assert fake_queue.payload.audit_context == {
        "user_id": 1,
        "user_email": "admin@example.com",
    }
