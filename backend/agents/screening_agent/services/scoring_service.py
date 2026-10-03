from __future__ import annotations

import re

from agents.screening_agent.config import settings
from agents.screening_agent.schemas.ats import (
    CandidateProfile,
    ExperienceAssessment,
    ExperienceEntry,
    ExperienceEntryAssessment,
    MatchAnalysis,
    ParsedJD,
    ResponsibilityMatch,
    ScoreBreakdown,
    SkillExperienceAssessment,
    SkillExperienceRequirement,
)
from agents.screening_agent.services.responsibility_matcher import match_responsibilities
from agents.screening_agent.utils.skill_normalizer import (
    find_known_skills,
    normalize_skill,
    normalize_skills,
    skill_search_terms,
    skills_implying,
)
from agents.screening_agent.utils.text_utils import (
    dedupe_preserve,
)


_GENERIC_TERMS = {
    "a",
    "an",
    "and",
    "the",
    "with",
    "for",
    "from",
    "into",
    "using",
    "role",
    "work",
    "working",
    "experience",
    "years",
    "year",
    "candidate",
    "team",
    "company",
    "organization",
    "senior",
    "junior",
    "lead",
    "professional",
    "required",
    "preferred",
    "strong",
    "knowledge",
    "responsible",
    "responsibilities",
    "minimum",
    "maximum",
    "business",
    "data",
    "solution",
    "solutions",
    "project",
    "projects",
    "support",
    "enterprise",
    "relevant",
    "including",
    "amp",
    "applications",
    "models",
    "design",
    "intelligent",
    "scalable",
    "ability",
    "various",
    "multiple",
    "etc",
    "well",
    "new",
    "high",
    "quality",
    "based",
    "across",
    "within",
    "environment",
    "environments",
    "industry",
    "field",
    "area",
    "areas",
    "duties",
    "job",
    "position",
    "description",
    "engineer",
    "engineering",
    "development",
    "developer",
    "build",
    "built",
    "develop",
    "developed",
    "create",
    "created",
    "implement",
    "implemented",
    "maintain",
    "maintained",
    "prepare",
    "prepared",
    "collect",
    "application",
    "design",
    "model",
}


_ADJACENT_EDUCATION_FIELDS = {
    "computing": {"data", "engineering"},
    "data": {"computing", "engineering"},
    "engineering": {"computing", "data"},
    "business": set(),
}

_TECHNICAL_JD_SKILL_HINT = re.compile(
    r"python|java|javascript|typescript|c\+\+|"
    r"tensorflow|pytorch|keras|machine learning|deep learning|"
    r"large language|generative ai|\bnlp\b|computer vision|"
    r"fastapi|django|flask|react|node\.?js|kubernetes|"
    r"data science|\bsql\b|azure|\baws\b|\bgcp\b",
    re.I,
)


def _education_level(
    text: str,
) -> int:
    value = text.casefold()

    if re.search(
        r"ph\.?d|doctorate",
        value,
    ):
        return 4

    if re.search(
        r"master(?:'s)?|m\.?tech|mca|mba|"
        r"m\.?sc|m\.?com|m\.?e\.?\b|\bme\b|"
        r"post\s*graduate",
        value,
    ):
        return 3

    if re.search(
        r"bachelor(?:'s)?|b\.?tech|bca|bba|"
        r"b\.?sc|b\.?com|b\.?e\.?\b|\bbe\b|"
        r"undergraduate|graduat(?:e|ion)",
        value,
    ):
        return 2

    if re.search(
        r"diploma|associate",
        value,
    ):
        return 1

    return 0


def _education_fields(
    text: str,
) -> set[str]:
    value = re.sub(
        r"[^a-z0-9+#]+",
        " ",
        text.casefold(),
    )

    fields: set[str] = set()

    if re.search(
        r"computer science|computer application|"
        r"computer engineering|information technology|"
        r"\bit\b|software|cyber|artificial intelligence|"
        r"machine learning|bca|mca",
        value,
    ):
        fields.add(
            "computing"
        )

    if re.search(
        r"data science|data analytics|analytics|"
        r"statistics|mathematics",
        value,
    ):
        fields.add(
            "data"
        )

    if re.search(
        r"engineering|btech|mtech|\bbe\b|\bme\b",
        value,
    ):
        fields.add(
            "engineering"
        )

    if re.search(
        r"business|management|commerce|finance|"
        r"accounting|economics|bba|mba|bcom|mcom|"
        r"marketing|sales|human resources|\bhr\b",
        value,
    ):
        fields.add(
            "business"
        )

    return fields


def _education_match(
    candidate: list[str],
    requirements: list[str],
    *,
    implied_fields: set[str] | None = None,
) -> float:
    if not requirements:
        return 1.0

    if not candidate:
        return 0.0

    candidate_text = " ".join(candidate)
    candidate_level = _education_level(candidate_text)
    candidate_fields = _education_fields(candidate_text)
    implied_fields = implied_fields or set()

    scores: list[float] = []

    for requirement in requirements:
        required_level = _education_level(requirement)
        required_fields = _education_fields(requirement) or set(implied_fields)

        if required_level == 0 and re.search(
            r"\bgraduate|graduation\b",
            requirement,
            re.I,
        ):
            required_level = 2

        if required_level == 0:
            level_score = 1.0 if candidate_level > 0 else 0.5
        elif candidate_level >= required_level:
            level_score = 1.0
        elif candidate_level > 0:
            level_score = max(0.25, candidate_level / required_level * 0.5)
        else:
            level_score = 0.0

        if not required_fields:
            field_score = 1.0
        elif required_fields & candidate_fields:
            field_score = 1.0
        elif any(
            neighbor in candidate_fields
            for required in required_fields
            for neighbor in _ADJACENT_EDUCATION_FIELDS.get(required, set())
        ):
            field_score = 0.4
        else:
            field_score = 0.0

        if required_fields:
            # JD named a domain. Wrong field must not get 70% just for degree level.
            score = 0.25 * level_score + 0.75 * field_score
            if field_score == 0.0:
                score = min(score, 0.15)
        else:
            score = 0.7 * level_score + 0.3 * field_score

        scores.append(min(1.0, max(0.0, score)))

    return sum(scores) / len(scores)


def _certification_match(
    candidate: list[str],
    requirements: list[str],
) -> float:
    if not requirements:
        return 1.0

    if not candidate:
        return 0.0

    candidate_text = " ".join(
        candidate
    ).casefold()

    matches = 0

    for requirement in requirements:
        words = [
            word
            for word
            in re.findall(
                r"[a-z0-9+#.]{2,}",
                requirement.casefold(),
            )
            if word
            not in {
                "certification",
                "certified",
                "certificate",
                "required",
                "preferred",
            }
        ]

        if (
            words
            and all(
                word in candidate_text
                for word in words[:3]
            )
        ):
            matches += 1

    return (
        matches
        / len(requirements)
    )


_DEGREE_EVIDENCE_RE = re.compile(
    r"\b(?:"
    r"ph\.?d|doctorate|"
    r"master(?:'s)?|bachelor(?:'s)?|"
    r"m\.?tech|b\.?tech|mca|bca|mba|bba|"
    r"m\.?sc|b\.?sc|m\.?com|b\.?com|"
    r"b\.?e\.?|m\.?e\.?|"
    r"diploma|degree"
    r")\b",
    re.I,
)


def _education_evidence_lines(candidate: CandidateProfile) -> list[str]:
    """Prefer parsed education lines; fall back to degree evidence in resume text."""
    lines = [line.strip() for line in candidate.education if str(line).strip()]
    if lines:
        return lines

    text = candidate.source_text or ""
    found: list[str] = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip(" •*-–—")
        if line and _DEGREE_EVIDENCE_RE.search(line):
            found.append(line)
    return dedupe_preserve(found)


def _implied_education_fields(jd: ParsedJD) -> set[str]:
    """Technical JDs imply a computing/engineering degree even if the JD says only 'Bachelor's'."""
    skill_text = " ".join(jd.required_skills.normalized + jd.preferred_skills.normalized)
    title = jd.job_title or ""
    if _TECHNICAL_JD_SKILL_HINT.search(f"{skill_text} {title}"):
        return {"computing", "engineering", "data"}
    return set()


def _education_certification_ratio(
    candidate: CandidateProfile,
    jd: ParsedJD,
) -> float:
    components: list[float] = []
    implied_fields = _implied_education_fields(jd)
    education_lines = _education_evidence_lines(candidate)

    if jd.education_requirements:
        components.append(
            _education_match(
                education_lines,
                jd.education_requirements,
                implied_fields=implied_fields,
            )
        )
    elif implied_fields and education_lines:
        # JD listed technical skills but no education line — still do not
        # treat an unrelated degree as a full education match.
        components.append(
            _education_match(
                education_lines,
                ["Bachelor's degree in Computer Science or related field"],
                implied_fields=implied_fields,
            )
        )

    if jd.certifications:
        components.append(
            _certification_match(
                candidate.certifications,
                jd.certifications,
            )
        )

    if not components:
        # Technical JDs imply an education bar — missing education must not
        # silently score as a perfect match.
        if implied_fields and not education_lines:
            return 0.0
        return 1.0

    return sum(components) / len(components)


def _is_scoreable_keyword(keyword: str) -> bool:
    cleaned = keyword.casefold().strip()
    if len(cleaned) < 3:
        return False
    if cleaned in _GENERIC_TERMS:
        return False
    if re.fullmatch(r"[a-z]+s?", cleaned) and cleaned in {
        "application",
        "applications",
        "model",
        "models",
        "design",
        "engineer",
        "engineering",
        "development",
        "intelligent",
        "system",
        "systems",
        "tool",
        "tools",
    }:
        return False
    return True


def _keyword_ratio(
    candidate: CandidateProfile,
    jd: ParsedJD,
) -> tuple[
    float,
    list[str],
]:
    skill_keys = {
        skill.casefold()
        for skill in normalize_skills(
            list(jd.required_skills.normalized) + list(jd.preferred_skills.normalized)
        )
    }
    jd_keywords = [
        keyword
        for keyword in jd.keywords
        if _is_scoreable_keyword(keyword) and keyword.casefold() not in skill_keys
    ]

    candidate_keywords = {
        keyword.casefold()
        for keyword
        in candidate.keywords
        if _is_scoreable_keyword(keyword)
    }

    candidate_text = (
        candidate
        .source_text
        .casefold()
    )

    matched = []
    for keyword in jd_keywords:
        key = keyword.casefold()
        if key in candidate_keywords or re.search(
            rf"\b{re.escape(key)}\b",
            candidate_text,
        ):
            matched.append(keyword)

    # Prefer domain phrases from the JD (title + responsibilities) over leftover
    # generic single tokens. Skills are excluded so this does not duplicate skill score.
    extra_phrases: list[str] = []
    for phrase in (jd.job_title, *jd.responsibilities, *jd.experience_requirements):
        tokens = [
            token
            for token in re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{3,}", phrase or "")
            if _is_scoreable_keyword(token) and token.casefold() not in skill_keys
        ]
        for index in range(len(tokens) - 1):
            extra_phrases.append(f"{tokens[index]} {tokens[index + 1]}")

    extra_matched = []
    seen_extra = {item.casefold() for item in matched}
    for phrase in extra_phrases:
        key = phrase.casefold()
        if key in seen_extra or key in skill_keys:
            continue
        if re.search(rf"\b{re.escape(key)}\b", candidate_text):
            extra_matched.append(phrase)
            seen_extra.add(key)

    pool = jd_keywords + extra_matched
    if not pool and not jd.keywords:
        return 1.0, []
    if not pool:
        return 0.0, []
    unique_pool = []
    seen_pool: set[str] = set()
    for item in jd_keywords + extra_matched:
        if item.casefold() in seen_pool:
            continue
        seen_pool.add(item.casefold())
        unique_pool.append(item)
    hit = [item for item in unique_pool if item.casefold() in seen_extra or item in matched]
    # Count JD keywords first, then extra phrase hits as a modest boost capped at 1.0.
    if jd_keywords:
        ratio = len(matched) / len(jd_keywords)
        if extra_matched:
            ratio = min(1.0, ratio + 0.15 * min(1.0, len(extra_matched) / 4))
        return round(ratio, 4), matched + extra_matched[:8]
    ratio = min(1.0, len(extra_matched) / max(3, len(unique_pool)))
    return round(ratio, 4), extra_matched[:8]


def _stem_token(
    token: str,
) -> str:
    token = token.casefold().strip(
        "._+#-/ "
    )

    mappings = (
        (
            r"^develop",
            "develop",
        ),
        (
            r"^analyt",
            "analyt",
        ),
        (
            r"^engineer",
            "engineer",
        ),
        (
            r"^automat",
            "automat",
        ),
        (
            r"^program",
            "program",
        ),
        (
            r"^consult",
            "consult",
        ),
        (
            r"^manage",
            "manage",
        ),
        (
            r"^administr",
            "admin",
        ),
        (
            r"^market",
            "market",
        ),
        (
            r"^account",
            "account",
        ),
        (
            r"^finance",
            "finance",
        ),
        (
            r"^report",
            "report",
        ),
        (
            r"^test",
            "test",
        ),
        (
            r"^design",
            "design",
        ),
        (
            r"^sale",
            "sales",
        ),
        (
            r"^customer",
            "customer",
        ),
        (
            r"^process",
            "process",
        ),
    )

    for pattern, replacement in mappings:
        if re.search(
            pattern,
            token,
        ):
            return replacement

    return token


def _meaningful_terms(
    text: str,
) -> set[str]:
    terms: set[str] = set()

    for token in re.findall(
        r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}",
        text,
    ):
        stem = _stem_token(
            token
        )

        if (
            len(stem) >= 3
            and stem not in _GENERIC_TERMS
        ):
            terms.add(
                stem
            )

    return terms


def _entry_skills(
    entry: ExperienceEntry,
) -> set[str]:
    return {
        str(
            match["normalized"]
        )
        for match
        in find_known_skills(
            f"{entry.role}\n{entry.text}"
        )
    }


def _experience_focus(
    jd: ParsedJD,
) -> tuple[
    set[str],
    set[str],
    set[str],
]:
    experience_text = " ".join(
        jd.experience_requirements
    )

    explicit_focus_skills = {
        str(
            match["normalized"]
        )
        for match
        in find_known_skills(
            experience_text
        )
    }

    title_terms = _meaningful_terms(
        jd.job_title
    )

    context_terms = _meaningful_terms(
        " ".join(
            [
                jd.job_title,
                experience_text,
                *jd.responsibilities,
                *jd.keywords,
            ]
        )
    )

    return (
        explicit_focus_skills,
        title_terms,
        context_terms,
    )


def _assess_entry_relevance(
    entry: ExperienceEntry,
    jd: ParsedJD,
) -> tuple[
    bool,
    list[str],
    str,
]:
    entry_text = (
        f"{entry.role}\n"
        f"{entry.company}\n"
        f"{entry.text}"
    )

    entry_terms = _meaningful_terms(
        entry_text
    )

    role_terms = _meaningful_terms(
        entry.role
    )

    entry_skills = _entry_skills(
        entry
    )

    (
        explicit_focus_skills,
        title_terms,
        context_terms,
    ) = _experience_focus(
        jd
    )

    required_skills = set(
        jd.required_skills.normalized
    )

    preferred_skills = set(
        jd.preferred_skills.normalized
    )

    focus_hits = sorted(
        explicit_focus_skills
        & entry_skills
    )

    required_hits = sorted(
        required_skills
        & entry_skills
    )

    preferred_hits = sorted(
        preferred_skills
        & entry_skills
    )

    role_hits = sorted(
        title_terms
        & role_terms
    )

    context_hits = sorted(
        context_terms
        & entry_terms
    )

    evidence = dedupe_preserve(
        focus_hits
        + required_hits
        + preferred_hits
        + role_hits
        + context_hits
    )

    if entry.entry_type in {"internship", "project", "research"} and (
        required_hits or preferred_hits or focus_hits
    ):
        snippet = re.sub(r"\s+", " ", (entry.text or "")).strip()[:180]
        role = entry.role or "Unspecified role"
        company = entry.company or "unspecified organization"
        dates = _date_range(entry) or "dates not stated"
        duration = (
            f"{entry.duration_years:g} years"
            if entry.duration_years
            else "unspecified duration"
        )
        signal_text = ", ".join((required_hits or preferred_hits or focus_hits)[:6])
        snippet_part = f' Evidence: "{snippet}"' if snippet else ""
        return (
            True,
            evidence,
            (
                f"{role} at {company} ({dates}, {duration}) is counted as "
                f"{entry.entry_type} exposure because it demonstrates {signal_text}."
                f"{snippet_part}"
            ),
        )

    # Strict rule:
    # "3-4 years Python development"
    # requires Python evidence inside that specific role.
    if explicit_focus_skills:
        snippet = re.sub(r"\s+", " ", (entry.text or "")).strip()[:180]
        role = entry.role or "Unspecified role"
        company = entry.company or "unspecified organization"
        dates = _date_range(entry) or "dates not stated"
        duration = (
            f"{entry.duration_years:g} years"
            if entry.duration_years
            else "unspecified duration"
        )
        if focus_hits:
            snippet_part = f' Evidence: "{snippet}"' if snippet else ""
            return (
                True,
                evidence,
                (
                    f"{role} at {company} ({dates}, {duration}) qualifies because "
                    f"it demonstrates {', '.join(focus_hits)} named in the JD "
                    f"experience requirement.{snippet_part}"
                ),
            )

        return (
            False,
            evidence,
            (
                f"{role} at {company} ({dates}) is not counted because it does not "
                f"show {', '.join(sorted(explicit_focus_skills))} from the JD "
                f"experience requirement."
            ),
        )

    direct_role_match = bool(
        role_hits
    )

    direct_skill_match = bool(
        required_hits
        or preferred_hits
    )

    strong_skill_match = (
        len(
            required_hits
        ) >= 2
    )

    responsibility_match = (
        len(
            context_hits
        ) >= 2
    )

    relevant = (
        (
            direct_role_match
            and (
                direct_skill_match
                or responsibility_match
            )
        )
        or strong_skill_match
        or (
            direct_skill_match
            and responsibility_match
        )
        or (
            not required_skills
            and direct_role_match
        )
    )

    snippet = re.sub(r"\s+", " ", (entry.text or "")).strip()
    if snippet:
        snippet = snippet[:180]

    role = entry.role or "Unspecified role"
    company = entry.company or "unspecified organization"
    dates = _date_range(entry) or "dates not stated"
    duration = (
        f"{entry.duration_years:g} years"
        if entry.duration_years
        else "unspecified duration"
    )
    signal_text = ", ".join(evidence[:6]) if evidence else ""

    if relevant:
        why = (
            f"demonstrates {signal_text}"
            if signal_text
            else "overlaps the JD role or domain"
        )
        snippet_part = f' Evidence: "{snippet}"' if snippet else ""
        return (
            True,
            evidence,
            (
                f"{role} at {company} ({dates}, {duration}) qualifies because "
                f"the entry {why}.{snippet_part}"
            ),
        )

    if direct_skill_match:
        reason = (
            "A technology is mentioned, but the role/domain "
            "evidence is too weak to count the complete "
            "employment period."
        )
    elif direct_role_match:
        reason = (
            "The title has partial overlap, but the resume "
            "does not show enough JD skill or responsibility "
            "evidence."
        )
    else:
        reason = (
            "The role, technologies, responsibilities, "
            "and domain are not directly relevant to this JD."
        )

    extra = f' Evidence reviewed: "{snippet}"' if snippet else (
        f" Signals reviewed: {signal_text}." if signal_text else ""
    )
    return (
        False,
        evidence,
        f"{role} at {company} ({dates}) is not counted. {reason}{extra}",
    )


def _date_range(
    entry: ExperienceEntry,
) -> str:
    if (
        entry.start_date
        and entry.end_date
    ):
        return (
            f"{entry.start_date} – "
            f"{entry.end_date}"
        )

    if entry.duration_years is not None:
        return (
            f"{entry.duration_years:g} "
            f"years stated"
        )

    return (
        "Dates/duration not stated"
    )


def _entry_assessment(
    entry: ExperienceEntry,
    *,
    matched_signals: list[str],
    reason: str,
) -> ExperienceEntryAssessment:
    return ExperienceEntryAssessment(
        role=(
            entry.role
            or "Unspecified role"
        ),
        company=entry.company,
        entry_type=entry.entry_type,
        date_range=_date_range(
            entry
        ),
        duration_years=entry.duration_years,
        matched_signals=matched_signals,
        reason=reason,
    )


def _merge_intervals(
    intervals: list[
        tuple[int, int]
    ],
) -> int:
    if not intervals:
        return 0

    intervals = sorted(
        intervals
    )

    total = 0

    (
        current_start,
        current_end,
    ) = intervals[0]

    for start, end in intervals[1:]:
        if start <= current_end:
            current_end = max(
                current_end,
                end,
            )

        else:
            total += (
                current_end
                - current_start
            )

            current_start = start
            current_end = end

    return (
        total
        + current_end
        - current_start
    )


def _format_requirement(
    jd: ParsedJD,
) -> str:
    if jd.experience_requirements:
        return " | ".join(
            jd.experience_requirements
        )

    minimum = (
        jd.minimum_experience_years
    )

    maximum = (
        jd.maximum_experience_years
    )

    if (
        minimum is not None
        and maximum is not None
    ):
        return (
            f"{minimum:g}–{maximum:g} "
            f"years relevant experience"
        )

    if minimum is not None:
        return (
            f"At least {minimum:g} "
            f"years relevant experience"
        )

    return (
        "No explicit experience duration stated"
    )


def _requirement_kind(jd: ParsedJD) -> str:
    kind = getattr(jd, "experience_requirement_kind", None) or "professional"
    return str(kind).casefold()


def _allows_internship(jd: ParsedJD) -> bool:
    if getattr(jd, "allows_internship_for_requirement", False):
        return True
    return _requirement_kind(jd) == "internship_included"


def _years_from_months(months: int) -> float:
    return round(months / 12, 2)


def _collect_type_months(
    entries_with_meta: list[
        tuple[ExperienceEntry, list[str], str]
    ],
) -> dict[str, int]:
    """Overlap-merge dated months per entry_type; undated only if no dated for that type."""
    by_type_dated: dict[str, list[tuple[int, int]]] = {}
    by_type_undated: dict[str, list[ExperienceEntry]] = {}

    for entry, _signals, _reason in entries_with_meta:
        entry_type = entry.entry_type or "other"
        has_dated = (
            entry.start_month_index is not None
            and entry.end_month_index is not None
            and entry.end_month_index >= entry.start_month_index
        )
        if has_dated:
            by_type_dated.setdefault(entry_type, []).append(
                (entry.start_month_index, entry.end_month_index + 1)
            )
        elif entry.duration_months and entry.duration_months > 0:
            by_type_undated.setdefault(entry_type, []).append(entry)

    months_by_type: dict[str, int] = {}
    for entry_type, intervals in by_type_dated.items():
        months_by_type[entry_type] = _merge_intervals(intervals)

    for entry_type, undated_entries in by_type_undated.items():
        if entry_type in months_by_type and months_by_type[entry_type] > 0:
            continue
        # Conservative: take the single longest undated duration for the type.
        best = max(
            (entry.duration_months or 0 for entry in undated_entries),
            default=0,
        )
        if best:
            months_by_type[entry_type] = best

    return months_by_type


def _years_toward_jd_requirement(
    *,
    kind: str,
    professional_years: float,
    internship_years: float,
    research_years: float,
    project_years: float,
    hands_on_years: float,
    allows_internship: bool,
) -> float:
    """
    Select which category years satisfy the JD minimum.

    HARD RULE: internships never count as professional unless the JD
    explicitly includes internships.
    """
    if kind in {"professional", "industry"}:
        return professional_years
    if kind == "internship_included" or allows_internship:
        return round(professional_years + internship_years, 2)
    if kind in {"relevant", "hands_on", "any"}:
        return hands_on_years
    # Unknown → conservative professional-only.
    return professional_years


def parse_skill_experience_requirements(
    lines: list[str],
    *,
    existing: list[SkillExperienceRequirement] | None = None,
) -> list[SkillExperienceRequirement]:
    """Parse per-skill/domain year requirements from JD experience lines."""
    if existing:
        return list(existing)

    range_re = re.compile(
        r"(?P<minimum>\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(?P<maximum>\d+(?:\.\d+)?)\s*\+?\s*years?",
        re.I,
    )
    single_re = re.compile(
        r"(?:minimum|at\s+least|min(?:imum)?\s+of)?\s*(?P<years>\d+(?:\.\d+)?)\s*\+?\s*years?",
        re.I,
    )
    preferred_re = re.compile(r"\b(preferred|nice to have|bonus|good to have)\b", re.I)
    experience_in_re = re.compile(
        r"\bexperience\s+(?:in|with|using|of)\b",
        re.I,
    )

    results: list[SkillExperienceRequirement] = []
    seen: set[str] = set()
    for line in lines:
        cleaned = re.sub(r"\s+", " ", line).strip()
        if not cleaned:
            continue
        range_match = range_re.search(cleaned)
        minimum: float | None = None
        maximum: float | None = None
        has_years = False
        if range_match:
            minimum = float(range_match.group("minimum"))
            maximum = float(range_match.group("maximum"))
            has_years = True
        else:
            single_match = single_re.search(cleaned)
            if single_match:
                minimum = float(single_match.group("years"))
                has_years = True
            elif not experience_in_re.search(cleaned):
                continue

        skills = [str(match["normalized"]) for match in find_known_skills(cleaned)]
        domain = ""
        domain_match = re.search(
            r"(?:in|with|using|of)\s+([A-Za-z0-9+#./& -]{2,80})$",
            cleaned,
            re.I,
        )
        if not skills and domain_match:
            domain = domain_match.group(1).strip(" .")
        labels = skills or ([normalize_skill(domain)] if domain else [])
        if not labels:
            continue
        for label in labels:
            key = f"{label.casefold()}|{minimum}|{maximum}|{bool(preferred_re.search(cleaned))}"
            if key in seen:
                continue
            seen.add(key)
            results.append(
                SkillExperienceRequirement(
                    skill_or_domain=label,
                    minimum_years=minimum,
                    maximum_years=maximum,
                    is_preferred=bool(preferred_re.search(cleaned)),
                    source_text=cleaned,
                )
            )
    return results


def _text_has_skill_term(blob: str, term: str) -> bool:
    cleaned = (term or "").strip().casefold()
    if len(cleaned) < 2:
        return False
    return bool(
        re.search(
            rf"(?<![a-z0-9+#]){re.escape(cleaned)}(?![a-z0-9+#])",
            blob.casefold(),
        )
    )


def _evaluate_skill_experience(
    candidate: CandidateProfile,
    jd: ParsedJD,
    allows_internship: bool,
) -> list[SkillExperienceAssessment]:
    requirements = parse_skill_experience_requirements(
        jd.experience_requirements,
        existing=getattr(jd, "skill_experience_requirements", None) or None,
    )
    global_skills = {
        skill.casefold()
        for skill in normalize_skills(candidate.skills.normalized_skills)
    }
    assessments: list[SkillExperienceAssessment] = []
    for requirement in requirements:
        skill_key = normalize_skill(requirement.skill_or_domain)
        terms = {term.casefold() for term in skill_search_terms(skill_key)}
        implying = {item.casefold() for item in skills_implying(skill_key)}
        explicit_intervals: list[tuple[int, int]] = []
        strong_intervals: list[tuple[int, int]] = []
        evidence: list[ExperienceEntryAssessment] = []
        undated = False

        for entry in candidate.experience_entries:
            if entry.entry_type == "internship" and not allows_internship:
                continue
            if entry.entry_type in {"project", "research", "other"}:
                continue
            blob = f"{entry.role}\n{entry.company}\n{entry.text}"
            entry_skills = {
                str(match["normalized"]).casefold()
                for match in find_known_skills(blob)
            }
            explicit = skill_key.casefold() in entry_skills or any(
                _text_has_skill_term(blob, term)
                for term in terms
            )
            strong = bool(entry_skills & implying) and not explicit
            if not explicit and not strong:
                continue
            kind = "EXPLICIT_DATED_EVIDENCE" if explicit else "STRONG_DATED_EVIDENCE"
            snippet = re.sub(r"\s+", " ", entry.text or "").strip()[:180]
            signals = [skill_key]
            if strong:
                signals.extend(
                    skill for skill in entry_skills if skill in implying
                )
            reason = (
                f"{entry.role or 'Unspecified role'} at "
                f"{entry.company or 'unspecified organization'} "
                f"({_date_range(entry) or 'dates not stated'}) "
                f"is {kind.replace('_', ' ').lower()}"
                + (
                    f' because the entry demonstrates {", ".join(signals[:4])}'
                )
                + (f': "{snippet}"' if snippet else ".")
            )
            evidence.append(
                _entry_assessment(
                    entry,
                    matched_signals=signals,
                    reason=reason,
                )
            )
            dated = (
                entry.start_month_index is not None
                and entry.end_month_index is not None
                and entry.end_month_index >= entry.start_month_index
            )
            if dated:
                interval = (entry.start_month_index, entry.end_month_index + 1)
                if explicit:
                    explicit_intervals.append(interval)
                else:
                    strong_intervals.append(interval)
            else:
                undated = True

        if (
            not evidence
            and skill_key.casefold() in global_skills
        ):
            undated = True

        explicit_years = _years_from_months(_merge_intervals(explicit_intervals))
        # Strong intervals that overlap explicit dates are not double-counted.
        strong_only = _merge_intervals(strong_intervals + explicit_intervals) - _merge_intervals(
            explicit_intervals
        )
        strong_years = _years_from_months(strong_only)
        supported_months = _merge_intervals(explicit_intervals + strong_intervals)
        supported_years = _years_from_months(supported_months)

        if explicit_years > 0 and strong_years > 0:
            evidence_kind = "MIXED_DATED_EVIDENCE"
        elif explicit_years > 0:
            evidence_kind = "EXPLICIT_DATED_EVIDENCE"
        elif strong_years > 0:
            evidence_kind = "STRONG_DATED_EVIDENCE"
        elif undated:
            evidence_kind = "UNDATED_EVIDENCE"
        else:
            evidence_kind = "NO_EVIDENCE"

        meets = None
        if requirement.minimum_years is not None:
            meets = supported_years >= requirement.minimum_years

        if evidence_kind == "NO_EVIDENCE":
            reason = (
                f"{skill_key}: no dated professional evidence found"
                + (
                    f"; requirement is {requirement.minimum_years:g}+ years"
                    if requirement.minimum_years is not None
                    else ""
                )
                + "."
            )
        elif evidence_kind == "UNDATED_EVIDENCE":
            reason = (
                f"{skill_key}: listed in the resume but not attributed to a dated "
                f"employment period (not counted toward years)."
            )
        else:
            parts = [f"{explicit_years:g} explicit dated"]
            if strong_years > 0:
                parts.append(f"{strong_years:g} strong dated")
            status = "PASS" if meets else ("FAIL" if meets is False else "n/a")
            reason = (
                f"{skill_key}: {supported_years:g} years supported "
                f"({'; '.join(parts)}). Requirement "
                f"{requirement.minimum_years:g}+ years → {status}."
                if requirement.minimum_years is not None
                else (
                    f"{skill_key}: {supported_years:g} years supported "
                    f"({'; '.join(parts)})."
                )
            )

        assessments.append(
            SkillExperienceAssessment(
                skill_or_domain=skill_key,
                source_text=requirement.source_text,
                minimum_years=requirement.minimum_years,
                maximum_years=requirement.maximum_years,
                is_preferred=requirement.is_preferred,
                candidate_years=supported_years,
                explicit_dated_years=explicit_years,
                strong_dated_years=strong_years,
                undated_years=0.0,
                supported_years=supported_years,
                evidence_kind=evidence_kind,
                meets_minimum=meets,
                evidence=evidence,
                reason=reason,
            )
        )
    return assessments


def _content_skill_terms(skill: str) -> list[str]:
    canonical = normalize_skill(skill) or skill
    return [canonical.casefold(), skill.casefold()]


def _responsibility_ratio(
    candidate: CandidateProfile,
    jd: ParsedJD,
) -> tuple[float, list[str], list[str], list]:
    """Evidence-based JD responsibility match using action + object + domain."""
    ratio, matches = match_responsibilities(candidate, jd)
    matched = [
        item.jd_responsibility
        for item in matches
        if item.match_status in {"STRONG_MATCH", "PARTIAL_MATCH"}
    ]
    missing = [
        item.jd_responsibility
        for item in matches
        if item.match_status == "UNSUPPORTED"
    ]
    return ratio, matched, missing, matches


def evaluate_relevant_experience(
    candidate: CandidateProfile,
    jd: ParsedJD,
) -> ExperienceAssessment:
    counted: list[ExperienceEntryAssessment] = []
    excluded: list[ExperienceEntryAssessment] = []
    relevant_meta: list[tuple[ExperienceEntry, list[str], str]] = []

    for entry in candidate.experience_entries:
        relevant, signals, reason = _assess_entry_relevance(entry, jd)

        has_dated_duration = (
            entry.start_month_index is not None
            and entry.end_month_index is not None
            and entry.end_month_index >= entry.start_month_index
        )
        has_explicit_duration = (
            entry.duration_months is not None and entry.duration_months > 0
        )

        if not relevant:
            excluded.append(
                _entry_assessment(
                    entry,
                    matched_signals=signals,
                    reason=reason,
                )
            )
            continue

        entry_type = entry.entry_type or "other"
        type_label = {
            "employment": "professional employment",
            "internship": "internship (not professional employment)",
            "project": "project (not professional employment)",
            "research": "research (not professional employment by default)",
            "other": "non-employment entry",
        }.get(entry_type, entry_type)

        if has_dated_duration or has_explicit_duration:
            relevant_meta.append((entry, signals, reason))
            counted.append(
                _entry_assessment(
                    entry,
                    matched_signals=signals,
                    reason=f"Counted as JD-relevant {type_label}. {reason}",
                )
            )
        else:
            excluded.append(
                _entry_assessment(
                    entry,
                    matched_signals=signals,
                    reason=(
                        "The entry is relevant, but no verifiable dates "
                        "or duration are present, so it is not added to "
                        "experience years."
                    ),
                )
            )

    # Prefer dated intervals; undated durations only contribute when no dated
    # periods exist for that entry type (handled inside _collect_type_months).
    dated_any = any(
        entry.start_month_index is not None and entry.end_month_index is not None
        for entry, _s, _r in relevant_meta
    )
    numeric_meta: list[tuple[ExperienceEntry, list[str], str]] = []
    for entry, signals, reason in relevant_meta:
        has_dated = (
            entry.start_month_index is not None
            and entry.end_month_index is not None
        )
        if has_dated or not dated_any:
            numeric_meta.append((entry, signals, reason))

    months_by_type = _collect_type_months(numeric_meta)

    professional_months = months_by_type.get("employment", 0)
    internship_months = months_by_type.get("internship", 0)
    research_months = months_by_type.get("research", 0)
    project_months = months_by_type.get("project", 0)
    other_months = months_by_type.get("other", 0)

    professional_years = _years_from_months(professional_months)
    internship_years = _years_from_months(internship_months)
    research_years = _years_from_months(research_months)
    project_years = _years_from_months(project_months)

    hands_on_months = (
        professional_months
        + internship_months
        + research_months
        + project_months
        + other_months
    )
    hands_on_years = _years_from_months(hands_on_months)
    # "Relevant experience" for display/totals = professional employment only.
    # Internships and academic projects stay in their own fields and may still
    # contribute to years_toward_requirement when the JD kind is hands_on /
    # relevant / internship_included.
    relevant_years = professional_years

    kind = _requirement_kind(jd)
    allows_internship = _allows_internship(jd)
    years_toward = _years_toward_jd_requirement(
        kind=kind,
        professional_years=professional_years,
        internship_years=internship_years,
        research_years=research_years,
        project_years=project_years,
        hands_on_years=hands_on_years,
        allows_internship=allows_internship,
    )

    total_years = candidate.total_experience_years
    unrelated_years = (
        round(max(total_years - professional_years, 0.0), 2)
        if total_years is not None
        else 0.0
    )

    minimum = jd.minimum_experience_years
    maximum = jd.maximum_experience_years
    meets_minimum = None if minimum is None else years_toward >= minimum

    kind_label = {
        "professional": "professional employment",
        "industry": "industry/professional employment",
        "relevant": "relevant hands-on exposure",
        "hands_on": "hands-on exposure",
        "internship_included": "professional + internship (JD allows internships)",
        "any": "any relevant exposure",
    }.get(kind, "professional employment")

    breakdown = (
        f"Professional (total relevant): {professional_years:g} yrs; "
        f"Internship (excluded from total relevant): {internship_years:g} yrs; "
        f"Projects (excluded from total relevant): {project_years:g} yrs; "
        f"Research: {research_years:g} yrs; "
        f"Supporting exposure (intern/projects/research only): "
        f"{round(internship_years + project_years + research_years, 2):g} yrs. "
        f"JD allows internship toward requirement: "
        f"{'YES' if allows_internship else 'NO'}."
    )

    if minimum is None:
        result = (
            "The JD does not state a minimum duration. "
            f"Verified JD-relevant exposure — {breakdown}"
        )
    elif not meets_minimum:
        range_text = (
            f"{minimum:g}–{maximum:g}"
            if maximum is not None
            else f"at least {minimum:g}"
        )
        result = (
            f"Does not meet the required {range_text} years of "
            f"{kind_label}. Years counted toward this requirement: "
            f"{years_toward:g}. {breakdown}"
        )
    elif maximum is not None and years_toward > maximum:
        result = (
            f"Meets the minimum {minimum:g} years of {kind_label} "
            f"and exceeds the stated upper range of {maximum:g} years "
            f"({years_toward:g} toward requirement). {breakdown}"
        )
    else:
        range_text = (
            f"{minimum:g}–{maximum:g}"
            if maximum is not None
            else f"at least {minimum:g}"
        )
        result = (
            f"Meets the required {range_text} years of {kind_label} "
            f"with {years_toward:g} years toward the requirement. {breakdown}"
        )

    supporting_years = round(
        internship_years + project_years + research_years,
        2,
    )
    skill_experience = _evaluate_skill_experience(candidate, jd, allows_internship)

    return ExperienceAssessment(
        jd_requirement=_format_requirement(jd),
        minimum_required_years=minimum,
        maximum_required_years=maximum,
        candidate_total_experience_years=total_years,
        candidate_relevant_experience_years=relevant_years,
        unrelated_experience_years=unrelated_years,
        professional_experience_years=professional_years,
        internship_experience_years=internship_years,
        research_experience_years=research_years,
        academic_project_years=project_years,
        relevant_hands_on_experience_years=hands_on_years,
        supporting_exposure_years=supporting_years,
        skill_experience_assessments=skill_experience,
        years_toward_requirement=years_toward,
        experience_requirement_kind=kind,  # type: ignore[arg-type]
        allows_internship_for_requirement=allows_internship,
        meets_minimum=meets_minimum,
        result=result,
        counted_experience=counted,
        excluded_experience=excluded,
    )


def _transferable_strengths(
    excluded: list[
        ExperienceEntryAssessment
    ],
) -> list[str]:
    role_text = " ".join(
        entry.role
        for entry in excluded
    ).casefold()

    strengths: list[str] = []

    if re.search(
        r"sales|account|business development|"
        r"customer|support|client",
        role_text,
    ):
        strengths.extend(
            [
                "communication",
                "client handling",
                "stakeholder interaction",
            ]
        )

    if re.search(
        r"manager|lead|supervisor|coordinator",
        role_text,
    ):
        strengths.extend(
            [
                "team coordination",
                "leadership",
            ]
        )

    if re.search(
        r"operations|administration|process",
        role_text,
    ):
        strengths.extend(
            [
                "operational discipline",
                "process awareness",
            ]
        )

    return dedupe_preserve(
        strengths
    )


def _experience_full_credit_years(jd: ParsedJD) -> float | None:
    """
    Years needed for a full experience component score.

    For a stated range such as "4-6 years", meeting the floor (4) is full
    credit. The upper bound is a typical hiring band, not a requirement to
    reach 6 years. Hard-requirement pass/fail still uses the same floor.
    Below the floor, the score scales linearly toward that minimum.
    """
    minimum = jd.minimum_experience_years
    if minimum is not None and minimum > 0:
        return float(minimum)
    maximum = jd.maximum_experience_years
    if maximum is not None and maximum > 0:
        return float(maximum)
    return None


def jd_is_scoreable(jd: ParsedJD) -> bool:
    """False when the JD has nothing to score against (empty/fake text like 'hi')."""
    if jd.required_skills.normalized:
        return True
    if jd.preferred_skills.normalized:
        return True
    if (jd.minimum_experience_years or 0) > 0:
        return True
    if (jd.maximum_experience_years or 0) > 0:
        return True
    if jd.education_requirements or jd.certifications:
        return True
    if jd.responsibilities:
        return True
    if any(_is_scoreable_keyword(keyword) for keyword in jd.keywords):
        return True
    return False


def score_candidate(
    candidate: CandidateProfile,
    jd: ParsedJD,
    match: MatchAnalysis,
) -> ScoreBreakdown:
    unique_required = normalize_skills(jd.required_skills.normalized)
    unique_preferred = [
        skill
        for skill in normalize_skills(jd.preferred_skills.normalized)
        if skill.casefold() not in {item.casefold() for item in unique_required}
    ]

    if not jd_is_scoreable(jd):
        experience = evaluate_relevant_experience(candidate, jd)
        unscoreable = (
            "The job description is too thin or empty to evaluate a candidate. "
            "It has no required skills, experience, education, or responsibilities. "
            "Upload a complete JD and re-screen."
        )
        return ScoreBreakdown(
            overall_score=0.0,
            skill_match_score=0.0,
            required_skill_score=0.0,
            preferred_skill_score=0.0,
            experience_score=0.0,
            education_score=0.0,
            keyword_score=0.0,
            responsibility_score=0.0,
            experience_assessment=experience,
            strengths=[],
            concerns=[unscoreable],
            recommendation=(
                "Do not shortlist from this score. Provide a real job description "
                "with skills and experience, then screen again."
            ),
            decision="Needs Review",
            hard_requirement_status="FAIL",
            hard_requirement_reasons=["UNSCOREABLE_JD: job description has no evaluable requirements."],
            score_weights={
                "required_skills": settings.ATS_REQUIRED_SKILLS_WEIGHT,
                "preferred_skills": settings.ATS_PREFERRED_SKILLS_WEIGHT,
                "experience": settings.ATS_EXPERIENCE_WEIGHT,
                "education_certification": settings.ATS_EDUCATION_CERTIFICATION_WEIGHT,
                "keywords": settings.ATS_KEYWORD_WEIGHT,
                "responsibilities": 0.0,
            },
        )

    required_score = (
        settings.ATS_REQUIRED_SKILLS_WEIGHT
        * match.required_match_ratio
    )

    preferred_ratio = match.preferred_match_ratio
    # Preferred skills must not compensate for missing mandatory requirements.
    if unique_required and match.required_match_ratio < 0.6:
        preferred_ratio *= match.required_match_ratio
    preferred_score = (
        settings.ATS_PREFERRED_SKILLS_WEIGHT
        * preferred_ratio
    )

    experience = (
        evaluate_relevant_experience(
            candidate,
            jd,
        )
    )

    full_credit_years = _experience_full_credit_years(jd)
    if full_credit_years is None:
        experience_ratio = 1.0
    else:
        # Score against the JD-appropriate category years only
        # (professional vs hands-on vs internship-included).
        # Range upper bound → full credit; below that → proportional.
        experience_ratio = min(
            experience.years_toward_requirement
            / full_credit_years,
            1.0,
        )

    experience_score = (
        settings.ATS_EXPERIENCE_WEIGHT
        * experience_ratio
    )

    education_ratio = (
        _education_certification_ratio(
            candidate,
            jd,
        )
    )

    education_score = (
        settings
        .ATS_EDUCATION_CERTIFICATION_WEIGHT
        * education_ratio
    )

    (
        keyword_ratio,
        matched_keywords,
    ) = _keyword_ratio(
        candidate,
        jd,
    )
    (
        responsibility_ratio,
        matched_responsibilities,
        missing_responsibilities,
        responsibility_matches,
    ) = _responsibility_ratio(candidate, jd)

    if jd.responsibilities:
        keyword_score = settings.ATS_KEYWORD_WEIGHT * 0.5 * keyword_ratio
        responsibility_score = round(
            settings.ATS_KEYWORD_WEIGHT * 0.5 * responsibility_ratio,
            2,
        )
    else:
        keyword_score = settings.ATS_KEYWORD_WEIGHT * keyword_ratio
        responsibility_score = 0.0
        responsibility_ratio = 1.0

    overall = round(
        required_score
        + preferred_score
        + experience_score
        + education_score
        + keyword_score
        + responsibility_score,
        2,
    )

    strengths: list[str] = []
    concerns: list[str] = []

    if match.matched_required_skills:
        strengths.append(
            f"Matches "
            f"{len(match.matched_required_skills)} "
            f"of "
            f"{len(unique_required) or len(jd.required_skills.normalized)} "
            f"unique required skills."
        )
        for item in match.semantic_required_matches[:8]:
            if item.match_level in {"EXACT_MATCH", "STRONG_SEMANTIC_MATCH"}:
                evidence = item.evidence or item.matched_resume_skill or ""
                strengths.append(
                    f"{item.jd_skill}: {item.match_level}"
                    + (f'. Evidence: "{evidence}"' if evidence else ".")
                )

    elif not unique_required:
        strengths.append(
            "The JD does not specify "
            "explicit required skills."
        )

    if match.partial_required_skills:
        concerns.append(
            "Partial required-skill matches (related evidence, not full demonstration): "
            + ", ".join(match.partial_required_skills)
            + "."
        )

    if match.matched_preferred_skills:
        strengths.append(
            f"Matches "
            f"{len(match.matched_preferred_skills)} "
            f"of "
            f"{len(unique_preferred)} "
            f"preferred skills."
        )

    if experience.counted_experience:
        strengths.append(
            f"Verified exposure — professional (total relevant) "
            f"{experience.professional_experience_years:g} yrs; "
            f"internship {experience.internship_experience_years:g} yrs; "
            f"projects {experience.academic_project_years:g} yrs "
            f"(supporting exposure "
            f"{experience.supporting_exposure_years:g} yrs, "
            f"not added to total relevant) "
            f"from {len(experience.counted_experience)} counted entries."
        )

    if experience.unrelated_experience_years > 0:
        transferable = (
            _transferable_strengths(
                experience.excluded_experience
            )
        )

        suffix = (
            f" It may demonstrate "
            f"{', '.join(transferable)}."
            if transferable
            else (
                " It may provide transferable "
                "professional skills."
            )
        )

        strengths.append(
            f"The candidate has approximately "
            f"{experience.unrelated_experience_years:g} "
            f"additional years outside direct JD relevance; "
            f"these years do not increase the experience "
            f"score.{suffix}"
        )

    if (
        education_ratio >= 0.99
        and (
            jd.education_requirements
            or jd.certifications
            or _implied_education_fields(jd)
        )
    ):
        strengths.append(
            "Education and certification evidence "
            "meets the stated requirements."
        )

    elif (
        education_ratio >= 0.5
        and (
            jd.education_requirements
            or jd.certifications
            or _implied_education_fields(jd)
        )
    ):
        strengths.append(
            "Candidate education is present and "
            "partially aligns with the stated requirement."
        )

    if matched_keywords:
        strengths.append(
            "Relevant domain keywords include: "
            + ", ".join(
                matched_keywords[:5]
            )
            + "."
        )

    if matched_responsibilities:
        strong_resp = [
            item
            for item in responsibility_matches
            if item.match_status == "STRONG_MATCH"
        ]
        strengths.append(
            "JD responsibilities with resume evidence: "
            + "; ".join(
                (
                    f"{item.jd_responsibility[:80]} [{item.match_status}]"
                    for item in (strong_resp or responsibility_matches)[:3]
                )
            )
            + "."
        )
        for item in strong_resp[:3]:
            if item.evidence:
                strengths.append(
                    f"{item.match_status}: {item.jd_responsibility[:90]}. "
                    f'Evidence: "{item.evidence[0][:160]}". {item.reason}'
                )

    for item in experience.skill_experience_assessments:
        if item.meets_minimum:
            strengths.append(item.reason)
        elif item.minimum_years is not None and not item.is_preferred:
            concerns.append(item.reason)

    if match.missing_required_skills:
        missing_bits: list[str] = []
        detail_map = {
            item.jd_skill.casefold(): item
            for item in match.semantic_required_matches
        }
        for skill in match.missing_required_skills:
            detail = detail_map.get(skill.casefold())
            if detail and detail.evidence:
                missing_bits.append(
                    f"{skill} (no explicit evidence; closest: {detail.evidence})"
                )
            else:
                missing_bits.append(f"{skill} (no explicit evidence found)")
        concerns.append(
            "Missing required skills: "
            + "; ".join(missing_bits)
            + "."
        )

    if missing_responsibilities:
        concerns.append(
            "Unsupported JD responsibilities: "
            + "; ".join(missing_responsibilities[:4])
            + "."
        )

    if match.missing_preferred_skills:
        concerns.append(
            "Missing preferred skills: "
            + ", ".join(
                match.missing_preferred_skills
            )
            + "."
        )

    if (
        jd.minimum_experience_years is not None
        and not experience.meets_minimum
    ):
        concerns.append(
            experience.result
        )

    if (
        not experience.counted_experience
        and jd.minimum_experience_years is not None
    ):
        concerns.append(
            "No resume entry had both direct JD relevance "
            "and a verifiable duration, so total work "
            "experience was not substituted for relevant "
            "experience."
        )

    if (
        education_ratio < 0.3
        and (
            jd.education_requirements
            or jd.certifications
            or _implied_education_fields(jd)
        )
    ):
        concerns.append(
            "Education does not match the required field "
            "or certification listed in the JD."
        )
    elif (
        education_ratio < 1.0
        and (
            jd.education_requirements
            or jd.certifications
            or _implied_education_fields(jd)
        )
    ):
        concerns.append(
            "Education or certification requirements "
            "are only partially matched or unverified."
        )

    if overall >= settings.ATS_SHORTLIST_THRESHOLD:
        decision = "Shortlisted"

    elif overall >= settings.ATS_REVIEW_THRESHOLD:
        decision = "Needs Review"

    else:
        decision = "Rejected"

    if (
        jd.required_skills.normalized
        and not match.matched_required_skills
    ):
        decision = "Rejected"
        concerns.append(
            "No required JD skills were matched, so this candidate "
            "cannot be shortlisted or held for review on skill score."
        )

    blockers: list[str] = []

    if (
        decision == "Shortlisted"
        and match.required_match_ratio
        < settings
        .ATS_MIN_REQUIRED_RATIO_FOR_SHORTLIST
    ):
        blockers.append(
            "required-skill coverage is below "
            "the shortlist gate"
        )

    if (
        decision == "Shortlisted"
        and jd.minimum_experience_years
        is not None
        and not experience.meets_minimum
    ):
        blockers.append(
            "verified JD-relevant experience "
            "is below the minimum requirement"
        )

    if blockers:
        decision = "Needs Review"

        concerns.append(
            "Automatic shortlist blocked because "
            + " and ".join(
                blockers
            )
            + "."
        )

    if decision == "Shortlisted":
        recommendation = (
            "Proceed to recruiter or technical interview, "
            "while validating the listed evidence."
        )

    elif decision == "Needs Review":
        recommendation = (
            "Review the missing or unverified requirements "
            "before making a shortlist decision."
        )

    else:
        recommendation = (
            "Do not shortlist for this JD unless "
            "requirements or candidate evidence are updated."
        )

    hard_status: str = "N/A"
    hard_reasons: list[str] = []

    if (
        jd.minimum_experience_years is not None
        and jd.minimum_experience_years > 0
        and not experience.meets_minimum
    ):
        hard_status = "FAIL"
        hard_reasons.append(
            "MANDATORY EXPERIENCE GAP: "
            f"required {jd.minimum_experience_years:g} years of "
            f"{experience.experience_requirement_kind.replace('_', ' ')} "
            f"experience; candidate has "
            f"{experience.years_toward_requirement:g} years toward that "
            f"requirement "
            f"(professional={experience.professional_experience_years:g}, "
            f"internship={experience.internship_experience_years:g}, "
            f"projects={experience.academic_project_years:g})."
        )
        if decision == "Shortlisted":
            decision = "Needs Review"
            concerns.append(
                "Automatic shortlist blocked because mandatory "
                "experience requirement is not met."
            )
            recommendation = (
                "Review the missing or unverified requirements "
                "before making a shortlist decision."
            )

    if (
        jd.required_skills.normalized
        and match.required_match_ratio < 0.25
        and match.matched_required_skills
    ):
        # Soft skill coverage gap — does not override experience hard fail.
        hard_reasons.append(
            "CRITICAL SKILL COVERAGE GAP: required-skill match ratio "
            f"is {match.required_match_ratio:.0%}."
        )
        if hard_status == "N/A":
            hard_status = "FAIL"

    if hard_status == "N/A" and (
        (
            jd.minimum_experience_years is None
            or experience.meets_minimum
        )
        and (
            not jd.required_skills.normalized
            or match.matched_required_skills
        )
    ):
        hard_status = "PASS"

    return ScoreBreakdown(
        overall_score=overall,
        skill_match_score=round(
            required_score
            + preferred_score,
            2,
        ),
        required_skill_score=round(
            required_score,
            2,
        ),
        preferred_skill_score=round(
            preferred_score,
            2,
        ),
        experience_score=round(
            experience_score,
            2,
        ),
        education_score=round(
            education_score,
            2,
        ),
        keyword_score=round(
            keyword_score,
            2,
        ),
        responsibility_score=responsibility_score,
        responsibility_matches=responsibility_matches,
        experience_assessment=experience,
        matched_skills=normalize_skills(
            match.matched_required_skills
            + match.matched_preferred_skills
        ),
        missing_skills=normalize_skills(
            match.missing_required_skills
            + match.missing_preferred_skills
        ),
        partial_skills=normalize_skills(
            list(match.partial_required_skills)
            + list(match.partial_preferred_skills)
        ),
        strengths=dedupe_preserve(
            strengths
        ),
        concerns=dedupe_preserve(
            concerns
        ),
        recommendation=recommendation,
        decision=decision,
        hard_requirement_status=hard_status,  # type: ignore[arg-type]
        hard_requirement_reasons=hard_reasons,
        score_weights={
            "required_skills": (
                settings
                .ATS_REQUIRED_SKILLS_WEIGHT
            ),
            "preferred_skills": (
                settings
                .ATS_PREFERRED_SKILLS_WEIGHT
            ),
            "experience": (
                settings
                .ATS_EXPERIENCE_WEIGHT
            ),
            "education_certification": (
                settings
                .ATS_EDUCATION_CERTIFICATION_WEIGHT
            ),
            "keywords": (
                settings.ATS_KEYWORD_WEIGHT * (0.5 if jd.responsibilities else 1.0)
            ),
            "responsibilities": (
                settings.ATS_KEYWORD_WEIGHT * 0.5 if jd.responsibilities else 0.0
            ),
        },
    )