from agents.screening_agent.config import settings
from agents.screening_agent.schemas.ats import (
    CandidateProfile,
    ExperienceEntry,
    ParsedJD,
    SkillCollection,
    SkillList,
)
from agents.screening_agent.services.matching_service import analyze_skill_match
from agents.screening_agent.services.responsibility_matcher import match_responsibilities
from agents.screening_agent.services.scoring_service import (
    evaluate_relevant_experience,
    parse_skill_experience_requirements,
    score_candidate,
)


def test_exact_responsibility_match():
    candidate = CandidateProfile(
        source_text="Developed backend APIs with FastAPI for production services.",
        experience_entries=[
            ExperienceEntry(
                role="Backend Engineer",
                entry_type="employment",
                text="Developed backend APIs with FastAPI",
            )
        ],
    )
    jd = ParsedJD(responsibilities=["Develop backend APIs"])
    ratio, matches = match_responsibilities(candidate, jd)
    item = matches[0]
    assert item.match_status == "STRONG_MATCH"
    assert item.evidence
    assert ratio >= 0.7


def test_semantic_chatbot_responsibility_match():
    candidate = CandidateProfile(
        source_text=(
            "Built a RAG chatbot. API-integrated intelligent assistants. "
            "Built multi-agent systems."
        )
    )
    jd = ParsedJD(
        responsibilities=[
            "Build AI-powered applications, chatbots, virtual assistants, and intelligent workflow solutions."
        ]
    )
    _ratio, matches = match_responsibilities(candidate, jd)
    item = matches[0]
    assert item.match_status == "STRONG_MATCH"
    assert any("chatbot" in ev.casefold() or "assistant" in ev.casefold() for ev in item.evidence)


def test_etl_pipeline_matches_data_processing_responsibility():
    candidate = CandidateProfile(
        source_text="ETL pipeline: ingestion → OCR → normalization → validation → DB write"
    )
    jd = ParsedJD(responsibilities=["Collect, clean, transform and prepare data"])
    _ratio, matches = match_responsibilities(candidate, jd)
    assert matches[0].match_status in {"STRONG_MATCH", "PARTIAL_MATCH"}
    assert any(
        "pipeline" in ev.casefold() or "etl" in ev.casefold() or "ingestion" in ev.casefold()
        for ev in matches[0].evidence
    )


def test_ml_model_responsibility_matches_classification_evidence():
    candidate = CandidateProfile(
        source_text="Developed ML models for classification, prediction, and recommendation systems."
    )
    jd = ParsedJD(
        responsibilities=[
            "Build and maintain machine learning models for prediction, classification, recommendation and optimisation"
        ]
    )
    _ratio, matches = match_responsibilities(candidate, jd)
    assert matches[0].match_status in {"STRONG_MATCH", "PARTIAL_MATCH"}


def test_unsupported_finetune_responsibility():
    candidate = CandidateProfile(
        source_text="Built a RAG chatbot and FastAPI services. No model training notes."
    )
    jd = ParsedJD(responsibilities=["Fine-tune and optimize AI models"])
    _ratio, matches = match_responsibilities(candidate, jd)
    assert matches[0].match_status == "UNSUPPORTED"
    assert matches[0].evidence == []


def test_rest_api_does_not_satisfy_enterprise_crm_responsibility():
    candidate = CandidateProfile(source_text="Built REST APIs with FastAPI.")
    jd = ParsedJD(responsibilities=["Build a complete enterprise CRM integration"])
    _ratio, matches = match_responsibilities(candidate, jd)
    assert matches[0].match_status != "STRONG_MATCH"


def test_hr_responsibility_semantic_match():
    candidate = CandidateProfile(
        source_text="Advised managers on employee-relations concerns and workplace issues."
    )
    jd = ParsedJD(
        job_title="HR Operations Manager",
        required_skills=SkillList(normalized=["Employee Relations"]),
        responsibilities=["Handle employee-relations matters and advise managers on workplace concerns."],
    )
    _ratio, matches = match_responsibilities(candidate, jd)
    assert matches[0].match_status in {"STRONG_MATCH", "PARTIAL_MATCH"}
    assert matches[0].priority == "CORE"


def test_action_synonyms_build_and_develop():
    candidate = CandidateProfile(
        source_text="Implemented machine learning systems for production scoring."
    )
    jd = ParsedJD(responsibilities=["Design and develop AI/ML solutions"])
    _ratio, matches = match_responsibilities(candidate, jd)
    assert matches[0].match_status in {"STRONG_MATCH", "PARTIAL_MATCH"}


def test_python_strong_dated_evidence_from_related_framework():
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python", "FastAPI"]),
        experience_entries=[
            ExperienceEntry(
                role="Python Developer",
                company="TCS",
                entry_type="employment",
                start_date="Jan 2022",
                end_date="Mar 2025",
                start_month_index=2022 * 12,
                end_month_index=2025 * 12 + 2,
                text="Python development for backend services",
            ),
            ExperienceEntry(
                role="AI/ML Engineer",
                company="Armakuni",
                entry_type="employment",
                start_date="Sep 2025",
                end_date="Present",
                start_month_index=2025 * 12 + 8,
                end_month_index=2026 * 12 + 8,
                text="FastAPI backend APIs and AI applications",
            ),
        ],
    )
    jd = ParsedJD(
        required_skills=SkillList(normalized=["Python", "FastAPI"]),
        experience_requirements=["4–6 years Python development"],
        minimum_experience_years=4,
        maximum_experience_years=6,
    )
    assessment = evaluate_relevant_experience(candidate, jd)
    python_req = next(
        item for item in assessment.skill_experience_assessments if item.skill_or_domain == "Python"
    )
    assert python_req.explicit_dated_years == 3.25
    assert python_req.strong_dated_years == 1.08
    assert python_req.supported_years == 4.33
    assert python_req.meets_minimum is True
    assert python_req.evidence_kind == "MIXED_DATED_EVIDENCE"
    assert "FAIL" not in python_req.reason


def test_global_skill_without_dated_role_is_undated():
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python"]),
        experience_entries=[
            ExperienceEntry(
                role="Sales Associate",
                company="Shop",
                entry_type="employment",
                start_month_index=2020 * 12,
                end_month_index=2024 * 12,
                text="Retail sales and customer service",
            )
        ],
    )
    jd = ParsedJD(experience_requirements=["3 years Python development"])
    assessment = evaluate_relevant_experience(candidate, jd)
    python_req = next(
        item for item in assessment.skill_experience_assessments if item.skill_or_domain == "Python"
    )
    assert python_req.supported_years == 0
    assert python_req.evidence_kind == "UNDATED_EVIDENCE"


def test_multiple_experience_requirements_are_independent():
    parsed = parse_skill_experience_requirements(
        [
            "4-6 years Python development",
            "Minimum 3 years AI/ML experience",
            "Experience in GenAI/LLM",
            "Experience in API development",
        ]
    )
    labels = {item.skill_or_domain for item in parsed}
    assert "Python" in labels
    assert "Machine Learning" in labels
    assert "Generative AI" in labels or "Large Language Models" in labels
    assert "REST API" in labels


def test_internship_still_excluded_from_skill_years():
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python"]),
        experience_entries=[
            ExperienceEntry(
                role="Python Intern",
                company="Lab",
                entry_type="internship",
                start_month_index=2020 * 12,
                end_month_index=2021 * 12,
                text="Python FastAPI",
            )
        ],
    )
    jd = ParsedJD(
        experience_requirements=["3 years Python development"],
        allows_internship_for_requirement=False,
    )
    assessment = evaluate_relevant_experience(candidate, jd)
    python_req = next(
        item for item in assessment.skill_experience_assessments if item.skill_or_domain == "Python"
    )
    assert python_req.supported_years == 0


def test_project_exclusion_from_skill_years():
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python"]),
        experience_entries=[
            ExperienceEntry(
                role="Capstone",
                entry_type="project",
                start_month_index=2020 * 12,
                end_month_index=2023 * 12,
                text="Python FastAPI",
            )
        ],
    )
    jd = ParsedJD(experience_requirements=["3 years Python development"])
    assessment = evaluate_relevant_experience(candidate, jd)
    python_req = next(
        item for item in assessment.skill_experience_assessments if item.skill_or_domain == "Python"
    )
    assert python_req.supported_years == 0


def test_non_technical_jd_responsibilities():
    candidate = CandidateProfile(
        source_text="Managed vendor coordination, inventory planning, and safety compliance audits."
    )
    jd = ParsedJD(
        job_title="Operations Lead",
        responsibilities=["Manage vendor coordination and inventory planning"],
    )
    _ratio, matches = match_responsibilities(candidate, jd)
    assert matches[0].match_status in {"STRONG_MATCH", "PARTIAL_MATCH"}


def test_civil_engineering_responsibility_match():
    candidate = CandidateProfile(
        source_text="Prepared structural drawings and supervised on-site concrete pouring for residential buildings."
    )
    jd = ParsedJD(
        job_title="Civil Engineer",
        responsibilities=["Prepare structural drawings and supervise on-site construction"],
    )
    _ratio, matches = match_responsibilities(candidate, jd)
    assert matches[0].match_status in {"STRONG_MATCH", "PARTIAL_MATCH"}
    assert matches[0].evidence


def test_jd_section_headings_are_not_scored_as_responsibilities():
    candidate = CandidateProfile(
        source_text="Developed Python FastAPI backend APIs and a RAG chatbot."
    )
    jd = ParsedJD(
        responsibilities=[
            "Application Development",
            "Innovation & Research",
            "Develop scalable backend services and APIs using Python frameworks",
        ]
    )
    _ratio, matches = match_responsibilities(candidate, jd)
    titles = [item.jd_responsibility for item in matches]
    assert "Application Development" not in titles
    assert "Innovation & Research" not in titles
    assert matches[0].match_status in {"STRONG_MATCH", "PARTIAL_MATCH"}


def test_overlapping_employment_dates_are_not_double_counted():
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python"]),
        experience_entries=[
            ExperienceEntry(
                role="Engineer",
                company="A",
                entry_type="employment",
                start_month_index=2022 * 12,
                end_month_index=2024 * 12,
                text="Python services",
            ),
            ExperienceEntry(
                role="Engineer",
                company="B",
                entry_type="employment",
                start_month_index=2023 * 12,
                end_month_index=2024 * 12 + 6,
                text="Python APIs",
            ),
        ],
    )
    jd = ParsedJD(experience_requirements=["3 years Python development"])
    assessment = evaluate_relevant_experience(candidate, jd)
    python_req = next(
        item for item in assessment.skill_experience_assessments if item.skill_or_domain == "Python"
    )
    # Jan 2022–Dec 2024 overlapping Jan 2023–Jun 2025 → union through Jun 2025, not 2+1.58.
    assert python_req.supported_years == round(((2024 * 12 + 6 + 1) - (2022 * 12)) / 12, 2)
    assert python_req.supported_years < 4.0


def test_json_is_not_xml():
    match = analyze_skill_match(
        SkillCollection(normalized_skills=["JSON"]),
        ParsedJD(required_skills=SkillList(normalized=["JSON", "XML"])),
        resume_text="Built schema-validated JSON APIs.",
    )
    assert "JSON" in match.matched_required_skills
    assert "XML" in match.missing_required_skills


def test_technical_and_nontechnical_jds_use_the_same_engine():
    tech = analyze_skill_match(
        SkillCollection(normalized_skills=["Python", "FastAPI"]),
        ParsedJD(required_skills=SkillList(normalized=["Python", "FastAPI"])),
        resume_text="Python FastAPI services",
    )
    hr = analyze_skill_match(
        SkillCollection(normalized_skills=["Employee Relations", "HRIS"]),
        ParsedJD(required_skills=SkillList(normalized=["Employee Relations"])),
        resume_text="Employee relations casework and HRIS administration",
    )
    assert "Python" in tech.matched_required_skills
    assert "Employee Relations" in hr.matched_required_skills
    assert "Python" not in hr.missing_required_skills + hr.matched_required_skills


def test_responsibility_score_uses_semantic_matches_not_just_keywords():
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python", "FastAPI"]),
        source_text="Built a RAG chatbot and API-integrated intelligent assistants.",
        education=["Bachelor's degree"],
    )
    jd = ParsedJD(
        required_skills=SkillList(normalized=["Python"]),
        responsibilities=[
            "Build AI-powered applications, chatbots, virtual assistants"
        ],
        education_requirements=["Bachelor's degree"],
        keywords=["applications", "models", "design"],
    )
    match = analyze_skill_match(candidate.skills, jd, resume_text=candidate.source_text)
    result = score_candidate(candidate, jd, match)
    assert result.responsibility_matches[0].match_status in {"STRONG_MATCH", "PARTIAL_MATCH"}
    assert result.responsibility_score > 0
    assert result.keyword_score <= settings.ATS_KEYWORD_WEIGHT


def test_json_is_not_xml():
    match = analyze_skill_match(
        SkillCollection(normalized_skills=["JSON"], raw_skills=["schema-validated JSON outputs"]),
        ParsedJD(required_skills=SkillList(normalized=["JSON", "XML"])),
        resume_text="Produced schema-validated JSON outputs.",
    )
    assert "JSON" in match.matched_required_skills
    assert "XML" in match.missing_required_skills


def test_duplicate_skills_are_not_listed_twice():
    match = analyze_skill_match(
        SkillCollection(normalized_skills=["Python", "Python", "FastAPI"]),
        ParsedJD(required_skills=SkillList(normalized=["Python", "Python", "FastAPI"])),
    )
    assert match.matched_required_skills.count("Python") == 1


def test_non_technical_jd_does_not_require_python():
    match = analyze_skill_match(
        SkillCollection(normalized_skills=["Employee Relations", "HRIS"]),
        ParsedJD(required_skills=SkillList(normalized=["Employee Relations"])),
    )
    assert match.matched_required_skills == ["Employee Relations"]
    assert "Python" not in match.missing_required_skills


def test_independent_skill_experience_is_not_total_experience():
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python", "FastAPI", "Generative AI", "RAG"]),
        experience_entries=[
            ExperienceEntry(
                role="Python Developer",
                company="TCS",
                entry_type="employment",
                start_month_index=2022 * 12,
                end_month_index=2025 * 12 + 2,
                text="Python REST APIs and FastAPI services",
            ),
            ExperienceEntry(
                role="AI/ML Engineer",
                company="Armakuni",
                entry_type="employment",
                start_month_index=2025 * 12 + 8,
                end_month_index=2026 * 12 + 8,
                text="FastAPI RAG chatbot and generative AI applications",
            ),
        ],
    )
    jd = ParsedJD(
        experience_requirements=[
            "4-6 years Python development",
            "Minimum 3 years AI/ML experience",
            "Experience in GenAI/LLM",
            "Experience in API development",
        ],
        minimum_experience_years=4,
    )
    assessment = evaluate_relevant_experience(candidate, jd)
    by_skill = {item.skill_or_domain: item for item in assessment.skill_experience_assessments}
    assert by_skill["Python"].supported_years >= 4
    assert by_skill["Python"].meets_minimum is True
    ml = by_skill.get("Machine Learning") or by_skill.get("Artificial Intelligence")
    assert ml is not None
    genai = by_skill.get("Generative AI") or by_skill.get("Large Language Models")
    assert genai is not None
    assert genai.supported_years > 0
    assert by_skill["REST API"].supported_years > 0


def test_paraphrased_responsibilities_and_missing_finetune():
    candidate = CandidateProfile(
        skills=SkillCollection(normalized_skills=["Python", "RAG"]),
        education=["BE Computer Engineering"],
        source_text=(
            "Built a RAG chatbot. API-integrated intelligent assistants. "
            "Developed ML models for classification. "
            "ETL pipeline: ingestion, normalization, validation."
        ),
        experience_entries=[
            ExperienceEntry(
                role="AI/ML Engineer",
                company="Acme",
                entry_type="employment",
                start_month_index=2022 * 12,
                end_month_index=2026 * 12 + 2,
                text="Python FastAPI RAG chatbot and ML models. ETL pipeline.",
            )
        ],
        total_experience_years=4.25,
    )
    jd = ParsedJD(
        required_skills=SkillList(normalized=["Python"]),
        education_requirements=["Bachelor's degree in Engineering"],
        responsibilities=[
            "Build AI-powered applications, chatbots, virtual assistants",
            "Build and maintain machine learning models for prediction and classification",
            "Develop data-processing pipelines",
            "Fine-tune and optimize AI models",
        ],
        keywords=["chatbot", "pipeline"],
        minimum_experience_years=4,
    )
    match = analyze_skill_match(candidate.skills, jd, resume_text=candidate.source_text)
    result = score_candidate(candidate, jd, match)
    statuses = {item.jd_responsibility: item.match_status for item in result.responsibility_matches}
    assert any(status == "STRONG_MATCH" for status in statuses.values())
    fine_tune = [item for item in result.responsibility_matches if "Fine-tune" in item.jd_responsibility]
    assert fine_tune and fine_tune[0].match_status == "UNSUPPORTED"
    assert result.responsibility_score > 0
