"""Execute a single queued screening extract or evaluation job."""

from __future__ import annotations

import asyncio
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from models.screening_job import ScreeningJob
from agents.screening_agent.config import settings
from agents.screening_agent.schemas.ats import (
    CandidateEvaluateRequest,
    EvaluationResponse,
    ExtractJobResult,
    ParsedJD,
)
from agents.screening_agent.schemas.resume import ParsedResume
from agents.screening_agent.graph import run_screening_graph
from agents.screening_agent.services.ai_parser import extract_resume_data
from agents.screening_agent.services.docling_extractor import extract_text_from_docx, extract_text_from_pdf
from agents.screening_agent.services.document_ingestion import get_uploads_root
from services.screening_integration_service import (
    ensure_not_screened_elsewhere,
    emails_from_parsed_resume,
    save_and_schedule_shortlisted,
    save_screening_evaluation,
)

logger = logging.getLogger(__name__)
_extract_semaphore: asyncio.Semaphore | None = None


def _get_extract_semaphore() -> asyncio.Semaphore:
    global _extract_semaphore
    if _extract_semaphore is None:
        _extract_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_EXTRACT_JOBS)
    return _extract_semaphore


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


def _is_extract_payload(payload: object) -> bool:
    return isinstance(payload, dict) and payload.get("kind") == "extract"


async def execute_extract_job(db: AsyncSession, job: ScreeningJob, payload: dict) -> str:
    """Docling + Groq parse, then enqueue the existing scoring job."""
    from agents.screening_agent.services.screening_queue_service import ScreeningQueueService

    relative = str(payload.get("stored_relative_path") or "").strip()
    if not relative or ".." in relative.replace("\\", "/"):
        raise ValueError("Extract job is missing a stored resume path.")

    path = get_uploads_root() / relative
    if not path.is_file():
        raise FileNotFoundError(f"Uploaded resume not found: {relative}")

    async with _get_extract_semaphore():
        extension = path.suffix.casefold()
        extractor = extract_text_from_pdf if extension == ".pdf" else extract_text_from_docx
        extracted = await asyncio.to_thread(extractor, str(path))
        text = str(extracted.get("full_text", "")).strip()
        if not text:
            raise ValueError("No readable text found in the file.")

        parsed = await asyncio.to_thread(extract_resume_data, text)
        parsed["extraction_warning"] = _merge_warnings(
            extracted.get("extraction_warning"),
            parsed.get("extraction_warning"),
        )
        company_id = payload.get("company_id") or job.company_id
        if company_id:
            await ensure_not_screened_elsewhere(
                db,
                emails=emails_from_parsed_resume(parsed, text),
                company_id=int(company_id),
            )

        evaluate = CandidateEvaluateRequest(
            parsed_resume=ParsedResume.model_validate(parsed),
            jd_text=payload.get("jd_text"),
            parsed_jd=(
                ParsedJD.model_validate(payload["parsed_jd"])
                if payload.get("parsed_jd") is not None
                else None
            ),
            resume_original_filename=payload.get("original_filename"),
            resume_file_url=payload.get("stored_url"),
            jd_original_filename=payload.get("jd_original_filename"),
            jd_file_url=payload.get("jd_file_url"),
            jd_source_text=payload.get("jd_source_text"),
            audit_context=(
                payload.get("audit_context")
                if isinstance(payload.get("audit_context"), dict)
                else None
            ),
            company_id=payload.get("company_id") or job.company_id,
            send_invite_email=bool(payload.get("send_invite_email", True)),
        )
        scoring_job_id = await ScreeningQueueService(db).enqueue(
            evaluate, company_id=evaluate.company_id
        )

        result = ExtractJobResult(
            kind="extract",
            original_filename=str(payload.get("original_filename") or ""),
            stored_file_url=str(payload.get("stored_url") or ""),
            pages=len(extracted.get("pages", []) or []),
            parsed_data=ParsedResume.model_validate(parsed),
            scoring_job_id=scoring_job_id,
            extraction_warning=str(parsed.get("extraction_warning") or ""),
        )
        logger.info(
            "Extract job %s parsed %s; scoring job %s queued",
            job.id,
            payload.get("original_filename"),
            scoring_job_id,
        )
        return result.model_dump_json()


async def execute_evaluate_job(db: AsyncSession, job: ScreeningJob, payload: CandidateEvaluateRequest) -> str:
    """Run evaluation + persistence for a claimed job. Returns result JSON."""
    company_id = job.company_id or payload.company_id
    if company_id:
        await ensure_not_screened_elsewhere(
            db,
            emails=emails_from_parsed_resume(payload.parsed_resume),
            company_id=int(company_id),
        )

    evaluation = await run_screening_graph(
        job_id=str(job.id),
        parsed_resume=payload.parsed_resume,
        jd_text=payload.jd_text,
        parsed_jd=payload.parsed_jd,
        resume_original_filename=payload.resume_original_filename,
    )

    jd_text = payload.jd_text or payload.jd_source_text
    company_id = job.company_id or payload.company_id
    saved_candidate, persist_warning = await save_screening_evaluation(
        db,
        evaluation,
        jd_text=jd_text,
        parsed_resume=payload.parsed_resume,
        resume_original_filename=payload.resume_original_filename,
        resume_file_url=payload.resume_file_url,
        jd_original_filename=payload.jd_original_filename,
        jd_file_url=payload.jd_file_url,
        company_id=company_id,
    )
    evaluation.saved_candidate_id = saved_candidate.candidate_id
    evaluation.persist_warning = persist_warning

    if evaluation.shortlist_status == "Shortlisted" and payload.send_invite_email:
        try:
            scheduling = await save_and_schedule_shortlisted(
                db,
                evaluation,
                jd_text=jd_text,
                parsed_resume=payload.parsed_resume,
                resume_original_filename=payload.resume_original_filename,
                resume_file_url=payload.resume_file_url,
                jd_original_filename=payload.jd_original_filename,
                jd_file_url=payload.jd_file_url,
                company_id=company_id,
            )
            evaluation.scheduling = scheduling
        except ValueError as exc:
            logger.warning("Shortlisted but scheduling skipped for job %s: %s", job.id, exc)
            evaluation.scheduling = None
        except Exception:
            logger.exception(
                "Scheduling/email failed for shortlisted job %s; evaluation result kept",
                job.id,
            )
            evaluation.scheduling = None

    try:
        from services.audit_service import AuditService

        context = dict(payload.audit_context or {}) if isinstance(payload.audit_context, dict) else {}
        audit = AuditService(db)
        if not context.get("user_id"):
            snapshot = await audit.actor_snapshot_at()
            for key, value in snapshot.items():
                context.setdefault(key, value)
        user = await audit.resolve_actor_user(context)
        invite_sent = bool(evaluation.scheduling)
        await audit.log_resume_evaluated(
            candidate=saved_candidate,
            shortlist_status=evaluation.shortlist_status,
            user=user,
            context=context,
            invite_sent=invite_sent,
        )
    except Exception:
        logger.exception("Failed to write screening audit for job %s", job.id)

    return json.dumps(evaluation.model_dump(mode="json"))


async def execute_screening_job(db: AsyncSession, job: ScreeningJob) -> str:
    """Dispatch extract vs scoring work for a claimed screening_jobs row."""
    raw = json.loads(job.payload_json)
    if _is_extract_payload(raw):
        return await execute_extract_job(db, job, raw)
    payload = CandidateEvaluateRequest.model_validate(raw)
    return await execute_evaluate_job(db, job, payload)


def parse_job_result(result_json: str | None) -> EvaluationResponse | None:
    if not result_json:
        return None
    data = json.loads(result_json)
    if _is_extract_payload(data):
        return None
    return EvaluationResponse.model_validate(data)


def parse_extract_result(result_json: str | None) -> ExtractJobResult | None:
    if not result_json:
        return None
    data = json.loads(result_json)
    if not _is_extract_payload(data):
        return None
    return ExtractJobResult.model_validate(data)
