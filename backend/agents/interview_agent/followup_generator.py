"""Follow-up question generation from candidate answers."""

from __future__ import annotations

import re
import uuid
from typing import Any

from agents.interview_agent.question_generator import shorten_question
from agents.interview_agent.schemas import FollowUpQuestion

_THIN_ANSWER = re.compile(
    r"\b(i don'?t know|dont know|no idea|not sure|skip(?: it)?|pass|"
    r"no comment|nothing|can'?t answer|cannot answer|no answer)\b",
    re.IGNORECASE,
)


def answer_is_thin(text: str) -> bool:
    cleaned = (text or "").strip()
    if len(cleaned.split()) < 18:
        return True
    return bool(_THIN_ANSWER.search(cleaned))


def answer_warrants_followup(
    text: str,
    evaluation: dict[str, Any] | None,
    *,
    is_followup: bool,
) -> bool:
    """Follow up only when the candidate answered, but left a useful gap."""
    if is_followup or answer_is_thin(text):
        return False
    eval_data = evaluation or {}
    verdict = str(eval_data.get("verdict") or "").lower()
    if verdict in {"insufficient", "off_topic", "strong"}:
        return False
    words = len((text or "").split())
    if words < 30:
        return False
    return bool(eval_data.get("suggest_followup")) and verdict in {"weak", "adequate"}


def build_turn_ack(
    *,
    evaluation: dict[str, Any] | None = None,
    next_question: dict[str, Any] | None = None,
    unanswered: bool = False,
    next_is_followup: bool = False,
) -> str:
    """Short spoken thank-you plus a bridge into the next question."""
    verdict = str((evaluation or {}).get("verdict") or "").lower()
    if unanswered:
        thanks = "Thank you. We can skip that for now."
    elif verdict == "strong":
        thanks = "Thank you, that was a helpful example."
    elif verdict == "adequate":
        thanks = "Thank you for walking me through that."
    else:
        thanks = "Thank you for sharing that."

    if not next_question:
        return thanks
    if next_is_followup:
        return f"{thanks} One quick follow-up."

    skill = ""
    tags = list(next_question.get("skill_tags") or [])
    if tags:
        skill = str(tags[0]).strip()
    skip_skill = skill.casefold() in {
        "",
        "core skills",
        "the required skill",
        "your experience",
        "this role",
        "your project",
        "your coursework",
    }
    if skill and not skip_skill:
        return f"{thanks} Next, a short question on {skill}."
    category = str(next_question.get("category_name") or "the next topic").strip()
    return f"{thanks} Let's move to {category.lower()}."


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p.strip() for p in parts if len(p.strip()) > 12]


def generate_followups(
    *,
    question_id: str,
    question_text: str,
    candidate_answer: str,
    max_followups: int = 2,
    skill_hints: list[str] | None = None,
) -> list[FollowUpQuestion]:
    """Create adaptive follow-ups from the transcribed answer (rule + template)."""
    answer = (candidate_answer or "").strip()
    if not answer or answer_is_thin(answer):
        return []

    followups: list[FollowUpQuestion] = []
    sentences = _sentences(answer)
    skills = [s for s in (skill_hints or []) if s][:3]
    lower = answer.lower()

    probes: list[tuple[str, str, str]] = []

    if any(w in lower for w in ("we ", "team", "they ")):
        probes.append(
            (
                "You mentioned working with others — what was specifically your contribution versus the team's?",
                "Clarify individual ownership.",
                "medium",
            )
        )
    if any(w in lower for w in ("challenge", "issue", "problem", "bug", "fail")):
        probes.append(
            (
                "What was the root cause of that challenge, and how did you verify the fix worked?",
                "Dig into problem-solving depth.",
                "hard",
            )
        )
    if any(w in lower for w in ("scale", "performance", "latency", "optim")):
        probes.append(
            (
                "What metrics improved after your change, and by how much?",
                "Push for measurable impact.",
                "hard",
            )
        )
    if skills:
        skill = skills[0]
        if skill.lower() not in lower:
            probes.append(
                (
                    f"How does that experience connect to {skill}, which this role emphasizes?",
                    f"Bridge answer to required skill {skill}.",
                    "medium",
                )
            )
        else:
            probes.append(
                (
                    f"You referenced {skill} — walk me through one concrete decision you made using it.",
                    f"Deepen {skill} evidence.",
                    "medium",
                )
            )

    if sentences and len(sentences[0].split()) <= 18:
        probes.append(
            (
                "What happened next, in one concrete step?",
                "Expand on a specific claim from the answer.",
                "easy",
            )
        )

    seen: set[str] = set()
    for text, reason, difficulty in probes:
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        followups.append(
            FollowUpQuestion(
                id=f"fu-{uuid.uuid4().hex[:10]}",
                parent_question_id=question_id,
                question_text=text,
                reason=reason,
                difficulty=difficulty,  # type: ignore[arg-type]
            )
        )
        if len(followups) >= max_followups:
            break

    return [
        item.model_copy(update={"question_text": shorten_question(item.question_text, 16)})
        for item in followups
    ]


def enrich_followups_with_llm(
    *,
    question_text: str,
    candidate_answer: str,
    base: list[FollowUpQuestion],
) -> list[FollowUpQuestion]:
    """Optional Groq enrichment; falls back to rule-based follow-ups."""
    try:
        from agents.screening_agent.config import settings
        from agents.screening_agent.services.ai_parser import _call_groq, _groq_client
    except Exception:
        return base

    if _groq_client() is None:
        return base

    try:
        raw = _call_groq(
            "You are Agent 4, a live technical interviewer. "
            "Return 1-2 sharp follow-up interview questions as a plain numbered list. "
            "No preamble.",
            f"Original question:\n{question_text}\n\nCandidate answer:\n{candidate_answer}\n",
        )
        lines = [
            re.sub(r"^\d+[\).\:\-]\s*", "", line).strip()
            for line in raw.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        lines = [ln for ln in lines if len(ln) > 20][:2]
        if not lines:
            return base
        return [
            FollowUpQuestion(
                id=f"fu-{uuid.uuid4().hex[:10]}",
                parent_question_id=base[0].parent_question_id if base else "unknown",
                question_text=line,
                reason="LLM adaptive follow-up",
                difficulty="medium",
            )
            for line in lines
        ]
    except Exception:
        return base
