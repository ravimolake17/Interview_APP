"""Persist and run the interview-room MCQ phase on evaluation_snapshot.interview_mcq."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from agents.evaluation_agent.evaluator import build_candidate_context
from agents.interview_agent.mcq import (
    generate_mcq_questions,
    intro_message,
    mcq_duration_seconds,
    mcq_question_count,
    mcq_rules_message,
    oral_rules_message,
)
from models.candidate import Candidate
from repositories.blueprint_repository import BlueprintRepository
from repositories.company_repository import CompanyRepository
from repositories.interview_question_set_repository import InterviewQuestionSetRepository
from services.interview_room_service import broadcast_mcq_session

logger = logging.getLogger(__name__)

SNAPSHOT_KEY = "interview_mcq"
TERMINAL = {"completed", "timed_out"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    stamp = value or _utcnow()
    return stamp.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _record(candidate: Candidate) -> dict[str, Any] | None:
    snapshot = candidate.evaluation_snapshot if isinstance(candidate.evaluation_snapshot, dict) else {}
    data = snapshot.get(SNAPSHOT_KEY)
    return dict(data) if isinstance(data, dict) else None


def remaining_seconds(record: dict[str, Any]) -> int:
    duration = max(0, int(record.get("duration_seconds") or 0))
    status = str(record.get("status") or "")
    if status in TERMINAL:
        return 0
    if status != "in_progress":
        return duration
    started = _parse_iso(str(record.get("started_at") or ""))
    if not started:
        return duration
    elapsed = int((_utcnow() - started).total_seconds())
    return max(0, duration - elapsed)


def _public_question(question: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": question.get("id"),
        "order": int(question.get("order") or 0),
        "question_text": question.get("question_text") or "",
        "options": [
            {"id": str(opt.get("id") or ""), "text": str(opt.get("text") or "")}
            for opt in (question.get("options") or [])
            if isinstance(opt, dict)
        ],
    }


def _score(record: dict[str, Any]) -> dict[str, int]:
    questions = [q for q in (record.get("questions") or []) if isinstance(q, dict)]
    answered = 0
    skipped = 0
    correct = 0
    for question in questions:
        if question.get("skipped"):
            skipped += 1
            continue
        if question.get("answer_option_id"):
            answered += 1
            if str(question.get("answer_option_id")) == str(question.get("correct_option_id")):
                correct += 1
    return {
        "answered": answered,
        "skipped": skipped,
        "correct": correct,
        "total": len(questions),
    }


async def _company_name(db: AsyncSession, candidate: Candidate) -> str:
    if not candidate.company_id:
        return "RR Parkon"
    company = await CompanyRepository(db).get_by_id(int(candidate.company_id))
    return (company.name if company and company.name else "RR Parkon").strip() or "RR Parkon"


async def _planned_minutes(db: AsyncSession, candidate: Candidate) -> int:
    questions_repo = InterviewQuestionSetRepository(db)
    latest = await questions_repo.get_latest(candidate.candidate_id)
    if latest and latest.total_duration_minutes:
        return max(10, int(latest.total_duration_minutes))
    blueprint = await BlueprintRepository(db).get_latest_for_candidate(candidate.candidate_id)
    if blueprint:
        payload = blueprint.blueprint_json if isinstance(blueprint.blueprint_json, dict) else {}
        time_alloc = payload.get("time_allocation") if isinstance(payload.get("time_allocation"), dict) else {}
        duration = time_alloc.get("total_duration_minutes")
        try:
            if duration is not None:
                return max(10, int(duration))
        except (TypeError, ValueError):
            pass
    return 30


def _messages(record: dict[str, Any]) -> dict[str, str]:
    minutes = max(1, int(round(int(record.get("duration_seconds") or 300) / 60)))
    count = len([q for q in (record.get("questions") or []) if isinstance(q, dict)])
    return {
        "intro_message": str(record.get("intro_message") or ""),
        "rules_message": str(record.get("rules_message") or mcq_rules_message(minutes=minutes, count=count or 8)),
        "oral_rules_message": str(record.get("oral_rules_message") or oral_rules_message()),
    }


def public_state(record: dict[str, Any] | None, *, include_results: bool = False) -> dict[str, Any]:
    if not record:
        return {
            "status": "missing",
            "total_questions": 0,
            "current_index": 0,
            "remaining_seconds": 0,
            "duration_seconds": 0,
            "current_question": None,
            "intro_message": "",
            "rules_message": "",
            "oral_rules_message": oral_rules_message(),
        }
    questions = [q for q in (record.get("questions") or []) if isinstance(q, dict)]
    index = max(0, min(int(record.get("current_index") or 0), len(questions)))
    status = str(record.get("status") or "pending")
    current = None
    if status == "in_progress" and index < len(questions):
        current = _public_question(questions[index])
    elif status == "pending" and questions:
        current = _public_question(questions[0])
    payload = {
        "status": status,
        "total_questions": len(questions),
        "current_index": index,
        "remaining_seconds": remaining_seconds(record),
        "duration_seconds": int(record.get("duration_seconds") or 0),
        "current_question": current,
        **_messages(record),
    }
    if include_results and status in TERMINAL:
        payload["result"] = _score(record)
    return payload


async def _save(db: AsyncSession, candidate: Candidate, record: dict[str, Any], *, broadcast: bool = True) -> dict[str, Any]:
    snapshot = dict(candidate.evaluation_snapshot or {})
    snapshot[SNAPSHOT_KEY] = record
    candidate.evaluation_snapshot = snapshot
    flag_modified(candidate, "evaluation_snapshot")
    await db.flush()
    state = public_state(record)
    if broadcast:
        await broadcast_mcq_session(candidate, state)
    return record


def _expire_if_needed(record: dict[str, Any]) -> dict[str, Any]:
    if str(record.get("status") or "") != "in_progress":
        return record
    if remaining_seconds(record) > 0:
        return record
    record["status"] = "timed_out"
    record["completed_at"] = _iso()
    record["current_index"] = len([q for q in (record.get("questions") or []) if isinstance(q, dict)])
    return record


async def ensure_mcq(
    db: AsyncSession,
    candidate: Candidate,
    *,
    planned_minutes: int | None = None,
) -> dict[str, Any]:
    existing = _record(candidate)
    if existing and existing.get("questions"):
        before = str(existing.get("status") or "")
        existing = _expire_if_needed(existing)
        if str(existing.get("status") or "") != before:
            await _save(db, candidate, existing)
        return existing

    minutes = planned_minutes if planned_minutes is not None else await _planned_minutes(db, candidate)
    count = mcq_question_count(minutes)
    duration = mcq_duration_seconds(minutes)
    snap = candidate.evaluation_snapshot if isinstance(candidate.evaluation_snapshot, dict) else {}
    resume_context = build_candidate_context(
        jd_text=candidate.jd_text,
        evaluation_snapshot=snap,
        job_position=candidate.job_position,
    )
    questions = generate_mcq_questions(
        count=count,
        job_title=candidate.job_position,
        resume_context=resume_context,
        seed=candidate.candidate_id,
    )
    first_name = (candidate.full_name or "").split()[0] if candidate.full_name else "there"
    company = await _company_name(db, candidate)
    record = {
        "status": "pending",
        "duration_seconds": duration,
        "started_at": None,
        "completed_at": None,
        "current_index": 0,
        "intro_message": intro_message(
            first_name=first_name,
            company_name=company,
            role=candidate.job_position or "",
        ),
        "rules_message": mcq_rules_message(minutes=max(1, round(duration / 60)), count=len(questions)),
        "oral_rules_message": oral_rules_message(),
        "questions": questions,
    }
    await _save(db, candidate, record)
    return record


async def start_mcq(db: AsyncSession, candidate: Candidate, planned_minutes: int | None = None) -> dict[str, Any]:
    record = await ensure_mcq(db, candidate, planned_minutes=planned_minutes)
    record = _expire_if_needed(record)
    if str(record.get("status") or "") in TERMINAL:
        return await _save(db, candidate, record)
    if str(record.get("status") or "") != "in_progress":
        record["status"] = "in_progress"
        record["started_at"] = record.get("started_at") or _iso()
        record["current_index"] = int(record.get("current_index") or 0)
    return await _save(db, candidate, record)


async def submit_mcq(
    db: AsyncSession,
    candidate: Candidate,
    *,
    option_id: str | None = None,
    skip: bool = False,
    question_id: str | None = None,
) -> dict[str, Any]:
    record = await ensure_mcq(db, candidate)
    record = _expire_if_needed(record)
    if str(record.get("status") or "") in TERMINAL:
        return await _save(db, candidate, record)
    if str(record.get("status") or "") != "in_progress":
        raise ValueError("MCQ test has not started.")

    questions = [q for q in (record.get("questions") or []) if isinstance(q, dict)]
    index = int(record.get("current_index") or 0)
    if index >= len(questions):
        record["status"] = "completed"
        record["completed_at"] = _iso()
        return await _save(db, candidate, record)

    current = questions[index]
    if question_id and str(current.get("id") or "") != str(question_id).strip():
        return await _save(db, candidate, record)
    if current.get("answer_option_id") or current.get("skipped"):
        return await _save(db, candidate, record)
    else:
        if skip or not str(option_id or "").strip():
            current["skipped"] = True
            current["answer_option_id"] = None
        else:
            allowed = {str(opt.get("id") or "") for opt in (current.get("options") or []) if isinstance(opt, dict)}
            choice = str(option_id).strip().upper()
            if choice not in allowed:
                raise ValueError("Invalid option.")
            current["skipped"] = False
            current["answer_option_id"] = choice
        current["answered_at"] = _iso()
        questions[index] = current
        record["questions"] = questions
        record["current_index"] = index + 1

    if remaining_seconds(record) <= 0:
        record["status"] = "timed_out"
        record["completed_at"] = _iso()
    elif int(record.get("current_index") or 0) >= len(questions):
        record["status"] = "completed"
        record["completed_at"] = _iso()
    return await _save(db, candidate, record)


async def finish_mcq(db: AsyncSession, candidate: Candidate, *, timed_out: bool = False) -> dict[str, Any]:
    record = await ensure_mcq(db, candidate)
    if str(record.get("status") or "") not in TERMINAL:
        record["status"] = "timed_out" if timed_out else "completed"
        record["completed_at"] = _iso()
    return await _save(db, candidate, record)


async def get_mcq_state(db: AsyncSession, candidate: Candidate) -> dict[str, Any]:
    record = _record(candidate)
    if not record:
        return public_state(None)
    record = _expire_if_needed(record)
    await _save(db, candidate, record, broadcast=False)
    return public_state(record)
