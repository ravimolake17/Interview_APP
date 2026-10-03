"""Agent 3: dynamic Interview Blueprint Generator.

This module does NOT generate actual interview questions.

It consumes existing upstream screening output:
- resume_json
- jd_json / jd_text
- ATS score/status
- matched skills
- missing skills
- projects
- education/courses

It produces an Interview Blueprint Report for future Agent 4.

Required category order:
1. Introductory Questions
2. Skills & JD Keyword-related Questions
3. Project-related Questions
4. Education & Courses-related Questions
"""

from __future__ import annotations

import math
import re
from typing import Any, Iterable

from agents.blueprint_agent.schemas import (
    Agent4Metadata,
    CategoryBreakdown,
    DecisionFactor,
    DifficultyDistribution,
    FlowStep,
    HumanReadableReport,
    InputSummary,
    InterviewBlueprintRequest,
    InterviewBlueprintResponse,
    SkillFocusPlan,
)


WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]{1,}")

YEAR_RE = re.compile(
    r"(?:(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)|"
    r"(?:minimum|min|at least)\s+(\d+(?:\.\d+)?))",
    re.IGNORECASE,
)

SENIOR_WORDS = re.compile(
    r"\b(senior|sr\.?|lead|principal|architect|manager|head)\b",
    re.I,
)

MID_WORDS = re.compile(
    r"\b(mid|intermediate|experienced|specialist|consultant)\b",
    re.I,
)

ENTRY_WORDS = re.compile(
    r"\b(fresher|fresh graduate|entry[ -]?level|graduate trainee|intern)\b",
    re.I,
)

PROJECT_WORDS = re.compile(
    r"\b(project|portfolio|research|capstone|case study|prototype|application|system|platform|model)\b",
    re.I,
)

EDUCATION_WORDS = re.compile(
    r"\b(education|course|courses|degree|bachelor|master|diploma|certification|certificate|nptel|training|semester|college|university|cgpa|gpa|academic)\b",
    re.I,
)

SKILL_SECTION_WORDS = re.compile(
    r"\b(skill|technology|technologies|tool|framework|language|database|cloud|stack|keyword)\b",
    re.I,
)

EXPERIENCE_WORDS = re.compile(
    r"\b(experience|internship|employment|work history|professional experience)\b",
    re.I,
)


CATEGORY_IDS = [
    "introductory_questions",
    "skills_jd_keyword_questions",
    "project_related_questions",
    "education_courses_questions",
]

CATEGORY_NAMES = {
    "introductory_questions": "Introductory Questions",
    "skills_jd_keyword_questions": "Skills & JD Keyword-related Questions",
    "project_related_questions": "Project-related Questions",
    "education_courses_questions": "Education & Courses-related Questions",
}

CATEGORY_FOCUS = {
    "introductory_questions": [
        "candidate_context",
        "resume_summary_validation",
        "role_interest",
        "resume_jd_alignment_opening",
    ],
    "skills_jd_keyword_questions": [
        "matched_required_skills",
        "missing_jd_keywords",
        "preferred_skill_depth",
        "tool_and_framework_usage",
    ],
    "project_related_questions": [
        "project_walkthrough",
        "implementation_decisions",
        "jd_responsibility_mapping",
        "practical_problem_solving",
    ],
    "education_courses_questions": [
        "degree_relevance",
        "coursework_to_jd_mapping",
        "certification_validation",
        "academic_foundation",
    ],
}


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _dedupe(values: Iterable[Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = _clean_text(value).strip(" ,;|")

        if not cleaned:
            continue

        key = cleaned.casefold()

        if key not in seen:
            seen.add(key)
            output.append(cleaned)

    return output


def _flatten_strings(value: Any, max_items: int = 300) -> list[str]:
    output: list[str] = []

    def visit(item: Any) -> None:
        if len(output) >= max_items:
            return

        if isinstance(item, dict):
            for nested in item.values():
                visit(nested)

        elif isinstance(item, list):
            for nested in item:
                visit(nested)

        else:
            cleaned = _clean_text(item)

            if cleaned:
                output.append(cleaned)

    visit(value)

    return _dedupe(output)[:max_items]


def _get_nested(data: Any, *keys: str, default: Any = None) -> Any:
    current = data

    for key in keys:
        if not isinstance(current, dict):
            return default

        current = current.get(key, default)

    return current


def _word_count(text: str) -> int:
    return len(WORD_RE.findall(text or ""))


def _skill_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        values: list[Any] = []
        values.extend(_as_list(value.get("normalized")))
        values.extend(_as_list(value.get("raw")))
        values.extend(_as_list(value.get("items")))
        return _dedupe(values)

    return _dedupe(_as_list(value))


def _resume_text(resume_json: dict[str, Any]) -> str:
    source_text = _clean_text(resume_json.get("source_text"))

    if source_text:
        return source_text

    return "\n".join(_flatten_strings(resume_json, 500))


def _extract_jd(payload: InterviewBlueprintRequest) -> dict[str, Any]:
    evaluation_jd = _get_nested(
        payload.ats_evaluation_result,
        "extracted_jd_requirements",
        default={},
    )

    if isinstance(evaluation_jd, dict) and evaluation_jd:
        merged = dict(payload.jd_json)
        merged.update(evaluation_jd)
        return merged

    return payload.jd_json


def _required_preferred_skills(jd_json: dict[str, Any]) -> tuple[list[str], list[str]]:
    required = _skill_values(jd_json.get("required_skills"))
    preferred = _skill_values(jd_json.get("preferred_skills"))

    required.extend(_skill_values(jd_json.get("must_have_skills")))
    preferred.extend(_skill_values(jd_json.get("nice_to_have_skills")))

    required = _dedupe(required)
    required_keys = {skill.casefold() for skill in required}

    preferred = _dedupe(
        skill for skill in preferred if skill.casefold() not in required_keys
    )

    return required, preferred


def _extract_jd_keywords(jd_json: dict[str, Any], jd_text: str) -> list[str]:
    values: list[str] = []

    values.extend(_skill_values(jd_json.get("keywords")))

    for line in re.split(r"[\n,;|•·]+", jd_text or ""):
        cleaned = _clean_text(line)

        if SKILL_SECTION_WORDS.search(cleaned) and len(cleaned) <= 160:
            values.extend(re.split(r"[,;|/]+", cleaned))

    return _dedupe(value for value in values if 1 < len(_clean_text(value)) <= 80)[:25]


def _match_analysis_lists(
    evaluation: dict[str, Any],
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    match = (
        evaluation.get("match_analysis")
        if isinstance(evaluation.get("match_analysis"), dict)
        else {}
    )

    return (
        _skill_values(match.get("matched_required_skills")),
        _skill_values(match.get("missing_required_skills")),
        _skill_values(match.get("matched_preferred_skills")),
        _skill_values(match.get("missing_preferred_skills")),
        _skill_values(match.get("additional_candidate_skills")),
    )


def _contains(values: list[str], item: str) -> bool:
    key = item.casefold()
    return any(value.casefold() == key for value in values)


def _extract_resume_skills(payload: InterviewBlueprintRequest) -> list[str]:
    skills: list[str] = []

    for key in (
        "skills",
        "technical_skills",
        "core_skills",
        "tools",
        "technologies",
    ):
        skills.extend(_skill_values(payload.resume_json.get(key)))

    for section in _as_list(payload.resume_json.get("sections")):
        if not isinstance(section, dict):
            continue

        heading = _clean_text(section.get("heading"))
        raw_text = _clean_text(section.get("raw_text"))

        if SKILL_SECTION_WORDS.search(heading):
            skills.extend(_skill_values(section.get("items")))
            skills.extend(re.split(r"[,;|\n•·]+", raw_text))

    return _dedupe(skill for skill in skills if 1 < len(skill) <= 80)


def _section_evidence(
    resume_json: dict[str, Any],
    pattern: re.Pattern[str],
    max_items: int = 6,
) -> list[str]:
    evidence: list[str] = []

    for section in _as_list(resume_json.get("sections")):
        if not isinstance(section, dict):
            continue

        heading = _clean_text(section.get("heading"))
        raw_text = _clean_text(section.get("raw_text"))
        items = _flatten_strings(section.get("items"), 20)

        combined = "\n".join([heading, raw_text, *items])

        if pattern.search(heading) or pattern.search(combined):
            if raw_text:
                evidence.append(raw_text[:350])

            evidence.extend(item[:250] for item in items)

    return _dedupe(evidence)[:max_items]


def _extract_years(text: str) -> float | None:
    values: list[float] = []

    for match in YEAR_RE.finditer(text or ""):
        raw = match.group(1) or match.group(2)

        if raw:
            try:
                values.append(float(raw))
            except ValueError:
                continue

    return min(values) if values else None


def _first_number(*values: Any) -> float | None:
    for value in values:
        if value is None or value == "":
            continue

        try:
            number = float(value)
        except (TypeError, ValueError):
            continue

        if 0 <= number <= 100:
            return number

    return None


def _infer_candidate_level(
    relevant_years: float | None,
    total_years: float | None,
    jd_required_years: float | None,
    resume_text: str,
    jd_text: str,
    job_title: str,
) -> tuple[str, str]:
    years = relevant_years if relevant_years is not None else total_years
    combined_role_text = f"{job_title} {jd_text}"

    if years is None:
        if ENTRY_WORDS.search(resume_text) or ENTRY_WORDS.search(combined_role_text):
            return "Fresher", "Fresher/entry-level wording was detected."

        years = _extract_years(resume_text)

    if years is None:
        if jd_required_years is not None and jd_required_years >= 4:
            return (
                "Mid-level",
                f"Candidate years were not explicit, but JD asks for {jd_required_years:g}+ years.",
            )

        return (
            "Entry-level",
            "Candidate years were not explicit, so blueprint avoids senior assumptions.",
        )

    if years < 0.5:
        level = "Fresher"
    elif years < 1.5:
        level = "Entry-level"
    elif years < 3.5:
        level = "Junior"
    elif years < 6.5:
        level = "Mid-level"
    else:
        level = "Senior"

    if jd_required_years is not None and years < jd_required_years:
        reason = (
            f"Candidate shows about {years:g} relevant years while JD asks for "
            f"{jd_required_years:g}+ years, so gap validation is included."
        )
    else:
        reason = f"Candidate shows about {years:g} relevant years, so {level} interview depth is used."

    return level, reason


def _jd_seniority_score(
    job_title: str,
    jd_text: str,
    jd_required_years: float | None,
) -> int:
    combined = f"{job_title} {jd_text}"
    score = 0

    if SENIOR_WORDS.search(combined):
        score += 3
    elif MID_WORDS.search(combined):
        score += 2
    elif ENTRY_WORDS.search(combined):
        score -= 1

    if jd_required_years is not None:
        if jd_required_years >= 6:
            score += 3
        elif jd_required_years >= 3:
            score += 2
        elif jd_required_years >= 1:
            score += 1

    return max(0, min(score, 5))


def _jd_complexity_score(
    jd_text: str,
    jd_skill_count: int,
    responsibilities_count: int,
    seniority_score: int,
) -> tuple[int, str]:
    word_count = _word_count(jd_text)

    score = seniority_score

    if jd_skill_count >= 10:
        score += 3
    elif jd_skill_count >= 6:
        score += 2
    elif jd_skill_count >= 3:
        score += 1

    if responsibilities_count >= 7:
        score += 2
    elif responsibilities_count >= 3:
        score += 1

    if word_count >= 700:
        score += 2
    elif word_count >= 300:
        score += 1

    if score >= 7:
        return score, "high"
    if score >= 5:
        return score, "moderate-high"
    if score >= 2:
        return score, "moderate"

    return score, "basic"


def _resume_depth_label(
    word_count: int,
    sections_count: int,
    project_count: int,
) -> str:
    score = 0

    if word_count >= 450:
        score += 2
    elif word_count >= 220:
        score += 1

    if sections_count >= 6:
        score += 2
    elif sections_count >= 4:
        score += 1

    if project_count >= 3:
        score += 2
    elif project_count >= 1:
        score += 1

    if score >= 5:
        return "deep"
    if score >= 3:
        return "moderate"

    return "shallow"


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _allocate(
    total: int,
    weights: dict[str, float],
    minimums: dict[str, int] | None = None,
) -> dict[str, int]:
    active = {key: max(0.0, float(value)) for key, value in weights.items() if value > 0}

    if not active:
        first = next(iter(weights), "default")
        return {first: total}

    minimums = minimums or {}

    allocation = {
        key: min(int(minimums.get(key, 0)), total)
        for key in active
    }

    while sum(allocation.values()) > total:
        for key in reversed(list(allocation)):
            if allocation[key] > 0 and sum(allocation.values()) > total:
                allocation[key] -= 1

    remaining = total - sum(allocation.values())
    total_weight = sum(active.values()) or 1.0

    raw = {
        key: (active[key] / total_weight) * remaining
        for key in active
    }

    floors = {
        key: int(math.floor(value))
        for key, value in raw.items()
    }

    for key, value in floors.items():
        allocation[key] += value

    left = total - sum(allocation.values())

    remainders = sorted(
        ((raw[key] - floors[key], key) for key in active),
        reverse=True,
    )

    for _fraction, key in remainders[:left]:
        allocation[key] += 1

    return allocation


def _total_questions(
    candidate_level: str,
    ats_score: float,
    jd_skill_count: int,
    missing_count: int,
    project_count: int,
    education_count: int,
    jd_complexity_score: int,
    resume_depth_label: str,
) -> int:
    base_by_level = {
        "Fresher": 9,
        "Entry-level": 10,
        "Junior": 12,
        "Mid-level": 14,
        "Senior": 16,
    }

    total = base_by_level.get(candidate_level, 10)

    if jd_skill_count >= 5:
        total += 2
    if jd_skill_count >= 9:
        total += 2

    if missing_count >= 2:
        total += 1
    if missing_count >= 5:
        total += 2

    if project_count >= 2:
        total += 2
    elif project_count == 1:
        total += 1

    if education_count >= 2 and candidate_level in {"Fresher", "Entry-level", "Junior"}:
        total += 1

    if jd_complexity_score >= 7:
        total += 3
    elif jd_complexity_score >= 5:
        total += 2
    elif jd_complexity_score >= 2:
        total += 1

    if ats_score >= 80 and resume_depth_label == "deep":
        total += 1

    limits = {
        "Fresher": (8, 14),
        "Entry-level": (9, 16),
        "Junior": (10, 19),
        "Mid-level": (12, 22),
        "Senior": (14, 26),
    }.get(candidate_level, (8, 20))

    return _clamp(total, *limits)


def _difficulty_weights(
    candidate_level: str,
    ats_score: float,
    missing_ratio: float,
    jd_seniority_score: int,
) -> dict[str, float]:
    weights_by_level = {
        "Fresher": {"easy": 0.55, "medium": 0.35, "hard": 0.10},
        "Entry-level": {"easy": 0.45, "medium": 0.40, "hard": 0.15},
        "Junior": {"easy": 0.34, "medium": 0.45, "hard": 0.21},
        "Mid-level": {"easy": 0.24, "medium": 0.45, "hard": 0.31},
        "Senior": {"easy": 0.15, "medium": 0.40, "hard": 0.45},
    }

    weights = dict(weights_by_level.get(candidate_level, weights_by_level["Entry-level"]))

    if ats_score >= 80:
        weights["hard"] += 0.08
        weights["easy"] -= 0.05

    elif ats_score < 55:
        weights["easy"] += 0.10
        weights["hard"] -= 0.05

    if missing_ratio >= 0.45:
        weights["medium"] += 0.08
        weights["easy"] += 0.04
        weights["hard"] -= 0.06

    elif missing_ratio <= 0.15 and ats_score >= 70:
        weights["hard"] += 0.05
        weights["easy"] -= 0.03

    if jd_seniority_score >= 4:
        weights["hard"] += 0.10
        weights["easy"] -= 0.06

    return {key: max(0.05, value) for key, value in weights.items()}


def _difficulty_distribution(
    total_questions: int,
    weights: dict[str, float],
) -> dict[str, int]:
    minimums = {"easy": 1, "medium": 1, "hard": 1}
    return _allocate(total_questions, weights, minimums)


def _category_importance_weights(
    candidate_level: str,
    resume_depth_label: str,
    jd_complexity_score: int,
    jd_skill_count: int,
    matched_count: int,
    missing_count: int,
    project_count: int,
    education_count: int,
    ats_score: float,
) -> dict[str, float]:
    weights = {
        "introductory_questions": 0.12,
        "skills_jd_keyword_questions": 0.38,
        "project_related_questions": 0.20,
        "education_courses_questions": 0.14,
    }

    if resume_depth_label == "shallow":
        weights["introductory_questions"] += 0.05
    elif resume_depth_label == "deep":
        weights["introductory_questions"] -= 0.02

    weights["skills_jd_keyword_questions"] += min(jd_skill_count, 10) * 0.018
    weights["skills_jd_keyword_questions"] += min(missing_count, 6) * 0.025
    weights["skills_jd_keyword_questions"] += min(matched_count, 8) * 0.008

    if jd_complexity_score >= 5:
        weights["skills_jd_keyword_questions"] += 0.07

    if project_count >= 3:
        weights["project_related_questions"] += 0.14
    elif project_count == 2:
        weights["project_related_questions"] += 0.10
    elif project_count == 1:
        weights["project_related_questions"] += 0.06
    else:
        weights["project_related_questions"] -= 0.08

    if candidate_level in {"Mid-level", "Senior"} and project_count:
        weights["project_related_questions"] += 0.05

    if candidate_level in {"Fresher", "Entry-level"}:
        weights["education_courses_questions"] += 0.10

    if education_count >= 3:
        weights["education_courses_questions"] += 0.08
    elif education_count >= 1:
        weights["education_courses_questions"] += 0.04
    else:
        weights["education_courses_questions"] -= 0.05

    if ats_score < 55:
        weights["introductory_questions"] += 0.03
        weights["education_courses_questions"] += 0.03

    return {key: max(0.05, value) for key, value in weights.items()}


def _holistic_total_minutes(
    total_questions: int,
    candidate_level: str,
    resume_word_count: int,
    resume_depth_label: str,
    jd_complexity_score: int,
    jd_word_count: int,
    project_count: int,
    education_count: int,
    jd_skill_count: int,
    missing_count: int,
) -> tuple[int, int]:
    minutes = 18

    if candidate_level in {"Fresher", "Entry-level"}:
        minutes += 4
    elif candidate_level == "Junior":
        minutes += 7
    elif candidate_level == "Mid-level":
        minutes += 11
    else:
        minutes += 15

    if resume_depth_label == "deep":
        minutes += 8
    elif resume_depth_label == "moderate":
        minutes += 4

    if jd_complexity_score >= 7:
        minutes += 10
    elif jd_complexity_score >= 5:
        minutes += 7
    elif jd_complexity_score >= 2:
        minutes += 4

    if project_count >= 3:
        minutes += 6
    elif project_count >= 1:
        minutes += 3

    if education_count >= 3 and candidate_level in {"Fresher", "Entry-level", "Junior"}:
        minutes += 4
    elif education_count >= 1:
        minutes += 2

    if jd_skill_count >= 8:
        minutes += 5
    elif jd_skill_count >= 4:
        minutes += 3

    if missing_count >= 4:
        minutes += 4
    elif missing_count >= 1:
        minutes += 2

    if jd_word_count >= 700 or resume_word_count >= 700:
        minutes += 5

    minimum_needed = 20 if total_questions <= 10 else 25 if total_questions <= 14 else 30

    minutes = _clamp(minutes, minimum_needed, 75)
    minutes = int(5 * round(minutes / 5))

    buffer_minutes = _buffer_for_minutes(minutes)

    return minutes, buffer_minutes


def _buffer_for_minutes(minutes: int) -> int:
    if minutes <= 12:
        return 2
    if minutes <= 25:
        return 3
    if minutes <= 40:
        return 4
    if minutes <= 55:
        return 5
    return 6


def _scale_questions_for_duration(
    base_questions: int,
    base_minutes: int,
    target_minutes: int,
    candidate_level: str,
) -> int:
    """Adjust question count when HR overrides total interview time."""
    scale = target_minutes / max(base_minutes, 1)
    scaled = int(round(base_questions * scale))
    # Four blueprint categories each need at least one question.
    category_floor = len(CATEGORY_IDS)
    duration_floor = max(category_floor, int(round(target_minutes / 2.5)))
    duration_cap = max(duration_floor, int(round(target_minutes / 1.6)))
    if target_minutes <= 20:
        low, high = duration_floor, min(10, duration_cap)
    else:
        limits = {
            "Fresher": (8, 14),
            "Entry-level": (9, 16),
            "Junior": (10, 19),
            "Mid-level": (12, 22),
            "Senior": (14, 26),
        }.get(candidate_level, (8, 20))
        low = max(category_floor, min(limits[0] - 2, duration_floor))
        high = min(60, max(limits[1] + 4, duration_cap))
    return _clamp(scaled, low, high)


def _category_difficulty_bias(
    category_id: str,
    global_weights: dict[str, float],
) -> dict[str, float]:
    weights = dict(global_weights)

    if category_id == "introductory_questions":
        weights["easy"] += 0.14
        weights["hard"] -= 0.08

    elif category_id == "skills_jd_keyword_questions":
        weights["medium"] += 0.08
        weights["hard"] += 0.06

    elif category_id == "project_related_questions":
        weights["medium"] += 0.08
        weights["hard"] += 0.04

    elif category_id == "education_courses_questions":
        weights["easy"] += 0.08
        weights["medium"] += 0.04
        weights["hard"] -= 0.04

    return {key: max(0.04, value) for key, value in weights.items()}


def _category_purpose(category_id: str) -> str:
    return {
        "introductory_questions": (
            "Open the interview by validating candidate profile, role understanding, "
            "and resume/JD alignment."
        ),
        "skills_jd_keyword_questions": (
            "Validate matched skills, missing JD skills, preferred skills, and JD keywords "
            "using resume evidence."
        ),
        "project_related_questions": (
            "Map resume projects to JD responsibilities and validate practical implementation depth."
        ),
        "education_courses_questions": (
            "Check how education, courses, certifications, and academic foundations support JD requirements."
        ),
    }[category_id]


def _category_instruction(category_id: str) -> str:
    return {
        "introductory_questions": (
            "Generate opening questions only from candidate resume summary/profile signals "
            "and the target JD role. Avoid generic self-introduction questions."
        ),
        "skills_jd_keyword_questions": (
            "Generate questions by cross-referencing resume skills/evidence with JD required skills, "
            "preferred skills, keywords, responsibilities, and upstream ATS missing skills."
        ),
        "project_related_questions": (
            "Generate questions only from resume projects/research/internship work and connect "
            "each question to one or more JD responsibilities or skills."
        ),
        "education_courses_questions": (
            "Generate questions from education, courses, certifications, degree subjects, "
            "and academic evidence, mapped to JD skills and requirements."
        ),
    }[category_id]


def _top(values: list[str], default: str, count: int = 3) -> list[str]:
    cleaned = _dedupe(values)
    return cleaned[:count] if cleaned else [default]


def _priority_label(score: int) -> str:
    if score >= 92:
        return "critical"
    if score >= 78:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def _difficulty_focus_for_skill(source: str, candidate_level: str) -> list[str]:
    if source in {"missing_required", "missing_preferred", "jd_only"}:
        return ["easy", "medium"]

    if candidate_level in {"Mid-level", "Senior"}:
        return ["medium", "hard"]

    if candidate_level == "Junior":
        return ["easy", "medium", "hard"]

    return ["easy", "medium"]


def _find_evidence(skill: str, evidence_values: list[str], fallback: str) -> str:
    key = skill.casefold()

    for value in evidence_values:
        if key in value.casefold():
            return value[:280]

    return fallback


def _skill_source(
    skill: str,
    required: list[str],
    preferred: list[str],
    matched: list[str],
    missing: list[str],
) -> str:
    if _contains(missing, skill) and _contains(required, skill):
        return "missing_required"

    if _contains(missing, skill) and _contains(preferred, skill):
        return "missing_preferred"

    if _contains(matched, skill) and _contains(required, skill):
        return "matched_required"

    if _contains(matched, skill) and _contains(preferred, skill):
        return "matched_preferred"

    if _contains(required, skill):
        return "matched_required"

    if _contains(preferred, skill):
        return "matched_preferred"

    return "jd_only"


def _build_skill_focus_plan(
    required_skills: list[str],
    preferred_skills: list[str],
    jd_keywords: list[str],
    ats_matched: list[str],
    ats_missing: list[str],
    resume_skills: list[str],
    resume_evidence_values: list[str],
    jd_evidence_values: list[str],
    skills_question_count: int,
    candidate_level: str,
) -> list[SkillFocusPlan]:
    candidates: dict[str, dict[str, Any]] = {}

    def add(skill: str, source: str, score: int) -> None:
        key = skill.casefold()

        if key in candidates and candidates[key]["score"] >= score:
            return

        candidates[key] = {
            "skill": skill,
            "source": source,
            "score": score,
        }

    for skill in ats_missing:
        source = _skill_source(skill, required_skills, preferred_skills, ats_matched, ats_missing)
        add(skill, source, 96 if source == "missing_required" else 74)

    for skill in ats_matched:
        source = _skill_source(skill, required_skills, preferred_skills, ats_matched, ats_missing)
        add(skill, source, 90 if source == "matched_required" else 78)

    for skill in required_skills:
        source = _skill_source(skill, required_skills, preferred_skills, ats_matched, ats_missing)
        add(skill, source, 86)

    for skill in preferred_skills:
        source = _skill_source(skill, required_skills, preferred_skills, ats_matched, ats_missing)
        add(skill, source, 72)

    for skill in jd_keywords:
        add(skill, "jd_only", 58)

    for skill in resume_skills[:12]:
        if not _contains(required_skills + preferred_skills + jd_keywords, skill):
            add(skill, "resume_only_relevant", 38)

    ordered = sorted(
        candidates.values(),
        key=lambda item: (-item["score"], item["skill"].casefold()),
    )[:12]

    if not ordered:
        return [
            SkillFocusPlan(
                skill_name="General JD skill fit",
                source="jd_only",
                priority="medium",
                planned_question_count=skills_question_count,
                difficulty_focus=["easy", "medium"],
                validation_goal=(
                    "Validate general role readiness because the upstream ATS result did not expose "
                    "specific skill lists."
                ),
                jd_evidence="JD text/JD JSON provided.",
            )
        ]

    allocation = _allocate(
        skills_question_count,
        {item["skill"]: item["score"] for item in ordered},
    )

    result: list[SkillFocusPlan] = []

    for item in ordered:
        skill = item["skill"]
        source = item["source"]
        score = int(item["score"])

        if source in {"missing_required", "missing_preferred", "jd_only"}:
            goal = (
                f"Check whether the candidate can reason about {skill} despite "
                "the upstream ATS skill/JD keyword gap."
            )
        elif source == "resume_only_relevant":
            goal = (
                f"Verify whether resume-only skill {skill} can transfer to JD responsibilities."
            )
        else:
            goal = (
                f"Validate practical depth and truthful usage of {skill} from matched "
                "resume and JD evidence."
            )

        result.append(
            SkillFocusPlan(
                skill_name=skill,
                source=source,
                priority=_priority_label(score),
                planned_question_count=allocation.get(skill, 0),
                difficulty_focus=_difficulty_focus_for_skill(source, candidate_level),
                validation_goal=goal,
                resume_evidence=_find_evidence(
                    skill,
                    resume_evidence_values,
                    "Present in upstream resume skill output.",
                )
                if source not in {"missing_required", "missing_preferred", "jd_only"}
                else "",
                jd_evidence=_find_evidence(
                    skill,
                    jd_evidence_values,
                    "Present in upstream JD/ATS output.",
                )
                if source != "resume_only_relevant"
                else "",
                related_keywords=jd_keywords[:6],
            )
        )

    return result


def _build_category_breakdown(
    category_counts: dict[str, int],
    category_minutes: dict[str, int],
    category_percentages: dict[str, float],
    difficulty_weights: dict[str, float],
    resume_signals: dict[str, list[str]],
    jd_signals: dict[str, list[str]],
    category_reasons: dict[str, str],
) -> list[CategoryBreakdown]:
    result: list[CategoryBreakdown] = []

    for order, category_id in enumerate(CATEGORY_IDS, start=1):
        question_count = int(category_counts.get(category_id, 0))
        if question_count < 1:
            question_count = 1

        difficulty_mix = _difficulty_distribution(
            question_count,
            _category_difficulty_bias(category_id, difficulty_weights),
        )

        result.append(
            CategoryBreakdown(
                order=order,
                category_id=category_id,  # type: ignore[arg-type]
                category_name=CATEGORY_NAMES[category_id],
                question_count=question_count,
                difficulty_mix=difficulty_mix,
                estimated_minutes=category_minutes.get(category_id, 1),
                time_percentage=category_percentages.get(category_id, 0.0),
                question_type_focus=CATEGORY_FOCUS[category_id],
                purpose=_category_purpose(category_id),
                selection_reason=category_reasons[category_id],
                candidate_resume_signals=resume_signals.get(category_id, []),
                jd_signals=jd_signals.get(category_id, []),
                cross_reference_basis=[
                    "Candidate resume JSON",
                    "JD text / JD JSON",
                    "Upstream ATS matched skills, missing skills, score, and status",
                ],
                agent4_generation_instruction=_category_instruction(category_id),
            )
        )

    return result


def _build_flow(categories: list[CategoryBreakdown]) -> list[FlowStep]:
    return [
        FlowStep(
            step_order=item.order,
            stage_name=item.category_name,
            category_ids=[item.category_id],
            question_count=item.question_count,
            estimated_minutes=item.estimated_minutes,
            interviewer_action=item.agent4_generation_instruction,
        )
        for item in categories
    ]


class InterviewBlueprintGenerator:
    """
    Main Agent 3 generator.

    No LLM/API call here.
    No actual questions here.
    Only blueprint planning from upstream screening output.
    """

    def generate(
        self,
        payload: InterviewBlueprintRequest,
    ) -> InterviewBlueprintResponse:
        jd_json = _extract_jd(payload)
        evaluation = payload.ats_evaluation_result

        resume_text = _resume_text(payload.resume_json)
        jd_text = payload.jd_text or "\n".join(_flatten_strings(jd_json, 120))

        job_title = _clean_text(jd_json.get("job_title")) or _clean_text(
            _get_nested(
                evaluation,
                "extracted_jd_requirements",
                "job_title",
                default="",
            )
        )

        required_skills, preferred_skills = _required_preferred_skills(jd_json)
        jd_keywords = _extract_jd_keywords(jd_json, jd_text)

        (
            matched_required,
            missing_required,
            matched_preferred,
            missing_preferred,
            additional_skills,
        ) = _match_analysis_lists(evaluation)

        ats = payload.ats_match_result

        ats_matched = _dedupe(
            ats.matched_skills + matched_required + matched_preferred
        )

        ats_missing = _dedupe(
            ats.missing_skills + missing_required + missing_preferred
        )

        resume_skills = _extract_resume_skills(payload)

        total_years = _first_number(
            evaluation.get("candidate_experience_years"),
            _get_nested(
                evaluation,
                "experience_assessment",
                "candidate_total_experience_years",
            ),
        )

        relevant_years = _first_number(
            evaluation.get("candidate_relevant_experience_years"),
            _get_nested(
                evaluation,
                "experience_assessment",
                "candidate_relevant_experience_years",
            ),
        )

        jd_required_years = _first_number(
            jd_json.get("minimum_experience_years"),
            _get_nested(
                evaluation,
                "experience_assessment",
                "minimum_required_years",
            ),
            _extract_years(jd_text),
        )

        project_evidence = _section_evidence(payload.resume_json, PROJECT_WORDS, 8)
        education_evidence = _section_evidence(payload.resume_json, EDUCATION_WORDS, 8)
        experience_evidence = _section_evidence(payload.resume_json, EXPERIENCE_WORDS, 6)

        resume_word_count = _word_count(resume_text)
        jd_word_count = _word_count(jd_text)
        sections_count = len(_as_list(payload.resume_json.get("sections")))

        project_count = len(project_evidence)
        education_count = len(education_evidence)

        resume_depth = _resume_depth_label(
            resume_word_count,
            sections_count,
            project_count,
        )

        candidate_level, level_reason = _infer_candidate_level(
            relevant_years,
            total_years,
            jd_required_years,
            resume_text,
            jd_text,
            job_title,
        )
        if payload.candidate_level:
            candidate_level = payload.candidate_level
            level_reason = (
                f"HR set candidate level to {candidate_level} for this blueprint."
            )

        jd_seniority = _jd_seniority_score(
            job_title,
            jd_text,
            jd_required_years,
        )

        jd_skill_count = len(
            _dedupe(required_skills + preferred_skills + jd_keywords)
        )

        responsibilities_count = len(_as_list(jd_json.get("responsibilities")))

        jd_complexity, complexity_label = _jd_complexity_score(
            jd_text,
            jd_skill_count,
            responsibilities_count,
            jd_seniority,
        )

        ats_score = float(ats.overall_score)
        matched_count = len(ats_matched)
        missing_count = len(ats_missing)

        missing_ratio = missing_count / max(
            jd_skill_count,
            matched_count + missing_count,
            1,
        )

        total_questions = _total_questions(
            candidate_level,
            ats_score,
            jd_skill_count,
            missing_count,
            project_count,
            education_count,
            jd_complexity,
            resume_depth,
        )

        difficulty_weights = _difficulty_weights(
            candidate_level,
            ats_score,
            missing_ratio,
            jd_seniority,
        )

        difficulty_counts = _difficulty_distribution(
            total_questions,
            difficulty_weights,
        )

        difficulty_reason = (
            f"{candidate_level} profile, ATS score {ats_score:g}, "
            f"{matched_count} matched skills, {missing_count} missing skills, "
            f"{resume_depth} resume depth, and {complexity_label} JD complexity "
            f"produced this mix. {level_reason}"
        )

        category_weights = _category_importance_weights(
            candidate_level,
            resume_depth,
            jd_complexity,
            jd_skill_count,
            matched_count,
            missing_count,
            project_count,
            education_count,
            ats_score,
        )

        category_counts = _allocate(
            total_questions,
            category_weights,
            {key: 1 for key in CATEGORY_IDS},
        )

        total_minutes, buffer_minutes = _holistic_total_minutes(
            total_questions,
            candidate_level,
            resume_word_count,
            resume_depth,
            jd_complexity,
            jd_word_count,
            project_count,
            education_count,
            jd_skill_count,
            missing_count,
        )

        if payload.total_duration_minutes is not None:
            target_minutes = int(5 * round(payload.total_duration_minutes / 5))
            target_minutes = _clamp(target_minutes, 10, 120)
            if target_minutes != total_minutes:
                total_questions = _scale_questions_for_duration(
                    total_questions,
                    total_minutes,
                    target_minutes,
                    candidate_level,
                )
                total_questions = max(len(CATEGORY_IDS), total_questions)
                difficulty_counts = _difficulty_distribution(
                    total_questions,
                    difficulty_weights,
                )
                category_counts = _allocate(
                    total_questions,
                    category_weights,
                    {key: 1 for key in CATEGORY_IDS},
                )
            total_minutes = target_minutes
            buffer_minutes = _buffer_for_minutes(total_minutes)
            difficulty_reason = (
                f"{difficulty_reason} HR set total interview time to "
                f"{total_minutes} minutes."
            )

        usable_minutes = total_minutes - buffer_minutes

        category_minutes = _allocate(
            usable_minutes,
            category_weights,
            {key: 1 for key in CATEGORY_IDS},
        )

        category_percentages = {
            key: round((minutes / max(usable_minutes, 1)) * 100, 1)
            for key, minutes in category_minutes.items()
        }

        resume_signals = {
            "introductory_questions": _top(
                [
                    _clean_text(payload.resume_json.get("candidate_name")),
                    *experience_evidence,
                    resume_text[:220],
                ],
                "Resume profile and extracted sections are available for opening context.",
                3,
            ),
            "skills_jd_keyword_questions": _top(
                resume_skills + ats_matched,
                "Resume skills were limited; use upstream matched/missing skill output.",
                6,
            ),
            "project_related_questions": _top(
                project_evidence,
                "No strong project evidence found; keep this category lighter and resume-grounded.",
                4,
            ),
            "education_courses_questions": _top(
                education_evidence,
                "No detailed education/course evidence found; use only available education fields.",
                4,
            ),
        }

        jd_signals = {
            "introductory_questions": _top(
                [job_title, *_flatten_strings(jd_json.get("responsibilities"), 4)],
                "JD role context provided.",
                4,
            ),
            "skills_jd_keyword_questions": _top(
                required_skills + preferred_skills + jd_keywords + ats_missing,
                "JD skills/keywords were limited; use JD responsibilities as role signal.",
                8,
            ),
            "project_related_questions": _top(
                _flatten_strings(jd_json.get("responsibilities"), 8)
                + required_skills,
                "Map projects to JD responsibilities and required skills.",
                6,
            ),
            "education_courses_questions": _top(
                _flatten_strings(jd_json.get("education_requirements"), 5)
                + required_skills,
                "Map courses/education to JD skill requirements.",
                6,
            ),
        }

        category_reasons = {
            "introductory_questions": (
                f"Opening allocation is based on {resume_depth} resume depth, "
                f"ATS status '{ats.status}', and candidate-JD context."
            ),
            "skills_jd_keyword_questions": (
                f"Highest weight because upstream ATS found {matched_count} matched and "
                f"{missing_count} missing skills across {jd_skill_count} JD skills/keywords."
            ),
            "project_related_questions": (
                f"Project allocation is {'increased' if project_count else 'kept lighter'} "
                f"because {project_count} project/research evidence items were found."
            ),
            "education_courses_questions": (
                f"Education/course allocation reflects {education_count} education/course "
                f"evidence items and {candidate_level} candidate level."
            ),
        }

        categories = _build_category_breakdown(
            category_counts,
            category_minutes,
            category_percentages,
            difficulty_weights,
            resume_signals,
            jd_signals,
            category_reasons,
        )

        resume_evidence_values = _flatten_strings(payload.resume_json, 250)
        jd_evidence_values = _flatten_strings(jd_json, 180) + [jd_text]

        skill_focus_plan = _build_skill_focus_plan(
            required_skills,
            preferred_skills,
            jd_keywords,
            ats_matched,
            ats_missing,
            resume_skills + additional_skills,
            resume_evidence_values,
            jd_evidence_values,
            category_counts.get("skills_jd_keyword_questions", 0),
            candidate_level,
        )

        flow = _build_flow(categories)

        decision_factors = [
            DecisionFactor(
                factor="Required category order",
                observed_value=(
                    "Introductory → Skills/JD Keywords → Projects → Education/Courses"
                ),
                impact="Agent 4 must follow this order exactly.",
            ),
            DecisionFactor(
                factor="Upstream ATS score/status",
                observed_value=f"{ats_score:g} / {ats.status}",
                impact="Controls interview depth only; Agent 3 does not change shortlist status.",
            ),
            DecisionFactor(
                factor="Resume depth and JD complexity",
                observed_value=(
                    f"resume {resume_depth} ({resume_word_count} words); "
                    f"JD {complexity_label} ({jd_word_count} words)"
                ),
                impact="Controls total interview time and category time distribution.",
            ),
            DecisionFactor(
                factor="Skill and keyword match",
                observed_value=(
                    f"{matched_count} matched, {missing_count} missing, "
                    f"{jd_skill_count} JD skills/keywords"
                ),
                impact="Drives Skills & JD Keyword-related category and skill focus plan.",
            ),
            DecisionFactor(
                factor="Projects and education evidence",
                observed_value=(
                    f"{project_count} project signals, "
                    f"{education_count} education/course signals"
                ),
                impact=(
                    "More project time when projects are rich; more education/course time "
                    "for fresher or education-heavy profiles."
                ),
            ),
        ]

        risk_flags: list[str] = []

        if missing_count:
            risk_flags.append(
                f"Upstream ATS reports missing JD skills/keywords: {', '.join(ats_missing[:6])}."
            )

        if ats_score < 55:
            risk_flags.append(
                "ATS score is below review threshold, so fundamentals should be checked first."
            )

        if (
            jd_required_years is not None
            and relevant_years is not None
            and relevant_years < jd_required_years
        ):
            risk_flags.append(
                f"Relevant experience appears below JD minimum "
                f"({relevant_years:g} vs {jd_required_years:g} years)."
            )

        if not project_count:
            risk_flags.append(
                "No strong project evidence was found; project questions must stay limited."
            )

        if not education_count and candidate_level in {"Fresher", "Entry-level"}:
            risk_flags.append(
                "Education/course evidence is limited for an early-level candidate."
            )

        recommended_flow = [
            f"{item.step_order}. {item.stage_name}: "
            f"{item.question_count} question slots, about {item.estimated_minutes} minutes."
            for item in flow
        ]

        interviewer_notes = [
            "Agent 3 returns a blueprint only; Agent 4 should generate actual live questions.",
            "Every category must cross-reference candidate resume evidence with JD requirements.",
            "Avoid generic questions.",
            "Time is holistic category-level time, not fixed/equal time per question.",
            "Do not recalculate or override Upstream ATS score/status during the live interview.",
        ]

        if skill_focus_plan:
            interviewer_notes.append(
                "Highest-priority skill/JD keyword validation: "
                + ", ".join(
                    f"{item.skill_name} ({item.priority})"
                    for item in skill_focus_plan[:4]
                )
                + "."
            )

        time_reason = (
            f"Total interview time is {total_minutes} minutes with "
            f"{buffer_minutes} minutes buffer. Category minutes are weighted by "
            f"resume depth ({resume_depth}), JD complexity ({complexity_label}), "
            "skill/keyword match depth, project evidence, and education/course evidence. "
            "They are not equal per question."
        )

        return InterviewBlueprintResponse(
            candidate_level=candidate_level,  # type: ignore[arg-type]
            input_summary=InputSummary(
                job_title=job_title,
                ats_score=ats_score,
                ats_status=ats.status,
                candidate_experience_years=total_years,
                candidate_relevant_experience_years=relevant_years,
                jd_required_experience_years=jd_required_years,
                resume_word_count=resume_word_count,
                resume_depth_label=resume_depth,
                jd_word_count=jd_word_count,
                jd_complexity_label=complexity_label,
                matched_skills_count=matched_count,
                missing_skills_count=missing_count,
                jd_required_skills_count=len(required_skills),
                jd_preferred_skills_count=len(preferred_skills),
                project_evidence_count=project_count,
                education_course_evidence_count=education_count,
            ),
            total_questions=total_questions,
            difficulty_distribution=DifficultyDistribution(
                easy=difficulty_counts.get("easy", 0),
                medium=difficulty_counts.get("medium", 0),
                hard=difficulty_counts.get("hard", 0),
                reasoning=difficulty_reason,
            ),
            category_breakdown=categories,
            time_allocation={
                "total_duration_minutes": total_minutes,
                "buffer_minutes": buffer_minutes,
                "category_minutes": category_minutes,
                "category_percentages": category_percentages,
                "time_distribution_basis": [
                    (
                        f"Resume length/depth: {resume_word_count} words, "
                        f"{sections_count} sections, {resume_depth} depth"
                    ),
                    (
                        f"JD complexity: {jd_word_count} words, {jd_skill_count} "
                        f"skills/keywords, {responsibilities_count} responsibilities, "
                        f"{complexity_label}"
                    ),
                    (
                        f"Candidate-JD match: {matched_count} matched skills and "
                        f"{missing_count} missing skills"
                    ),
                    f"Project evidence count: {project_count}",
                    f"Education/course evidence count: {education_count}",
                ],
                "reasoning": time_reason,
            },
            skill_focus_plan=skill_focus_plan,
            interview_flow=flow,
            decision_factors=decision_factors,
            agent4_metadata=Agent4Metadata(
                guardrails=[
                    "Generate actual questions only in Agent 4.",
                    "Follow the required category order exactly.",
                    "Use upstream ATS output as truth for ATS score, matched skills, missing skills, and experience assessment.",
                    "Ground every question in resume evidence plus JD evidence.",
                    "Do not generate generic standalone questions.",
                    "Use holistic category time allocation; do not force equal time per question.",
                ]
            ),
            human_readable_report=HumanReadableReport(
                summary=(
                    f"Plan a {total_minutes}-minute {candidate_level} interview blueprint "
                    f"with {total_questions} question slots across Introductory, "
                    "Skills/JD Keywords, Project, and Education/Courses categories."
                ),
                recommended_flow=recommended_flow,
                interviewer_notes=interviewer_notes,
                risk_flags=risk_flags,
            ),
        )


def generate_interview_blueprint(
    payload: InterviewBlueprintRequest,
) -> InterviewBlueprintResponse:
    return InterviewBlueprintGenerator().generate(payload)


# Backward compatibility for old route/import names.
# It still returns blueprint, not actual questions.
def generate_interview_questions(
    payload: InterviewBlueprintRequest,
) -> InterviewBlueprintResponse:
    return generate_interview_blueprint(payload)