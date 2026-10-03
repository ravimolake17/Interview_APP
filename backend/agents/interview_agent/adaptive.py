"""Meta Llama–powered adaptive question + follow-up generation for Agent 4."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from agents.interview_agent.followup_generator import generate_followups
from agents.interview_agent.question_generator import (
    generate_questions_from_blueprint,
    shorten_question,
    _looks_like_intro,
    _question_key,
)
from agents.interview_agent.schemas import FollowUpQuestion, InterviewQuestion
from agents.shared.llama_client import call_llama_json, llama_available, llama_model_id
from core.chroma_store import retrieve_interview_questions

logger = logging.getLogger(__name__)


def generate_questions_with_llama(
    blueprint: dict[str, Any],
    *,
    job_title: str | None = None,
    resume_context: dict[str, str] | None = None,
) -> list[InterviewQuestion]:
    """Prefer Meta Llama question bank; fall back to deterministic templates."""
    base = generate_questions_from_blueprint(blueprint, job_title=job_title)
    if not llama_available() or not base:
        return base

    ctx = resume_context or {}
    chroma_lines: list[str] = []
    seen_q: set[str] = set()
    for q in base[:8]:
        skill = (q.skill_tags[0] if q.skill_tags else "") or ""
        for hit in retrieve_interview_questions(
            role=str(job_title or ctx.get("job_position") or ""),
            skill=skill,
            category=q.category_id,
            n_results=2,
        ):
            text = str(hit.get("document") or "").strip()
            key = text.casefold()
            meta = hit.get("metadata") if isinstance(hit.get("metadata"), dict) else {}
            hit_cat = str(meta.get("category") or "").strip()
            if hit_cat and hit_cat != q.category_id:
                continue
            if q.category_id != "introductory_questions" and _looks_like_intro(text):
                continue
            if text and key not in seen_q:
                seen_q.add(key)
                chroma_lines.append(f"- [{q.category_id}] {text}")
            if len(chroma_lines) >= 6:
                break
        if len(chroma_lines) >= 6:
            break
    past_questions = "\n".join(chroma_lines) if chroma_lines else "n/a"

    preview = [
        {
            "order": q.order,
            "category_id": q.category_id,
            "category_name": q.category_name,
            "difficulty": q.difficulty,
            "skill_tags": q.skill_tags,
            "seed": q.question_text,
            "intent": q.intent,
        }
        for q in base[:20]
    ]
    system = (
        "You are a senior interviewer with 15 years of hiring experience. "
        "Rewrite each seed so it sounds like a real human interviewer speaking live — "
        "calm, professional, specific, and conversational. "
        "Rules: one question, one question mark, max 28 words, no bullet lists, "
        "no 'please introduce yourself' cliches, no stacking two questions. "
        "Introductory questions must be a genuine opening about background or motivation. "
        "Do NOT put FastAPI, Flask, Python, or any tool into an intro question. "
        "Experience questions should probe ownership, delivery, and judgment. "
        "Skills and project questions should use the seed skill_tags and resume/JD facts. "
        "Cover different topics. Keep the same count, order, and category as the seeds. "
        "Each question_text MUST be unique — never repeat or lightly rephrase another seed. "
        "You may borrow phrasing from past questions that worked, but do not copy them verbatim. "
        "Return JSON: {\"questions\": [{\"order\":1,\"question_text\":\"...\","
        "\"intent\":\"...\",\"follow_up_hints\":[\"...\"],\"skill_tags\":[\"...\"]}] }"
    )
    user = (
        f"Job title: {job_title or ctx.get('job_position') or 'role'}\n"
        f"Resume summary: {ctx.get('resume_summary') or 'n/a'}\n"
        f"Skills: {ctx.get('skills') or 'n/a'}\n"
        f"JD requirements: {ctx.get('jd_requirements') or 'n/a'}\n"
        f"JD excerpt: {ctx.get('jd_text') or 'n/a'}\n\n"
        f"Past questions that worked for similar roles:\n{past_questions}\n\n"
        f"Seed questions JSON:\n{preview}"
    )
    try:
        data = call_llama_json(system, user, temperature=0.4, max_tokens=2500)
        refined = data.get("questions") if isinstance(data, dict) else None
        if not isinstance(refined, list) or not refined:
            return base
        by_order = {
            int(item.get("order") or 0): item
            for item in refined
            if isinstance(item, dict)
        }
        out: list[InterviewQuestion] = []
        used_texts: set[str] = set()
        for q in base:
            item = by_order.get(q.order) or {}
            text = str(item.get("question_text") or q.question_text).strip()
            text = shorten_question(text or q.question_text, 28)
            tags = list(item.get("skill_tags") or q.skill_tags)[:5] or list(q.skill_tags)
            planned = [str(tag) for tag in (q.skill_tags or []) if len(str(tag)) > 2]
            if q.category_id == "introductory_questions":
                tags = []
                lower = text.lower()
                if any(tag.lower() in lower for tag in planned) or any(
                    tool in lower
                    for tool in ("fastapi", "flask", "django", "python", "java", "react", "aws")
                ):
                    text = q.question_text
            elif planned and not any(tag.lower() in text.lower() for tag in planned):
                if q.category_id in {"skills_jd_keyword_questions", "project_related_questions"}:
                    text = shorten_question(q.question_text, 28)
                    tags = list(q.skill_tags)
            if q.category_id != "introductory_questions" and _looks_like_intro(text):
                text = q.question_text
            key = _question_key(text)
            if not key or key in used_texts:
                text = q.question_text
                key = _question_key(text)
            used_texts.add(key or f"order-{q.order}")
            out.append(
                q.model_copy(
                    update={
                        "question_text": text or q.question_text,
                        "intent": str(item.get("intent") or q.intent),
                        "follow_up_hints": list(item.get("follow_up_hints") or q.follow_up_hints)[
                            :3
                        ],
                        "skill_tags": tags,
                    }
                )
            )
        logger.info(
            "Agent 4 refined %s questions with Meta Llama (%s)",
            len(out),
            llama_model_id(),
        )
        return out
    except Exception:
        logger.exception("Meta Llama question refinement failed; using templates")
        return base


def generate_adaptive_followups(
    *,
    question_id: str,
    question_text: str,
    candidate_answer: str,
    evaluation: dict[str, Any] | None,
    skill_hints: list[str] | None = None,
    max_followups: int = 2,
) -> list[FollowUpQuestion]:
    """Generate follow-ups using Agent 6 feedback + Meta Llama."""
    base = generate_followups(
        question_id=question_id,
        question_text=question_text,
        candidate_answer=candidate_answer,
        max_followups=max_followups,
        skill_hints=skill_hints,
    )
    if not llama_available():
        return base

    eval_data = evaluation or {}
    system = (
        "You are Agent 4. If the candidate did not really answer, return {\"follow_ups\": []}. "
        "Do not rephrase the original question. "
        "If a follow-up is needed, write ONE new short probe (max 16 words) on a missing detail. "
        "Return JSON: {\"follow_ups\": [{\"question_text\":\"...\",\"reason\":\"...\","
        "\"difficulty\":\"easy|medium|hard\"}] }"
    )
    user = (
        f"Original question:\n{question_text}\n\n"
        f"Candidate answer:\n{candidate_answer}\n\n"
        f"Agent 6 score: {eval_data.get('score')}\n"
        f"Agent 6 verdict: {eval_data.get('verdict')}\n"
        f"Gaps: {eval_data.get('gaps')}\n"
        f"Feedback for Agent 4: {eval_data.get('feedback_for_agent4')}\n"
        f"Follow-up hints: {eval_data.get('followup_hints')}\n"
        f"Suggested focus: {eval_data.get('suggested_next_focus')}\n"
        f"Max follow-ups: {max_followups}"
    )
    try:
        data = call_llama_json(system, user, temperature=0.35, max_tokens=800)
        items = data.get("follow_ups") if isinstance(data, dict) else None
        if not isinstance(items, list) or not items:
            return base
        out: list[FollowUpQuestion] = []
        for item in items[:max_followups]:
            if not isinstance(item, dict):
                continue
            text = shorten_question(str(item.get("question_text") or "").strip(), 16)
            if len(text) < 12:
                continue
            difficulty = str(item.get("difficulty") or "medium").lower()
            if difficulty not in {"easy", "medium", "hard"}:
                difficulty = "medium"
            out.append(
                FollowUpQuestion(
                    id=f"fu-{uuid.uuid4().hex[:10]}",
                    parent_question_id=question_id,
                    question_text=text,
                    reason=str(item.get("reason") or "Agent 6–guided follow-up"),
                    difficulty=difficulty,  # type: ignore[arg-type]
                )
            )
        return out or base
    except Exception:
        logger.exception("Adaptive follow-up generation failed")
        return base


def adapt_next_question(
    next_question: dict[str, Any] | None,
    *,
    evaluation: dict[str, Any] | None = None,
    turn_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Keep the planned next question on its own JD/resume topic."""
    _ = evaluation, turn_history
    return next_question
