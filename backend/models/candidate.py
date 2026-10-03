"""Candidate model — populated by Agent 1 (Resume Screening)."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base

if TYPE_CHECKING:
    from models.interview import Interview
    from models.interview_blueprint import InterviewBlueprint
    from models.schedule_token import ScheduleToken


class CandidateStatus(str, enum.Enum):
    PENDING = "PENDING"
    SHORTLISTED = "SHORTLISTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REJECTED = "REJECTED"
    INTERVIEW_SCHEDULED = "INTERVIEW_SCHEDULED"
    INTERVIEW_COMPLETED = "INTERVIEW_COMPLETED"


class Candidate(Base):
    __tablename__ = "candidate"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resume_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    job_position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[CandidateStatus] = mapped_column(
        Enum(CandidateStatus, name="candidate_status"),
        nullable=False,
        default=CandidateStatus.PENDING,
    )
    jd_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resume_original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resume_file_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    jd_original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    jd_file_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    interviews: Mapped[list["Interview"]] = relationship(back_populates="candidate")
    schedule_tokens: Mapped[list["ScheduleToken"]] = relationship(back_populates="candidate")
    blueprints: Mapped[list["InterviewBlueprint"]] = relationship(back_populates="candidate")
