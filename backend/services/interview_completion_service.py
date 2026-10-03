"""Mark and detect candidates who actually finished their interview."""

from __future__ import annotations

import logging

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.candidate import Candidate, CandidateStatus
from models.hr_recommendation_report import HrRecommendationReport
from models.interview import Interview, InterviewStatus
from models.interview_evaluation import InterviewEvaluation

logger = logging.getLogger(__name__)

_FINISHED_RUNTIME = frozenset({"COMPLETED", "ENDED"})
_FINISHED_AGENT5 = frozenset({"completed", "terminated"})


def _runtime_from_snapshot(snapshot: dict | None) -> dict:
    snap = snapshot if isinstance(snapshot, dict) else {}
    agent5 = snap.get("agent5") if isinstance(snap.get("agent5"), dict) else {}
    runtime = agent5.get("interview_runtime")
    if isinstance(runtime, dict):
        return runtime
    root = snap.get("interview_runtime")
    return root if isinstance(root, dict) else {}


def snapshot_shows_completed(snapshot: dict | None) -> bool:
    """True when the in-room runtime already finished (completed or left)."""
    runtime = _runtime_from_snapshot(snapshot)
    return str(runtime.get("state") or "").upper() in _FINISHED_RUNTIME


def agent5_session_id_from_snapshot(snapshot: dict | None) -> str | None:
    snap = snapshot if isinstance(snapshot, dict) else {}
    agent5 = snap.get("agent5") if isinstance(snap.get("agent5"), dict) else {}
    session_id = str(agent5.get("session_id") or "").strip()
    if session_id:
        return session_id
    runtime = _runtime_from_snapshot(snap)
    extra = str(runtime.get("agent5_session_id") or "").strip()
    return extra or None


async def _agent5_session_finished(db: AsyncSession, session_id: str | None) -> bool:
    if not session_id:
        return False
    try:
        row = (
            await db.execute(
                text(
                    """
                    SELECT status, started_at
                    FROM agent5.sessions
                    WHERE id = :sid
                    LIMIT 1
                    """
                ),
                {"sid": session_id},
            )
        ).first()
    except Exception:
        logger.debug("Agent 5 session lookup skipped for %s", session_id, exc_info=True)
        return False
    if not row:
        return False
    status = str(row[0] or "").strip().lower()
    started = row[1] is not None
    return started and status in _FINISHED_AGENT5


async def has_finished_interview(db: AsyncSession, candidate: Candidate) -> bool:
    """True when the candidate actually sat the interview and the session ended."""
    if candidate.status == CandidateStatus.INTERVIEW_COMPLETED:
        return True
    if snapshot_shows_completed(candidate.evaluation_snapshot):
        return True

    interview = (
        await db.execute(
            select(Interview)
            .where(Interview.candidate_id == candidate.candidate_id)
            .order_by(Interview.created_at.desc())
        )
    ).scalars().first()
    if interview and interview.status == InterviewStatus.COMPLETED:
        return True

    if await _agent5_session_finished(
        db, agent5_session_id_from_snapshot(candidate.evaluation_snapshot)
    ):
        return True

    eval_count = await db.scalar(
        select(func.count())
        .select_from(InterviewEvaluation)
        .where(InterviewEvaluation.candidate_id == candidate.candidate_id)
    )
    report = (
        await db.execute(
            select(HrRecommendationReport)
            .where(HrRecommendationReport.candidate_id == candidate.candidate_id)
            .order_by(HrRecommendationReport.updated_at.desc())
        )
    ).scalars().first()
    # Stale live runtime after a crash/tab-switch: answers or Agent 7 interview
    # scores mean the interview already happened.
    if int(eval_count or 0) > 0 and report is not None:
        return True
    if report is not None and float(report.interview_score or 0) > 0:
        return True
    return False


async def mark_interview_completed(db: AsyncSession, candidate_id: str) -> bool:
    """Persist Interview COMPLETED and Candidate INTERVIEW_COMPLETED."""
    candidate = await db.scalar(select(Candidate).where(Candidate.candidate_id == candidate_id))
    if candidate is None:
        return False

    interview = (
        await db.execute(
            select(Interview)
            .where(Interview.candidate_id == candidate_id)
            .order_by(Interview.created_at.desc())
        )
    ).scalars().first()
    if interview and interview.status != InterviewStatus.COMPLETED:
        interview.status = InterviewStatus.COMPLETED

    if candidate.status != CandidateStatus.REJECTED:
        candidate.status = CandidateStatus.INTERVIEW_COMPLETED
    await db.flush()
    return True


async def sync_completed_interviews(
    db: AsyncSession, *, company_id: int | None = None
) -> int:
    """Backfill candidates who finished but were left as Interview Scheduled."""
    updated = 0

    interview_query = select(Interview).where(Interview.status == InterviewStatus.COMPLETED)
    if company_id is not None:
        interview_query = interview_query.where(Interview.company_id == company_id)
    completed_interviews = list((await db.execute(interview_query)).scalars().all())
    for interview in completed_interviews:
        candidate = await db.scalar(
            select(Candidate).where(Candidate.candidate_id == interview.candidate_id)
        )
        if candidate is None:
            continue
        if candidate.status in {CandidateStatus.INTERVIEW_COMPLETED, CandidateStatus.REJECTED}:
            continue
        candidate.status = CandidateStatus.INTERVIEW_COMPLETED
        updated += 1

    scheduled_query = select(Candidate).where(
        Candidate.status == CandidateStatus.INTERVIEW_SCHEDULED
    )
    if company_id is not None:
        scheduled_query = scheduled_query.where(Candidate.company_id == company_id)
    for candidate in (await db.execute(scheduled_query)).scalars().all():
        if not await has_finished_interview(db, candidate):
            continue
        await mark_interview_completed(db, candidate.candidate_id)
        updated += 1

    if updated:
        await db.flush()
        logger.info("Synced %s completed interview candidate(s)", updated)
    return updated


def mark_interview_completed_by_agent5_session(session, session_id: str) -> None:
    """Best-effort sync path from Agent 5's SQLAlchemy session."""
    if not session_id:
        return
    try:
        from sqlalchemy import text as sql_text

        row = session.execute(
            sql_text(
                """
                SELECT candidate_id
                FROM candidate
                WHERE evaluation_snapshot->'agent5'->>'session_id' = :sid
                   OR evaluation_snapshot->'agent5'->'interview_runtime'->>'agent5_session_id' = :sid
                LIMIT 1
                """
            ),
            {"sid": session_id},
        ).first()
        if not row:
            return
        candidate_id = row[0]
        session.execute(
            sql_text(
                """
                UPDATE interview
                SET status = 'COMPLETED'
                WHERE candidate_id = :cid AND status <> 'COMPLETED'
                """
            ),
            {"cid": candidate_id},
        )
        session.execute(
            sql_text(
                """
                UPDATE candidate
                SET status = 'INTERVIEW_COMPLETED'
                WHERE candidate_id = :cid AND status <> 'REJECTED'
                """
            ),
            {"cid": candidate_id},
        )
    except Exception:
        logger.exception(
            "Failed to mark interview completed for Agent 5 session %s", session_id
        )
