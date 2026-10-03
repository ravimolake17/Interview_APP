"""
resume_parser.py
─────────────────────────────────────────────────────────────
Rule-based fallback parser — fully dynamic, no fixed schema.

Used when the AI (Groq) call fails, times out, or returns invalid
JSON. The output shape is identical in spirit to the AI path: an
ordered list of sections discovered from the document itself, each
carrying its original (or inferred) heading and complete verbatim
content. There are no hardcoded top-level fields like "education" or
"experience" — every resume produces whatever sections it actually
contains.

Contact recovery (name / email / phone) and experience recovery are
best-effort enrichments so scoring still has usable fields when Groq
is unavailable.
"""

from __future__ import annotations

import re
from urllib.parse import unquote

from agents.screening_agent.services.section_detector import classify_section, detect_sections
from agents.screening_agent.utils.skill_normalizer import find_known_skills

EMAIL_REGEX = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
_EMAIL_RE = re.compile(EMAIL_REGEX)
PHONE_REGEX = r"(?:\+91[- ]?)?[6-9]\d{9}|\+?\d[\d\s\-()]{8,15}"
URL_REGEX = r"(?:https?://)?(?:www\.)?[a-zA-Z0-9.-]+\.[A-Za-z]{2,}(?:/\S*)?"
_MAILTO_RE = re.compile(r"mailto:([^\s>'\"<>]+)", re.I)
_MD_MAILTO_RE = re.compile(r"\[([^\]]+)\]\(\s*mailto:([^)\s]+)\s*\)", re.I)
_SPACED_EMAIL_RE = re.compile(
    r"([A-Za-z0-9._%+-]+)\s*@\s*([A-Za-z0-9.-]+)\s*\.\s*([A-Za-z]{2,})"
)
_OBFUSCATED_EMAIL_RE = re.compile(
    r"([A-Za-z0-9._%+-]+)\s*(?:\[at\]|\(at\)|\{at\})\s*"
    r"([A-Za-z0-9.-]+)\s*(?:\[dot\]|\(dot\)|\{dot\}|\.)\s*([A-Za-z]{2,})",
    re.I,
)
_EXPERIENCE_HEADING = re.compile(
    r"experience|employment|work history|internship|professional background",
    re.I,
)
_DATE_RANGE_RE = re.compile(
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?|[01]?\d[/-]\d{4}|20\d{2})"
    r".{0,24}(?:-|–|—|to|till|until)\s*"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?|present|current|now|till\s*date|20\d{2}|[01]?\d[/-]\d{4})",
    re.I,
)
_ROLE_RE = re.compile(
    r"developer|engineer|analyst|scientist|architect|consultant|manager|"
    r"executive|specialist|associate|intern|trainee|administrator|officer|"
    r"coordinator|designer|tester|founder|lead\b|director",
    re.I,
)
_JUNK_NAME_RE = re.compile(
    r"^(?:curriculum\s+vitae|curriculum vitae|resume|cv|bio-?data|"
    r"contact(?: information)?|personal details|"
    r"summary|profile|objective|education|experience|"
    r"(?:key |core )?competenc(?:y|ies)|highlights?)$",
    re.I,
)
_HEADING_TAIL_RE = re.compile(
    r"\b(?:summary|profile|objective|education|experience|employment|"
    r"projects?|skills?|certifications?|achievements?|qualifications?)$",
    re.I,
)
_ORG_OR_SCHOOL_RE = re.compile(
    r"\b(?:"
    r"university|college|institute|polytechnic|academy|"
    r"vidyalaya|vidyapeeth|campus|faculty|department|"
    r"high\s+school|secondary\s+school|"
    r"ltd\.?|limited|pvt\.?|private|inc\.?|llp|"
    r"corp\.?|corporation|technologies|solutions|services|"
    r"systems|company|group|industries|consulting"
    r")\b",
    re.I,
)
_NAME_LABEL_RE = re.compile(
    r"(?:^|\n)\s*(?:candidate\s+)?name\s*:\s*(.+)$",
    re.I | re.M,
)


def extract_emails_from_text(text: str) -> list[str]:
    """Collect emails from plaintext, mailto links, and obfuscated forms."""
    if not text:
        return []

    found: list[str] = []
    seen: set[str] = set()

    def _add(raw: str) -> None:
        cleaned = unquote(raw).strip().strip(".,;:<>()[]{}").replace(" ", "")
        if cleaned.startswith("mailto:"):
            cleaned = cleaned[7:]
        if not _EMAIL_RE.fullmatch(cleaned):
            return
        key = cleaned.casefold()
        if key in seen:
            return
        seen.add(key)
        found.append(cleaned)

    for match in _MD_MAILTO_RE.finditer(text):
        _add(match.group(2))
    for match in _MAILTO_RE.finditer(text):
        _add(match.group(1))
    for match in _OBFUSCATED_EMAIL_RE.finditer(text):
        _add(f"{match.group(1)}@{match.group(2)}.{match.group(3)}")
    for match in _SPACED_EMAIL_RE.finditer(text):
        _add(f"{match.group(1)}@{match.group(2)}.{match.group(3)}")
    for match in _EMAIL_RE.findall(text):
        _add(match)

    return found


def guess_candidate_name(text: str) -> str:
    """Best-effort name from the resume lead, skipping CV/title lines."""
    if not text.strip():
        return ""

    labelled = _NAME_LABEL_RE.search(text)
    if labelled:
        candidate = _clean_name_line(labelled.group(1))
        if candidate:
            return candidate

    md_mailto = _MD_MAILTO_RE.search(text)
    if md_mailto:
        candidate = _clean_name_line(md_mailto.group(1))
        if candidate:
            return candidate

    for line in text.splitlines()[:40]:
        stripped = re.sub(r"^#+\s*", "", line).strip()
        if not stripped:
            continue
        if _JUNK_NAME_RE.fullmatch(stripped.strip(" •*|:-")):
            continue
        candidate = _clean_name_line(stripped)
        if candidate:
            return candidate
    return ""


def _clean_name_line(line: str) -> str:
    value = re.sub(r"^#+\s*", "", line).strip(" •*|,:-–—")
    value = re.sub(r"\s+", " ", value).strip()
    if " | " in value:
        value = value.split(" | ", 1)[0].strip()
    if not value or _JUNK_NAME_RE.fullmatch(value):
        return ""
    if 2 <= len(value.split()) <= 6 and _HEADING_TAIL_RE.search(value):
        return ""
    if _EMAIL_RE.search(value) or re.search(r"https?://|www\.|linkedin\.com", value, re.I):
        return ""
    if re.search(r"\d", value):
        return ""
    if _ROLE_RE.search(value) or _ORG_OR_SCHOOL_RE.search(value):
        return ""
    compact = re.sub(r"[^a-z0-9+#]+", "", value.casefold())
    for match in find_known_skills(value):
        skill = str(match.get("normalized") or "")
        if re.sub(r"[^a-z0-9+#]+", "", skill.casefold()) == compact:
            return ""
    if len(value.split()) < 2:
        return ""
    if len(value) > 80 or not 1 <= len(value.split()) <= 6:
        return ""
    if not any(character.isalpha() for character in value):
        return ""
    if any(not (character.isalpha() or character in " .'-") for character in value):
        return ""
    return value


def _extract_contact_hints(text: str) -> dict:
    """
    Best-effort contact detail extraction used only to enrich the Header
    section's structured `items`, not to replace it — the verbatim
    raw_text of the header is always preserved regardless.
    """
    emails = extract_emails_from_text(text)
    return {
        "emails": emails,
        "phones": sorted(set(re.findall(PHONE_REGEX, text))),
        "links": sorted(set(re.findall(URL_REGEX, text))),
        "name": guess_candidate_name(text),
    }


def _section_id(heading: str, index: int, used: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", heading.lower()).strip("_") or f"section_{index}"
    candidate = base
    n = 2
    while candidate in used:
        candidate = f"{base}_{n}"
        n += 1
    used.add(candidate)
    return candidate


def _is_other_section_heading(line: str) -> bool:
    return bool(
        re.fullmatch(
            r"(?:education|skills?|projects?|certifications?|summary|objective|profile)\s*:?",
            line.strip(),
            re.I,
        )
    )


def _is_skill_list_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or _ROLE_RE.search(stripped) or _DATE_RANGE_RE.search(stripped):
        return False
    parts = [part.strip() for part in re.split(r"[,|/]", stripped) if part.strip()]
    return len(parts) >= 2 and all(len(part.split()) <= 3 for part in parts)


def _recover_experience_text(text: str) -> str:
    """Recover dated job blocks when Docling dropped the Experience heading."""
    lines = [line.rstrip() for line in text.splitlines()]
    used: set[int] = set()
    blocks: list[str] = []

    for index, line in enumerate(lines):
        if index in used or not _DATE_RANGE_RE.search(line):
            continue
        nearby = "\n".join(lines[max(0, index - 3) : min(len(lines), index + 4)])
        if not _ROLE_RE.search(nearby):
            continue

        start = index
        for back in range(1, 4):
            previous = index - back
            if previous < 0:
                break
            previous_line = lines[previous].strip()
            if not previous_line:
                continue
            if _is_other_section_heading(previous_line) or _is_skill_list_line(previous_line):
                break
            if _ROLE_RE.search(previous_line):
                start = previous
                break

        end = min(len(lines), index + 4)
        for cursor in range(index + 1, end):
            if _is_other_section_heading(lines[cursor]):
                end = cursor
                break

        for cursor in range(start, end):
            used.add(cursor)
        block = "\n".join(lines[start:end]).strip()
        if block:
            blocks.append(block)
    return "\n\n".join(blocks).strip()


def _header_items(contacts: dict, existing: list) -> list:
    items: list = []
    name = str(contacts.get("name") or "").strip()
    if name:
        items.append({"key": "Name", "value": name})
    for email in contacts.get("emails") or []:
        items.append({"key": "Email", "value": email})
    for phone in contacts.get("phones") or []:
        items.append({"key": "Phone", "value": phone})
    if items:
        return items
    return existing if isinstance(existing, list) else []


def parse_resume(text: str) -> dict:
    """
    Fully dynamic rule-based fallback. Splits the resume into sections
    purely from its own structure (via section_detector) and emits each
    one verbatim, with best-effort content-type classification. Nothing
    is mapped onto a predefined field — the resume's own headings (or an
    inferred heading for the unlabeled leading block) drive the output.
    """
    sections = detect_sections(text)
    used_ids: set[str] = set()
    output_sections = []
    contacts = _extract_contact_hints(text)

    for order, sec in enumerate(sections):
        heading = sec["heading"]
        body = sec["body"]
        is_header = heading == "Header"

        if is_header:
            heading_out = "Contact Information"
            heading_source = "inferred"
        else:
            heading_out = heading
            heading_source = "original"

        # Preserve heading-only sections (empty body from source line-splitting)
        # rather than discarding the heading text.
        content_text = body if body else heading

        classification = classify_section(content_text)

        section_obj = {
            "section_id": _section_id(heading_out, order, used_ids),
            "heading": heading_out,
            "heading_source": heading_source,
            "order": order,
            "content_type": classification["content_type"],
            "items": classification["items"],
            "raw_text": content_text,
        }

        if is_header:
            section_obj["content_type"] = "key_value"
            section_obj["detected_contacts"] = {
                "emails": contacts["emails"],
                "phones": contacts["phones"],
                "links": contacts["links"],
            }
            section_obj["items"] = _header_items(contacts, classification["items"])

        output_sections.append(section_obj)

    has_experience = any(
        _EXPERIENCE_HEADING.search(str(section.get("heading", "")))
        for section in output_sections
    )
    experience_text = ""
    if has_experience:
        for section in output_sections:
            if _EXPERIENCE_HEADING.search(str(section.get("heading", ""))):
                experience_text += "\n" + str(section.get("raw_text", ""))
    if not _ROLE_RE.search(experience_text) or not _DATE_RANGE_RE.search(experience_text):
        recovered = _recover_experience_text(text)
        if recovered:
            if has_experience:
                for section in output_sections:
                    if not _EXPERIENCE_HEADING.search(str(section.get("heading", ""))):
                        continue
                    current = str(section.get("raw_text", "")).strip()
                    if recovered not in current:
                        merged = f"{current}\n\n{recovered}".strip() if current else recovered
                        section["raw_text"] = merged
                        section["items"] = classify_section(merged)["items"]
                    break
            else:
                classification = classify_section(recovered)
                output_sections.append(
                    {
                        "section_id": _section_id("Experience", len(output_sections), used_ids),
                        "heading": "Experience",
                        "heading_source": "inferred",
                        "order": len(output_sections),
                        "content_type": classification["content_type"],
                        "items": classification["items"],
                        "raw_text": recovered,
                    }
                )

    return {
        "sections": output_sections,
        "extraction_method": "rule_based_fallback",
    }
