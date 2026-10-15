"""Agent 3 scenario plan + Agent 4 LLM-primary generation (mocked)."""

from unittest.mock import patch

from agents.blueprint_agent.scenario_plan import (
    build_deterministic_question_plan,
    enrich_blueprint_with_scenario_plan,
    infer_role_family,
)
from agents.blueprint_agent.schemas import (
    Agent4Metadata,
    CategoryBreakdown,
    DifficultyDistribution,
    HumanReadableReport,
    InputSummary,
    InterviewBlueprintResponse,
    TimeAllocation,
)
from agents.interview_agent.adaptive import generate_questions_with_llama
from agents.interview_agent.question_generator import is_spoken_interview_question


def _minimal_blueprint(*, skill: str = "OCR", project: str = "PDF Pipeline") -> InterviewBlueprintResponse:
    categories = [
        CategoryBreakdown(
            order=1,
            category_id="introductory_questions",
            category_name="Introductory Questions",
            question_count=1,
            difficulty_mix={"easy": 1},
            estimated_minutes=3,
            time_percentage=20,
            purpose="Open",
            selection_reason="Warm up",
            candidate_resume_signals=[],
            jd_signals=["AI Engineer"],
            agent4_generation_instruction="Open on motivation",
        ),
        CategoryBreakdown(
            order=2,
            category_id="skills_jd_keyword_questions",
            category_name="Skills & JD Keyword-related Questions",
            question_count=2,
            difficulty_mix={"medium": 1, "hard": 1},
            estimated_minutes=8,
            time_percentage=45,
            purpose="Skills",
            selection_reason="JD skills",
            candidate_resume_signals=[skill],
            jd_signals=[skill, "Python"],
            agent4_generation_instruction="Probe skills",
        ),
        CategoryBreakdown(
            order=3,
            category_id="project_related_questions",
            category_name="Project-related Questions",
            question_count=1,
            difficulty_mix={"hard": 1},
            estimated_minutes=5,
            time_percentage=25,
            purpose="Projects",
            selection_reason="Project evidence",
            candidate_resume_signals=[project],
            jd_signals=[skill],
            agent4_generation_instruction="Probe projects",
        ),
        CategoryBreakdown(
            order=4,
            category_id="education_courses_questions",
            category_name="Education & Courses-related Questions",
            question_count=1,
            difficulty_mix={"easy": 1},
            estimated_minutes=2,
            time_percentage=10,
            purpose="Education",
            selection_reason="Education",
            candidate_resume_signals=["MCA"],
            jd_signals=[],
            agent4_generation_instruction="Probe education",
        ),
    ]
    return InterviewBlueprintResponse(
        candidate_level="Junior",
        input_summary=InputSummary(
            job_title="AI Engineer",
            ats_score=72,
            ats_status="Shortlisted",
            resume_word_count=400,
            resume_depth_label="medium",
            jd_word_count=300,
            jd_complexity_label="medium",
            matched_skills_count=4,
            missing_skills_count=1,
            jd_required_skills_count=5,
            jd_preferred_skills_count=2,
            project_evidence_count=1,
            education_course_evidence_count=1,
        ),
        total_questions=5,
        difficulty_distribution=DifficultyDistribution(
            easy=2,
            medium=1,
            hard=2,
            reasoning="Test mix",
        ),
        category_breakdown=categories,
        time_allocation=TimeAllocation(
            total_duration_minutes=25,
            buffer_minutes=7,
            category_minutes={
                "introductory_questions": 3,
                "skills_jd_keyword_questions": 8,
                "project_related_questions": 5,
                "education_courses_questions": 2,
            },
            category_percentages={
                "introductory_questions": 16.7,
                "skills_jd_keyword_questions": 44.4,
                "project_related_questions": 27.8,
                "education_courses_questions": 11.1,
            },
            time_distribution_basis=["test"],
            reasoning="Test time allocation across categories for unit coverage.",
        ),
        skill_focus_plan=[],
        interview_flow=[],
        agent4_metadata=Agent4Metadata(),
        human_readable_report=HumanReadableReport(
            summary="Test blueprint for scenario plan unit coverage.",
            recommended_flow=["1. Intro"],
            interviewer_notes=["Use scenario intents"],
            risk_flags=[],
        ),
    )


def test_infer_role_family_software_for_ai_engineer():
    assert infer_role_family(job_title="AI Engineer", jd_text="Python OCR FastAPI") == "software"


def test_deterministic_question_plan_has_scale_and_failure_slots():
    blueprint = _minimal_blueprint()
    slots = build_deterministic_question_plan(blueprint)
    assert len(slots) == 5
    probes = {s.probe_type for s in slots}
    assert "motivation" in probes
    assert probes & {"scale", "failure", "tradeoff", "change", "ownership"}
    assert all(s.scenario_intent for s in slots)
    assert all("motivated" not in s.scenario_intent.casefold() for s in slots)


def test_enrich_attaches_plan_without_llm():
    blueprint = _minimal_blueprint()
    with patch("agents.blueprint_agent.scenario_plan.llama_available", return_value=False):
        enriched = enrich_blueprint_with_scenario_plan(blueprint, None)
    assert enriched.question_plan
    assert len(enriched.question_plan) == enriched.total_questions
    assert enriched.role_family in {"software", "data", "ops", "product", "non_tech", "general"}


def test_agent4_prefers_llm_spoken_questions_from_plan():
    blueprint = _minimal_blueprint()
    with patch("agents.blueprint_agent.scenario_plan.llama_available", return_value=False):
        enriched = enrich_blueprint_with_scenario_plan(blueprint, None)
    payload = enriched.model_dump(mode="json")

    llm_payload = {
        "questions": [
            {
                "order": 1,
                "question_text": "What about this AI Engineer role made you want to interview with us?",
                "intent": "motivation",
                "follow_up_hints": ["Listen for clarity"],
                "skill_tags": [],
            },
            {
                "order": 2,
                "question_text": (
                    "If your OCR service suddenly received a thousand PDFs at once, "
                    "how would you keep latency and errors under control?"
                ),
                "intent": "scale OCR",
                "follow_up_hints": ["Queues"],
                "skill_tags": ["OCR"],
            },
            {
                "order": 3,
                "question_text": (
                    "When OCR accuracy dropped in production, what failed first and how did you recover?"
                ),
                "intent": "failure OCR",
                "follow_up_hints": ["Monitoring"],
                "skill_tags": ["OCR"],
            },
            {
                "order": 4,
                "question_text": (
                    "On the PDF Pipeline work, what would you change first if a single file was two gigabytes?"
                ),
                "intent": "scale project",
                "follow_up_hints": ["Memory"],
                "skill_tags": ["PDF Pipeline"],
            },
            {
                "order": 5,
                "question_text": "How have you applied your MCA coursework on real OCR or document work?",
                "intent": "education",
                "follow_up_hints": ["Transfer"],
                "skill_tags": ["MCA"],
            },
        ]
    }

    with (
        patch("agents.interview_agent.adaptive.llama_available", return_value=True),
        patch("agents.interview_agent.adaptive.call_llama_json", return_value=llm_payload),
    ):
        questions = generate_questions_with_llama(
            payload,
            job_title="AI Engineer",
            resume_context={"skills": "OCR, Python", "resume_summary": "n/a"},
        )

    assert len(questions) == 5
    joined = " ".join(q.question_text for q in questions).casefold()
    assert "thousand pdfs" in joined or "thousand" in joined
    assert "two gigabytes" in joined or "gigabyte" in joined
    assert "motivated and research" not in joined
    assert all(is_spoken_interview_question(q.question_text) for q in questions)
