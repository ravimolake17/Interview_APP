"""Agent 6 — Answer evaluation API (Meta Llama + resume/JD/web)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from agents.evaluation_agent.schemas import EvaluateAnswerRequest, EvaluateAnswerResponse
from api.deps import get_client_ip, get_current_user
from api.tenancy import accessible_candidate
from models.candidate import Candidate
from core.database import get_db
from models.user import User
from services.audit_service import AuditService
from services.evaluation_agent_service import EvaluationAgentService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/interview/agent6", tags=["Evaluation Agent (Agent 6)"])


@router.get("/candidates/{candidate_id}/status")
async def get_evaluation_agent_status(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    _tenant: Candidate = Depends(accessible_candidate),
) -> dict:
    try:
        return await EvaluationAgentService(db).get_status(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/candidates/{candidate_id}/evaluate",
    response_model=EvaluateAnswerResponse,
)
async def evaluate_answer(
    candidate_id: str,
    payload: EvaluateAnswerRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _tenant: Candidate = Depends(accessible_candidate),
) -> EvaluateAnswerResponse:
    service = EvaluationAgentService(db)
    try:
        result = await service.evaluate(
            candidate_id,
            question_id=payload.question_id,
            question_text=payload.question_text,
            candidate_answer=payload.candidate_answer,
            skill_tags=payload.skill_tags,
            use_web=payload.use_web,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Agent 6 evaluation failed for %s", candidate_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    await AuditService(db).log(
        action="INTERVIEW_ANSWER_EVALUATED",
        entity_type="candidate",
        entity_id=candidate_id,
        user=current_user,
        request=request,
        ip_address=get_client_ip(request),
        details={
            "score": result.evaluation.score,
            "verdict": result.evaluation.verdict,
            "model": result.evaluation.model,
        },
        message=(
            f"Agent 6 scored answer for {candidate_id}: "
            f"{result.evaluation.score:.0f} ({result.evaluation.verdict})."
        ),
    )
    await db.commit()
    return result


@router.get("/candidates/{candidate_id}/evaluations")
async def list_evaluations(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    _tenant: Candidate = Depends(accessible_candidate),
) -> dict:
    try:
        items = await EvaluationAgentService(db).list_evaluations(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(items, dict):
        return items
    return {"candidate_id": candidate_id, "evaluations": items}


@router.get("/candidates/{candidate_id}/answers/{question_id}/audio")
async def get_oral_answer_audio(
    candidate_id: str,
    question_id: str,
    db: AsyncSession = Depends(get_db),
    candidate: Candidate = Depends(accessible_candidate),
):
    from services.interview_oral_store import oral_turns, resolve_answer_audio

    wanted = str(question_id or "").strip()
    for turn in oral_turns(candidate):
        qid = str(turn.get("question_id") or "").strip()
        if qid != wanted and wanted not in qid:
            continue
        path = resolve_answer_audio(str(turn.get("audio_path") or ""))
        if path is None:
            continue
        suffix = path.suffix.lower()
        media = "audio/webm" if suffix == ".webm" else "audio/wav" if suffix == ".wav" else "application/octet-stream"
        return FileResponse(path, media_type=media, filename=path.name)
    raise HTTPException(status_code=404, detail="No saved voice answer for this question.")
