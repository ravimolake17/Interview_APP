from agents.screening_agent.schemas.ats import (
    CandidateProfile,
    ExperienceEntry,
    ParsedJD,
    SkillCollection,
    SkillList,
)
from agents.screening_agent.services.matching_service import analyze_skill_match
from agents.screening_agent.services.resume_profile_service import _extract_education
from agents.screening_agent.services.scoring_service import (
    evaluate_relevant_experience,
    parse_skill_experience_requirements,
    score_candidate,
)
from agents.screening_agent.utils.skill_normalizer import (
    expand_compound_skill,
    normalize_skill,
    normalize_skills,
)


def test_compound_skills_are_decomposed_and_deduped():
    skills = normalize_skills(
        [
            "FastAPI",
            "FastAPI / Flask / Django",
            "TensorFlow / PyTorch",
            "Pandas, NumPy",
            "Pandas",
            "CI/CD",
        ]
    )
    assert skills.count("FastAPI") == 1
    assert "Flask" in skills
    assert "Django" in skills
    assert "TensorFlow" in skills
    assert "PyTorch" in skills
    assert "Pandas" in skills
    assert "NumPy" in skills
    assert "CI/CD" in skills
    assert "FastAPI / Flask / Django" not in skills
    assert "Pandas, NumPy" not in skills


def test_expand_compound_does_not_split_hr_phrase():
    assert expand_compound_skill("HR Policies and Procedures") == ["HR Policies and Procedures"]


def test_aliases_across_industries():
    assert normalize_skill("REST APIs") == "REST API"
    assert normalize_skill("REST API Development") == "REST API"
    assert normalize_skill("Postgres") == "PostgreSQL"
    assert normalize_skill("GenAI") == "Generative AI"
    assert normalize_skill("NLP") == "Natural Language Processing"
    assert normalize_skill("OOP") == "Object-Oriented Programming"
    assert normalize_skill("ML") == "Machine Learning"
    assert normalize_skill("RAG") == "RAG"
    assert normalize_skill("Python (Advanced)") == "Python"


def test_exact_semantic_partial_and_missing_levels():
    candidate = SkillCollection(
        normalized_skills=["Python", "REST API", "JSON", "NumPy", "Microsoft Azure"],
        raw_skills=["schema-validated JSON outputs", "REST APIs"],
    )
    resume = (
        "Built REST APIs and schema-validated JSON outputs. "
        "Used NumPy and Azure. Integrated downstream APIs with enterprise databases."
    )
    jd = ParsedJD(
        required_skills=SkillList(
            normalized=[
                "Python (Advanced)",
                "REST API Development",
                "JSON",
                "XML",
                "Pandas",
                "Enterprise System Integration",
                "Azure OpenAI",
            ]
        )
    )
    match = analyze_skill_match(candidate, jd, resume_text=resume)

    by_skill = {item.jd_skill: item for item in match.semantic_required_matches}
    assert by_skill["Python"].match_level == "STRONG_SEMANTIC_MATCH"
    assert by_skill["REST API"].match_level in {"EXACT_MATCH", "STRONG_SEMANTIC_MATCH"}
    assert by_skill["JSON"].match_level == "EXACT_MATCH"
    assert "JSON" not in match.missing_required_skills
    assert by_skill["XML"].match_level == "MISSING"
    assert by_skill["Pandas"].match_level == "MISSING"
    assert by_skill["Azure OpenAI"].match_level in {"PARTIAL_MATCH", "MISSING"}
    assert "Pandas" in match.missing_required_skills
    assert "XML" in match.missing_required_skills
    assert "Pandas, NumPy" not in match.missing_required_skills


def test_json_is_not_xml_and_numpy_is_not_pandas():
    match = analyze_skill_match(
        SkillCollection(normalized_skills=["JSON", "NumPy", "scikit-learn"]),
        ParsedJD(required_skills=SkillList(normalized=["XML", "Pandas"])),
        resume_text="Produced schema-validated JSON outputs using NumPy and scikit-learn.",
    )
    assert match.missing_required_skills == ["XML", "Pandas"]
    assert match.matched_required_skills == []


def test_duplicate_required_skills_do_not_inflate_denominator():
    jd = ParsedJD(
        required_skills=SkillList(
            normalized=["FastAPI", "FastAPI / Flask / Django", "Flask", "Django"]
        )
    )
    match = analyze_skill_match(
        SkillCollection(normalized_skills=["FastAPI", "Flask", "Django"]),
        jd,
    )
    assert match.required_match_ratio == 1.0
    assert set(match.matched_required_skills) == {"FastAPI", "Flask", "Django"}
    assert match.missing_required_skills == []


def test_education_extracts_be_computer_engineering():
    rows = [
        {
            "heading": "Education",
            "text": "BE Computer Engineering\nUniversity of Example, 2021",
        }
    ]
    lines = _extract_education(rows, "BE Computer Engineering\nUniversity of Example, 2021")
    assert any("BE Computer Engineering" in line for line in lines)


def test_education_scans_full_text_when_heading_has_no_degree():
    rows = [
        {
            "heading": "Qualifications",
            "text": "Strong communication and stakeholder management",
        }
    ]
    text = "B.Tech in Computer Science\nABC University"
    lines = _extract_education(rows, text)
    assert any("B.Tech" in line or "Computer Science" in line for line in lines)


def test_internships_and_projects_are_excluded_from_professional_years():
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python"]),
        experience_entries=[
            ExperienceEntry(
                role="Python Developer",
                company="Acme",
                entry_type="employment",
                start_date="Jan 2020",
                end_date="Mar 2024",
                start_month_index=2020 * 12,
                end_month_index=2024 * 12 + 2,
                text="Python backend development",
            ),
            ExperienceEntry(
                role="ML Intern",
                company="Lab",
                entry_type="internship",
                start_date="Jan 2019",
                end_date="Jun 2019",
                start_month_index=2019 * 12,
                end_month_index=2019 * 12 + 5,
                text="Python machine learning internship",
            ),
            ExperienceEntry(
                role="Capstone",
                company="College",
                entry_type="project",
                start_date="Jan 2018",
                end_date="May 2018",
                start_month_index=2018 * 12,
                end_month_index=2018 * 12 + 4,
                text="Python academic project",
            ),
        ],
        total_experience_years=4.25,
    )
    jd = ParsedJD(
        required_skills=SkillList(normalized=["Python"]),
        minimum_experience_years=3,
        job_title="Python Developer",
    )
    assessment = evaluate_relevant_experience(candidate, jd)
    assert assessment.professional_experience_years == 4.25
    assert assessment.internship_experience_years > 0
    assert assessment.academic_project_years > 0
    assert assessment.supporting_exposure_years == round(
        assessment.internship_experience_years
        + assessment.academic_project_years
        + assessment.research_experience_years,
        2,
    )
    assert assessment.supporting_exposure_years != assessment.professional_experience_years
    assert assessment.years_toward_requirement == 4.25


def test_overlapping_employment_is_not_double_counted_for_skill_years():
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python"]),
        experience_entries=[
            ExperienceEntry(
                role="Python Engineer",
                company="A",
                entry_type="employment",
                start_date="Jan 2022",
                end_date="Dec 2023",
                start_month_index=2022 * 12,
                end_month_index=2023 * 12 + 11,
                text="Python development",
            ),
            ExperienceEntry(
                role="Python Contractor",
                company="B",
                entry_type="employment",
                start_date="Jun 2022",
                end_date="Dec 2023",
                start_month_index=2022 * 12 + 5,
                end_month_index=2023 * 12 + 11,
                text="Python APIs",
            ),
        ],
    )
    jd = ParsedJD(
        required_skills=SkillList(normalized=["Python"]),
        experience_requirements=["4-6 years Python development"],
        minimum_experience_years=4,
        maximum_experience_years=6,
    )
    assessment = evaluate_relevant_experience(candidate, jd)
    python_req = next(
        item
        for item in assessment.skill_experience_assessments
        if item.skill_or_domain == "Python"
    )
    assert python_req.candidate_years == 2.0


def test_skill_specific_experience_requirements_are_independent():
    parsed = parse_skill_experience_requirements(
        [
            "4-6 years Python development",
            "Minimum 3 years AI/ML experience",
            "Preferred 2 years of healthcare operations",
        ]
    )
    labels = {item.skill_or_domain: item for item in parsed}
    assert labels["Python"].minimum_years == 4
    assert labels["Python"].maximum_years == 6
    assert labels["Machine Learning"].minimum_years == 3
    assert labels["Machine Learning"].is_preferred is False


def test_hr_and_healthcare_skills_still_match():
    match = analyze_skill_match(
        SkillCollection(normalized_skills=["Employee Relations", "Onboarding", "HIPAA"]),
        ParsedJD(
            required_skills=SkillList(
                normalized=["Employee Relations", "Orientation and Onboarding"]
            )
        ),
    )
    assert "Employee Relations" in match.matched_required_skills
    assert "Orientation and Onboarding" in match.matched_required_skills


def test_finance_skill_is_not_inferred_from_unrelated_software():
    match = analyze_skill_match(
        SkillCollection(normalized_skills=["Python", "Excel"]),
        ParsedJD(required_skills=SkillList(normalized=["IFRS", "Financial Modelling"])),
        resume_text="Python scripts and Microsoft Excel dashboards",
    )
    assert "IFRS" in match.missing_required_skills


def test_akshat_style_resume_regression_without_hardcoded_score():
    """Representative evidence from the current resume/JD case — not a score lock."""
    resume = (
        "Akshat Shah\n"
        "BE Computer Engineering\n"
        "Python, FastAPI, Flask, Django, TensorFlow, PyTorch, NLP, GenAI, LLMs, "
        "Prompt Engineering, RAG, SQL, Azure, Docker, CI/CD, JSON\n"
        "Developed backend APIs with FastAPI and schema-validated JSON outputs. "
        "Built a RAG chatbot and API-integrated intelligent assistants. "
        "Developed ML models for classification, prediction, and time-series. "
        "ETL pipeline: ingestion, OCR, normalization, validation, DB write. "
        "Deployed services with Azure, AWS, Docker, and CI/CD.\n"
    )
    candidate = CandidateProfile(
        skills=SkillCollection(
            normalized_skills=[
                "Python",
                "FastAPI",
                "Flask",
                "Django",
                "TensorFlow",
                "PyTorch",
                "Natural Language Processing",
                "Generative AI",
                "Large Language Models",
                "Prompt Engineering",
                "RAG",
                "SQL",
                "Microsoft Azure",
                "Docker",
                "CI/CD",
                "JSON",
            ]
        ),
        education=["BE Computer Engineering"],
        source_text=resume,
        experience_entries=[
            ExperienceEntry(
                role="Python Developer",
                company="TCS",
                entry_type="employment",
                start_date="Jan 2022",
                end_date="Mar 2025",
                start_month_index=2022 * 12,
                end_month_index=2025 * 12 + 2,
                text="Python backend services, Flask, Django, REST APIs.",
            ),
            ExperienceEntry(
                role="AI/ML Engineer",
                company="Armakuni",
                entry_type="employment",
                start_date="Sep 2025",
                end_date="Present",
                start_month_index=2025 * 12 + 8,
                end_month_index=2026 * 12 + 8,
                text="FastAPI backend APIs, RAG chatbot, intelligent assistants, Azure Docker CI/CD.",
            ),
        ],
        total_experience_years=4.25,
    )
    jd = ParsedJD(
        required_skills=SkillList(
            normalized=[
                "Python",
                "FastAPI / Flask / Django",
                "TensorFlow / PyTorch",
                "JSON",
                "XML",
                "Pandas",
                "NumPy",
                "Enterprise System Integration",
                "REST API Development",
            ]
        ),
        education_requirements=["Bachelor's degree in Engineering/Computer Science or related field"],
        minimum_experience_years=4,
        experience_requirements=["4–6 years Python development", "Minimum 3 years AI/ML"],
        responsibilities=[
            "Build AI-powered applications, chatbots, virtual assistants",
            "Build and maintain machine learning models for prediction and classification",
            "Develop data-processing pipelines",
            "Fine-tune and optimize AI models",
            "Develop scalable backend APIs",
        ],
    )
    match = analyze_skill_match(
        candidate.skills,
        jd,
        experience_entries=candidate.experience_entries,
        resume_text=resume,
    )
    result = score_candidate(candidate, jd, match)
    assessment = result.experience_assessment

    assert "JSON" in match.matched_required_skills
    assert "JSON" not in match.missing_required_skills
    assert "XML" in match.missing_required_skills
    assert "Pandas" in match.missing_required_skills
    assert "NumPy" in match.missing_required_skills
    assert "Pandas, NumPy" not in match.missing_required_skills
    assert "FastAPI / Flask / Django" not in match.missing_required_skills
    assert candidate.education
    assert result.education_score > 0
    assert assessment.professional_experience_years >= 4.25
    assert assessment.supporting_exposure_years != assessment.professional_experience_years
    listed = set(
        match.matched_required_skills
        + match.missing_required_skills
        + match.partial_required_skills
    )
    assert "FastAPI / Flask / Django" not in listed
    assert len(listed) == len(set(item.casefold() for item in listed))
    assert result.overall_score < 100

    by_resp = {item.jd_responsibility: item.match_status for item in result.responsibility_matches}
    assert by_resp["Build AI-powered applications, chatbots, virtual assistants"] in {
        "STRONG_MATCH",
        "PARTIAL_MATCH",
    }
    assert by_resp["Build and maintain machine learning models for prediction and classification"] in {
        "STRONG_MATCH",
        "PARTIAL_MATCH",
    }
    assert by_resp["Develop data-processing pipelines"] in {"STRONG_MATCH", "PARTIAL_MATCH"}
    assert by_resp["Fine-tune and optimize AI models"] == "UNSUPPORTED"
    assert by_resp["Develop scalable backend APIs"] in {"STRONG_MATCH", "PARTIAL_MATCH"}

    python_req = next(
        item
        for item in assessment.skill_experience_assessments
        if item.skill_or_domain == "Python"
    )
    assert python_req.supported_years >= 4
    assert python_req.meets_minimum is True
    assert python_req.explicit_dated_years == 3.25
    assert python_req.strong_dated_years > 0
