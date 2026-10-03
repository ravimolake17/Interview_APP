"""
section_detector.py
─────────────────────────────────────────────────────────────
Heuristic, format-agnostic resume section splitter.

This module does NOT try to understand resume content semantically —
that's the AI parser's job. Instead it provides a deterministic,
zero-dependency safety net that guarantees no part of the resume is
ever silently dropped:

1. It splits the raw resume text into an ordered list of
   {heading, body} blocks using layout/typography heuristics
   (ALL CAPS lines, Title Case short lines, common separators, etc).
2. The detected heading list is fed into the AI prompt so the model
   has an explicit checklist of every section it must account for.
3. After the AI responds, the route layer cross-checks the AI output
   against this detected list. Any heading the AI didn't map to a
   known field or to `additional_sections` is appended automatically
   as a raw-text fallback section — so even if the LLM misses or
   mislabels something, it still ends up in the final response.
4. If the AI call fails entirely, this detector is the backbone of
   the rule-based fallback parser (see resume_parser.py).
"""

import html
import re
from typing import Any


# A line is a plausible heading if it's short, not a sentence, and
# visually distinct (ALL CAPS, Title Case, or ends without punctuation).
_HEADING_MAX_WORDS = 6
_HEADING_MAX_CHARS = 45

# Common bullet / artifact characters to strip
_BULLET_CHARS = "•●▪◦‣·-–—*►➤❖"

_KNOWN_HEADING_HINTS = re.compile(
    r"^(summary|profile|objective|about( me)?|career objective|"
    r"education|academic[s]?|qualification[s]?|"
    r"experience|work experience|professional experience|employment( history)?|internship[s]?|"
    r"industrial training|apprenticeship|freelance|consulting|research experience|"
    r"project[s]?|academic project[s]?|personal project[s]?|"
    r"(?:[\w.&/'#-]+\s+){1,4}projects?|"
    r"skill[s]?|technical skill[s]?|soft skill[s]?|"
    r"core competenc(y|ies)|key competenc(y|ies)|competenc(y|ies)|highlights?|technical summary|"
    r"certification[s]?|licen[cs]e[s]?|"
    r"publication[s]?|research|patent[s]?|"
    r"award[s]?|achievement[s]?|honou?r[s]?|"
    r"conference[s]?|workshop[s]?|training[s]?|"
    r"volunteer(ing)?( experience)?|community service|"
    r"leadership( experience)?|extra[- ]?curricular( activit(y|ies))?|"
    r"open source( contributions)?|hackathon[s]?|competition[s]?|"
    r"language[s]?|interest[s]?|hobb(y|ies)|"
    r"reference[s]?|portfolio|contact( information)?|social( links| profiles)?|"
    r"membership[s]?|affiliation[s]?|military( service)?|declaration|"
    r"personal details|strength[s]?|additional information)\s*:?$",
    re.IGNORECASE,
)

_ROLE_OR_ENTRY_LINE = re.compile(
    r"\b(developer|engineer|scientist|analyst|manager|consultant|intern|specialist|"
    r"architect|administrator|officer|associate|executive|director|lead|founder|student)\b",
    re.IGNORECASE,
)
_GENERIC_TITLE_HEADING = re.compile(
    r"^(?:(?:additional|professional|technical|core|key|relevant|selected|other)\s+)?"
    r"(?:overview|coursework|activities|contributions|accomplishments|credentials|"
    r"technologies|tools|interests|associations|seminars|capabilities|competencies)$",
    re.IGNORECASE,
)

# Docling converts some DOCX table-based resumes into a Markdown table where
# every paragraph in a cell is collapsed onto one line. Recover explicit
# headings from those cells before applying the normal line-based detector.
_INLINE_HEADING_NAMES = (
    "Professional Experience",
    "Work Experience",
    "Employment History",
    "Contact Information",
    "Technical Skills",
    "Soft Skills",
    "Core Competencies",
    "Key Competencies",
    "Competencies",
    "Career Objective",
    "Personal Details",
    "Additional Information",
    "Open Source Contributions",
    "Volunteer Experience",
    "Education",
    "Qualifications",
    "Experience",
    "Internships",
    "Internship",
    "Projects",
    "Skills",
    "Certifications",
    "Certification",
    "Licenses",
    "License",
    "Publications",
    "Research",
    "Patents",
    "Awards",
    "Achievements",
    "Training",
    "Languages",
    "Interests",
    "Hobbies",
    "References",
    "Portfolio",
    "Summary",
    "Profile",
    "Objective",
)
_INLINE_HEADING_RE = re.compile(
    r"(?<![A-Za-z])("
    + "|".join(
        re.escape(value)
        for value in sorted(_INLINE_HEADING_NAMES, key=len, reverse=True)
    )
    + r")(?:\s*:)?(?=\s|$)",
    re.IGNORECASE,
)
_MARKDOWN_TABLE_SEPARATOR_RE = re.compile(
    r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$"
)


def _split_collapsed_table_cell(cell: str) -> list[str]:
    """Expand one Docling Markdown table cell into heading/body lines."""
    text = re.sub(r"\s+", " ", html.unescape(cell)).strip()
    if not text:
        return []

    matches = []
    for match in _INLINE_HEADING_RE.finditer(text):
        token = match.group(1)
        # Avoid splitting ordinary prose such as "relevant experience".
        if (
            match.start() == 0
            or token.isupper()
            or text[match.start() : match.end()].endswith(":")
        ):
            matches.append(match)

    if not matches:
        return [text]

    output: list[str] = []
    prefix = text[: matches[0].start()].strip(" |")
    if prefix:
        output.append(prefix)

    for index, match in enumerate(matches):
        output.append(match.group(1).strip())
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip(" |")
        if body:
            # Restore bullets that Word/Docling collapsed onto the same row.
            body = re.sub(r"\s+([•●▪◦‣►➤❖])\s*", r"\n\1 ", body)
            output.extend(part.strip() for part in body.splitlines() if part.strip())

    return output


def _prepare_detection_text(text: str) -> str:
    """Normalize layout artifacts only for section-boundary detection."""
    expanded: list[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if _MARKDOWN_TABLE_SEPARATOR_RE.fullmatch(raw_line):
            continue

        stripped = raw_line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            # Split before HTML entity decoding so encoded pipes inside a cell
            # (for example a role | company | date line) remain cell content.
            cells = [cell.strip() for cell in stripped[1:-1].split("|")]
            for cell in cells:
                expanded.extend(_split_collapsed_table_cell(cell))
            continue

        expanded.append(html.unescape(raw_line))

    return "\n".join(expanded)


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip(" :\t")
    if not stripped or len(stripped) > _HEADING_MAX_CHARS:
        return False

    words = stripped.split()
    if len(words) == 0 or len(words) > _HEADING_MAX_WORDS:
        return False

    # Explicit match against known resume vocabulary (cheap, high precision)
    if _KNOWN_HEADING_HINTS.match(stripped):
        return True

    # No sentence punctuation in the middle, no trailing period
    if re.search(r"[.,;]$", stripped):
        return False

    # Avoid treating role titles, dates, links, skill lists, and score rows as headings.
    if _ROLE_OR_ENTRY_LINE.search(stripped):
        return False
    if re.search(r"@|https?://|\d{4}|[,|/]", stripped):
        return False
    if re.search(
        r"(?:cgpa|gpa|sgpa|sgpi|spi|cpi|percentage|marks?)\s*[:\-]?\s*\d",
        stripped,
        re.I,
    ):
        return False

    # ALL CAPS remains a strong visual heading signal, except for short
    # one-token technology acronyms such as SQL, AWS, NLP, HTML, or JAVA.
    letters = [c for c in stripped if c.isalpha()]
    if letters and all(c.isupper() for c in letters) and len(letters) >= 3:
        if len(words) == 1 and len(letters) <= 4:
            return False
        return True

    # Unknown Title Case headings are accepted only when they contain a
    # section-like noun. This avoids classifying company names/job titles.
    if (
        stripped[0].isupper()
        and len(words) <= 4
        and _GENERIC_TITLE_HEADING.fullmatch(stripped)
    ):
        cap_words = sum(1 for word in words if word[0].isupper())
        return cap_words >= max(1, len(words) - 1)

    return False


def _is_known_section_heading(heading: str) -> bool:
    """True for standard resume section titles (Education, Experience, …)."""
    clean = re.sub(r"^#+\s*", "", str(heading or "")).strip().rstrip(":").strip()
    if not clean or clean.casefold() == "header":
        return False
    return bool(_KNOWN_HEADING_HINTS.match(clean))


def _looks_like_orphan_content_heading(heading: str) -> bool:
    """
    True when a 'heading' is actually body text that was split onto the next
    page after a real section title (e.g. degree line after EDUCATION).
    """
    clean = re.sub(r"^#+\s*", "", str(heading or "")).strip().rstrip(":").strip()
    if not clean or _is_known_section_heading(clean):
        return False
    # Degree / school / date-bearing lines are content, not section titles.
    if re.search(
        r"\b(?:bachelor|master|ph\.?d|b\.?tech|m\.?tech|mca|bca|mba|"
        r"diploma|university|college|school|cgpa|gpa|percentage)\b",
        clean,
        re.I,
    ):
        return True
    if re.search(r"\d{4}", clean):
        return True
    if len(clean) > _HEADING_MAX_CHARS:
        return True
    return False


def _repair_page_break_orphans(
    sections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Re-attach body text that landed after an empty known heading.

    PDF/Docling page breaks often yield:
        EDUCATION          ← end of page 1 (empty body)
        Bachelor of …      ← start of page 2 (mis-labeled as its own section)

    Without this repair, education (and similar sections) appear missing.
    """
    if not sections:
        return sections

    repaired: list[dict[str, Any]] = []
    index = 0
    while index < len(sections):
        current = {
            "heading": sections[index]["heading"],
            "body": str(sections[index].get("body") or "").strip(),
        }
        heading = current["heading"]
        body = current["body"]

        if _is_known_section_heading(heading) and not body:
            absorbed: list[str] = []
            cursor = index + 1
            while cursor < len(sections):
                nxt = sections[cursor]
                nxt_heading = str(nxt.get("heading") or "").strip()
                nxt_body = str(nxt.get("body") or "").strip()

                if _is_known_section_heading(nxt_heading):
                    break

                # Content mistakenly promoted to a heading after a page break.
                if nxt_heading and nxt_heading.casefold() != "header":
                    if _looks_like_orphan_content_heading(nxt_heading) or not _looks_like_heading(
                        nxt_heading.lstrip(_BULLET_CHARS + " ").strip()
                    ):
                        absorbed.append(nxt_heading)
                    elif nxt_heading:
                        # Ambiguous — still absorb into the empty known section
                        # rather than leaving the known section empty.
                        absorbed.append(nxt_heading)

                if nxt_body:
                    absorbed.append(nxt_body)

                cursor += 1

            if absorbed:
                current["body"] = "\n".join(absorbed).strip()
                repaired.append(current)
                index = cursor
                continue

        repaired.append(current)
        index += 1

    return repaired


def detect_sections(text: str) -> list[dict[str, Any]]:
    """
    Split resume text into an ordered list of sections.

    Returns:
        [{"heading": str, "body": str}, ...]
        The first block (before any detected heading) is returned with
        heading="Header" and typically holds name/contact info.
    """
    # Normalize page-break control characters so body lines after a heading
    # remain in the same stream (common PDF → text artifact).
    normalized = (
        str(text or "")
        .replace("\f", "\n")
        .replace("\x0c", "\n")
    )
    lines = _prepare_detection_text(normalized).split("\n")
    sections: list[dict[str, Any]] = []

    current_heading = "Header"
    current_body: list[str] = []
    seen_first_nonempty_line = False

    for raw_line in lines:
        line = raw_line.strip()
        clean = line.lstrip(_BULLET_CHARS + " ").strip()
        # Ignore solitary page numbers between a heading and its body.
        if re.fullmatch(r"\d{1,3}", clean):
            continue

        is_first_line = bool(clean) and not seen_first_nonempty_line
        if clean:
            seen_first_nonempty_line = True

        # The very first line of a resume is almost always the candidate's
        # name, not a section heading — unless it explicitly matches known
        # resume vocabulary (rare, but possible for unusually formatted docs).
        if is_first_line and not _KNOWN_HEADING_HINTS.match(clean):
            current_body.append(line)
            continue

        if _looks_like_heading(clean):
            # Flush previous section
            if current_body or sections:
                sections.append(
                    {
                        "heading": current_heading,
                        "body": "\n".join(current_body).strip(),
                    }
                )
            current_heading = clean.rstrip(":").strip()
            current_body = []
        else:
            if line:
                current_body.append(line)

    sections.append(
        {"heading": current_heading, "body": "\n".join(current_body).strip()}
    )

    # Drop completely empty header-only stubs; keep other empty known headings
    # so page-break repair can still attach following content.
    sections = [s for s in sections if s["body"] or s["heading"] != "Header"]
    return _repair_page_break_orphans(sections)


def normalize_heading(heading: str) -> str:
    """Lowercase, strip punctuation/whitespace — used for fuzzy de-duplication."""
    return re.sub(r"[^a-z0-9]+", "", heading.lower())


def build_segmented_text(sections: list[dict[str, Any]]) -> str:
    """
    Render detected sections into an explicitly boundary-marked block of
    text for the LLM prompt:

        ===SECTION_START: "EDUCATION" (#1)===
        ...body...
        ===SECTION_END (#1)===

    Giving the model hard, unambiguous boundaries is the single biggest
    lever against cross-section data bleeding (e.g. an Experience bullet
    getting attributed to Projects, or a Skills entry leaking into
    Certifications) — far more reliable than asking it to infer
    boundaries from raw, unmarked text alone.
    """
    parts: list[str] = []
    for i, sec in enumerate(sections, start=1):
        heading = sec["heading"]
        body = sec["body"]
        # Keep known headings even when body is temporarily empty so the LLM
        # (and rule fallback) still see the section boundary after page breaks.
        if not body and not _is_known_section_heading(heading):
            continue
        label = "HEADER / CONTACT BLOCK" if heading == "Header" else heading
        parts.append(f'===SECTION_START: "{label}" (#{i})===')
        parts.append(body if body else "[section continues after page break]")
        parts.append(f"===SECTION_END (#{i})===")
    return "\n".join(parts)


# ──────────────────────────────────────────────
# Content-type classification + structured item extraction
# Used both by the rule-based fallback and as a hint surface for the AI,
# so dynamic sections aren't just opaque blobs of raw text — wherever the
# shape is mechanically obvious (a bullet list, a "Key: Value" block, a
# pipe-delimited table row), we extract it without needing a fixed schema
# for *what kind* of section it is.
# ──────────────────────────────────────────────

_BULLET_LINE = re.compile(r"^\s*[•●▪◦‣·\-–—*►➤❖]\s*")
_KEY_VALUE_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 /&]{1,40}?)\s*:\s+(.+)$")


def classify_section(body: str) -> dict[str, Any]:
    """
    Heuristically classify a section's body and extract structured items.

    Returns:
        {"content_type": "list" | "table" | "key_value" | "text", "items": [...]}
    """
    if not body.strip():
        return {"content_type": "text", "items": []}

    lines = [ln for ln in body.split("\n") if ln.strip()]
    if not lines:
        return {"content_type": "text", "items": []}

    bullet_lines = sum(1 for ln in lines if _BULLET_LINE.match(ln))
    table_lines = sum(1 for ln in lines if " | " in ln or ln.count("|") >= 2)
    kv_lines = sum(1 for ln in lines if _KEY_VALUE_LINE.match(ln.strip()))

    total = len(lines)

    if table_lines and table_lines / total >= 0.5:
        items = [
            [cell.strip() for cell in re.split(r"\s*\|\s*", ln.strip()) if cell.strip()]
            for ln in lines
            if "|" in ln
        ]
        return {"content_type": "table", "items": items}

    if bullet_lines and bullet_lines / total >= 0.4:
        items = [_BULLET_LINE.sub("", ln).strip() for ln in lines]
        return {"content_type": "list", "items": [i for i in items if i]}

    if kv_lines and kv_lines / total >= 0.5:
        items = []
        for ln in lines:
            m = _KEY_VALUE_LINE.match(ln.strip())
            if m:
                items.append({"key": m.group(1).strip(), "value": m.group(2).strip()})
            else:
                items.append({"key": "", "value": ln.strip()})
        return {"content_type": "key_value", "items": items}

    return {"content_type": "text", "items": []}
