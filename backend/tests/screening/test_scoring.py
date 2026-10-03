from __future__ import annotations

import pytest

from agents.screening_agent.config import settings
from agents.screening_agent.schemas.ats import (
    CandidateProfile,
    ExperienceEntry,
    MatchAnalysis,
    ParsedJD,
    SkillCollection,
    SkillList,
)
from agents.screening_agent.services.scoring_service import score_candidate


def _build_candidate() -> CandidateProfile:
    """Create a candidate without verified dated experience entries.

    The candidate has three total career years, but the scorer must not
    automatically treat all three years as Python/FastAPI experience.
    """
    return CandidateProfile(
        skills=SkillCollection(
            normalized_skills=[
                "Python",
                "FastAPI",
                "Docker",
            ]
        ),
        total_experience_years=3,
        education=[
            "Bachelor of Computer Applications",
        ],
        keywords=[
            "backend",
            "api",
        ],
        source_text=(
            "Python FastAPI Docker backend API "
            "Bachelor of Computer Applications"
        ),
    )


def _build_jd() -> ParsedJD:
    """Create the common Python backend JD used by scoring tests."""
    return ParsedJD(
        required_skills=SkillList(
            normalized=[
                "Python",
                "FastAPI",
            ]
        ),
        preferred_skills=SkillList(
            normalized=[
                "Docker",
            ]
        ),
        minimum_experience_years=2,
        education_requirements=[
            "Bachelor's degree",
        ],
        keywords=[
            "backend",
            "api",
        ],
    )


def test_full_match_without_verified_experience_scores_80():
    """A complete skill match must not invent relevant experience.

    Score calculation:

    Required skills:  45
    Preferred skills: 15
    Experience:        0
    Education:        10
    Keywords:         10
    Total:            80

    Although total_experience_years is 3, there are no individual,
    dated experience entries proving Python/FastAPI experience.
    """
    candidate = _build_candidate()
    jd = _build_jd()

    match = MatchAnalysis(
        matched_required_skills=[
            "Python",
            "FastAPI",
        ],
        matched_preferred_skills=[
            "Docker",
        ],
        required_match_ratio=1.0,
        preferred_match_ratio=1.0,
    )

    result = score_candidate(
        candidate,
        jd,
        match,
    )

    assert result.required_skill_score == pytest.approx(45.0)
    assert result.preferred_skill_score == pytest.approx(15.0)
    assert result.skill_match_score == pytest.approx(60.0)

    # Total career experience alone must not receive relevant-
    # experience points.
    assert result.experience_score == pytest.approx(0.0)

    assert result.education_score == pytest.approx(10.0)
    assert result.keyword_score == pytest.approx(10.0)
    assert result.overall_score == pytest.approx(80.0)

    # The experience requirement is not supported by verified,
    # dated JD-relevant experience entries.
    assert (
        result
        .experience_assessment
        .candidate_relevant_experience_years
        == pytest.approx(0.0)
    )

    assert (
        result
        .experience_assessment
        .meets_minimum
        is False
    )

    # A candidate with unknown/unverified relevant experience
    # must not be automatically shortlisted.
    assert result.decision == "Needs Review"


def test_missing_preferred_skill_only_removes_preferred_points():
    """Missing an optional skill removes only its score component."""
    candidate = _build_candidate()
    jd = _build_jd()

    full_match = MatchAnalysis(
        matched_required_skills=[
            "Python",
            "FastAPI",
        ],
        matched_preferred_skills=[
            "Docker",
        ],
        required_match_ratio=1.0,
        preferred_match_ratio=1.0,
    )

    missing_preferred_match = MatchAnalysis(
        matched_required_skills=[
            "Python",
            "FastAPI",
        ],
        matched_preferred_skills=[],
        required_match_ratio=1.0,
        preferred_match_ratio=0.0,
    )

    full_result = score_candidate(
        candidate,
        jd,
        full_match,
    )

    missing_preferred_result = score_candidate(
        candidate,
        jd,
        missing_preferred_match,
    )

    assert full_result.required_skill_score == pytest.approx(45.0)
    assert missing_preferred_result.required_skill_score == pytest.approx(
        45.0
    )

    assert full_result.preferred_skill_score == pytest.approx(15.0)
    assert missing_preferred_result.preferred_skill_score == pytest.approx(
        0.0
    )

    # Only the 15 preferred-skill points should be removed.
    assert (
        full_result.overall_score
        - missing_preferred_result.overall_score
    ) == pytest.approx(15.0)

    assert missing_preferred_result.overall_score == pytest.approx(65.0)

    # Missing an optional skill is not the reason for rejection.
    # The candidate remains in review because relevant experience
    # is unverified.
    assert missing_preferred_result.decision == "Needs Review"


def test_partial_required_skill_match_reduces_required_score():
    """Required-skill score must follow the required match ratio."""
    candidate = _build_candidate()
    jd = _build_jd()

    match = MatchAnalysis(
        matched_required_skills=[
            "Python",
        ],
        matched_preferred_skills=[
            "Docker",
        ],
        required_match_ratio=0.5,
        preferred_match_ratio=1.0,
    )

    result = score_candidate(
        candidate,
        jd,
        match,
    )

    # 50% of the 45 required-skill weight.
    assert result.required_skill_score == pytest.approx(22.5)

    # Required coverage below the shortlist gate: preferred skills cannot
    # compensate for missing mandatory requirements.
    assert result.preferred_skill_score == pytest.approx(7.5)

    assert result.skill_match_score == pytest.approx(30.0)
    assert result.experience_score == pytest.approx(0.0)
    assert result.education_score == pytest.approx(10.0)
    assert result.keyword_score == pytest.approx(10.0)

    assert result.overall_score == pytest.approx(50.0)
    assert result.decision != "Shortlisted"


def test_total_experience_does_not_replace_relevant_experience():
    """Protect against reintroducing the old experience-scoring bug."""
    candidate = CandidateProfile(
        skills=SkillCollection(
            normalized_skills=[
                "Python",
                "FastAPI",
            ]
        ),
        total_experience_years=10,
        education=[
            "Bachelor of Computer Applications",
        ],
        keywords=[
            "backend",
            "api",
        ],
        source_text="Python FastAPI backend API",
    )

    jd = ParsedJD(
        required_skills=SkillList(
            normalized=[
                "Python",
                "FastAPI",
            ]
        ),
        preferred_skills=SkillList(
            normalized=[]
        ),
        minimum_experience_years=2,
        education_requirements=[
            "Bachelor's degree",
        ],
        keywords=[
            "backend",
            "api",
        ],
    )

    match = MatchAnalysis(
        matched_required_skills=[
            "Python",
            "FastAPI",
        ],
        matched_preferred_skills=[],
        required_match_ratio=1.0,
        preferred_match_ratio=0.0,
    )

    result = score_candidate(
        candidate,
        jd,
        match,
    )

    # Even ten total years cannot be assumed to be ten years of
    # relevant Python backend experience.
    assert result.experience_score == pytest.approx(0.0)

    assert (
        result
        .experience_assessment
        .candidate_total_experience_years
        == pytest.approx(10.0)
    )

    assert (
        result
        .experience_assessment
        .candidate_relevant_experience_years
        == pytest.approx(0.0)
    )

    assert (
        result
        .experience_assessment
        .meets_minimum
        is False
    )

    assert result.decision == "Needs Review"


def test_zero_required_skill_match_scores_zero_and_rejects():
    """Unmatched required skills must not earn required/preferred points."""
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Marketing", "MBA"]),
        total_experience_years=3.25,
        education=["Master of Business Administration (MBA) - Marketing"],
        keywords=["business", "support", "solutions"],
        source_text=(
            "Rajiv Agarwal MBA Marketing intern business enterprise "
            "support solutions amp"
        ),
    )
    jd = ParsedJD(
        job_title="Python Developer (AI/ML Engineer)",
        required_skills=SkillList(
            normalized=[
                "Python",
                "Machine Learning",
                "TensorFlow",
                "PyTorch",
            ]
        ),
        preferred_skills=SkillList(normalized=["FastAPI", "SQL"]),
        minimum_experience_years=3,
        education_requirements=[
            "Bachelor's degree in Computer Science or related field",
        ],
        keywords=["python", "model", "business", "support", "solutions", "amp"],
    )
    match = MatchAnalysis(
        matched_required_skills=[],
        missing_required_skills=[
            "Python",
            "Machine Learning",
            "TensorFlow",
            "PyTorch",
        ],
        matched_preferred_skills=[],
        missing_preferred_skills=["FastAPI", "SQL"],
        required_match_ratio=0.0,
        preferred_match_ratio=0.0,
    )

    result = score_candidate(candidate, jd, match)

    assert result.required_skill_score == pytest.approx(0.0)
    assert result.preferred_skill_score == pytest.approx(0.0)
    assert result.education_score < 3.0
    assert result.keyword_score == pytest.approx(0.0)
    assert result.overall_score < 20.0
    assert result.decision == "Rejected"
    assert "No required JD skills were matched" in " ".join(result.concerns)


def test_partial_required_coverage_matches_matched_count():
    """12 of 19 required skills must score 12/19 of the required weight."""
    candidate = _build_candidate()
    jd = ParsedJD(
        required_skills=SkillList(
            normalized=["Python"] + [f"Skill{i}" for i in range(18)]
        ),
        preferred_skills=SkillList(normalized=[]),
        minimum_experience_years=2,
        education_requirements=["Bachelor's degree"],
        keywords=["backend"],
    )
    match = MatchAnalysis(
        matched_required_skills=["Python"] + [f"Skill{i}" for i in range(11)],
        missing_required_skills=[f"Skill{i}" for i in range(11, 18)],
        matched_preferred_skills=[],
        missing_preferred_skills=[],
        required_match_ratio=12 / 19,
        preferred_match_ratio=1.0,
    )

    result = score_candidate(candidate, jd, match)

    assert result.required_skill_score == pytest.approx(45.0 * 12 / 19, abs=0.05)
    assert result.preferred_skill_score == pytest.approx(15.0)
    assert result.decision != "Rejected"


def test_experience_range_scores_against_floor_not_upper_bound():
    """For '4-6 years', meeting 4 years is full credit; 3.67 is scaled to the floor."""
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python", "FastAPI", "PyTorch"]),
        experience_entries=[
            ExperienceEntry(
                role="Python Developer",
                company="Acme",
                entry_type="employment",
                start_date="Jan 2022",
                end_date="Aug 2025",
                start_month_index=2022 * 12,
                end_month_index=2025 * 12 + 7,
                text="Python FastAPI PyTorch backend and AI/ML development",
            )
        ],
        education=["Bachelor of Technology in Computer Science"],
        source_text="Python FastAPI PyTorch Bachelor of Technology",
    )
    # Jan 2022 – Aug 2025 inclusive = 44 months ≈ 3.67 years
    assert candidate.experience_entries[0].duration_years == pytest.approx(3.67, abs=0.02)

    jd = ParsedJD(
        job_title="Python Developer",
        required_skills=SkillList(normalized=["Python", "FastAPI", "PyTorch"]),
        experience_requirements=[
            "4-6 years of experience in Python development",
            "Minimum 3 years of hands-on experience in AI/ML solution development",
        ],
        minimum_experience_years=4,
        maximum_experience_years=6,
        experience_requirement_kind="professional",
        education_requirements=["Bachelor's degree in Computer Science"],
    )
    match = MatchAnalysis(
        matched_required_skills=["Python", "FastAPI", "PyTorch"],
        missing_required_skills=[],
        required_match_ratio=1.0,
        preferred_match_ratio=1.0,
    )
    score = score_candidate(candidate, jd, match)

    assert score.experience_assessment.years_toward_requirement == pytest.approx(3.67, abs=0.02)
    assert score.experience_assessment.meets_minimum is False
    assert score.hard_requirement_status == "FAIL"
    # Full credit at the 4-year floor → 3.67/4 * 20 ≈ 18.35 (not 20).
    assert score.experience_score == pytest.approx(20.0 * (3.67 / 4.0), abs=0.15)
    assert score.experience_score < settings.ATS_EXPERIENCE_WEIGHT


def test_in_range_years_get_full_experience_score():
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python"]),
        experience_entries=[
            ExperienceEntry(
                role="Python Developer",
                entry_type="employment",
                start_month_index=2022 * 12,
                end_month_index=2026 * 12 + 2,
                text="Python development",
            )
        ],
        total_experience_years=4.25,
    )
    jd = ParsedJD(
        required_skills=SkillList(normalized=["Python"]),
        experience_requirements=["4-6 years of experience in Python development"],
        minimum_experience_years=4,
        maximum_experience_years=6,
        experience_requirement_kind="professional",
    )
    match = MatchAnalysis(
        matched_required_skills=["Python"],
        required_match_ratio=1.0,
        preferred_match_ratio=1.0,
    )
    score = score_candidate(candidate, jd, match)
    assert score.experience_assessment.professional_experience_years == pytest.approx(4.25, abs=0.02)
    assert score.experience_assessment.meets_minimum is True
    assert score.experience_score == pytest.approx(settings.ATS_EXPERIENCE_WEIGHT)


def test_experience_range_full_credit_at_upper_bound():
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python", "FastAPI"]),
        experience_entries=[
            ExperienceEntry(
                role="Python Developer",
                entry_type="employment",
                start_date="Jan 2019",
                end_date="Jan 2025",
                start_month_index=2019 * 12,
                end_month_index=2025 * 12,
                text="Python FastAPI development",
            )
        ],
        education=["B.Tech Computer Science"],
        source_text="Python FastAPI",
    )
    jd = ParsedJD(
        required_skills=SkillList(normalized=["Python", "FastAPI"]),
        experience_requirements=["4-6 years of experience in Python development"],
        minimum_experience_years=4,
        maximum_experience_years=6,
        experience_requirement_kind="professional",
    )
    match = MatchAnalysis(
        matched_required_skills=["Python", "FastAPI"],
        missing_required_skills=[],
        required_match_ratio=1.0,
        preferred_match_ratio=1.0,
    )
    score = score_candidate(candidate, jd, match)
    assert score.experience_assessment.years_toward_requirement >= 6.0
    assert score.experience_assessment.meets_minimum is True
    assert score.experience_score == pytest.approx(settings.ATS_EXPERIENCE_WEIGHT)
    assert score.hard_requirement_status == "PASS"


def test_empty_or_fake_jd_does_not_score_100():
    """A JD with no requirements must not award a perfect match."""
    candidate = _build_candidate()
    jd = ParsedJD(job_title="Job description")
    match = MatchAnalysis(
        matched_required_skills=[],
        missing_required_skills=[],
        required_match_ratio=1.0,
        preferred_match_ratio=1.0,
    )
    score = score_candidate(candidate, jd, match)
    assert score.overall_score == 0
    assert score.required_skill_score == 0
    assert score.preferred_skill_score == 0
    assert score.experience_score == 0
    assert score.education_score == 0
    assert score.keyword_score == 0
    assert score.decision == "Needs Review"
    assert score.hard_requirement_status == "FAIL"
    assert any("too thin or empty" in item.lower() for item in score.concerns)