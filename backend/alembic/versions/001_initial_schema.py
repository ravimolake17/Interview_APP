"""Initial database schema for Interview Scheduler Agent."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    candidate_status = postgresql.ENUM(
        "PENDING",
        "SHORTLISTED",
        "REJECTED",
        "INTERVIEW_SCHEDULED",
        name="candidate_status",
        create_type=False,
    )
    interview_status = postgresql.ENUM(
        "PENDING",
        "SCHEDULED",
        "COMPLETED",
        "CANCELLED",
        name="interview_status",
        create_type=False,
    )

    bind = op.get_bind()
    candidate_status.create(bind, checkfirst=True)
    interview_status.create(bind, checkfirst=True)

    op.create_table(
        "candidate",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("resume_score", sa.Float(), nullable=False),
        sa.Column("status", candidate_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id"),
    )
    op.create_index("ix_candidate_candidate_id", "candidate", ["candidate_id"])
    op.create_index("ix_candidate_email", "candidate", ["email"])

    op.create_table(
        "available_slots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("is_booked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("booked_candidate", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["booked_candidate"], ["candidate.candidate_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", "start_time", name="uq_slot_date_start"),
    )
    op.create_index("ix_available_slots_date", "available_slots", ["date"])

    op.create_table(
        "interview",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.String(length=64), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("scheduled_time", sa.Time(), nullable=False),
        sa.Column("meeting_link", sa.String(length=512), nullable=True),
        sa.Column("calendar_event_id", sa.String(length=256), nullable=True),
        sa.Column("status", interview_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate.candidate_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_candidate_id", "interview", ["candidate_id"])

    op.create_table(
        "schedule_token",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.String(length=64), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expiry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate.candidate_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index("ix_schedule_token_candidate_id", "schedule_token", ["candidate_id"])
    op.create_index("ix_schedule_token_token", "schedule_token", ["token"])


def downgrade() -> None:
    op.drop_table("schedule_token")
    op.drop_table("interview")
    op.drop_table("available_slots")
    op.drop_table("candidate")
    postgresql.ENUM(name="interview_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="candidate_status").drop(op.get_bind(), checkfirst=True)
