"""Central company (tenant) records. One database, shared tables, company_id isolation."""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class CompanyStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    logo: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Full company blurb from SuperAdmin; spoken version is shortened for TTS intro.
    interview_intro: Mapped[str | None] = mapped_column(Text, nullable=True)
    interview_intro_spoken: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=CompanyStatus.ACTIVE, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
