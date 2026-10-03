"""Tests for hybrid semantic + rule-based skill matching."""

from __future__ import annotations

import numpy as np
import pytest

from agents.screening_agent.config import settings
from agents.screening_agent.schemas.ats import ParsedJD, SkillCollection, SkillList
from agents.screening_agent.services.matching_service import analyze_skill_match
from agents.screening_agent.services.semantic_matching_service import (
    average_match_ratio,
    build_semantic_skill_matches,
    classify_similarity,
)


@pytest.fixture
def enable_semantic_matching(monkeypatch):
    monkeypatch.setattr(settings, "ATS_SEMANTIC_MATCHING_ENABLED", True)


def _mock_vectors(pairs: dict[str, str]) -> dict[str, np.ndarray]:
    """Build unit vectors so paired phrases are highly similar."""
    vectors: dict[str, np.ndarray] = {}
    dim = 8
    for index, (left, right) in enumerate(pairs.items()):
        base = np.zeros(dim, dtype=np.float32)
        base[index % dim] = 1.0
        left_vec = base / np.linalg.norm(base)
        noise = np.zeros(dim, dtype=np.float32)
        noise[(index + 1) % dim] = 0.05
        right_vec = (left_vec + noise).astype(np.float32)
        right_vec /= np.linalg.norm(right_vec)
        vectors[left] = left_vec
        vectors[right] = right_vec
        # Matching service embeds with a "Technical skill:" context prefix.
        vectors[f"Technical skill: {left}"] = left_vec
        vectors[f"Technical skill: {right}"] = right_vec
    return vectors


def _fake_embedding_service(vectors: dict[str, np.ndarray]):
    class FakeEmbeddingService:
        def is_available(self) -> bool:
            return True

        def embed_texts(self, texts):
            return {text: vectors[text] for text in texts if text in vectors}

        @staticmethod
        def cosine_similarity(left, right):
            return float(np.dot(left, right))

    return FakeEmbeddingService()


def test_classify_similarity_thresholds():
    assert classify_similarity(0.91) == "Perfect Match"
    assert classify_similarity(0.87) == "Strong Match"
    assert classify_similarity(0.82) == "Good Match"
    assert classify_similarity(0.76) == "Partial Match"
    assert classify_similarity(0.70) == "No Match"


def test_semantic_matches_alias_skills(monkeypatch, enable_semantic_matching):
    monkeypatch.setattr(settings, "ATS_SEMANTIC_MIN_MATCH_THRESHOLD", 0.75)

    pairs = {
        "REST API": "HTTP Endpoints",
        "Docker": "Containerization",
        "JWT": "Bearer Token",
        "FastAPI": "ASGI Framework",
        "PostgreSQL": "Relational Database",
    }
    vectors = _mock_vectors(pairs)
    fake = _fake_embedding_service(vectors)

    monkeypatch.setattr(
        "agents.screening_agent.services.matching_service.get_embedding_service",
        lambda: fake,
    )
    monkeypatch.setattr(
        "agents.screening_agent.services.semantic_matching_service.get_embedding_service",
        lambda: fake,
    )

    jd = ParsedJD(
        required_skills=SkillList(
            normalized=[
                "REST API",
                "Docker",
                "JWT",
                "FastAPI",
                "PostgreSQL",
            ]
        )
    )
    candidate = SkillCollection(
        normalized_skills=[
            "HTTP Endpoints",
            "Containerization",
            "Bearer Token",
            "ASGI Framework",
            "Relational Database",
        ]
    )

    match = analyze_skill_match(candidate, jd)
    assert match.semantic_matching_enabled is True
    assert len(match.matched_required_skills) == 5
    assert match.missing_required_skills == []
    assert match.required_match_ratio >= 0.75
    assert all(item.matched for item in match.semantic_required_matches)


def test_exact_rule_match_still_wins(monkeypatch, enable_semantic_matching):
    fake = _fake_embedding_service(
        {
            text: np.array([1.0, 0.0], dtype=np.float32)
            for text in (
                "Technical skill: Python",
                "Technical skill: FastAPI",
            )
        }
    )

    monkeypatch.setattr(
        "agents.screening_agent.services.matching_service.get_embedding_service",
        lambda: fake,
    )
    monkeypatch.setattr(
        "agents.screening_agent.services.semantic_matching_service.get_embedding_service",
        lambda: fake,
    )

    match = analyze_skill_match(
        SkillCollection(normalized_skills=["Python", "FastAPI"]),
        ParsedJD(required_skills=SkillList(normalized=["Python", "FastAPI"])),
    )
    assert match.required_match_ratio == 1.0
    assert match.semantic_required_matches[0].match_method == "exact"


def test_average_match_ratio_counts_only_actual_matches():
    from agents.screening_agent.schemas.ats import SemanticSkillMatch

    matches = [
        SemanticSkillMatch(
            jd_skill="A",
            matched_resume_skill="B",
            similarity=0.94,
            matched=True,
            match_method="semantic",
        ),
        SemanticSkillMatch(
            jd_skill="C",
            matched_resume_skill="D",
            similarity=0.50,
            matched=False,
            match_method="none",
        ),
    ]
    assert average_match_ratio(matches) == pytest.approx(0.5)


def test_build_semantic_skill_matches_respects_exact_map(monkeypatch):
    # Empty vectors: exact map must still win without embeddings.
    fake = _fake_embedding_service({})

    monkeypatch.setattr(
        "agents.screening_agent.services.matching_service.get_embedding_service",
        lambda: fake,
    )
    monkeypatch.setattr(
        "agents.screening_agent.services.semantic_matching_service.get_embedding_service",
        lambda: fake,
    )

    matches = build_semantic_skill_matches(
        ["Python"],
        ["Python", "Java"],
        exact_matches={"python": "Python"},
    )
    assert matches[0].match_method == "exact"
    assert matches[0].similarity == 1.0
