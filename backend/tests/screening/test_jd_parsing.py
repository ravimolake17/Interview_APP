from agents.screening_agent.config import settings
from agents.screening_agent.services.jd_parser import parse_job_description


JD = """
Job Title: Python Backend Developer

Required Skills:
- Python
- FastAPI
- PostgreSQL
- Minimum 2 years of backend experience

Preferred Skills:
- Docker
- AWS

Responsibilities:
- Develop REST APIs
- Maintain backend services

Education:
Bachelor's degree in Computer Science or a related field.
"""


def test_jd_parser_separates_required_and_preferred(monkeypatch):
    monkeypatch.setattr(settings, "USE_LLM_FOR_JD_PARSING", False)
    parsed = parse_job_description(JD)
    assert parsed.job_title == "Python Backend Developer"
    assert {"Python", "FastAPI", "PostgreSQL"}.issubset(set(parsed.required_skills.normalized))
    assert {"Docker", "AWS"}.issubset(set(parsed.preferred_skills.normalized))
    assert parsed.minimum_experience_years == 2
    assert parsed.education_requirements
    assert any("Develop REST APIs" in item for item in parsed.responsibilities)


def test_empty_jd_is_rejected():
    try:
        parse_job_description("   ")
    except ValueError as exc:
        assert "empty" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError")


def test_inline_required_and_preferred_headings_are_parsed(monkeypatch):
    monkeypatch.setattr(settings, "USE_LLM_FOR_JD_PARSING", False)
    parsed = parse_job_description(
        "Job Title: Backend Developer\n"
        "Required Skills: Python, FastAPI, PostgreSQL\n"
        "Preferred Skills: Docker, AWS\n"
        "Minimum 2 years experience"
    )
    assert parsed.required_skills.normalized == ["Python", "FastAPI", "PostgreSQL"]
    assert parsed.preferred_skills.normalized == ["Docker", "AWS"]


def test_responsibility_only_technology_is_not_forced_into_required_skills(monkeypatch):
    monkeypatch.setattr(settings, "USE_LLM_FOR_JD_PARSING", False)
    parsed = parse_job_description(
        "Data Engineer\nResponsibilities:\n- Maintain Python services and data pipelines"
    )
    assert "Python" not in parsed.required_skills.normalized


def test_preferred_qualifications_are_not_promoted_to_required(monkeypatch):
    monkeypatch.setattr(settings, "USE_LLM_FOR_JD_PARSING", False)
    parsed = parse_job_description(
        "Backend Developer\n"
        "Preferred Qualifications:\n"
        "- Python\n"
        "- Docker"
    )
    assert parsed.required_skills.normalized == []
    assert parsed.preferred_skills.normalized == ["Python", "Docker"]


def test_preferred_experience_is_not_converted_to_minimum(monkeypatch):
    monkeypatch.setattr(settings, "USE_LLM_FOR_JD_PARSING", False)
    parsed = parse_job_description(
        "Backend Developer\nPreferred: 5 years experience"
    )
    assert parsed.minimum_experience_years is None
    assert parsed.preferred_experience_years == 5


HR_JD = """
## Senior HR Operations Manager

## Required Skills
- HR policies and procedures
- Orientation and onboarding
- Employee relations
- Recruitment lifecycle management
- Training and employee development
- Performance management
- Benefits administration
- HRIS administration
- HR program and project management
- Workforce reporting and analytics

## Required Qualifications
- Bachelor's degree in Human Resources, Business Administration, Management, Arts, or a related discipline.
- At least 8 years of progressive professional experience in Human Resources.
- Strong communication, stakeholder-management, problem-solving, and organisational skills.
"""


def test_hr_required_skills_section_is_extracted_not_soft_skills(monkeypatch):
    """Non-tech JDs must keep explicit Required Skills bullets, not Qualifications soft skills."""
    monkeypatch.setattr(settings, "USE_LLM_FOR_JD_PARSING", False)
    parsed = parse_job_description(HR_JD)
    required = {skill.casefold() for skill in parsed.required_skills.normalized}

    assert "hr policies and procedures" in required
    assert "employee relations" in required
    assert "hris administration" in required
    assert "workforce reporting and analytics" in required
    assert len(parsed.required_skills.normalized) >= 8

    # Soft skills buried in Qualifications must not replace the skill list.
    assert "communication" not in required
    assert "problem solving" not in required
    assert parsed.minimum_experience_years == 8


def test_explicit_skill_bullets_survive_without_tech_catalog(monkeypatch):
    monkeypatch.setattr(settings, "USE_LLM_FOR_JD_PARSING", False)
    parsed = parse_job_description(
        "Operations Lead\n"
        "Required Skills:\n"
        "- Vendor coordination\n"
        "- Inventory planning\n"
        "- Safety compliance\n"
    )
    required = {skill.casefold() for skill in parsed.required_skills.normalized}
    assert "vendor coordination" in required
    assert "inventory planning" in required
    assert "safety compliance" in required


PYTHON_AI_JD = """
Job Description – Python Developer (AI/ML Engineer)
Role Purpose
We are seeking a highly motivated Python Developer (AI/ML Engineer).

Required Technical Skills
**Programming &amp; Development**
- Python (Advanced)
- Object-Oriented Programming (OOP)
- REST API Development
- FastAPI / Flask / Django
**AI &amp; Machine Learning**
- TensorFlow / PyTorch
- Pandas, NumPy
- Machine Learning Algorithms
- NLP (Natural Language Processing)
**Generative AI &amp; LLMs**
- Prompt Engineering
- RAG (Retrieval-Augmented Generation)
**Data &amp; Integration**
- SQL and Database Development
- API Integration
- JSON, XML
**Cloud &amp; DevOps**
- Azure OpenAI
- CI/CD Pipelines
- Docker (Preferred)

Experience
4–6 years of experience in Python development.
Minimum 3 years of hands-on experience in AI/ML solution development.
"""


def test_docling_categorized_skills_are_not_split_into_fake_entries(monkeypatch):
    """Docling HTML entities and category subheadings must not inflate required skills."""
    monkeypatch.setattr(settings, "USE_LLM_FOR_JD_PARSING", False)
    parsed = parse_job_description(PYTHON_AI_JD)
    required = {skill.casefold() for skill in parsed.required_skills.normalized}

    assert parsed.job_title == "Python Developer (AI/ML Engineer)"
    # Strictest floor across "4-6 years" and "Minimum 3 years hands-on".
    assert parsed.minimum_experience_years == 4
    assert parsed.maximum_experience_years == 6
    assert "python (advanced)" in required or any("python" in skill for skill in required)
    assert "fastapi" in required
    assert "flask" in required
    assert "django" in required
    assert "tensorflow" in required
    assert "pytorch" in required
    assert "pandas" in required
    assert "numpy" in required
    assert "prompt engineering" in required
    assert "rag" in required or any("rag" in skill for skill in required)
    assert "ci/cd pipelines" in required or "ci/cd" in required

    bogus = {
        "programming",
        "development",
        "programming &",
        "ai &",
        "data &",
        "cloud &",
        "generative ai &",
        "llms",
        "integration",
        "devops",
        "machine learning",
        "ci",
        "cd pipelines",
    }
    assert not bogus.intersection(required)
    assert len(parsed.required_skills.normalized) <= 22
