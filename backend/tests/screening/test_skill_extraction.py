from agents.screening_agent.services.skill_extractor import extract_resume_skills


def test_skill_extraction_keeps_raw_normalized_and_categories():
    resume = {
        "sections": [
            {
                "heading": "Technical Skills",
                "raw_text": "Languages: python3, JavaScript\nFrameworks: ReactJS, FastAPI\nDatabase: Postgres",
            },
            {
                "heading": "Experience",
                "raw_text": "Built REST APIs using Python and Docker.",
            },
        ]
    }
    result = extract_resume_skills(resume)
    assert {"Python", "JavaScript", "React", "FastAPI", "PostgreSQL", "REST API", "Docker"}.issubset(
        set(result.normalized_skills)
    )
    assert "programming_languages" in result.skills_by_category
    assert result.evidence


def test_skill_extraction_does_not_invent_absent_skill():
    resume = {"sections": [{"heading": "Summary", "raw_text": "Business graduate and analyst."}]}
    result = extract_resume_skills(resume)
    assert "Python" not in result.normalized_skills


def test_unknown_explicit_skill_is_preserved_without_hallucination():
    resume = {"sections": [{"heading": "Technical Skills", "raw_text": "Snowflake, dbt"}]}
    result = extract_resume_skills(resume)
    assert "Snowflake" in result.normalized_skills
    assert "dbt" in result.normalized_skills
