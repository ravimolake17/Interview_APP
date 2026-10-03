"""Manual add / edit / reorder helpers for the Agent 4 question bank."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from agents.interview_agent.question_generator import shorten_question
from agents.interview_agent.schemas import InterviewQuestion

CATEGORY_OPTIONS: list[tuple[str, str]] = [
    ("introductory_questions", "Introductory Questions"),
    ("experience_questions", "Experience Questions"),
    ("skills_jd_keyword_questions", "Skills & JD Keyword-Related Questions"),
    ("project_related_questions", "Project-Related Questions"),
    ("education_courses_questions", "Education & Courses Questions"),
]

CATEGORY_NAMES = {cid: name for cid, name in CATEGORY_OPTIONS}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}
QUESTION_EDIT_LOCK_MINUTES = 10


class QuestionBankLockedError(Exception):
    """Raised when add/update/delete is blocked by interview timing."""

    def __init__(self, reason: str, *, policy: dict[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.policy = policy or {}


def question_edit_policy(
    *,
    now: datetime,
    start_at: datetime | None,
    interview_status: str | None = None,
    live_started: bool = False,
    lock_minutes: int = QUESTION_EDIT_LOCK_MINUTES,
) -> dict[str, Any]:
    """Allow edits only until `lock_minutes` before the scheduled start."""
    status = str(interview_status or "").strip().upper()
    if live_started:
        return {
            "allowed": False,
            "reason": "Questions cannot be changed after the interview has started.",
            "lock_at": None,
            "interview_start_at": start_at,
            "lock_minutes": lock_minutes,
        }
    if status == "COMPLETED":
        return {
            "allowed": False,
            "reason": "Questions cannot be changed after the interview is completed.",
            "lock_at": None,
            "interview_start_at": start_at,
            "lock_minutes": lock_minutes,
        }
    if start_at is None:
        return {
            "allowed": True,
            "reason": None,
            "lock_at": None,
            "interview_start_at": None,
            "lock_minutes": lock_minutes,
        }
    if now.tzinfo is not None and start_at.tzinfo is None:
        start_at = start_at.replace(tzinfo=now.tzinfo)
    elif now.tzinfo is None and start_at.tzinfo is not None:
        now = now.replace(tzinfo=start_at.tzinfo)
    lock_at = start_at - timedelta(minutes=max(0, int(lock_minutes)))
    if now >= start_at:
        reason = "Questions cannot be changed after the interview has started."
        allowed = False
    elif now >= lock_at:
        reason = (
            f"Questions cannot be changed in the last {lock_minutes} minutes before the interview."
        )
        allowed = False
    else:
        reason = None
        allowed = True
    return {
        "allowed": allowed,
        "reason": reason,
        "lock_at": lock_at,
        "interview_start_at": start_at,
        "lock_minutes": lock_minutes,
    }


def _as_dict(question: Any) -> dict[str, Any]:
    if hasattr(question, "model_dump"):
        return question.model_dump(mode="json")
    return dict(question or {})


def _clamp_position(insert_at: int | None, count: int, *, allow_append: bool) -> int:
    upper = count + 1 if allow_append else max(count, 1)
    if insert_at is None:
        return count + 1 if allow_append else max(count, 1)
    return max(1, min(int(insert_at), upper))


def _normalize_category(category_id: str | None, category_name: str | None) -> tuple[str, str]:
    cid = str(category_id or "").strip() or "skills_jd_keyword_questions"
    if cid not in CATEGORY_NAMES:
        cid = "skills_jd_keyword_questions"
    name = str(category_name or "").strip() or CATEGORY_NAMES[cid]
    return cid, name


def _normalize_difficulty(difficulty: str | None) -> str:
    value = str(difficulty or "medium").strip().lower()
    return value if value in VALID_DIFFICULTIES else "medium"


def renumber_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, raw in enumerate(questions, start=1):
        item = dict(raw)
        item["order"] = index
        out.append(item)
    return out


def build_manual_question(
    *,
    question_text: str,
    order: int,
    category_id: str | None = None,
    category_name: str | None = None,
    difficulty: str | None = None,
    skill_tags: list[str] | None = None,
    estimated_seconds: int = 120,
    question_id: str | None = None,
) -> dict[str, Any]:
    cid, cname = _normalize_category(category_id, category_name)
    text = shorten_question(question_text, 40)
    if len(text) < 8:
        raise ValueError("Question text is too short.")
    tags = [str(tag).strip() for tag in (skill_tags or []) if str(tag).strip()][:5]
    question = InterviewQuestion(
        id=question_id or f"q-{uuid.uuid4().hex[:10]}",
        order=max(1, order),
        category_id=cid,
        category_name=cname,
        difficulty=_normalize_difficulty(difficulty),  # type: ignore[arg-type]
        question_text=text,
        intent="Manually added by interviewer.",
        follow_up_hints=["Ask for one concrete example."],
        estimated_seconds=max(30, min(int(estimated_seconds or 120), 600)),
        skill_tags=tags,
    )
    return question.model_dump(mode="json")


def insert_manual_question(
    questions: list[Any],
    *,
    question_text: str,
    insert_at: int | None = None,
    category_id: str | None = None,
    category_name: str | None = None,
    difficulty: str | None = None,
    skill_tags: list[str] | None = None,
    estimated_seconds: int = 120,
) -> list[dict[str, Any]]:
    items = [_as_dict(item) for item in questions]
    position = _clamp_position(insert_at, len(items), allow_append=True)
    new_question = build_manual_question(
        question_text=question_text,
        order=position,
        category_id=category_id,
        category_name=category_name,
        difficulty=difficulty,
        skill_tags=skill_tags,
        estimated_seconds=estimated_seconds,
    )
    items.insert(position - 1, new_question)
    return renumber_questions(items)


def update_manual_question(
    questions: list[Any],
    question_id: str,
    *,
    question_text: str | None = None,
    insert_at: int | None = None,
    category_id: str | None = None,
    category_name: str | None = None,
    difficulty: str | None = None,
    skill_tags: list[str] | None = None,
    estimated_seconds: int | None = None,
) -> list[dict[str, Any]]:
    items = [_as_dict(item) for item in questions]
    index = next((i for i, item in enumerate(items) if str(item.get("id") or "") == question_id), None)
    if index is None:
        raise ValueError("Question not found in this set.")
    current = items.pop(index)
    if question_text is not None:
        text = shorten_question(question_text, 40)
        if len(text) < 8:
            raise ValueError("Question text is too short.")
        current["question_text"] = text
    if category_id is not None or category_name is not None:
        cid, cname = _normalize_category(
            category_id if category_id is not None else current.get("category_id"),
            category_name if category_name is not None else current.get("category_name"),
        )
        current["category_id"] = cid
        current["category_name"] = cname
    if difficulty is not None:
        current["difficulty"] = _normalize_difficulty(difficulty)
    if skill_tags is not None:
        current["skill_tags"] = [str(tag).strip() for tag in skill_tags if str(tag).strip()][:5]
    if estimated_seconds is not None:
        current["estimated_seconds"] = max(30, min(int(estimated_seconds), 600))
    position = _clamp_position(insert_at, len(items) + 1, allow_append=True)
    if insert_at is None:
        position = min(index + 1, len(items) + 1)
    items.insert(position - 1, current)
    return renumber_questions(items)


def delete_manual_question(questions: list[Any], question_id: str) -> list[dict[str, Any]]:
    items = [_as_dict(item) for item in questions]
    kept = [item for item in items if str(item.get("id") or "") != question_id]
    if len(kept) == len(items):
        raise ValueError("Question not found in this set.")
    return renumber_questions(kept)
