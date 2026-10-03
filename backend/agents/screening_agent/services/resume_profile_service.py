from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from agents.screening_agent.schemas.ats import (
    CandidateDetails,
    CandidateProfile,
    ExperienceEntry,
)
from agents.screening_agent.services.section_detector import detect_sections
from agents.screening_agent.services.resume_parser import (
    extract_emails_from_text,
    guess_candidate_name,
)
from agents.screening_agent.services.skill_extractor import (
    extract_resume_skills,
)
from agents.screening_agent.utils.resume_content import (
    flatten_section_items,
    get_canonical_section_text,
)
from agents.screening_agent.utils.skill_normalizer import find_known_skills
from agents.screening_agent.utils.text_utils import (
    dedupe_preserve,
    extract_keywords,
)


_EMAIL = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)

_SPACED_EMAIL = re.compile(
    r"([A-Za-z0-9._%+-]+)\s*@\s*([A-Za-z0-9.-]+)\s*\.\s*([A-Za-z]{2,})"
)

_PHONE = re.compile(
    r"(?:\+91[\s-]*)?[6-9]\d{4}[\s-]?\d{5}"
)

_URL = re.compile(
    r"(?:https?://|www\.)\S+|"
    r"(?:linkedin\.com|github\.com)/\S+",
    re.I,
)

_EXPERIENCE_HEADING = re.compile(
    r"experience|employment|work history|"
    r"professional background|career history|"
    r"professional experience|work experience|"
    r"relevant experience|technical experience|"
    r"internship|internships|industrial training|"
    r"apprenticeship|freelance|consulting|"
    r"volunteer(?:ing)?(?: experience)?|"
    r"research experience|research assistant",
    re.I,
)

_PROJECT_HEADING = re.compile(
    r"projects?|portfolio|case studies|"
    r"academic projects?|personal projects?|"
    r"research projects?|key projects?",
    re.I,
)

_RESEARCH_HEADING = re.compile(
    r"\bresearch\b|\bpublications?\b",
    re.I,
)

_EDUCATION_HEADING = re.compile(
    r"(?:^|\b)(?:education(?:al)?(?:\s+(?:qualifications?|details|background|history))?|"
    r"academic(?:s)?(?:\s+(?:background|qualifications?|details|history|profile))?|"
    r"scholastic(?:\s+(?:record|achievements?|details|background))?|"
    r"qualifications?)(?:\b|$)",
    re.I,
)

_CERT_HEADING = re.compile(
    r"certification|certificate|"
    r"licen[cs]e|training|course",
    re.I,
)


_NOTICE_RE = re.compile(
    r"notice\s*period\s*[:\-]?\s*(\d+)\s*(day|days|month|months)",
    re.I,
)
_LOCATION_RE = re.compile(
    r"(?:location|based in|residing in|current location)\s*[:\-]\s*([A-Za-z .,]{2,60})",
    re.I,
)


def _extract_location_and_notice(text: str) -> tuple[str, int | None]:
    location = ""
    notice_days: int | None = None
    loc_match = _LOCATION_RE.search(text or "")
    if loc_match:
        location = " ".join(loc_match.group(1).split()).strip(" ,.")
    notice_match = _NOTICE_RE.search(text or "")
    if notice_match:
        amount = int(notice_match.group(1))
        unit = notice_match.group(2).lower()
        notice_days = amount * 30 if unit.startswith("month") else amount
    return location, notice_days

_DEGREE_LINE = re.compile(
    r"(?:"
    r"(?<![A-Za-z])(?:"
    r"ph\.?d\.?|m\.?\s*tech\.?|b\.?\s*tech\.?|"
    r"m\.?\s*e\.?|b\.?\s*e\.?|"
    r"m\.?\s*sc\.?|b\.?\s*sc\.?|"
    r"m\.?\s*com\.?|b\.?\s*com\.?|"
    r"m\.?\s*c\.?\s*a\.?|b\.?\s*c\.?\s*a\.?|"
    r"m\.?\s*b\.?\s*a\.?|b\.?\s*b\.?\s*a\.?|"
    r"m\.?\s*a\.?|b\.?\s*a\.?|"
    r"h\.?\s*s\.?\s*c\.?|s\.?\s*s\.?\s*c\.?"
    r")(?![A-Za-z])|"
    r"\b(?:"
    r"doctorate|"
    r"master'?s|masters|master\s+(?:of|in|degree)|"
    r"bachelor(?:'?s)?|"
    r"post\s*graduate|undergraduate|"
    r"mca|bca|mba|bba|"
    r"diploma|degree|graduat(?:e|ion)|"
    r"higher\s+secondary|senior\s+secondary|"
    r"cbse|icse|"
    r"(?:class|std\.?|standard)\s*(?:10|12|x{1,2}|xii)|"
    r"10th|12th|xth|xiith"
    r")\b"
    r")",
    re.I,
)

_UNIVERSITY_LINE = re.compile(
    r"\b(?:university|college|institute|polytechnic|"
    r"vidyalaya|vidyapeeth|academy|campus|"
    r"school of|high\s+school|secondary\s+school|"
    r"board of|education board|state board)\b",
    re.I,
)

_SCORE_LINE = re.compile(
    r"(?:"
    r"(?:cgpa|gpa|sgpa|sgpi|spi|cpi|pointer)\s*[:\-]?\s*"
    r"\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?"
    r"|"
    r"\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?(?:\s*(?:cgpa|gpa))?"
    r"|"
    r"\d+(?:\.\d+)?\s*(?:cgpa|gpa|sgpa|spi|cpi)"
    r"|"
    r"(?:percentage|percent|pct\.?|marks?)\s*[:\-]?\s*"
    r"\d+(?:\.\d+)?\s*%?"
    r")",
    re.I,
)

_EDU_TABLE_HEADER = re.compile(
    r"^(?:degree|course|program|stream|speciali[sz]ation|"
    r"institute|institution|university|college|board|"
    r"year|duration|duration of study|"
    r"score|cgpa|gpa|percentage|marks?|result)$",
    re.I,
)

_EDU_YEAR = re.compile(r"(?:\b(?:19|20)\d{2}\b|'\d{2}\b)")
_DUTY_VERB_RE = re.compile(
    r"(?:developed|designed|built|implemented|created|deployed|"
    r"worked|responsible|achieved|improved|increased|reduced|"
    r"trained|fine[- ]tuned|owned|led|automated)\b",
    re.I,
)

_ROLE_WORDS = re.compile(
    r"developer|engineer|analyst|scientist|"
    r"architect|consultant|manager|executive|"
    r"specialist|associate|intern|trainee|"
    r"administrator|lead|officer|coordinator|"
    r"support|sales|marketing|recruiter|"
    r"accountant|designer|tester|"
    r"quality assurance|qa|faculty|teacher|professor",
    re.I,
)

_COMPANY_WORDS = re.compile(
    r"\b(?:"
    r"ltd\.?|limited|pvt\.?|private|inc\.?|llp|"
    r"corp\.?|corporation|technologies|technology|"
    r"solutions|services|systems|company|group|"
    r"bank|university|college|institute|"
    r"industries|consulting"
    r")\b",
    re.I,
)

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_MONTH_NAME = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|"
    r"apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|"
    r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)

# Supports: Feb 2025 | Feb 16, 2025 | 16 Feb 2025 | 02/2025 | 16/02/2025 | 2025 | Jun '17
_ABBREV_YEAR = r"'\d{2}"
_DATE_TOKEN = (
    rf"(?:"
    rf"(?:{_MONTH_NAME})"
    rf"(?:\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,)?)?"
    rf"\s+\d{{4}}"
    rf"|"
    rf"(?:{_MONTH_NAME})\s+{_ABBREV_YEAR}"
    rf"|"
    rf"\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTH_NAME}),?\s+\d{{4}}"
    rf"|"
    rf"\d{{1,2}}/\d{{1,2}}/\d{{4}}"
    rf"|"
    rf"\d{{1,2}}/\d{{4}}"
    rf"|"
    rf"\d{{4}}"
    rf")"
)

_RANGE_RE = re.compile(
    rf"(?P<start>{_DATE_TOKEN})"
    rf"\s*(?:-|–|—|to|till|until)\s*"
    rf"(?P<end>{_DATE_TOKEN}|present|current|now|till\s*date|to\s*date)",
    re.I,
)

# LinkedIn/PDF often drops the dash: "Jun '17 May '20"
_ABBREV_SPACE_RANGE_RE = re.compile(
    rf"(?P<start>(?:{_MONTH_NAME})\s+{_ABBREV_YEAR})"
    rf"\s+"
    rf"(?P<end>(?:{_MONTH_NAME})\s+{_ABBREV_YEAR}|present|current|now)",
    re.I,
)

# Common resume form: "February 16 - June 12, 2025" (year only on the end).
_SHARED_YEAR_RANGE_RE = re.compile(
    rf"(?P<start_month>{_MONTH_NAME})"
    rf"(?:\s+(?P<start_day>\d{{1,2}})(?:st|nd|rd|th)?)?"
    rf"\s*(?:-|–|—|to)\s*"
    rf"(?P<end_month>{_MONTH_NAME})"
    rf"(?:\s+(?P<end_day>\d{{1,2}})(?:st|nd|rd|th)?)?"
    rf",?\s+(?P<year>\d{{4}})",
    re.I,
)

_EXPLICIT_YEARS = re.compile(
    r"(?<!\d)(\d+(?:\.\d+)?)"
    r"\s*\+?\s*years?\b",
    re.I,
)

_EXPLICIT_MONTHS = re.compile(
    r"(?<!\d)(\d+(?:\.\d+)?)"
    r"\s*\+?\s*months?\b",
    re.I,
)

_ROLE_KEYS = (
    "role",
    "title",
    "position",
    "designation",
    "job_title",
    "jobtitle",
)

_COMPANY_KEYS = (
    "company",
    "employer",
    "organization",
    "organisation",
    "client",
)

_DATE_KEYS = (
    "date",
    "dates",
    "duration",
    "period",
    "tenure",
    "timeline",
)

_DESCRIPTION_KEYS = (
    "description",
    "responsibilities",
    "responsibility",
    "bullets",
    "achievements",
    "projects",
    "technologies",
    "skills",
    "details",
    "summary",
)


def _flatten_value(
    value: Any,
) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        cleaned = value.strip()

        return [
            cleaned
        ] if cleaned else []

    if isinstance(value, dict):
        parts: list[str] = []

        for nested in value.values():
            parts.extend(
                _flatten_value(
                    nested
                )
            )

        return parts

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        parts: list[str] = []

        for nested in value:
            parts.extend(
                _flatten_value(
                    nested
                )
            )

        return parts

    cleaned = str(value).strip()

    return [
        cleaned
    ] if cleaned else []


def _section_rows(
    parsed_resume: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for section in parsed_resume.get("sections", []):
        if not isinstance(section, dict):
            continue

        heading = str(section.get("heading", "") or "").strip()
        text = get_canonical_section_text(section)
        rows.append(
            {
                "heading": heading,
                "text": text,
                "items": section.get("items", []),
            }
        )

    return rows


def _parse_month(
    token: str,
) -> int | None:
    """Parse a date token to a month index (year*12 + month - 1).

    Day-of-month values are ignored for duration math. Convention:
    inclusive month counting (Feb–Jun = 5 months ≈ 0.42 years).
    """
    token = re.sub(r"\s+", " ", token.strip().casefold())
    token = re.sub(r"\b(till\s*date|to\s*date)\b", "present", token)

    now = datetime.now()

    if token in {
        "present",
        "current",
        "now",
    }:
        return now.year * 12 + now.month - 1

    if re.fullmatch(r"\d{4}", token):
        return int(token) * 12

    if re.fullmatch(r"'\d{2}", token):
        return _century_year(int(token[1:])) * 12

    # Month 'YY  e.g. Jun '17 (LinkedIn abbreviated years)
    named_abbrev = re.fullmatch(rf"({_MONTH_NAME})\s+'(\d{{2}})", token)
    if named_abbrev:
        month = _MONTHS.get(named_abbrev.group(1)[:3])
        if month:
            return _century_year(int(named_abbrev.group(2))) * 12 + month - 1

    numeric_mdy = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", token)
    if numeric_mdy:
        first = int(numeric_mdy.group(1))
        second = int(numeric_mdy.group(2))
        year = int(numeric_mdy.group(3))
        # Prefer DD/MM when day > 12; otherwise treat as MM/DD (US) only if month valid.
        if first > 12 and 1 <= second <= 12:
            month = second
        elif second > 12 and 1 <= first <= 12:
            month = first
        elif 1 <= first <= 12:
            month = first
        else:
            return None
        return year * 12 + month - 1

    numeric = re.fullmatch(r"(\d{1,2})/(\d{4})", token)
    if numeric:
        month = int(numeric.group(1))
        year = int(numeric.group(2))
        if 1 <= month <= 12:
            return year * 12 + month - 1
        return None

    # Month [day] Year  e.g. Feb 16, 2025 | February 2025
    named = re.fullmatch(
        rf"({_MONTH_NAME})(?:\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,)?)?\s+(\d{{4}})",
        token,
    )
    if named:
        month = _MONTHS.get(named.group(1)[:3])
        if month:
            return int(named.group(2)) * 12 + month - 1

    # Day Month Year  e.g. 16 Feb 2025 | 16th February, 2025
    named_dmy = re.fullmatch(
        rf"\d{{1,2}}(?:st|nd|rd|th)?\s+({_MONTH_NAME}),?\s+(\d{{4}})",
        token,
    )
    if named_dmy:
        month = _MONTHS.get(named_dmy.group(1)[:3])
        if month:
            return int(named_dmy.group(2)) * 12 + month - 1

    return None


def _century_year(year: int) -> int:
    if year < 100:
        return 2000 + year if year <= 50 else 1900 + year
    return year


def _line_has_date_range(line: str) -> bool:
    return bool(
        _RANGE_RE.search(line)
        or _SHARED_YEAR_RANGE_RE.search(line)
        or _ABBREV_SPACE_RANGE_RE.search(line)
    )


def _duration_from_text(
    text: str,
) -> tuple[
    str,
    str,
    int | None,
    int | None,
    int | None,
]:
    match = _RANGE_RE.search(
        text
    )

    if match:
        start_text = match.group(
            "start"
        ).strip()

        end_text = match.group(
            "end"
        ).strip()

        start = _parse_month(
            start_text
        )

        end = _parse_month(
            end_text
        )

        if (
            start is not None
            and end is not None
            and end >= start
            and end - start <= 600
        ):
            months = (
                end
                - start
                + 1
            )

            return (
                start_text,
                end_text,
                start,
                end,
                months,
            )

    abbrev_space = _ABBREV_SPACE_RANGE_RE.search(text)
    if abbrev_space:
        start_text = abbrev_space.group("start").strip()
        end_text = abbrev_space.group("end").strip()
        start = _parse_month(start_text)
        end = _parse_month(end_text)
        if (
            start is not None
            and end is not None
            and end >= start
            and end - start <= 600
        ):
            return (
                start_text,
                end_text,
                start,
                end,
                end - start + 1,
            )

    shared = _SHARED_YEAR_RANGE_RE.search(text)
    if shared:
        year = shared.group("year")
        start_month = shared.group("start_month")
        end_month = shared.group("end_month")
        start_day = shared.group("start_day") or ""
        end_day = shared.group("end_day") or ""
        start_text = f"{start_month} {start_day} {year}".strip()
        end_text = f"{end_month} {end_day} {year}".strip()
        start = _parse_month(start_text)
        end = _parse_month(end_text)
        if (
            start is not None
            and end is not None
            and end >= start
            and end - start <= 600
        ):
            return (
                start_text,
                end_text,
                start,
                end,
                end - start + 1,
            )

    explicit_months = [
        float(value)
        for value
        in _EXPLICIT_MONTHS.findall(
            text
        )
    ]

    explicit_years = [
        float(value)
        for value
        in _EXPLICIT_YEARS.findall(
            text
        )
    ]

    if explicit_months:
        return (
            "",
            "",
            None,
            None,
            int(
                round(
                    max(
                        explicit_months
                    )
                )
            ),
        )

    if explicit_years:
        return (
            "",
            "",
            None,
            None,
            int(
                round(
                    max(
                        explicit_years
                    )
                    * 12
                )
            ),
        )

    return (
        "",
        "",
        None,
        None,
        None,
    )


def _clean_header_line(
    line: str,
) -> str:
    line = re.sub(r"^#+\s*", "", line).strip()
    line = _RANGE_RE.sub(
        "",
        line,
    )
    line = _SHARED_YEAR_RANGE_RE.sub(
        "",
        line,
    )
    line = _ABBREV_SPACE_RANGE_RE.sub(
        "",
        line,
    )
    line = re.sub(
        r"^\s*(?:duration|period|dates?|tenure)\s*:?\s*",
        "",
        line,
        flags=re.I,
    )

    line = re.sub(
        r"\s*[|,:\-–—]+\s*$",
        "",
        line,
    )

    return line.strip(
        " •*|,:-–—"
    )


def _guess_role_company(
    lines: list[str],
) -> tuple[str, str]:
    headers: list[str] = []

    for line in lines:
        if _line_has_date_range(line):
            remainder = _clean_header_line(line)
            # Skip pure date lines; keep titles that embed a date range.
            if len(remainder) < 8:
                continue

        cleaned = _clean_header_line(
            line
        )

        if not cleaned:
            continue

        if re.match(
            r"^[•*\-–—]",
            line.strip(),
        ):
            break

        if re.match(
            r"^(?:duration|period|dates?|guide|mentor|advisor)\b",
            cleaned,
            re.I,
        ):
            continue

        if (
            len(cleaned) > 160
            or cleaned.endswith(".")
        ):
            break

        headers.append(
            cleaned
        )

        if len(headers) >= 4:
            break

    role = next(
        (
            line
            for line in headers
            if _ROLE_WORDS.search(
                line
            )
            or len(line.split()) <= 12
        ),
        "",
    )

    company = next(
        (
            line
            for line in headers
            if (
                line != role
                and (
                    _COMPANY_WORDS.search(
                        line
                    )
                    or len(
                        line.split()
                    ) <= 7
                )
            )
        ),
        "",
    )

    if (
        not role
        and headers
    ):
        role = headers[0]

    if (
        not company
        and len(headers) > 1
    ):
        company = (
            headers[1]
            if headers[1] != role
            else ""
        )

    return (
        role,
        company,
    )


def _entry_from_text(
    text: str,
    *,
    section_heading: str,
    entry_type: str,
    role: str = "",
    company: str = "",
) -> ExperienceEntry | None:
    cleaned = text.strip()

    if not cleaned:
        return None

    lines = [
        line.strip()
        for line
        in cleaned.splitlines()
        if line.strip()
    ]

    (
        guessed_role,
        guessed_company,
    ) = _guess_role_company(
        lines
    )

    role = (
        role.strip()
        or guessed_role
    )

    company = (
        company.strip()
        or guessed_company
    )

    (
        start_text,
        end_text,
        start,
        end,
        months,
    ) = _duration_from_text(
        cleaned
    )

    if (
        entry_type == "employment"
        and re.search(
            r"\bintern(?:ship)?\b|\btrainee\b",
            role or cleaned,
            re.I,
        )
    ):
        entry_type = "internship"

    elif entry_type in {"employment", "other"} and re.search(
        r"\bresearch\s+assistant\b|\bresearch\s+intern\b",
        role or cleaned,
        re.I,
    ):
        entry_type = "research"

    return ExperienceEntry(
        role=role,
        company=company,
        entry_type=entry_type,
        source_section=section_heading,
        start_date=start_text,
        end_date=end_text,
        start_month_index=start,
        end_month_index=end,
        duration_months=months,
        duration_years=(
            round(
                months / 12,
                2,
            )
            if months is not None
            else None
        ),
        text=cleaned,
    )


def _dict_first(
    data: dict[str, Any],
    keys: tuple[str, ...],
) -> str:
    lowered = {
        str(key).casefold(): value
        for key, value in data.items()
    }

    for key in keys:
        if key in lowered:
            values = _flatten_value(
                lowered[key]
            )

            if values:
                return " | ".join(
                    values
                )

    return ""


def _entries_from_structured_items(
    items: Any,
    *,
    heading: str,
    entry_type: str,
) -> list[ExperienceEntry]:
    if not isinstance(
        items,
        list,
    ):
        return []

    entries: list[ExperienceEntry] = []

    for item in items:
        if not isinstance(
            item,
            dict,
        ):
            continue

        role = _dict_first(
            item,
            _ROLE_KEYS,
        )

        company = _dict_first(
            item,
            _COMPANY_KEYS,
        )

        dates = _dict_first(
            item,
            _DATE_KEYS,
        )

        descriptions: list[str] = []

        for key in _DESCRIPTION_KEYS:
            value = next(
                (
                    value
                    for item_key, value
                    in item.items()
                    if str(
                        item_key
                    ).casefold() == key
                ),
                None,
            )

            descriptions.extend(
                _flatten_value(
                    value
                )
            )

        # Do not treat a complete nested experience section as
        # one job. It must have direct job/company/date evidence.
        if not (
            role
            or company
            or dates
        ):
            continue

        full_parts = [
            part
            for part in (
                role,
                company,
                dates,
                *descriptions,
            )
            if part
        ]

        entry = _entry_from_text(
            "\n".join(
                full_parts
            ),
            section_heading=heading,
            entry_type=entry_type,
            role=role,
            company=company,
        )

        if entry:
            entries.append(
                entry
            )

    return entries


def _date_block_starts(
    lines: list[str],
    date_indexes: list[int],
) -> list[int]:
    starts: list[int] = []
    previous_date = -1

    for date_index in date_indexes:
        start = date_index
        cursor = date_index - 1
        header_lines = 0

        while cursor > previous_date:
            line = lines[
                cursor
            ].strip()

            if not line:
                if header_lines:
                    break

                cursor -= 1
                continue

            if (
                _line_has_date_range(
                    line
                )
                or re.match(
                    r"^[•*\-–—]",
                    line,
                )
            ):
                break

            if (
                len(line) > 180
                or line.endswith(".")
            ):
                break

            start = cursor
            header_lines += 1

            if header_lines >= 3:
                break

            cursor -= 1

        starts.append(
            start
        )

        previous_date = date_index

    return starts


def _entries_from_text_section(
    text: str,
    *,
    heading: str,
    entry_type: str,
) -> list[ExperienceEntry]:
    if not text.strip():
        return []

    lines = text.splitlines()

    date_indexes = [
        index
        for index, line
        in enumerate(
            lines
        )
        if _line_has_date_range(
            line
        )
    ]

    entries: list[ExperienceEntry] = []

    if date_indexes:
        starts = _date_block_starts(
            lines,
            date_indexes,
        )

        for position, start in enumerate(
            starts
        ):
            end = (
                starts[
                    position + 1
                ]
                if position + 1
                < len(starts)
                else len(lines)
            )

            block = "\n".join(
                lines[
                    start:end
                ]
            ).strip()

            entry = _entry_from_text(
                block,
                section_heading=heading,
                entry_type=entry_type,
            )

            if entry:
                entries.append(
                    entry
                )

        return entries

    paragraphs = [
        part.strip()
        for part in re.split(
            r"\n\s*\n",
            text,
        )
        if part.strip()
    ]

    for paragraph in paragraphs:
        if not (
            _EXPLICIT_YEARS.search(
                paragraph
            )
            or _EXPLICIT_MONTHS.search(
                paragraph
            )
        ):
            continue

        entry = _entry_from_text(
            paragraph,
            section_heading=heading,
            entry_type=entry_type,
        )

        if entry:
            entries.append(
                entry
            )

    return entries


def _dedupe_entries(
    entries: list[ExperienceEntry],
) -> list[ExperienceEntry]:
    output: list[ExperienceEntry] = []

    seen: set[
        tuple[str, str, str, str]
    ] = set()

    for entry in entries:
        key = (
            entry.role.casefold().strip(),
            entry.company.casefold().strip(),
            entry.start_date.casefold().strip(),
            entry.end_date.casefold().strip(),
        )

        text_key = re.sub(
            r"\s+",
            " ",
            entry.text,
        ).casefold().strip()

        identity = (
            key
            if any(key)
            else (
                text_key,
                "",
                "",
                "",
            )
        )

        if identity in seen:
            continue

        seen.add(
            identity
        )

        output.append(
            entry
        )

    return output


def _looks_like_education_block(text: str) -> bool:
    compact = _DEGREE_LINE.sub(" ", text)
    has_degree = bool(_DEGREE_LINE.search(text))
    has_school = bool(_UNIVERSITY_LINE.search(text))
    has_job_role = bool(_ROLE_WORDS.search(compact))
    if has_degree and has_school and not has_job_role:
        return True
    if has_degree and not has_job_role:
        return True
    return False


def _extract_experience_entries(
    rows: list[dict[str, Any]],
    full_text: str = "",
) -> list[ExperienceEntry]:
    entries: list[ExperienceEntry] = []

    for row in rows:
        heading = str(
            row["heading"]
        )

        if _EXPERIENCE_HEADING.search(heading):
            if re.search(r"intern|trainee|apprentice", heading, re.I):
                entry_type = "internship"
            elif re.search(r"research", heading, re.I):
                entry_type = "research"
            elif re.search(r"volunteer", heading, re.I):
                entry_type = "other"
            else:
                entry_type = "employment"

        elif _PROJECT_HEADING.search(heading):
            entry_type = "project"

        elif _RESEARCH_HEADING.search(heading):
            entry_type = "research"

        else:
            continue

        structured = (
            _entries_from_structured_items(
                row.get(
                    "items"
                ),
                heading=heading,
                entry_type=entry_type,
            )
        )

        entries.extend(
            structured
        )

        text_entries = (
            _entries_from_text_section(
                str(
                    row.get(
                        "text",
                        "",
                    )
                ),
                heading=heading,
                entry_type=entry_type,
            )
        )

        entries.extend(
            text_entries
        )

    recovered_source = full_text or "\n".join(
        str(row.get("text", "")) for row in rows if str(row.get("text", "")).strip()
    )
    recovered = _entries_from_text_section(
        recovered_source,
        heading="Experience",
        entry_type="employment",
    )
    seen_spans = {
        (entry.start_month_index, entry.end_month_index)
        for entry in entries
        if entry.start_month_index is not None and entry.end_month_index is not None
    }
    for entry in recovered:
        if _looks_like_education_block(entry.text):
            continue
        blob = " ".join(part for part in (entry.role, entry.company, entry.text) if part)
        if not _ROLE_WORDS.search(blob) and not entry.company:
            continue
        span = (entry.start_month_index, entry.end_month_index)
        if span[0] is not None and span in seen_spans:
            continue
        if span[0] is not None:
            seen_spans.add(span)
        entries.append(entry)

    return _dedupe_entries(entries)


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


def _total_experience(
    entries: list[ExperienceEntry],
) -> float | None:
    # Professional total only — internships/projects/research are tracked
    # separately and must not inflate professional experience years.
    work_entries = [
        entry
        for entry in entries
        if entry.entry_type == "employment"
    ]

    intervals = [
        (
            entry.start_month_index,
            entry.end_month_index + 1,
        )
        for entry in work_entries
        if (
            entry.start_month_index is not None
            and entry.end_month_index is not None
        )
    ]

    dated_months = _merge_intervals(
        intervals
    )

    # Undated durations cannot safely be added together
    # because the periods may overlap.
    undated_months = max(
        (
            entry.duration_months
            or 0
            for entry in work_entries
            if entry.start_month_index is None
        ),
        default=0,
    )

    total_months = (
        dated_months
        + undated_months
    )

    if not total_months:
        return None

    return round(
        total_months / 12,
        2,
    )


_INVALID_NAME_VALUES = {
    "candidate",
    "candidate name",
    "curriculum vitae",
    "cv",
    "resume",
    "contact",
    "contact information",
    "personal details",
    "unknown",
    "not specified",
    "not available",
    "n/a",
    "na",
    "null",
    "none",
    "image",
    "img",
    "picture",
    "photo",
    "figure",
    "logo",
    "profile",
    "summary",
    "objective",
    "about",
    "about me",
    "skills",
    "technical skills",
    "soft skills",
    "experience",
    "education",
    "projects",
    "certifications",
    "career objective",
    "key competencies",
    "core competencies",
    "competencies",
    "highlights",
    "technical summary",
}

_KNOWN_SECTION_HEADING_RE = re.compile(
    r"^(?:summary|profile|objective|about(?: me)?|career objective|"
    r"education|academics?|qualifications?|"
    r"experience|work experience|professional experience|employment(?: history)?|internships?|"
    r"projects?|skills?|technical skills?|soft skills?|"
    r"(?:key |core )?competenc(?:y|ies)|highlights?|technical summary|"
    r"certifications?|licen[cs]es?|"
    r"publications?|research|patents?|"
    r"awards?|achievements?|honou?rs?|"
    r"conferences?|workshops?|trainings?|"
    r"volunteering(?: experience)?|community service|"
    r"leadership(?: experience)?|extra[- ]?curricular(?: activit(?:y|ies))?|"
    r"open source(?: contributions)?|hackathons?|competitions?|"
    r"languages?|interests?|hobb(?:y|ies)|"
    r"references?|portfolio|contact(?: information)?|social(?: links| profiles)?|"
    r"memberships?|affiliations?|military(?: service)?|declaration|"
    r"personal details|strengths?|additional information)$",
    re.IGNORECASE,
)

_NAME_LABEL_RE = re.compile(
    r"(?:^|\n)\s*(?:candidate\s+)?name\s*:\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)
_EMAIL_LABEL_RE = re.compile(
    r"(?:^|\n)\s*(?:e-?mail(?:\s*(?:id|address))?)\s*[:\-]\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)


def _normalize_heading_label(value: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", value.casefold()).strip()


_HEADING_TAIL_RE = re.compile(
    r"\b(?:summary|profile|objective|education|experience|employment|"
    r"projects?|skills?|certifications?|achievements?|qualifications?|"
    r"highlights|competencies|responsibilities)$",
    re.I,
)


def _is_resume_section_heading(value: str) -> bool:
    normalized = _normalize_heading_label(value)
    if not normalized:
        return True
    if normalized in _INVALID_NAME_VALUES:
        return True
    if _KNOWN_SECTION_HEADING_RE.fullmatch(normalized):
        return True
    words = normalized.split()
    return 2 <= len(words) <= 6 and bool(_HEADING_TAIL_RE.search(normalized))


def _looks_like_org_or_institution(value: str) -> bool:
    """True for school/company lines that should never be treated as a person."""
    cleaned = re.sub(r"\s+", " ", value or "").strip()
    if not cleaned:
        return False
    if _COMPANY_WORDS.search(cleaned) or _UNIVERSITY_LINE.search(cleaned):
        return True
    return bool(
        re.search(
            r"\b(?:campus|faculty|department|board of|"
            r"high\s+school|secondary\s+school)\b",
            cleaned,
            re.I,
        )
    )


def _looks_like_skill_label(value: str) -> bool:
    """True when the whole line is a catalog skill, not a person name."""
    cleaned = re.sub(r"\s+", " ", value or "").strip(" •*|,:-–—")
    if not cleaned or len(cleaned) > 40:
        return False
    compact = re.sub(r"[^a-z0-9+#]+", "", cleaned.casefold())
    if not compact:
        return False
    for match in find_known_skills(cleaned):
        skill = str(match.get("normalized") or "")
        if re.sub(r"[^a-z0-9+#]+", "", skill.casefold()) == compact:
            return True
    return False


def _email_local_letters(email: str) -> str:
    local = (email or "").split("@", 1)[0]
    return re.sub(r"[^a-z]", "", local.casefold())


def _name_supported_by_email(name: str, emails: list[str]) -> bool:
    compact = re.sub(r"[^a-z]", "", name.casefold())
    if len(compact) < 4:
        return False
    return any(compact in _email_local_letters(email) for email in emails if email)


def _name_from_structured_email(email: str) -> str:
    local = (email or "").split("@", 1)[0]
    local = re.sub(r"\d+$", "", local)
    if "." in local or "_" in local or "-" in local:
        parts = re.split(r"[._-]+", local)
        words = [part for part in parts if part.isalpha() and 2 <= len(part) <= 20]
        if 2 <= len(words) <= 4:
            return " ".join(word.title() for word in words)
    return ""


def _is_plausible_person_name(
    value: str,
    *,
    emails: list[str] | None = None,
    labelled: bool = False,
) -> bool:
    if (
        not value
        or _is_resume_section_heading(value)
        or _looks_like_skill_label(value)
        or _looks_like_org_or_institution(value)
    ):
        return False
    words = value.split()
    if labelled:
        return 1 <= len(words) <= 6
    if _name_supported_by_email(value, emails or []):
        return 1 <= len(words) <= 6
    return 2 <= len(words) <= 6


def _source_contact_preamble(source_text: str) -> str:
    """Recover the pre-heading contact block from the original resume text."""
    if not source_text.strip():
        return ""
    blocks = detect_sections(source_text)
    if blocks and blocks[0]["heading"] == "Header":
        return str(blocks[0].get("body", "")).strip()
    return ""


def _collect_detected_contacts(
    parsed_resume: dict[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    emails: list[str] = []
    phones: list[str] = []
    links: list[str] = []

    for section in parsed_resume.get("sections", []):
        if not isinstance(section, dict):
            continue
        detected = section.get("detected_contacts")
        if not isinstance(detected, dict):
            continue
        emails.extend(str(value) for value in detected.get("emails", []) if value)
        phones.extend(str(value) for value in detected.get("phones", []) if value)
        links.extend(str(value) for value in detected.get("links", []) if value)

    return emails, phones, links


def _collapse_spaced_letter_name(value: str) -> str:
    """Convert decorative resume titles like 'S U R A J   S H A R M A'."""
    cleaned = re.sub(r"^#+\s*", "", value).strip(" •*|,:-–—")
    if not cleaned:
        return ""

    name_parts: list[str] = []
    for chunk in re.split(r"\s{2,}", cleaned):
        chunk = chunk.strip()
        if not chunk:
            continue
        tokens = chunk.split()
        if tokens and all(len(token) == 1 and token.isalpha() for token in tokens):
            if len(tokens) < 2:
                continue
            name_parts.append("".join(tokens).title())
            continue
        if 1 <= len(tokens) <= 4 and all(
            re.fullmatch(r"[A-Za-z][A-Za-z.'-]*", token) for token in tokens
        ):
            name_parts.extend(token.title() for token in tokens)
            continue
        return ""

    if not name_parts:
        tokens = cleaned.split()
        if tokens and all(len(token) == 1 and token.isalpha() for token in tokens):
            if len(tokens) < 4:
                return ""
            joined = "".join(tokens).title()
            if 4 <= len(joined) <= 40:
                return joined
        return ""

    result = " ".join(name_parts)
    if not 1 <= len(result.split()) <= 6 or len(result) > 80:
        return ""
    if _ROLE_WORDS.search(result) or _EMAIL.search(result) or re.search(r"\d", result):
        return ""
    if _is_resume_section_heading(result):
        return ""
    return result


def _flatten_items_to_text(items: Any) -> str:
    if not isinstance(items, list):
        return ""
    lines: list[str] = []
    for item in items:
        if isinstance(item, dict):
            key = str(item.get("key", "")).strip()
            value = str(item.get("value", "")).strip()
            if key and value:
                lines.append(f"{key}: {value}")
            elif value:
                lines.append(value)
            elif key:
                lines.append(key)
        elif item is not None:
            lines.append(str(item))
    return "\n".join(lines)


def _extract_name_from_source_lead(source_text: str, emails: list[str] | None = None) -> str:
    if not source_text.strip():
        return ""
    fallback = ""
    for line in source_text.splitlines()[:40]:
        stripped = line.strip()
        if not stripped:
            continue
        heading_probe = re.sub(r"^#+\s*", "", stripped).strip()
        if _is_resume_section_heading(heading_probe):
            continue
        candidate = _clean_candidate_name_line(stripped)
        if not candidate or _is_resume_section_heading(candidate):
            continue
        if _is_plausible_person_name(candidate, emails=emails or []):
            if emails and _name_supported_by_email(candidate, emails):
                return candidate
            if not fallback:
                fallback = candidate
    return fallback


def _extract_labelled_name(text: str, emails: list[str] | None = None) -> str:
    match = _NAME_LABEL_RE.search(text)
    if not match:
        return ""
    candidate = _clean_candidate_name_line(match.group(1).strip())
    if candidate and _is_plausible_person_name(candidate, emails=emails, labelled=True):
        return candidate
    return ""


def _name_before_email(text: str, email: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    emails = [email]
    for index, line in enumerate(lines):
        if email.casefold() not in line.casefold():
            continue
        window = list(reversed(lines[max(0, index - 8) : index])) + lines[index + 1 : index + 6]
        email_match = ""
        other = ""
        for previous in window:
            candidate = _clean_candidate_name_line(previous)
            if not candidate or not _is_plausible_person_name(candidate, emails=emails):
                continue
            if _name_supported_by_email(candidate, emails):
                return candidate
            if not other:
                other = candidate
        return email_match or other
    return ""


def _first_valid_name_from_text(
    text: str,
    *,
    limit: int = 40,
    emails: list[str] | None = None,
) -> str:
    fallback = ""
    for line in text.splitlines()[:limit]:
        candidate = _clean_candidate_name_line(line.strip())
        if not candidate or not _is_plausible_person_name(candidate, emails=emails or []):
            continue
        if emails and _name_supported_by_email(candidate, emails):
            return candidate
        if not fallback:
            fallback = candidate
    return fallback


def _name_from_filename(filename: str) -> str:
    if not filename:
        return ""
    stem = Path(filename).stem
    stem = re.sub(r"^naukri[_-]?", "", stem, flags=re.I)
    stem = re.sub(r"\[.*?\]", " ", stem)
    stem = re.sub(r"\(\d+\)", " ", stem)
    stem = re.sub(r"[-_]+", " ", stem)
    stem = re.sub(
        r"\b(updated|resume|cv|final|copy|draft|new)\b",
        " ",
        stem,
        flags=re.I,
    )
    stem = re.sub(r"\s+", " ", stem).strip()
    return _clean_candidate_name_line(stem)


def _collect_emails(*texts: str) -> list[str]:
    combined = "\n".join(part for part in texts if part)
    if not combined:
        return []
    normalized = _SPACED_EMAIL.sub(
        lambda match: f"{match.group(1)}@{match.group(2)}.{match.group(3)}",
        combined,
    )
    return dedupe_preserve(
        extract_emails_from_text(normalized) + _EMAIL.findall(normalized)
    )


def _clean_candidate_name_line(line: str) -> str:
    spaced_name = _collapse_spaced_letter_name(line)
    if spaced_name:
        return spaced_name

    value = re.sub(r"^#+\s*", "", line).strip(" •*|,:-–—")
    value = re.sub(r"\s+", " ", value).strip()

    labelled = re.match(r"^(?:candidate\s+)?name\s*:\s*(.+)$", value, re.I)
    if labelled:
        value = labelled.group(1).strip()

    # A header line often contains the name before a pipe-separated contact.
    if " | " in value:
        value = value.split(" | ", 1)[0].strip()

    normalized = value.casefold()
    if not value or normalized in _INVALID_NAME_VALUES:
        return ""
    if _is_resume_section_heading(value):
        return ""
    if re.fullmatch(r"<!--\s*.*?\s*-->", value, re.I | re.S):
        return ""
    if re.fullmatch(r"!\[[^]]*]\([^)]*\)", value, re.I):
        return ""
    if re.fullmatch(r"<(?:image|img)(?:\s[^>]*)?/?>", value, re.I):
        return ""
    if _EMAIL.search(value) or _PHONE.fullmatch(value) or _URL.search(value):
        return ""
    if _RANGE_RE.search(value) or re.search(r"\d", value):
        return ""
    if _ROLE_WORDS.search(value) or _COMPANY_WORDS.search(value):
        return ""
    if _looks_like_skill_label(value):
        return ""
    if len(value) > 80 or not 1 <= len(value.split()) <= 6:
        return ""
    if not any(character.isalpha() for character in value):
        return ""
    if any(
        not (character.isalpha() or character in " .'-")
        for character in value
    ):
        return ""
    return value


def _candidate_details(
    rows: list[dict[str, Any]],
    parsed_resume: dict[str, Any] | None = None,
    resume_filename: str = "",
) -> CandidateDetails:
    parsed_resume = parsed_resume or {}
    source_text = str(parsed_resume.get("source_text", "") or "").strip()
    preamble = _source_contact_preamble(source_text)
    filename = resume_filename or str(
        parsed_resume.get("resume_original_filename", "") or ""
    )

    contact_rows = [
        str(row.get("text", ""))
        for row in rows
        if re.search(r"contact|header|personal", str(row.get("heading", "")), re.I)
        and str(row.get("text", "")).strip()
    ]

    if not contact_rows and rows:
        first_heading = str(rows[0].get("heading", "")).strip()
        first_text = str(rows[0].get("text", "")).strip()
        if first_text and not _is_resume_section_heading(first_heading):
            contact_rows = [first_text]
        elif first_text:
            contact_rows = [first_text]

    header_parts = [part for part in (preamble, "\n".join(contact_rows).strip()) if part]
    header_text = "\n".join(header_parts).strip()
    contact_scan = "\n".join(
        line for line in (preamble + "\n" + header_text).splitlines()[:30]
    )

    emails = _collect_emails(header_text, preamble, source_text, contact_scan)
    for row in rows:
        items = row.get("items")
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                key = str(item.get("key", "")).casefold()
                value = str(item.get("value", ""))
                if "email" in key and value:
                    emails.extend(_collect_emails(value))
    detected_emails, detected_phones, detected_links = _collect_detected_contacts(parsed_resume)
    emails = dedupe_preserve(emails + detected_emails)

    for labelled_email in _EMAIL_LABEL_RE.finditer("\n".join((source_text, header_text))):
        emails = dedupe_preserve(emails + _collect_emails(labelled_email.group(1)))
    for row in rows:
        labelled_email = _EMAIL_LABEL_RE.search(str(row.get("text", "")))
        if labelled_email:
            emails = dedupe_preserve(emails + _collect_emails(labelled_email.group(1)))

    name = _extract_labelled_name(source_text or header_text, emails)
    if not name:
        for row in rows:
            labelled = _extract_labelled_name(str(row.get("text", "")), emails)
            if labelled:
                name = labelled
                break
            items = row.get("items")
            if isinstance(items, list):
                labelled = _extract_labelled_name(_flatten_items_to_text(items), emails)
                if labelled:
                    name = labelled
                    break
    if not name and emails:
        name = _name_before_email(source_text or header_text, emails[0])
    if not name:
        name = _extract_name_from_source_lead(source_text, emails)
    if not name:
        guessed = guess_candidate_name(source_text)
        if guessed and _is_plausible_person_name(guessed, emails=emails):
            name = guessed
    if not name:
        name = _first_valid_name_from_text(header_text, emails=emails)
    if not name and preamble:
        name = _first_valid_name_from_text(preamble, emails=emails)
    if not name:
        name = _name_from_filename(filename)
        if name and not _is_plausible_person_name(name, emails=emails):
            name = ""
    if not name and emails:
        name = _name_from_structured_email(emails[0])

    phones = dedupe_preserve(
        [match.group(0).strip() for match in _PHONE.finditer(contact_scan)]
        + detected_phones
    )
    links = dedupe_preserve(
        [match.group(0).rstrip(".,)") for match in _URL.finditer(contact_scan)]
        + detected_links
    )

    return CandidateDetails(
        name=name,
        emails=emails,
        phones=phones,
        links=links,
    )


def _normalize_education_line(line: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(line or "")).strip(" •*-–—|")
    cleaned = re.sub(r"^#+\s*", "", cleaned).strip()
    return cleaned


def _looks_like_duty_or_project_line(line: str) -> bool:
    """True for work/project bullets that must not be stored as education."""
    cleaned = _normalize_education_line(line)
    if not cleaned:
        return False
    if _DUTY_VERB_RE.match(cleaned):
        return True
    if _DEGREE_LINE.search(cleaned) or _UNIVERSITY_LINE.search(cleaned):
        return False
    if re.search(r"\b(?:accuracy|precision|recall|pipeline|module|dataset)\b", cleaned, re.I):
        return True
    return len(cleaned) > 120


def _looks_like_skill_catalog_line(line: str) -> bool:
    """True for 'Label: skill, skill' rows that follow education in two-column PDFs."""
    cleaned = _normalize_education_line(line)
    if not cleaned or ":" not in cleaned:
        return False
    if _DEGREE_LINE.search(cleaned) or _UNIVERSITY_LINE.search(cleaned) or _SCORE_LINE.search(cleaned):
        return False
    label, _, rest = cleaned.partition(":")
    rest = rest.strip()
    if not label.strip() or not rest:
        return False
    if len(label.split()) > 6:
        return False
    return "," in rest


def _looks_like_employment_start(line: str) -> bool:
    """True when a line begins a job, not a course date."""
    cleaned = _normalize_education_line(line)
    if not cleaned:
        return False
    if _DEGREE_LINE.search(cleaned) or _UNIVERSITY_LINE.search(cleaned) or _SCORE_LINE.search(cleaned):
        return False
    if _looks_like_duty_or_project_line(cleaned):
        return True
    if not _line_has_date_range(cleaned):
        return False
    if re.search(r"\b(?:present|current|now|till\s*date)\b", cleaned, re.I):
        return True
    if _ROLE_WORDS.search(cleaned):
        return True
    return bool(
        _COMPANY_WORDS.search(cleaned)
        and not _UNIVERSITY_LINE.search(cleaned)
    )


def _education_content_from_line(line: str) -> str:
    """Keep degree/institute/score fragments; drop duty/project tails on the same line."""
    cleaned = _normalize_education_line(line)
    if not cleaned or _is_other_resume_section_heading(cleaned):
        return ""
    fragments: list[str] = []
    for part in re.split(r"\s*\|\s*", cleaned):
        part = part.strip()
        if not part:
            continue
        if _is_other_resume_section_heading(part):
            break
        if _looks_like_duty_or_project_line(part):
            duty = _DUTY_VERB_RE.search(part)
            if duty and duty.start() > 0 and (
                _DEGREE_LINE.search(part[: duty.start()])
                or _UNIVERSITY_LINE.search(part[: duty.start()])
                or _SCORE_LINE.search(part[: duty.start()])
            ):
                prefix = part[: duty.start()].strip(" ,;-")
                if prefix:
                    fragments.append(prefix)
            break
        fragments.append(part)
    return " | ".join(fragments)


def _clip_education_span(text: str) -> str:
    """Keep education facts; stop at the next section, skill list, or job."""
    kept: list[str] = []
    seen_education_fact = False
    for raw in str(text or "").splitlines():
        line = _normalize_education_line(raw)
        if not line:
            if seen_education_fact:
                kept.append("")
            continue
        if _is_other_resume_section_heading(line):
            if seen_education_fact:
                break
            continue
        if _looks_like_skill_catalog_line(line) or _looks_like_employment_start(line):
            break
        content = _education_content_from_line(raw)
        if content:
            kept.append(content)
            seen_education_fact = True
            continue
        if _looks_like_duty_or_project_line(line):
            if seen_education_fact:
                break
            continue
        if seen_education_fact and not _is_education_continuation(line):
            break
        kept.append(line)
    return "\n".join(kept).strip()


def _is_other_resume_section_heading(heading: str) -> bool:
    heading = _normalize_education_line(heading)
    if not heading or _EDUCATION_HEADING.search(heading):
        return False
    if _DEGREE_LINE.search(heading) or _UNIVERSITY_LINE.search(heading):
        return False
    return bool(
        _EXPERIENCE_HEADING.search(heading)
        or _PROJECT_HEADING.search(heading)
        or _CERT_HEADING.search(heading)
        or _is_resume_section_heading(heading)
    )


def _is_education_noise_line(line: str) -> bool:
    if not line:
        return True
    if _EDUCATION_HEADING.fullmatch(line) or _EDU_TABLE_HEADER.fullmatch(line):
        return True
    if _looks_like_duty_or_project_line(line):
        return True
    if _looks_like_skill_catalog_line(line) or _looks_like_employment_start(line):
        return True
    if _DEGREE_LINE.search(line) or _UNIVERSITY_LINE.search(line) or _SCORE_LINE.search(line):
        return False
    if _is_other_resume_section_heading(line):
        return True
    return False


def _education_signals(line: str) -> dict[str, bool]:
    return {
        "degree": bool(_DEGREE_LINE.search(line)),
        "institution": bool(_UNIVERSITY_LINE.search(line)),
        "score": bool(_SCORE_LINE.search(line)),
        "year": bool(_EDU_YEAR.search(line)),
    }


def _is_education_cluster(cluster: list[str], *, require_degree: bool) -> bool:
    kept = [line for line in cluster if not _looks_like_duty_or_project_line(line)]
    compact = " ".join(kept)
    if not compact.strip():
        return False
    if re.search(r"\bto be\b", compact, re.I) and not _DEGREE_LINE.search(compact):
        return False
    signals = _education_signals(compact)
    if signals["degree"]:
        return True
    if signals["institution"] and (signals["score"] or signals["year"] or not require_degree):
        return True
    return False


def _is_education_continuation(line: str) -> bool:
    if (
        _looks_like_duty_or_project_line(line)
        or _is_other_resume_section_heading(line)
        or _looks_like_skill_catalog_line(line)
        or _looks_like_employment_start(line)
    ):
        return False
    signals = _education_signals(line)
    if signals["degree"] or signals["institution"] or signals["score"] or signals["year"]:
        return True
    if line.endswith("."):
        return False
    return 1 <= len(line.split()) <= 8


def _cluster_education_lines(lines: list[str]) -> list[list[str]]:
    clusters: list[list[str]] = []
    current: list[str] = []
    current_has_degree = False

    def _flush() -> None:
        nonlocal current, current_has_degree
        if current:
            clusters.append(current)
        current = []
        current_has_degree = False

    for raw in lines:
        line = _education_content_from_line(raw)
        if not line:
            line = _normalize_education_line(raw)
        if not line:
            _flush()
            continue
        if _is_other_resume_section_heading(line):
            _flush()
            break
        if (
            _is_education_noise_line(line)
            or _looks_like_duty_or_project_line(line)
            or _looks_like_skill_catalog_line(line)
            or _looks_like_employment_start(line)
        ):
            _flush()
            continue
        signals = _education_signals(line)
        if current and signals["degree"] and current_has_degree:
            _flush()
        if current and not signals["degree"] and not _is_education_continuation(line):
            _flush()
            if not _is_education_continuation(line):
                continue
        current.append(line)
        current_has_degree = current_has_degree or signals["degree"]
    _flush()
    return clusters


def _format_education_cluster(cluster: list[str]) -> str:
    parts = [
        _normalize_education_line(line)
        for line in cluster
        if _normalize_education_line(line) and not _looks_like_duty_or_project_line(line)
    ]
    return " | ".join(part for part in parts if part)


def _education_text_from_row(row: dict[str, Any]) -> str:
    text = str(row.get("text") or "")
    extra_lines = flatten_section_items(row.get("items"))
    extra = "\n".join(extra_lines)
    if extra and extra.casefold() not in text.casefold():
        return f"{text}\n{extra}".strip()
    return text.strip()


def _education_blocks_from_source(source_text: str) -> list[str]:
    if not source_text.strip():
        return []
    blocks: list[str] = []
    sections = detect_sections(source_text)
    index = 0
    while index < len(sections):
        heading = str(sections[index].get("heading") or "")
        body = str(sections[index].get("body") or "")
        if not _EDUCATION_HEADING.search(heading):
            index += 1
            continue
        if _DEGREE_LINE.search(body) or _UNIVERSITY_LINE.search(body):
            block = _clip_education_span(body)
            if block:
                blocks.append(block)
            index += 1
            continue
        parts = [body]
        cursor = index + 1
        while cursor < len(sections):
            next_heading = str(sections[cursor].get("heading") or "")
            next_body = str(sections[cursor].get("body") or "")
            peeled = _clip_education_span(next_body)
            if not _DEGREE_LINE.search(peeled):
                peeled = _clip_education_span(f"{next_heading}\n{next_body}")
            if _DEGREE_LINE.search(peeled):
                parts.append(peeled)
                break
            if _is_other_resume_section_heading(next_heading):
                break
            cursor += 1
        block = _clip_education_span("\n".join(part for part in parts if str(part).strip()))
        if block:
            blocks.append(block)
        index = max(cursor, index + 1)
    return blocks


def _entries_from_education_text(text: str, *, require_degree: bool) -> list[str]:
    entries: list[str] = []
    for cluster in _cluster_education_lines(_clip_education_span(text).splitlines()):
        if not _is_education_cluster(cluster, require_degree=require_degree):
            continue
        formatted = _format_education_cluster(cluster)
        if formatted:
            entries.append(formatted)
    return entries


def _collapse_education_entries(entries: list[str]) -> list[str]:
    unique = [
        item
        for item in dedupe_preserve(entries)
        if _DEGREE_LINE.search(item) or _UNIVERSITY_LINE.search(item)
    ]
    kept: list[str] = []
    for item in sorted(unique, key=len, reverse=True):
        folded = item.casefold()
        if any(folded in other.casefold() and item != other for other in kept):
            continue
        kept.append(item)
    order = {item: index for index, item in enumerate(unique)}
    return sorted(kept, key=lambda item: order.get(item, 0))


def _line_looks_like_job_not_education(line: str, nearby: str) -> bool:
    """Skip employment rows that mention 'engineer' but are not degrees."""
    if _DEGREE_LINE.search(line) or _UNIVERSITY_LINE.search(line):
        return False
    remainder = _DEGREE_LINE.sub(" ", nearby)
    return bool(_ROLE_WORDS.search(remainder) and _line_has_date_range(nearby))


def _scan_education_from_full_text(text: str) -> list[str]:
    lines = [_normalize_education_line(line) for line in str(text or "").splitlines()]
    entries: list[str] = []
    used: set[int] = set()
    for index, line in enumerate(lines):
        if not line or index in used or not _DEGREE_LINE.search(line):
            continue
        nearby = " ".join(lines[max(0, index - 1) : min(len(lines), index + 3)])
        if _line_looks_like_job_not_education(line, nearby):
            continue
        start = index
        end = index + 1
        for back in range(1, 4):
            previous = index - back
            if previous < 0 or not lines[previous]:
                break
            if _is_education_noise_line(lines[previous]):
                break
            previous_signals = _education_signals(lines[previous])
            if previous_signals["institution"] or previous_signals["score"]:
                start = previous
        for forward in range(1, 5):
            nxt = index + forward
            if nxt >= len(lines) or not lines[nxt]:
                break
            if _DEGREE_LINE.search(lines[nxt]):
                break
            if _is_education_noise_line(lines[nxt]):
                break
            signals = _education_signals(lines[nxt])
            if signals["institution"] or signals["score"] or signals["year"] or len(lines[nxt].split()) <= 8:
                end = nxt + 1
                continue
            break
        cluster = [lines[cursor] for cursor in range(start, end) if lines[cursor]]
        used.update(range(start, end))
        if _is_education_cluster(cluster, require_degree=True):
            formatted = _format_education_cluster(cluster)
            if formatted:
                entries.append(formatted)
    return entries


def _extract_education(
    rows: list[dict[str, Any]],
    *texts: str,
) -> list[str]:
    heading_entries: list[str] = []
    for index, row in enumerate(rows):
        heading = str(row.get("heading") or "")
        body = _education_text_from_row(row)
        if not _EDUCATION_HEADING.search(heading):
            continue
        entries = _entries_from_education_text(body, require_degree=True)
        if not entries or not any(_DEGREE_LINE.search(item) for item in entries):
            following = "\n".join(
                _education_text_from_row(later)
                for later in rows[index + 1 :]
                if not _EDUCATION_HEADING.search(str(later.get("heading") or ""))
            )
            entries = _entries_from_education_text(following, require_degree=True)
        heading_entries.extend(entries)

    source_text = next((str(part) for part in reversed(texts) if str(part).strip()), "")
    source_entries: list[str] = []
    for block in _education_blocks_from_source(source_text):
        source_entries.extend(_entries_from_education_text(block, require_degree=True))

    heading_based = _collapse_education_entries(heading_entries + source_entries)
    if heading_based:
        return heading_based

    fallback_entries: list[str] = []
    for row in rows:
        heading = str(row.get("heading") or "")
        body = _education_text_from_row(row)
        if _DEGREE_LINE.search(heading) or _UNIVERSITY_LINE.search(heading):
            fallback_entries.extend(
                _entries_from_education_text(
                    f"{heading}\n{body}".strip(),
                    require_degree=True,
                )
            )

    full_text = "\n".join(part for part in texts if str(part).strip())
    return _collapse_education_entries(
        fallback_entries + _scan_education_from_full_text(full_text)
    )


def build_candidate_profile(
    parsed_resume: dict[str, Any],
    resume_filename: str = "",
) -> CandidateProfile:
    rows = _section_rows(
        parsed_resume
    )

    if not rows:
        raise ValueError(
            "Parsed resume contains no sections."
        )

    plain_full_text = "\n\n".join(
        str(
            row["text"]
        )
        for row in rows
        if row["text"]
    ).strip()

    if not plain_full_text:
        raise ValueError(
            "Parsed resume contains no readable text."
        )

    marked_full_text = "\n\n".join(
        f"===SECTION:{row['heading']}===\n"
        f"{row['text']}"
        for row in rows
        if row["text"]
    ).strip()

    experience_entries = (
        _extract_experience_entries(
            rows,
            str(parsed_resume.get("source_text", "") or "") or plain_full_text,
        )
    )

    total_experience = (
        _total_experience(
            experience_entries
        )
    )

    education = _extract_education(
        rows,
        plain_full_text,
        str(parsed_resume.get("source_text", "") or ""),
    )

    certifications = dedupe_preserve(
        [
            line.strip(
                " •*-–—"
            )
            for row in rows
            if _CERT_HEADING.search(
                str(
                    row["heading"]
                )
            )
            for line
            in str(
                row["text"]
            ).splitlines()
            if line.strip()
        ]
    )

    warnings: list[str] = []

    if total_experience is None:
        warnings.append(
            "Total work experience could not be verified "
            "from individual resume roles and dates."
        )

    if not experience_entries:
        warnings.append(
            "No separate employment, internship, or dated "
            "project entries were identified."
        )

    if not education:
        warnings.append(
            "Candidate education could not be identified "
            "from the parsed resume."
        )

    return CandidateProfile(
        candidate_details=_candidate_details(
            rows,
            parsed_resume,
            resume_filename=resume_filename,
        ),
        skills=extract_resume_skills(
            parsed_resume
        ),
        total_experience_years=total_experience,
        experience_entries=experience_entries,
        education=education,
        certifications=certifications,
        keywords=extract_keywords(
            plain_full_text
        ),
        current_location=_extract_location_and_notice(plain_full_text)[0],
        notice_period_days=_extract_location_and_notice(plain_full_text)[1],
        domain_signals=list(
            extract_resume_skills(parsed_resume).skills_by_category.get(
                "domain_skills", []
            )
        ),
        source_text=marked_full_text,
        warnings=warnings,
    )