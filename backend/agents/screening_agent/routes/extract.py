from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from core.database import get_db
from api.deps import get_optional_user
from api.tenancy import company_id_for_actor
from models.user import User
from agents.screening_agent.config import settings
from agents.screening_agent.schemas.ats import ScreeningJobAcceptedResponse
from agents.screening_agent.schemas.resume import ResumeResponse
from agents.screening_agent.services.ai_parser import extract_resume_data
from agents.screening_agent.services.groq_queue import GroqRateLimitError
from agents.screening_agent.services.docling_extractor import DoclingConversionError, DoclingDependencyError, dependency_status
from agents.screening_agent.services.document_ingestion import ingest_document, store_uploaded_document
from agents.screening_agent.services.screening_queue_service import ScreeningQueueService
from services.audit_service import audit_context_from_request

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Resume Extraction"])


def _merge_warnings(*warnings: object) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for warning in warnings:
        cleaned = str(warning or "").strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            values.append(cleaned)
    return " ".join(values)


def _job_poll_url(job_id: str) -> str:
    return f"/api/candidates/evaluate/jobs/{job_id}"


def _parse_optional_jd(
    jd_text: str | None,
    parsed_jd: str | None,
) -> tuple[str | None, dict | None]:
    text = (jd_text or "").strip() or None
    parsed: dict | None = None
    if parsed_jd and parsed_jd.strip():
        try:
            loaded = json.loads(parsed_jd)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="parsed_jd must be valid JSON.") from exc
        if not isinstance(loaded, dict):
            raise HTTPException(status_code=422, detail="parsed_jd must be a JSON object.")
        parsed = loaded
    if bool(text) == bool(parsed):
        raise HTTPException(
            status_code=422,
            detail="Provide exactly one of jd_text or parsed_jd.",
        )
    return text, parsed


@router.post("/extract", response_model=ResumeResponse)
async def extract_resume(file: UploadFile = File(...)) -> ResumeResponse:
    try:
        extracted = await ingest_document(file, "resumes")
        parsed: dict[str, Any] = await run_in_threadpool(extract_resume_data, extracted["text"])
        parsed["extraction_warning"] = _merge_warnings(
            extracted.get("extraction_warning"),
            parsed.get("extraction_warning"),
        )

        return ResumeResponse(
            status="success",
            original_filename=extracted["original_filename"],
            stored_file_url=extracted["stored_url"],
            pages=extracted["pages"],
            parsed_data=parsed,
        )
    except HTTPException:
        raise
    except GroqRateLimitError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc) or "Groq is busy. Queue this resume with POST /extract/async.",
        ) from exc
    except DoclingDependencyError as exc:
        logger.exception("Resume extraction dependency is unavailable")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DoclingConversionError as exc:
        logger.exception("Document conversion failed")
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        logger.exception("Resume data validation failed")
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Resume parsing failed")
        raise HTTPException(
            status_code=500,
            detail="Unable to process the uploaded resume.",
        ) from exc


@router.post("/extract/async", response_model=ScreeningJobAcceptedResponse, status_code=202)
async def extract_resume_async(
    request: Request,
    file: UploadFile = File(...),
    jd_text: str | None = Form(None),
    parsed_jd: str | None = Form(None),
    jd_source_text: str | None = Form(None),
    jd_original_filename: str | None = Form(None),
    jd_file_url: str | None = Form(None),
    send_invite_email: str = Form("true"),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> ScreeningJobAcceptedResponse:
    """Save the file to disk and queue Docling + Groq extraction, then scoring."""
    if not settings.SCREENING_QUEUE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Screening queue is disabled. Use POST /extract instead.",
        )

    text, parsed = _parse_optional_jd(jd_text, parsed_jd)
    try:
        stored = await store_uploaded_document(file, "resumes")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Resume upload failed")
        raise HTTPException(status_code=500, detail="Unable to store the uploaded resume.") from exc

    queue = ScreeningQueueService(db)
    job_id = await queue.enqueue_extract(
        {
            "stored_relative_path": stored["stored_relative_path"],
            "stored_url": stored["stored_url"],
            "original_filename": stored["original_filename"],
            "jd_text": text,
            "parsed_jd": parsed,
            "jd_source_text": (jd_source_text or "").strip() or None,
            "jd_original_filename": (jd_original_filename or "").strip() or None,
            "jd_file_url": (jd_file_url or "").strip() or None,
            "send_invite_email": str(send_invite_email or "true").strip().lower()
            in {"1", "true", "yes", "on"},
            "audit_context": audit_context_from_request(current_user, request),
            "company_id": company_id_for_actor(current_user, request),
        }
    )
    return ScreeningJobAcceptedResponse(
        job_id=job_id,
        poll_url=_job_poll_url(job_id),
        message="Resume stored. Extraction queued; scoring starts after parse completes.",
    )


@router.get("/health")
def health_check() -> dict[str, Any]:
    dependencies = dependency_status()
    docling_ready = bool(dependencies["docling"]["installed"])
    return {
        "status": "ok" if docling_ready else "degraded",
        "extractor": "docling",
        "ats": "enabled",
        "dependencies": dependencies,
    }
