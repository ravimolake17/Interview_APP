import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_optional_user
from api.tenancy import company_id_for_actor, get_tenant_scope
from core.database import get_db
from core.tenancy import TenantScope
from models.user import User
from repositories.screening_job_repository import ScreeningJobRepository
from agents.screening_agent.config import settings
from agents.screening_agent.schemas.ats import (
    CandidateEvaluateRequest,
    CandidateScoreRequest,
    EvaluationResponse,
    ScoreBreakdown,
    ScreeningBatchAcceptedResponse,
    ScreeningJobAcceptedResponse,
    ScreeningJobDetailResponse,
    ScreeningQueueStatsResponse,
)
from agents.screening_agent.services.evaluation_service import evaluate_candidate
from agents.screening_agent.services.matching_service import analyze_skill_match
from agents.screening_agent.services.scoring_service import score_candidate
from agents.screening_agent.services.screening_job_runner import (
    parse_extract_result,
    parse_job_result,
)
from agents.screening_agent.services.screening_queue_service import ScreeningQueueService
from services.screening_integration_service import (
    CandidateAlreadyScreenedElsewhereError,
    emails_from_parsed_resume,
    ensure_not_screened_elsewhere,
    save_and_schedule_shortlisted,
    save_screening_evaluation,
)
from services.audit_service import audit_context_from_request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/candidates", tags=["Resume Screening"])


def _job_poll_url(job_id: str) -> str:
    return f"/api/candidates/evaluate/jobs/{job_id}"


def _job_to_detail(job) -> ScreeningJobDetailResponse:
    extraction = parse_extract_result(job.result_json)
    return ScreeningJobDetailResponse(
        job_id=job.id,
        status=job.status,
        result=parse_job_result(job.result_json),
        extraction=extraction,
        scoring_job_id=extraction.scoring_job_id if extraction else None,
        error=job.error_message,
        created_at=job.created_at.isoformat() if job.created_at else None,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


async def _run_sync_evaluation(
    payload: CandidateEvaluateRequest,
    db: AsyncSession,
    *,
    current_user: User | None = None,
    request: Request | None = None,
) -> EvaluationResponse:
    """Synchronous path — evaluate immediately in the request thread."""
    company_id = company_id_for_actor(current_user, request)
    payload.company_id = company_id
    if company_id:
        await ensure_not_screened_elsewhere(
            db,
            emails=emails_from_parsed_resume(payload.parsed_resume),
            company_id=company_id,
        )

    evaluation = evaluate_candidate(
        payload.parsed_resume,
        jd_text=payload.jd_text,
        parsed_jd=payload.parsed_jd,
        resume_original_filename=payload.resume_original_filename,
    )

    jd_text = payload.jd_text or payload.jd_source_text
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

    invite_sent = False
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
            invite_sent = scheduling is not None
        except ValueError as exc:
            logger.warning("Shortlisted but scheduling skipped: %s", exc)
            evaluation.scheduling = None
        except Exception as exc:
            logger.exception("Failed to auto-schedule shortlisted candidate")
            raise HTTPException(
                status_code=500,
                detail=f"Candidate shortlisted but scheduling failed: {exc}",
            ) from exc

    from services.audit_service import AuditService

    await AuditService(db).log_resume_evaluated(
        candidate=saved_candidate,
        shortlist_status=evaluation.shortlist_status,
        user=current_user,
        request=request,
        invite_sent=invite_sent,
    )

    return evaluation


@router.post("/score", response_model=ScoreBreakdown)
def candidate_score(payload: CandidateScoreRequest) -> ScoreBreakdown:
    """Score trusted candidate/JD data using a server-computed skill match."""
    try:
        computed_match = analyze_skill_match(
            payload.candidate_profile.skills,
            payload.parsed_jd,
            experience_entries=payload.candidate_profile.experience_entries,
            keywords=payload.candidate_profile.keywords,
            resume_text=payload.candidate_profile.source_text,
        )

        if (
            payload.match_analysis is not None
            and payload.match_analysis != computed_match
        ):
            logger.warning(
                "Ignoring inconsistent client-supplied match_analysis; "
                "the server recomputed it from candidate and JD skills."
            )

        return score_candidate(
            payload.candidate_profile,
            payload.parsed_jd,
            computed_match,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Candidate scoring failed")
        raise HTTPException(
            status_code=500,
            detail="Unable to score the candidate.",
        ) from exc


@router.post("/evaluate", response_model=EvaluationResponse)
async def candidate_evaluate(
    payload: CandidateEvaluateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> EvaluationResponse:
    """
    Evaluate resume against JD (synchronous).
    For high-volume use, prefer POST /evaluate/async or /evaluate/batch/async.
    """
    try:
        result = await _run_sync_evaluation(
            payload,
            db,
            current_user=current_user,
            request=request,
        )
        await db.commit()
        return result
    except CandidateAlreadyScreenedElsewhereError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Candidate evaluation failed")
        raise HTTPException(
            status_code=500,
            detail="Unable to evaluate the candidate.",
        ) from exc


@router.post(
    "/evaluate/async",
    response_model=ScreeningJobAcceptedResponse,
    status_code=202,
)
async def candidate_evaluate_async(
    payload: CandidateEvaluateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> ScreeningJobAcceptedResponse:
    """Queue a single evaluation job. Poll GET /evaluate/jobs/{job_id} for results."""
    if not settings.SCREENING_QUEUE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Screening queue is disabled. Use POST /api/candidates/evaluate instead.",
        )
    try:
        payload.audit_context = audit_context_from_request(current_user, request)
        payload.company_id = company_id_for_actor(current_user, request)
        if payload.company_id:
            await ensure_not_screened_elsewhere(
                db,
                emails=emails_from_parsed_resume(payload.parsed_resume),
                company_id=payload.company_id,
            )
        queue = ScreeningQueueService(db)
        job_id = await queue.enqueue(payload, company_id=payload.company_id)
        return ScreeningJobAcceptedResponse(
            job_id=job_id,
            poll_url=_job_poll_url(job_id),
            message="Evaluation queued. Poll the job URL until status is completed.",
        )
    except CandidateAlreadyScreenedElsewhereError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/evaluate/batch/async",
    response_model=ScreeningBatchAcceptedResponse,
    status_code=202,
)
async def candidate_evaluate_batch_async(
    payloads: list[CandidateEvaluateRequest],
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> ScreeningBatchAcceptedResponse:
    """Queue up to 100 evaluations at once for parallel worker processing."""
    if not settings.SCREENING_QUEUE_ENABLED:
        raise HTTPException(status_code=503, detail="Screening queue is disabled.")
    if not payloads:
        raise HTTPException(status_code=422, detail="At least one evaluation payload is required.")
    try:
        context = audit_context_from_request(current_user, request)
        company_id = company_id_for_actor(current_user, request)
        for payload in payloads:
            payload.audit_context = context
            payload.company_id = company_id
            if company_id:
                await ensure_not_screened_elsewhere(
                    db,
                    emails=emails_from_parsed_resume(payload.parsed_resume),
                    company_id=company_id,
                )
        queue = ScreeningQueueService(db)
        job_ids = await queue.enqueue_many(payloads)
        jobs = [
            ScreeningJobAcceptedResponse(job_id=job_id, poll_url=_job_poll_url(job_id))
            for job_id in job_ids
        ]
        return ScreeningBatchAcceptedResponse(total=len(jobs), jobs=jobs)
    except CandidateAlreadyScreenedElsewhereError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/evaluate/jobs/{job_id}", response_model=ScreeningJobDetailResponse)
async def get_screening_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    scope: TenantScope = Depends(get_tenant_scope),
) -> ScreeningJobDetailResponse:
    """Poll evaluation job status and retrieve results when completed."""
    try:
        uuid.UUID(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc

    repo = ScreeningJobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job or not scope.allows(job.company_id):
        raise HTTPException(status_code=404, detail="Job not found.")
    return _job_to_detail(job)


@router.get("/evaluate/queue/stats", response_model=ScreeningQueueStatsResponse)
async def screening_queue_stats(
    db: AsyncSession = Depends(get_db),
) -> ScreeningQueueStatsResponse:
    """Queue depth and worker capacity for monitoring."""
    repo = ScreeningJobRepository(db)
    counts = await repo.count_by_status()
    return ScreeningQueueStatsResponse(
        pending=counts.get("pending", 0),
        processing=counts.get("processing", 0),
        completed=counts.get("completed", 0),
        failed=counts.get("failed", 0),
        max_concurrent_workers=settings.MAX_CONCURRENT_SCREENING_JOBS,
    )
