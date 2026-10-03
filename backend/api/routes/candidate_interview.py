"""Candidate in-app interview room APIs (Agent 4 + Agent 6, no Google Meet)."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from agents.interview_agent.graph import InterviewLangGraphAgent
from agents.interview_agent.mcq import intro_message
from agents.interview_agent.schemas import (
    InterviewSessionAnswerRequest,
    InterviewSessionStateResponse,
    McqAnswerRequest,
    McqFinishRequest,
    McqStateResponse,
    SpeakRequest,
    TranscribeResponse,
)
from api.deps import get_current_user
from api.tenancy import accessible_candidate
from models.candidate import Candidate
from api.routes.interview_agent import _persist_latest_evaluation, _session_response
from core.database import get_db
from models.user import User
from repositories.company_repository import CompanyRepository
from services.interview_agent_service import InterviewAgentService
from services import interview_mcq_service as mcq_svc
from services.interview_room_service import (
    AI_INTERVIEW_ACTIVE,
    COMPLETED,
    ENDED,
    HR_INTERVENTION,
    MAX_ROOM_JOINS,
    READY,
    broadcast_ai_session,
    can_rejoin_room,
    register_room_join,
    require_room_payload,
    require_scheduled_interview,
    room_join_count,
    runtime_from_snapshot,
    set_runtime_state,
    verify_agent5_prerequisites,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/interview/room", tags=["In-app interview room"])


class RoomControlIn(BaseModel):
    action: Literal["join_conversation", "return_to_ai", "end"]
    message: str | None = Field(default=None, max_length=2000)


class RoomControlResponse(BaseModel):
    candidate_id: str
    state: str
    hr_speaking: bool = False
    hr_message: str | None = None


class HrLiveControlIn(BaseModel):
    action: Literal[
        "skip",
        "next",
        "goto",
        "add_question",
        "speak",
        "return_to_ai",
    ]
    question_text: str | None = Field(default=None, max_length=2000)
    target_index: int | None = Field(default=None, ge=0)
    ask_now: bool = True
    message: str | None = Field(default=None, max_length=2000)


def _require_hr_participant(payload: dict) -> None:
    if str(payload.get("participant_role") or "").lower() != "hr":
        raise HTTPException(status_code=403, detail="HR participant token required for this control.")


async def _authorized_candidate(
    session_id: str,
    db: AsyncSession,
    authorization: str | None,
    *,
    require_verified: bool = True,
):
    payload = require_room_payload(authorization, session_id)
    candidate_id = str(payload.get("rr_candidate_id"))
    if require_verified:
        verify_agent5_prerequisites(session_id, payload)
    candidate, interview = await require_scheduled_interview(db, candidate_id)
    return payload, candidate, interview


def _mcq_status(candidate) -> str:
    snapshot = candidate.evaluation_snapshot if isinstance(candidate.evaluation_snapshot, dict) else {}
    data = snapshot.get("interview_mcq") if isinstance(snapshot.get("interview_mcq"), dict) else {}
    return str(data.get("status") or "")


def _mcq_blocks_oral(candidate) -> bool:
    return _mcq_status(candidate) in {"pending", "in_progress"}


async def _company_display_name(db: AsyncSession, candidate) -> str:
    if not getattr(candidate, "company_id", None):
        return "RR Parkon"
    company = await CompanyRepository(db).get_by_id(int(candidate.company_id))
    return (company.name if company and company.name else "RR Parkon").strip() or "RR Parkon"


@router.get("/sessions/{session_id}/runtime")
async def get_room_runtime(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    _payload, candidate, _interview = await _authorized_candidate(
        session_id, db, authorization, require_verified=False
    )
    runtime = runtime_from_snapshot(candidate)
    company_name = None
    company_code = None
    if candidate.company_id:
        company = await CompanyRepository(db).get_by_id(int(candidate.company_id))
        if company:
            company_name = company.name
            company_code = company.code
    return {
        "candidate_id": candidate.candidate_id,
        "full_name": candidate.full_name,
        "job_position": candidate.job_position,
        "session_id": session_id,
        "state": runtime.get("state") or READY,
        "hr_speaking": bool(runtime.get("hr_speaking")),
        "hr_message": runtime.get("hr_message"),
        "company_name": company_name,
        "company_code": company_code,
        "room_join_count": room_join_count(runtime),
        "room_visit_open": bool(runtime.get("room_visit_open")),
        "can_rejoin": can_rejoin_room(runtime),
        "max_room_joins": MAX_ROOM_JOINS,
    }


@router.post("/sessions/{session_id}/ai/start", response_model=InterviewSessionStateResponse)
async def start_room_ai(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    payload, candidate, _interview = await _authorized_candidate(session_id, db, authorization)
    if str(payload.get("participant_role") or "").lower() != "hr":
        register_room_join(candidate)
    agent = InterviewLangGraphAgent(db)
    is_resume = False
    try:
        existing = await agent.get_session_state(candidate.candidate_id)
        if existing and str(existing.get("Status") or "") not in {"FAILED", "COMPLETED", ""}:
            state = existing
            is_resume = True
        else:
            state = await agent.start_session(candidate.candidate_id, force_questions=False)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to start in-app AI interview for %s", candidate.candidate_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    status = str(state.get("Status") or "IN_PROGRESS")
    room_state = COMPLETED if status == "COMPLETED" else AI_INTERVIEW_ACTIVE
    await set_runtime_state(
        db,
        candidate.candidate_id,
        room_state,
        extra={"hr_speaking": False, "agent5_session_id": session_id, "started_by": str(payload.get("sub"))},
    )
    await db.commit()

    response = _session_response(candidate.candidate_id, state)

    # Compose a personalised greeting from Agent 4 for fresh sessions only.
    if not is_resume and status != "COMPLETED":
        first_name = (candidate.full_name or "").split()[0] if candidate.full_name else "there"
        company_name = await _company_display_name(db, candidate)
        response.welcome_message = intro_message(
            first_name=first_name,
            company_name=company_name,
            role=candidate.job_position or "",
        )

    return response


@router.get("/sessions/{session_id}/ai/session", response_model=InterviewSessionStateResponse)
async def get_room_ai_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    _payload, candidate, _interview = await _authorized_candidate(
        session_id, db, authorization, require_verified=False
    )
    agent = InterviewLangGraphAgent(db)
    state = await agent.get_session_state(candidate.candidate_id)
    if not state:
        raise HTTPException(status_code=404, detail="No AI interview session found.")
    return _session_response(candidate.candidate_id, state)


def _mcq_response(payload: dict) -> McqStateResponse:
    return McqStateResponse.model_validate(payload)


@router.get("/sessions/{session_id}/ai/mcq", response_model=McqStateResponse)
async def get_room_mcq(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    _payload, candidate, _interview = await _authorized_candidate(
        session_id, db, authorization, require_verified=False
    )
    state = await mcq_svc.get_mcq_state(db, candidate)
    if state.get("status") != "missing":
        await db.commit()
        return _mcq_response(state)

    agent = InterviewLangGraphAgent(db)
    session = await agent.get_session_state(candidate.candidate_id)
    history = list((session or {}).get("TurnHistory") or [])
    oral_started = any(str((turn or {}).get("answer_text") or "").strip() for turn in history)
    if oral_started:
        return _mcq_response(state)

    planned = None
    try:
        planned = int((session or {}).get("PlannedDurationMinutes") or 0) or None
    except (TypeError, ValueError):
        planned = None
    record = await mcq_svc.ensure_mcq(db, candidate, planned_minutes=planned)
    await db.commit()
    return _mcq_response(mcq_svc.public_state(record))


@router.post("/sessions/{session_id}/ai/mcq/start", response_model=McqStateResponse)
async def start_room_mcq(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    payload, candidate, _interview = await _authorized_candidate(session_id, db, authorization)
    if str(payload.get("participant_role") or "").lower() == "hr":
        raise HTTPException(status_code=403, detail="Only the candidate can start the MCQ test.")
    record = await mcq_svc.start_mcq(db, candidate)
    await db.commit()
    return _mcq_response(mcq_svc.public_state(record))


@router.post("/sessions/{session_id}/ai/mcq/answer", response_model=McqStateResponse)
async def answer_room_mcq(
    session_id: str,
    body: McqAnswerRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    payload, candidate, _interview = await _authorized_candidate(session_id, db, authorization)
    if str(payload.get("participant_role") or "").lower() == "hr":
        raise HTTPException(status_code=403, detail="Only the candidate can answer the MCQ test.")
    try:
        record = await mcq_svc.submit_mcq(
            db,
            candidate,
            option_id=body.option_id,
            skip=body.skip,
            question_id=body.question_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return _mcq_response(mcq_svc.public_state(record))


@router.post("/sessions/{session_id}/ai/mcq/finish", response_model=McqStateResponse)
async def finish_room_mcq(
    session_id: str,
    body: McqFinishRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    payload, candidate, _interview = await _authorized_candidate(session_id, db, authorization)
    if str(payload.get("participant_role") or "").lower() == "hr":
        raise HTTPException(status_code=403, detail="Only the candidate can finish the MCQ test.")
    record = await mcq_svc.finish_mcq(db, candidate, timed_out=body.timed_out)
    await db.commit()
    return _mcq_response(mcq_svc.public_state(record))


@router.post("/sessions/{session_id}/ai/answer", response_model=InterviewSessionStateResponse)
async def submit_room_answer(
    session_id: str,
    payload: InterviewSessionAnswerRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    _auth, candidate, _interview = await _authorized_candidate(session_id, db, authorization)
    if _mcq_blocks_oral(candidate):
        raise HTTPException(status_code=409, detail="Complete the MCQ test before the oral interview.")
    runtime = runtime_from_snapshot(candidate)
    if runtime.get("state") == HR_INTERVENTION or runtime.get("hr_speaking"):
        raise HTTPException(status_code=409, detail="AI interviewer is paused while HR is speaking.")
    agent = InterviewLangGraphAgent(db)
    try:
        state = await agent.submit_answer(candidate.candidate_id, payload.answer_text)
    except Exception as exc:
        logger.exception("Failed to submit in-app interview answer for %s", candidate.candidate_id)
        raise HTTPException(status_code=400, detail=str(exc) or "No active AI interview session.") from exc
    await _persist_latest_evaluation(db, candidate.candidate_id, state)
    status = str(state.get("Status") or "")
    await set_runtime_state(
        db,
        candidate.candidate_id,
        COMPLETED if status == "COMPLETED" else AI_INTERVIEW_ACTIVE,
        extra={"hr_speaking": False},
    )
    await db.commit()
    response = _session_response(candidate.candidate_id, state)
    await broadcast_ai_session(candidate, response.model_dump())
    return response


@router.post("/sessions/{session_id}/ai/transcribe", response_model=TranscribeResponse)
async def transcribe_room_answer(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
    file: UploadFile = File(...),
    question_id: str | None = Form(default=None),
    partial: bool = Form(default=False),
    prior_text: str | None = Form(default=None),
):
    _auth, candidate, _interview = await _authorized_candidate(session_id, db, authorization)
    service = InterviewAgentService(db)
    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file too large (max 25MB).")
    try:
        result = await service.transcribe_answer(
            candidate.candidate_id,
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
    except Exception:
        logger.exception("Whisper transcription failed for in-app room %s", candidate.candidate_id)
        raise HTTPException(status_code=500, detail="Transcription failed.") from None

    if not partial:
        from services.interview_oral_store import save_answer_audio, upsert_oral_turn

        current_question: dict = {}
        try:
            state = await InterviewLangGraphAgent(db).get_session_state(candidate.candidate_id)
            current_question = (state or {}).get("CurrentQuestion") or {}
            if not isinstance(current_question, dict):
                current_question = {}
        except Exception:
            current_question = {}
        qid = (question_id or "").strip() or str(current_question.get("id") or "").strip()
        audio_path = save_answer_audio(
            candidate.candidate_id,
            qid or None,
            content,
            file.filename or "answer.webm",
        )
        upsert_oral_turn(
            candidate,
            {
                "question_id": qid,
                "question_text": str(current_question.get("question_text") or ""),
                "answer_text": str(getattr(result, "text", "") or ""),
                "audio_path": audio_path,
            },
        )
        await db.commit()
    return result


@router.post("/sessions/{session_id}/ai/speak")
async def speak_room_text(
    session_id: str,
    payload: SpeakRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> Response:
    _auth, candidate, _interview = await _authorized_candidate(session_id, db, authorization)
    service = InterviewAgentService(db)
    text = (payload.text or "").strip() or None
    question_id = (payload.question_id or "").strip() or None
    voice = (payload.voice or "female").strip() or "female"
    if not text and not question_id:
        raise HTTPException(status_code=400, detail="Provide question_id or text to speak.")
    try:
        result = await service.speak(
            candidate.candidate_id,
            text=text,
            question_id=question_id,
            voice=voice,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception:
        logger.exception("TTS failed for in-app room %s", candidate.candidate_id)
        raise HTTPException(status_code=500, detail="Speech synthesis failed.") from exc
    return Response(
        content=result["audio_bytes"],
        media_type=result.get("content_type") or "audio/wav",
        headers={
            "X-TTS-Provider": str(result.get("provider") or ""),
            "X-TTS-Model": str(result.get("model") or ""),
            "X-TTS-Cached": "1" if result.get("cached") else "0",
        },
    )


@router.post("/sessions/{session_id}/leave")
async def leave_room(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    _auth, candidate, _interview = await _authorized_candidate(
        session_id, db, authorization, require_verified=False
    )
    left_by = "hr" if str(_auth.get("participant_role") or "").lower() == "hr" else "candidate"
    runtime = runtime_from_snapshot(candidate)
    next_state = COMPLETED if runtime.get("state") == COMPLETED else ENDED
    extra = {"left_by": left_by, "hr_speaking": False}
    if left_by == "candidate":
        extra["room_visit_open"] = False
    merged = await set_runtime_state(
        db,
        candidate.candidate_id,
        next_state,
        extra=extra,
    )
    updated = runtime_from_snapshot(candidate)
    can_rejoin = left_by == "candidate" and can_rejoin_room(updated)
    finalize_session = left_by == "candidate" and not can_rejoin
    if left_by == "candidate":
        try:
            from services.recommendation_agent_service import RecommendationAgentService

            await RecommendationAgentService(db).generate_report(candidate.candidate_id, force=True)
        except Exception:
            logger.warning("Agent 7 report skipped after leave for %s", candidate.candidate_id, exc_info=True)
    await db.commit()
    return {
        "candidate_id": candidate.candidate_id,
        "state": merged.get("state"),
        "left_by": left_by,
        "room_join_count": room_join_count(updated),
        "can_rejoin": can_rejoin,
        "finalize_session": finalize_session,
        "max_room_joins": MAX_ROOM_JOINS,
    }


@router.post("/sessions/{session_id}/ai/hr-control", response_model=InterviewSessionStateResponse)
async def hr_live_control(
    session_id: str,
    payload: HrLiveControlIn,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    """HR-in-room controls: skip/next/goto/add question, pause AI to speak, return to AI."""
    auth, candidate, _interview = await _authorized_candidate(
        session_id, db, authorization, require_verified=False
    )
    _require_hr_participant(auth)
    if _mcq_blocks_oral(candidate) and payload.action in {"skip", "next", "goto", "add_question"}:
        raise HTTPException(status_code=409, detail="Candidate is still taking the MCQ test.")
    agent = InterviewLangGraphAgent(db)

    if payload.action == "speak":
        runtime = await set_runtime_state(
            db,
            candidate.candidate_id,
            HR_INTERVENTION,
            extra={
                "hr_speaking": True,
                "hr_message": (payload.message or "").strip()
                or "HR has joined the conversation. The AI interviewer is paused.",
            },
        )
        await db.commit()
        state = await agent.get_session_state(candidate.candidate_id)
        if not state:
            raise HTTPException(status_code=404, detail="No AI interview session found.")
        response = _session_response(candidate.candidate_id, state)
        await broadcast_ai_session(candidate, response.model_dump())
        return response

    if payload.action == "return_to_ai":
        await set_runtime_state(
            db,
            candidate.candidate_id,
            AI_INTERVIEW_ACTIVE,
            extra={"hr_speaking": False, "hr_message": None},
        )
        await db.commit()
        state = await agent.get_session_state(candidate.candidate_id)
        if not state:
            raise HTTPException(status_code=404, detail="No AI interview session found.")
        response = _session_response(candidate.candidate_id, state)
        await broadcast_ai_session(candidate, response.model_dump())
        return response

    try:
        if payload.action == "add_question":
            text = (payload.question_text or "").strip()
            if not text:
                raise HTTPException(status_code=400, detail="question_text is required to add a question.")
            state = await agent.hr_add_question(
                candidate.candidate_id,
                text,
                ask_now=bool(payload.ask_now),
            )
        elif payload.action == "goto":
            if payload.target_index is None:
                raise HTTPException(status_code=400, detail="target_index is required for goto.")
            state = await agent.hr_skip_or_goto(
                candidate.candidate_id,
                action="goto",
                target_index=int(payload.target_index),
            )
        else:
            state = await agent.hr_skip_or_goto(
                candidate.candidate_id,
                action="skip" if payload.action == "skip" else "next",
            )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("HR live control failed for session %s", session_id)
        raise HTTPException(status_code=400, detail=str(exc) or "HR control failed.") from exc

    status = str(state.get("Status") or "")
    await set_runtime_state(
        db,
        candidate.candidate_id,
        COMPLETED if status == "COMPLETED" else AI_INTERVIEW_ACTIVE,
        extra={"hr_speaking": False, "hr_message": None, "controlled_by": "hr"},
    )
    await db.commit()
    response = _session_response(candidate.candidate_id, state)
    await broadcast_ai_session(candidate, response.model_dump())
    return response


@router.post("/candidates/{candidate_id}/control", response_model=RoomControlResponse)
async def hr_room_control(
    candidate_id: str,
    payload: RoomControlIn,
    db: AsyncSession = Depends(get_db),
    _tenant: Candidate = Depends(accessible_candidate),
):
    """HR observer: pause AI and join, or return control to the AI interviewer."""
    candidate, _interview = await require_scheduled_interview(db, candidate_id)
    if payload.action == "join_conversation":
        runtime = await set_runtime_state(
            db,
            candidate_id,
            HR_INTERVENTION,
            extra={"hr_speaking": True, "hr_message": (payload.message or "").strip() or "HR has joined the conversation."},
        )
    elif payload.action == "return_to_ai":
        runtime = await set_runtime_state(
            db,
            candidate_id,
            AI_INTERVIEW_ACTIVE,
            extra={"hr_speaking": False, "hr_message": None},
        )
    else:
        runtime = await set_runtime_state(
            db,
            candidate_id,
            ENDED,
            extra={"hr_speaking": False, "left_by": "hr"},
        )
    await db.commit()
    return RoomControlResponse(
        candidate_id=candidate.candidate_id,
        state=str(runtime.get("state") or READY),
        hr_speaking=bool(runtime.get("hr_speaking")),
        hr_message=runtime.get("hr_message"),
    )


@router.get("/candidates/{candidate_id}/runtime", response_model=RoomControlResponse)
async def hr_room_runtime(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    _tenant: Candidate = Depends(accessible_candidate),
):
    candidate, _interview = await require_scheduled_interview(db, candidate_id)
    runtime = runtime_from_snapshot(candidate)
    return RoomControlResponse(
        candidate_id=candidate.candidate_id,
        state=str(runtime.get("state") or READY),
        hr_speaking=bool(runtime.get("hr_speaking")),
        hr_message=runtime.get("hr_message"),
    )
