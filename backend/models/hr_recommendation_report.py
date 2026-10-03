"""Persisted Agent 7 HR recommendation reports."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class HrRecommendationReport(Base):
    __tablename__ = "hr_recommendation_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("candidate.candidate_id", ondelete="CASCADE"), index=True
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False, default="HOLD")
    overall_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    screening_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    interview_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="preliminary")
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    report_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
