from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agents.screening_agent.config import settings
from agents.screening_agent.schemas.resume import ParsedResume


Decision = Literal["Shortlisted", "Needs Review", "Rejected"]
HardRequirementStatus = Literal["PASS", "FAIL", "N/A"]
ExperienceEntryType = Literal[
    "employment",
    "internship",
    "project",
    "research",
    "other",
]
# How the JD's experience minimum should be satisfied.
# professional/industry: employment only (internships/projects do NOT count)
# internship_included: employment + internship when JD explicitly allows internships
# relevant/hands_on: employment + internship + project + research (still labeled separately)
# any: any dated relevant exposure
ExperienceRequirementKind = Literal[
    "professional",
    "industry",
    "relevant",
    "hands_on",
    "internship_included",
    "any",
]


def _clean_strings(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value).split()).strip(" ,;|")
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            output.append(cleaned)
    return output


class SkillEvidence(BaseModel):
    raw_skill: str
    normalized_skill: str
    category: str
    section: str = ""
    source_text: str = ""


class SkillCollection(BaseModel):
    raw_skills: list[str] = Field(default_factory=list)
    normalized_skills: list[str] = Field(default_factory=list)
    skills_by_category: dict[str, list[str]] = Field(default_factory=dict)
    evidence: list[SkillEvidence] = Field(default_factory=list)

    @field_validator("raw_skills", "normalized_skills")
    @classmethod
    def clean_skill_lists(cls, value: list[str]) -> list[str]:
        return _clean_strings(value)


class SkillList(BaseModel):
    raw: list[str] = Field(default_factory=list)
    normalized: list[str] = Field(default_factory=list)

    @field_validator("raw", "normalized")
    @classmethod
    def clean_values(cls, value: list[str]) -> list[str]:
        return _clean_strings(value)


class ParsedJD(BaseModel):
    model_config = ConfigDict(extra="allow")

    job_title: str = ""
    required_skills: SkillList = Field(default_factory=SkillList)
    preferred_skills: SkillList = Field(default_factory=SkillList)
    responsibilities: list[str] = Field(default_factory=list)

    minimum_experience_years: float | None = Field(default=None, ge=0, le=100)
    maximum_experience_years: float | None = Field(default=None, ge=0, le=100)
    preferred_experience_years: float | None = Field(default=None, ge=0, le=100)

    experience_requirements: list[str] = Field(default_factory=list)
    skill_experience_requirements: list["SkillExperienceRequirement"] = Field(
        default_factory=list
    )
    # Conservative default: years-of-experience means professional employment.
    experience_requirement_kind: ExperienceRequirementKind = "professional"
    # True only when the JD explicitly says internships count toward the requirement.
    allows_internship_for_requirement: bool = False
    education_requirements: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    parsing_method: str = "rule_based"
    warnings: list[str] = Field(default_factory=list)

    @field_validator(
        "responsibilities",
        "experience_requirements",
        "education_requirements",
        "certifications",
        "keywords",
        "warnings",
    )
    @classmethod
    def clean_text_lists(cls, value: list[str]) -> list[str]:
        return _clean_strings(value)

    @field_validator("job_title", "parsing_method")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_experience_range(self) -> "ParsedJD":
        if (
            self.minimum_experience_years is not None
            and self.maximum_experience_years is not None
            and self.maximum_experience_years < self.minimum_experience_years
        ):
            raise ValueError(
                "maximum_experience_years cannot be less than minimum_experience_years."
            )
        return self


class CandidateDetails(BaseModel):
    name: str = ""
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return " ".join(value.split()).strip()

    @field_validator("emails", "phones", "links")
    @classmethod
    def clean_contact_lists(cls, value: list[str]) -> list[str]:
        return _clean_strings(value)


class ExperienceEntry(BaseModel):
    role: str = ""
    company: str = ""
    entry_type: ExperienceEntryType = "employment"
    source_section: str = ""
    start_date: str = ""
    end_date: str = ""
    start_month_index: int | None = Field(default=None, ge=0)
    end_month_index: int | None = Field(default=None, ge=0)
    duration_months: int | None = Field(default=None, ge=0, le=1200)
    duration_years: float | None = Field(default=None, ge=0, le=100)
    text: str = ""

    @model_validator(mode="after")
    def validate_duration(self) -> "ExperienceEntry":
        if self.start_month_index is not None and self.end_month_index is not None:
            if self.end_month_index < self.start_month_index:
                raise ValueError("Experience end date cannot precede its start date.")
            computed_months = self.end_month_index - self.start_month_index + 1
            self.duration_months = computed_months
            self.duration_years = round(computed_months / 12, 2)
        elif self.duration_months is not None:
            self.duration_years = round(self.duration_months / 12, 2)
        elif self.duration_years is not None:
            self.duration_months = int(round(self.duration_years * 12))
        return self


class CandidateProfile(BaseModel):
    candidate_details: CandidateDetails = Field(default_factory=CandidateDetails)
    skills: SkillCollection = Field(default_factory=SkillCollection)
    total_experience_years: float | None = Field(default=None, ge=0, le=100)
    experience_entries: list[ExperienceEntry] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    source_text: str = ""
    warnings: list[str] = Field(default_factory=list)


MatchLevel = Literal[
    "EXACT_MATCH",
    "STRONG_SEMANTIC_MATCH",
    "PARTIAL_MATCH",
    "MISSING",
]


class SemanticSkillMatch(BaseModel):
    """Evidence for one JD skill → best resume skill alignment."""

    jd_skill: str
    matched_resume_skill: str | None = None
    similarity: float = Field(default=0.0, ge=0, le=1)
    match_status: str = "No Match"
    match_level: MatchLevel = "MISSING"
    matched: bool = False
    match_method: str = "none"  # exact | lexical | semantic | partial | none
    evidence: str = ""

    @field_validator("jd_skill")
    @classmethod
    def clean_jd_skill(cls, value: str) -> str:
        cleaned = " ".join(str(value).split()).strip(" ,;|")
        if not cleaned:
            raise ValueError("jd_skill must not be empty.")
        return cleaned


class ResponsibilityMatch(BaseModel):
    jd_responsibility: str
    match_status: Literal["STRONG_MATCH", "PARTIAL_MATCH", "WEAK_MATCH", "UNSUPPORTED"] = (
        "UNSUPPORTED"
    )
    priority: Literal["CORE", "IMPORTANT", "SUPPORTING"] = "IMPORTANT"
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    reason: str = ""


class SkillExperienceRequirement(BaseModel):
    skill_or_domain: str
    minimum_years: float | None = Field(default=None, ge=0, le=100)
    maximum_years: float | None = Field(default=None, ge=0, le=100)
    is_preferred: bool = False
    source_text: str = ""


class SkillExperienceAssessment(BaseModel):
    skill_or_domain: str
    source_text: str = ""
    minimum_years: float | None = Field(default=None, ge=0, le=100)
    maximum_years: float | None = Field(default=None, ge=0, le=100)
    is_preferred: bool = False
    candidate_years: float = Field(default=0.0, ge=0, le=100)
    explicit_dated_years: float = Field(default=0.0, ge=0, le=100)
    strong_dated_years: float = Field(default=0.0, ge=0, le=100)
    undated_years: float = Field(default=0.0, ge=0, le=100)
    supported_years: float = Field(default=0.0, ge=0, le=100)
    evidence_kind: str = "NO_EVIDENCE"
    meets_minimum: bool | None = None
    evidence: list["ExperienceEntryAssessment"] = Field(default_factory=list)
    reason: str = ""


class MatchAnalysis(BaseModel):
    matched_required_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    matched_preferred_skills: list[str] = Field(default_factory=list)
    missing_preferred_skills: list[str] = Field(default_factory=list)
    partial_required_skills: list[str] = Field(default_factory=list)
    partial_preferred_skills: list[str] = Field(default_factory=list)
    additional_candidate_skills: list[str] = Field(default_factory=list)
    required_match_ratio: float = Field(default=1.0, ge=0, le=1)
    preferred_match_ratio: float = Field(default=1.0, ge=0, le=1)
    semantic_matching_enabled: bool = False
    semantic_required_matches: list[SemanticSkillMatch] = Field(default_factory=list)
    semantic_preferred_matches: list[SemanticSkillMatch] = Field(default_factory=list)

    @field_validator(
        "matched_required_skills",
        "missing_required_skills",
        "matched_preferred_skills",
        "missing_preferred_skills",
        "partial_required_skills",
        "partial_preferred_skills",
        "additional_candidate_skills",
    )
    @classmethod
    def clean_match_lists(cls, value: list[str]) -> list[str]:
        return _clean_strings(value)


class ExperienceEntryAssessment(BaseModel):
    role: str = ""
    company: str = ""
    entry_type: ExperienceEntryType = "employment"
    date_range: str = ""
    duration_years: float | None = Field(default=None, ge=0, le=100)
    matched_signals: list[str] = Field(default_factory=list)
    reason: str = ""


class ExperienceAssessment(BaseModel):
    jd_requirement: str = ""
    minimum_required_years: float | None = Field(default=None, ge=0, le=100)
    maximum_required_years: float | None = Field(default=None, ge=0, le=100)
    candidate_total_experience_years: float | None = Field(default=None, ge=0, le=100)
    candidate_relevant_experience_years: float = Field(default=0.0, ge=0, le=100)
    unrelated_experience_years: float = Field(default=0.0, ge=0, le=100)
    # Type-separated relevant exposure (overlap-merged within each type).
    professional_experience_years: float = Field(default=0.0, ge=0, le=100)
    internship_experience_years: float = Field(default=0.0, ge=0, le=100)
    research_experience_years: float = Field(default=0.0, ge=0, le=100)
    academic_project_years: float = Field(default=0.0, ge=0, le=100)
    relevant_hands_on_experience_years: float = Field(default=0.0, ge=0, le=100)
    supporting_exposure_years: float = Field(default=0.0, ge=0, le=100)
    skill_experience_assessments: list[SkillExperienceAssessment] = Field(
        default_factory=list
    )
    # Years used to evaluate the JD minimum (depends on experience_requirement_kind).
    years_toward_requirement: float = Field(default=0.0, ge=0, le=100)
    experience_requirement_kind: ExperienceRequirementKind = "professional"
    allows_internship_for_requirement: bool = False
    meets_minimum: bool | None = None
    result: str = ""
    counted_experience: list[ExperienceEntryAssessment] = Field(default_factory=list)
    excluded_experience: list[ExperienceEntryAssessment] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    overall_score: float = Field(ge=0, le=100)
    skill_match_score: float = Field(ge=0, le=100)
    required_skill_score: float = Field(ge=0, le=100)
    preferred_skill_score: float = Field(ge=0, le=100)
    experience_score: float = Field(ge=0, le=100)
    education_score: float = Field(ge=0, le=100)
    keyword_score: float = Field(ge=0, le=100)
    responsibility_score: float = Field(default=0.0, ge=0, le=100)
    responsibility_matches: list[ResponsibilityMatch] = Field(default_factory=list)
    experience_assessment: ExperienceAssessment = Field(
        default_factory=ExperienceAssessment
    )
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    partial_skills: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    recommendation: str
    decision: Decision
    hard_requirement_status: HardRequirementStatus = "N/A"
    hard_requirement_reasons: list[str] = Field(default_factory=list)
    score_weights: dict[str, float] = Field(default_factory=dict)


class SchedulingInfo(BaseModel):
    """Returned when a shortlisted candidate is auto-scheduled by Agent 2."""

    candidate_id: str
    scheduling_link: str
    token: str
    interview_status: str
    message: str
    blueprint_id: int | None = None
    candidate_level: str | None = None
    total_questions: int | None = None


class EvaluationResponse(BaseModel):
    candidate_details: CandidateDetails
    candidate_experience_years: float | None = Field(default=None, ge=0, le=100)
    candidate_relevant_experience_years: float = Field(default=0.0, ge=0, le=100)
    candidate_education: list[str] = Field(default_factory=list)
    candidate_certifications: list[str] = Field(default_factory=list)
    extracted_resume_skills: SkillCollection
    extracted_jd_requirements: ParsedJD
    match_analysis: MatchAnalysis
    experience_assessment: ExperienceAssessment = Field(
        default_factory=ExperienceAssessment
    )
    score_breakdown: ScoreBreakdown
    final_recommendation: str
    shortlist_status: Decision
    scheduling: SchedulingInfo | None = None
    saved_candidate_id: str | None = None
    persist_warning: str | None = None


class ScreeningJobAcceptedResponse(BaseModel):
    job_id: str
    status: Literal["pending"] = "pending"
    message: str = "Evaluation queued for processing."
    poll_url: str


class ExtractJobResult(BaseModel):
    kind: Literal["extract"] = "extract"
    original_filename: str = ""
    stored_file_url: str = ""
    pages: int = Field(default=0, ge=0)
    parsed_data: ParsedResume | None = None
    scoring_job_id: str | None = None
    extraction_warning: str = ""


class ScreeningJobDetailResponse(BaseModel):
    job_id: str
    status: Literal["pending", "processing", "completed", "failed"]
    result: EvaluationResponse | None = None
    extraction: ExtractJobResult | None = None
    scoring_job_id: str | None = None
    error: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class ScreeningBatchAcceptedResponse(BaseModel):
    total: int
    jobs: list[ScreeningJobAcceptedResponse]


class ScreeningQueueStatsResponse(BaseModel):
    pending: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    max_concurrent_workers: int


class JDUploadResponse(BaseModel):
    status: Literal["success"] = "success"
    original_filename: str = ""
    stored_file_url: str = ""
    jd_text: str
    parsed_jd: ParsedJD


class JDParseRequest(BaseModel):
    jd_text: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_text(self) -> "JDParseRequest":
        self.jd_text = self.jd_text.strip()
        if not self.jd_text:
            raise ValueError("JD text cannot be empty.")
        if len(self.jd_text) > settings.MAX_JD_TEXT_CHARS:
            raise ValueError(
                f"JD text exceeds the {settings.MAX_JD_TEXT_CHARS:,}-character limit."
            )
        return self


class MatchingAnalyzeRequest(BaseModel):
    candidate_skills: SkillCollection
    parsed_jd: ParsedJD


class CandidateScoreRequest(BaseModel):
    candidate_profile: CandidateProfile
    parsed_jd: ParsedJD
    match_analysis: MatchAnalysis | None = None


class CandidateEvaluateRequest(BaseModel):
    parsed_resume: ParsedResume
    jd_text: str | None = None
    parsed_jd: ParsedJD | None = None
    resume_original_filename: str | None = None
    resume_file_url: str | None = None
    jd_original_filename: str | None = None
    jd_file_url: str | None = None
    jd_source_text: str | None = None
    audit_context: dict | None = None
    company_id: int | None = None
    send_invite_email: bool = True

    @model_validator(mode="after")
    def validate_jd_input(self) -> "CandidateEvaluateRequest":
        has_text = bool(self.jd_text and self.jd_text.strip())
        has_parsed = self.parsed_jd is not None

        if has_text == has_parsed:
            raise ValueError("Provide exactly one of jd_text or parsed_jd.")

        if has_text:
            self.jd_text = self.jd_text.strip()
            if len(self.jd_text) > settings.MAX_JD_TEXT_CHARS:
                raise ValueError(
                    f"JD text exceeds the {settings.MAX_JD_TEXT_CHARS:,}-character limit."
                )

        if self.jd_source_text:
            self.jd_source_text = self.jd_source_text.strip()

        return self
