"""Agent 4 — Interview agent API (Meta Llama, Whisper STT, TTS, Agent 6 loop)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from agents.interview_agent.graph import InterviewLangGraphAgent
from agents.interview_agent.schemas import (
    FollowUpRequest,
    FollowUpResponse,
    GenerateQuestionsRequest,
    InterviewAgentStatusResponse,
    InterviewSessionAnswerRequest,
    InterviewSessionStartRequest,
    InterviewSessionStateResponse,
    ManualQuestionRequest,
    QuestionSetResponse,
    SpeakRequest,
    TranscribeResponse,
)
from agents.interview_agent.question_bank import QuestionBankLockedError
from api.deps import get_client_ip, get_current_user
from api.tenancy import accessible_candidate
from models.candidate import Candidate
from core.database import AsyncSessionLocal, get_db
from core.langgraph_runtime import get_checkpointer_backend
from models.user import User
from repositories.candidate_repository import CandidateRepository
from repositories.interview_evaluation_repository import InterviewEvaluationRepository
from services.audit_service import AuditService
from services.interview_agent_service import InterviewAgentService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/interview/agent4", tags=["Interview Agent (Agent 4)"])


async def _prepare_tts_background(question_set_id: int) -> None:
    """Background job: pre-generate Kokoro audio, committing after each clip."""
    async with AsyncSessionLocal() as db:
        try:
            service = InterviewAgentService(db)
            # commit_each=True so status polls see 1/16, 2/16, ... live.
            result = await service.prepare_speak_audio(question_set_id)
            # Final safety commit (no-op if already committed per item).
            try:
                await db.commit()
            except Exception:
                pass
            logger.info(
                "TTS cache ready for question_set=%s ready=%s/%s",
                question_set_id,
                result.get("ready"),
                result.get("total"),
            )
        except Exception:
            await db.rollback()
            logger.exception("Background TTS prepare failed for set %s", question_set_id)


@router.get(
    "/candidates/{candidate_id}/status",
    response_model=InterviewAgentStatusResponse,
)
async def get_interview_agent_status(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    _tenant: Candidate = Depends(accessible_candidate),
) -> InterviewAgentStatusResponse:
    try:
        payload = await InterviewAgentService(db).get_status(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return InterviewAgentStatusResponse.model_validate(payload)


@router.get(
    "/candidates/{candidate_id}/questions",
    response_model=QuestionSetResponse,
)
async def get_questions(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    _tenant: Candidate = Depends(accessible_candidate),
) -> QuestionSetResponse:
    service = InterviewAgentService(db)
    try:
        status = await service.get_status(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not status.get("question_set"):
        raise HTTPException(status_code=404, detail="No question set generated yet.")
    return status["question_set"]


@router.post(
    "/candidates/{candidate_id}/questions",
    response_model=QuestionSetResponse,
)
async def generate_questions(
    candidate_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    payload: GenerateQuestionsRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _tenant: Candidate = Depends(accessible_candidate),
) -> QuestionSetResponse:
    force = bool(payload.force) if payload else False
    prepare_tts = bool(payload.prepare_tts) if payload else True
    service = InterviewAgentService(db)
    try:
        result = await service.generate_questions(candidate_id, force=force)
    except QuestionBankLockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        status = 404 if "not found" in detail.lower() or "blueprint" in detail.lower() else 400
        raise HTTPException(status_code=status, detail=detail) from exc

    await AuditService(db).log(
        action="INTERVIEW_QUESTIONS_GENERATED",
        entity_type="candidate",
        entity_id=candidate_id,
        user=current_user,
        request=request,
        ip_address=get_client_ip(request),
        details={
            "question_set_id": result.id,
            "total_questions": result.total_questions,
            "force": force,
            "prepare_tts": prepare_tts,
        },
        message=(
            f"Agent 4 generated {result.total_questions} interview questions "
            f"for {candidate_id}."
        ),
    )
    await db.commit()

    # Pre-generate Kokoro TTS in the background so Speak is instant afterward.
    if prepare_tts and (force or result.tts_preparing or not result.tts_ready):
        background_tasks.add_task(_prepare_tts_background, result.id)

    return result


@router.post(
    "/candidates/{candidate_id}/questions/manual",
    response_model=QuestionSetResponse,
)
async def add_manual_question(
    candidate_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    payload: ManualQuestionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _tenant: Candidate = Depends(accessible_candidate),
) -> QuestionSetResponse:
    service = InterviewAgentService(db)
    try:
        result = await service.save_manual_question(
            candidate_id,
            question_text=payload.question_text,
            insert_at=payload.insert_at,
            category_id=payload.category_id,
            category_name=payload.category_name,
            difficulty=payload.difficulty,
            skill_tags=payload.skill_tags,
            estimated_seconds=payload.estimated_seconds,
        )
    except QuestionBankLockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await AuditService(db).log(
        action="INTERVIEW_QUESTION_ADDED",
        entity_type="candidate",
        entity_id=candidate_id,
        user=current_user,
        request=request,
        ip_address=get_client_ip(request),
        details={
            "question_set_id": result.id,
            "insert_at": payload.insert_at,
            "total_questions": result.total_questions,
        },
        message=f"Added interview question at position {payload.insert_at or result.total_questions} for {candidate_id}.",
        company_id=_tenant.company_id,
    )
    await db.commit()
    if payload.prepare_tts:
        background_tasks.add_task(_prepare_tts_background, result.id)
    return result


@router.patch(
    "/candidates/{candidate_id}/questions/manual/{question_id}",
    response_model=QuestionSetResponse,
)
async def update_manual_question(
    candidate_id: str,
    question_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    payload: ManualQuestionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _tenant: Candidate = Depends(accessible_candidate),
) -> QuestionSetResponse:
    service = InterviewAgentService(db)
    try:
        result = await service.save_manual_question(
            candidate_id,
            question_id=question_id,
            question_text=payload.question_text,
            insert_at=payload.insert_at,
            category_id=payload.category_id,
            category_name=payload.category_name,
            difficulty=payload.difficulty,
            skill_tags=payload.skill_tags,
            estimated_seconds=payload.estimated_seconds,
        )
    except QuestionBankLockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        status = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    await AuditService(db).log(
        action="INTERVIEW_QUESTION_UPDATED",
        entity_type="candidate",
        entity_id=candidate_id,
        user=current_user,
        request=request,
        ip_address=get_client_ip(request),
        details={
            "question_id": question_id,
            "insert_at": payload.insert_at,
            "total_questions": result.total_questions,
        },
        message=f"Updated interview question {question_id} for {candidate_id}.",
        company_id=_tenant.company_id,
    )
    await db.commit()
    if payload.prepare_tts:
        background_tasks.add_task(_prepare_tts_background, result.id)
    return result


@router.delete(
    "/candidates/{candidate_id}/questions/manual/{question_id}",
    response_model=QuestionSetResponse,
)
async def delete_manual_question(
    candidate_id: str,
    question_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _tenant: Candidate = Depends(accessible_candidate),
) -> QuestionSetResponse:
    service = InterviewAgentService(db)
    try:
        result = await service.delete_manual_question(candidate_id, question_id)
    except QuestionBankLockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        status = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    await AuditService(db).log(
        action="INTERVIEW_QUESTION_DELETED",
        entity_type="candidate",
        entity_id=candidate_id,
        user=current_user,
        request=request,
        ip_address=get_client_ip(request),
        details={"question_id": question_id, "total_questions": result.total_questions},
        message=f"Deleted interview question {question_id} for {candidate_id}.",
        company_id=_tenant.company_id,
    )
    await db.commit()
    return result


@router.post(
    "/candidates/{candidate_id}/followups",
    response_model=FollowUpResponse,
)
async def generate_followups(
    candidate_id: str,
    payload: FollowUpRequest,
    db: AsyncSession = Depends(get_db),
    _tenant: Candidate = Depends(accessible_candidate),
) -> FollowUpResponse:
    try:
        return await InterviewAgentService(db).create_followups(
            candidate_id,
            question_id=payload.question_id,
            question_text=payload.question_text,
            candidate_answer=payload.candidate_answer,
            max_followups=payload.max_followups,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/candidates/{candidate_id}/transcribe",
    response_model=TranscribeResponse,
)
async def transcribe_answer(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    _tenant: Candidate = Depends(accessible_candidate),
    file: UploadFile = File(...),
    question_id: str | None = Form(default=None),
    partial: bool = Form(default=False),
    prior_text: str | None = Form(default=None),
) -> TranscribeResponse:
    """Whisper STT with resume-aware correction for project names and proper nouns."""
    service = InterviewAgentService(db)
    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file too large (max 25MB).")

    try:
        return await service.transcribe_answer(
            candidate_id,
            content=content,
            filename=file.filename or "audio.webm",
            question_id=(question_id or "").strip() or None,
            partial=partial,
            prior_text=(prior_text or "").strip() or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Whisper transcription failed for %s", candidate_id)
        raise HTTPException(status_code=500, detail="Transcription failed.") from exc


@router.post("/candidates/{candidate_id}/speak")
async def speak_text(
    candidate_id: str,
    payload: SpeakRequest,
    db: AsyncSession = Depends(get_db),
    _tenant: Candidate = Depends(accessible_candidate),
) -> Response:
    """Speak a question from TTS cache when ready; otherwise synthesize with Indic Parler-TTS."""
    service = InterviewAgentService(db)
    text = (payload.text or "").strip() or None
    question_id = (payload.question_id or "").strip() or None
    voice = (payload.voice or "female").strip() or "female"
    if not text and not question_id:
        raise HTTPException(status_code=400, detail="Provide question_id or text to speak.")

    try:
        result = await service.speak(
            candidate_id,
            text=text,
            question_id=question_id,
            voice=voice,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("TTS failed for %s", candidate_id)
        raise HTTPException(status_code=500, detail="Speech synthesis failed.") from exc

    return Response(
        content=result["audio_bytes"],
        media_type=result.get("content_type") or "audio/wav",
        headers={
            "X-TTS-Provider": str(result.get("provider") or ""),
            "X-TTS-Model": str(result.get("model") or ""),
            "X-TTS-Cached": "1" if result.get("cached") else "0",
            "X-STT-Companion": "whisper-large-v3",
        },
    )


@router.post("/candidates/{candidate_id}/questions/{question_set_id}/prepare-tts")
async def prepare_question_tts(
    candidate_id: str,
    question_set_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _tenant: Candidate = Depends(accessible_candidate),
) -> dict:
    """Manually (re)queue Kokoro TTS pre-generation for a question set."""
    service = InterviewAgentService(db)
    try:
        await service.get_status(candidate_id)
        row = await service.questions_repo.get_by_id(question_set_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not row or row.candidate_id != candidate_id:
        raise HTTPException(status_code=404, detail="Question set not found for candidate.")
    await service.questions_repo.update_status(question_set_id, "SPEAK_PREPARING")
    await db.commit()
    background_tasks.add_task(_prepare_tts_background, question_set_id)
    return {
        "candidate_id": candidate_id,
        "question_set_id": question_set_id,
        "status": "SPEAK_PREPARING",
        "message": "Kokoro TTS pre-generation queued.",
    }


def _session_response(candidate_id: str, state: dict) -> InterviewSessionStateResponse:
    questions = list(state.get("Questions") or [])
    elapsed = 0
    started = str(state.get("SessionStartedAt") or "").strip()
    if started:
        try:
            from datetime import datetime, timezone

            started_at = datetime.fromisoformat(started.replace("Z", "+00:00"))
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            elapsed = max(0, int((datetime.now(timezone.utc) - started_at).total_seconds()))
        except ValueError:
            elapsed = 0
    planned = state.get("PlannedDurationMinutes")
    try:
        planned_minutes = int(planned) if planned is not None else None
    except (TypeError, ValueError):
        planned_minutes = None
    return InterviewSessionStateResponse(
        candidate_id=candidate_id,
        status=str(state.get("Status") or "UNKNOWN"),
        current_question=state.get("CurrentQuestion"),
        current_index=int(state.get("CurrentIndex") or 0),
        total_questions=int(state.get("TotalQuestions") or len(questions)),
        remaining_questions=int(state.get("RemainingQuestions") or 0),
        follow_ups=list(state.get("FollowUps") or []),
        turn_history=list(state.get("TurnHistory") or []),
        latest_evaluation=state.get("LatestEvaluation"),
        agent6_feedback=state.get("Agent6Feedback"),
        model=state.get("Model"),
        error=state.get("Error"),
        langgraph=True,
        questions=questions,
        planned_duration_minutes=planned_minutes,
        elapsed_seconds=elapsed,
        duration_extended=bool(state.get("DurationExtended")),
        interview_phase=str(state.get("InterviewPhase") or "") or None,
        turn_ack=str(state.get("TurnAck") or "").strip() or None,
    )


async def _persist_latest_evaluation(db: AsyncSession, candidate_id: str, state: dict) -> None:
    evaluation = state.get("LatestEvaluation")
    history = list(state.get("TurnHistory") or [])
    if not history:
        return
    candidate = await CandidateRepository(db).get_by_candidate_id(candidate_id)
    if candidate is None:
        return
    from services.interview_oral_store import oral_turns, sync_oral_from_history

    sync_oral_from_history(candidate, history)
    last = history[-1]
    question = last.get("question") or {}
    if question.get("is_candidate_qna") or last.get("candidate_qna"):
        return
    answer_text = str(last.get("answer_text") or "")
    if not evaluation:
        return
    try:
        payload = dict(evaluation)
        qid = str(question.get("id") or "").strip()
        oral = next(
            (item for item in oral_turns(candidate) if str(item.get("question_id") or "").strip() == qid),
            {},
        )
        if oral.get("audio_path"):
            payload["audio_path"] = oral.get("audio_path")
        await InterviewEvaluationRepository(db).create(
            candidate_id=candidate_id,
            question_id=str(question.get("id") or "") or None,
            question_text=str(question.get("question_text") or ""),
            answer_text=answer_text,
            score=float(evaluation.get("score") or 0),
            verdict=str(evaluation.get("verdict") or "adequate"),
            evaluation_json=payload,
            model=str(evaluation.get("model") or ""),
            company_id=int(candidate.company_id),
        )
    except Exception:
        logger.exception("Failed to persist Agent 6 evaluation for %s", candidate_id)


@router.post(
    "/candidates/{candidate_id}/session/start",
    response_model=InterviewSessionStateResponse,
)
async def start_interview_session(
    candidate_id: str,
    request: Request,
    payload: InterviewSessionStartRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _tenant: Candidate = Depends(accessible_candidate),
) -> InterviewSessionStateResponse:
    """Start Agent 4 LangGraph interview loop (runs until answer interrupt)."""
    force = bool(payload.force_questions) if payload else False
    agent = InterviewLangGraphAgent(db)
    try:
        state = await agent.start_session(candidate_id, force_questions=force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to start interview session for %s", candidate_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    await AuditService(db).log(
        action="INTERVIEW_SESSION_STARTED",
        entity_type="candidate",
        entity_id=candidate_id,
        user=current_user,
        request=request,
        ip_address=get_client_ip(request),
        details={"status": state.get("Status"), "checkpointer": get_checkpointer_backend()},
        message=f"Agent 4 LangGraph interview session started for {candidate_id}.",
    )
    await db.commit()
    return _session_response(candidate_id, state)


@router.post(
    "/candidates/{candidate_id}/session/answer",
    response_model=InterviewSessionStateResponse,
)
async def submit_interview_answer(
    candidate_id: str,
    payload: InterviewSessionAnswerRequest,
    db: AsyncSession = Depends(get_db),
    _tenant: Candidate = Depends(accessible_candidate),
) -> InterviewSessionStateResponse:
    """Resume Agent 4 after Whisper STT / typed answer; Agent 6 evaluates in parallel."""
    agent = InterviewLangGraphAgent(db)
    try:
        state = await agent.submit_answer(candidate_id, payload.answer_text)
    except Exception as exc:
        logger.exception("Failed to resume interview session for %s", candidate_id)
        raise HTTPException(
            status_code=400,
            detail=str(exc) or "No active interview session. Start the session first.",
        ) from exc
    await _persist_latest_evaluation(db, candidate_id, state)
    await db.commit()
    return _session_response(candidate_id, state)


@router.get(
    "/candidates/{candidate_id}/session",
    response_model=InterviewSessionStateResponse,
)
async def get_interview_session(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    _tenant: Candidate = Depends(accessible_candidate),
) -> InterviewSessionStateResponse:
    agent = InterviewLangGraphAgent(db)
    state = await agent.get_session_state(candidate_id)
    if not state:
        raise HTTPException(status_code=404, detail="No LangGraph interview session found.")
    return _session_response(candidate_id, state)
