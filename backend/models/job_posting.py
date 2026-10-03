"""Job posting model — roles stored from JD parsing or manual HR entry."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class JobPostingStatus(str, enum.Enum):
    ACTIVE = "Active"
    DRAFT = "Draft"
    CLOSED = "Closed"


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    experience: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[JobPostingStatus] = mapped_column(
        Enum(
            JobPostingStatus,
            name="job_posting_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=JobPostingStatus.ACTIVE,
    )
    jd_original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    jd_file_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    jd_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_jd: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
