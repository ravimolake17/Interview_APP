from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from ..config import get_settings
from ..dependencies import DbSession, require_hr_reviewer
from ..models import AuditLog, Candidate, FraudEvent, InterviewSession, Recording, Report, ReviewDecision, SystemError
from ..schemas import ReviewIn
from ..services.audit import audit, record_error
from ..services.risk import calculate_score
from ..services.reports import build_report_data, generate_report
from ..services.retention import delete_session_data

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/login")
def login(_: DbSession):
    raise HTTPException(status_code=403, detail="Agent5 admin login is disabled. Use the main HR application.")


@router.post("/media-token")
def media_token(reviewer: dict = Depends(require_hr_reviewer)):
    """HR JWT is accepted directly for media URLs."""
    return {"token": None, "use_hr_token": True, "reviewer_id": reviewer.get("sub")}


@router.get("/sessions")
def list_sessions(
    db: DbSession,
    reviewer: dict = Depends(require_hr_reviewer),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    risk: str | None = None,
    search: str | None = None,
):
    conditions = []
    if status:
        conditions.append(InterviewSession.status == status)
    if risk:
        normalized_risk = "moderate" if risk == "medium" else risk
        if normalized_risk not in {"low", "moderate", "high", "critical"}:
            raise HTTPException(status_code=422, detail="risk must be low, moderate, high, or critical")
        conditions.append(InterviewSession.risk_classification == normalized_risk)
    if search:
        term = f"%{search.strip()}%"
        conditions.append(or_(Candidate.full_name.ilike(term), Candidate.email.ilike(term), InterviewSession.id.ilike(term)))
    query = select(InterviewSession).join(Candidate).options(selectinload(InterviewSession.candidate)).order_by(InterviewSession.created_at.desc())
    count_query = select(func.count()).select_from(InterviewSession).join(Candidate)
    for condition in conditions:
        query = query.where(condition)
        count_query = count_query.where(condition)
    total = db.scalar(count_query) or 0
    sessions = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": [
            {
                "id": item.id,
                "candidate": {"id": item.candidate.id, "full_name": item.candidate.full_name, "email": item.candidate.email},
                "status": item.status,
                "started_at": item.started_at.isoformat() if item.started_at else None,
                "ended_at": item.ended_at.isoformat() if item.ended_at else None,
                "termination_reason": item.termination_reason,
                "risk_score": item.risk_score,
                "risk_classification": item.risk_classification,
                "tab_switch_count": item.tab_switch_count,
            }
            for item in sessions
        ],
    }


@router.get("/sessions/{session_id}")
def session_detail(session_id: str, db: DbSession, reviewer: dict = Depends(require_hr_reviewer)):
    try:
        data = build_report_data(db, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    errors = db.scalars(select(SystemError).where(SystemError.session_id == session_id).order_by(SystemError.created_at)).all()
    data["system_errors"] = [{"id": e.id, "component": e.component, "message": e.message, "details": e.details, "resolved": e.resolved, "created_at": e.created_at.isoformat()} for e in errors]
    return data


@router.post("/sessions/{session_id}/report/regenerate")
def regenerate_report(session_id: str, db: DbSession, reviewer: dict = Depends(require_hr_reviewer)):
    session = db.get(InterviewSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    try:
        report = generate_report(db, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        record_error(db, "admin_report_generation", str(exc), session_id=session_id)
        db.commit()
        raise HTTPException(status_code=422, detail=f"report generation failed: {exc}") from exc
    audit(db, "admin", "report_regenerated", actor_id=str(reviewer.get("sub", "hr")), target_type="session", target_id=session_id)
    db.commit()
    return {
        "report_id": report.id,
        "json_url": f"/api/media/report/{report.id}/json",
        "html_url": f"/api/media/report/{report.id}/html",
        "pdf_url": f"/api/media/report/{report.id}/pdf",
        "checksums": {
            "json": report.json_checksum,
            "html": report.html_checksum,
            "pdf": report.pdf_checksum,
        },
        "integrity_manifest": report.integrity_manifest,
    }


@router.post("/sessions/{session_id}/review")
def review_session(session_id: str, payload: ReviewIn, db: DbSession, reviewer: dict = Depends(require_hr_reviewer)):
    session = db.get(InterviewSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    reviewer_id = str(reviewer.get("sub", "hr"))
    review = db.scalar(
        select(ReviewDecision)
        .where(ReviewDecision.session_id == session_id, ReviewDecision.admin_id == reviewer_id)
        .order_by(ReviewDecision.created_at.desc())
    )
    action = "session_review_updated"
    if review is None:
        review = ReviewDecision(session_id=session_id, admin_id=reviewer_id, decision=payload.decision, notes=payload.notes)
        db.add(review)
        action = "session_review_created"
    else:
        review.decision = payload.decision
        review.notes = payload.notes
    audit(db, "admin", action, actor_id=reviewer_id, target_type="session", target_id=session_id, details=payload.model_dump())
    db.commit()
    db.refresh(review)
    return {"id": review.id, "decision": review.decision, "notes": review.notes, "updated": action == "session_review_updated"}


@router.patch("/events/{event_id}/review")
def review_event(event_id: str, status: str, db: DbSession, reviewer: dict = Depends(require_hr_reviewer)):
    if status not in {"pending", "confirmed", "dismissed"}:
        raise HTTPException(status_code=422, detail="invalid event review status")
    event = db.get(FraudEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    event.review_status = status
    audit(db, "admin", "event_reviewed", actor_id=str(reviewer.get("sub", "hr")), target_type="fraud_event", target_id=event.id, details={"status": status})
    db.flush()
    events = db.scalars(select(FraudEvent).where(FraudEvent.session_id == event.session_id).order_by(FraudEvent.server_timestamp)).all()
    adjusted_score, adjusted_classification, adjusted_contributions = calculate_score(
        item for item in events if item.review_status != "dismissed"
    )
    db.commit()
    return {
        "id": event.id,
        "review_status": event.review_status,
        "automated_score_preserved": True,
        "review_adjusted_score": adjusted_score,
        "review_adjusted_classification": adjusted_classification,
        "review_adjusted_contributions_by_type": adjusted_contributions,
    }


@router.get("/audit")
def list_audit(db: DbSession, reviewer: dict = Depends(require_hr_reviewer), limit: int = Query(100, ge=1, le=500)):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [{"id": r.id, "actor_type": r.actor_type, "actor_id": r.actor_id, "action": r.action, "target_type": r.target_type, "target_id": r.target_id, "details": r.details, "created_at": r.created_at.isoformat()} for r in rows]


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: DbSession, reviewer: dict = Depends(require_hr_reviewer), best_effort_overwrite: bool = False):
    settings = get_settings()
    session = db.get(InterviewSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    audit(db, "admin", "session_deletion_requested", actor_id=str(reviewer.get("sub", "hr")), target_type="session", target_id=session_id, details={"best_effort_overwrite": best_effort_overwrite})
    db.commit()
    deleted = delete_session_data(db, session_id, settings.resolved_storage_dir, overwrite=best_effort_overwrite)
    return {"deleted": deleted, "session_id": session_id, "note": "Best-effort local deletion; storage-device remanence cannot be guaranteed."}
