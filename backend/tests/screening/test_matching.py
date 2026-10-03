from agents.screening_agent.schemas.ats import ParsedJD, SkillCollection, SkillList
from agents.screening_agent.services.matching_service import analyze_skill_match


def test_required_preferred_and_additional_skills_are_separated():
    candidate = SkillCollection(normalized_skills=["Python", "FastAPI", "MySQL"])
    jd = ParsedJD(
        required_skills=SkillList(normalized=["Python", "FastAPI", "PostgreSQL"]),
        preferred_skills=SkillList(normalized=["Docker"]),
    )
    match = analyze_skill_match(candidate, jd)
    assert match.matched_required_skills == ["Python", "FastAPI"]
    assert match.missing_required_skills == ["PostgreSQL"]
    assert match.missing_preferred_skills == ["Docker"]
    assert match.additional_candidate_skills == ["MySQL"]
    assert match.required_match_ratio == 0.6667


def test_matching_is_case_insensitive_and_canonical():
    from agents.screening_agent.schemas.ats import ParsedJD, SkillCollection, SkillList
    from agents.screening_agent.services.matching_service import analyze_skill_match

    result = analyze_skill_match(
        SkillCollection(normalized_skills=["python", "postgres"]),
        ParsedJD(required_skills=SkillList(normalized=["Python", "PostgreSQL"])),
    )

    assert result.matched_required_skills == ["Python", "PostgreSQL"]
    assert result.missing_required_skills == []
    assert result.required_match_ratio == 1.0
