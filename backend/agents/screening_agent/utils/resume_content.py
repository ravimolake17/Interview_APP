"""Prepare parsed resume content safely for ATS processing.

A parsed resume section can contain the same information in two forms:

1. raw_text:
   Original section content with formatting and line breaks.

2. items:
   Structured list, table, or key-value representation of the same content.

Both fields are useful in the extraction API response. However, downstream
ATS processing must never combine both fields because that could count the
same skills, experience, projects, certifications, or keywords twice.

This module creates a separate deep copy for ATS processing. The original
extraction response remains unchanged.
"""

from __future__ import annotations

import html
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any


def clean_section_text(value: Any) -> str:
    """Clean extracted text without removing meaningful resume content."""
    if value is None:
        return ""

    text = html.unescape(str(value))

    text = text.replace("\u00a0", " ")
    text = text.replace("\\_", "_")
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Remove trailing spaces without removing headings, bullets, or structure.
    text = re.sub(r"[ \t]+\n", "\n", text)

    # Avoid excessive empty lines.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _is_scalar(value: Any) -> bool:
    """Return whether a value can be represented as a simple text cell."""
    return value is None or isinstance(
        value,
        (str, int, float, bool),
    )


def _flatten_mapping(value: Mapping[str, Any]) -> list[str]:
    """Flatten a dictionary into readable text lines."""
    lines: list[str] = []

    for key, nested_value in value.items():
        key_text = clean_section_text(key)

        if _is_scalar(nested_value):
            value_text = clean_section_text(nested_value)

            if key_text and value_text:
                lines.append(f"{key_text}: {value_text}")
            elif value_text:
                lines.append(value_text)

            continue

        nested_lines = _flatten_item(nested_value)

        if key_text and nested_lines:
            lines.append(f"{key_text}: {' | '.join(nested_lines)}")
        else:
            lines.extend(nested_lines)

    return lines


def _flatten_sequence(value: Sequence[Any]) -> list[str]:
    """Flatten a nested list or table row."""
    sequence = list(value)

    if not sequence:
        return []

    # A nested scalar list normally represents one table row.
    if all(_is_scalar(item) for item in sequence):
        cells = [
            clean_section_text(item)
            for item in sequence
            if clean_section_text(item)
        ]

        if not cells:
            return []

        return [" | ".join(cells)]

    lines: list[str] = []

    for item in sequence:
        lines.extend(_flatten_item(item))

    return lines


def _flatten_item(value: Any) -> list[str]:
    """Recursively flatten one structured item."""
    if value is None:
        return []

    if isinstance(value, Mapping):
        return _flatten_mapping(value)

    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return _flatten_sequence(value)

    cleaned = clean_section_text(value)

    return [cleaned] if cleaned else []


def flatten_section_items(items: Any) -> list[str]:
    """Convert section items into readable lines.

    Top-level list entries remain separate lines. Nested scalar lists are
    treated as table rows and joined using ``|``.
    """
    if items is None:
        return []

    if isinstance(items, Mapping):
        lines = _flatten_mapping(items)

    elif isinstance(items, Sequence) and not isinstance(
        items,
        (str, bytes, bytearray),
    ):
        lines = []

        for item in items:
            lines.extend(_flatten_item(item))

    else:
        lines = _flatten_item(items)

    return deduplicate_text_lines(lines)


def deduplicate_text_lines(lines: list[str]) -> list[str]:
    """Remove duplicate text lines while preserving their original order."""
    unique_lines: list[str] = []
    seen: set[str] = set()

    for line in lines:
        cleaned = clean_section_text(line)

        if not cleaned:
            continue

        comparison_key = re.sub(
            r"\s+",
            " ",
            cleaned,
        ).strip().casefold()

        if comparison_key in seen:
            continue

        seen.add(comparison_key)
        unique_lines.append(cleaned)

    return unique_lines


def get_canonical_section_text(
    section: Mapping[str, Any],
) -> str:
    """Return exactly one content representation for a section.

    Priority:

    1. Use raw_text when it exists.
    2. Use items only when raw_text is missing or empty.
    3. Never combine raw_text and items.
    """
    raw_text = clean_section_text(section.get("raw_text"))

    if raw_text:
        return raw_text

    item_lines = flatten_section_items(section.get("items", []))

    return "\n".join(item_lines).strip()


def _convert_to_dictionary(value: Any) -> dict[str, Any]:
    """Convert dictionaries or Pydantic models into plain dictionaries."""
    if isinstance(value, Mapping):
        return deepcopy(dict(value))

    model_dump = getattr(value, "model_dump", None)

    if callable(model_dump):
        dumped_value = model_dump(mode="python")

        if isinstance(dumped_value, Mapping):
            return deepcopy(dict(dumped_value))

    raise TypeError(
        "Parsed resume data must be a dictionary or a Pydantic model."
    )


def prepare_resume_for_ats(parsed_resume: Any) -> dict[str, Any]:
    """Create a safe processing copy of a parsed resume.

    The original parsed resume is never modified.

    Inside the processing copy:

    - raw_text contains the canonical section content.
    - items is emptied to prevent downstream double processing.
    - all other section fields remain unchanged.

    The extraction API may still return both raw_text and items.
    """
    processing_resume = _convert_to_dictionary(parsed_resume)

    sections = processing_resume.get("sections", [])

    if not isinstance(sections, list):
        processing_resume["sections"] = []
        return processing_resume

    processed_sections: list[dict[str, Any]] = []

    for section_value in sections:
        try:
            section = _convert_to_dictionary(section_value)
        except TypeError:
            # Ignore invalid non-dictionary section values.
            continue

        canonical_text = get_canonical_section_text(section)

        # One canonical representation for ATS services.
        section["raw_text"] = canonical_text
        section["items"] = []

        processed_sections.append(section)

    processing_resume["sections"] = processed_sections

    return processing_resume