from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from agents.screening_agent.schemas.ats import SkillCollection, SkillEvidence
from agents.screening_agent.utils.skill_normalizer import (
    find_known_skills,
    normalize_skill,
    skill_category,
)
from agents.screening_agent.utils.text_utils import dedupe_preserve


_SKILL_HEADING = re.compile(
    r"(skill|technolog|tool|framework|language|database|cloud|competenc|"
    r"expertise|stack|core\s+competenc|areas?\s+of\s+expertise|"
    r"professional\s+skills?|key\s+skills?)",
    re.IGNORECASE,
)

_CATEGORY_LABELS = re.compile(
    r"^(programming languages?|languages?|frameworks?|libraries|databases?|cloud|tools?|"
    r"technologies|technical skills?|soft skills?|skills?|platforms?|concepts?)\s*:\s*",
    re.IGNORECASE,
)


def _flatten_sections(parsed_resume: dict[str, Any]) -> list[dict[str, str]]:
    sections = parsed_resume.get("sections", []) if isinstance(parsed_resume, dict) else []
    output: list[dict[str, str]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        heading = str(section.get("heading", "")).strip()
        raw_text = str(section.get("raw_text", "")).strip()
        if not raw_text:
            items = section.get("items", [])
            if isinstance(items, list):
                raw_text = "\n".join(
                    str(item.get("value", item)) if isinstance(item, dict) else str(item)
                    for item in items
                )
        output.append({"heading": heading, "text": raw_text})
    return output


def _explicit_skill_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for line in text.splitlines():
        line = line.strip(" \t•*-–—#")
        if not line:
            continue
        line = _CATEGORY_LABELS.sub("", line)
        parts = re.split(r"\s*[|,;•]\s*", line)
        if len(parts) == 1 and ":" in line:
            parts = re.split(r"\s*:\s*", line, maxsplit=1)[-1:]
        for part in parts:
            cleaned = re.sub(r"\s+", " ", part).strip(" .()[]#")
            if not cleaned or len(cleaned) > 55 or len(cleaned.split()) > 7:
                continue
            if re.search(
                r"\b(responsible|developed|worked|created|managed|implemented|"
                r"fluent|native|days?|notice)\b",
                cleaned,
                re.I,
            ):
                continue
            if cleaned.casefold() in {
                "skills",
                "technical skills",
                "tools",
                "technologies",
                "strategy",
                "campaigns",
                "analytics",
            }:
                continue
            candidates.append(cleaned)
    return dedupe_preserve(candidates)


def extract_resume_skills(parsed_resume: dict[str, Any]) -> SkillCollection:
    """Extract evidence-backed skills from the existing dynamic resume JSON."""
    sections = _flatten_sections(parsed_resume)
    raw_skills: list[str] = []
    normalized_skills: list[str] = []
    evidence: list[SkillEvidence] = []
    by_category: dict[str, list[str]] = defaultdict(list)
    seen_pairs: set[tuple[str, str]] = set()

    for section in sections:
        heading = section["heading"]
        text = section["text"]
        for match in find_known_skills(text):
            raw = str(match["raw"])
            canonical = str(match["normalized"])
            category = str(match["category"])
            pair = (canonical.casefold(), heading.casefold())
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                evidence.append(
                    SkillEvidence(
                        raw_skill=raw,
                        normalized_skill=canonical,
                        category=category,
                        section=heading,
                        source_text=raw,
                    )
                )
            raw_skills.append(raw)
            normalized_skills.append(canonical)
            by_category[category].append(canonical)

        if _SKILL_HEADING.search(heading):
            for raw in _explicit_skill_candidates(text):
                if find_known_skills(raw):
                    continue
                canonical = normalize_skill(raw)
                category = skill_category(canonical, "other")
                pair = (canonical.casefold(), heading.casefold())
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    evidence.append(
                        SkillEvidence(
                            raw_skill=raw,
                            normalized_skill=canonical,
                            category=category,
                            section=heading,
                            source_text=raw,
                        )
                    )
                raw_skills.append(raw)
                normalized_skills.append(canonical)
                by_category[category].append(canonical)

    raw_skills = dedupe_preserve(raw_skills)
    normalized_skills = dedupe_preserve(normalized_skills)
    normalized_set = {skill.casefold() for skill in normalized_skills}

    clean_categories: dict[str, list[str]] = {}
    for category, values in by_category.items():
        deduped = [value for value in dedupe_preserve(values) if value.casefold() in normalized_set]
        if deduped:
            clean_categories[category] = deduped

    return SkillCollection(
        raw_skills=raw_skills,
        normalized_skills=normalized_skills,
        skills_by_category=dict(sorted(clean_categories.items())),
        evidence=evidence,
    )
