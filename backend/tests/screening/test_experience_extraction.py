"""Regression tests for generic experience date parsing and type breakdown."""

from __future__ import annotations

from agents.screening_agent.config import settings
from agents.screening_agent.schemas.ats import (
    CandidateProfile,
    ExperienceEntry,
    MatchAnalysis,
    ParsedJD,
    SkillCollection,
    SkillList,
)
from agents.screening_agent.services.resume_profile_service import (
    _duration_from_text,
    _parse_month,
    build_candidate_profile,
)
from agents.screening_agent.services.scoring_service import (
    evaluate_relevant_experience,
    score_candidate,
)


def test_day_inclusive_dates_parse_to_months():
    """Feb 16, 2025 – Jun 12, 2025 must parse (internship regression)."""
    start, end, start_idx, end_idx, months = _duration_from_text(
        "Deep Learning Intern\nFeb 16, 2025 – Jun 12, 2025\nPyTorch MONAI"
    )
    assert start_idx is not None and end_idx is not None
    assert months == 5  # inclusive Feb–Jun
    assert "feb" in start.casefold()
    assert "jun" in end.casefold()


def test_shared_year_date_range_february_to_june():
    """Resume style 'February 16 - June 12, 2025' (year only on end)."""
    _start, _end, start_idx, end_idx, months = _duration_from_text(
        "Duration:\nFebruary 16 - June 12, 2025\nDeep learning intern"
    )
    assert start_idx is not None and end_idx is not None
    assert months == 5
    assert start_idx == 2025 * 12 + 1
    assert end_idx == 2025 * 12 + 5


def test_multiple_date_formats():
    cases = [
        ("Jan 2024 - Mar 2025", 15),
        ("January 2024 - March 2025", 15),
        ("2024 - 2025", 13),  # Jan 2024 through Jan 2025 inclusive months
        ("02/2024 - 03/2025", 14),
        ("Feb 16, 2025 - Jun 12, 2025", 5),
        ("16 Feb 2025 - 12 Jun 2025", 5),
        ("Jan 2024 - Present", None),  # present depends on now; just ensure parses
    ]
    for text, expected_months in cases:
        _start, _end, start_idx, end_idx, months = _duration_from_text(text)
        assert start_idx is not None, text
        assert end_idx is not None, text
        if expected_months is not None:
            assert months == expected_months, text


def test_abbreviated_linkedin_date_ranges_parse():
    start, end, start_idx, end_idx, months = _duration_from_text("Jun '17 May '20")
    assert start_idx is not None and end_idx is not None
    assert start_idx == 2017 * 12 + 5
    assert end_idx == 2020 * 12 + 4
    assert months == 36


def test_parse_month_present_aliases():
    assert _parse_month("present") is not None
    assert _parse_month("current") is not None
    assert _parse_month("till date") is not None


def test_overlapping_jobs_are_not_double_counted():
    """Concurrent roles must merge calendar months."""
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python", "FastAPI"]),
        experience_entries=[
            ExperienceEntry(
                role="Backend Engineer",
                company="A",
                entry_type="employment",
                start_date="Jan 2022",
                end_date="Jan 2024",
                start_month_index=2022 * 12,
                end_month_index=2024 * 12,
                text="Python FastAPI backend services",
            ),
            ExperienceEntry(
                role="API Developer",
                company="B",
                entry_type="employment",
                start_date="Jun 2023",
                end_date="Dec 2024",
                start_month_index=2023 * 12 + 5,
                end_month_index=2024 * 12 + 11,
                text="Python FastAPI REST API",
            ),
        ],
        source_text="Python FastAPI",
    )
    jd = ParsedJD(
        job_title="Python Developer",
        required_skills=SkillList(normalized=["Python", "FastAPI"]),
        experience_requirements=["3 years Python development"],
        minimum_experience_years=3,
    )
    assessment = evaluate_relevant_experience(candidate, jd)
    # Jan 2022 – Dec 2024 inclusive = 36 months = 3.0 years (not 3+1.5)
    assert assessment.candidate_relevant_experience_years == 3.0
    assert assessment.professional_experience_years == 3.0


def test_internship_and_projects_are_separated():
    candidate = CandidateProfile(
        skills=SkillCollection(
            normalized_skills=["Python", "PyTorch", "TensorFlow", "FastAPI"]
        ),
        experience_entries=[
            ExperienceEntry(
                role="Deep Learning Intern",
                company="Lab",
                entry_type="internship",
                start_date="Feb 16, 2025",
                end_date="Jun 12, 2025",
                start_month_index=2025 * 12 + 1,
                end_month_index=2025 * 12 + 5,
                text="Developed MeshSegNet using PyTorch and MONAI Python",
            ),
            ExperienceEntry(
                role="Potato Leaf Disease Detection",
                entry_type="project",
                start_date="Nov 2024",
                end_date="Jan 2025",
                start_month_index=2024 * 12 + 10,
                end_month_index=2025 * 12,
                text="Python TensorFlow Keras FastAPI OpenCV",
            ),
            ExperienceEntry(
                role="Crop Recommendation System",
                entry_type="project",
                start_date="May 2023",
                end_date="Aug 2023",
                start_month_index=2023 * 12 + 4,
                end_month_index=2023 * 12 + 7,
                text="Python Flask SQLite",
            ),
        ],
        source_text="Python PyTorch TensorFlow FastAPI",
    )
    jd = ParsedJD(
        job_title="Python Developer (AI/ML Engineer)",
        required_skills=SkillList(normalized=["Python", "PyTorch", "TensorFlow"]),
        experience_requirements=[
            "4-6 years of experience in Python development",
            "Minimum 3 years of hands-on experience in AI/ML solution development",
        ],
        minimum_experience_years=3,
    )
    assessment = evaluate_relevant_experience(candidate, jd)
    assert assessment.internship_experience_years == 0.42  # 5/12
    assert assessment.academic_project_years > 0
    assert assessment.professional_experience_years == 0
    # Total relevant = professional only (internships/projects excluded).
    assert assessment.candidate_relevant_experience_years == 0
    assert assessment.relevant_hands_on_experience_years == (
        round(
            assessment.internship_experience_years
            + assessment.academic_project_years,
            2,
        )
    )
    assert assessment.meets_minimum is False
    assert "internship" in assessment.result.casefold()
    assert "project" in assessment.result.casefold()


def test_unrelated_html_project_not_counted_for_aiml_jd():
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["HTML", "CSS"]),
        experience_entries=[
            ExperienceEntry(
                role="College Website",
                entry_type="project",
                start_date="Jan 2023",
                end_date="Jun 2023",
                start_month_index=2023 * 12,
                end_month_index=2023 * 12 + 5,
                text="Created a college website using HTML and CSS",
            )
        ],
        source_text="HTML CSS college website",
    )
    jd = ParsedJD(
        job_title="AI/ML Engineer",
        required_skills=SkillList(normalized=["Python", "PyTorch"]),
        experience_requirements=["3 years AI/ML solution development"],
        minimum_experience_years=3,
    )
    assessment = evaluate_relevant_experience(candidate, jd)
    assert assessment.candidate_relevant_experience_years == 0
    assert assessment.academic_project_years == 0


def test_hard_requirement_fail_on_experience_gap(monkeypatch):
    monkeypatch.setattr(settings, "ATS_SHORTLIST_THRESHOLD", 50)
    monkeypatch.setattr(settings, "ATS_REVIEW_THRESHOLD", 30)
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python", "FastAPI"]),
        experience_entries=[
            ExperienceEntry(
                role="Intern",
                entry_type="internship",
                start_date="Jan 2025",
                end_date="Mar 2025",
                start_month_index=2025 * 12,
                end_month_index=2025 * 12 + 2,
                text="Python FastAPI",
            )
        ],
        education=["BCA"],
        source_text="Python FastAPI BCA",
    )
    jd = ParsedJD(
        required_skills=SkillList(normalized=["Python", "FastAPI"]),
        minimum_experience_years=5,
        experience_requirements=["5 years Python"],
        education_requirements=["Bachelor's degree"],
    )
    match = MatchAnalysis(
        matched_required_skills=["Python", "FastAPI"],
        missing_required_skills=[],
        required_match_ratio=1.0,
        preferred_match_ratio=1.0,
    )
    score = score_candidate(candidate, jd, match)
    assert score.hard_requirement_status == "FAIL"
    assert any("MANDATORY EXPERIENCE GAP" in reason for reason in score.hard_requirement_reasons)
    assert score.decision != "Shortlisted"


def test_internship_section_extracted_from_resume_text(monkeypatch):
    monkeypatch.setattr(settings, "USE_LLM_FOR_RESUME_PARSING", False)
    parsed = {
        "sections": [
            {
                "heading": "Internship",
                "items": [],
                "raw_text": (
                    "Deep Learning Intern — Research Lab\n"
                    "Feb 16, 2025 – Jun 12, 2025\n"
                    "Developed and trained a MeshSegNet deep learning model "
                    "using PyTorch and MONAI for 3D medical imaging."
                ),
            },
            {
                "heading": "Projects",
                "items": [],
                "raw_text": (
                    "Tater-Check Disease Detection\n"
                    "Nov 2024 – Jan 2025\n"
                    "Python TensorFlow FastAPI"
                ),
            },
        ],
        "extraction_method": "rule_based_fallback",
    }
    profile = build_candidate_profile(parsed)
    types = {entry.entry_type for entry in profile.experience_entries}
    assert "internship" in types
    assert "project" in types
    internship = next(e for e in profile.experience_entries if e.entry_type == "internship")
    assert internship.duration_months == 5
    assert internship.start_month_index is not None
    # Internship must not inflate professional total years.
    assert profile.total_experience_years in (None, 0)


def test_full_time_plus_internship_not_merged_into_professional():
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python", "FastAPI"]),
        experience_entries=[
            ExperienceEntry(
                role="Software Engineer",
                company="Acme",
                entry_type="employment",
                start_date="Jan 2023",
                end_date="Jan 2025",
                start_month_index=2023 * 12,
                end_month_index=2025 * 12,
                text="Python FastAPI backend",
            ),
            ExperienceEntry(
                role="Python Intern",
                company="Startup",
                entry_type="internship",
                start_date="Jan 2022",
                end_date="Jul 2022",
                start_month_index=2022 * 12,
                end_month_index=2022 * 12 + 6,
                text="Python FastAPI",
            ),
        ],
        source_text="Python FastAPI",
    )
    jd = ParsedJD(
        required_skills=SkillList(normalized=["Python", "FastAPI"]),
        experience_requirements=["2 years professional Python experience"],
        minimum_experience_years=2,
        experience_requirement_kind="professional",
    )
    assessment = evaluate_relevant_experience(candidate, jd)
    assert assessment.professional_experience_years == 2.08  # Jan 2023–Jan 2025 = 25 months
    assert abs(assessment.internship_experience_years - 0.58) < 0.02  # 7 months
    assert assessment.professional_experience_years < 2.6
    assert assessment.meets_minimum is True
    assert assessment.years_toward_requirement == assessment.professional_experience_years


def test_jd_explicitly_including_internships_allows_contribution():
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python", "FastAPI"]),
        experience_entries=[
            ExperienceEntry(
                role="Python Backend Engineer",
                entry_type="employment",
                start_date="Jan 2022",
                end_date="Jan 2024",
                start_month_index=2022 * 12,
                end_month_index=2024 * 12,
                text="Python FastAPI REST API backend development",
            ),
            ExperienceEntry(
                role="Python Intern",
                entry_type="internship",
                start_date="Jan 2021",
                end_date="Jan 2022",
                start_month_index=2021 * 12,
                end_month_index=2022 * 12,
                text="Python FastAPI backend development",
            ),
        ],
        source_text="Python FastAPI",
    )
    jd = ParsedJD(
        job_title="Python Developer",
        required_skills=SkillList(normalized=["Python", "FastAPI"]),
        experience_requirements=[
            "3 years relevant experience including internships"
        ],
        minimum_experience_years=3,
        experience_requirement_kind="internship_included",
        allows_internship_for_requirement=True,
    )
    assessment = evaluate_relevant_experience(candidate, jd)
    assert assessment.professional_experience_years == 2.08
    assert assessment.internship_experience_years == 1.08
    assert assessment.allows_internship_for_requirement is True
    assert assessment.years_toward_requirement == round(
        assessment.professional_experience_years + assessment.internship_experience_years,
        2,
    )
    assert assessment.meets_minimum is True
    # Internship must still be labeled separately — never relabeled professional.
    assert assessment.professional_experience_years < 3


def test_academic_projects_only_fail_professional_requirement():
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python", "TensorFlow", "FastAPI"]),
        experience_entries=[
            ExperienceEntry(
                role="ML Capstone Project",
                entry_type="project",
                start_date="Jan 2021",
                end_date="Jan 2024",
                start_month_index=2021 * 12,
                end_month_index=2024 * 12,
                text="Python TensorFlow FastAPI machine learning model development",
            )
        ],
        source_text="Python TensorFlow FastAPI",
    )
    jd = ParsedJD(
        job_title="Python Developer",
        required_skills=SkillList(normalized=["Python", "TensorFlow", "FastAPI"]),
        experience_requirements=["3 years professional experience"],
        minimum_experience_years=3,
        experience_requirement_kind="professional",
    )
    assessment = evaluate_relevant_experience(candidate, jd)
    assert assessment.professional_experience_years == 0
    assert assessment.academic_project_years > 0
    assert assessment.relevant_hands_on_experience_years > 0
    assert assessment.meets_minimum is False
    assert assessment.years_toward_requirement == 0


def test_hands_on_jd_can_use_internship_and_projects_without_calling_them_professional():
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python", "PyTorch"]),
        experience_entries=[
            ExperienceEntry(
                role="AI Intern",
                entry_type="internship",
                start_date="Jan 2024",
                end_date="Jul 2024",
                start_month_index=2024 * 12,
                end_month_index=2024 * 12 + 6,
                text="Python PyTorch deep learning",
            ),
            ExperienceEntry(
                role="Vision Project",
                entry_type="project",
                start_date="Jan 2023",
                end_date="Jul 2023",
                start_month_index=2023 * 12,
                end_month_index=2023 * 12 + 6,
                text="Python PyTorch computer vision",
            ),
        ],
        source_text="Python PyTorch",
    )
    jd = ParsedJD(
        required_skills=SkillList(normalized=["Python", "PyTorch"]),
        experience_requirements=["1 year hands-on AI/ML experience"],
        minimum_experience_years=1,
        experience_requirement_kind="hands_on",
    )
    assessment = evaluate_relevant_experience(candidate, jd)
    assert assessment.professional_experience_years == 0
    assert assessment.internship_experience_years > 0
    assert assessment.academic_project_years > 0
    assert assessment.years_toward_requirement == assessment.relevant_hands_on_experience_years
    assert assessment.meets_minimum is True
    assert "professional" in assessment.result.casefold() or "internship" in assessment.result.casefold()


def test_jd_parser_classifies_professional_vs_internship_included(monkeypatch):
    from agents.screening_agent.services.jd_parser import parse_job_description

    monkeypatch.setattr(settings, "USE_LLM_FOR_JD_PARSING", False)
    professional = parse_job_description(
        "Backend Engineer\nRequired Skills: Python\n"
        "3 years professional experience in Python development."
    )
    assert professional.experience_requirement_kind == "professional"
    assert professional.allows_internship_for_requirement is False

    included = parse_job_description(
        "Backend Engineer\nRequired Skills: Python\n"
        "3 years relevant experience including internships."
    )
    assert included.experience_requirement_kind == "internship_included"
    assert included.allows_internship_for_requirement is True

    hands_on = parse_job_description(
        "ML Engineer\nRequired Skills: PyTorch\n"
        "Minimum 2 years hands-on machine learning experience."
    )
    assert hands_on.experience_requirement_kind == "hands_on"
