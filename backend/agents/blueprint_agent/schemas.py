from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.config import get_settings


CandidateLevel = Literal["Fresher", "Entry-level", "Junior", "Mid-level", "Senior"]
Difficulty = Literal["easy", "medium", "hard"]

BlueprintCategory = Literal[
    "introductory_questions",
    "skills_jd_keyword_questions",
    "project_related_questions",
    "education_courses_questions",
]

SkillPriority = Literal["critical", "high", "medium", "low"]

SkillSource = Literal[
    "matched_required",
    "matched_preferred",
    "missing_required",
    "missing_preferred",
    "resume_only_relevant",
    "jd_only",
]


CATEGORY_DISPLAY_ORDER: list[str] = [
    "Introductory Questions",
    "Skills & JD Keyword-related Questions",
    "Project-related Questions",
    "Education & Courses-related Questions",
]


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _clean_string_list(value: Any) -> list[str]:
    if value is None:
        return []

    values = value if isinstance(value, list) else [value]

    output: list[str] = []
    seen: set[str] = set()

    for item in values:
        cleaned = _clean_text(item).strip(" ,;|")
        key = cleaned.casefold()

        if cleaned and key not in seen:
            seen.add(key)
            output.append(cleaned)

    return output


class AtsMatchResult(BaseModel):
    """
    Trusted ATS match result consumed by Agent 3.

    Agent 3 does not recalculate ATS score.
    It only reads score/status/matched/missing skills.
    """

    model_config = ConfigDict(extra="allow")

    overall_score: float = Field(ge=0, le=100)
    status: str = Field(min_length=1)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    weak_areas: list[str] = Field(default_factory=list)

    @field_validator("status", mode="before")
    @classmethod
    def strip_status(cls, value: Any) -> str:
        cleaned = _clean_text(value)
        if not cleaned:
            raise ValueError("ats_match_result.status is required.")
        return cleaned

    @field_validator("matched_skills", "missing_skills", "weak_areas", mode="before")
    @classmethod
    def normalize_string_list(cls, value: Any) -> list[str]:
        return _clean_string_list(value)


class InterviewBlueprintRequest(BaseModel):
    """
    Request body for Agent 3 blueprint generator.

    Agent 3 consumes existing upstream data:
    - resume_json
    - jd_text / jd_json
    - ats_match_result
    - optional ats_evaluation_result

    Optional HR overrides:
    - candidate_level — force interview depth band
    - total_duration_minutes — force total interview length
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    resume_json: dict[str, Any] = Field(default_factory=dict)
    jd_text: str = ""
    jd_json: dict[str, Any] = Field(default_factory=dict)
    ats_match_result: AtsMatchResult
    ats_evaluation_result: dict[str, Any] = Field(default_factory=dict)
    candidate_level: CandidateLevel | None = None
    total_duration_minutes: int | None = Field(default=None, ge=10, le=120)

    @model_validator(mode="after")
    def validate_inputs(self) -> "InterviewBlueprintRequest":
        self.jd_text = self.jd_text.strip()

        if self.jd_text and len(self.jd_text) > get_settings().blueprint_max_jd_text_chars:
            raise ValueError(
                f"JD text exceeds the {get_settings().blueprint_max_jd_text_chars:,}-character limit."
            )

        if not self.resume_json:
            raise ValueError("resume_json is required.")

        if not self.jd_text and not self.jd_json:
            # Screening may save a shortlisted candidate before a JD is extracted.
            # Agent 3/4 must still run after a late invite and slot booking.
            self.jd_text = (
                "Open Role\n\nJob description was not extracted. "
                "Plan a general competency interview using the resume and ATS match."
            )
            self.jd_json = {"job_title": "Open Role", "responsibilities": []}

        return self


class DifficultyDistribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    easy: int = Field(ge=0)
    medium: int = Field(ge=0)
    hard: int = Field(ge=0)
    reasoning: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_questions(self) -> "DifficultyDistribution":
        if self.easy + self.medium + self.hard <= 0:
            raise ValueError("Difficulty distribution must contain at least one question.")
        return self


class CategoryBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: int = Field(ge=1, le=4)
    category_id: BlueprintCategory
    category_name: str = Field(min_length=1)
    question_count: int = Field(ge=1)
    difficulty_mix: dict[str, int]
    estimated_minutes: int = Field(ge=1)
    time_percentage: float = Field(ge=0, le=100)

    question_type_focus: list[str] = Field(default_factory=list)
    purpose: str = Field(min_length=1)
    selection_reason: str = Field(min_length=1)

    candidate_resume_signals: list[str] = Field(default_factory=list)
    jd_signals: list[str] = Field(default_factory=list)
    cross_reference_basis: list[str] = Field(default_factory=list)

    agent4_generation_instruction: str = Field(min_length=1)

    @field_validator(
        "category_name",
        "purpose",
        "selection_reason",
        "agent4_generation_instruction",
        mode="before",
    )
    @classmethod
    def clean_text_fields(cls, value: Any) -> str:
        return _clean_text(value)

    @field_validator(
        "question_type_focus",
        "candidate_resume_signals",
        "jd_signals",
        "cross_reference_basis",
        mode="before",
    )
    @classmethod
    def clean_lists(cls, value: Any) -> list[str]:
        return _clean_string_list(value)

    @model_validator(mode="after")
    def validate_mix_sum(self) -> "CategoryBreakdown":
        total = sum(int(value) for value in self.difficulty_mix.values())

        if total != self.question_count:
            raise ValueError(
                f"difficulty_mix for {self.category_id} must sum to question_count."
            )

        return self


class TimeAllocation(BaseModel):
    """
    Time is holistic interview-level time.

    It is not fixed/equal time per question.
    Category minutes are calculated from resume depth, JD complexity,
    category importance, projects, education, skills, and candidate-JD match.
    """

    model_config = ConfigDict(extra="forbid")

    total_duration_minutes: int = Field(ge=10, le=120)
    buffer_minutes: int = Field(ge=0)
    category_minutes: dict[str, int] = Field(default_factory=dict)
    category_percentages: dict[str, float] = Field(default_factory=dict)
    time_distribution_basis: list[str] = Field(default_factory=list)
    reasoning: str = Field(min_length=1)

    @field_validator("reasoning", mode="before")
    @classmethod
    def clean_reasoning(cls, value: Any) -> str:
        return _clean_text(value)

    @field_validator("time_distribution_basis", mode="before")
    @classmethod
    def clean_basis(cls, value: Any) -> list[str]:
        return _clean_string_list(value)


class SkillFocusPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_name: str = Field(min_length=1)
    source: SkillSource
    priority: SkillPriority
    planned_question_count: int = Field(ge=0)
    difficulty_focus: list[Difficulty] = Field(default_factory=list)
    validation_goal: str = Field(min_length=1)
    resume_evidence: str = ""
    jd_evidence: str = ""
    related_keywords: list[str] = Field(default_factory=list)

    @field_validator(
        "skill_name",
        "validation_goal",
        "resume_evidence",
        "jd_evidence",
        mode="before",
    )
    @classmethod
    def clean_text_fields(cls, value: Any) -> str:
        return _clean_text(value)

    @field_validator("related_keywords", mode="before")
    @classmethod
    def clean_keywords(cls, value: Any) -> list[str]:
        return _clean_string_list(value)


class FlowStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_order: int = Field(ge=1)
    stage_name: str = Field(min_length=1)
    category_ids: list[BlueprintCategory] = Field(default_factory=list)
    question_count: int = Field(ge=0)
    estimated_minutes: int = Field(ge=0)
    interviewer_action: str = Field(min_length=1)

    @field_validator("stage_name", "interviewer_action", mode="before")
    @classmethod
    def clean_text_fields(cls, value: Any) -> str:
        return _clean_text(value)


class DecisionFactor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    factor: str = Field(min_length=1)
    observed_value: str = Field(min_length=1)
    impact: str = Field(min_length=1)

    @field_validator("factor", "observed_value", "impact", mode="before")
    @classmethod
    def clean_text_fields(cls, value: Any) -> str:
        return _clean_text(value)


class Agent4Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consumer: str = "Agent 4 live interview engine"
    output_contract: str = "blueprint_only_no_actual_questions"
    should_generate_actual_questions: bool = True
    should_recalculate_ats_score: bool = False
    required_category_order: list[str] = Field(
        default_factory=lambda: CATEGORY_DISPLAY_ORDER.copy()
    )
    required_inputs_for_agent4: list[str] = Field(
        default_factory=lambda: [
            "category_breakdown",
            "skill_focus_plan",
            "difficulty_distribution",
            "interview_flow",
            "time_allocation",
            "resume_json",
            "jd_json_or_jd_text",
            "ats_match_result",
        ]
    )
    guardrails: list[str] = Field(default_factory=list)


class HumanReadableReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    recommended_flow: list[str] = Field(default_factory=list)
    interviewer_notes: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)

    @field_validator("summary", mode="before")
    @classmethod
    def clean_summary(cls, value: Any) -> str:
        return _clean_text(value)

    @field_validator("recommended_flow", "interviewer_notes", "risk_flags", mode="before")
    @classmethod
    def clean_lists(cls, value: Any) -> list[str]:
        return _clean_string_list(value)


class InputSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_title: str = ""
    ats_score: float = Field(ge=0, le=100)
    ats_status: str = Field(min_length=1)

    candidate_experience_years: float | None = Field(default=None, ge=0, le=100)
    candidate_relevant_experience_years: float | None = Field(default=None, ge=0, le=100)
    jd_required_experience_years: float | None = Field(default=None, ge=0, le=100)

    resume_word_count: int = Field(ge=0)
    resume_depth_label: str = Field(min_length=1)

    jd_word_count: int = Field(ge=0)
    jd_complexity_label: str = Field(min_length=1)

    matched_skills_count: int = Field(ge=0)
    missing_skills_count: int = Field(ge=0)
    jd_required_skills_count: int = Field(ge=0)
    jd_preferred_skills_count: int = Field(ge=0)

    project_evidence_count: int = Field(ge=0)
    education_course_evidence_count: int = Field(ge=0)


class InterviewBlueprintResponse(BaseModel):
    """
    Agent 3 output.

    This is Interview Blueprint Report only.
    It does not contain final interview questions.
    """

    model_config = ConfigDict(extra="forbid")

    blueprint_version: str = "3.1"
    generation_source: str = "deterministic_agent3_blueprint_logic"

    category_order: list[str] = Field(
        default_factory=lambda: CATEGORY_DISPLAY_ORDER.copy()
    )

    candidate_level: CandidateLevel
    input_summary: InputSummary

    total_questions: int = Field(ge=4, le=60)
    difficulty_distribution: DifficultyDistribution

    category_breakdown: list[CategoryBreakdown] = Field(min_length=4, max_length=4)
    time_allocation: TimeAllocation

    skill_focus_plan: list[SkillFocusPlan] = Field(default_factory=list)
    interview_flow: list[FlowStep] = Field(default_factory=list)
    decision_factors: list[DecisionFactor] = Field(default_factory=list)

    agent4_metadata: Agent4Metadata = Field(default_factory=Agent4Metadata)
    human_readable_report: HumanReadableReport

    @model_validator(mode="after")
    def validate_blueprint_totals(self) -> "InterviewBlueprintResponse":
        difficulty_total = (
            self.difficulty_distribution.easy
            + self.difficulty_distribution.medium
            + self.difficulty_distribution.hard
        )

        if difficulty_total != self.total_questions:
            raise ValueError("difficulty_distribution must sum to total_questions.")

        category_total = sum(item.question_count for item in self.category_breakdown)

        if category_total != self.total_questions:
            raise ValueError(
                "category_breakdown question counts must sum to total_questions."
            )

        actual_order = [item.category_name for item in self.category_breakdown]

        if actual_order != CATEGORY_DISPLAY_ORDER:
            raise ValueError(
                "category_breakdown must follow the required category order exactly."
            )

        flow_total = sum(item.question_count for item in self.interview_flow)

        if self.interview_flow and flow_total != self.total_questions:
            raise ValueError("interview_flow question counts must sum to total_questions.")

        category_minutes = sum(self.time_allocation.category_minutes.values())
        expected_category_minutes = (
            self.time_allocation.total_duration_minutes
            - self.time_allocation.buffer_minutes
        )

        if category_minutes != expected_category_minutes:
            raise ValueError(
                "time_allocation.category_minutes must sum to "
                "total_duration_minutes - buffer_minutes."
            )

        return self


# Backward compatibility.
# Older routes/imports may still use these names.
InterviewQuestionRequest = InterviewBlueprintRequest
InterviewQuestionResponse = InterviewBlueprintResponse
