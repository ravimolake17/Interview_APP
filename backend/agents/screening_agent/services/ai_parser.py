"""AI-assisted dynamic resume extraction with deterministic safeguards."""

from __future__ import annotations

import json
import logging
import re
import time
from functools import lru_cache
from typing import Any

from agents.screening_agent.config import settings
from agents.screening_agent.services.groq_queue import (
    GroqRateLimitError,
    get_groq_resume_queue,
    is_rate_limited,
)
from agents.screening_agent.services.prompt_style import prompt_style_instruction
from agents.screening_agent.schemas.resume import ParsedResume
from agents.screening_agent.services.resume_parser import parse_resume
from agents.screening_agent.services.section_detector import (
    build_segmented_text,
    classify_section,
    detect_sections,
    normalize_heading,
)

logger = logging.getLogger(__name__)
# Keep resume prompts under Groq on-demand TPM (~8000 tokens/request).
_MAX_TEXT_CHARS = 5_500
_ALLOWED_CONTENT_TYPES = {"text", "list", "key_value", "table"}
_PRIORITY_SECTION = re.compile(
    r"header|contact|summary|profile|objective|skill|"
    r"experience|employment|work history|internship|"
    r"education|qualification|project",
    re.I,
)
_EXPERIENCE_SECTION = re.compile(
    r"experience|employment|work history|internship",
    re.I,
)
_EDUCATION_SECTION = re.compile(r"education|qualification", re.I)
_SKILL_SECTION = re.compile(r"skill", re.I)

SYSTEM_PROMPT = """You are a resume DATA EXTRACTOR. Return all resume content as valid JSON only.
Walk top to bottom. Preserve section headings, order, and complete raw text. Never invent,
summarize, or omit content. Output exactly an object with a `sections` array. Each section
must contain section_id, heading, heading_source, order, content_type, items, and raw_text.
Allowed content_type values: text, list, key_value, table. Contact sections may include
`detected_contacts` with emails, phones, and links. Section IDs must be short snake_case.
"""


@lru_cache(maxsize=1)
def _groq_client():
    if not settings.GROQ_API_KEY:
        return None
    try:
        from groq import Groq
    except ImportError:
        logger.warning("Groq package is unavailable; using rule-based resume parsing.")
        return None
    return Groq(
        api_key=settings.GROQ_API_KEY,
        timeout=settings.GROQ_TIMEOUT_SECONDS,
        max_retries=settings.GROQ_MAX_RETRIES,
    )


def _truncate(text: str, max_chars: int = _MAX_TEXT_CHARS) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    detected = detect_sections(text)
    budgets = {"head": 900, "exp": 2200, "edu": 900, "skill": 800, "other": 400}
    used = {key: 0 for key in budgets}
    selected: list[tuple[int, str, str]] = []

    for index, section in enumerate(detected):
        heading = str(section.get("heading") or "").strip()
        body = str(section.get("body") or "").strip()
        chunk = f"{heading}\n{body}".strip() if heading else body
        if not chunk:
            continue
        heading_key = heading.lstrip("# ").strip()
        if index == 0 or re.search(r"header|contact", heading_key, re.I):
            bucket = "head"
        elif _EXPERIENCE_SECTION.search(heading_key):
            bucket = "exp"
        elif _EDUCATION_SECTION.search(heading_key):
            bucket = "edu"
        elif _SKILL_SECTION.search(heading_key):
            bucket = "skill"
        elif _PRIORITY_SECTION.search(heading_key):
            bucket = "other"
        else:
            continue
        remain = budgets[bucket] - used[bucket]
        if remain <= 80:
            continue
        if len(chunk) > remain:
            clipped = chunk[:remain]
            if "\n" in clipped:
                heading_part, _, rest = clipped.partition("\n")
                chunk = heading_part if not rest.strip() else clipped
            else:
                chunk = clipped
        selected.append((index, chunk, bucket))
        used[bucket] += len(chunk)

    def _join(items: list[tuple[int, str, str]]) -> str:
        return "\n\n".join(chunk for _, chunk, _ in sorted(items)).strip()

    assembled = _join(selected)
    if len(assembled) > max_chars:
        selected = [item for item in selected if item[2] != "other"]
        assembled = _join(selected)
    if len(assembled) > max_chars:
        assembled = assembled[:max_chars].rsplit("\n", 1)[0] or assembled[:max_chars]
    if not assembled:
        cut = text.rfind("\n", 0, max_chars)
        cut = cut if cut > 0 else max_chars
        return text[:cut], True
    return assembled, True


def _build_user_prompt(segmented: str, headings: str) -> str:
    return f"""Extract the following resume into the required JSON schema.
Detected headings are a checklist; include each one when evidence exists:
{headings}
Boundary marker lines are instructions, not resume content.

{segmented}

Return one valid JSON object only."""


def _strip_code_fences(content: str) -> str:
    return re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        content.strip(),
        flags=re.I | re.S,
    )


def _is_rate_limited(exc: BaseException) -> bool:
    return is_rate_limited(exc)


def _call_groq(system_prompt: str, user_prompt: str, *, retry_rate_limit: bool = True) -> str:
    client = _groq_client()
    if client is None:
        raise RuntimeError("Groq is not configured.")
    last_error: Exception | None = None
    attempts = 5 if retry_rate_limit else 1
    for attempt in range(attempts):
        try:
            response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                temperature=settings.GROQ_TEMPERATURE,
                response_format={"type": "json_object"},
                max_tokens=settings.GROQ_MAX_TOKENS,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"{user_prompt}\n\nAnalysis style: {prompt_style_instruction()}",
                    },
                ],
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Groq returned an empty response.")
            return content.strip()
        except Exception as exc:
            last_error = exc
            if retry_rate_limit and attempt < attempts - 1 and is_rate_limited(exc):
                time.sleep(min(16.0, 2.0 * (2 ** attempt)))
                continue
            raise
    raise last_error or RuntimeError("Groq resume extraction failed.")


def _section_id(heading: str, used: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", heading.casefold()).strip("_") or "section"
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _flatten_items(items: Any) -> str:
    if isinstance(items, dict):
        return "\n".join(
            f"{key}: {_flatten_items(value)}".strip() for key, value in items.items()
        ).strip()
    if isinstance(items, list):
        return "\n".join(_flatten_items(value) for value in items).strip()
    return str(items or "").strip()


def _valid_ai_sections(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    sections = parsed.get("sections", [])
    if not isinstance(sections, list):
        return []
    return [dict(section) for section in sections if isinstance(section, dict)]


def _heading_key(heading: str) -> str:
    key = normalize_heading(heading)
    if key in {
        "header",
        "contact",
        "contactinfo",
        "contactinformation",
        "personaldetails",
    }:
        return "contactinformation"
    return key


def _normalize_ai_section(
    section: dict[str, Any],
    *,
    order: int,
    used_ids: set[str],
) -> dict[str, Any] | None:
    heading = str(section.get("heading", "")).strip()
    if not heading:
        return None

    raw_text = str(section.get("raw_text", "") or "").strip()
    items = section.get("items", [])
    if not isinstance(items, list):
        items = [items]
    if not raw_text:
        raw_text = _flatten_items(items)

    content_type = str(section.get("content_type", "")).strip().lower()
    if content_type not in _ALLOWED_CONTENT_TYPES:
        classification = classify_section(raw_text)
        content_type = classification["content_type"]
        if not items:
            items = classification["items"]

    normalized = dict(section)
    normalized.update(
        {
            "section_id": _section_id(heading, used_ids),
            "heading": heading,
            "heading_source": (
                "inferred"
                if str(section.get("heading_source", "original")).lower() == "inferred"
                else "original"
            ),
            "order": order,
            "content_type": content_type,
            "items": items,
            "raw_text": raw_text,
        }
    )
    return normalized


def _missing_source_lines(
    source_text: str, sections: list[dict[str, Any]]
) -> list[str]:
    represented = " ".join(
        re.sub(r"\s+", " ", str(section.get("raw_text", ""))).casefold()
        for section in sections
    )
    missing: list[str] = []
    seen: set[str] = set()
    for line in source_text.splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip()
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        if key not in represented:
            missing.append(cleaned)
    return missing


def _reconcile_with_source(parsed: dict[str, Any], full_text: str) -> dict[str, Any]:
    """Keep AI structure while making source text the authority for content."""
    fallback = parse_resume(full_text)
    source_sections = list(fallback.get("sections", []))
    ai_sections = _valid_ai_sections(parsed)
    used_ids: set[str] = set()

    # When deterministic heading detection finds meaningful sections, their
    # exact source boundaries and raw text are authoritative. AI output is used
    # only to enrich the matching section with structured items/content type.
    if len(source_sections) > 1:
        reconciled: list[dict[str, Any]] = []
        used_ai: set[int] = set()

        for order, source in enumerate(source_sections):
            source_heading = str(source.get("heading", "Section")).strip() or "Section"
            source_key = _heading_key(source_heading)
            match_index = next(
                (
                    index
                    for index, candidate in enumerate(ai_sections)
                    if index not in used_ai
                    and _heading_key(str(candidate.get("heading", ""))) == source_key
                ),
                None,
            )

            enriched = dict(source)
            if match_index is not None:
                used_ai.add(match_index)
                candidate = ai_sections[match_index]
                for key, value in candidate.items():
                    if key not in {
                        "section_id",
                        "heading",
                        "heading_source",
                        "order",
                        "raw_text",
                    }:
                        enriched[key] = value

            raw_text = str(source.get("raw_text", "") or "")
            content_type = str(enriched.get("content_type", "text")).lower()
            if content_type not in _ALLOWED_CONTENT_TYPES:
                content_type = classify_section(raw_text)["content_type"]
            items = enriched.get("items", [])
            if not isinstance(items, list):
                items = [items]

            enriched.update(
                {
                    "section_id": _section_id(source_heading, used_ids),
                    "heading": source_heading,
                    "heading_source": source.get("heading_source", "original"),
                    "order": order,
                    "content_type": content_type,
                    "items": items,
                    "raw_text": raw_text,
                }
            )
            reconciled.append(enriched)
    else:
        # Some resumes have no mechanically detectable headings. Preserve the
        # AI-discovered structure, then append only source lines it omitted.
        reconciled = []
        for section in ai_sections:
            normalized = _normalize_ai_section(
                section,
                order=len(reconciled),
                used_ids=used_ids,
            )
            if normalized is not None:
                reconciled.append(normalized)

        if not reconciled:
            reconciled = source_sections
            used_ids = {str(section.get("section_id", "")) for section in reconciled}

        missing_lines = _missing_source_lines(full_text, reconciled)
        if missing_lines:
            missing_text = "\n".join(missing_lines)
            classification = classify_section(missing_text)
            reconciled.append(
                {
                    "section_id": _section_id("Unclassified Source Content", used_ids),
                    "heading": "Unclassified Source Content",
                    "heading_source": "inferred",
                    "order": len(reconciled),
                    "content_type": classification["content_type"],
                    "items": classification["items"],
                    "raw_text": missing_text,
                    "source": "coverage_fallback",
                }
            )

    result = dict(parsed)
    result["sections"] = reconciled
    result["source_text"] = full_text
    return result


def _fallback_result(source_text: str, warning: str) -> dict[str, Any]:
    fallback = parse_resume(source_text)
    fallback["source_text"] = source_text
    fallback["extraction_method"] = "rule_based_fallback"
    fallback["extraction_warning"] = warning
    return ParsedResume.model_validate(fallback).model_dump(mode="json")


def extract_resume_data(text: str) -> dict[str, Any]:
    source_text = text.strip()
    if not source_text:
        raise ValueError("Resume text cannot be empty.")

    if _groq_client() is None or not settings.USE_LLM_FOR_RESUME_PARSING:
        warning = (
            "Resume LLM parsing is disabled; the deterministic parser was used."
            if _groq_client() is not None
            else "Groq is not configured; the deterministic parser was used."
        )
        return _fallback_result(source_text, warning)

    safe_text, was_truncated = _truncate(source_text)
    detected = detect_sections(safe_text)
    segmented = build_segmented_text(detected)
    headings = (
        "\n".join(
            f"- {'Contact Information' if section['heading'] == 'Header' else section['heading']}"
            for section in detected
        )
        or "- No explicit headings detected"
    )
    user_prompt = _build_user_prompt(segmented, headings)

    queue = get_groq_resume_queue()
    for attempt in range(3):
        try:
            system_prompt = SYSTEM_PROMPT
            if attempt:
                system_prompt += (
                    " Previous output was invalid. Return one valid JSON object only."
                )
            raw = _strip_code_fences(
                queue.call(
                    lambda prompt=system_prompt: _call_groq(
                        prompt, user_prompt, retry_rate_limit=False
                    )
                )
            )
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("AI output must be a JSON object.")

            parsed = _reconcile_with_source(parsed, source_text)
            parsed["extraction_method"] = "ai_with_source_reconciliation"
            parsed["extraction_warning"] = (
                "The AI input exceeded its safe prompt size. Exact source text and "
                "deterministic section content were retained during reconciliation."
                if was_truncated
                else ""
            )

            validated = ParsedResume.model_validate(parsed)
            if not validated.sections:
                raise ValueError("AI returned no resume sections.")
            return validated.model_dump(mode="json")
        except GroqRateLimitError:
            raise
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "Resume AI validation failed on attempt %s: %s",
                attempt + 1,
                exc,
            )
        except Exception as exc:
            if is_rate_limited(exc):
                raise GroqRateLimitError(
                    "Groq rate limit persisted; resume was not parsed or saved."
                ) from exc
            logger.exception("Groq resume extraction failed")
            break

    return _fallback_result(
        source_text,
        "AI extraction failed; the deterministic parser was used.",
    )


def extract_resume_text(text: str) -> dict[str, Any]:
    return extract_resume_data(text)
