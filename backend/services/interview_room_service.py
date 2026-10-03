"""In-app interview room: candidate auth, session state, HR intervention.

The live interview uses the existing Agent 5 browser media room
(getUserMedia + WebSocket monitoring + Agent 4 STT/LLM/TTS). There is no
Google Meet or LiveKit dependency.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models.candidate import Candidate
from models.interview import Interview, InterviewStatus

logger = logging.getLogger(__name__)

RUNTIME_KEY = "interview_runtime"
MAX_ROOM_JOINS = 3
ROOM_REJOIN_BLOCKED = (
    "You have already joined this interview 3 times. "
    "A fourth entry is not allowed. Please contact HR."
)

AUTHENTICATING = "AUTHENTICATING"
READY = "READY"
AI_INTERVIEW_ACTIVE = "AI_INTERVIEW_ACTIVE"
HR_INTERVENTION = "HR_INTERVENTION"
AI_PAUSED = "AI_PAUSED"
COMPLETED = "COMPLETED"
ENDED = "ENDED"


def _utcnow() -> datetime:
    from core.trusted_time import trusted_utc_now

    return trusted_utc_now()


def in_app_room_url(meeting_link: str | None, join_link: str | None = None) -> str | None:
    """Never return an external Meet URL; prefer the hashed in-app join link."""
    if join_link:
        return join_link
    if meeting_link and "meet.google.com" in meeting_link.lower():
        return None
    return meeting_link


def decode_candidate_room_token(authorization: str | None) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        from agents.proctoring_agent.security import decode_token

        payload = decode_token(token, expected_type="candidate")
    except Exception as exc:
        raise HTTPException(status_code=401, detail="invalid candidate token") from exc
    return payload


def require_room_payload(authorization: str | None, session_id: str) -> dict[str, Any]:
    payload = decode_candidate_room_token(authorization)
    if str(payload.get("session_id") or "") != session_id:
        raise HTTPException(status_code=401, detail="candidate token is not bound to this session")
    rr_candidate_id = str(payload.get("rr_candidate_id") or "").strip()
    if not rr_candidate_id:
        raise HTTPException(status_code=403, detail="This session is not linked to a scheduled interview.")
    return payload


def verify_agent5_prerequisites(session_id: str, payload: dict[str, Any]) -> None:
    # HR observers enter the room without candidate identity gates.
    if str(payload.get("participant_role") or "").lower() == "hr":
        return

    from agents.proctoring_agent.db import SessionLocal
    from agents.proctoring_agent.models import DeviceCheck, InterviewSession

    with SessionLocal() as db:
        session = db.get(InterviewSession, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found.")
        if str(payload.get("sub") or "") != session.candidate_id:
            raise HTTPException(status_code=401, detail="candidate token is not bound to this session")
        if session.status in {"terminated", "completed"}:
            raise HTTPException(status_code=409, detail="This interview session is already finalized.")
        latest_check = db.scalar(
            select(DeviceCheck)
            .where(DeviceCheck.session_id == session.id)
            .order_by(DeviceCheck.created_at.desc())
        )
        missing: list[str] = []
        if not latest_check or not (latest_check.camera_ok and latest_check.microphone_ok):
            missing.append("device_checks")
        if not session.face_enrolled or not session.initial_face_verified:
            missing.append("face_enrollment_and_verification")
        if not session.voice_enrolled or not session.initial_voice_verified:
            missing.append("voice_enrollment_and_verification")
        if missing:
            raise HTTPException(
                status_code=409,
                detail={"message": "Complete identity verification before entering the interview room.", "missing": missing},
            )


async def require_scheduled_interview(db: AsyncSession, candidate_id: str) -> tuple[Candidate, Interview]:
    candidate = await db.scalar(select(Candidate).where(Candidate.candidate_id == candidate_id))
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    interview = await db.scalar(
        select(Interview)
        .where(Interview.candidate_id == candidate_id)
        .order_by(Interview.created_at.desc())
    )
    if interview is None:
        raise HTTPException(status_code=409, detail="No scheduled interview was found for this candidate.")
    if interview.status != InterviewStatus.SCHEDULED:
        raise HTTPException(status_code=409, detail="This interview is no longer active.")
    expires_at = interview.join_token_expires_at
    if expires_at is not None:
        expiry = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
        if _utcnow() > expiry:
            raise HTTPException(status_code=410, detail="This interview link has expired.")
    return candidate, interview


def runtime_from_snapshot(candidate: Candidate) -> dict[str, Any]:
    snapshot = dict(candidate.evaluation_snapshot or {})
    agent5 = dict(snapshot.get("agent5") or {})
    runtime = dict(agent5.get(RUNTIME_KEY) or {})
    if not runtime.get("state"):
        runtime["state"] = READY
    return runtime


PLAN_LOCK_RUNTIME = {AI_INTERVIEW_ACTIVE, HR_INTERVENTION, COMPLETED, ENDED}
PLAN_LOCK_SESSION = {
    "IN_PROGRESS",
    "AWAITING_ANSWER",
    "TURN_COMPLETE",
    "CANDIDATE_QNA",
    "COMPLETED",
}


def plan_is_locked(candidate: Candidate | None, langgraph_status: str | None = None) -> bool:
    """True once the live interview has started — Agent 3 edits no longer apply."""
    if candidate is not None:
        runtime = runtime_from_snapshot(candidate)
        if str(runtime.get("state") or "") in PLAN_LOCK_RUNTIME:
            return True
    status = str(langgraph_status or "").upper()
    return status in PLAN_LOCK_SESSION


def room_join_count(runtime: dict[str, Any] | None) -> int:
    try:
        return max(0, int((runtime or {}).get("room_join_count") or 0))
    except (TypeError, ValueError):
        return 0


def can_rejoin_room(runtime: dict[str, Any] | None) -> bool:
    data = runtime or {}
    if bool(data.get("room_visit_open")):
        return True
    return room_join_count(data) < MAX_ROOM_JOINS


def register_room_join(candidate: Candidate) -> dict[str, Any]:
    """Count a candidate entering the live interview room. Max 3 visits."""
    runtime = runtime_from_snapshot(candidate)
    if bool(runtime.get("room_visit_open")):
        return runtime
    if room_join_count(runtime) >= MAX_ROOM_JOINS:
        raise HTTPException(status_code=403, detail=ROOM_REJOIN_BLOCKED)
    return persist_runtime(
        candidate,
        {
            "room_join_count": room_join_count(runtime) + 1,
            "room_visit_open": True,
            "left_by": None,
        },
    )


def register_room_join_sync(rr_candidate_id: str) -> dict[str, Any]:
    """Same join-limit check for the sync Agent 5 start endpoint."""
    import json

    from agents.proctoring_agent.db import SessionLocal
    from sqlalchemy import text

    cid = str(rr_candidate_id or "").strip()
    if not cid:
        return {}
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT evaluation_snapshot FROM public.candidate WHERE candidate_id = :cid"),
            {"cid": cid},
        ).first()
        if not row:
            return {}
        snapshot = dict(row[0] or {}) if isinstance(row[0], dict) else {}
        if not snapshot and row[0]:
            snapshot = dict(row[0])
        agent5 = dict(snapshot.get("agent5") or {})
        runtime = dict(agent5.get(RUNTIME_KEY) or {})
        if bool(runtime.get("room_visit_open")):
            return runtime
        if room_join_count(runtime) >= MAX_ROOM_JOINS:
            raise HTTPException(status_code=403, detail=ROOM_REJOIN_BLOCKED)
        runtime.update(
            {
                "room_join_count": room_join_count(runtime) + 1,
                "room_visit_open": True,
                "left_by": None,
                "updated_at": _utcnow().isoformat(),
            }
        )
        agent5[RUNTIME_KEY] = runtime
        snapshot["agent5"] = agent5
        db.execute(
            text(
                "UPDATE public.candidate SET evaluation_snapshot = CAST(:snap AS jsonb) "
                "WHERE candidate_id = :cid"
            ),
            {"snap": json.dumps(snapshot), "cid": cid},
        )
        db.commit()
        return runtime


def close_room_visit(candidate: Candidate, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {"room_visit_open": False, **(extra or {})}
    return persist_runtime(candidate, payload)


def persist_runtime(candidate: Candidate, runtime: dict[str, Any]) -> dict[str, Any]:
    snapshot = dict(candidate.evaluation_snapshot or {})
    agent5 = dict(snapshot.get("agent5") or {})
    merged = dict(agent5.get(RUNTIME_KEY) or {})
    merged.update(runtime)
    merged["updated_at"] = _utcnow().isoformat()
    agent5[RUNTIME_KEY] = merged
    snapshot["agent5"] = agent5
    candidate.evaluation_snapshot = snapshot
    flag_modified(candidate, "evaluation_snapshot")
    return merged


async def set_runtime_state(
    db: AsyncSession,
    candidate_id: str,
    state: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate = await db.scalar(select(Candidate).where(Candidate.candidate_id == candidate_id))
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    payload = {"state": state, **(extra or {})}
    merged = persist_runtime(candidate, payload)
    await db.flush()
    if str(state or "").upper() in {COMPLETED, ENDED}:
        try:
            from services.interview_completion_service import mark_interview_completed

            await mark_interview_completed(db, candidate_id)
        except Exception:
            logger.exception("Failed to mark interview completed for %s", candidate_id)
    await _broadcast_runtime(candidate, merged)
    return merged


async def _broadcast_runtime(candidate: Candidate, runtime: dict[str, Any]) -> None:
    snapshot = dict(candidate.evaluation_snapshot or {})
    session_id = str((snapshot.get("agent5") or {}).get("session_id") or "")
    if not session_id:
        return
    try:
        from agents.proctoring_agent.api.ws import manager

        await manager.broadcast(
            session_id,
            {
                "type": "interview_runtime",
                "state": runtime.get("state"),
                "hr_speaking": bool(runtime.get("hr_speaking")),
                "hr_message": runtime.get("hr_message"),
            },
        )
    except Exception:
        logger.exception("Failed to broadcast interview runtime for session %s", session_id)


async def broadcast_ai_session(candidate: Candidate, session_payload: dict[str, Any]) -> None:
    """Push updated AI question state to all room clients (candidate + HR)."""
    snapshot = dict(candidate.evaluation_snapshot or {})
    session_id = str((snapshot.get("agent5") or {}).get("session_id") or "")
    if not session_id:
        return
    try:
        from agents.proctoring_agent.api.ws import manager

        await manager.broadcast(
            session_id,
            {"type": "ai_session", "session": session_payload},
        )
    except Exception:
        logger.exception("Failed to broadcast AI session for %s", candidate.candidate_id)


async def broadcast_mcq_session(candidate: Candidate, mcq_payload: dict[str, Any]) -> None:
    """Push MCQ test progress to candidate and HR room clients."""
    snapshot = dict(candidate.evaluation_snapshot or {})
    session_id = str((snapshot.get("agent5") or {}).get("session_id") or "")
    if not session_id:
        return
    try:
        from agents.proctoring_agent.api.ws import manager

        await manager.broadcast(
            session_id,
            {"type": "mcq_session", "mcq": mcq_payload},
        )
    except Exception:
        logger.exception("Failed to broadcast MCQ session for %s", candidate.candidate_id)
