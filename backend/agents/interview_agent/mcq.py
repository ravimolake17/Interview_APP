"""Short timed MCQ section that runs after the AI intro and before oral questions."""

from __future__ import annotations

import logging
import random
import re
from typing import Any

from agents.shared.llama_client import call_llama_json, llama_available

logger = logging.getLogger(__name__)

OPTION_IDS = ("A", "B", "C", "D")

_FALLBACK_BANK: list[dict[str, Any]] = [
    {
        "question_text": "Which practice most reliably reduces defects before code reaches production?",
        "options": [
            "Skipping peer review to ship faster",
            "Automated tests plus a code review",
            "Testing only after the release",
            "Rewriting the whole module every sprint",
        ],
        "correct_index": 1,
        "skill": "quality",
    },
    {
        "question_text": "A production issue is impacting customers. What should you do first?",
        "options": [
            "Rewrite the service from scratch",
            "Wait for the next planned release",
            "Contain the impact, then find the root cause",
            "Delete logs so the incident stays quiet",
        ],
        "correct_index": 2,
        "skill": "operations",
    },
    {
        "question_text": "Which description best matches a REST API?",
        "options": [
            "A UI-only design with no backend",
            "A resource-oriented HTTP interface using standard methods",
            "A database backup format",
            "A hardware monitoring protocol",
        ],
        "correct_index": 1,
        "skill": "api",
    },
    {
        "question_text": "Why do teams keep secrets out of source control?",
        "options": [
            "Secrets make git slower",
            "It is only a style preference",
            "Exposed credentials can be reused by anyone with repo access",
            "Compilers reject files that contain passwords",
        ],
        "correct_index": 2,
        "skill": "security",
    },
    {
        "question_text": "What is the main benefit of breaking work into small pull requests?",
        "options": [
            "Reviews are faster and regressions are easier to spot",
            "It hides incomplete work from the team",
            "It removes the need for testing",
            "It guarantees zero production bugs",
        ],
        "correct_index": 0,
        "skill": "collaboration",
    },
    {
        "question_text": "When requirements are unclear, what is the strongest next step?",
        "options": [
            "Guess and ship the largest design",
            "Ask clarifying questions and confirm the acceptance criteria",
            "Ignore the requirement until someone complains",
            "Copy an unrelated feature from another product",
        ],
        "correct_index": 1,
        "skill": "communication",
    },
    {
        "question_text": "Which statement about SQL indexes is most accurate?",
        "options": [
            "Indexes always make every query slower",
            "They can speed lookups but add write overhead",
            "They replace the need for a primary key",
            "They are only used in NoSQL databases",
        ],
        "correct_index": 1,
        "skill": "databases",
    },
    {
        "question_text": "What does a 401 HTTP status typically mean?",
        "options": [
            "The request succeeded",
            "The resource was created",
            "The client is not authenticated",
            "The server is restarting",
        ],
        "correct_index": 2,
        "skill": "http",
    },
    {
        "question_text": "Which Git command creates a new branch and switches to it?",
        "options": [
            "git blame",
            "git checkout --orphan",
            "git switch -c",
            "git stash drop",
        ],
        "correct_index": 2,
        "skill": "git",
    },
    {
        "question_text": "A service is slow only during peak traffic. What is the most useful first check?",
        "options": [
            "Delete the monitoring dashboard",
            "Look at latency, errors, and resource saturation",
            "Rewrite the UI in a new framework",
            "Disable all logging permanently",
        ],
        "correct_index": 1,
        "skill": "performance",
    },
    {
        "question_text": "Why do teams write automated tests for critical business paths?",
        "options": [
            "Tests replace product owners",
            "They catch regressions before customers do",
            "They make code unreadable on purpose",
            "They are required only for mobile apps",
        ],
        "correct_index": 1,
        "skill": "testing",
    },
    {
        "question_text": "Which option is the safest way to handle a customer’s personal data?",
        "options": [
            "Store it in a shared spreadsheet",
            "Collect only what is needed and restrict access",
            "Email it to a personal inbox for backup",
            "Publish it in a public wiki for transparency",
        ],
        "correct_index": 1,
        "skill": "privacy",
    },
]


def mcq_duration_seconds(planned_minutes: int | None) -> int:
    planned = max(10, int(planned_minutes or 30))
    minutes = max(4, min(8, round(planned * 5 / 30)))
    return int(minutes * 60)


def mcq_question_count(planned_minutes: int | None) -> int:
    planned = max(10, int(planned_minutes or 30))
    return 10 if planned >= 45 else 8


def mcq_rules_message(*, minutes: int, count: int) -> str:
    return (
        f"Before the spoken interview, you will take a short multiple-choice test. "
        f"You will see one question at a time. Select an option to lock your answer — "
        f"you cannot go back or change it. You may skip a question if you are unsure. "
        f"You have about {minutes} minutes for {count} questions. "
        "When you finish or time runs out, we will begin the oral interview."
    )


def oral_rules_message() -> str:
    return (
        "The multiple-choice section is complete. Now we begin the oral interview. "
        "I will ask you one question at a time. Please listen carefully, then answer "
        "naturally using your microphone. When you stop speaking, your answer will be "
        "captured automatically. At the end, you will get time to share feedback and "
        "ask me questions about the role. Let's begin."
    )


def intro_message(*, first_name: str, company_name: str, role: str) -> str:
    name = first_name.strip() or "there"
    company = company_name.strip() or "RR Parkon"
    role_phrase = f" for the {role.strip()} position" if role.strip() else ""
    return (
        f"Hello {name}, welcome to {company} — part of RR Global. "
        f"I'm your AI interviewer today{role_phrase}. "
        "RR Global builds intelligent recruitment and enterprise software solutions. "
        "This interview is confidential and proctored to ensure fairness for every candidate."
    )


def _skills_from_context(resume_context: dict[str, str] | None, job_title: str | None) -> list[str]:
    ctx = resume_context or {}
    raw = ",".join(
        filter(
            None,
            [
                ctx.get("skills") or "",
                ctx.get("jd_requirements") or "",
                job_title or "",
            ],
        )
    )
    parts = re.split(r"[,;/|]+", raw)
    seen: set[str] = set()
    out: list[str] = []
    for part in parts:
        skill = re.sub(r"\s+", " ", part).strip()
        key = skill.casefold()
        if len(skill) < 2 or key in seen:
            continue
        seen.add(key)
        out.append(skill[:48])
        if len(out) >= 10:
            break
    return out


def _shuffle_options(options: list[str], correct_index: int, rng: random.Random) -> tuple[list[dict[str, str]], str]:
    pairs = list(enumerate(options[:4]))
    while len(pairs) < 4:
        pairs.append((len(pairs), "None of the above"))
    rng.shuffle(pairs)
    mapped: list[dict[str, str]] = []
    correct_id = "A"
    for idx, (original_index, text) in enumerate(pairs[:4]):
        option_id = OPTION_IDS[idx]
        mapped.append({"id": option_id, "text": str(text).strip()[:180]})
        if original_index == correct_index:
            correct_id = option_id
    return mapped, correct_id


def _normalize_llm_questions(payload: dict[str, Any], count: int) -> list[dict[str, Any]]:
    raw = payload.get("questions") if isinstance(payload, dict) else None
    if not isinstance(raw, list):
        return []
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = re.sub(r"\s+", " ", str(item.get("question_text") or "").strip())
        options = item.get("options") if isinstance(item.get("options"), list) else []
        option_texts = [re.sub(r"\s+", " ", str(opt).strip()) for opt in options]
        option_texts = [opt for opt in option_texts if opt]
        if len(text) < 12 or len(option_texts) < 4:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        try:
            correct_index = int(item.get("correct_index", 0))
        except (TypeError, ValueError):
            correct_index = 0
        if correct_index < 0 or correct_index > 3:
            correct_index = 0
        cleaned.append(
            {
                "question_text": text[:280],
                "options": option_texts[:4],
                "correct_index": correct_index,
                "skill": str(item.get("skill") or "role").strip()[:48] or "role",
            }
        )
        if len(cleaned) >= count:
            break
    return cleaned


def _fallback_questions(count: int, skills: list[str], rng: random.Random) -> list[dict[str, Any]]:
    bank = list(_FALLBACK_BANK)
    rng.shuffle(bank)
    selected = bank[:count]
    extras: list[dict[str, Any]] = []
    for skill in skills:
        extras.append(
            {
                "question_text": f"In day-to-day work, which habit best shows real {skill} strength?",
                "options": [
                    f"Name-dropping {skill} without examples",
                    f"Using {skill} to deliver a measurable outcome",
                    "Avoiding documentation so only you understand it",
                    "Changing tools every week with no reason",
                ],
                "correct_index": 1,
                "skill": skill,
            }
        )
    pool = selected + extras
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in pool:
        key = str(item["question_text"]).casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= count:
            break
    while len(out) < count:
        item = bank[len(out) % len(bank)]
        clone = dict(item)
        clone["question_text"] = f"{item['question_text']} (scenario {len(out) + 1})"
        out.append(clone)
    return out[:count]


def generate_mcq_questions(
    *,
    count: int,
    job_title: str | None = None,
    resume_context: dict[str, str] | None = None,
    seed: str | None = None,
) -> list[dict[str, Any]]:
    """Return 8–10 four-option MCQs. Never raises: LLM first, then a local bank."""
    rng = random.Random(seed or "mcq")
    target = max(8, min(10, int(count or 8)))
    skills = _skills_from_context(resume_context, job_title)
    ctx = resume_context or {}
    questions: list[dict[str, Any]] = []

    if llama_available():
        system = (
            "You write a short professional screening quiz for a live interview. "
            "Create distinct multiple-choice questions at easy-to-medium difficulty. "
            "Each question has exactly 4 concise options and one clearly correct answer. "
            "Do not use trick wording, code-golf, or multi-select. "
            "Keep each question under 40 words. "
            'Return JSON: {"questions":[{"question_text":"...","options":["...","...","...","..."],'
            '"correct_index":0,"skill":"..."}]}'
        )
        user = (
            f"Job title: {job_title or ctx.get('job_position') or 'role'}\n"
            f"Resume summary: {ctx.get('resume_summary') or 'n/a'}\n"
            f"Skills: {ctx.get('skills') or ', '.join(skills) or 'n/a'}\n"
            f"JD requirements: {ctx.get('jd_requirements') or 'n/a'}\n"
            f"Create exactly {target} questions covering different skills and judgment."
        )
        try:
            payload = call_llama_json(system, user, temperature=0.35, max_tokens=2800)
            questions = _normalize_llm_questions(payload, target)
        except Exception:
            logger.exception("MCQ LLM generation failed; using fallback bank.")
            questions = []

    if len(questions) < target:
        questions.extend(_fallback_questions(target - len(questions), skills, rng))
        questions = questions[:target]

    built: list[dict[str, Any]] = []
    for index, item in enumerate(questions[:target], start=1):
        options, correct_id = _shuffle_options(
            list(item.get("options") or []),
            int(item.get("correct_index") or 0),
            rng,
        )
        built.append(
            {
                "id": f"mcq-{index}",
                "order": index,
                "question_text": str(item.get("question_text") or "").strip(),
                "options": options,
                "correct_option_id": correct_id,
                "skill": str(item.get("skill") or "role"),
                "answer_option_id": None,
                "skipped": False,
                "answered_at": None,
            }
        )
    return built
