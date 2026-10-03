"""Persisted Agent 6 evaluation turns for a candidate interview."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class InterviewEvaluation(Base):
    __tablename__ = "interview_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("candidate.candidate_id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    answer_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False, default="adequate")
    evaluation_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
