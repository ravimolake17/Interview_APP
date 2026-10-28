"""Follow-up question generation from candidate answers."""

from __future__ import annotations

import re
import uuid
from typing import Any

from agents.interview_agent.question_generator import (
    looks_like_resume_summary,
    sanitize_topic,
    shorten_question,
)
from agents.interview_agent.schemas import FollowUpQuestion

_THIN_ANSWER = re.compile(
    r"\b(i don'?t know|dont know|no idea|not sure|skip(?: it)?|pass|"
    r"no comment|nothing|can'?t answer|cannot answer|no answer)\b",
    re.IGNORECASE,
)

_OWNERSHIP_PROBE = (
    "You mentioned working with others — what was specifically your contribution versus the team's?"
)
_OWNERSHIP_REASON = "Clarify individual ownership."

_PERSONAL_OWNERSHIP = re.compile(
    r"\b(i\s+(built|wrote|owned|led|designed|implemented|developed|created|handled|"
    r"was responsible|took ownership|my (role|part|contribution|responsibility)))\b",
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


def should_treat_as_unanswered(
    answer: str,
    evaluation: dict[str, Any] | None = None,
) -> bool:
    """True only when there was no usable answer — never when Agent 6 scored a real reply."""
    cleaned = (answer or "").strip()
    if not cleaned:
        return True
    verdict = str((evaluation or {}).get("verdict") or "").lower()
    # Any scored substantive verdict means the candidate answered (incl. HR-added questions).
    if verdict in {"strong", "adequate", "weak"}:
        return False
    if verdict in {"insufficient", "off_topic"}:
        return True
    return answer_is_thin(cleaned)


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
        skill = sanitize_topic(str(tags[0]).strip())
    skip_skill = (
        not skill
        or looks_like_resume_summary(skill)
        or len(skill.split()) > 6
        or skill.casefold()
        in {
            "core skills",
            "the required skill",
            "your experience",
            "this role",
            "your project",
            "your coursework",
            "candidate background",
            "the job requirements",
            "the role",
        }
    )
    if skill and not skip_skill:
        return f"{thanks} Next, a short question on {skill}."
    category = str(next_question.get("category_name") or "the next topic").strip()
    return f"{thanks} Let's move to {category.lower()}."


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p.strip() for p in parts if len(p.strip()) > 12]


def asked_followup_keys(turn_history: list[dict[str, Any]] | None) -> set[str]:
    """Normalize previously asked follow-up texts/reasons so we never repeat them."""
    keys: set[str] = set()
    for turn in turn_history or []:
        question = turn.get("question") or {}
        if question.get("is_followup"):
            text = str(question.get("question_text") or "").strip().casefold()
            if text:
                keys.add(text)
            reason = str(question.get("reason") or "").strip().casefold()
            if reason:
                keys.add(f"reason:{reason}")
        for fu in turn.get("follow_ups") or []:
            text = str(fu.get("question_text") or "").strip().casefold()
            if text:
                keys.add(text)
            reason = str(fu.get("reason") or "").strip().casefold()
            if reason:
                keys.add(f"reason:{reason}")
    return keys


def _mentions_team_without_ownership(answer: str) -> bool:
    lower = answer.lower()
    if not any(w in lower for w in ("we ", " our team", "the team", "teammate", "colleagues")):
        return False
    if _PERSONAL_OWNERSHIP.search(answer):
        return False
    return True


def generate_followups(
    *,
    question_id: str,
    question_text: str,
    candidate_answer: str,
    max_followups: int = 2,
    skill_hints: list[str] | None = None,
    already_asked: set[str] | None = None,
) -> list[FollowUpQuestion]:
    """Create adaptive follow-ups from the transcribed answer (rule + template)."""
    answer = (candidate_answer or "").strip()
    if not answer or answer_is_thin(answer):
        return []

    followups: list[FollowUpQuestion] = []
    sentences = _sentences(answer)
    skills = [s for s in (skill_hints or []) if s][:3]
    lower = answer.lower()
    used = {k.casefold() for k in (already_asked or set())}

    probes: list[tuple[str, str, str]] = []

    # Hardcoded ownership probe — only once per interview, and only when team
    # language appears without a clear personal contribution.
    ownership_key = _OWNERSHIP_PROBE.casefold()
    ownership_reason_key = f"reason:{_OWNERSHIP_REASON.casefold()}"
    if (
        ownership_key not in used
        and ownership_reason_key not in used
        and _mentions_team_without_ownership(answer)
    ):
        probes.append((_OWNERSHIP_PROBE, _OWNERSHIP_REASON, "medium"))

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

    seen: set[str] = set(used)
    for text, reason, difficulty in probes:
        key = text.casefold()
        reason_key = f"reason:{reason.casefold()}"
        if key in seen or reason_key in seen:
            continue
        seen.add(key)
        seen.add(reason_key)
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
