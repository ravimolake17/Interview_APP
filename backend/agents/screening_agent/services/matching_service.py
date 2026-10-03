from __future__ import annotations

import logging
import re

from agents.screening_agent.config import settings
from agents.screening_agent.schemas.ats import (
    ExperienceEntry,
    MatchAnalysis,
    ParsedJD,
    SemanticSkillMatch,
    SkillCollection,
)
from agents.screening_agent.services.embedding_service import get_embedding_service
from agents.screening_agent.services.semantic_matching_service import (
    build_semantic_skill_matches,
)
from agents.screening_agent.utils.skill_normalizer import (
    are_exclusive_distinct_skills,
    expand_compound_skill,
    normalize_skill,
    normalize_skills,
    skill_had_proficiency_modifier,
    skill_search_terms,
)
from agents.screening_agent.utils.text_utils import dedupe_preserve

logger = logging.getLogger(__name__)

_LEVEL_CREDIT = {
    "EXACT_MATCH": 1.0,
    "STRONG_SEMANTIC_MATCH": 0.85,
    "PARTIAL_MATCH": 0.40,
    "MISSING": 0.0,
}
_FULL_MATCH_LEVELS = {"EXACT_MATCH", "STRONG_SEMANTIC_MATCH"}

_GENERIC_SKILL_TOKENS = {
    "development",
    "developer",
    "experience",
    "advanced",
    "intermediate",
    "beginner",
    "basic",
    "expert",
    "preferred",
    "required",
    "using",
    "knowledge",
    "skills",
    "skill",
    "tools",
    "tool",
    "systems",
    "system",
    "services",
    "service",
    "applications",
    "application",
    "software",
    "platform",
    "platforms",
    "technology",
    "technologies",
    "framework",
    "frameworks",
    "library",
    "libraries",
    "and",
    "the",
    "with",
    "for",
}

# Generic single tokens that inflate false semantic hits when used as anchors.
_GENERIC_RESUME_ANCHORS = frozenset(
    {
        "cloud",
        "platforms",
        "tools",
        "data",
        "services",
        "systems",
        "software",
        "backend",
        "frontend",
        "programming",
        "development",
        "management",
        "control",
        "security",
        "automation",
        "testing",
        "database",
        "web",
        "http",
        "api",
        "server",
        "application",
        "applications",
        "engineer",
        "engineering",
        "models",
        "design",
        "intelligent",
    }
)


def _casefold_map(values: list[str]) -> dict[str, str]:
    """Return canonical values keyed case-insensitively, preserving order."""
    normalized = normalize_skills(values)
    return {value.casefold(): value for value in normalized}


def _content_tokens(value: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9+#.]{2,}", (value or "").casefold())
    return {token.strip(".-") for token in tokens if token not in _GENERIC_SKILL_TOKENS}


def _find_evidence_snippet(
    skill: str,
    *,
    resume_text: str,
    resume_skills: list[str],
    evidence_texts: list[str],
) -> str:
    """Return a short resume snippet that actually names the skill, if any."""
    terms = skill_search_terms(skill)
    haystacks = [text for text in (*evidence_texts, resume_text) if text]
    for term in sorted(terms, key=len, reverse=True):
        pattern = re.compile(
            rf"(?<![A-Za-z0-9+#]){re.escape(term)}(?![A-Za-z0-9+#])",
            re.IGNORECASE,
        )
        for haystack in haystacks:
            match = pattern.search(haystack)
            if not match:
                continue
            start = max(0, match.start() - 48)
            end = min(len(haystack), match.end() + 64)
            snippet = re.sub(r"\s+", " ", haystack[start:end]).strip(" \t\r\n,;|•-–—")
            if snippet:
                return snippet[:220]
    canonical = normalize_skill(skill)
    for resume_skill in resume_skills:
        if canonical and canonical.casefold() == resume_skill.casefold():
            return resume_skill
    return ""


def _lexical_match_level(
    jd_skill: str,
    resume_skills: list[str],
    *,
    resume_text: str,
    evidence_texts: list[str],
    display_skill: str | None = None,
) -> SemanticSkillMatch:
    canonical = display_skill or normalize_skill(jd_skill) or jd_skill
    resume_map = {skill.casefold(): skill for skill in resume_skills}
    evidence = _find_evidence_snippet(
        jd_skill,
        resume_text=resume_text,
        resume_skills=resume_skills,
        evidence_texts=evidence_texts,
    )
    had_modifier = skill_had_proficiency_modifier(jd_skill)

    if canonical.casefold() in resume_map:
        level = "STRONG_SEMANTIC_MATCH" if had_modifier else "EXACT_MATCH"
        return SemanticSkillMatch(
            jd_skill=canonical,
            matched_resume_skill=resume_map[canonical.casefold()],
            similarity=1.0,
            match_status="Perfect Match" if level == "EXACT_MATCH" else "Strong Match",
            match_level=level,  # type: ignore[arg-type]
            matched=True,
            match_method="exact",
            evidence=evidence or resume_map[canonical.casefold()],
        )

    jd_tokens = _content_tokens(canonical)
    best_resume = ""
    best_overlap = 0.0
    for resume_skill in resume_skills:
        if are_exclusive_distinct_skills(canonical, resume_skill):
            continue
        resume_tokens = _content_tokens(resume_skill)
        if not jd_tokens or not resume_tokens:
            continue
        if jd_tokens <= resume_tokens or resume_tokens <= jd_tokens:
            overlap = 1.0
        else:
            overlap = len(jd_tokens & resume_tokens) / len(jd_tokens | resume_tokens)
        if overlap > best_overlap:
            best_overlap = overlap
            best_resume = resume_skill

    if evidence:
        if had_modifier:
            return SemanticSkillMatch(
                jd_skill=canonical,
                matched_resume_skill=best_resume or canonical,
                similarity=0.92,
                match_status="Strong Match",
                match_level="STRONG_SEMANTIC_MATCH",
                matched=True,
                match_method="lexical",
                evidence=evidence,
            )
        return SemanticSkillMatch(
            jd_skill=canonical,
            matched_resume_skill=best_resume or canonical,
            similarity=1.0,
            match_status="Perfect Match",
            match_level="EXACT_MATCH",
            matched=True,
            match_method="lexical",
            evidence=evidence,
        )

    if best_resume and best_overlap >= 0.72 and not are_exclusive_distinct_skills(canonical, best_resume):
        return SemanticSkillMatch(
            jd_skill=canonical,
            matched_resume_skill=best_resume,
            similarity=round(best_overlap, 4),
            match_status="Strong Match",
            match_level="STRONG_SEMANTIC_MATCH",
            matched=True,
            match_method="lexical",
            evidence=best_resume,
        )

    if best_resume and best_overlap >= 0.34:
        return SemanticSkillMatch(
            jd_skill=canonical,
            matched_resume_skill=best_resume,
            similarity=round(best_overlap, 4),
            match_status="Partial Match",
            match_level="PARTIAL_MATCH",
            matched=False,
            match_method="partial",
            evidence=best_resume,
        )

    distinctive = {token for token in jd_tokens if len(token) >= 6}
    resume_fold = f"{resume_text} {' '.join(evidence_texts)}".casefold()
    token_hits = [
        token
        for token in distinctive
        if token in resume_fold
        or any(word.startswith(token[:6]) for word in re.findall(r"[a-z]{4,}", resume_fold))
    ]
    if distinctive and len(token_hits) >= max(1, len(distinctive) // 2):
        snippet = _find_evidence_snippet(
            token_hits[0],
            resume_text=resume_text,
            resume_skills=resume_skills,
            evidence_texts=evidence_texts,
        ) or "; ".join(token_hits)
        return SemanticSkillMatch(
            jd_skill=canonical,
            matched_resume_skill=best_resume or None,
            similarity=0.45,
            match_status="Partial Match",
            match_level="PARTIAL_MATCH",
            matched=False,
            match_method="partial",
            evidence=snippet,
        )

    return SemanticSkillMatch(
        jd_skill=canonical,
        matched=False,
        match_status="No Match",
        match_level="MISSING",
        match_method="none",
        evidence="",
    )


def _ratio_from_matches(matches: list[SemanticSkillMatch], skills: list[str]) -> float:
    if not skills:
        return 1.0
    credit = sum(_LEVEL_CREDIT.get(item.match_level, 0.0) for item in matches)
    return round(min(1.0, credit / len(skills)), 4)


def _partition_matches(
    matches: list[SemanticSkillMatch],
) -> tuple[list[str], list[str], list[str]]:
    matched: list[str] = []
    partial: list[str] = []
    missing: list[str] = []
    for item in matches:
        if item.match_level in _FULL_MATCH_LEVELS:
            matched.append(item.jd_skill)
        elif item.match_level == "PARTIAL_MATCH":
            partial.append(item.jd_skill)
        else:
            missing.append(item.jd_skill)
    return (
        dedupe_preserve(matched),
        dedupe_preserve(partial),
        dedupe_preserve(missing),
    )


def _is_usable_semantic_anchor(phrase: str) -> bool:
    cleaned = " ".join(str(phrase).split()).strip(" ,;|")
    if len(cleaned) < 3:
        return False
    tokens = [token for token in re.split(r"[\s/,&]+", cleaned) if token]
    if len(tokens) == 1 and tokens[0].casefold() in _GENERIC_RESUME_ANCHORS:
        return False
    return True


def _semantic_resume_phrases(
    candidate_skills: SkillCollection,
    *,
    experience_entries: list[ExperienceEntry] | None = None,
    keywords: list[str] | None = None,
) -> list[str]:
    """Skill-label phrase pool for semantic matching (no noisy keyword dumps)."""
    del experience_entries, keywords
    phrases: list[str] = []
    phrases.extend(candidate_skills.normalized_skills or [])
    phrases.extend(candidate_skills.raw_skills or [])
    for evidence in candidate_skills.evidence or []:
        if evidence.normalized_skill:
            phrases.append(evidence.normalized_skill)
        if evidence.raw_skill:
            phrases.append(evidence.raw_skill)

    return dedupe_preserve(
        [phrase for phrase in phrases if _is_usable_semantic_anchor(phrase)]
    )


def _merge_semantic_classification(
    lexical: SemanticSkillMatch,
    semantic: SemanticSkillMatch | None,
) -> SemanticSkillMatch:
    if lexical.match_level in _FULL_MATCH_LEVELS:
        return lexical
    if semantic is None or not semantic.matched_resume_skill:
        return lexical
    if are_exclusive_distinct_skills(lexical.jd_skill, semantic.matched_resume_skill):
        return lexical

    jd_tokens = _content_tokens(lexical.jd_skill)
    resume_tokens = _content_tokens(semantic.matched_resume_skill)
    token_overlap = 0.0
    if jd_tokens and resume_tokens:
        token_overlap = len(jd_tokens & resume_tokens) / len(jd_tokens | resume_tokens)
    subset = bool(jd_tokens and resume_tokens and (jd_tokens <= resume_tokens or resume_tokens <= jd_tokens))

    if semantic.match_level in _FULL_MATCH_LEVELS and (subset or token_overlap >= 0.28):
        evidence = lexical.evidence or semantic.evidence or semantic.matched_resume_skill
        return SemanticSkillMatch(
            jd_skill=lexical.jd_skill,
            matched_resume_skill=semantic.matched_resume_skill,
            similarity=semantic.similarity,
            match_status=semantic.match_status,
            match_level="STRONG_SEMANTIC_MATCH",
            matched=True,
            match_method="semantic",
            evidence=evidence,
        )

    if (
        semantic.match_level in {"STRONG_SEMANTIC_MATCH", "PARTIAL_MATCH", "EXACT_MATCH"}
        or semantic.similarity >= settings.ATS_SEMANTIC_PARTIAL_THRESHOLD
    ) and (subset or token_overlap >= 0.18 or lexical.match_level == "PARTIAL_MATCH"):
        evidence = lexical.evidence or semantic.evidence or semantic.matched_resume_skill
        return SemanticSkillMatch(
            jd_skill=lexical.jd_skill,
            matched_resume_skill=semantic.matched_resume_skill,
            similarity=semantic.similarity,
            match_status="Partial Match",
            match_level="PARTIAL_MATCH",
            matched=False,
            match_method="partial",
            evidence=evidence,
        )

    return lexical


def _canonical_skill_originals(values: list[str]) -> tuple[list[str], dict[str, str]]:
    originals: dict[str, str] = {}
    ordered: list[str] = []
    for raw in values:
        expanded = expand_compound_skill(raw)
        for part in expanded:
            canonical = normalize_skill(part)
            if not canonical:
                continue
            key = canonical.casefold()
            if key not in originals:
                originals[key] = raw if len(expanded) == 1 else part
                ordered.append(canonical)
    return ordered, originals


def analyze_skill_match(
    candidate_skills: SkillCollection,
    parsed_jd: ParsedJD,
    *,
    experience_entries: list[ExperienceEntry] | None = None,
    keywords: list[str] | None = None,
    resume_text: str = "",
) -> MatchAnalysis:
    """Hybrid skill match: unique atomic skills with exact/semantic/partial/missing levels."""
    resume_skills = normalize_skills(
        list(candidate_skills.normalized_skills or [])
        + list(candidate_skills.raw_skills or [])
    )
    required, required_originals = _canonical_skill_originals(
        parsed_jd.required_skills.normalized
    )
    preferred_ordered, preferred_originals = _canonical_skill_originals(
        parsed_jd.preferred_skills.normalized
    )
    preferred = [
        skill
        for skill in preferred_ordered
        if skill.casefold() not in {item.casefold() for item in required}
    ]

    evidence_texts = [
        item.source_text
        for item in (candidate_skills.evidence or [])
        if item.source_text
    ]
    if experience_entries:
        evidence_texts.extend(
            f"{entry.role} {entry.company} {entry.text}" for entry in experience_entries
        )

    required_lexical = [
        _lexical_match_level(
            required_originals.get(skill.casefold(), skill),
            resume_skills,
            resume_text=resume_text,
            evidence_texts=evidence_texts,
            display_skill=skill,
        )
        for skill in required
    ]
    preferred_lexical = [
        _lexical_match_level(
            preferred_originals.get(skill.casefold(), skill),
            resume_skills,
            resume_text=resume_text,
            evidence_texts=evidence_texts,
            display_skill=skill,
        )
        for skill in preferred
    ]

    exact_required = {
        item.jd_skill.casefold(): item.matched_resume_skill or item.jd_skill
        for item in required_lexical
        if item.match_level == "EXACT_MATCH" and item.matched_resume_skill
    }
    exact_preferred = {
        item.jd_skill.casefold(): item.matched_resume_skill or item.jd_skill
        for item in preferred_lexical
        if item.match_level == "EXACT_MATCH" and item.matched_resume_skill
    }

    semantic_enabled = settings.ATS_SEMANTIC_MATCHING_ENABLED
    embedding_service = get_embedding_service()
    if semantic_enabled and not embedding_service.is_available():
        logger.warning(
            "Semantic matching enabled but embedding backend unavailable; "
            "falling back to rule-based skill matching."
        )
        semantic_enabled = False

    semantic_required: list[SemanticSkillMatch] = []
    semantic_preferred: list[SemanticSkillMatch] = []

    if semantic_enabled and resume_skills and (required or preferred):
        semantic_phrases = _semantic_resume_phrases(
            candidate_skills,
            experience_entries=experience_entries,
            keywords=keywords,
        )
        try:
            semantic_required = build_semantic_skill_matches(
                required,
                semantic_phrases,
                exact_matches=exact_required,
            )
            semantic_preferred = build_semantic_skill_matches(
                preferred,
                semantic_phrases,
                exact_matches=exact_preferred,
            )
        except Exception as exc:
            logger.exception(
                "Semantic skill matching failed (%s); falling back to lexical matching",
                type(exc).__name__,
            )
            semantic_enabled = False
            semantic_required = []
            semantic_preferred = []

    semantic_required_map = {item.jd_skill.casefold(): item for item in semantic_required}
    semantic_preferred_map = {item.jd_skill.casefold(): item for item in semantic_preferred}

    required_matches = [
        _merge_semantic_classification(
            lexical,
            semantic_required_map.get(lexical.jd_skill.casefold()),
        )
        for lexical in required_lexical
    ]
    preferred_matches = [
        _merge_semantic_classification(
            lexical,
            semantic_preferred_map.get(lexical.jd_skill.casefold()),
        )
        for lexical in preferred_lexical
    ]

    matched_required, partial_required, missing_required = _partition_matches(
        required_matches
    )
    matched_preferred, partial_preferred, missing_preferred = _partition_matches(
        preferred_matches
    )

    jd_keys = {skill.casefold() for skill in required + preferred}
    additional = [
        skill
        for skill in resume_skills
        if skill.casefold() not in jd_keys
    ]

    return MatchAnalysis(
        matched_required_skills=matched_required,
        missing_required_skills=missing_required,
        matched_preferred_skills=matched_preferred,
        missing_preferred_skills=missing_preferred,
        partial_required_skills=partial_required,
        partial_preferred_skills=partial_preferred,
        additional_candidate_skills=dedupe_preserve(additional),
        required_match_ratio=_ratio_from_matches(required_matches, required),
        preferred_match_ratio=_ratio_from_matches(preferred_matches, preferred),
        semantic_matching_enabled=semantic_enabled,
        semantic_required_matches=required_matches,
        semantic_preferred_matches=preferred_matches,
    )
