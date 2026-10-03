"""Page-break / orphaned-heading repairs for resume section detection."""

from agents.screening_agent.services.resume_parser import parse_resume
from agents.screening_agent.services.resume_profile_service import (
    _extract_education,
    build_candidate_profile,
)
from agents.screening_agent.services.section_detector import detect_sections


def test_education_heading_on_prior_page_keeps_following_degree_line():
    """EDUCATION at end of page 1 + degree on page 2 must stay one section."""
    text = """
Jane Doe
jane@example.com

SELECTED PROJECTS
ML Customer Churn Model | Python, FastAPI

EDUCATION
\f
Bachelor of Technology in Computer Science — Jawaharlal Nehru Technological University | 2017 – 2021

CERTIFICATIONS
Python for Data Science
"""
    sections = detect_sections(text)
    by_heading = {s["heading"].casefold().lstrip("#").strip(): s["body"] for s in sections}

    assert "education" in by_heading
    education_body = by_heading["education"]
    assert "bachelor of technology" in education_body.casefold()
    assert "jawaharlal" in education_body.casefold()
    assert "2017" in education_body


def test_education_orphaned_as_fake_heading_is_reattached():
    """If the degree line is mis-detected as its own heading, repair it."""
    # Force the shape that page-break repair must fix: empty EDUCATION, then
    # a following non-known heading block containing the degree details.
    sections = detect_sections(
        "Name\n"
        "EDUCATION\n"
        "\n"
        "Bachelor of Technology in Computer Science\n"
        "Jawaharlal Nehru Technological University | 2017 – 2021\n"
        "CERTIFICATIONS\n"
        "Java Spring Boot\n"
    )
    education = next(s for s in sections if "education" in s["heading"].casefold())
    assert "bachelor" in education["body"].casefold()
    assert "2017" in education["body"]


def test_build_profile_recovers_education_after_page_break(monkeypatch):
    from agents.screening_agent.config import settings

    monkeypatch.setattr(settings, "USE_LLM_FOR_RESUME_PARSING", False)
    parsed = parse_resume(
        "Alex Candidate\n"
        "SELECTED PROJECTS\n"
        "Order System | Java\n"
        "EDUCATION\n"
        "\f"
        "Bachelor of Technology in Computer Science — Example University | 2017 – 2021\n"
        "CERTIFICATIONS\n"
        "Python for Data Science\n"
    )
    profile = build_candidate_profile(parsed)
    assert profile.education
    joined = " ".join(profile.education).casefold()
    assert "bachelor" in joined or "b.tech" in joined or "technology" in joined


def test_extract_education_ignores_bare_heading_only():
    rows = [{"heading": "Education", "text": "Education", "items": []}]
    assert _extract_education(rows, "Education\n") == []


def test_reconcile_fills_empty_education_from_secondary_text_layer():
    """Docling-like primary text drops cross-page body; text-layer secondary restores it."""
    from agents.screening_agent.services.docling_extractor import (
        _reconcile_missing_section_bodies,
    )

    primary = (
        "Candidate Name\n"
        "SELECTED PROJECTS\n"
        "Sample Project\n"
        "EDUCATION\n"
        "CERTIFICATIONS\n"
        "Cloud Fundamentals\n"
    )
    secondary = (
        "Candidate Name\n"
        "SELECTED PROJECTS\n"
        "Sample Project\n"
        "EDUCATION\n"
        "\f"
        "Bachelor of Technology in Computer Science — Example State University | 2017 – 2021\n"
        "CERTIFICATIONS\n"
        "Cloud Fundamentals\n"
    )
    merged, recovered = _reconcile_missing_section_bodies(primary, secondary)
    assert any("education" in item.casefold() for item in recovered)
    assert "bachelor of technology" in merged.casefold()
    assert "example state university" in merged.casefold()

    sections = detect_sections(merged)
    education = next(s for s in sections if "education" in s["heading"].casefold())
    assert "bachelor" in education["body"].casefold()
    assert "2017" in education["body"]


def test_title_case_project_heading_is_not_swallowed_by_education():
    text = (
        "Name Candidate\n"
        "name@example.com\n"
        "Education\n"
        "Bachelor of Engineering\n"
        "Example State University\n"
        "Key Data Science Projects\n"
        "Developed an automated classifier with 96% accuracy.\n"
        "Skills\nPython\n"
    )
    sections = detect_sections(text)
    education = next(s for s in sections if "education" in s["heading"].casefold())
    assert "bachelor" in education["body"].casefold()
    assert "developed" not in education["body"].casefold()
    assert any("project" in s["heading"].casefold() for s in sections)


def test_reconcile_recovers_education_when_docling_puts_a_job_date_there():
    """Two-column PDFs: layout engine fills EDUCATION with a job date; text layer has the degree."""
    from agents.screening_agent.services.docling_extractor import (
        _reconcile_missing_section_bodies,
    )
    from agents.screening_agent.services.resume_parser import parse_resume
    from agents.screening_agent.services.resume_profile_service import (
        build_candidate_profile,
    )

    primary = (
        "## SUMMARY\nAI engineer.\n"
        "## WORK EXPERIENCE\nSept 2025 - Present\nEngineered pipelines.\n"
        "## EDUCATION\nSept 2024 - Sept 2025\n"
        "## PROJECTS\nBuilt a chatbot.\n"
    )
    secondary = (
        "Candidate Name\n"
        "candidate@example.com\n"
        "EDUCATION\n"
        "WORK EXPERIENCE\n"
        "Bachelor Of Computer Science (July 2020-june 2023)\n"
        "Example State University\n"
        "CGPA: 9.53\n"
        "Programming Languages: Python, SQL, FastAPI\n"
        "Sept 2025 - Present\n"
        "Engineered pipelines.\n"
    )
    merged, recovered = _reconcile_missing_section_bodies(primary, secondary)
    assert any("education" in item.casefold() for item in recovered)
    assert "bachelor of computer science" in merged.casefold()
    assert "example state university" in merged.casefold()
    assert "9.53" in merged

    parsed = parse_resume(merged)
    parsed["source_text"] = merged
    profile = build_candidate_profile(parsed)
    joined = " ".join(profile.education).casefold()
    assert "bachelor of computer science" in joined
    assert "example state university" in joined
    assert "programming languages" not in joined

