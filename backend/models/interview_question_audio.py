"""Persisted Indic Parler-TTS audio metadata for interview questions."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class InterviewQuestionAudio(Base):
    __tablename__ = "interview_question_audio"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("candidate.candidate_id", ondelete="CASCADE"), index=True
    )
    question_set_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("interview_question_sets.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False, default="audio/wav")
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="indic_parler_tts")
    model: Mapped[str] = mapped_column(
        String(120), nullable=False, default="ai4bharat/indic-parler-tts"
    )
    voice: Mapped[str] = mapped_column(String(64), nullable=False, default="female")
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="READY")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
