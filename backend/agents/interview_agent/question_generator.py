"""Deterministic (+ optional LLM) question generation from Agent 3 blueprint."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from agents.interview_agent.schemas import InterviewQuestion
from core.chroma_store import retrieve_interview_questions

logger = logging.getLogger(__name__)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _difficulty_cycle(mix: dict[str, Any], count: int) -> list[str]:
    pool: list[str] = []
    for key in ("easy", "medium", "hard"):
        pool.extend([key] * max(0, int(mix.get(key, 0) or 0)))
    if not pool:
        pool = ["medium"] * max(count, 1)
    while len(pool) < count:
        pool.append(pool[len(pool) % max(len(pool), 1)])
    return pool[:count]


def shorten_question(text: str, max_words: int = 28) -> str:
    """Keep live questions to one spoken sentence a senior interviewer would ask."""
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return cleaned
    first = re.split(r"(?<=[?])\s+", cleaned)[0].strip()
    words = first.split()
    if len(words) > max_words:
        first = " ".join(words[:max_words]).rstrip(",;: ")
    first = first.rstrip(".,;:")
    if not first.endswith("?"):
        first += "?"
    return first


def _unique_topics(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        item = str(raw or "").strip()
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _question_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").casefold()).strip()


def _looks_like_intro(text: str) -> bool:
    lower = (text or "").casefold()
    return any(
        marker in lower
        for marker in (
            "hiring manager",
            "two minutes",
            "walk me through your background",
            "what made you want to interview",
            "career so far",
        )
    )


def _chroma_seed_question(
    *,
    role: str,
    skill: str,
    category_id: str,
    used: set[str],
) -> str:
    hits = retrieve_interview_questions(
        role=role,
        skill=skill,
        category=category_id,
        n_results=6,
    )
    for hit in hits:
        text = shorten_question(str(hit.get("document") or "").strip(), 28)
        if len(text) < 20:
            continue
        key = _question_key(text)
        if not key or key in used:
            continue
        meta = hit.get("metadata") if isinstance(hit.get("metadata"), dict) else {}
        hit_cat = str(meta.get("category") or "").strip()
        if hit_cat and hit_cat != category_id:
            continue
        if category_id != "introductory_questions" and _looks_like_intro(text):
            continue
        return text
    return ""


CATEGORY_ORDER = [
    "introductory_questions",
    "experience_questions",
    "skills_jd_keyword_questions",
    "project_related_questions",
    "education_courses_questions",
]


def _question_templates(category_id: str, difficulty: str) -> list[str]:
    templates = {
        "introductory_questions": {
            "easy": [
                "To start, walk me through your background and what you are working on right now.",
                "What about this {role} role made you want to interview with us?",
            ],
            "medium": [
                "Give me a two-minute picture of your career so far, focused on work closest to this {role} role.",
                "How would you describe the kind of work you want to be doing in the next year?",
            ],
            "hard": [
                "If I had two minutes with a hiring manager, what should I remember about you for this {role} role?",
                "What outcome from your last role is most relevant to this {role} job?",
                "Why should we keep talking after this interview for this {role} role?",
            ],
        },
        "experience_questions": {
            "easy": [
                "Walk me through the work on your resume that is closest to this {role} role.",
                "Tell me about a piece of work you personally owned from start to finish.",
            ],
            "medium": [
                "Pick one result you delivered recently. What was the problem, what did you do, and what changed?",
                "Where have you had real ownership, not just helping a team, in work like this {role} role?",
            ],
            "hard": [
                "Tell me about the hardest delivery you have owned. What went wrong, and how did you handle it?",
                "When did you have to push back on a stakeholder, and what happened next?",
            ],
        },
        "skills_jd_keyword_questions": {
            "easy": [
                "Talk me through a time you used {skill} on real work, not just in a course.",
                "How comfortable are you with {skill} day to day, and where have you used it?",
            ],
            "medium": [
                "Give me a concrete example of using {skill} to solve a production problem.",
                "If we asked you to use {skill} for {jd_signal}, how would you start?",
            ],
            "hard": [
                "When {skill} has gone wrong for you, what did you learn and what would you do differently?",
                "How would you debug a production issue that traces back to {skill}?",
                "What would you refuse to do with {skill} in production, and why?",
            ],
        },
        "project_related_questions": {
            "easy": [
                "On the {signal} work, what did you personally own?",
                "How did the {signal} work start, and what was your first decision?",
            ],
            "medium": [
                "On {signal}, what trade-off did you make, and why did you choose that path?",
                "How did you know the {signal} work was actually good enough to ship?",
            ],
            "hard": [
                "If you rebuilt {signal} today, what would you change first, and why?",
                "What broke, or almost broke, on {signal}, and how did you recover?",
            ],
        },
        "education_courses_questions": {
            "easy": [
                "Which part of your {signal} training do you actually use on the job?",
            ],
            "medium": [
                "How have you applied {signal} on real work, not only in class?",
            ],
            "hard": [
                "Where do you still feel a gap after {signal}, and how are you closing it for this role?",
            ],
        },
    }
    by_cat = templates.get(category_id, templates["skills_jd_keyword_questions"])
    return by_cat.get(difficulty, by_cat.get("medium", ["Tell me more about {signal}."]))


def _fill(template: str, *, role: str, skill: str, signal: str, jd_signal: str) -> str:
    return shorten_question(
        template.replace("{role}", role or "this")
        .replace("{skill}", skill or "the required skill")
        .replace("{signal}", signal or "your experience")
        .replace("{jd_signal}", jd_signal or "the job requirements")
    )


def _category_template_pool(category_id: str, difficulty: str) -> list[str]:
    preferred = list(_question_templates(category_id, difficulty))
    extras: list[str] = []
    for other in ("easy", "medium", "hard"):
        if other == difficulty:
            continue
        extras.extend(_question_templates(category_id, other))
    seen: set[str] = set()
    out: list[str] = []
    for template in preferred + extras:
        key = template.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(template)
    return out


def _unused_text(candidates: list[str], used: set[str]) -> str:
    for text in candidates:
        cleaned = shorten_question(text, 28)
        key = _question_key(cleaned)
        if cleaned and key and key not in used:
            used.add(key)
            return cleaned
    return ""


def _make_question(
    *,
    order: int,
    category_id: str,
    category_name: str,
    difficulty: str,
    text: str,
    intent: str,
    hints: list[str],
    estimated_seconds: int,
    skill_tags: list[str],
) -> InterviewQuestion:
    return InterviewQuestion(
        id=f"q-{uuid.uuid4().hex[:10]}",
        order=order,
        category_id=category_id,
        category_name=category_name,
        difficulty=difficulty,  # type: ignore[arg-type]
        question_text=text,
        intent=intent,
        follow_up_hints=hints[:3],
        estimated_seconds=estimated_seconds,
        skill_tags=skill_tags,
    )


def _finalize_question_bank(
    questions: list[InterviewQuestion],
    *,
    role: str,
) -> list[InterviewQuestion]:
    """Keep a professional intro first, then experience, skills, projects, education."""
    existing_ids = {q.category_id for q in questions}
    if "introductory_questions" not in existing_ids:
        questions = [
            _make_question(
                order=1,
                category_id="introductory_questions",
                category_name="Introductory Questions",
                difficulty="easy",
                text=_fill(
                    "To start, walk me through your background and what you are working on right now.",
                    role=role,
                    skill="",
                    signal="",
                    jd_signal="",
                ),
                intent="Warm opening from a senior interviewer.",
                hints=["Listen for communication and career narrative."],
                estimated_seconds=90,
                skill_tags=[],
            ),
            *questions,
        ]

    rank = {cid: index for index, cid in enumerate(CATEGORY_ORDER)}
    ordered = sorted(
        questions,
        key=lambda question: (rank.get(question.category_id, 50), question.order),
    )
    used: set[str] = set()
    unique: list[InterviewQuestion] = []
    for index, question in enumerate(ordered, start=1):
        text = question.question_text
        key = _question_key(text)
        if key in used:
            extra = next((tag for tag in question.skill_tags if tag), f"topic {index}")
            text = shorten_question(f"{text.rstrip('?')} in {extra}?", 28)
            key = _question_key(text) or f"order-{index}"
        used.add(key)
        unique.append(question.model_copy(update={"order": index, "question_text": text}))
    return unique


def generate_questions_from_blueprint(
    blueprint: dict[str, Any],
    *,
    job_title: str | None = None,
) -> list[InterviewQuestion]:
    """Build concrete interview questions from Agent 3 blueprint categories."""
    summary = _as_dict(blueprint.get("input_summary"))
    role = (job_title or summary.get("job_title") or "the role").strip()
    categories = _as_list(blueprint.get("category_breakdown"))
    skill_focus = _as_list(blueprint.get("skill_focus_plan"))
    skill_names = [
        str(item.get("skill_name") or item.get("skill") or "").strip()
        for item in skill_focus
        if isinstance(item, dict)
    ]
    skill_names = _unique_topics(skill_names)
    all_resume = _unique_topics(
        [
            str(s)
            for cat in categories
            if isinstance(cat, dict)
            for s in _as_list(cat.get("candidate_resume_signals"))
            if s
        ]
    )
    all_jd = _unique_topics(
        [
            str(s)
            for cat in categories
            if isinstance(cat, dict)
            for s in _as_list(cat.get("jd_signals"))
            if s
        ]
    )
    topic_pool = _unique_topics(skill_names + all_jd + all_resume)
    topic_cursor = 0
    used_questions: set[str] = set()

    def _next_topic(pool: list[str], fallback: str) -> str:
        nonlocal topic_cursor
        source = pool or topic_pool
        if not source:
            return fallback
        item = source[topic_cursor % len(source)]
        topic_cursor += 1
        return item

    questions: list[InterviewQuestion] = []
    order = 1

    for cat in categories:
        if not isinstance(cat, dict):
            continue
        category_id = str(cat.get("category_id") or "skills_jd_keyword_questions")
        category_name = str(cat.get("category_name") or category_id)
        count = max(1, int(cat.get("question_count") or 1))
        mix = _as_dict(cat.get("difficulty_mix"))
        diffs = _difficulty_cycle(mix, count)
        resume_signals = _unique_topics([str(s) for s in _as_list(cat.get("candidate_resume_signals")) if s])
        jd_signals = _unique_topics([str(s) for s in _as_list(cat.get("jd_signals")) if s])
        instruction = str(cat.get("agent4_generation_instruction") or "").strip()
        minutes = max(1, int(cat.get("estimated_minutes") or count * 2))
        seconds_each = max(45, int((minutes * 60) / count))

        for i in range(count):
            difficulty = diffs[i] if i < len(diffs) else "medium"
            if category_id == "introductory_questions":
                topic = ""
            elif category_id == "experience_questions":
                topic = ""
            elif category_id == "project_related_questions":
                topic = _next_topic(resume_signals or all_resume, "your project")
            elif category_id == "education_courses_questions":
                topic = _next_topic(resume_signals, "your coursework")
            else:
                topic = _next_topic(skill_names or jd_signals or topic_pool, "core skills")
            skill = topic
            signal = topic or "your work"
            jd_signal = jd_signals[i % len(jd_signals)] if jd_signals else (topic or role)
            chroma_text = (
                ""
                if category_id in {"introductory_questions", "experience_questions"}
                else _chroma_seed_question(
                    role=role,
                    skill=skill,
                    category_id=category_id,
                    used=used_questions,
                )
            )
            filled = [
                _fill(template, role=role, skill=skill, signal=signal, jd_signal=jd_signal)
                for template in _category_template_pool(category_id, difficulty)
            ]
            text = _unused_text(([chroma_text] if chroma_text else []) + filled, used_questions)
            if not text:
                specialized = _fill(
                    filled[0] if filled else "Tell me more about {signal}.",
                    role=role,
                    skill=skill or f"example {order}",
                    signal=f"{signal} example {order}",
                    jd_signal=jd_signal,
                )
                specialized = shorten_question(
                    f"{specialized.rstrip('?')} for {skill or signal or f'topic {order}'}?",
                    28,
                )
                used_questions.add(_question_key(specialized) or f"q-{order}")
                text = specialized

            skill_tags = [skill] if skill and category_id not in {
                "introductory_questions",
                "experience_questions",
            } else []

            hints = ["Ask for one concrete example."]
            if skill:
                hints.insert(0, f"Stay on {skill}.")
            if instruction:
                hints.append(instruction[:120])

            questions.append(
                _make_question(
                    order=order,
                    category_id=category_id,
                    category_name=category_name,
                    difficulty=difficulty,
                    text=text,
                    intent=instruction or f"Assess {category_name}",
                    hints=hints,
                    estimated_seconds=seconds_each,
                    skill_tags=skill_tags,
                )
            )
            order += 1

    return _finalize_question_bank(questions, role=role)
