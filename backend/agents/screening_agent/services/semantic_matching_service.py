"""Semantic skill matching using BGE-M3 dense embeddings."""

from __future__ import annotations

import logging
import re

from agents.screening_agent.config import settings
from agents.screening_agent.schemas.ats import SemanticSkillMatch
from agents.screening_agent.services.embedding_service import get_embedding_service
from agents.screening_agent.utils.skill_normalizer import (
    are_exclusive_distinct_skills,
    strip_skill_category_prefix,
)

logger = logging.getLogger(__name__)

_GENERIC_TOKENS = {
    "development",
    "experience",
    "systems",
    "system",
    "services",
    "service",
    "applications",
    "application",
    "software",
    "platform",
    "and",
    "the",
    "with",
    "for",
}


def classify_similarity(similarity: float) -> str:
    if similarity >= settings.ATS_SEMANTIC_PERFECT_THRESHOLD:
        return "Perfect Match"
    if similarity >= settings.ATS_SEMANTIC_STRONG_THRESHOLD:
        return "Strong Match"
    if similarity >= settings.ATS_SEMANTIC_GOOD_THRESHOLD:
        return "Good Match"
    if similarity >= settings.ATS_SEMANTIC_PARTIAL_THRESHOLD:
        return "Partial Match"
    return "No Match"


def _match_level_from_similarity(
    similarity: float,
    *,
    token_ok: bool,
) -> str:
    if similarity >= settings.ATS_SEMANTIC_STRONG_THRESHOLD and token_ok:
        return "STRONG_SEMANTIC_MATCH"
    if similarity >= settings.ATS_SEMANTIC_PARTIAL_THRESHOLD and token_ok:
        return "PARTIAL_MATCH"
    return "MISSING"


def _content_tokens(value: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9+#.]{2,}", (value or "").casefold())
    return {token.strip(".-") for token in tokens if token not in _GENERIC_TOKENS}


def _token_relation(jd_skill: str, resume_skill: str) -> tuple[float, bool]:
    jd_tokens = _content_tokens(jd_skill)
    resume_tokens = _content_tokens(resume_skill)
    if not jd_tokens or not resume_tokens:
        return 0.0, False
    if are_exclusive_distinct_skills(jd_skill, resume_skill):
        return 0.0, False
    subset = jd_tokens <= resume_tokens or resume_tokens <= jd_tokens
    overlap = len(jd_tokens & resume_tokens) / len(jd_tokens | resume_tokens)
    return overlap, bool(subset or overlap >= 0.18)


def _log_match(item: SemanticSkillMatch) -> None:
    logger.info(
        "Semantic skill match | JD=%r | Resume=%r | Similarity=%.3f | Status=%s | Level=%s | Method=%s",
        item.jd_skill,
        item.matched_resume_skill,
        item.similarity,
        item.match_status,
        item.match_level,
        item.match_method,
    )


def _embed_key(text: str) -> str:
    """Contextualize short skill labels so BGE-M3 ranks paraphrases correctly."""
    cleaned = " ".join(str(text).split()).strip(" ,;|")
    if not cleaned:
        return ""
    return f"Technical skill: {cleaned}"


def expand_resume_phrases(phrases: list[str]) -> list[str]:
    """Expand skill labels into embeddable variants (strip category prefixes)."""
    out: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        cleaned = " ".join(str(phrase).split()).strip(" ,;|")
        if not cleaned:
            continue
        variants = [cleaned]
        stripped = strip_skill_category_prefix(cleaned)
        if stripped and stripped.casefold() != cleaned.casefold():
            variants.append(stripped)
        for variant in variants:
            key = variant.casefold()
            if key not in seen and len(variant) >= 2:
                seen.add(key)
                out.append(variant)
    return out


def build_semantic_skill_matches(
    jd_skills: list[str],
    resume_skills: list[str],
    *,
    exact_matches: dict[str, str],
) -> list[SemanticSkillMatch]:
    """Find the best resume skill for each JD skill using cosine similarity."""
    if not jd_skills:
        return []

    service = get_embedding_service()
    if not service.is_available():
        return []

    resume_phrases = expand_resume_phrases(resume_skills)
    if not resume_phrases:
        return []

    jd_keys = {_embed_key(skill): skill for skill in jd_skills if _embed_key(skill)}
    resume_keys = {
        _embed_key(phrase): phrase for phrase in resume_phrases if _embed_key(phrase)
    }
    vectors = service.embed_texts(list(jd_keys.keys()) + list(resume_keys.keys()))

    resume_vectors = {
        phrase: vectors[key]
        for key, phrase in resume_keys.items()
        if key in vectors
    }

    matches: list[SemanticSkillMatch] = []
    for jd_skill in jd_skills:
        exact_resume = exact_matches.get(jd_skill.casefold())
        if exact_resume:
            item = SemanticSkillMatch(
                jd_skill=jd_skill,
                matched_resume_skill=exact_resume,
                similarity=1.0,
                match_status="Perfect Match",
                match_level="EXACT_MATCH",
                matched=True,
                match_method="exact",
                evidence=exact_resume,
            )
            matches.append(item)
            _log_match(item)
            continue

        jd_key = _embed_key(jd_skill)
        jd_vector = vectors.get(jd_key)
        if jd_vector is None or not resume_vectors:
            item = SemanticSkillMatch(
                jd_skill=jd_skill,
                matched=False,
                match_method="none",
                match_level="MISSING",
            )
            matches.append(item)
            _log_match(item)
            continue

        best_skill: str | None = None
        best_similarity = 0.0
        for resume_skill, resume_vector in resume_vectors.items():
            if are_exclusive_distinct_skills(jd_skill, resume_skill):
                continue
            similarity = service.cosine_similarity(jd_vector, resume_vector)
            if similarity > best_similarity:
                best_similarity = similarity
                best_skill = resume_skill

        token_overlap, token_ok = (
            _token_relation(jd_skill, best_skill) if best_skill else (0.0, False)
        )
        del token_overlap
        match_level = _match_level_from_similarity(best_similarity, token_ok=token_ok)
        matched = match_level in {"EXACT_MATCH", "STRONG_SEMANTIC_MATCH"}
        item = SemanticSkillMatch(
            jd_skill=jd_skill,
            matched_resume_skill=best_skill,
            similarity=round(best_similarity, 4),
            match_status=classify_similarity(best_similarity),
            match_level=match_level,  # type: ignore[arg-type]
            matched=matched,
            match_method="semantic" if matched else ("partial" if match_level == "PARTIAL_MATCH" else "none"),
            evidence=best_skill or "",
        )
        matches.append(item)
        _log_match(item)

    return matches


def average_match_ratio(matches: list[SemanticSkillMatch]) -> float:
    """Weighted fraction of JD skills using exact/semantic/partial credit."""
    if not matches:
        return 1.0
    credits = {
        "EXACT_MATCH": 1.0,
        "STRONG_SEMANTIC_MATCH": 0.85,
        "PARTIAL_MATCH": 0.40,
        "MISSING": 0.0,
    }
    total = 0.0
    for item in matches:
        if item.match_level != "MISSING":
            total += credits.get(item.match_level, 0.0)
        else:
            total += 1.0 if item.matched else 0.0
    return round(total / len(matches), 4)
