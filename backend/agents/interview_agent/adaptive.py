"""LLM-primary question + follow-up generation for Agent 4 (templates as fallback)."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from agents.blueprint_agent.scenario_plan import enrich_blueprint_with_scenario_plan
from agents.blueprint_agent.schemas import (
    InterviewBlueprintResponse,
    QuestionPlanSlot,
)
from agents.interview_agent.followup_generator import generate_followups
from agents.interview_agent.question_generator import (
    generate_questions_from_blueprint,
    is_spoken_interview_question,
    looks_like_resume_summary,
    sanitize_topic,
    shorten_question,
    _looks_like_intro,
    _make_question,
    _question_key,
    _safe_fallback_question,
)
from agents.interview_agent.schemas import FollowUpQuestion, InterviewQuestion
from agents.shared.llama_client import call_llama_json, llama_available, llama_model_id

logger = logging.getLogger(__name__)

SCENARIO_MAX_WORDS = 42
FOLLOWUP_MAX_WORDS = 22


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _plan_slots_from_blueprint(blueprint: dict[str, Any]) -> list[QuestionPlanSlot]:
    raw = blueprint.get("question_plan")
    if isinstance(raw, list) and raw:
        slots: list[QuestionPlanSlot] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                slots.append(QuestionPlanSlot.model_validate(item))
            except Exception:
                continue
        if slots:
            return slots
    try:
        model = InterviewBlueprintResponse.model_validate(blueprint)
        if model.question_plan:
            return list(model.question_plan)
        enriched = enrich_blueprint_with_scenario_plan(model, None)
        return list(enriched.question_plan)
    except Exception:
        logger.debug("Could not rebuild question_plan from blueprint", exc_info=True)
        return []


def _template_questions_from_plan(
    slots: list[QuestionPlanSlot],
    *,
    role: str,
) -> list[InterviewQuestion]:
    """Deterministic spoken fallback when LLM is unavailable."""
    questions: list[InterviewQuestion] = []
    used: set[str] = set()
    for slot in slots:
        skill = sanitize_topic(slot.skill) or sanitize_topic(slot.evidence)
        if slot.category_id == "introductory_questions":
            text = shorten_question(
                "To start, walk me through your background and what drew you to this role?",
                SCENARIO_MAX_WORDS,
            )
        elif slot.probe_type == "scale":
            topic = skill or sanitize_topic(slot.evidence) or "your service"
            text = shorten_question(
                f"If {topic} suddenly had to handle a ten-times traffic spike, "
                f"how would you protect latency, memory, and error rates?",
                SCENARIO_MAX_WORDS,
            )
        elif slot.probe_type == "failure":
            topic = skill or sanitize_topic(slot.evidence) or "that system"
            text = shorten_question(
                f"Describe a production failure involving {topic}: what broke first, "
                f"how did you diagnose it, and what did you change afterward?",
                SCENARIO_MAX_WORDS,
            )
        elif slot.probe_type == "tradeoff":
            topic = skill or sanitize_topic(slot.evidence) or "the design"
            text = shorten_question(
                f"On {topic}, what important trade-off did you choose, and what did you give up?",
                SCENARIO_MAX_WORDS,
            )
        elif slot.probe_type == "change":
            topic = skill or sanitize_topic(slot.evidence) or "that approach"
            text = shorten_question(
                f"If you had to redesign {topic} from scratch next month, what would you change first?",
                SCENARIO_MAX_WORDS,
            )
        elif slot.category_id == "education_courses_questions":
            topic = skill or "your strongest coursework"
            text = shorten_question(
                f"Which part of {topic} do you actually use on the job, and where do you still feel a gap?",
                SCENARIO_MAX_WORDS,
            )
        else:
            text = _safe_fallback_question(
                category_id=slot.category_id,
                role=role,
                skill=skill or "",
                signal=skill or slot.evidence or "",
                jd_signal=skill or role,
                difficulty=slot.difficulty,
                order=slot.order,
            )
        if not is_spoken_interview_question(text):
            text = _safe_fallback_question(
                category_id=slot.category_id,
                role=role,
                skill=skill or "",
                signal=skill or "",
                jd_signal=role,
                difficulty=slot.difficulty,
                order=slot.order,
            )
        key = _question_key(text)
        if key in used:
            text = shorten_question(f"{text.rstrip('?')} for this {role or 'role'}?", SCENARIO_MAX_WORDS)
            key = _question_key(text) or f"order-{slot.order}"
        used.add(key)
        tags = (
            [skill]
            if skill
            and slot.category_id
            not in {"introductory_questions", "experience_questions"}
            else []
        )
        questions.append(
            _make_question(
                order=slot.order,
                category_id=slot.category_id,
                category_name=slot.category_name,
                difficulty=slot.difficulty,
                text=text,
                intent=slot.scenario_intent,
                hints=[f"Probe: {slot.probe_type}", "Ask for one concrete example."],
                estimated_seconds=slot.estimated_seconds,
                skill_tags=tags,
            )
        )
    return questions


def _clean_plan_slots(slots: list[QuestionPlanSlot]) -> list[QuestionPlanSlot]:
    cleaned: list[QuestionPlanSlot] = []
    for slot in slots:
        skill = sanitize_topic(slot.skill) or ""
        evidence = sanitize_topic(slot.evidence) or ""
        intent = re.sub(r"^[#>*\-\d.]+\s*", "", (slot.scenario_intent or "").strip())
        intent = re.sub(r"\s+", " ", intent).strip()
        cleaned.append(
            slot.model_copy(
                update={
                    "skill": skill,
                    "evidence": evidence,
                    "scenario_intent": intent or slot.scenario_intent,
                }
            )
        )
    return cleaned


def _call_llm_question_batch(
    batch: list[QuestionPlanSlot],
    *,
    job_title: str,
    role_family: str,
    resume_context: dict[str, str],
) -> list[dict[str, Any]]:
    preview = [
        {
            "order": s.order,
            "category_id": s.category_id,
            "difficulty": s.difficulty,
            "skill": s.skill,
            "evidence": s.evidence,
            "probe_type": s.probe_type,
            "scenario_intent": s.scenario_intent,
        }
        for s in batch
    ]
    system = (
        "You are a hiring manager with 15 years of experience running live technical interviews. "
        "Write professional spoken questions like ChatGPT would for a real interview — specific, "
        "scenario-based, and grounded in the candidate's skills/projects — NOT generic templates. "
        "For EACH slot return exactly one question_text. "
        "Hard rules:\n"
        "- One question, one '?', max 42 words, natural speech.\n"
        "- Never use resume bio/objective wording; never markdown (#).\n"
        "- Intro category: motivation/background only (no tool names).\n"
        "- Skills/projects: invent a concrete scenario matching probe_type "
        "(scale = burst load / large files / concurrency; failure = outage/bug; "
        "tradeoff = design choice; ownership = what they personally built; "
        "change = what they'd rebuild).\n"
        "- Example quality: 'If your OCR API received 1000 PDFs in one minute, "
        "how would you keep memory and latency under control?' "
        "Avoid: 'Talk me through a time you used FastAPI.'\n"
        "- Keep the same order values as the slots.\n"
        "Return JSON only: {\"questions\":[{\"order\":1,\"question_text\":\"...\","
        "\"intent\":\"...\",\"follow_up_hints\":[\"...\"],\"skill_tags\":[\"...\"]}]}"
    )
    user = (
        f"Job title: {job_title or resume_context.get('job_position') or 'role'}\n"
        f"Role family: {role_family or 'general'}\n"
        f"Skills: {resume_context.get('skills') or 'n/a'}\n"
        f"JD requirements: {resume_context.get('jd_requirements') or 'n/a'}\n"
        f"JD excerpt: {(resume_context.get('jd_text') or 'n/a')[:700]}\n"
        f"Resume context (planning only — never read aloud): "
        f"{(resume_context.get('resume_summary') or 'n/a')[:500]}\n\n"
        f"Slots ({len(batch)}):\n{preview}"
    )
    data = call_llama_json(system, user, temperature=0.5, max_tokens=2200)
    refined = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(refined, list):
        return []
    return [item for item in refined if isinstance(item, dict)]


def _llm_spoken_questions_from_plan(
    slots: list[QuestionPlanSlot],
    *,
    job_title: str,
    role_family: str,
    resume_context: dict[str, str],
) -> list[InterviewQuestion] | None:
    if not slots:
        return None
    if not llama_available():
        logger.warning(
            "Agent 4 LLM unavailable (configure Azure OpenAI or GROQ_API_KEY in SuperAdmin); "
            "falling back to templates"
        )
        return None

    slots = _clean_plan_slots(slots)
    by_order: dict[int, dict[str, Any]] = {}
    batch_size = 4
    try:
        for start in range(0, len(slots), batch_size):
            batch = slots[start : start + batch_size]
            try:
                items = _call_llm_question_batch(
                    batch,
                    job_title=job_title,
                    role_family=role_family,
                    resume_context=resume_context,
                )
            except Exception:
                logger.exception(
                    "Agent 4 LLM batch failed for orders %s-%s; retrying once",
                    batch[0].order,
                    batch[-1].order,
                )
                items = _call_llm_question_batch(
                    batch,
                    job_title=job_title,
                    role_family=role_family,
                    resume_context=resume_context,
                )
            for item in items:
                try:
                    order = int(item.get("order") or 0)
                except (TypeError, ValueError):
                    continue
                if order:
                    by_order[order] = item
        if len(by_order) < max(1, len(slots) // 2):
            logger.warning(
                "Agent 4 LLM returned too few questions (%s/%s); using template fallback",
                len(by_order),
                len(slots),
            )
            return None

        fallback = _template_questions_from_plan(slots, role=job_title)
        fallback_by_order = {q.order: q for q in fallback}
        out: list[InterviewQuestion] = []
        used: set[str] = set()
        llm_used = 0
        for slot in slots:
            seed = fallback_by_order.get(slot.order)
            item = by_order.get(slot.order) or {}
            raw_text = str(item.get("question_text") or "").strip()
            raw_text = re.sub(r"^[#>*\-\d.]+\s*", "", raw_text)
            text = shorten_question(
                raw_text or (seed.question_text if seed else ""),
                SCENARIO_MAX_WORDS,
            )
            from_llm = bool(raw_text) and is_spoken_interview_question(text)
            if from_llm:
                llm_used += 1
            else:
                text = seed.question_text if seed else text
            tags = [
                tag
                for tag in (
                    sanitize_topic(str(t))
                    for t in (item.get("skill_tags") or ([slot.skill] if slot.skill else []))
                )
                if tag and not looks_like_resume_summary(tag)
            ][:3]
            if slot.category_id == "introductory_questions":
                tags = []
                lower = text.lower()
                if any(
                    tool in lower
                    for tool in (
                        "fastapi",
                        "flask",
                        "django",
                        "python",
                        "java",
                        "react",
                        "aws",
                        "ocr",
                    )
                ):
                    text = seed.question_text if seed else text
            if slot.category_id != "introductory_questions" and _looks_like_intro(text):
                text = seed.question_text if seed else text
            if not is_spoken_interview_question(text):
                text = seed.question_text if seed else text
            key = _question_key(text)
            if not key or key in used:
                alt = shorten_question(
                    f"{text.rstrip('?')} — focusing on {sanitize_topic(slot.skill or slot.evidence) or 'this role'}?",
                    SCENARIO_MAX_WORDS,
                )
                if is_spoken_interview_question(alt) and _question_key(alt) not in used:
                    text = alt
                elif seed:
                    text = seed.question_text
                key = _question_key(text) or f"order-{slot.order}"
            used.add(key)
            out.append(
                _make_question(
                    order=slot.order,
                    category_id=slot.category_id,
                    category_name=slot.category_name,
                    difficulty=slot.difficulty,
                    text=text,
                    intent=str(item.get("intent") or slot.scenario_intent),
                    hints=list(item.get("follow_up_hints") or [f"Probe: {slot.probe_type}"])[:3],
                    estimated_seconds=slot.estimated_seconds,
                    skill_tags=tags
                    if slot.category_id
                    not in {"introductory_questions", "experience_questions"}
                    else [],
                )
            )
        logger.info(
            "Agent 4 generated questions via LLM (%s/%s from model %s)",
            llm_used,
            len(out),
            llama_model_id(),
        )
        if llm_used == 0:
            return None
        return out
    except Exception:
        logger.exception("Agent 4 LLM question generation from plan failed")
        return None


def generate_questions_with_llama(
    blueprint: dict[str, Any],
    *,
    job_title: str | None = None,
    resume_context: dict[str, str] | None = None,
) -> list[InterviewQuestion]:
    """LLM-primary spoken questions from Agent 3 question_plan; templates only as fallback.

    The returned bank is the default paper. HR add/edit/delete updates
    questions_json and that edited bank is what the live interview uses.
    """
    ctx = resume_context or {}
    role = (job_title or ctx.get("job_position") or _as_dict(blueprint.get("input_summary")).get("job_title") or "the role")
    role = str(role).strip() or "the role"
    role_family = str(blueprint.get("role_family") or "general")

    slots = _plan_slots_from_blueprint(blueprint)
    if slots:
        llm_questions = _llm_spoken_questions_from_plan(
            slots,
            job_title=role,
            role_family=role_family,
            resume_context=ctx,
        )
        if llm_questions:
            return llm_questions
        logger.warning(
            "Agent 4 using template fallback for %s slots (LLM missing or failed). "
            "Check SuperAdmin chat model / GROQ_API_KEY / Azure OpenAI.",
            len(slots),
        )
        return _template_questions_from_plan(slots, role=role)

    # Legacy blueprints without question_plan.
    base = generate_questions_from_blueprint(blueprint, job_title=role)
    if not llama_available() or not base:
        return base

    # One-shot LLM rewrite of legacy template seeds (still better than templates alone).
    preview = [
        {
            "order": q.order,
            "category_id": q.category_id,
            "difficulty": q.difficulty,
            "skill_tags": q.skill_tags,
            "seed": q.question_text,
            "intent": q.intent,
        }
        for q in base[:24]
    ]
    system = (
        "Rewrite each seed into a strong spoken interview question (max 42 words). "
        "Prefer concrete scenario probes (scale, failure, trade-off) over generic recitals. "
        "Never use resume bio language. Keep count/order/category. "
        "Return JSON: {\"questions\":[{\"order\":1,\"question_text\":\"...\","
        "\"intent\":\"...\",\"follow_up_hints\":[\"...\"],\"skill_tags\":[\"...\"]}] }"
    )
    user = (
        f"Job title: {role}\n"
        f"Skills: {ctx.get('skills') or 'n/a'}\n"
        f"Seeds:\n{preview}"
    )
    try:
        data = call_llama_json(system, user, temperature=0.4, max_tokens=3000)
        refined = data.get("questions") if isinstance(data, dict) else None
        if not isinstance(refined, list) or not refined:
            return base
        by_order = {
            int(item.get("order") or 0): item
            for item in refined
            if isinstance(item, dict)
        }
        out: list[InterviewQuestion] = []
        used: set[str] = set()
        for q in base:
            item = by_order.get(q.order) or {}
            text = shorten_question(
                str(item.get("question_text") or q.question_text).strip(),
                SCENARIO_MAX_WORDS,
            )
            if not is_spoken_interview_question(text):
                text = q.question_text
            key = _question_key(text)
            if not key or key in used:
                text = q.question_text
                key = _question_key(text) or f"order-{q.order}"
            used.add(key)
            tags = [
                tag
                for tag in (sanitize_topic(str(t)) for t in (item.get("skill_tags") or q.skill_tags))
                if tag and not looks_like_resume_summary(tag)
            ][:3]
            out.append(
                q.model_copy(
                    update={
                        "question_text": text,
                        "intent": str(item.get("intent") or q.intent),
                        "follow_up_hints": list(item.get("follow_up_hints") or q.follow_up_hints)[:3],
                        "skill_tags": tags
                        if q.category_id
                        not in {"introductory_questions", "experience_questions"}
                        else [],
                    }
                )
            )
        return out
    except Exception:
        logger.exception("Legacy LLM rewrite failed; using templates")
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
    """Prefer LLM follow-ups from Agent 6 gaps; template probes only as fallback."""
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
        "You are Agent 4 on a live voice interview. "
        "If the candidate did not really answer, return {\"follow_ups\": []}. "
        "Do not rephrase the original question. "
        "Write up to N NEW short spoken probes (max 22 words each) that dig into "
        "Agent 6 gaps, missing ownership, scale/limits, failure handling, or trade-offs. "
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
        f"Skill hints: {skill_hints or []}\n"
        f"Max follow-ups: {max_followups}"
    )
    try:
        data = call_llama_json(system, user, temperature=0.35, max_tokens=900)
        items = data.get("follow_ups") if isinstance(data, dict) else None
        if not isinstance(items, list) or not items:
            return base
        out: list[FollowUpQuestion] = []
        for item in items[:max_followups]:
            if not isinstance(item, dict):
                continue
            text = shorten_question(str(item.get("question_text") or "").strip(), FOLLOWUP_MAX_WORDS)
            if len(text) < 12 or looks_like_resume_summary(text.rstrip("?")):
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
