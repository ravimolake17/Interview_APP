"""Persisted Agent 4 question set for a candidate interview."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class InterviewQuestionSet(Base):
    __tablename__ = "interview_question_sets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("candidate.candidate_id", ondelete="CASCADE"), index=True
    )
    blueprint_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("interview_blueprint.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUESTIONS_GENERATED")
    candidate_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    questions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
