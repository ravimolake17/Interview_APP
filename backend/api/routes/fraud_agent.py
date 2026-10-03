"""Bridge Agent 5 (fraud detection) to RR Parkon candidates and interviews."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from agents.proctoring_agent.integration import agent5_ready, startup_agent5
from api.deps import get_current_user
from api.tenancy import accessible_candidate
from models.candidate import Candidate
from core.config import get_settings
from core.database import get_db
from models.candidate import Candidate
from models.user import User
from repositories.company_repository import CompanyRepository
from repositories.interview_repository import InterviewRepository
from services.agent5_bootstrap_service import bootstrap_agent5_session, snapshot_payload_from_bootstrap

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/interview/agent5", tags=["Agent 5 — Fraud Detection"])
settings = get_settings()


class FraudBootstrapResponse(BaseModel):
    candidate_id: str
    agent5_session_id: str
    agent5_token: str
    proctoring_url: str
    monitor_url: str
    ready: bool
    message: str


class FraudStatusResponse(BaseModel):
    candidate_id: str
    enabled: bool
    ready: bool
    agent5_session_id: str | None = None
    risk_score: float | None = None
    risk_classification: str | None = None
    session_status: str | None = None
    join_link: str | None = None
    verification_status: str | None = None


class Agent5ReportResponse(BaseModel):
    candidate_id: str
    agent5_session_id: str | None = None
    report: dict[str, Any] | None = None
    message: str | None = None


def _recover_agent5_from_audit(rr_candidate_id: str) -> dict[str, Any] | None:
    """Find the latest Agent5 session linked to an RR candidate when snapshot metadata was lost."""
    try:
        from sqlalchemy import desc, select

        from agents.proctoring_agent.db import SessionLocal
        from agents.proctoring_agent.models import AuditLog as Agent5AuditLog

        with SessionLocal() as agent_db:
            row = agent_db.scalar(
                select(Agent5AuditLog)
                .where(
                    Agent5AuditLog.action == "candidate_registered_from_rr",
                    Agent5AuditLog.actor_id == rr_candidate_id,
                )
                .order_by(desc(Agent5AuditLog.created_at))
                .limit(1)
            )
            if row and row.target_id:
                return {"session_id": str(row.target_id)}
    except Exception:
        logger.debug(
            "Could not recover Agent5 session from audit for %s",
            rr_candidate_id,
            exc_info=True,
        )
    return None


def _snapshot_agent5(candidate: Candidate) -> dict[str, Any]:
    snapshot = dict(candidate.evaluation_snapshot or {})
    meta = dict(snapshot.get("agent5") or {})
    if meta.get("session_id"):
        return meta
    recovered = _recover_agent5_from_audit(candidate.candidate_id)
    if recovered:
        meta.update(recovered)
    return meta


def _persist_agent5_snapshot(candidate: Candidate, payload: dict[str, Any]) -> None:
    snapshot = dict(candidate.evaluation_snapshot or {})
    snapshot["agent5"] = payload
    candidate.evaluation_snapshot = snapshot
    flag_modified(candidate, "evaluation_snapshot")


@router.get("/ready")
async def fraud_detection_ready() -> dict[str, object]:
    startup = startup_agent5()
    return {
        "enabled": bool(startup.get("ok")),
        "ready": agent5_ready(),
        "startup": startup,
        "proctoring_ui": "/proctoring/",
        "docs": "/docs",
    }


@router.get("/candidates/{candidate_id}/status", response_model=FraudStatusResponse)
async def fraud_status(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    _tenant: Candidate = Depends(accessible_candidate),
) -> FraudStatusResponse:
    candidate = await db.scalar(
        select(Candidate).where(Candidate.candidate_id == candidate_id)
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    meta = _snapshot_agent5(candidate)
    session_id = meta.get("session_id")
    if session_id and not (dict(candidate.evaluation_snapshot or {}).get("agent5") or {}).get("session_id"):
        _persist_agent5_snapshot(candidate, meta)
        await db.flush()

    risk_score = None
    risk_class = None
    session_status = None

    if session_id and startup_agent5().get("ok"):
        try:
            from agents.proctoring_agent.db import SessionLocal
            from agents.proctoring_agent.models import InterviewSession as Agent5Session

            with SessionLocal() as agent_db:
                session = agent_db.get(Agent5Session, str(session_id))
                if session:
                    risk_score = float(session.risk_score)
                    risk_class = session.risk_classification
                    session_status = session.status
        except Exception:
            logger.debug("Could not load Agent5 session %s", session_id, exc_info=True)

    interview = await InterviewRepository(db).get_by_candidate_id(candidate_id)
    join_link = meta.get("join_link")
    verification_status = session_status or "not_started"

    return FraudStatusResponse(
        candidate_id=candidate_id,
        enabled=bool(startup_agent5().get("ok")),
        ready=agent5_ready(),
        agent5_session_id=str(session_id) if session_id else None,
        risk_score=risk_score,
        risk_classification=risk_class,
        session_status=session_status,
        join_link=join_link,
        verification_status=verification_status,
    )


@router.get("/candidates/{candidate_id}/report", response_model=Agent5ReportResponse)
async def fraud_session_report(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    _tenant: Candidate = Depends(accessible_candidate),
) -> Agent5ReportResponse:
    candidate = await db.scalar(
        select(Candidate).where(Candidate.candidate_id == candidate_id)
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    meta = _snapshot_agent5(candidate)
    session_id = meta.get("session_id")
    if session_id and not (dict(candidate.evaluation_snapshot or {}).get("agent5") or {}).get("session_id"):
        _persist_agent5_snapshot(candidate, meta)
        await db.flush()

    if not session_id:
        return Agent5ReportResponse(
            candidate_id=candidate_id,
            agent5_session_id=None,
            report=None,
            message="No Agent5 session exists for this candidate yet.",
        )

    try:
        from agents.proctoring_agent.db import SessionLocal
        from agents.proctoring_agent.services.reports import build_report_data

        with SessionLocal() as agent_db:
            report = build_report_data(agent_db, str(session_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to load Agent5 report for %s", candidate_id)
        raise HTTPException(status_code=500, detail=f"Failed to load report: {exc}") from exc

    return Agent5ReportResponse(
        candidate_id=candidate_id,
        agent5_session_id=str(session_id),
        report=report,
    )


@router.post("/candidates/{candidate_id}/bootstrap", response_model=FraudBootstrapResponse)
async def bootstrap_fraud_session(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    _tenant: Candidate = Depends(accessible_candidate),
) -> FraudBootstrapResponse:
    """HR-only troubleshooting bootstrap for Agent5."""
    candidate = await db.scalar(
        select(Candidate).where(Candidate.candidate_id == candidate_id)
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    meta = _snapshot_agent5(candidate)
    company = (
        await CompanyRepository(db).get_by_id(candidate.company_id)
        if candidate.company_id
        else None
    )
    try:
        payload = bootstrap_agent5_session(
            candidate_id=candidate.candidate_id,
            full_name=candidate.full_name,
            email=candidate.email,
            existing_snapshot=meta,
            company_code=company.code if company else None,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    merged = dict(meta)
    merged.update(snapshot_payload_from_bootstrap(payload))
    _persist_agent5_snapshot(candidate, merged)
    await db.commit()

    return FraudBootstrapResponse(
        candidate_id=candidate_id,
        agent5_session_id=str(payload["agent5_session_id"]),
        agent5_token=str(payload["agent5_token"]),
        proctoring_url=str(payload["proctoring_url"]),
        monitor_url=str(payload["monitor_url"]),
        ready=bool(payload["ready"]),
        message=(
            "Reusing existing Agent5 session."
            if payload.get("reused")
            else "Agent5 session created for HR troubleshooting."
        ),
    )
