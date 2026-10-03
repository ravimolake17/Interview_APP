from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ..dependencies import DbSession, require_candidate_session
from ..models import InterviewSession, RecordingChunk
from ..schemas import RecordingCompleteIn
from ..services.audit import audit, record_error
from ..services.finalization import finalize_session_artifacts
from ..services.reports import generate_report
from ..services.recordings import ingest_chunk, mark_recording_upload_complete, recording_status_payload
from .common import read_upload_limited, require_own_session, utcnow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions", tags=["recording"])


@router.post("/{session_id}/recording/chunks")
async def upload_chunk(
    session_id: str,
    db: DbSession,
    chunk: UploadFile = File(...),
    sequence: Annotated[int, Form(ge=0)] = 0,
    segment_id: Annotated[str, Form(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")] = "segment-0",
    segment_sequence: Annotated[int, Form(ge=0)] = 0,
    is_final: Annotated[bool, Form()] = False,
    captured_at: Annotated[datetime | None, Form()] = None,
    duration_ms: Annotated[int | None, Form(ge=0)] = None,
    checksum: Annotated[str | None, Form(max_length=64, pattern=r"^[A-Fa-f0-9]{64}$")] = None,
    auth_session: InterviewSession = Depends(require_candidate_session),
):
    session = require_own_session(auth_session, session_id)
    if session.status not in {"active", "terminated", "completed", "terminating"}:
        raise HTTPException(status_code=409, detail="recording chunks are not accepted in this session state")
    if session.recording_upload_complete:
        raise HTTPException(status_code=409, detail="recording upload is already marked complete")
    data = await read_upload_limited(chunk, allowed_prefixes=("video/webm", "video/mp4", "application/octet-stream"), kind="recording chunk")
    try:
        record, created = ingest_chunk(
            db,
            session.id,
            sequence,
            data,
            chunk.content_type or "video/webm",
            checksum,
            segment_id=segment_id,
            segment_sequence=segment_sequence,
            is_final=is_final,
            captured_at=captured_at,
            duration_ms=duration_ms,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return {
        "acknowledged": True,
        "created": created,
        "sequence": record.sequence,
        "segment_id": record.segment_id,
        "segment_sequence": record.segment_sequence,
        "is_final": record.is_final,
        "checksum": record.checksum,
        "size_bytes": record.size_bytes,
    }


@router.get("/{session_id}/recording/status")
def recording_status(session_id: str, db: DbSession, auth_session: InterviewSession = Depends(require_candidate_session)):
    session = require_own_session(auth_session, session_id)
    return recording_status_payload(db, session)


@router.post("/{session_id}/recording/complete")
def recording_complete(
    session_id: str,
    payload: RecordingCompleteIn,
    db: DbSession,
    auth_session: InterviewSession = Depends(require_candidate_session),
):
    session = require_own_session(auth_session, session_id)
    if session.status not in {"active", "terminating", "terminated", "completed"}:
        raise HTTPException(status_code=409, detail="recording completion is not accepted in this session state")
    try:
        status = mark_recording_upload_complete(db, session, payload.expected_total_chunks, payload.segment_ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    if not status["complete"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "recording queue is not fully drained",
                "missing_sequences": status["missing_sequences"],
                "unexpected_sequences": status["unexpected_sequences"],
                "missing_segments": status["missing_segments"],
                "unclosed_segments": status["unclosed_segments"],
                "premature_final_segments": status["premature_final_segments"],
                "unexpected_segments": status["unexpected_segments"],
            },
        )
    return status


@router.post("/{session_id}/recover-finalization")
def recover_finalization(
    session_id: str,
    db: DbSession,
    auth_session: InterviewSession = Depends(require_candidate_session),
):
    """Idempotently recover report/recording finalization after refresh or disconnect.

    The backend keeps the policy termination authoritative. Any queued chunks
    uploaded after reconnection are assembled when complete; otherwise an
    explicitly partial report is generated without inventing missing evidence.
    """
    session = require_own_session(auth_session, session_id)
    if session.status == "terminating":
        session.status = "terminated"
        session.termination_reason = session.termination_reason or "interrupted_termination_recovery"
        session.ended_at = session.ended_at or session.termination_requested_at or utcnow()
    if session.status not in {"completed", "terminated"}:
        raise HTTPException(status_code=409, detail="finalization recovery is available only for completed or terminated sessions")

    chunks = db.query(RecordingChunk).filter(RecordingChunk.session_id == session.id).order_by(RecordingChunk.sequence).all()
    recording_status = recording_status_payload(db, session)
    if chunks and not session.recording_upload_complete:
        expected_total = max(item.sequence for item in chunks) + 1
        segment_ids = list(dict.fromkeys(item.segment_id for item in chunks))
        try:
            recording_status = mark_recording_upload_complete(db, session, expected_total, segment_ids)
        except ValueError:
            recording_status = recording_status_payload(db, session, expected_total)

    artifacts: dict[str, object] = {}
    complete = bool(recording_status.get("complete"))
    try:
        if complete:
            artifacts = finalize_session_artifacts(db, session)
        else:
            report = generate_report(db, session.id)
            artifacts = {"report": report.id, "recording": None}
    except Exception as exc:
        record_error(db, "session_recovery_finalization", str(exc), session_id=session.id)
        db.commit()
        raise HTTPException(status_code=422, detail=f"finalization recovery failed: {exc}") from exc

    audit(
        db,
        "candidate",
        "interview_finalization_recovered",
        actor_id=session.candidate_id,
        target_type="session",
        target_id=session.id,
        details={"recording_complete": complete, "artifacts": artifacts},
    )
    db.commit()
    return {
        "status": session.status,
        "termination_reason": session.termination_reason,
        "recording_complete": complete,
        "report_completeness": "complete" if complete else "partial",
        "recording_status": recording_status,
        "artifacts": artifacts,
    }


@router.post("/{session_id}/finish")
def finish_session(
    session_id: str,
    db: DbSession,
    reason: Annotated[str, Form(max_length=120)] = "normal_completion",
    auth_session: InterviewSession = Depends(require_candidate_session),
):
    session = require_own_session(auth_session, session_id)
    chunks_exist = db.query(RecordingChunk.id).filter(RecordingChunk.session_id == session.id).first() is not None
    if not chunks_exist:
        raise HTTPException(status_code=409, detail="complete interview recording is missing")
    if not session.recording_upload_complete:
        status = recording_status_payload(db, session)
        raise HTTPException(
            status_code=409,
            detail={
                "message": "recording upload must complete before artifact finalization",
                "missing_sequences": status["missing_sequences"],
                "segments": status["segments"],
            },
        )

    if session.status == "completed" and reason == "normal_completion":
        try:
            artifacts = finalize_session_artifacts(db, session)
        except Exception as exc:
            record_error(db, "session_refinalization", str(exc), session_id=session.id)
            db.commit()
            raise HTTPException(status_code=422, detail=f"session is completed, but artifact refresh failed: {exc}") from exc
        db.commit()
        return {"status": session.status, "idempotent": True, "termination_reason": session.termination_reason, "artifacts": artifacts}

    final_reason = "repeated_tab_switch" if session.termination_reason == "repeated_tab_switch" else reason
    final_status = "completed" if final_reason == "normal_completion" else "terminated"
    original_status = session.status
    original_ended_at = session.ended_at
    session.status = final_status
    session.termination_reason = None if final_status == "completed" else final_reason
    session.ended_at = session.ended_at or utcnow()
    try:
        artifacts = finalize_session_artifacts(db, session)
    except Exception as exc:
        db.rollback()
        current = db.get(InterviewSession, session_id)
        if current is not None:
            current.status = original_status if original_status != "terminated" else "terminating"
            current.ended_at = original_ended_at
            record_error(db, "session_finalization", str(exc), session_id=current.id)
            db.commit()
        raise HTTPException(status_code=422, detail=f"artifact finalization failed; session remains pending: {exc}") from exc
    if final_status in {"completed", "terminated"}:
        try:
            from services.interview_completion_service import mark_interview_completed_by_agent5_session

            mark_interview_completed_by_agent5_session(db, session.id)
        except Exception:
            logger.exception("Failed to persist completed interview for session %s", session.id)
    audit(
        db,
        "candidate",
        "interview_finalized",
        actor_id=session.candidate_id,
        target_type="session",
        target_id=session.id,
        details={"reason": final_reason, **artifacts},
    )
    db.commit()
    return {
        "status": session.status,
        "termination_reason": session.termination_reason,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "artifacts": artifacts,
    }
