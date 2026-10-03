from __future__ import annotations

import html
import json
import logging
import re
from functools import lru_cache
from typing import Any

from agents.screening_agent.config import settings
from agents.screening_agent.services.prompt_style import prompt_style_instruction
from agents.screening_agent.schemas.ats import ParsedJD, SkillList
from agents.screening_agent.utils.skill_normalizer import (
    find_known_skills,
    normalize_skills,
)
from agents.screening_agent.utils.text_utils import (
    clean_lines,
    dedupe_preserve,
    extract_keywords,
    text_contains_phrase,
)


logger = logging.getLogger(__name__)


_PREFERRED_SIGNALS = re.compile(
    r"preferred|nice to have|good to have|"
    r"bonus|plus|advantage|desirable",
    re.I,
)

_REQUIRED_SIGNALS = re.compile(
    r"required|must have|mandatory|essential|"
    r"minimum|proficien|strong knowledge|hands-on",
    re.I,
)

_RESP_HEADING = re.compile(
    r"responsibilit|duties|"
    r"what you(?:'|’)ll do|"
    r"role overview|day.to.day",
    re.I,
)

_PREF_HEADING = re.compile(
    r"preferred|nice to have|good to have|"
    r"bonus|desirable",
    re.I,
)

_REQ_HEADING = re.compile(
    r"requirement|qualification|must have|"
    r"required skill|technical skill",
    re.I,
)

_EXPLICIT_SKILL_HEADING = re.compile(
    r"(?:required|preferred|key|core|must[- ]have|technical|essential)\s+skills?\b"
    r"|skills?\s+(?:required|preferred|needed)\b"
    r"|core\s+competenc(?:y|ies)\b"
    r"|areas?\s+of\s+expertise\b"
    r"|professional\s+skills?\b",
    re.I,
)

_BULLET_PREFIX_RE = re.compile(
    r"^[\s•*●○■□▪▫·\-–—\uf0b7\uf0a7\u2022\u25cf\u25e6\u00b7]+"
)

_SKIP_TITLE_RE = re.compile(
    r"^(?:role purpose|job summary|about the role|"
    r"about the company|company overview|overview)$",
    re.I,
)

_SKILL_CATEGORY_HEADING_RE = re.compile(
    r"^(?:"
    r"programming|application|data engineering|data|ai|cloud|generative ai|"
    r"business|innovation|machine learning|ai platform"
    r")"
    r".{0,40}(?:&|and)\s+"
    r"(?:development|learning|integration|devops|llms|processing|"
    r"deployment|collaboration|research|machine learning)"
    r"\s*$",
    re.I,
)


def _prepare_jd_text(text: str) -> str:
    """Normalize Docling markdown/HTML before rule or LLM parsing."""
    value = html.unescape(str(text or ""))
    value = re.sub(r"\*\*([^*]+)\*\*", r"\1", value)
    return value

_EXP_HEADING = re.compile(
    r"experience|eligibility|qualification",
    re.I,
)


def _strip_bullet(line: str) -> str:
    """Remove bullet / markdown markers from a JD line."""
    value = str(line or "").strip()
    # Docling often emits "-  text" — strip repeatedly.
    for _ in range(3):
        cleaned = _BULLET_PREFIX_RE.sub("", value).strip()
        if cleaned == value:
            break
        value = cleaned
    value = value.lstrip("#").strip()
    return value.strip(" \t-–—•*")


def _is_skill_category_heading(phrase: str) -> bool:
    """Docling emits bold subheadings like 'Programming & Development' inside skill lists."""
    cleaned = re.sub(r"\s+", " ", phrase).strip(" .:-")
    if not cleaned:
        return False
    if _SKILL_CATEGORY_HEADING_RE.match(cleaned):
        return True
    return bool(
        re.fullmatch(
            r"(?:ai|data|cloud|generative ai)\s*(?:&|and)\s*"
            r"(?:machine learning|integration|devops|llms)",
            cleaned,
            re.I,
        )
    )


def _looks_like_skill_phrase(line: str) -> bool:
    """True for short skill labels; false for duties, education, or experience sentences."""
    phrase = _strip_bullet(line)
    if not phrase or len(phrase) < 2:
        return False
    if _is_skill_category_heading(phrase):
        return False
    words = phrase.split()
    if len(phrase) > 90 or len(words) > 12:
        return False
    if phrase.endswith(".") and len(words) > 6:
        return False
    if _EDU_RE.search(phrase) and re.search(
        r"\b(?:degree|bachelor|master|ph\.?d|diploma|discipline)\b",
        phrase,
        re.I,
    ):
        return False
    if re.search(r"\b\d+(?:\.\d+)?\s*\+?\s*years?\b", phrase, re.I) and re.search(
        r"\b(?:experience|minimum|at least|progressive)\b",
        phrase,
        re.I,
    ):
        return False
    if len(words) > 8 and re.match(
        r"^(?:develop|design|build|maintain|manage|collaborate|"
        r"implement|create|lead|support|analy[sz]e|automate|"
        r"prepare|deliver|coordinate|handle|administer|"
        r"work with|assist with|plan|advise)\b",
        phrase,
        re.I,
    ):
        return False
    return True


def _split_inline_skill_parts(phrase: str) -> list[str]:
    """Split list markers without breaking HTML entities (unescape first) or CI/CD."""
    parts = [
        part.strip(" .")
        for part in re.split(r"\s*[,;|]\s*", phrase)
        if part.strip(" .")
    ]
    expanded: list[str] = []
    for part in parts:
        if re.search(r"\s/\s", part):
            expanded.extend(
                segment.strip(" .")
                for segment in re.split(r"\s/\s", part)
                if segment.strip(" .")
            )
        else:
            expanded.append(part)
    return expanded


def _skill_phrases_from_line(line: str) -> list[str]:
    """Split comma/semicolon lists used in inline 'Required Skills: A, B, C' JDs."""
    phrase = _strip_bullet(line)
    phrase = re.sub(
        r"\s*\((?:preferred|nice to have|bonus)\)\s*$",
        "",
        phrase,
        flags=re.I,
    ).strip()
    if not phrase:
        return []
    if re.search(r"[,;|]|\s/\s", phrase):
        parts = _split_inline_skill_parts(phrase)
        return [part for part in parts if _looks_like_skill_phrase(part)]
    return [phrase] if _looks_like_skill_phrase(phrase) else []

_EDU_RE = re.compile(
    r"\b("
    r"bachelor|master|ph\.?d|doctorate|"
    r"degree|diploma|b\.?tech|m\.?tech|"
    r"bca|mca|bba|mba"
    r")\b",
    re.I,
)

_CERT_RE = re.compile(
    r"\b("
    r"certification|certified|certificate|"
    r"pmp|scrummaster|csm"
    r")\b",
    re.I,
)

_RANGE_YEARS_RE = re.compile(
    r"(?P<minimum>\d+(?:\.\d+)?)"
    r"\s*(?:-|–|—|to)\s*"
    r"(?P<maximum>\d+(?:\.\d+)?)"
    r"\s*\+?\s*years?",
    re.I,
)

_SINGLE_YEARS_RE = re.compile(
    r"(?P<context>.{0,80}?)"
    r"(?P<years>\d+(?:\.\d+)?)"
    r"\s*\+?\s*years?",
    re.I,
)


def _split_sections(
    text: str,
) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []

    heading = "general"
    body: list[str] = []

    def is_heading(
        value: str,
    ) -> bool:
        return bool(
            len(value) <= 65
            and len(value.split()) <= 8
            and (
                _RESP_HEADING.search(value)
                or _PREF_HEADING.search(value)
                or _REQ_HEADING.search(value)
                or _EXP_HEADING.fullmatch(value.strip())
                or re.fullmatch(
                    r"education|certifications?|"
                    r"about the role|job description|"
                    r"role summary|expected outcomes|"
                    r"success measures|key responsibilities|"
                    r"job summary|about the company",
                    value,
                    re.I,
                )
            )
        )

    for raw in text.splitlines():
        line = raw.strip()

        if not line:
            continue

        stripped = line.strip("#* ")

        if ":" in stripped:
            label, remainder = stripped.split(
                ":",
                1,
            )

            if is_heading(label.strip()):
                if body:
                    sections.append(
                        (
                            heading,
                            body,
                        )
                    )

                heading = label.strip()
                body = []

                if remainder.strip():
                    body.append(_strip_bullet(remainder))

                continue

        clean = stripped.rstrip(":").strip()

        if is_heading(clean):
            if body:
                sections.append(
                    (
                        heading,
                        body,
                    )
                )

            heading = clean
            body = []

        else:
            body.append(_strip_bullet(line))

    if body:
        sections.append(
            (
                heading,
                body,
            )
        )

    return sections


def _find_job_title(
    text: str,
    lines: list[str],
) -> str:
    job_desc_match = re.search(
        r"job description\s*[–—-]\s*([^\n]{3,80})",
        text,
        re.I,
    )
    if job_desc_match:
        return job_desc_match.group(1).strip(" .:-")

    for line in lines[:8]:
        stripped = _strip_bullet(line).lstrip("#").strip()
        stripped = re.sub(
            r"^(?:job\s*title|position|role)\s*:\s*",
            "",
            stripped,
            flags=re.I,
        ).strip()
        if _SKIP_TITLE_RE.match(stripped):
            continue
        if (
            8 <= len(stripped) <= 80
            and len(stripped.split()) <= 10
            and not stripped.endswith(".")
            and not re.search(
                r"job description|about us|company|"
                r"location|work mode|department|"
                r"employment type|experience required|"
                r"designed for|alignment|role purpose",
                stripped,
                re.I,
            )
        ):
            return stripped

    patterns = (
        r"(?:job title|position|role)"
        r"\s*:\s*([^\n|]{2,80})",
        r"(?:hiring|seeking|looking for)"
        r"\s+(?:an?\s+)?([A-Z][^\n.,]{2,60}?(?:Manager|Engineer|Developer|Analyst|Lead|Specialist|Officer|Executive|Director))",
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            re.I,
        )

        if match:
            return match.group(1).strip(" .:-")

    return ""


def _experience_lines(
    text: str,
) -> list[str]:
    lines = clean_lines(text)

    return dedupe_preserve(
        [
            line
            for line in lines
            if (
                re.search(
                    r"\byears?\b",
                    line,
                    re.I,
                )
                and (
                    re.search(
                    r"experience|experienced|minimum|"
                    r"preferred|required|relevant|hands-on|"
                    r"at\s+least|internships?",
                        line,
                        re.I,
                    )
                    or _RANGE_YEARS_RE.search(line)
                )
            )
        ]
    )


def _classify_experience_requirement_kind(
    requirements: list[str],
    text: str = "",
) -> tuple[str, bool]:
    """
    Classify how JD experience years should be satisfied.

    Conservative default: professional employment only.
    Internships count toward the requirement ONLY when the JD explicitly
    includes them (e.g. "including internships").

    When requirement lines conflict, the stricter interpretation wins:
    professional/industry > internship_included > relevant > hands_on > any.
    """
    lines = [line for line in requirements if line and line.strip()]
    if not lines and text:
        lines = [text]

    allows_internship = False
    kinds: list[str] = []

    for line in lines:
        lower = line.casefold()
        line_allows = bool(
            re.search(
                r"includ(?:e|ing|es)\s+internships?"
                r"|internships?\s+(?:are\s+)?(?:accepted|allowed|count|considered)"
                r"|experience\s+including\s+internships?",
                lower,
            )
        )
        allows_internship = allows_internship or line_allows

        if line_allows:
            kinds.append("internship_included")
        elif re.search(r"\bindustry\s+experience\b", lower):
            kinds.append("industry")
        elif re.search(r"\bprofessional\s+experience\b|\bwork\s+experience\b", lower):
            kinds.append("professional")
        elif re.search(r"\brelevant\s+experience\b", lower):
            kinds.append("relevant")
        elif re.search(r"\bhands[\s-]?on\b", lower):
            kinds.append("hands_on")
        elif re.search(r"\byears?\b", lower) and re.search(
            r"experience|development|engineer",
            lower,
        ):
            # "N years of Python development" → professional by default.
            kinds.append("professional")
        else:
            kinds.append("professional")

    priority = [
        "professional",
        "industry",
        "internship_included",
        "relevant",
        "hands_on",
        "any",
    ]
    kind = "professional"
    for candidate in priority:
        if candidate in kinds:
            kind = candidate
            break

    if kind == "internship_included":
        allows_internship = True

    return kind, allows_internship


def _extract_experience(
    text: str,
) -> tuple[
    float | None,
    float | None,
    float | None,
    list[str],
    str,
    bool,
]:
    requirements = _experience_lines(text)

    required_minimums: list[float] = []
    required_maximums: list[float] = []
    preferred_values: list[float] = []

    for line in requirements:
        is_preferred = bool(_PREFERRED_SIGNALS.search(line))

        range_match = _RANGE_YEARS_RE.search(line)

        if range_match:
            minimum = float(range_match.group("minimum"))

            maximum = float(range_match.group("maximum"))

            if is_preferred:
                preferred_values.append(minimum)

            else:
                required_minimums.append(minimum)

                required_maximums.append(maximum)

            continue

        for match in _SINGLE_YEARS_RE.finditer(line):
            years = float(match.group("years"))

            context = f"{match.group('context')} {line}"

            if is_preferred or _PREFERRED_SIGNALS.search(context):
                preferred_values.append(years)

            else:
                required_minimums.append(years)

    # Strictest mandatory floor wins when multiple experience lines exist
    # (e.g. "4-6 years Python" + "Minimum 3 years hands-on" → floor = 4).
    minimum = max(required_minimums) if required_minimums else None

    maximum = max(required_maximums) if required_maximums else None

    preferred = max(preferred_values) if preferred_values else None

    kind, allows_internship = _classify_experience_requirement_kind(
        requirements,
        text,
    )

    return (
        minimum,
        maximum,
        preferred,
        requirements,
        kind,
        allows_internship,
    )


def _classify_skills(
    text: str,
    sections: list[tuple[str, list[str]]],
) -> tuple[
    list[str],
    list[str],
    list[str],
    list[str],
]:
    required_raw: list[str] = []
    preferred_raw: list[str] = []
    explicit_required: list[str] = []
    explicit_preferred: list[str] = []

    for heading, lines in sections:
        heading_preferred = bool(_PREF_HEADING.search(heading))
        heading_required = bool(_REQ_HEADING.search(heading) and not heading_preferred)
        explicit_skill_list = bool(_EXPLICIT_SKILL_HEADING.search(heading))

        if explicit_skill_list:
            phrases: list[str] = []
            for line in lines:
                phrases.extend(_skill_phrases_from_line(line))
            if heading_preferred:
                explicit_preferred.extend(phrases)
            else:
                explicit_required.extend(phrases)
            continue

        # Qualifications / responsibilities: only keep catalog hits that are not
        # soft-skill fillers. Soft skills in "Strong communication..." lines must
        # not replace an explicit Required Skills list.
        for line in lines:
            matches = find_known_skills(line)
            if not matches:
                continue

            preferred = heading_preferred or bool(_PREFERRED_SIGNALS.search(line))
            required = heading_required or bool(_REQUIRED_SIGNALS.search(line))

            for match in matches:
                if str(match.get("category", "")) == "soft_skills":
                    continue
                raw = str(match["raw"])
                if preferred and not required:
                    preferred_raw.append(raw)
                elif required or not _RESP_HEADING.search(heading):
                    required_raw.append(raw)

    if explicit_required:
        required_raw = explicit_required
    if explicit_preferred:
        preferred_raw = explicit_preferred + preferred_raw

    has_responsibility_section = any(
        _RESP_HEADING.search(heading) for heading, _lines in sections
    )

    if not required_raw and not preferred_raw and not has_responsibility_section:
        for match in find_known_skills(text):
            start = max(0, int(match["start"]) - 80)
            end = min(len(text), int(match["end"]) + 80)
            context = text[start:end]
            if _PREFERRED_SIGNALS.search(context):
                preferred_raw.append(str(match["raw"]))
            else:
                required_raw.append(str(match["raw"]))

    required_raw = dedupe_preserve(required_raw)
    preferred_raw = dedupe_preserve(preferred_raw)
    required_norm = normalize_skills(required_raw)
    preferred_norm = [
        skill for skill in normalize_skills(preferred_raw) if skill not in required_norm
    ]
    preferred_raw = [
        raw
        for raw in preferred_raw
        if (normalize_skills([raw]) and normalize_skills([raw])[0] not in required_norm)
    ]

    return (
        required_raw,
        required_norm,
        preferred_raw,
        preferred_norm,
    )



_JD_LOCATION_RE = re.compile(
    r"(?:location|work\s*location|based\s*in)\s*[:\-]\s*([^\n|;]+)",
    re.I,
)
_JD_NOTICE_RE = re.compile(
    r"(?:notice\s*period|joining\s*period)\s*[:\-]?\s*(\d+)\s*(day|days|month|months)",
    re.I,
)
_JD_REMOTE_RE = re.compile(r"\b(remote|hybrid|on[- ]?site|work\s*from\s*home|wfh)\b", re.I)


def _extract_jd_location_notice(text: str) -> tuple[list[str], list[str], int | None]:
    locations: list[str] = []
    arrangements: list[str] = []
    notice_days: int | None = None
    for match in _JD_LOCATION_RE.finditer(text or ""):
        value = " ".join(match.group(1).split()).strip(" ,.;")
        if value:
            locations.append(value)
    for match in _JD_REMOTE_RE.finditer(text or ""):
        arrangements.append(match.group(1))
    notice_match = _JD_NOTICE_RE.search(text or "")
    if notice_match:
        amount = int(notice_match.group(1))
        unit = notice_match.group(2).lower()
        notice_days = amount * 30 if unit.startswith("month") else amount
    return dedupe_preserve(locations), dedupe_preserve(arrangements), notice_days

def _rule_based_parse(
    text: str,
) -> ParsedJD:
    lines = clean_lines(text)

    sections = _split_sections(text)

    (
        required_raw,
        required_norm,
        preferred_raw,
        preferred_norm,
    ) = _classify_skills(
        text,
        sections,
    )

    (
        minimum_exp,
        maximum_exp,
        preferred_exp,
        experience_requirements,
        experience_requirement_kind,
        allows_internship_for_requirement,
    ) = _extract_experience(text)

    responsibilities: list[str] = []
    education: list[str] = []
    certifications: list[str] = []

    for heading, section_lines in sections:
        if _RESP_HEADING.search(heading):
            responsibilities.extend(section_lines)

        for line in section_lines:
            if _EDU_RE.search(line):
                education.append(line)

            if _CERT_RE.search(line):
                certifications.append(line)

    if not responsibilities:
        responsibilities = [
            line
            for line in lines
            if re.match(
                r"^(develop|design|build|maintain|"
                r"manage|collaborate|implement|create|"
                r"lead|support|analy[sz]e|automate|"
                r"prepare|deliver)",
                line,
                re.I,
            )
        ]

    excluded_skill_tokens = {
        token.casefold().strip(".+#")
        for skill in (required_norm + preferred_norm)
        for token in skill.split()
    }

    return ParsedJD(
        job_title=_find_job_title(
            text,
            lines,
        ),
        required_skills=SkillList(
            raw=required_raw,
            normalized=required_norm,
        ),
        preferred_skills=SkillList(
            raw=preferred_raw,
            normalized=preferred_norm,
        ),
        responsibilities=dedupe_preserve(responsibilities),
        minimum_experience_years=minimum_exp,
        maximum_experience_years=maximum_exp,
        preferred_experience_years=preferred_exp,
        experience_requirements=experience_requirements,
        experience_requirement_kind=experience_requirement_kind,  # type: ignore[arg-type]
        allows_internship_for_requirement=allows_internship_for_requirement,
        education_requirements=dedupe_preserve(education),
        certifications=dedupe_preserve(certifications),
        keywords=[
            keyword
            for keyword in extract_keywords(text)
            if keyword not in excluded_skill_tokens
        ],
        locations=_extract_jd_location_notice(text)[0],
        work_arrangements=_extract_jd_location_notice(text)[1],
        maximum_notice_period_days=_extract_jd_location_notice(text)[2],
        parsing_method="rule_based",
    )


@lru_cache(maxsize=1)
def _groq_client():
    if not settings.GROQ_API_KEY:
        return None

    try:
        from groq import Groq

    except ImportError:
        logger.warning("Groq package is not installed; JD parser will use rules only.")

        return None

    return Groq(
        api_key=settings.GROQ_API_KEY,
        timeout=settings.GROQ_TIMEOUT_SECONDS,
        max_retries=settings.GROQ_MAX_RETRIES,
    )


def _parse_with_llm(
    text: str,
) -> dict[str, Any] | None:
    client = _groq_client()

    if not client or not settings.USE_LLM_FOR_JD_PARSING:
        return None

    prompt = """
Extract this job description into JSON only.
Do not invent information.

Shape:
{
  "job_title": "",
  "required_skills": [],
  "preferred_skills": [],
  "responsibilities": [],
  "minimum_experience_years": null,
  "maximum_experience_years": null,
  "preferred_experience_years": null,
  "experience_requirements": [],
  "education_requirements": [],
  "certifications": []
}

Keep required and preferred skills separate.

When the JD has an explicit "Required Skills" or "Preferred Skills"
section, copy those bullet items into required_skills / preferred_skills
verbatim (including HR, marketing, operations, and other non-technical
skills). Do not replace them with soft skills from Qualifications.

Preserve the full experience requirement sentence,
especially text such as:
"3-4 years of Python development experience".
"At least 8 years of progressive professional experience in Human Resources".

    JOB DESCRIPTION:
""" + text[:12000] + f"\n\nAnalysis style: {prompt_style_instruction()}"

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            temperature=settings.GROQ_TEMPERATURE,
            response_format={"type": "json_object"},
            max_tokens=settings.GROQ_MAX_TOKENS,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You extract structured "
                        "job-description facts and "
                        "return valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        response_content = response.choices[0].message.content
        if not response_content:
            return None
        content = response_content.strip()

        content = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            content,
            flags=re.I | re.S,
        )

        parsed = json.loads(content)

        return (
            parsed
            if isinstance(
                parsed,
                dict,
            )
            else None
        )

    except Exception:
        logger.exception("Groq JD parsing failed; using deterministic parser.")

        return None


def _number_if_evidenced(
    value: Any,
    source_text: str,
) -> float | None:
    try:
        number = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None

    number_text = str(int(number)) if number.is_integer() else str(number)

    if re.search(
        rf"(?<!\d)"
        rf"{re.escape(number_text)}"
        rf"(?!\d)",
        source_text,
    ):
        return number

    return None


def _evidenced_llm_phrases(
    values: Any,
    source_text: str,
) -> list[str]:
    if not isinstance(values, list):
        return []

    phrases: list[str] = []
    for value in values:
        phrase = re.sub(r"\s+", " ", str(value)).strip(" •*-–—")
        if phrase and text_contains_phrase(source_text, phrase):
            phrases.append(phrase)
    return dedupe_preserve(phrases)


def _merge_llm_result(
    base: ParsedJD,
    llm: dict[str, Any],
    source_text: str,
) -> ParsedJD:
    evidence_skills = {
        str(match["normalized"]) for match in find_known_skills(source_text)
    }

    def _keep_llm_skill(skill: str) -> bool:
        if skill in evidence_skills:
            return True
        return text_contains_phrase(source_text, skill)

    llm_required = [
        skill
        for skill in normalize_skills(map(str, llm.get("required_skills", []) or []))
        if _keep_llm_skill(skill)
    ]
    llm_preferred = [
        skill
        for skill in normalize_skills(map(str, llm.get("preferred_skills", []) or []))
        if _keep_llm_skill(skill)
    ]

    required = dedupe_preserve(base.required_skills.normalized + llm_required)
    required_keys = {skill.casefold() for skill in required}
    preferred = [
        skill
        for skill in dedupe_preserve(base.preferred_skills.normalized + llm_preferred)
        if skill.casefold() not in required_keys
    ]

    title = base.job_title
    llm_title = str(llm.get("job_title", "")).strip()
    if llm_title and text_contains_phrase(source_text, llm_title):
        title = llm_title

    experience_requirements = dedupe_preserve(
        base.experience_requirements
        + _evidenced_llm_phrases(
            llm.get("experience_requirements", []),
            source_text,
        )
    )
    responsibilities = dedupe_preserve(
        base.responsibilities
        + _evidenced_llm_phrases(llm.get("responsibilities", []), source_text)
    )
    education = dedupe_preserve(
        base.education_requirements
        + _evidenced_llm_phrases(
            llm.get("education_requirements", []),
            source_text,
        )
    )
    certifications = dedupe_preserve(
        base.certifications
        + _evidenced_llm_phrases(llm.get("certifications", []), source_text)
    )

    minimum = base.minimum_experience_years
    maximum = base.maximum_experience_years
    preferred_exp = base.preferred_experience_years

    if minimum is None:
        minimum = _number_if_evidenced(llm.get("minimum_experience_years"), source_text)
    if maximum is None:
        maximum = _number_if_evidenced(llm.get("maximum_experience_years"), source_text)
    if preferred_exp is None:
        preferred_exp = _number_if_evidenced(
            llm.get("preferred_experience_years"), source_text
        )

    warnings = list(base.warnings)
    if minimum is not None and maximum is not None and maximum < minimum:
        warnings.append(
            "The LLM returned an invalid experience range; the upper bound was ignored."
        )
        maximum = base.maximum_experience_years

    payload = base.model_dump(mode="python")
    payload.update(
        {
            "job_title": title,
            "required_skills": SkillList(
                raw=dedupe_preserve(base.required_skills.raw + llm_required),
                normalized=required,
            ),
            "preferred_skills": SkillList(
                raw=dedupe_preserve(base.preferred_skills.raw + llm_preferred),
                normalized=preferred,
            ),
            "responsibilities": responsibilities,
            "minimum_experience_years": minimum,
            "maximum_experience_years": maximum,
            "preferred_experience_years": preferred_exp,
            "experience_requirements": experience_requirements,
            "education_requirements": education,
            "certifications": certifications,
            "parsing_method": "hybrid_llm_rules",
            "warnings": dedupe_preserve(warnings),
        }
    )
    return ParsedJD.model_validate(payload)


def parse_job_description(
    jd_text: str,
) -> ParsedJD:
    text = _prepare_jd_text(jd_text.strip())

    if len(text) > settings.MAX_JD_TEXT_CHARS:
        raise ValueError(
            f"JD text exceeds the {settings.MAX_JD_TEXT_CHARS:,}-character limit."
        )

    if not text:
        raise ValueError("JD text cannot be empty.")

    base = _rule_based_parse(text)

    llm = _parse_with_llm(text)

    if llm:
        return _merge_llm_result(
            base,
            llm,
            text,
        )

    return base
