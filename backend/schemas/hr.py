"""Pydantic schemas for HR candidate management."""

from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class HRCandidateSummary(BaseModel):
    candidate_id: str
    full_name: str
    email: str
    phone: str | None = None
    resume_score: float
    job_position: str | None = None
    status: str
    created_at: datetime
    resume_original_filename: str | None = None
    resume_file_url: str | None = None
    jd_original_filename: str | None = None
    jd_file_url: str | None = None
    interview_scheduled: bool = False
    interview_completed: bool = False
    invite_used: bool = False
    invite_sent: bool = False
    can_resend_invite: bool = False
    email_missing: bool = False
    can_edit_email: bool = False
    experience_summary: str | None = None
    education_summary: str | None = None
    interview_result: str | None = None

    model_config = {"from_attributes": True}


class HRCandidateListResponse(BaseModel):
    status_filter: str
    total: int
    candidates: list[HRCandidateSummary]


class HRCandidateDetailResponse(HRCandidateSummary):
    jd_text: str | None = None
    evaluation_snapshot: dict[str, Any] | None = None
    final_recommendation: str | None = None
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    resume_sections: list[dict[str, Any]] = Field(default_factory=list)
    resume_text: str = ""
    scheduled_date: date | None = None
    scheduled_time: time | None = None
    meeting_link: str | None = None
    join_link: str | None = None
    calendar_event_id: str | None = None


class UpdateCandidateEmailRequest(BaseModel):
    email: EmailStr


class UpdateCandidateEmailResponse(BaseModel):
    message: str
    candidate_id: str
    email: str


class ShortlistActionResponse(BaseModel):
    message: str
    candidate_id: str
    status: str
    scheduling_link: str | None = None
    token: str | None = None


class ResendInviteResponse(BaseModel):
    message: str
    candidate_id: str
    scheduling_link: str
    token: str


class InviteDeliveryCandidate(BaseModel):
    candidate_id: str
    full_name: str
    email: str
    job_position: str | None = None
    invite_sent: bool = False
    can_resend: bool = False


class InviteDeliveryStats(BaseModel):
    issued: int = 0
    not_issued: int = 0
    awaiting_booking: int = 0
    booked: int = 0
    candidates: list[InviteDeliveryCandidate] = Field(default_factory=list)


class RejectActionResponse(BaseModel):
    message: str
    candidate_id: str
    status: str


class AuditLogEntry(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: str | None = None
    user_id: int | None = None
    user_email: str | None = None
    user_name: str | None = None
    user_role: str | None = None
    details: dict[str, Any] | None = None
    old_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    status: str = "SUCCESS"
    location: str | None = None
    company_id: int | None = None
    company_name: str | None = None
    message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    total: int
    entries: list[AuditLogEntry]


class DashboardStatsResponse(BaseModel):
    total_candidates: int = 0
    active_jobs: int = 0
    ai_screened: int = 0
    pending_reviews: int = 0
    shortlisted: int = 0
    rejected: int = 0
    interview_scheduled: int = 0
    interview_completed: int = 0
    average_match_score: float = 0.0
    status_distribution: list[dict[str, Any]] = Field(default_factory=list)
    applications_per_job: list[dict[str, Any]] = Field(default_factory=list)
    match_trend: list[dict[str, Any]] = Field(default_factory=list)
    top_skills: list[dict[str, Any]] = Field(default_factory=list)
    hiring_funnel: list[dict[str, Any]] = Field(default_factory=list)
    invite_delivery: InviteDeliveryStats = Field(default_factory=InviteDeliveryStats)
