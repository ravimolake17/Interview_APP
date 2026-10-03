"""Schemas for HR job postings."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


JobStatusLiteral = Literal["Active", "Draft", "Closed"]


class JobPostingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    department: str | None = None
    experience: str | None = None
    location: str | None = None
    description: str | None = None
    skills: list[str] = Field(default_factory=list)
    status: JobStatusLiteral = "Active"
    jd_original_filename: str | None = None
    jd_file_url: str | None = None
    jd_text: str | None = None
    parsed_jd: dict[str, Any] | None = None
    on_duplicate: Literal["error", "replace", "rename"] = "error"


class JobPostingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    department: str | None = None
    experience: str | None = None
    location: str | None = None
    description: str | None = None
    skills: list[str] | None = None
    status: JobStatusLiteral | None = None
    jd_original_filename: str | None = None
    jd_file_url: str | None = None
    jd_text: str | None = None
    parsed_jd: dict[str, Any] | None = None


class JobApplicantSummary(BaseModel):
    candidate_id: str
    full_name: str


class JobPostingResponse(BaseModel):
    id: int
    title: str
    department: str | None = None
    experience: str | None = None
    location: str | None = None
    description: str | None = None
    skills: list[str] = Field(default_factory=list)
    status: JobStatusLiteral
    applicants: int = 0
    applicant_list: list[JobApplicantSummary] = Field(default_factory=list)
    jd_original_filename: str | None = None
    jd_file_url: str | None = None
    jd_text: str | None = None
    parsed_jd: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobPostingListResponse(BaseModel):
    total: int
    jobs: list[JobPostingResponse]


class JobDuplicateCheckResponse(BaseModel):
    duplicate: bool = False
    reason: Literal["title", "file"] | None = None
    existing: JobPostingResponse | None = None
