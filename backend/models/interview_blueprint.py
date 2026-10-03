"""Interview blueprint model — Agent 3 output stored for Agent 4 handoff."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base

if TYPE_CHECKING:
    from models.candidate import Candidate


class InterviewBlueprint(Base):
    __tablename__ = "interview_blueprint"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("candidate.candidate_id"),
        nullable=False,
        index=True,
    )
    blueprint_version: Mapped[str] = mapped_column(String(16), nullable=False, default="3.1")
    candidate_level: Mapped[str] = mapped_column(String(32), nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    blueprint_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    candidate: Mapped["Candidate"] = relationship(back_populates="blueprints")
