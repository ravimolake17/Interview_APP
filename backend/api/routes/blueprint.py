"""Agent 3 — Interview Blueprint API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from agents.blueprint_agent.generator import generate_interview_blueprint
from agents.blueprint_agent.schemas import (
    CandidateLevel,
    InterviewBlueprintRequest,
    InterviewBlueprintResponse,
)
from api.deps import get_client_ip, get_current_user, get_optional_user
from api.tenancy import accessible_candidate
from models.candidate import Candidate, CandidateStatus
from core.database import get_db
from models.user import User
from repositories.candidate_repository import CandidateRepository
from services.application_settings_service import ApplicationSettingsService
from services.audit_service import AuditService
from services.blueprint_service import BlueprintService
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/interview", tags=["Interview Blueprint (Agent 3)"])


async def _plan_locked_for_candidate(db: AsyncSession, candidate_id: str) -> bool:
    """Same window as question edits: open until 10 minutes before scheduled start."""
    from services.interview_agent_service import InterviewAgentService

    policy = await InterviewAgentService(db).get_question_edit_policy(
        candidate_id,
        include_session=True,
    )
    return not bool(policy.get("allowed", True))


class BlueprintStoredResponse(BaseModel):
    id: int
    candidate_id: str
    blueprint_version: str
    candidate_level: str
    total_questions: int
    job_title: str | None = None
    blueprint: InterviewBlueprintResponse
    default_duration_minutes: int = 30
    plan_locked: bool = False


class GenerateBlueprintForCandidateRequest(BaseModel):
    force: bool = Field(
        default=False,
        description="If true, regenerate even when a blueprint already exists.",
    )
    candidate_level: CandidateLevel | None = Field(
        default=None,
        description="Optional HR override for interview level. Omit to use inferred default.",
    )
    total_duration_minutes: int | None = Field(
        default=None,
        ge=10,
        le=120,
        description=(
            "Optional HR override for total interview minutes. "
            "Omit to use Settings → Interview hours slot length."
        ),
    )


@router.post("/blueprint", response_model=InterviewBlueprintResponse)
async def create_interview_blueprint(
    payload: InterviewBlueprintRequest,
) -> InterviewBlueprintResponse:
    """Generate Agent 3 blueprint from raw resume/JD/ATS payload (no DB write)."""
    try:
        return generate_interview_blueprint(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Interview blueprint generation failed")
        raise HTTPException(
            status_code=500,
            detail="Unable to generate interview blueprint.",
        ) from exc


@router.post(
    "/blueprint/candidates/{candidate_id}",
    response_model=BlueprintStoredResponse,
)
async def generate_blueprint_for_candidate(
    candidate_id: str,
    request: Request,
    payload: GenerateBlueprintForCandidateRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
    _tenant: Candidate = Depends(accessible_candidate),
):
    """Generate (or return existing) blueprint from stored Agent 1 evaluation data."""
    force = bool(payload.force) if payload else False
    candidate_level = payload.candidate_level if payload else None
    total_duration_minutes = payload.total_duration_minutes if payload else None
    if (force or candidate_level or total_duration_minutes is not None) and current_user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to generate or regenerate a blueprint.",
        )
    if force or candidate_level or total_duration_minutes is not None:
        if await _plan_locked_for_candidate(db, candidate_id):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Level and timing can only be edited until 10 minutes before "
                    "the scheduled interview start."
                ),
            )
    service = BlueprintService(db)
    try:
        row, blueprint = await service.generate_and_save_for_candidate(
            candidate_id,
            force=force or candidate_level is not None or total_duration_minutes is not None,
            candidate_level=candidate_level,
            total_duration_minutes=total_duration_minutes,
        )
    except ValueError as exc:
        detail = str(exc)
        lowered = detail.lower()
        if "not found" in lowered:
            status = 404
        elif "interview slot" in lowered:
            status = 409
        else:
            status = 404
        raise HTTPException(status_code=status, detail=detail) from exc
    except Exception as exc:
        logger.exception("Blueprint generation failed for %s", candidate_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    await AuditService(db).log(
        action="INTERVIEW_BLUEPRINT_GENERATED",
        entity_type="candidate",
        entity_id=candidate_id,
        user=current_user,
        request=request,
        ip_address=get_client_ip(request),
        details={
            "blueprint_id": row.id,
            "candidate_level": blueprint.candidate_level,
            "total_questions": blueprint.total_questions,
            "total_duration_minutes": blueprint.time_allocation.total_duration_minutes,
            "force": force,
            "level_override": candidate_level,
            "duration_override": total_duration_minutes,
        },
        message=(
            f"Agent 3 blueprint generated for {candidate_id}: "
            f"{blueprint.candidate_level}, {blueprint.total_questions} questions, "
            f"{blueprint.time_allocation.total_duration_minutes} min."
        ),
    )
    await db.commit()

    return BlueprintStoredResponse(
        id=row.id,
        candidate_id=row.candidate_id,
        blueprint_version=row.blueprint_version,
        candidate_level=row.candidate_level,
        total_questions=row.total_questions,
        job_title=row.job_title,
        blueprint=blueprint,
        default_duration_minutes=await ApplicationSettingsService(db).get_default_interview_minutes(),
        plan_locked=await _plan_locked_for_candidate(db, candidate_id),
    )


@router.get(
    "/blueprint/candidates/{candidate_id}",
    response_model=BlueprintStoredResponse,
)
async def get_blueprint_for_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    _tenant: Candidate = Depends(accessible_candidate),
):
    """Fetch the latest stored Agent 3 blueprint for a candidate.

    Catch-up generation runs only after the candidate has booked a slot
    (INTERVIEW_SCHEDULED), not on shortlist/invite alone.
    """
    service = BlueprintService(db)
    row = await service.get_latest(candidate_id)
    if not row:
        candidate = await CandidateRepository(db).get_by_candidate_id(candidate_id)
        if candidate and candidate.status == CandidateStatus.INTERVIEW_SCHEDULED:
            try:
                generated = await service.generate_and_save_for_candidate(
                    candidate_id, force=False
                )
                row = generated[0] if generated else None
            except Exception:
                logger.exception(
                    "Agent 3 catch-up generation failed for %s", candidate_id
                )
                row = None
    if not row:
        raise HTTPException(status_code=404, detail="No blueprint found for candidate.")

    return BlueprintStoredResponse(
        id=row.id,
        candidate_id=row.candidate_id,
        blueprint_version=row.blueprint_version,
        candidate_level=row.candidate_level,
        total_questions=row.total_questions,
        job_title=row.job_title,
        blueprint=InterviewBlueprintResponse.model_validate(row.blueprint_json),
        default_duration_minutes=await ApplicationSettingsService(db).get_default_interview_minutes(),
        plan_locked=await _plan_locked_for_candidate(db, candidate_id),
    )
