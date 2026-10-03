"""Pydantic schemas for interview scheduling API."""

from datetime import date, datetime, time

from pydantic import BaseModel, Field


class SendInviteRequest(BaseModel):
    candidate_id: str = Field(..., description="Unique candidate identifier from Agent 1")


class SendInviteResponse(BaseModel):
    message: str
    thread_id: str
    token: str
    scheduling_link: str


class BookSlotRequest(BaseModel):
    token: str
    slot_id: int


class BookSlotResponse(BaseModel):
    message: str
    interview_date: date
    interview_time: time
    join_link: str | None = None
    status: str


class JoinInterviewResponse(BaseModel):
    candidate_id: str
    candidate_name: str
    interview_date: date
    interview_time: time
    session_id: str
    agent5_token: str
    proctoring_url: str
    participant_role: str = "candidate"
    company_name: str | None = None
    company_code: str | None = None


class SlotResponse(BaseModel):
    id: int
    date: date
    start_time: time
    end_time: time
    is_booked: bool

    model_config = {"from_attributes": True}


class TokenValidationResponse(BaseModel):
    valid: bool
    candidate_id: str | None = None
    full_name: str | None = None
    email: str | None = None
    job_position: str | None = None
    resume_score: float | None = None
    already_booked: bool = False
    error: str | None = None
    company_name: str | None = None
    company_code: str | None = None
    slots: list[SlotResponse] = []
    server_now: datetime | None = None
    server_today: date | None = None
    timezone: str | None = None


class InterviewDetailsResponse(BaseModel):
    candidate_id: str
    full_name: str
    email: str
    job_position: str | None = None
    scheduled_date: date | None = None
    scheduled_time: time | None = None
    meeting_link: str | None = None
    join_link: str | None = None
    calendar_event_id: str | None = None
    status: str
    created_at: datetime | None = None


class CalendarInterviewResponse(BaseModel):
    interview_id: int
    candidate_id: str
    candidate_name: str
    candidate_email: str
    job_position: str | None = None
    scheduled_date: date
    start_time: time
    end_time: time
    meeting_link: str | None = None
    status: str


class CalendarWeekResponse(BaseModel):
    week_start: date
    week_end: date
    interviews: list[CalendarInterviewResponse]
    server_now: datetime | None = None
    server_today: date | None = None
    timezone: str | None = None
