"""Agent 3 scenario plan: structured intents for Agent 4 (not spoken questions)."""

from __future__ import annotations

import logging
import re
from typing import Any

from agents.blueprint_agent.schemas import (
    InterviewBlueprintRequest,
    InterviewBlueprintResponse,
    ProbeType,
    QuestionPlanSlot,
    RoleFamily,
)
from agents.shared.llama_client import call_llama_json, llama_available, llama_model_id

logger = logging.getLogger(__name__)

CATEGORY_NAMES = {
    "introductory_questions": "Introductory Questions",
    "skills_jd_keyword_questions": "Skills & JD Keyword-related Questions",
    "project_related_questions": "Project-related Questions",
    "education_courses_questions": "Education & Courses-related Questions",
}

# Rotate probe styles so banks are not all "tell me about X".
_SKILL_PROBES: list[ProbeType] = ["ownership", "scale", "failure", "tradeoff", "change"]
_PROJECT_PROBES: list[ProbeType] = ["ownership", "scale", "failure", "tradeoff", "change"]
_EDU_PROBES: list[ProbeType] = ["fundamentals", "ownership", "change"]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def _short_label(value: Any, *, max_words: int = 6) -> str:
    text = _clean(value).strip(" ,;|.-")
    if not text:
        return ""
    first = re.split(r"[.!?;|\n]\s*", text)[0].strip()
    for sep in (" - ", " – ", " — ", ": "):
        if sep in first:
            first = first.split(sep, 1)[0].strip()
            break
    words = first.split()
    if len(words) > max_words:
        first = " ".join(words[:max_words])
    # Drop resume-summary style blurbs.
    lower = first.casefold()
    if any(
        marker in lower
        for marker in (
            "motivated",
            "passionate",
            "research-oriented",
            "graduate with",
            "seeking",
            "looking for",
        )
    ):
        return ""
    if len(first) > 64:
        return ""
    return first


def infer_role_family(
    *,
    job_title: str = "",
    jd_text: str = "",
    skills: list[str] | None = None,
) -> RoleFamily:
    blob = " ".join(
        [
            job_title,
            jd_text[:1200],
            " ".join(skills or []),
        ]
    ).casefold()
    if re.search(
        r"\b(data scientist|machine learning|ml engineer|analytics|bi developer|"
        r"data engineer|statistician)\b",
        blob,
    ):
        return "data"
    if re.search(
        r"\b(devops|sre|site reliability|platform engineer|cloud engineer|"
        r"infrastructure|sysadmin|network engineer)\b",
        blob,
    ):
        return "ops"
    if re.search(
        r"\b(product manager|program manager|scrum master|business analyst)\b",
        blob,
    ):
        return "product"
    if re.search(
        r"\b(software|developer|engineer|backend|frontend|full[\s-]?stack|"
        r"python|java|react|api|microservices|ocr|fastapi)\b",
        blob,
    ):
        return "software"
    if re.search(
        r"\b(hr|recruiter|sales|marketing|accountant|nurse|teacher|"
        r"customer support|operations executive)\b",
        blob,
    ):
        return "non_tech"
    return "general"


def _difficulty_cycle(mix: dict[str, Any], count: int) -> list[str]:
    pool: list[str] = []
    for key in ("easy", "medium", "hard"):
        pool.extend([key] * max(0, int(mix.get(key, 0) or 0)))
    if not pool:
        pool = ["medium"] * max(count, 1)
    while len(pool) < count:
        pool.append(pool[len(pool) % max(len(pool), 1)])
    return pool[:count]


def _default_intent(
    *,
    category_id: str,
    probe: ProbeType,
    skill: str,
    evidence: str,
    role: str,
) -> str:
    topic = skill or evidence or role or "the role"
    if category_id == "introductory_questions":
        return "Open with career narrative and motivation for this role"
    if category_id == "education_courses_questions":
        return f"Connect {topic} learning to real on-the-job application"
    mapping = {
        "ownership": f"Probe personal ownership delivering work with {topic}",
        "scale": f"Probe how {topic} behaves under burst load, large volume, or size limits",
        "failure": f"Probe failure modes, recovery, and lessons with {topic}",
        "tradeoff": f"Probe a hard trade-off made while using {topic}",
        "change": f"Probe what they would redesign first about {topic}",
        "fundamentals": f"Probe core understanding of {topic} beyond buzzwords",
        "motivation": "Probe motivation and fit for this role",
    }
    return mapping.get(probe, f"Probe practical depth on {topic}")


def build_deterministic_question_plan(
    blueprint: InterviewBlueprintResponse,
) -> list[QuestionPlanSlot]:
    """Expand category counts into ordered slots with rotating probe types."""
    skills = [
        _short_label(item.skill_name)
        for item in (blueprint.skill_focus_plan or [])
        if _short_label(item.skill_name)
    ]
    all_resume: list[str] = []
    all_jd: list[str] = []
    for cat in blueprint.category_breakdown:
        for signal in cat.candidate_resume_signals:
            label = _short_label(signal)
            if label:
                all_resume.append(label)
        for signal in cat.jd_signals:
            label = _short_label(signal)
            if label:
                all_jd.append(label)

    skills = list(dict.fromkeys(skills + all_jd))
    projects = list(dict.fromkeys(all_resume))
    role = _short_label(blueprint.input_summary.job_title) or "this role"

    slots: list[QuestionPlanSlot] = []
    order = 1
    skill_i = 0
    project_i = 0
    probe_i = 0

    for cat in blueprint.category_breakdown:
        count = max(1, int(cat.question_count))
        diffs = _difficulty_cycle(dict(cat.difficulty_mix or {}), count)
        minutes = max(1, int(cat.estimated_minutes or count * 2))
        seconds_each = max(45, int((minutes * 60) / count))
        cat_resume = [_short_label(s) for s in cat.candidate_resume_signals if _short_label(s)]
        cat_jd = [_short_label(s) for s in cat.jd_signals if _short_label(s)]

        for i in range(count):
            difficulty = diffs[i] if i < len(diffs) else "medium"
            skill = ""
            evidence = ""
            if cat.category_id == "introductory_questions":
                probe: ProbeType = "motivation"
            elif cat.category_id == "education_courses_questions":
                probe = _EDU_PROBES[i % len(_EDU_PROBES)]
                evidence = (cat_resume[i % len(cat_resume)] if cat_resume else "") or (
                    projects[project_i % len(projects)] if projects else ""
                )
                if projects:
                    project_i += 1
                skill = evidence or (cat_jd[0] if cat_jd else "")
            elif cat.category_id == "project_related_questions":
                probe = _PROJECT_PROBES[probe_i % len(_PROJECT_PROBES)]
                probe_i += 1
                evidence = (cat_resume[i % len(cat_resume)] if cat_resume else "") or (
                    projects[project_i % len(projects)] if projects else "recent project"
                )
                if projects:
                    project_i += 1
                skill = evidence
            else:
                probe = _SKILL_PROBES[probe_i % len(_SKILL_PROBES)]
                probe_i += 1
                skill = (skills[skill_i % len(skills)] if skills else "") or (
                    cat_jd[i % len(cat_jd)] if cat_jd else "core skills"
                )
                if skills:
                    skill_i += 1
                evidence = cat_resume[i % len(cat_resume)] if cat_resume else ""

            slots.append(
                QuestionPlanSlot(
                    order=order,
                    category_id=cat.category_id,
                    category_name=cat.category_name or CATEGORY_NAMES.get(cat.category_id, cat.category_id),
                    difficulty=difficulty,  # type: ignore[arg-type]
                    skill=skill or "",
                    evidence=evidence or "",
                    scenario_intent=_default_intent(
                        category_id=cat.category_id,
                        probe=probe,
                        skill=skill,
                        evidence=evidence,
                        role=role,
                    ),
                    probe_type=probe,
                    estimated_seconds=seconds_each,
                )
            )
            order += 1
    return slots


def _llm_refine_intents(
    slots: list[QuestionPlanSlot],
    *,
    role_family: RoleFamily,
    job_title: str,
    skills: list[str],
    projects: list[str],
    jd_excerpt: str,
    resume_summary: str,
) -> list[QuestionPlanSlot]:
    if not llama_available() or not slots:
        return slots

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
        for s in slots
    ]
    system = (
        "You are Agent 3, an interview planner. "
        "For each slot, rewrite scenario_intent only — short planning notes for Agent 4. "
        "Do NOT write the final spoken interview question. "
        "Do NOT use resume objective/summary bio language. "
        "For probe_type=scale, invent a concrete pressure scenario fitting the skill and role_family "
        "(examples by domain: burst document load, large file memory, concurrent users, "
        "month-end volume spike, peak support tickets) — adapt beyond IT when role_family is non_tech. "
        "For failure/tradeoff/change/ownership, be specific to skill/evidence. "
        "Keep each scenario_intent under 28 words. "
        "Keep the same count and order. "
        "Return JSON: {\"slots\": [{\"order\":1,\"scenario_intent\":\"...\",\"skill\":\"...\","
        "\"evidence\":\"...\",\"probe_type\":\"ownership|scale|failure|tradeoff|change|motivation|fundamentals\"}] }"
    )
    user = (
        f"Job title: {job_title or 'role'}\n"
        f"Role family: {role_family}\n"
        f"Skills: {', '.join(skills[:12]) or 'n/a'}\n"
        f"Projects/evidence: {', '.join(projects[:8]) or 'n/a'}\n"
        f"JD excerpt: {(jd_excerpt or 'n/a')[:600]}\n"
        f"Resume context (planning only, never quote as a question): "
        f"{(resume_summary or 'n/a')[:400]}\n\n"
        f"Slots JSON:\n{preview}"
    )
    try:
        data = call_llama_json(system, user, temperature=0.35, max_tokens=2800)
        refined = data.get("slots") if isinstance(data, dict) else None
        if not isinstance(refined, list) or not refined:
            return slots
        by_order = {
            int(item.get("order") or 0): item
            for item in refined
            if isinstance(item, dict)
        }
        out: list[QuestionPlanSlot] = []
        valid_probes = {
            "motivation",
            "ownership",
            "scale",
            "failure",
            "tradeoff",
            "change",
            "fundamentals",
        }
        for slot in slots:
            item = by_order.get(slot.order) or {}
            intent = _clean(item.get("scenario_intent") or slot.scenario_intent)
            if len(intent.split()) > 32:
                intent = " ".join(intent.split()[:32])
            skill = _short_label(item.get("skill") or slot.skill) or slot.skill
            evidence = _short_label(item.get("evidence") or slot.evidence) or slot.evidence
            probe = str(item.get("probe_type") or slot.probe_type).strip().lower()
            if probe not in valid_probes:
                probe = slot.probe_type
            if not intent:
                intent = slot.scenario_intent
            out.append(
                slot.model_copy(
                    update={
                        "scenario_intent": intent,
                        "skill": skill,
                        "evidence": evidence,
                        "probe_type": probe,
                    }
                )
            )
        logger.info(
            "Agent 3 refined %s scenario intents with LLM (%s)",
            len(out),
            llama_model_id(),
        )
        return out
    except Exception:
        logger.exception("Agent 3 scenario-intent LLM refine failed; using deterministic intents")
        return slots


def enrich_blueprint_with_scenario_plan(
    blueprint: InterviewBlueprintResponse,
    payload: InterviewBlueprintRequest | None = None,
) -> InterviewBlueprintResponse:
    """Attach role_family + question_plan (deterministic, optionally LLM-refined)."""
    job_title = blueprint.input_summary.job_title or ""
    skills = [
        _short_label(item.skill_name)
        for item in (blueprint.skill_focus_plan or [])
        if _short_label(item.skill_name)
    ]
    jd_text = ""
    resume_summary = ""
    if payload is not None:
        jd_text = _clean(payload.jd_text) or _clean(
            _as_dict(payload.jd_json).get("raw_text")
            or _as_dict(payload.jd_json).get("description")
        )
        resume_summary = _clean(
            _as_dict(payload.resume_json).get("summary")
            or _as_dict(payload.resume_json).get("professional_summary")
        )
        if not job_title:
            job_title = _clean(_as_dict(payload.jd_json).get("job_title")) or job_title

    role_family = infer_role_family(job_title=job_title, jd_text=jd_text, skills=skills)
    slots = build_deterministic_question_plan(blueprint)
    projects = list(
        dict.fromkeys(
            _short_label(s)
            for cat in blueprint.category_breakdown
            for s in cat.candidate_resume_signals
            if _short_label(s)
        )
    )
    slots = _llm_refine_intents(
        slots,
        role_family=role_family,
        job_title=job_title,
        skills=skills,
        projects=projects,
        jd_excerpt=jd_text,
        resume_summary=resume_summary,
    )
    source = (
        "deterministic_agent3_plus_llm_scenario_plan"
        if llama_available()
        else "deterministic_agent3_scenario_plan"
    )
    meta = blueprint.agent4_metadata.model_copy(
        update={
            "output_contract": "blueprint_plus_question_plan_intents_no_spoken_questions",
            "guardrails": list(
                dict.fromkeys(
                    list(blueprint.agent4_metadata.guardrails or [])
                    + [
                        "Agent 4 must turn question_plan scenario_intent into spoken questions.",
                        "Prefer scenario probes (scale/failure/tradeoff) over generic skill recitals.",
                        "HR-edited question bank is the final interview paper once saved.",
                    ]
                )
            ),
        }
    )
    return blueprint.model_copy(
        update={
            "role_family": role_family,
            "question_plan": slots,
            "generation_source": source,
            "agent4_metadata": meta,
            "blueprint_version": "3.2",
        }
    )
